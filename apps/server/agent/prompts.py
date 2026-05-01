"""Text-to-SQL 시스템 프롬프트 빌더.

정적 규칙과 few-shot 예제는 상수로 유지하고, 허용 테이블/컬럼은 retrieved_schema에서
주입한다. 전체 스키마 박제 금지.

시뮬레이터 컨텍스트(`{region, total_budget}`)는 `format_context_hint`가 별도 섹션으로
변환해 시스템 프롬프트 말미에 부착한다. 질문에 명시되지 않은 값의 기본값으로만 작용하며,
사용자가 질문에 명시한 값이 있으면 컨텍스트보다 우선한다는 규칙을 함께 명시한다.
"""

from agent.schema_retrieval import SCHEMA_CATALOG

# --- 정적 규칙 (모든 호출 공통) -----------------------------------------------
_STATIC_RULES = """\
You are a read-only PostgreSQL Text-to-SQL generator for an apartment real-estate
database. Follow these rules strictly.

# Output Rules
- Return ONLY a single SQL SELECT statement. Do NOT wrap it in markdown code blocks.
- Do NOT add explanations, comments, or any prose before/after the SQL.
- Always include `LIMIT 100` or lower. Never exceed 100 rows.
- Always include `is_canceled = FALSE` in WHERE when querying sales_transactions
  (취소/해제 거래 제외).

# Domain Rules
- `price` is stored in 만원 (ten-thousand KRW). 1억 = 10000. 10억 = 100000.
- `exclusive_area` is stored in ㎡. To convert to 평: divide by 3.306.
- Korean 구/시/군 filters go against `regions.sigungu` (e.g. '강남구').
- Korean 시/도 filters go against `regions.sido` (e.g. '서울특별시').
"""

# --- few-shot 예제 5개 (정적) -------------------------------------------------
_FEW_SHOTS = """\
# Examples

## Example 1 — 최근 거래 조회
Q: 강남구 최근 거래 5건
A: SELECT s.deal_date, a.apartment_name, s.price, s.exclusive_area
   FROM sales_transactions s
   JOIN apartments a USING (apartment_id)
   JOIN regions r USING (region_id)
   WHERE r.sigungu = '강남구' AND s.is_canceled = FALSE
   ORDER BY s.deal_date DESC
   LIMIT 5;

## Example 2 — 구별 평균 가격
Q: 서울 구별 평균 거래 가격
A: SELECT r.sigungu, ROUND(AVG(s.price)) AS avg_price
   FROM sales_transactions s
   JOIN apartments a USING (apartment_id)
   JOIN regions r USING (region_id)
   WHERE r.sido = '서울특별시' AND s.is_canceled = FALSE
   GROUP BY r.sigungu
   ORDER BY avg_price DESC
   LIMIT 100;

## Example 3 — 월별 추이
Q: 송파구 2024년 월별 평균 가격 추이
A: SELECT s.deal_year, s.deal_month, ROUND(AVG(s.price)) AS avg_price, COUNT(*) AS cnt
   FROM sales_transactions s
   JOIN apartments a USING (apartment_id)
   JOIN regions r USING (region_id)
   WHERE r.sigungu = '송파구' AND s.deal_year = 2024 AND s.is_canceled = FALSE
   GROUP BY s.deal_year, s.deal_month
   ORDER BY s.deal_year, s.deal_month
   LIMIT 100;

## Example 4 — 가격 필터
Q: 강남구에서 10억 이하로 거래된 아파트 20건
A: SELECT s.deal_date, a.apartment_name, s.price, s.exclusive_area
   FROM sales_transactions s
   JOIN apartments a USING (apartment_id)
   JOIN regions r USING (region_id)
   WHERE r.sigungu = '강남구' AND s.price <= 100000 AND s.is_canceled = FALSE
   ORDER BY s.deal_date DESC
   LIMIT 20;

## Example 5 — 전월 대비 변동률
Q: 서초구 최근 2개월 평균가 변동률
A: WITH monthly AS (
       SELECT s.deal_year, s.deal_month, AVG(s.price) AS avg_price
       FROM sales_transactions s
       JOIN apartments a USING (apartment_id)
       JOIN regions r USING (region_id)
       WHERE r.sigungu = '서초구' AND s.is_canceled = FALSE
       GROUP BY s.deal_year, s.deal_month
       ORDER BY s.deal_year DESC, s.deal_month DESC
       LIMIT 2
   )
   SELECT deal_year, deal_month, avg_price,
          ROUND(100.0 * (avg_price - LAG(avg_price) OVER (ORDER BY deal_year, deal_month))
                / LAG(avg_price) OVER (ORDER BY deal_year, deal_month), 2) AS change_pct
   FROM monthly
   ORDER BY deal_year, deal_month
   LIMIT 100;
"""


