"""query_cache 모듈 단위 테스트.

TDD: 실패 테스트 → 구현 → 통과.
"""

import pytest
from cachetools import TTLCache

from services import query_cache


@pytest.fixture(autouse=True)
def _reset_cache():
    """각 테스트마다 cache를 초기화해 상태 격리."""
    query_cache.clear()
    yield
    query_cache.clear()


def test_make_cache_key_normalizes_whitespace_and_case():
    """대소문자/공백만 다른 동일 질문은 같은 key를 반환."""
    k1 = query_cache.make_cache_key("강남구 최근 거래 5건", None)
    k2 = query_cache.make_cache_key("  강남구   최근 거래 5건  ", None)
    k3 = query_cache.make_cache_key("강남구 최근 거래 5건", {})
    assert k1 == k2
    # None과 빈 dict는 다를 수 있거나 같을 수 있음 — 여기서는 context 없음(None)과
    # 빈 dict를 동일 취급(정규화 정책). 만약 다르게 구현하면 테스트도 조정.
    assert k1 == k3


def test_make_cache_key_different_context_differs():
    """context가 다르면 key가 달라야 함."""
    k1 = query_cache.make_cache_key("최근 거래", {"region": "강남구"})
    k2 = query_cache.make_cache_key("최근 거래", {"region": "서초구"})
    assert k1 != k2


def test_make_cache_key_context_order_independent():
    """context dict 키 순서가 달라도 동일 key."""
    k1 = query_cache.make_cache_key("q", {"a": 1, "b": 2})
    k2 = query_cache.make_cache_key("q", {"b": 2, "a": 1})
    assert k1 == k2


def test_set_and_get_returns_same_payload():
    """set 후 get은 동일한 dict 반환."""
    key = query_cache.make_cache_key("강남구", None)
    payload = {"answer": "hello", "sql": "SELECT 1"}
    query_cache.set(key, payload)
    got = query_cache.get(key)
    assert got == payload


def test_get_miss_returns_none():
    """없는 key는 None."""
    assert query_cache.get("nonexistent-key") is None


def test_same_question_hits_cache_second_time():
    """동일 질문 두 번째 호출은 hit."""
    key1 = query_cache.make_cache_key("강남구 거래", None)
    query_cache.set(key1, {"answer": "A"})

    key2 = query_cache.make_cache_key("강남구 거래", None)
    got = query_cache.get(key2)
    assert got == {"answer": "A"}


def test_case_and_whitespace_only_difference_hits():
    """대소문자/공백만 다른 질문은 hit."""
    key1 = query_cache.make_cache_key("Gangnam Apartments", None)
    query_cache.set(key1, {"answer": "A"})

    key2 = query_cache.make_cache_key("  gangnam   apartments  ", None)
    assert query_cache.get(key2) == {"answer": "A"}


def test_different_context_misses():
    """context가 다르면 miss."""
    k1 = query_cache.make_cache_key("q", {"region": "강남구"})
    query_cache.set(k1, {"answer": "A"})

    k2 = query_cache.make_cache_key("q", {"region": "서초구"})
    assert query_cache.get(k2) is None


def test_ttl_expiry(monkeypatch):
    """TTL 만료 시 get이 None 반환."""
    fake_time = [1000.0]

    def fake_timer() -> float:
        return fake_time[0]

    # TTLCache는 생성 시 timer를 받음. 테스트용 cache를 교체.
    test_cache = TTLCache(
        maxsize=query_cache.CACHE_MAXSIZE,
        ttl=query_cache.CACHE_TTL_SECONDS,
        timer=fake_timer,
    )
    monkeypatch.setattr(query_cache, "_cache", test_cache)

    key = query_cache.make_cache_key("q", None)
    query_cache.set(key, {"answer": "A"})
    assert query_cache.get(key) == {"answer": "A"}

    # TTL + 1초 경과
    fake_time[0] += query_cache.CACHE_TTL_SECONDS + 1
    assert query_cache.get(key) is None


def test_maxsize_eviction(monkeypatch):
    """maxsize 초과 시 오래된 항목 eviction."""
    # 작은 캐시로 교체
    small_cache = TTLCache(maxsize=2, ttl=query_cache.CACHE_TTL_SECONDS)
    monkeypatch.setattr(query_cache, "_cache", small_cache)

    query_cache.set("k1", {"v": 1})
    query_cache.set("k2", {"v": 2})
    query_cache.set("k3", {"v": 3})  # k1 eviction 유발

    # k1은 evict되고 k2, k3는 존재
    assert query_cache.get("k1") is None
    assert query_cache.get("k2") == {"v": 2}
    assert query_cache.get("k3") == {"v": 3}


def test_stats_returns_size_and_limits():
    """stats()는 현재 캐시 크기와 설정 값을 반환."""
    query_cache.set("k1", {"v": 1})
    stats = query_cache.stats()
    assert stats["size"] == 1
    assert stats["maxsize"] == query_cache.CACHE_MAXSIZE
    assert stats["ttl"] == query_cache.CACHE_TTL_SECONDS
