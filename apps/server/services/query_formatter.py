"""Text-to-SQL 결과 포맷터.

- `detect_visualization`: 결과가 차트로 표현 가능한지 판별.
- `format_warnings`: 결과/SQL에 대한 경고 문구 목록 생성.

본 모듈은 LLM을 호출하지 않으며, 순수 함수만 포함한다.
"""

import re

# --- 차트 감지 ---------------------------------------------------------------
# 시계열/카테고리/수치 컬럼 힌트
_TIME_SERIES_COLUMNS = {"deal_year", "deal_month", "deal_date"}
_CATEGORY_COLUMNS = {"sigungu", "sido", "dong", "apartment_name"}
_NUMERIC_NAME_HINTS = (
    "price",
    "cnt",
    "count",
    "avg",
    "sum",
    "max",
    "min",
    "total",
    "ratio",
    "pct",
    "change",
)

_MAX_BAR_ROWS = 30


def _is_numeric_column(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _NUMERIC_NAME_HINTS)


def detect_visualization(columns: list[str], rows: list[tuple]) -> dict | None:
    """결과 컬럼/행을 보고 차트 spec 반환, 불가하면 None.

    Args:
        columns: 결과 컬럼명 목록 (execute_query의 첫 반환값).
        rows: 결과 행 목록 (execute_query의 두 번째 반환값).

    Returns:
        - 시계열 컬럼(deal_year/deal_month/deal_date) + 수치 컬럼 → `line` spec
        - 카테고리 컬럼(sigungu/sido 등) + 수치 컬럼, 행 수 <= 30 → `bar` spec
        - 그 외 → None
    """
    if not columns or not rows:
        return None

    col_set = set(columns)

    # 시계열 판별
    time_cols = col_set & _TIME_SERIES_COLUMNS
    numeric_cols = [c for c in columns if _is_numeric_column(c) and c not in time_cols]

    if time_cols and numeric_cols:
        # x축: 시계열 컬럼 (카탈로그 우선순위 year → month → date)
        x_order = ["deal_year", "deal_month", "deal_date"]
        x_col = next((c for c in x_order if c in time_cols), next(iter(time_cols)))
        return {"type": "line", "x": x_col, "y": numeric_cols[0]}

    # 카테고리 판별
    cat_cols = col_set & _CATEGORY_COLUMNS
    cat_numeric = [c for c in columns if _is_numeric_column(c) and c not in cat_cols]
    if cat_cols and cat_numeric and len(rows) <= _MAX_BAR_ROWS:
        x_col = next(iter(cat_cols))
        return {"type": "bar", "x": x_col, "y": cat_numeric[0]}

    return None


# --- 경고 ---------------------------------------------------------------------
_IS_CANCELED_PATTERN = re.compile(r"is_canceled", re.IGNORECASE)


def format_warnings(sql: str, rows: list[tuple], original_question: str) -> list[str]:
    """SQL/결과 기반 경고 문구 목록.

    Args:
        sql: 실행된 SQL 문자열.
        rows: 결과 행.
        original_question: 원래 질문 (향후 확장 여지를 위한 파라미터, 현재 사용 안 함).

    Returns:
        경고 문자열 목록. 없으면 빈 리스트.
    """
    _ = original_question  # 명시적 미사용
    warnings: list[str] = []

    if len(rows) == 0:
        warnings.append("데이터 없음: 조건에 해당하는 결과가 없습니다.")
    elif len(rows) >= 100:
        warnings.append("결과가 제한됨: 상위 100건만 표시됩니다.")

    # sales_transactions를 조회하면서 is_canceled 필터가 없으면 경고
    if "sales_transactions" in sql.lower() and not _IS_CANCELED_PATTERN.search(sql):
        warnings.append("해제 거래 포함 가능: is_canceled 필터가 적용되지 않았습니다.")

    return warnings
