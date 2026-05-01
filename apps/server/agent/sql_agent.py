"""Text-to-SQL 에이전트 — 2단계 모델 파이프라인 + 재시도 금지.

Step 1 (Haiku, cheap):
    `extract_intent_and_tables()` — 유저 질문에서 intent와 관련 테이블/컬럼을 JSON으로 추출.
    intent가 allowlist에 매칭되면 상위 라우터는 `intent_to_sql`로 템플릿 SQL을 생성하고
    Step 2를 완전히 스킵한다.

Step 2 (Sonnet/Opus, good):
    `text_to_sql()` — retrieved_schema만 주입된 시스템 프롬프트로 SQL을 생성.
    응답의 markdown 코드블록을 제거한 뒤 `validate_sql`을 통과해야 한다.

재시도 금지 원칙:
    - validate_sql이 ValueError raise 시 catch 금지. 즉시 상위로 전파.
    - Claude API 오류도 재호출 금지 — 원래 예외를 그대로 전파하거나 RuntimeError로 wrap.

generate_answer (Haiku):
    쿼리 결과를 한국어 자연어로 요약. 5건 이하는 인라인, 5건 초과는 상위 3건 + 총 N건.

모든 함수는 동기(sync). FastAPI 서비스 레이어에서 executor로 실행된다.
"""

from __future__ import annotations

import json
import re
from typing import Any

from anthropic import Anthropic

from agent.intent_mapper import SUPPORTED_INTENTS
from agent.prompts import build_system_prompt, format_context_hint
from agent.schema_retrieval import retrieve_relevant_schema
from agent.validators import validate_sql
from config import settings

# --- 내부 상수 ----------------------------------------------------------------

_MAX_HISTORY_TURNS = 5
_INLINE_ROW_THRESHOLD = 5
_SUMMARY_TOP_N = 3

_CODEBLOCK_RE = re.compile(
    r"^```(?:sql|SQL|postgres|postgresql)?\s*\n?(?P<body>.*?)\n?```$",
    re.DOTALL,
)


# --- 클라이언트 접근 ----------------------------------------------------------

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    """모듈 싱글턴 Anthropic 클라이언트. 테스트는 monkeypatch로 교체 가능."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


# --- 유틸 ---------------------------------------------------------------------


def _last_user_message(messages: list[dict]) -> str:
    """messages에서 마지막 user turn의 content(str) 추출."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [p.get("text", "") for p in content if isinstance(p, dict)]
                return " ".join(parts)
    return ""


def _slice_recent_messages(messages: list[dict]) -> list[dict]:
    """최근 N턴만 반환 (system 메시지 제외)."""
    non_system = [m for m in messages if m.get("role") != "system"]
    return non_system[-_MAX_HISTORY_TURNS:]


def _strip_code_fence(text: str) -> str:
    """응답의 markdown 코드블록(```sql ... ``` 또는 ``` ... ```) 제거."""
    stripped = text.strip()
    match = _CODEBLOCK_RE.match(stripped)
    if match:
        return match.group("body").strip()
    return stripped


def _coerce_intent(raw: Any) -> dict | None:
    """LLM이 반환한 intent dict가 SUPPORTED_INTENTS 매칭되는지 확인.

    매칭 실패 시 None을 반환해 상위 라우터가 Step 2로 진행하도록 한다.
    """
    if not isinstance(raw, dict):
        return None
    intent_type = raw.get("type")
    if not isinstance(intent_type, str):
        return None
    if intent_type not in SUPPORTED_INTENTS:
        return None
    return raw


def _coerce_schema(raw: Any) -> dict[str, list[str]] | None:
    """LLM이 반환한 tables dict를 정규화. 실패 시 None."""
    if not isinstance(raw, dict):
        return None
    result: dict[str, list[str]] = {}
    for table, cols in raw.items():
        if not isinstance(table, str):
            continue
        if not isinstance(cols, list):
            continue
        str_cols = [c for c in cols if isinstance(c, str)]
        if str_cols:
            result[table] = str_cols
    return result or None


