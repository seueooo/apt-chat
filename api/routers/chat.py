"""/api/chat 엔드포인트 — 캐시 + 세션 rate limit + Text-to-SQL 파이프라인.

요청 처리 흐름:
  1. X-Session-Id 헤더 검증 → 없으면 400
  2. rate_limit.check_and_increment(session_id) → 초과 시 429
  3. query_cache.get(key) 조회 → hit 시 즉시 반환 (LLM/DB 호출 없음)
  4. Step 1 (Haiku): extract_intent_and_tables
     - intent 매칭 시 intent_to_sql → Step 2 스킵
     - intent 미매칭 시 Step 2 (Sonnet/Opus): text_to_sql
  5. validate_sql (intent 경로에서도 한 번 더 검증 — 안전성/정규화)
  6. execute_query → query_formatter → generate_answer (optional)
  7. query_cache.set (성공 시에만)
  8. remaining_questions 채워 반환

재시도 금지: validate_sql 실패 시 즉시 400.
"""

from __future__ import annotations

import anthropic
import psycopg.errors
from fastapi import APIRouter, Header, HTTPException
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, Field

from agent.intent_mapper import intent_to_sql
from agent.sql_agent import (
    extract_intent_and_tables,
    generate_answer,
    text_to_sql,
)
from agent.validators import validate_sql
from db.connection import execute_query
from services import query_cache, rate_limit
from services.query_formatter import detect_visualization, format_warnings

router = APIRouter()


# --- Pydantic 모델 ------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    context: dict | None = None
    summarize: bool = True


class ChatResponse(BaseModel):
    answer: str
    sql: str
    columns: list[str]
    rows: list[list]
    visualization: dict | None
    warnings: list[str]
    cache_hit: bool
    remaining_questions: int


# --- 내부 헬퍼 ----------------------------------------------------------------


def _last_user_content(messages: list[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in messages]


def _intent_params(intent: dict) -> tuple:
    """Intent dict에서 intent_type별 psycopg 바인딩 params 추출."""
    intent_type = intent.get("type")
    if intent_type == "recent_transactions":
        region = intent.get("region")
        if not region:
            raise HTTPException(status_code=400, detail="질문을 다시 작성해 주세요")
        return (region,)
    if intent_type == "avg_price_by_region":
        sido = intent.get("sido")
        if not sido:
            raise HTTPException(status_code=400, detail="질문을 다시 작성해 주세요")
        return (sido,)
    if intent_type == "monthly_trend":
        region = intent.get("region")
        year = intent.get("year")
        if not region or year is None:
            raise HTTPException(status_code=400, detail="질문을 다시 작성해 주세요")
        return (region, year)
    if intent_type == "price_filter":
        region = intent.get("region")
        max_price = intent.get("max_price")
        if not region or max_price is None:
            raise HTTPException(status_code=400, detail="질문을 다시 작성해 주세요")
        return (region, max_price)
    if intent_type == "top_apartments":
        region = intent.get("region")
        if not region:
            raise HTTPException(status_code=400, detail="질문을 다시 작성해 주세요")
        return (region,)
    raise HTTPException(status_code=400, detail="지원하지 않는 intent")


def _serialize_rows(rows: list[tuple]) -> list[list]:
    """DB row를 JSON 직렬화 가능한 값으로 변환 (date/datetime 등 → str)."""
    result: list[list] = []
    for row in rows:
        result.append([_serialize_value(v) for v in row])
    return result


def _serialize_value(v):
    import datetime
    from decimal import Decimal

    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (datetime.date, datetime.datetime)):
        return str(v)
    if isinstance(v, Decimal):
        # 가격/카운트 등은 int로 반환 가능하면 int, 아니면 float
        if v == v.to_integral_value():
            return int(v)
        return float(v)
    return str(v)


# --- 엔드포인트 ---------------------------------------------------------------


@router.post("/api/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    x_session_id: str | None = Header(default=None),
) -> ChatResponse:
    # 1. 세션 ID 검증
    if not x_session_id:
        raise HTTPException(status_code=400, detail="세션 ID가 필요합니다")

    # 2. Rate limit
    try:
        remaining = rate_limit.check_and_increment(x_session_id)
    except rate_limit.RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="세션당 최대 3회 질문 가능합니다",
        ) from exc

    # 3. 캐시 조회
    last_question = _last_user_content(req.messages)
    cache_key = query_cache.make_cache_key(last_question, req.context)
    cached = query_cache.get(cache_key)
    if cached is not None:
        return ChatResponse(
            answer=cached["answer"],
            sql=cached["sql"],
            columns=cached["columns"],
            rows=cached["rows"],
            visualization=cached.get("visualization"),
            warnings=cached.get("warnings", []),
            cache_hit=True,
            remaining_questions=remaining,
        )

    # 4. Text-to-SQL 파이프라인
    messages_dicts = _messages_to_dicts(req.messages)
    try:
        intent, retrieved_schema = extract_intent_and_tables(messages_dicts, req.context)

        if intent is not None:
            # Step 2 스킵 — 템플릿 SQL
            sql = intent_to_sql(intent)
            params: tuple | None = _intent_params(intent)
        else:
            # Step 2 — LLM 기반 SQL 생성
            sql = text_to_sql(messages_dicts, req.context, retrieved_schema)
            params = None

        # intent 경로도 validate_sql로 정규화 + 안전 검증
        sql = validate_sql(sql)
    except ValueError as exc:
        # validate_sql 실패 — 재시도 금지
        raise HTTPException(status_code=400, detail="질문을 다시 작성해 주세요") from exc
    except anthropic.APIError as exc:
        raise HTTPException(status_code=500, detail="AI 서비스 오류") from exc

    # 5. DB 실행
    warnings: list[str] = []
    db_error = False
    try:
        columns, rows = execute_query(sql, params, statement_timeout_ms=10000)
    except psycopg.errors.QueryCanceled as exc:
        raise HTTPException(status_code=504, detail="DB 쿼리 시간이 초과됐습니다") from exc
    except (psycopg.errors.OperationalError, PoolTimeout):
        columns, rows = [], []
        warnings.append("데이터베이스 오류로 결과를 가져오지 못했습니다")
        db_error = True

    # 6. 포맷팅 + 경고 + 차트
    warnings.extend(format_warnings(sql, rows, last_question))
    visualization = detect_visualization(columns, rows) if rows else None

    # 7. 한국어 답변 생성 (요청 시)
    answer = ""
    if req.summarize and not db_error and rows:
        try:
            answer = generate_answer(last_question, columns, rows, sql)
        except anthropic.APIError as exc:
            raise HTTPException(status_code=500, detail="AI 서비스 오류") from exc
    elif db_error:
        answer = "데이터베이스 오류로 결과를 가져오지 못했습니다."
    elif not rows:
        answer = "조건에 해당하는 결과가 없습니다."

    serialized_rows = _serialize_rows(rows)

    response = ChatResponse(
        answer=answer,
        sql=sql,
        columns=columns,
        rows=serialized_rows,
        visualization=visualization,
        warnings=warnings,
        cache_hit=False,
        remaining_questions=remaining,
    )

    # 8. 캐시 저장 (DB 성공 시에만 — 실패 응답 저장 금지)
    if not db_error:
        query_cache.set(
            cache_key,
            {
                "answer": answer,
                "sql": sql,
                "columns": columns,
                "rows": serialized_rows,
                "visualization": visualization,
                "warnings": warnings,
            },
        )

    return response
