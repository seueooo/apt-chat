"""prompts.build_system_prompt 단위 테스트.

검증:
- 반환값에 정적 규칙 포함 (가격 단위 만원, is_canceled=FALSE, LIMIT 100, SQL-only)
- few-shot 5개 포함
- retrieved_schema의 테이블/컬럼만 나열, 그 외는 언급 금지
- 시뮬레이터 컨텍스트(`{region, total_budget}`)가 별도 섹션으로 부착되고,
  비어 있으면 섹션이 생략된다.
"""

from agent.prompts import build_system_prompt, format_context_hint


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


# --- format_context_hint -------------------------------------------------------


def test_format_context_hint_empty_when_none():
    """None / 빈 dict / falsy 필드만 있으면 빈 문자열 반환."""
    assert format_context_hint(None) == ""
    assert format_context_hint({}) == ""
    assert format_context_hint({"region": "", "total_budget": 0}) == ""
    assert format_context_hint({"region": None, "total_budget": None}) == ""


def test_format_context_hint_region_only():
    """region만 주어지면 시군구 라인만 포함하고 예산 라인은 생략."""
    out = format_context_hint({"region": "강남구"})
    assert "강남구" in out
    assert "시군구" in out
    assert "총예산" not in out
    assert "사용자 컨텍스트" in out
    # 우선순위 규칙이 함께 명시돼야 한다
    assert "우선" in out


def test_format_context_hint_region_and_budget():
    """region + total_budget 모두 주어지면 두 라인 모두 포함."""
    out = format_context_hint({"region": "강남구", "total_budget": 50000})
    assert "강남구" in out
    assert "50000" in out
    assert "총예산" in out
    # 분석 질의에는 적용 금지 디스클레이머 포함
    assert "시세" in out or "추이" in out or "분석" in out


def test_build_system_prompt_omits_context_when_none():
    """context=None(디폴트) 호출은 기존 동작과 동일 — 컨텍스트 섹션 없음."""
    prompt = build_system_prompt({"sales_transactions": ["price"]})
    assert "사용자 컨텍스트" not in prompt


def test_build_system_prompt_includes_context_section():
    """context 전달 시 동적 스키마와 few-shot 사이에 컨텍스트 섹션이 들어간다."""
    schema = {"sales_transactions": ["deal_date", "price"]}
    prompt = build_system_prompt(schema, context={"region": "송파구", "total_budget": 80000})

    assert "송파구" in prompt
    assert "80000" in prompt
    # 컨텍스트 섹션은 # Available Schema 뒤, # Examples 앞에 위치해야 한다
    schema_idx = prompt.index("# Available Schema")
    context_idx = prompt.index("# 사용자 컨텍스트")
    examples_idx = prompt.index("# Examples")
    assert schema_idx < context_idx < examples_idx
