"""세션 기반 요청 빈도 제한.

- In-memory `dict[session_id, int]` + `threading.Lock`.
- 서버 재시작 시 초기화. 단일 프로세스 범위에서만 동작.
- 카운터는 cache hit 여부와 무관하게 증가. 남용 방지 목적.
"""

from __future__ import annotations

import threading

MAX_REQUESTS_PER_SESSION = 3


class RateLimitExceeded(Exception):  # noqa: N818 — plan-specified public name
    """세션당 허용 한도 초과."""


_counters: dict[str, int] = {}
_lock = threading.Lock()


def check_and_increment(session_id: str) -> int:
    """세션 카운터를 증가시키고 남은 요청 수를 반환.

    Args:
        session_id: 세션 식별자.

    Returns:
        증가 후 남은 요청 수 (0..MAX).

    Raises:
        RateLimitExceeded: 이미 MAX회 요청을 소비한 경우.
    """
    with _lock:
        current = _counters.get(session_id, 0)
        if current >= MAX_REQUESTS_PER_SESSION:
            raise RateLimitExceeded(
                f"session {session_id} exceeded {MAX_REQUESTS_PER_SESSION} requests"
            )
        _counters[session_id] = current + 1
        return MAX_REQUESTS_PER_SESSION - _counters[session_id]


def get_remaining(session_id: str) -> int:
    """카운터를 증가시키지 않고 남은 요청 수를 반환."""
    with _lock:
        used = _counters.get(session_id, 0)
    return max(0, MAX_REQUESTS_PER_SESSION - used)


def reset(session_id: str) -> None:
    """특정 세션 카운터 초기화. 테스트 전용."""
    with _lock:
        _counters.pop(session_id, None)


def clear_all() -> None:
    """전체 세션 카운터 초기화. 테스트 전용."""
    with _lock:
        _counters.clear()
