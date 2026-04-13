"""Text-to-SQL 시스템 프롬프트 빌더.

정적 규칙과 few-shot 예제는 상수로 유지하고, 허용 테이블/컬럼은 retrieved_schema에서
주입한다. 전체 스키마 박제 금지.
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


def build_system_prompt(retrieved_schema: dict[str, list[str]]) -> str:
    """Text-to-SQL 시스템 프롬프트 빌드.

    Args:
        retrieved_schema: schema_retrieval.retrieve_relevant_schema() 결과.
            {테이블: [컬럼]} 형태. 여기 포함된 컬럼만 동적 스키마 섹션에 나열됨.

    Returns:
        시스템 프롬프트 문자열. 정적 규칙 + 동적 스키마 + few-shot 예제 포함.
    """
    schema_section = _format_schema_section(retrieved_schema)
    return (
        f"{_STATIC_RULES}\n"
        f"# Available Schema\n"
        f"Only the following tables and columns are available. Do NOT reference any\n"
        f"table or column not listed here.\n\n"
        f"{schema_section}\n"
        f"{_FEW_SHOTS}"
    )
