"""intent_mapper 단위 테스트 — 템플릿 기반 SQL 생성 (LLM 호출 없음)."""

import pytest

from agent.intent_mapper import (
    SUPPORTED_INTENTS,
    intent_to_sql,
)
from agent.validators import validate_sql


def test_supported_intents_list():
    """plan이 요구하는 5개 intent 지원."""
    expected = {
        "recent_transactions",
        "avg_price_by_region",
        "monthly_trend",
        "price_filter",
        "top_apartments",
    }
    assert expected.issubset(set(SUPPORTED_INTENTS))


def test_recent_transactions_generates_valid_sql():
    """최근 거래 intent — 지역 + limit 파라미터."""
    sql = intent_to_sql({"type": "recent_transactions", "region": "강남구", "limit": 5})
    assert isinstance(sql, str)
    assert "SELECT" in sql.upper()
    assert "is_canceled" in sql.lower()
    # validator 통과해야 함
    validated = validate_sql(sql)
    assert validated


def test_recent_transactions_param_binding():
    """SQL에 f-string 보간 금지 — 지역명은 %s 바인딩으로 처리되어 SQL에 직접 포함되지 않음."""
    sql = intent_to_sql({"type": "recent_transactions", "region": "강남구", "limit": 5})
    assert "강남구" not in sql  # 파라미터 바인딩(%s) 사용
    assert "%s" in sql


def test_avg_price_by_region():
    """구별 평균 가격 intent — 시/도 필터만."""
    sql = intent_to_sql({"type": "avg_price_by_region", "sido": "서울특별시"})
    assert "AVG" in sql.upper() or "avg" in sql.lower()
    assert "GROUP BY" in sql.upper()
    assert "%s" in sql
    assert "서울특별시" not in sql
    validate_sql(sql)


def test_monthly_trend():
    """월별 추이 intent — 지역 + 연도."""
    sql = intent_to_sql({"type": "monthly_trend", "region": "송파구", "year": 2024})
    assert "deal_month" in sql.lower()
    assert "deal_year" in sql.lower()
    assert "GROUP BY" in sql.upper()
    validate_sql(sql)


def test_price_filter():
    """가격 필터 intent — max_price 만원 단위."""
    sql = intent_to_sql(
        {"type": "price_filter", "region": "강남구", "max_price": 100000, "limit": 20}
    )
    assert "price" in sql.lower()
    assert "%s" in sql
    validate_sql(sql)


def test_top_apartments():
    """상위 아파트 intent — 가격 기준 내림차순."""
    sql = intent_to_sql({"type": "top_apartments", "region": "강남구", "limit": 10})
    assert "ORDER BY" in sql.upper()
    assert "DESC" in sql.upper()
    validate_sql(sql)


def test_unknown_intent_raises():
    """지원하지 않는 intent는 ValueError."""
    with pytest.raises(ValueError):
        intent_to_sql({"type": "unknown_xxx"})


def test_missing_type_raises():
    """type 필드 없으면 ValueError."""
    with pytest.raises(ValueError):
        intent_to_sql({"region": "강남구"})


def test_limit_clamped():
    """limit이 100 초과여도 validator에서 100으로 클램프."""
    sql = intent_to_sql({"type": "recent_transactions", "region": "강남구", "limit": 500})
    validated = validate_sql(sql)
    # sqlglot 정규화된 SQL에 LIMIT 500은 존재하지 않아야 함
    assert "500" not in validated
