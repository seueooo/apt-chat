"""prompts.build_system_prompt 단위 테스트.

검증:
- 반환값에 정적 규칙 포함 (가격 단위 만원, is_canceled=FALSE, LIMIT 100, SQL-only)
- few-shot 5개 포함
- retrieved_schema의 테이블/컬럼만 나열, 그 외는 언급 금지
"""

from agent.prompts import build_system_prompt


def test_static_rules_included():
    """정적 규칙 — 가격 단위, ㎡, is_canceled, LIMIT, SQL-only."""
    schema = {"sales_transactions": ["deal_date", "price", "is_canceled"]}
    prompt = build_system_prompt(schema)

    assert "만원" in prompt
    assert "10000" in prompt  # 1억 = 10000
    assert "3.306" in prompt or "㎡" in prompt
    assert "is_canceled" in prompt
    assert "FALSE" in prompt.upper()
    assert "100" in prompt  # LIMIT 100
    # SQL-only directive
    assert "SQL" in prompt.upper()


def test_dynamic_schema_injected():
    """retrieved_schema에 포함된 테이블/컬럼만 프롬프트에 나열."""
    schema = {
        "sales_transactions": ["deal_date", "price", "is_canceled"],
        "regions": ["region_id", "sigungu"],
    }
    prompt = build_system_prompt(schema)

    assert "sales_transactions" in prompt
    assert "regions" in prompt
    assert "deal_date" in prompt
    assert "price" in prompt
    assert "sigungu" in prompt


def test_non_retrieved_columns_not_mentioned():
    """retrieved_schema에 없는 컬럼은 테이블 스키마 섹션에 언급 금지.

    few-shot 예제에는 다양한 컬럼이 포함되지만, 동적 스키마 섹션에는 주입된 컬럼만 있어야 함.
    """
    schema = {"sales_transactions": ["deal_date", "price"]}
    prompt = build_system_prompt(schema)

    # 동적 스키마 섹션 — "# Available Schema" 부터 "# Examples" 직전까지
    start_marker = "# Available Schema"
    end_marker = "# Examples"
    assert start_marker in prompt
    assert end_marker in prompt
    start_idx = prompt.index(start_marker)
    end_idx = prompt.index(end_marker)
    dynamic_section = prompt[start_idx:end_idx]

    assert "deal_date" in dynamic_section
    assert "price" in dynamic_section
    # build_year는 apartments의 컬럼. 주입되지 않았으므로 동적 섹션에 없어야 함
    assert "build_year" not in dynamic_section
    # apartments 테이블은 주입되지 않았으므로 동적 섹션에 없어야 함
    assert "apartments" not in dynamic_section


def test_few_shot_count():
    """few-shot 예제 5개 포함 (최근 거래, 구별 평균, 월별 추이, 가격 필터, 전월 대비)."""
    schema = {"sales_transactions": ["deal_date", "price"]}
    prompt = build_system_prompt(schema)

    # Example 1 ~ Example 5 이 있어야 함
    for i in range(1, 6):
        assert f"Example {i}" in prompt or f"예제 {i}" in prompt


def test_empty_schema_still_returns_prompt():
    """빈 스키마여도 정적 규칙은 포함된 프롬프트 반환."""
    prompt = build_system_prompt({})
    assert "만원" in prompt
    assert "SQL" in prompt.upper()
