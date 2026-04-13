"""챗봇 응답 캐시 레이어.

- `cachetools.TTLCache` 기반 프로세스 내 캐시.
- 키: 정규화된 마지막 유저 질문 + context JSON → sha256.
- 히스토리는 키에 포함하지 않아 히트율을 높인다.
- TTLCache는 스레드 안전하지 않으므로 모든 접근은 `_lock`으로 보호.
- `ChatResponse`에 해당하는 dict 전체를 value로 저장.
- set은 validate_sql 통과 + DB 성공 후에만 호출될 것을 호출자가 보장.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading

from cachetools import TTLCache

CACHE_MAXSIZE = 1000
CACHE_TTL_SECONDS = 86400  # 24h

_cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
_lock = threading.Lock()

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_question(question: str) -> str:
    """질문 문자열을 소문자화하고 공백을 단일 space로 정규화."""
    if not question:
        return ""
    lowered = question.strip().lower()
    return _WHITESPACE_RE.sub(" ", lowered)


def _normalize_context(context: dict | None) -> str:
    """context를 정렬된 JSON 문자열로. None과 {} 는 동일 취급."""
    if not context:
        return "{}"
    return json.dumps(context, sort_keys=True, ensure_ascii=False)


def make_cache_key(last_question: str, context: dict | None) -> str:
    """정규화된 (질문, context) 조합에서 sha256 hex digest 생성.

    Args:
        last_question: 마지막 유저 질문 (원본). 내부에서 정규화.
        context: optional context dict. None/빈 dict 동일.

    Returns:
        64자리 hex sha256.
    """
    normalized_q = _normalize_question(last_question)
    normalized_ctx = _normalize_context(context)
    raw = f"{normalized_q}\x00{normalized_ctx}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(key: str) -> dict | None:
    """캐시 조회. 없거나 만료 시 None."""
    with _lock:
        return _cache.get(key)


def set(key: str, value: dict) -> None:
    """캐시에 저장. 호출자는 validate_sql + DB 성공 후에만 호출한다."""
    with _lock:
        _cache[key] = value


def clear() -> None:
    """테스트 전용: 캐시 전체 비우기."""
    with _lock:
        _cache.clear()


def stats() -> dict:
    """현재 캐시 사이즈와 설정 상수 반환."""
    with _lock:
        size = len(_cache)
    return {
        "size": size,
        "maxsize": CACHE_MAXSIZE,
        "ttl": CACHE_TTL_SECONDS,
    }
