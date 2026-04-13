"""Intent → SQL 템플릿 매핑.

LLM 호출 없이 사전 정의된 SQL 템플릿으로 SQL을 생성한다.
SQL 안전성:
    - 모든 사용자 값은 psycopg `%s` 파라미터 바인딩으로 전달.
    - f-string 보간 금지.
    - 반환된 SQL은 호출자 쪽에서 `(sql, params)` 형태로 execute_query에 전달하면 되지만,
      본 모듈은 SQL 문자열만 반환한다 (플랜의 `intent_to_sql(intent) -> str` 시그니처 준수).

지원 intent (type 필드):
    - recent_transactions: 최근 거래 N건 (region, limit)
    - avg_price_by_region: 시/도 하위 구별 평균 가격 (sido)
    - monthly_trend: 월별 평균 추이 (region, year)
    - price_filter: 가격 상한 필터 (region, max_price, limit)
    - top_apartments: 가격 상위 아파트 (region, limit)
"""

SUPPORTED_INTENTS: tuple[str, ...] = (
    "recent_transactions",
    "avg_price_by_region",
    "monthly_trend",
    "price_filter",
    "top_apartments",
)

# 기본 limit. validator가 추가로 100으로 클램프한다.
_DEFAULT_LIMIT = 10


def _clamp_limit(value: object) -> int:
    """limit 값을 1..100 범위로 클램프. validator도 100 상한을 강제한다."""
    try:
        n = int(value) if value is not None else _DEFAULT_LIMIT
    except (TypeError, ValueError):
        n = _DEFAULT_LIMIT
    return max(1, min(100, n))


def intent_to_sql(intent: dict) -> str:
    """Intent dict → 파라미터 바인딩 SQL 문자열.

    Args:
        intent: `{"type": ..., "region": ..., ...}` 형태. `type`은 SUPPORTED_INTENTS 중 하나.

    Returns:
        psycopg `%s` 바인딩을 포함한 SELECT SQL. 사용자 값은 SQL 문자열에 직접 포함되지 않음.

    Raises:
        ValueError: type 누락/미지원 / 필수 파라미터 누락 시.
    """
    if not isinstance(intent, dict):
        raise ValueError("intent must be a dict")

    intent_type = intent.get("type")
    if not intent_type:
        raise ValueError("intent.type is required")

    if intent_type not in SUPPORTED_INTENTS:
        raise ValueError(f"unsupported intent type: {intent_type}")

    # limit은 SQL에 직접 포함. validator가 100으로 클램프.
    limit = _clamp_limit(intent.get("limit"))

    if intent_type == "recent_transactions":
        # region 필터 + 최근 deal_date 정렬
        return (
            "SELECT s.deal_date, a.apartment_name, s.price, s.exclusive_area, s.floor "
            "FROM sales_transactions s "
            "JOIN apartments a USING (apartment_id) "
            "JOIN regions r USING (region_id) "
            "WHERE r.sigungu = %s AND s.is_canceled = FALSE "
            "ORDER BY s.deal_date DESC "
            f"LIMIT {limit}"
        )

    if intent_type == "avg_price_by_region":
        return (
            "SELECT r.sigungu, ROUND(AVG(s.price)) AS avg_price, COUNT(*) AS cnt "
            "FROM sales_transactions s "
            "JOIN apartments a USING (apartment_id) "
            "JOIN regions r USING (region_id) "
            "WHERE r.sido = %s AND s.is_canceled = FALSE "
            "GROUP BY r.sigungu "
            "ORDER BY avg_price DESC "
            "LIMIT 100"
        )

    if intent_type == "monthly_trend":
        return (
            "SELECT s.deal_year, s.deal_month, ROUND(AVG(s.price)) AS avg_price, "
            "COUNT(*) AS cnt "
            "FROM sales_transactions s "
            "JOIN apartments a USING (apartment_id) "
            "JOIN regions r USING (region_id) "
            "WHERE r.sigungu = %s AND s.deal_year = %s AND s.is_canceled = FALSE "
            "GROUP BY s.deal_year, s.deal_month "
            "ORDER BY s.deal_year, s.deal_month "
            "LIMIT 100"
        )

    if intent_type == "price_filter":
        return (
            "SELECT s.deal_date, a.apartment_name, s.price, s.exclusive_area "
            "FROM sales_transactions s "
            "JOIN apartments a USING (apartment_id) "
            "JOIN regions r USING (region_id) "
            "WHERE r.sigungu = %s AND s.price <= %s AND s.is_canceled = FALSE "
            "ORDER BY s.deal_date DESC "
            f"LIMIT {limit}"
        )

    if intent_type == "top_apartments":
        return (
            "SELECT a.apartment_name, MAX(s.price) AS max_price, COUNT(*) AS cnt "
            "FROM sales_transactions s "
            "JOIN apartments a USING (apartment_id) "
            "JOIN regions r USING (region_id) "
            "WHERE r.sigungu = %s AND s.is_canceled = FALSE "
            "GROUP BY a.apartment_name "
            "ORDER BY max_price DESC "
            f"LIMIT {limit}"
        )

    # Unreachable — SUPPORTED_INTENTS 체크에서 이미 걸러짐
    raise ValueError(f"unhandled intent type: {intent_type}")
