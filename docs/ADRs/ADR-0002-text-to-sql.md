# ADR-0002: Text-to-SQL — Claude SDK 직접 호출

## Status

Accepted — 2026-04

## Context

- 자연어 → SQL 변환이 챗봇의 핵심 기능이다.
- Anthropic API 호출 비용에 상한을 두어야 한다 (사용자 세션당 3회, 요청당 LLM 호출 최대 3회).
- SQL injection, 허가되지 않은 테이블, DELETE 등 파괴적 구문을 차단해야 한다.
- LLM이 실패할 때마다 자동 재시도하면 비용이 무한히 증가할 수 있다.

## Decision

- **Claude SDK 직접 호출** — LangChain / LlamaIndex 등 고수준 프레임워크 미사용.
- **2단계 파이프라인**
  - Step 1 — Haiku(`claude-haiku-4-5-20251001`): intent 추출 + 키워드 기반 schema retrieval.
  - Step 2 — Sonnet(`claude-sonnet-4-6`): intent가 `SUPPORTED_INTENTS`에 매칭되지 않을 때만 SQL을 생성한다.
  - intent 매칭 시 `agent/intent_mapper.intent_to_sql`의 코드 상수 템플릿으로 Step 2를 스킵한다.
- **SUPPORTED_INTENTS**: `recent_transactions`, `avg_price_by_region`, `monthly_trend`, `price_filter`, `top_apartments`.
- **Schema retrieval**: 키워드 정규식 기반 (`agent/schema_retrieval.py`). 벡터 임베딩 미사용.
- **SQL 검증**: `agent/validators.validate_sql`이 sqlglot AST로 파싱한 뒤 규칙을 강제한다.
  - `ALLOWED_TABLES` = {`sales_transactions`, `apartments`, `regions`}
  - SELECT 단일 statement만 허용
  - `MAX_JOINS = 3`, `MAX_SUBQUERY_DEPTH = 2`, `MAX_LIMIT = 100` (미지정 시 100으로 주입)
- **재시도 금지**: `validate_sql` 실패 → HTTP 400 즉시. `anthropic.APIError` → HTTP 500 즉시. `psycopg.errors.QueryCanceled` → HTTP 504.
- **캐시 + rate limit**: `services/query_cache` TTLCache(1000, 24h) + Lock, `services/rate_limit` 세션당 3회 + Lock. 템플릿 경로도 `validate_sql`을 한 번 더 통과시킨다.

## Consequences

**이점**

- 요청당 LLM 호출 상한이 명확하다 — 캐시 히트 0회, intent 매칭 1~2회, fallback 2~3회.
- sqlglot AST 검증으로 injection, 허가되지 않은 테이블, DELETE/UPDATE를 결정론적으로 차단.
- 필수 의존성은 `anthropic`, `sqlglot`, `psycopg` 셋이다.

**단점 / 트레이드오프**

- intent allowlist를 확장할 때마다 `intent_mapper`, `_intent_params`, 테스트를 함께 고쳐야 한다.
- 키워드 기반 schema retrieval이라 모호한 질의("비싼 거 보여줘")는 fallback(Sonnet) 경로로 빠진다.
- LangChain `SQLDatabaseChain` 등이 제공하는 체인 조합/자가 치유 기능은 포기한다.

## Alternatives considered

- **LangChain SQLDatabaseChain**: 프롬프트·재시도 로직이 내부에 숨어 있어 비용 제어가 어렵다.
- **LLM 기반 SQL 검증**: 결정론성이 없고 추가 호출이 발생한다.
- **Embedding 기반 schema retrieval**: 벡터 스토어/인덱스 관리 부담이 커 MVP 범위 밖.
