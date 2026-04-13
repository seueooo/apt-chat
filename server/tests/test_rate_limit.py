"""rate_limit 모듈 단위 테스트."""

import pytest

from services import rate_limit


@pytest.fixture(autouse=True)
def _reset():
    """각 테스트마다 내부 카운터 초기화."""
    rate_limit.clear_all()
    yield
    rate_limit.clear_all()


def test_new_session_allows_max_requests():
    """새 세션은 MAX_REQUESTS_PER_SESSION 회까지 허용."""
    session = "s1"
    for _ in range(rate_limit.MAX_REQUESTS_PER_SESSION):
        rate_limit.check_and_increment(session)  # 예외 없어야 함


def test_exceeding_max_raises():
    """MAX+1회째 RateLimitExceeded 발생."""
    session = "s1"
    for _ in range(rate_limit.MAX_REQUESTS_PER_SESSION):
        rate_limit.check_and_increment(session)
    with pytest.raises(rate_limit.RateLimitExceeded):
        rate_limit.check_and_increment(session)


def test_check_and_increment_returns_remaining():
    """check_and_increment은 증가 후 남은 요청 수를 반환."""
    session = "s-return"
    remaining = rate_limit.check_and_increment(session)
    assert remaining == rate_limit.MAX_REQUESTS_PER_SESSION - 1

    remaining = rate_limit.check_and_increment(session)
    assert remaining == rate_limit.MAX_REQUESTS_PER_SESSION - 2

    remaining = rate_limit.check_and_increment(session)
    assert remaining == 0


def test_independent_sessions():
    """서로 다른 세션 ID는 독립된 카운터."""
    for _ in range(rate_limit.MAX_REQUESTS_PER_SESSION):
        rate_limit.check_and_increment("session-A")

    # session-B는 여전히 MAX회 가능
    remaining = rate_limit.check_and_increment("session-B")
    assert remaining == rate_limit.MAX_REQUESTS_PER_SESSION - 1


def test_get_remaining_without_increment():
    """get_remaining은 카운터를 증가시키지 않음."""
    session = "s-get"
    assert rate_limit.get_remaining(session) == rate_limit.MAX_REQUESTS_PER_SESSION

    rate_limit.check_and_increment(session)
    assert rate_limit.get_remaining(session) == rate_limit.MAX_REQUESTS_PER_SESSION - 1
    # 재조회해도 동일
    assert rate_limit.get_remaining(session) == rate_limit.MAX_REQUESTS_PER_SESSION - 1


def test_get_remaining_new_session_returns_max():
    """새 세션은 MAX 반환."""
    assert rate_limit.get_remaining("brand-new") == rate_limit.MAX_REQUESTS_PER_SESSION


def test_reset_clears_single_session():
    """reset(session_id)은 해당 세션만 초기화."""
    for _ in range(rate_limit.MAX_REQUESTS_PER_SESSION):
        rate_limit.check_and_increment("s-reset")
    for _ in range(2):
        rate_limit.check_and_increment("s-other")

    rate_limit.reset("s-reset")
    assert rate_limit.get_remaining("s-reset") == rate_limit.MAX_REQUESTS_PER_SESSION
    # 다른 세션은 영향 없음
    assert rate_limit.get_remaining("s-other") == rate_limit.MAX_REQUESTS_PER_SESSION - 2
