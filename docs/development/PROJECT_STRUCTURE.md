# Project Structure

pnpm workspace 기반 모노레포. 백엔드(`api/`), 프런트엔드(`web/`), 데이터 수집(`etl/`), 문서(`docs/`)가 단일 저장소에 공존한다.

```
apt-chat/
├── AGENTS.md                       # 에이전트 작업 규약
├── DESIGN.md                       # 디자인 토큰 + UI 가이드
├── Makefile                        # make dev 등 개발 편의 타겟
├── README.md                       # 루트 README (작성 예정)
├── biome.json                      # biome(JS/TS) 설정
├── lefthook.yml                    # pre-commit 훅 (ruff + biome)
├── package.json                    # workspace 루트
├── pnpm-workspace.yaml             # web 워크스페이스 정의
│
├── api/                            # FastAPI 백엔드 (Python 3.12)
│   ├── config.py                   # pydantic-settings Settings
│   ├── main.py                     # FastAPI app + CORS + router include
│   ├── pyproject.toml              # ruff 설정 등
│   ├── requirements.txt            # 런타임 의존성
│   ├── requirements-dev.txt        # pytest/ruff 등
│   ├── agent/                      # Text-to-SQL 에이전트
│   │   ├── intent_mapper.py        # SUPPORTED_INTENTS + intent_to_sql 템플릿
│   │   ├── prompts.py              # Claude 시스템/유저 프롬프트
│   │   ├── schema_retrieval.py     # 키워드 정규식 기반 스키마 선택
│   │   ├── sql_agent.py            # extract_intent, text_to_sql, generate_answer
│   │   └── validators.py           # sqlglot AST 기반 validate_sql
│   ├── db/
│   │   └── connection.py           # psycopg[pool] 연결 풀 + execute_query
│   ├── routers/                    # FastAPI APIRouter
│   │   ├── chat.py                 # /api/chat
│   │   ├── simulate.py             # /api/simulate
│   │   └── stats.py                # /api/regions, /api/stats
│   ├── services/                   # 순수 서비스 로직 (I/O 경계 최소화)
│   │   ├── loan_calculator.py      # DSR + 금리 기반 한도 계산
│   │   ├── query_cache.py          # TTLCache 1000/24h + Lock
│   │   ├── query_formatter.py      # detect_visualization + format_warnings
│   │   └── rate_limit.py           # 세션당 3회 + Lock
│   └── tests/                      # pytest (현재 101 passed)
│       ├── test_chat.py
│       ├── test_intent_mapper.py
│       ├── test_loan_calculator.py
│       ├── test_prompts.py
│       ├── test_query_cache.py
│       ├── test_query_formatter.py
│       ├── test_rate_limit.py
│       ├── test_schema_retrieval.py
│       ├── test_simulate.py
│       ├── test_sql_agent.py
│       ├── test_stats.py
│       └── test_validators.py
│
├── web/                            # Next.js 16 App Router + React 19
│   ├── app/
│   │   ├── layout.tsx              # 루트 레이아웃
│   │   ├── page.tsx                # Server Component (Dashboard 진입점)
│   │   ├── globals.css             # Tailwind v4 디자인 토큰
│   │   └── api/[...path]/route.ts  # FastAPI 프록시 (X-Session-Id 포워딩)
│   ├── components/
│   │   ├── Dashboard.tsx           # 시뮬레이터 + 챗봇 레이아웃
│   │   ├── providers.tsx           # TanStack Query 프로바이더
│   │   ├── Simulator/              # 시뮬레이터 UI
│   │   │   ├── AdvancedSettings.tsx
│   │   │   ├── AptList.tsx
│   │   │   ├── RegionSelector.tsx
│   │   │   ├── SliderGroup.tsx
│   │   │   └── SummaryCards.tsx
│   │   └── Chat/                   # 챗봇 UI
│   │       ├── ChartDisplay.tsx
│   │       ├── ChatWindow.tsx
│   │       ├── ContextBadge.tsx
│   │       ├── MessageBubble.tsx
│   │       └── SampleQuestions.tsx
│   ├── hooks/
│   │   ├── useChat.ts              # TanStack useMutation
│   │   └── useSimulator.ts         # TanStack useQuery (디바운스)
│   ├── lib/
│   │   ├── api.ts                  # fetch 래퍼
│   │   ├── session.ts              # 세션 ID + 클라이언트 3회 카운터
│   │   └── types.ts                # API 응답 타입 (백엔드와 1:1)
│   ├── utils/format.ts             # 숫자/가격 포매터
│   ├── next.config.ts
│   ├── package.json
│   ├── postcss.config.mjs
│   └── tsconfig.json
│
├── etl/                            # 공공데이터포털 → Supabase ETL
│   ├── collect.py                  # 원본 수집
│   ├── constants.py
│   ├── load.py                     # Supabase 적재
│   ├── schema.sql                  # regions/apartments/sales_transactions
│   └── transform.py                # 정규화
│
└── docs/                           # 이 문서들
    ├── README.md
    ├── architecture/
    ├── ADRs/
    ├── development/
    └── process/
```

## 제외 (git 추적 안 함)

- `docs/superpowers/` — 로컬 도구용 디렉토리
- `node_modules/`, `.next/`, `web/.next/` — JS 빌드 산출물
- `api/.venv/`, `__pycache__/` — Python 가상환경 및 캐시
- `api/.env`, `web/.env` — 환경 변수 (각각 `.env.example` 참고)
