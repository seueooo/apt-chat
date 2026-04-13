"""/api/chat 엔드포인트 테스트.

LLM / DB는 monkeypatch로 mock. 라우터 흐름(헤더 검증, rate limit, cache, 에러 매핑)만 검증.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from services import query_cache, rate_limit

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    """각 테스트마다 caches와 rate limit 초기화."""
    query_cache.clear()
    rate_limit.clear_all()
    yield
    query_cache.clear()
    rate_limit.clear_all()


@pytest.fixture
def mock_pipeline(monkeypatch):
    """sql_agent 2단계 파이프라인과 execute_query를 성공 경로로 mock.

    intent 경로 사용(extract_intent_and_tables가 intent 반환 → text_to_sql 호출 안 됨).
    """
    from routers import chat as chat_module

    def fake_extract(messages, context):
        intent = {"type": "recent_transactions", "region": "강남구", "limit": 5}
        schema = {"sales_transactions": ["deal_date"]}
        return intent, schema

    def fake_intent_to_sql(intent):
        # validate_sql을 통과하는 간단한 SELECT
        return (
            "SELECT s.deal_date, a.apartment_name, s.price "
            "FROM sales_transactions s "
            "JOIN apartments a USING (apartment_id) "
            "JOIN regions r USING (region_id) "
            "WHERE r.sigungu = %s AND s.is_canceled = FALSE "
            "ORDER BY s.deal_date DESC LIMIT 5"
        )

    def fake_execute_query(sql, params=None, statement_timeout_ms=10000):
        columns = ["deal_date", "apartment_name", "price"]
        rows = [("2024-01-15", "래미안", 43000)]
        return columns, rows

    def fake_generate_answer(question, columns, rows, sql):
        return "강남구 최근 거래 내역입니다."

    monkeypatch.setattr(chat_module, "extract_intent_and_tables", fake_extract)
    monkeypatch.setattr(chat_module, "intent_to_sql", fake_intent_to_sql)
    monkeypatch.setattr(chat_module, "execute_query", fake_execute_query)
    monkeypatch.setattr(chat_module, "generate_answer", fake_generate_answer)


def _body(question: str = "강남구 최근 거래 5건"):
    return {
        "messages": [{"role": "user", "content": question}],
        "context": None,
        "summarize": True,
    }


def test_missing_session_id_returns_400():
    """X-Session-Id 헤더 없으면 400."""
    res = client.post("/api/chat", json=_body())
    assert res.status_code == 400


def test_success_response_shape(mock_pipeline):
    """정상 경로 → 필수 필드 존재."""
    res = client.post("/api/chat", json=_body(), headers={"X-Session-Id": "sess1"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "sql" in data
    assert "columns" in data
    assert "rows" in data
    assert "visualization" in data
    assert "warnings" in data
    assert data["cache_hit"] is False
    assert data["remaining_questions"] == rate_limit.MAX_REQUESTS_PER_SESSION - 1


def test_cache_hit_on_second_call(mock_pipeline):
    """동일 질문 두 번째 호출은 cache hit, LLM 재호출 없음."""
    res1 = client.post("/api/chat", json=_body(), headers={"X-Session-Id": "sess-c"})
    assert res1.status_code == 200
    assert res1.json()["cache_hit"] is False

    res2 = client.post("/api/chat", json=_body(), headers={"X-Session-Id": "sess-c"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["cache_hit"] is True
    # 캐시 hit도 rate limit 카운터 증가 → 2회 사용
    assert data2["remaining_questions"] == rate_limit.MAX_REQUESTS_PER_SESSION - 2


def test_rate_limit_exceeded_returns_429(mock_pipeline):
    """MAX+1회째 요청은 429."""
    headers = {"X-Session-Id": "sess-rl"}
    for _ in range(rate_limit.MAX_REQUESTS_PER_SESSION):
        res = client.post("/api/chat", json=_body(), headers=headers)
        assert res.status_code == 200

    res = client.post("/api/chat", json=_body(), headers=headers)
    assert res.status_code == 429


def test_sql_validation_failure_returns_400(monkeypatch):
    """text_to_sql이 ValueError raise → 400, 재시도 없음."""
    from routers import chat as chat_module

    def fake_extract(messages, context):
        return None, {"sales_transactions": ["deal_date"]}  # intent None → Step 2

    def fake_text_to_sql(messages, context, retrieved_schema):
        raise ValueError("unsafe sql")

    monkeypatch.setattr(chat_module, "extract_intent_and_tables", fake_extract)
    monkeypatch.setattr(chat_module, "text_to_sql", fake_text_to_sql)

    res = client.post("/api/chat", json=_body(), headers={"X-Session-Id": "sess-v"})
    assert res.status_code == 400


def test_db_timeout_returns_504(monkeypatch):
    """DB statement_timeout 초과 → 504."""
    import psycopg.errors

    from routers import chat as chat_module

    def fake_extract(messages, context):
        intent = {"type": "recent_transactions", "region": "강남구"}
        return intent, {}

    def fake_intent_to_sql(intent):
        return "SELECT s.deal_date FROM sales_transactions s WHERE s.is_canceled = FALSE LIMIT 5"

    def fake_execute_query(sql, params=None, statement_timeout_ms=10000):
        raise psycopg.errors.QueryCanceled("statement timeout")

    monkeypatch.setattr(chat_module, "extract_intent_and_tables", fake_extract)
    monkeypatch.setattr(chat_module, "intent_to_sql", fake_intent_to_sql)
    monkeypatch.setattr(chat_module, "execute_query", fake_execute_query)

    res = client.post("/api/chat", json=_body(), headers={"X-Session-Id": "sess-t"})
    assert res.status_code == 504


def test_empty_messages_returns_400():
    """messages가 비어있으면 400."""
    res = client.post(
        "/api/chat",
        json={"messages": [], "context": None},
        headers={"X-Session-Id": "sess-e"},
    )
    # pydantic validation 또는 핸들러 검증 어느 쪽이든 4xx
    assert res.status_code in (400, 422)


def test_cache_not_set_on_error(monkeypatch):
    """SQL validation 실패 시 캐시에 저장하지 않음 (재호출 시 또 fail)."""
    from routers import chat as chat_module

    call_count = {"n": 0}

    def fake_extract(messages, context):
        call_count["n"] += 1
        return None, {"sales_transactions": ["deal_date"]}

    def fake_text_to_sql(messages, context, retrieved_schema):
        raise ValueError("bad")

    monkeypatch.setattr(chat_module, "extract_intent_and_tables", fake_extract)
    monkeypatch.setattr(chat_module, "text_to_sql", fake_text_to_sql)

    headers = {"X-Session-Id": "sess-ne"}
    res1 = client.post("/api/chat", json=_body(), headers=headers)
    assert res1.status_code == 400
    res2 = client.post("/api/chat", json=_body(), headers=headers)
    assert res2.status_code == 400
    # 캐시 미저장 → 2번 다 extract 호출됐어야 함
    assert call_count["n"] == 2
