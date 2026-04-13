# Definition of Done — MVP

## Backend

- `/api/simulate`, `/api/regions`, `/api/stats`, `/api/chat`, `/api/health` 엔드포인트가 구현되고 pytest 커버리지를 갖는다.
- `ruff check .`이 exit 0, `pytest`가 exit 0 (현재 101 passed).
- `validate_sql`이 모든 실패 케이스에서 재시도 없이 즉시 예외를 전파하며, 회귀 테스트가 존재한다.
- `query_cache`와 `rate_limit`은 `threading.Lock`으로 보호된다.
- API 응답 스펙이 `web/lib/types.ts`와 1:1로 일치한다.
- 신규 환경 변수는 `api/.env.example`과 동기화된다.

## Frontend

- `pnpm biome check`가 exit 0, `pnpm tsc --noEmit`이 exit 0.
- 색상/간격은 `DESIGN.md` 토큰만 사용하며 hex/rgba/기본 Tailwind 팔레트 직접 사용은 0건.
- 모든 인터랙티브 컴포넌트에 `'use client'` 지시자, `app/page.tsx`는 Server Component 유지.
- 한글 IME 조합 중 Enter 오전송이 발생하지 않는다.
- 클라이언트 세션당 3회 제한, 4번째 요청 차단, 새 탭 독립, 429 응답 시 카운터를 0으로 강제한다.
- `web/app/api/[...path]/route.ts` 프록시가 `X-Session-Id` 헤더를 FastAPI로 포워딩한다.

## Documentation

- `docs/README.md` 인덱스가 최신 상태를 반영한다.
- 주요 결정은 ADR로 기록된다 (`docs/ADRs/ADR-NNNN-*.md`).
- `PROJECT_STRUCTURE.md`가 실제 디렉토리 트리와 일치한다.
- 신규 환경 변수와 스택 변경은 ADR과 `.env.example`에 반영된다.

## Security

- `ANTHROPIC_API_KEY`는 `api/.env`에만 존재한다. `web/.env`, 브라우저 번들, 프록시 `route.ts` 어디에도 포함되지 않는다.
- 클라이언트 → Anthropic 직접 호출 경로가 없고 Next.js 프록시 경유가 강제된다.
- 원시 SQL에 f-string 보간을 금지하고 psycopg `%s` 파라미터 바인딩만 사용한다.
- DB 오류 메시지는 사용자에게 타임아웃 등 일반 문구만 노출하며, 상세 예외는 서버 로그에만 남긴다.

## Operations

- `make dev`로 API와 Web이 동시에 기동된다.
- `pnpm build` (web)과 `pytest` (api)가 모두 성공한다.
- lefthook pre-commit 훅이 ruff + biome을 자동 실행한다.
- Task 15 Docker 이미지 빌드는 현재 미완 — 별도 태스크로 진행한다.
- 실기기 smoke: 세션당 3회 질문 제한, 캐시 히트, 429 상태 동기화, 시뮬레이터 디바운스가 정상 동작한다.