def _apply_context_defaults(intent: dict | None, context: dict | None) -> dict | None:
    """LLM이 채우지 못한 intent 슬롯을 시뮬레이터 컨텍스트로 보충.

    Q1 결정 — 사용자 명시값(LLM이 추출한 값)이 있으면 절대 덮어쓰지 않는다.
    region(시군구)만 결정론적으로 보충하고, total_budget은 LLM 판단에 맡긴다 (Q2).
    """
    if intent is None or not context:
        return intent
    region = context.get("region")
    if isinstance(region, str) and region.strip() and intent.get("region") is None:
        intent["region"] = region.strip()
    return intent


# --- Step 1 -------------------------------------------------------------------

_STEP1_SYSTEM_PROMPT = """\
당신은 부동산 실거래 DB 질문 분석기입니다. 유저 질문을 읽고 아래 형식의
**JSON만** 반환하세요. 다른 문장/코드블록 금지.

{
  "intent": {
    "type": "<SUPPORTED_INTENTS 중 하나 또는 null>",
    "region": "<시/군/구 또는 null>",
    "sido": "<시/도 또는 null>",
    "year": <연도 또는 null>,
    "max_price": <만원 단위 정수 또는 null>,
    "limit": <1~100 정수 또는 null>
  },
  "tables": {
    "<table_name>": ["<column>", ...],
    ...
  }
}

규칙:
- intent.type 은 다음 중 하나여야 매칭된 것으로 간주됩니다. 확실하지 않으면 null.
  recent_transactions, avg_price_by_region, monthly_trend, price_filter, top_apartments
- tables 는 질문에 답하기 위해 필요한 테이블과 최소 컬럼만. 허용 테이블:
  sales_transactions, apartments, regions
- 추측 금지. 모르면 해당 필드를 null로 두세요.
"""


def extract_intent_and_tables(
    messages: list[dict],
    context: dict | None,
) -> tuple[dict | None, dict[str, list[str]]]:
    """Step 1 — Haiku 1회 호출로 intent와 관련 스키마 추출.

    Args:
        messages: Chat 턴 목록. 마지막 user 메시지 기준으로 분석.
        context: 시뮬레이터 컨텍스트 (`{region?, total_budget?}`).
            시스템 프롬프트의 보조 섹션으로 부착되며, intent의 region 슬롯이 비어 있으면
            컨텍스트의 region으로 결정론적으로 보충한다 (질문에 명시된 값은 절대 덮어쓰지 않음).

    Returns:
        (intent, retrieved_schema) 튜플.
        - intent: SUPPORTED_INTENTS에 매칭된 dict 또는 None.
        - retrieved_schema: LLM이 반환한 스키마 → 정규화 실패 시 keyword 기반 fallback.

    Raises:
        anthropic.APIError 계열: API 오류 시 원본 예외를 그대로 전파. 재호출 금지.
    """
    last_question = _last_user_message(messages)
    system_prompt = _STEP1_SYSTEM_PROMPT + format_context_hint(context)

    client = _get_client()
    response = client.messages.create(
        model=settings.anthropic_model_cheap,
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": last_question or ""}],
    )
    raw_text = response.content[0].text if response.content else ""
    cleaned = _strip_code_fence(raw_text)

    intent: dict | None = None
    llm_schema: dict[str, list[str]] | None = None
    try:
        parsed = json.loads(cleaned)
    except (ValueError, TypeError):
        parsed = None

    if isinstance(parsed, dict):
        intent = _coerce_intent(parsed.get("intent"))
        llm_schema = _coerce_schema(parsed.get("tables"))

    intent = _apply_context_defaults(intent, context)

    if llm_schema is None:
        llm_schema = retrieve_relevant_schema(last_question)

    return intent, llm_schema


# --- Step 2 -------------------------------------------------------------------


