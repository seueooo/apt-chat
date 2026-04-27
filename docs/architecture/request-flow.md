# Request Flow

## Overview

브라우저는 Next.js 16의 App Router 프록시(`apps/web/app/api/[...path]/route.ts`)를 통해 FastAPI 백엔드와 통신한다. Anthropic SDK 호출과 Supabase(PostgreSQL) 연결은 모두 FastAPI 안에서만 일어나며, 클라이언트 번들에는 API 키가 포함되지 않는다. 시뮬레이터는 순수 계산 + DB 조회로 끝나고, 챗봇은 캐시 → 2단계 Claude → sqlglot 검증 → DB 실행을 거친다.

## 전체 아키텍처

상위 컴포넌트와 외부 의존성의 배치. Next.js는 프록시 역할만 하며 비즈니스 로직은 FastAPI에 집중된다.

```mermaid
flowchart TD
    subgraph Browser["Browser (React 19 Client Components)"]
        Dash[Dashboard.tsx]
        Sim[Simulator/*]
        Chat[Chat/*]
        UseSim[useSimulator<br/>TanStack Query]
        UseChat[useChat<br/>useMutation]
    end

    subgraph NextJS["Next.js 16 (App Router)"]
        Page[app/page.tsx<br/>Server Component]
        Proxy["app/api/[...path]/route.ts<br/>GET + POST 프록시"]
    end

    subgraph FastAPI["FastAPI (Python 3.12)"]
        SimR[routers/simulate.py]
        StatsR[routers/stats.py]
        ChatR[routers/chat.py]
        Agent[agent/<br/>sql_agent + validators<br/>intent_mapper + schema_retrieval]
        Services[services/<br/>loan_calculator<br/>query_cache<br/>rate_limit<br/>query_formatter]
        DB[db/connection.py<br/>psycopg pool]
    end

    Anthropic[(Anthropic API<br/>Haiku + Sonnet)]
    Supabase[(Supabase<br/>PostgreSQL)]

    Dash --> Sim
    Dash --> Chat
    Sim --> UseSim
    Chat --> UseChat
    UseSim -->|fetch /api/simulate| Proxy
    UseChat -->|fetch /api/chat<br/>X-Session-Id| Proxy
    Page --> Dash
    Proxy -->|forward X-Session-Id| SimR
    Proxy --> StatsR
    Proxy --> ChatR
    SimR --> Services
    SimR --> DB
    StatsR --> DB
    ChatR --> Services
    ChatR --> Agent
    ChatR --> DB
    Agent --> Anthropic
    DB --> Supabase
```

## 시뮬레이터 플로우

연봉·DSR·금리 입력이 바뀌면 `useSimulator`가 디바운스 후 `/api/simulate`를 호출한다. FastAPI는 `loan_calculator`로 대출 한도를 구하고 Supabase에서 조건에 맞는 아파트를 조회한다. LLM 호출은 없다.

```mermaid
sequenceDiagram
    participant U as User
    participant CW as Dashboard + Simulator/*
    participant H as useSimulator
    participant P as Next.js Proxy
    participant R as simulate router
    participant S as services/loan_calculator
    participant D as db/connection (Supabase)

    U->>CW: 연봉/DSR/금리/지역 변경
    CW->>H: 입력 반영
    H->>H: 디바운스
    H->>P: POST /api/simulate
    P->>R: POST /api/simulate
    R->>R: 입력 검증 (금리/DSR 상한)
    R->>S: calculate_loan_limit(...)
    S-->>R: 월납입/총대출 한도
    R->>D: execute_query (동적 WHERE + total count)
    D-->>R: (columns, rows)
    R-->>P: SimulateResponse
    P-->>H: JSON
    H-->>CW: SummaryCards + AptList 렌더
```

## 챗봇 플로우

챗봇은 세션 ID 검증 → rate limit → 캐시 → intent 추출 → (템플릿 또는 SQL 생성) → sqlglot 검증 → DB 실행 → 요약 생성 → 캐시 저장 순서로 동작한다. 캐시 히트는 LLM 호출을 0회로 만들고, intent 매칭은 Sonnet 호출을 생략한다.

