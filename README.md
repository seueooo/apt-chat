# apt-chat

> 연봉 기반 아파트 시뮬레이터와 Text-to-SQL AI 챗봇을 한 화면에서 제공하는 실거래가 대시보드.

## 프로젝트 소개

apt-chat은 서울 아파트 실거래 데이터를 바탕으로 "내 연봉으로 살 수 있는 집"을 한 번에 탐색할 수 있게 해 주는 웹 서비스입니다.
좌측 시뮬레이터가 DSR 기반 대출 한도와 총예산을 계산해 매물 목록을 보여주고, 우측 AI 챗봇이 같은 데이터셋에 대해 자연어 질문 → SQL 변환 → 결과 시각화를 수행합니다.
두 기능이 단일 대시보드에서 컨텍스트를 공유하기 때문에, 사용자는 슬라이더를 조정한 뒤 바로 "방금 조건에서 평당가가 가장 높은 동은?" 같은 질문으로 이어갈 수 있습니다.

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

### 3. AI 오케스트레이션 설계

AI native 방식으로 제작한 서비스입니다. 설계·파이프라인 구축·성능 최적화는 직접 담당하고, 코드 작성은 LLM에 위임했습니다.
하나의 plan 문서에 전체 구조와 기능을 태스크로 정리하고, 각 태스크를 탐색 → 구현 → 검증 3단계로 자동 실행하는 커스텀 스킬(apt-chat-exec)을 설계했습니다. 단계별로 역할 템플릿·스킬·모델을 다르게 주입해, AI 코드가 의도대로 생성되도록 하는 시스템을 구축했습니다.

```
apt-chat/
├── .claude/
│   └── skills/
│       └── apt-chat-exec/
│           ├── SKILL.md                # 오케스트레이터 — Phase 0~4, 모델 라우팅, 에러 처리
│           ├── server-implementer.md   # BE 워커 role — supabase-pg-bestpractice, TDD, 의존성 단방향
│           ├── web-implementer.md      # FE 워커 role — vercel-react-bestpractice, DESIGN.md 토큰 전용
│           └── verifier.md             # 검증 워커 role — ruff/pytest/biome/tsc raw output 강제
│
└── docs/
    └── plans/
        └── 2026-04-11-aptchat-mvp.md   # 진실 소스 (read-only) 인간(me)이 설계
                                        #  ├─ Goal / Architecture / Tech Stack
                                        #  ├─ Cost Control & Security Principles
                                        #  ├─ REQUIRED SKILLS ↔ Task 범위 매트릭스
                                        #  └─ Task 1..16 (체크박스 완료 조건)
```

plan 문서의 각 태스크마다 아래 3단계 루프가 반복 실행됩니다.

**Phase 1: Explore** (sonnet, 병렬)

- Claude Code 내장 Explore 서브에이전트를 파일 그룹당 하나씩 병렬 스폰
- 목적은 factual 리서치 전용 — "개선 제안·코드 품질 평가·구현 조언 금지"를 프롬프트에 명시
- run_in_background=true로 동시 실행 → 수천 라인 코드 조사를 wall-clock 수십 초에 완료

**Phase 2: Implement** (opus, 도메인별 병렬)

- 파일 경로로 도메인 자동 판별 (server / web / both)
- both인 경우 FastAPI 워커 + Next.js 워커를 병렬 스폰
- 각 워커에 role template + Task 발췌 + Phase 1 탐색 리포트 + 담당 파일 경로를 합친 독립 컨텍스트 주입
- 워커 내부에서 MUST-USE 스킬 2~3개를 먼저 호출한 뒤 TDD 사이클(실패 테스트 → 구현 → 통과)로 작업

**Phase 3: Verify** (sonnet, 독립 세션)

- 구현 워커 ≠ 검증 워커 — "성공했습니다" 거짓 양성 방지
- superpowers:verification-before-completion 스킬을 MUST-USE로 주입 ("증거 없이 성공 선언 금지" 원칙)
- ruff check, pytest, biome check, tsc --noEmit 실행 후 raw output을 응답에 그대로 인용하도록 강제
- 판정: 모든 exit 0 + 체크박스가 실제 파일에 반영 → 통과 / warning only → 통과(내용 보고) / error → 실패

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