def format_context_hint(context: dict | None) -> str:
    """시뮬레이터 컨텍스트를 LLM 시스템 프롬프트 보조 섹션으로 변환.

    Args:
        context: ChatRequest.context. shape는 `{region?: str, total_budget?: int}` (만원 단위).

    Returns:
        시스템 프롬프트 끝에 부착할 섹션 문자열, 또는 컨텍스트가 비어 있으면 빈 문자열.

    Notes:
        - region은 사용자가 시뮬레이터에서 선택한 시군구이며, 질문에 지역이 명시되지 않은
          경우의 기본값으로만 사용되도록 모델에 알린다.
        - total_budget은 정보로만 노출하고 사용 여부는 LLM 판단에 맡긴다 (시세/추이 같은
          분석 질의에는 적용하지 않도록 명시).
    """
    if not context:
        return ""
    parts: list[str] = []
    region = context.get("region")
    if isinstance(region, str) and region.strip():
        parts.append(f"- 사용자가 시뮬레이터에서 보고 있는 시군구: {region.strip()}")
    total_budget = context.get("total_budget")
    if isinstance(total_budget, (int, float)) and total_budget > 0:
        parts.append(
            f"- 사용자의 총예산 상한(만원): {int(total_budget)} "
            "(사용자가 예산을 명시한 질문에서만 가격 필터로 사용. "
            "시세/추이 등 분석성 질의에는 적용하지 말 것.)"
        )
    if not parts:
        return ""
    return (
        "\n# 사용자 컨텍스트 (질문에 명시되지 않은 값의 기본값)\n"
        + "\n".join(parts)
        + "\n주의: 질문에 명시된 지역·조건은 항상 컨텍스트보다 우선합니다.\n"
    )


def _format_schema_section(retrieved_schema: dict[str, list[str]]) -> str:
    """retrieved_schema에 포함된 테이블/컬럼만 나열.

    각 컬럼은 SCHEMA_CATALOG의 설명과 함께 출력. 주입되지 않은 컬럼/테이블은 언급하지 않는다.
    """
    if not retrieved_schema:
        return "(no tables selected — refuse to generate SQL)\n"

    lines: list[str] = []
    for table, cols in retrieved_schema.items():
        if table not in SCHEMA_CATALOG:
            continue
        lines.append(f"## {table}")
        for col in cols:
            desc = SCHEMA_CATALOG[table].get(col)
            if desc:
                lines.append(f"  - {col}: {desc}")
        lines.append("")
    return "\n".join(lines)


def build_system_prompt(
    retrieved_schema: dict[str, list[str]],
    context: dict | None = None,
) -> str:
    """Text-to-SQL 시스템 프롬프트 빌드.

    Args:
        retrieved_schema: schema_retrieval.retrieve_relevant_schema() 결과.
            {테이블: [컬럼]} 형태. 여기 포함된 컬럼만 동적 스키마 섹션에 나열됨.
        context: 선택적 시뮬레이터 컨텍스트 (`{region?, total_budget?}`).
            None이거나 비어 있으면 컨텍스트 섹션을 생략한다.

    Returns:
        시스템 프롬프트 문자열. 정적 규칙 + 동적 스키마 + (선택) 컨텍스트 + few-shot 예제 포함.
    """
    schema_section = _format_schema_section(retrieved_schema)
    context_section = format_context_hint(context)
    return (
        f"{_STATIC_RULES}\n"
        f"# Available Schema\n"
        f"Only the following tables and columns are available. Do NOT reference any\n"
        f"table or column not listed here.\n\n"
        f"{schema_section}\n"
        f"{context_section}"
        f"{_FEW_SHOTS}"
    )
