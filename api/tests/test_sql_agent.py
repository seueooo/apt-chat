"""sql_agent 단위 테스트.

2단계 파이프라인과 재시도 금지 원칙 검증:
- Haiku 1회 호출로 intent + schema 추출
- intent 매칭 시 Sonnet/Opus 호출 스킵
- Sonnet 응답의 markdown 코드블록 제거
- validate_sql 실패 시 LLM 재호출 없이 즉시 ValueError 전파
- 결과 크기에 따른 generate_answer 포맷 차이
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent import sql_agent


def _mock_response(text: str) -> SimpleNamespace:
    """anthropic SDK Message 응답을 흉내 낸 구조체.

    `.content[0].text` 접근만 가능하면 충분.
    """
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


@pytest.fixture
def mock_client(monkeypatch):
    """sql_agent._get_client가 반환하는 anthropic client를 MagicMock으로 교체."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = MagicMock()
    monkeypatch.setattr(sql_agent, "_get_client", lambda: client)
    return client


# --- extract_intent_and_tables ------------------------------------------------


def test_extract_intent_and_tables_returns_tuple(mock_client):
    """Haiku 호출 1회로 (intent, retrieved_schema) tuple 반환."""
    mock_client.messages.create.return_value = _mock_response(
        '{"intent": {"type": "recent_transactions", "region": "강남구", "limit": 5}, '
        '"tables": {"sales_transactions": ["deal_date", "price"], '
        '"regions": ["region_id", "sigungu"]}}'
    )

    messages = [{"role": "user", "content": "강남구 최근 거래 5건"}]
    intent, schema = sql_agent.extract_intent_and_tables(messages, None)

    assert isinstance(intent, dict)
    assert intent["type"] == "recent_transactions"
    assert isinstance(schema, dict)
    assert "sales_transactions" in schema
    assert mock_client.messages.create.call_count == 1


def test_extract_intent_fallback_on_parse_failure(mock_client):
    """응답 JSON 파싱 실패 시 intent=None, schema는 retrieve_relevant_schema로 fallback."""
    mock_client.messages.create.return_value = _mock_response("not-a-json-blob")

    messages = [{"role": "user", "content": "강남구 최근 거래"}]
    intent, schema = sql_agent.extract_intent_and_tables(messages, None)

    assert intent is None
    assert isinstance(schema, dict)
    assert len(schema) > 0  # fallback이 _default_schema나 keyword 매칭 결과 반환


def test_extract_intent_matched_skips_step2(mock_client):
    """intent가 allowlist 매칭 시 text_to_sql은 Anthropic 호출을 하지 않는다 (통합 흐름).

    extract_intent_and_tables가 유효한 intent를 돌려주면,
    상위 라우터는 intent_to_sql을 호출하고 text_to_sql은 호출하지 않는 것이 원칙.
    여기서는 sql_agent 레벨에서 text_to_sql을 직접 호출하지 않았을 때
    mock_client.messages.create가 Haiku 1회만 호출됐는지 검증한다.
    """
    mock_client.messages.create.return_value = _mock_response(
        '{"intent": {"type": "recent_transactions", "region": "강남구", "limit": 5}, '
        '"tables": {"sales_transactions": ["deal_date"]}}'
    )

    messages = [{"role": "user", "content": "강남구 최근 거래 5건"}]
    intent, _schema = sql_agent.extract_intent_and_tables(messages, None)

    # intent가 매칭됐으므로 상위 라우터는 text_to_sql을 부르지 않음 -> 1회 호출만 발생
    assert intent is not None
    assert intent["type"] in {
        "recent_transactions",
        "avg_price_by_region",
        "monthly_trend",
        "price_filter",
        "top_apartments",
    }
    assert mock_client.messages.create.call_count == 1


# --- text_to_sql --------------------------------------------------------------


def test_text_to_sql_uses_only_retrieved_schema(mock_client):
    """시스템 프롬프트에는 retrieved_schema에 포함된 테이블만 나열된다."""
    mock_client.messages.create.return_value = _mock_response(
        "SELECT deal_date, price FROM sales_transactions WHERE is_canceled = FALSE LIMIT 10"
    )

    retrieved_schema = {
        "sales_transactions": ["deal_date", "price", "is_canceled"],
    }
    messages = [{"role": "user", "content": "최근 거래 보여줘"}]
    sql = sql_agent.text_to_sql(messages, None, retrieved_schema)

    assert mock_client.messages.create.call_count == 1
    _, kwargs = mock_client.messages.create.call_args
    system_prompt = kwargs["system"]
    # retrieved된 테이블은 포함돼야 함
    assert "sales_transactions" in system_prompt
    # 동적 스키마 섹션에 apartments/regions는 언급되면 안 됨
    start_idx = system_prompt.index("# Available Schema")
    end_idx = system_prompt.index("# Examples")
    dynamic_section = system_prompt[start_idx:end_idx]
    assert "apartments" not in dynamic_section
    assert "regions" not in dynamic_section
    assert "SELECT" in sql.upper()


