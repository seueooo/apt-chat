# apt-chat

> 연봉 기반 아파트 시뮬레이터와 Text-to-SQL AI 챗봇을 한 화면에서 제공하는 실거래가 대시보드.

## 프로젝트 소개

apt-chat은 서울 아파트 실거래 데이터를 바탕으로 "내 연봉으로 살 수 있는 집"을 한 번에 탐색할 수 있게 해 주는 웹 서비스입니다. 좌측 시뮬레이터가 DSR 기반 대출 한도와 총예산을 계산해 매물 목록을 보여주고, 우측 AI 챗봇이 같은 데이터셋에 대해 자연어 질문 → SQL 변환 → 결과 시각화를 수행합니다. 두 기능이 단일 대시보드에서 컨텍스트를 공유하기 때문에, 사용자는 슬라이더를 조정한 뒤 바로 "방금 조건에서 평당가가 가장 높은 동은?" 같은 질문으로 이어갈 수 있습니다.

> 현재 상태: MVP. 서울 실거래 데이터에 한정되며, 프로덕션 배포 전 단계입니다.

## 주요 기능

### 1. 아파트 시뮬레이터

- **입력**: 연봉(만원), 가용 자금, 대출 기간, 지역(시군구/동), 금리·DSR 한도
- **출력**: 최대 대출 가능액, 월 상환액, 총예산, 구매 가능 매물 수와 목록
- **계산 방식**: 원리금균등상환 식을 역산해 DSR 한도를 지키는 최대 대출액 도출
- 엔드포인트: `POST /api/simulate`, `GET /api/regions`, `GET /api/stats`

### 2. AI 챗봇 (Text-to-SQL)

- 자연어 질문 → 2단계 Claude 파이프라인(Haiku intent 추출 → Sonnet SQL 생성) → sqlglot AST 검증 → Postgres 실행 → 한국어 답변 + 테이블/차트
- 시뮬레이터가 선택한 지역·예산을 그대로 챗봇 컨텍스트로 전달
- 비용 보호: TTL 캐시(24h, 1000 entry) + 세션당 최대 3회 rate limit
- 엔드포인트: `POST /api/chat` (헤더 `X-Session-Id` 필수)

## 빠른 시작 (Quick Start)

### 사전 준비

- Node.js 20+, pnpm 9.4.0
- Python 3.12+
- Postgres (Supabase 권장)
- Anthropic API Key, 공공데이터포털 API Key

### 로컬 개발 경로

```bash
# 1. 의존성 설치 + .env 복사 + git hook 설치
make setup

# 2. .env 값 채우기
#   apps/server/.env   → ANTHROPIC_API_KEY, SUPABASE_DB_URL, PUBLIC_DATA_API_KEY
#   apps/web/.env      → API_URL=http://localhost:8000
#   apps/etl/.env      → SUPABASE_DB_URL, PUBLIC_DATA_API_KEY

# 3. DB 스키마 적용
psql "$SUPABASE_DB_URL" -f apps/etl/schema.sql

# 4. ETL 실행 (공공데이터포털 → Supabase 적재)
cd apps/etl
python collect.py     # 원시 XML 수집
python transform.py   # 정제 CSV 생성
python load.py        # Supabase 적재
cd -

# 5. 개발 서버 동시 실행 (FastAPI :8000 + Next.js :3000)
make dev
```

브라우저에서 `http://localhost:3000` 접속.

### Docker 경로

```bash
# apps/server/.env 를 먼저 준비한 뒤
make docker-up        # server :8000 + web :3000
make docker-down
```

### Make 타겟 치트시트

| 타겟 | 설명 |
|---|---|
| `make setup` | install + .env.example 복사 + lefthook install |
| `make install` | pnpm install + server venv 생성 + pip install |
| `make dev` | FastAPI + Next.js 동시 실행 |
| `make dev-server` | FastAPI만 실행 (:8000) |
| `make dev-web` | Next.js만 실행 (:3000) |
| `make test` | pnpm test |
| `make lint` / `make format` | Biome + ruff 검사/포맷 |
| `make clean` | node_modules / .next / venv 정리 |
| `make docker-up` / `make docker-down` | Docker Compose 기동/종료 |

## 기술 스택

| 영역 | 스택 |
|---|---|
| Backend | Python 3.12, FastAPI, uvicorn, Anthropic SDK, sqlglot, psycopg3, pydantic-settings, cachetools |
| Frontend | Next.js 16 (App Router), React 19, TypeScript 5, TanStack Query 5, Recharts 3, Tailwind CSS 4 |
| Database | Supabase (Postgres) |
| ETL | Python 3.12, pandas, psycopg3, requests, xmltodict |
| 툴체인 | pnpm 9.4 workspace, Biome 2, ruff, lefthook, Docker Compose |

## 설계 의사결정 요약

apt-chat은 비용 제어와 보안을 가장 먼저 고려한 제약 기반 설계를 따릅니다.

**비용 제어**
- 전체 DB 스키마를 프롬프트에 통째로 넣지 않습니다. 질문과 관련된 테이블·컬럼만 동적으로 주입합니다.
- 2단계 모델 분할: Haiku로 intent를 뽑아 자주 묻는 질문은 템플릿 SQL로 처리하고, 새 질문일 때만 Sonnet을 호출합니다.
- TTLCache(24h, 1000 entry)와 세션당 3회 rate limit으로 반복 호출을 차단합니다.
- SQL 검증 실패 시 재시도 루프 없이 즉시 400 — LLM 재호출로 비용이 터지는 경로를 차단합니다.

**보안**
- 모든 LLM 호출은 브라우저 → Next.js API Route 프록시 → FastAPI → Anthropic 순으로만 흐릅니다. `NEXT_PUBLIC_ANTHROPIC_*` 같은 클라 노출 키를 쓰지 않습니다.
- `ANTHROPIC_API_KEY` 는 `apps/server/.env` 한 곳에만 존재합니다.
- 생성된 SQL은 sqlglot AST로 결정론적 검증을 거칩니다: ALLOWED_TABLES 화이트리스트, SELECT 전용, MAX_JOINS=3, MAX_SUBQUERY_DEPTH=2, MAX_LIMIT=100.
- LLM을 쿼리 검증용으로 쓰지 않습니다 — 검증은 코드로만.

자세한 근거는 아래 ADR에 있습니다.

## 문서

- [프로젝트 구조](./docs/development/PROJECT_STRUCTURE.md) — 디렉토리 트리와 책임 분리
- [ADR-0001: 기술 스택](./docs/ADRs/ADR-0001-tech-stack.md)
- [ADR-0002: Text-to-SQL 설계](./docs/ADRs/ADR-0002-text-to-sql.md)
- [요청 흐름 다이어그램](./docs/architecture/request-flow.md)
- [UI 디자인 토큰](./DESIGN.md)