def text_to_sql(
    messages: list[dict],
    context: dict | None,
    retrieved_schema: dict[str, list[str]],
) -> str:
    """Step 2 — Sonnet/Opus 1회 호출로 SQL 생성 + validate_sql 통과.

    Args:
        messages: Chat 턴 목록. 최근 `_MAX_HISTORY_TURNS` 턴만 LLM에 전달.
        context: 시뮬레이터 컨텍스트 (`{region?, total_budget?}`).
            `build_system_prompt`로 전달돼 시스템 프롬프트의 보조 섹션으로 부착된다.
        retrieved_schema: Step 1에서 추출한 `{table: [columns]}`.
            이 스키마만 프롬프트에 주입되며, 전체 카탈로그는 박제되지 않는다.

    Returns:
        `validate_sql`이 정규화한 안전한 SELECT SQL 문자열.

    Raises:
        ValueError: LLM 응답이 validate_sql을 통과하지 못할 때. **재호출 금지 — 즉시 전파.**
        anthropic.APIError 계열: API 오류 시 원본 예외 전파.
    """
    system_prompt = build_system_prompt(retrieved_schema, context=context)
    recent = _slice_recent_messages(messages)
    payload_messages = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in recent
        if m.get("role") in {"user", "assistant"}
    ]
    if not payload_messages:
        # 안전 장치: 최소 1건의 user 메시지 확보
        payload_messages = [{"role": "user", "content": _last_user_message(messages)}]

    client = _get_client()
    response = client.messages.create(
        model=settings.anthropic_model_good,
        max_tokens=1024,
        system=system_prompt,
        messages=payload_messages,
    )
    raw_text = response.content[0].text if response.content else ""
    candidate_sql = _strip_code_fence(raw_text)

    # validate_sql 실패 시 재호출 금지 — 예외를 그대로 상위로 전파한다.
    return validate_sql(candidate_sql)


# --- Answer generation --------------------------------------------------------

_ANSWER_SYSTEM_PROMPT = """\
당신은 부동산 실거래 데이터에 대한 한국어 답변 생성기입니다.
아래 사용자 질문과 SQL 실행 결과를 바탕으로 간결한 한국어 답변을 작성하세요.

규칙:
- 한국어로 2~5문장 이내.
- 가격은 만원 단위. 1억 = 10000.
- 결과에 없는 정보는 추측하지 마세요.
- 마크다운 코드블록이나 표 금지. 평문 문장으로 답하세요.
"""


def _format_rows_inline(columns: list[str], rows: list[tuple]) -> str:
    lines = [" | ".join(columns)]
    for row in rows:
        lines.append(" | ".join(str(v) for v in row))
    return "\n".join(lines)


def generate_answer(
    question: str,
    columns: list[str],
    rows: list[tuple],
    sql: str,
) -> str:
    """Haiku 1회 호출로 쿼리 결과를 한국어 자연어 답변으로 변환.

    Args:
        question: 원래 유저 질문.
        columns: SELECT된 컬럼명 목록.
        rows: DB 결과 tuple 목록.
        sql: 실행된 SQL (디버깅/트레이싱용으로 프롬프트에 포함).

    Returns:
        한국어 답변 텍스트.

    Raises:
        anthropic.APIError 계열: API 오류 시 원본 예외 전파. 재호출 금지.
    """
    total = len(rows)
    if total <= _INLINE_ROW_THRESHOLD:
        result_section = _format_rows_inline(columns, rows)
        summary_note = f"(총 {total}건)"
    else:
        top_rows = rows[:_SUMMARY_TOP_N]
        result_section = _format_rows_inline(columns, top_rows)
        summary_note = f"(상위 {_SUMMARY_TOP_N}건만 표시, 총 {total}건)"

    user_content = (
        f"# 질문\n{question}\n\n# 실행된 SQL\n{sql}\n\n# 결과 {summary_note}\n{result_section}\n"
    )

    client = _get_client()
    response = client.messages.create(
        model=settings.anthropic_model_cheap,
        max_tokens=512,
        system=_ANSWER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    text = response.content[0].text if response.content else ""
    return text.strip()
