# ADR-0001: 기술 스택 선택 — FastAPI + Next.js + Supabase

## Status

Accepted — 2026-04 (MVP 시점)

## Context

- 연봉 기반 시뮬레이터(DSR 계산)와 Text-to-SQL 챗봇을 단일 대시보드에 함께 제공해야 한다.
- Anthropic API 키는 서버 외부에 노출될 수 없다.
- 공공데이터포털 실거래가를 주기적으로 수집해 DB에 적재한다.
- 모노레포 단일 저장소에 BE/FE/ETL/Docs가 공존한다.

## Decision

- **Backend**: FastAPI 0.115+, Python 3.12, `psycopg[binary,pool]` 3.2+, `pydantic-settings`, `anthropic` SDK, `sqlglot`, `cachetools`.
- **Frontend**: Next.js 16 (App Router), React 19, TypeScript 5, Tailwind v4, TanStack Query 5, Recharts 3.
- **Database**: Supabase (PostgreSQL). 테이블 3개 — `regions`, `apartments`, `sales_transactions`.
- **툴체인**: ruff + pytest (BE), biome + tsc (FE), lefthook pre-commit.
- Next.js Route Handler(`web/app/api/[...path]/route.ts`)를 FastAPI 프록시로 사용한다. 클라이언트는 Anthropic을 직접 호출하지 않는다.

## Consequences

**이점**
- `sqlglot` AST 기반 검증으로 SQL 안전성을 결정론적으로 보장.
- Next.js 프록시가 브라우저와 Anthropic 사이를 차단해 API 키 유출 경로가 없다.
- Supabase PostgreSQL의 partial index, CTE, window 함수를 그대로 활용 가능.

**단점 / 트레이드오프**
- 배포 시 API + Web 두 프로세스를 기동해야 한다 (Task 15 Docker 작업에서 해결 예정, 현재 미완).
- Next.js 16은 이전 버전 대비 breaking change가 많아 `web/AGENTS.md`에 주의 경고가 필요하다.
- Anthropic SDK는 동기 호출 기반이므로 FastAPI에서 executor 경유가 필요하다.

## Alternatives considered

- **Django + DRF**: 풀스택 프레임워크지만 sqlglot + pydantic-settings 조합 상 FastAPI가 더 가볍다.
- **Supabase Edge Functions**: Deno 런타임 제약으로 `anthropic` SDK 사용이 번거롭다.
- **LangChain 등 LLM 프레임워크**: 비용 제어 관점에서 기각 (ADR-0002 참조).
