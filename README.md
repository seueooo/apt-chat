# apt-chat

> 연봉 기반 아파트 시뮬레이터와 Text-to-SQL AI 챗봇을 한 화면에 모은 실거래가 대시보드.

## 프로젝트 소개

apt-chat은 서울 아파트 실거래 데이터를 바탕으로 "내 연봉으로 살 수 있는 집"을 찾아볼 수 있는 웹 서비스입니다.
좌측 시뮬레이터가 DSR 기반 대출 한도와 총예산을 계산해 매물 목록을 보여주고, 우측 AI 챗봇이 같은 데이터셋에 대해 자연어 질문 → SQL 변환 → 결과 시각화를 수행합니다.
두 기능이 한 대시보드에서 컨텍스트를 공유하므로, 슬라이더를 조정하고 곧바로 "방금 조건에서 평당가가 가장 높은 동은?"이라고 물어볼 수 있습니다.

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

## 기술 스택

| 영역     | 스택                                                                                           |
| -------- | ---------------------------------------------------------------------------------------------- |
| Backend  | Python 3.12, FastAPI, uvicorn, Anthropic SDK, sqlglot, psycopg3, pydantic-settings, cachetools |
| Frontend | Next.js 16 (App Router), React 19, TypeScript 5, TanStack Query 5, Recharts 3, Tailwind CSS 4  |
| Database | Supabase (Postgres)                                                                            |
| ETL      | Python 3.12, pandas, psycopg3, requests, xmltodict                                             |
| 툴체인   | pnpm 9.4 workspace, Biome 2, ruff, lefthook, Docker Compose                                    |

## 문서 목록

- **Architecture**
  - [Request Flow](./docs/architecture/request-flow.md) — 컴포넌트 구성과 두 주요 플로우의 시퀀스 다이어그램
- **ADRs**
  - [ADR-0001 — 기술 스택](./docs/ADRs/ADR-0001-tech-stack.md)
  - [ADR-0002 — Text-to-SQL 파이프라인](./docs/ADRs/ADR-0002-text-to-sql.md)
- **Development**
  - [Project Structure](./docs/development/PROJECT_STRUCTURE.md) — 모노레포 디렉토리 트리
  - [Optimization Log](./docs/development/optimization-log.md) — 성능 최적화 기록