def test_text_to_sql_strips_markdown_codeblock(mock_client):
    """응답이 ```sql ... ``` 로 감싸진 경우 코드블록을 제거."""
    wrapped = (
        "```sql\n"
        "SELECT deal_date, price FROM sales_transactions "
        "WHERE is_canceled = FALSE LIMIT 10\n"
        "```"
    )
    mock_client.messages.create.return_value = _mock_response(wrapped)

    retrieved_schema = {"sales_transactions": ["deal_date", "price", "is_canceled"]}
    sql = sql_agent.text_to_sql([{"role": "user", "content": "최근 거래"}], None, retrieved_schema)

    assert "```" not in sql
    assert sql.strip().upper().startswith("SELECT")


def test_text_to_sql_strips_generic_codeblock(mock_client):
    """응답이 ``` 만 있는 (language 태그 없음) 코드블록도 제거."""
    wrapped = "```\nSELECT 1 FROM sales_transactions WHERE is_canceled = FALSE LIMIT 10\n```"
    mock_client.messages.create.return_value = _mock_response(wrapped)

    retrieved_schema = {"sales_transactions": ["is_canceled"]}
    sql = sql_agent.text_to_sql([{"role": "user", "content": "아무거나"}], None, retrieved_schema)
    assert "```" not in sql


def test_sql_agent_no_retry(mock_client):
    """validate_sql이 ValueError raise 시 LLM 재호출 없이 즉시 전파.

    plan이 명시적으로 요구한 회귀 방지 테스트.
    """
    # UPDATE는 SELECT가 아니므로 validate_sql이 ValueError raise
    mock_client.messages.create.return_value = _mock_response(
        "UPDATE sales_transactions SET price = 0"
    )

    retrieved_schema = {"sales_transactions": ["price"]}
    with pytest.raises(ValueError):
        sql_agent.text_to_sql(
            [{"role": "user", "content": "가격 업데이트"}], None, retrieved_schema
        )

    # LLM은 정확히 1회만 호출됐어야 한다 — 재시도 금지
    assert mock_client.messages.create.call_count == 1


# --- generate_answer ----------------------------------------------------------


def test_generate_answer_inline_for_small_results(mock_client):
    """5건 이하 → Haiku에게 전체 결과를 그대로 전달 (인라인 요약)."""
    mock_client.messages.create.return_value = _mock_response("3건의 거래가 있었습니다.")

    columns = ["deal_date", "price"]
    rows = [
        ("2024-01-01", 100000),
        ("2024-01-02", 120000),
        ("2024-01-03", 110000),
    ]
    sql = "SELECT deal_date, price FROM sales_transactions LIMIT 3"

    answer = sql_agent.generate_answer("최근 거래?", columns, rows, sql)

    assert isinstance(answer, str)
    assert mock_client.messages.create.call_count == 1
    _, kwargs = mock_client.messages.create.call_args
    # 사용자 프롬프트에 모든 3개 row 값이 등장해야 함 (인라인 모드)
    user_content = str(kwargs["messages"])
    assert "100000" in user_content
    assert "110000" in user_content
    assert "120000" in user_content


def test_generate_answer_summarizes_large_results(mock_client):
    """5건 초과 → 상위 3건 + 총 N건 문구 포함."""
    mock_client.messages.create.return_value = _mock_response(
        "최근 거래는 다음과 같습니다. 총 7건입니다."
    )

    columns = ["deal_date", "price"]
    rows = [(f"2024-01-{i:02d}", 100000 + i * 1000) for i in range(1, 8)]  # 7건
    sql = "SELECT deal_date, price FROM sales_transactions LIMIT 100"

    answer = sql_agent.generate_answer("거래 내역 보여줘", columns, rows, sql)

    assert isinstance(answer, str)
    assert mock_client.messages.create.call_count == 1
    _, kwargs = mock_client.messages.create.call_args
    user_content = str(kwargs["messages"])
    # 상위 3건의 price (100001000 의 101000, 102000, 103000) 포함
    assert "101000" in user_content
    assert "102000" in user_content
    assert "103000" in user_content
    # 총 건수 7 등장
    assert "7" in user_content
    # 4번째 이후 row는 프롬프트에 직접 포함되지 않음 (상위 3건 + 총 N건 요약 모드)
    assert "107000" not in user_content