```mermaid
sequenceDiagram
    participant U as User
    participant CW as Chat/ChatWindow
    participant H as useChat
    participant P as Next.js Proxy
    participant R as chat router
    participant RL as services/rate_limit
    participant QC as services/query_cache
    participant AG as agent/sql_agent
    participant IM as agent/intent_mapper
    participant V as agent/validators
    participant A as Anthropic API
    participant D as Supabase

    U->>CW: 질문 입력 (Enter)
    CW->>H: mutate(messages)
    H->>P: POST /api/chat (X-Session-Id)
    P->>R: forward header
    R->>RL: check_and_increment(session_id)
    alt 초과
        RL-->>R: RateLimitExceeded
        R-->>P: 429
    else 허용
        RL-->>R: remaining
        R->>QC: get(cache_key)
        alt cache hit
            QC-->>R: cached payload
            R-->>P: ChatResponse (cache_hit=true)
        else cache miss
            R->>AG: extract_intent_and_tables (Haiku)
            AG->>A: messages.create (haiku-4-5)
            A-->>AG: intent + retrieved_schema
            alt intent ∈ SUPPORTED_INTENTS
                R->>IM: intent_to_sql(intent)
                IM-->>R: 템플릿 SQL + params
            else intent 미매칭
                R->>AG: text_to_sql (Sonnet)
                AG->>A: messages.create (sonnet-4-6)
                A-->>AG: SQL
                AG-->>R: SQL (params 없음)
            end
            R->>V: validate_sql (sqlglot AST)
            V-->>R: 정규화된 SQL
            R->>D: execute_query (statement_timeout 10s)
            D-->>R: (columns, rows)
            R->>R: detect_visualization + format_warnings
            opt summarize=true AND rows 존재
                R->>AG: generate_answer (Haiku)
                AG->>A: messages.create (haiku-4-5)
                A-->>AG: answer text
            end
            R->>QC: set (db_error=false일 때만)
            R-->>P: ChatResponse (cache_hit=false, remaining_questions)
        end
    end
    P-->>H: JSON
    H-->>CW: MessageBubble + ChartDisplay 렌더
```

## 에러 처리

응답 실패 경로와 상태 코드. `validate_sql` 실패와 Claude API 오류 모두 **재시도하지 않고** 즉시 전파된다.

```mermaid
flowchart TD
    Req[POST /api/chat] --> Hdr{X-Session-Id?}
    Hdr -->|없음| E400A[400 세션 ID 필요]
    Hdr -->|있음| RL{rate_limit OK?}
    RL -->|초과| E429[429 세션당 최대 3회]
    RL -->|OK| Cache[cache 조회]
    Cache --> Pipeline[intent → SQL → validate_sql]
    Pipeline -->|ValueError| E400B[400 질문을 다시 작성해 주세요]
    Pipeline -->|anthropic.APIError| E500[500 AI 서비스 오류]
    Pipeline -->|OK| Exec[execute_query 10s]
    Exec -->|QueryCanceled| E504[504 DB 쿼리 시간 초과]
    Exec -->|OperationalError / PoolTimeout| Warn[경고 + 빈 결과<br/>cache 저장 안 함]
    Exec -->|OK| OK[200 ChatResponse]
    Warn --> OK
```

| 상태           | 조건                                                                               |
| -------------- | ---------------------------------------------------------------------------------- |
| 400            | `X-Session-Id` 누락, `validate_sql` 실패, intent 필수 파라미터 누락, 미지원 intent |
| 429            | `rate_limit.check_and_increment` 초과 (세션당 3회)                                 |
| 500            | `anthropic.APIError` (Claude 호출 실패)                                            |
| 504            | `psycopg.errors.QueryCanceled` (statement_timeout 10초)                            |
| 200 + warnings | `OperationalError` / `PoolTimeout` (결과 비고, 캐시 저장 스킵)                     |

## 비용 제어 포인트

- 재시도 루프 금지 — `validate_sql` 실패도 Claude API 오류도 즉시 HTTP 예외로 전파된다.
- 캐시 히트 시 LLM 호출 0회, DB 호출 0회. `query_cache`는 TTLCache(1000, 86400s) + `threading.Lock`.
- Intent 매칭 시 Sonnet 호출 생략 — Haiku 1회(extract_intent) + Haiku 1회(summarize)로 종결. 템플릿 SQL은 `intent_mapper.intent_to_sql`이 코드 상수로 반환.
- 서버 세션당 3회 제한(`rate_limit.check_and_increment`) + 클라이언트 `apps/web/lib/session.ts` 3회 제한으로 이중 보호. 캐시 히트도 카운트된다.
- Anthropic API 키는 `apps/server/.env`에만 존재하고 프록시는 해당 헤더를 포워딩하지 않는다.
