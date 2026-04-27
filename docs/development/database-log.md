# Database Log

데이터베이스 설계 및 데이터 처리 관련 기록. 새 엔트리는 **상단에 추가** (최신순).

엔트리 형식:

- **문제** — 무엇이 문제였는가
- **원인** — 왜 그런 동작이 나왔는가
- **기존 방식** — 수정 전 코드/접근
- **수정 방식** — 수정 후 코드/접근
- **결과** — 측정치 또는 관찰된 변화

---

## AI 생성 SQL의 보안 — sqlglot AST 검증 파이프라인

### 문제

챗봇이 자연어를 SQL로 바꾸는 구조라, LLM이 `DROP TABLE`, `DELETE`, 다중 statement 삽입 같은 의도하지 않은 쿼리를 뱉어낼 위험을 막지 못했다. 프롬프트 레벨 제약만으로는 악의적 입력(prompt injection)을 다 막아낼 수 없다.

### 원인

LLM 출력은 같은 입력에도 다른 답을 낸다. 시스템 프롬프트에 "SELECT만 사용하라"고 못 박아도, 사용자가 교묘한 프롬프트를 끼워 넣으면 LLM이 `DELETE FROM sales_transactions; --` 같은 쿼리를 뱉어낸다. 문자열 패턴 매칭(`sql.startswith("SELECT")`)으로는 CTE, 서브쿼리, 세미콜론 기반 다중 문 등을 다 걸러내지 못한다.

### 기존 방식

LLM 시스템 프롬프트에 "SELECT만 생성하라"는 지시만 존재. 별도 검증 없이 생성된 SQL을 그대로 DB에 실행했다.

### 수정 방식

`sqlglot`으로 SQL을 AST(Abstract Syntax Tree)로 파싱한 뒤, 트리 자체를 직접 뜯어보는 검증 단계를 끼워 넣었다.

```python
# agent/validators.py
ALLOWED_TABLES = {"sales_transactions", "apartments", "regions"}
MAX_LIMIT = 100
MAX_JOINS = 3
MAX_SUBQUERY_DEPTH = 2

def validate_sql(sql: str) -> str:
    statements = sqlglot.parse(sql, dialect="postgres")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise ValueError("단일 SQL statement만 허용됩니다.")

    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise ValueError("SELECT 문만 허용됩니다.")

    for table in tree.find_all(exp.Table):
        if table.name and table.name not in ALLOWED_TABLES:
            raise ValueError(f"허용되지 않은 테이블: {table.name}")

    if len(list(tree.find_all(exp.Join))) > MAX_JOINS:
        raise ValueError("JOIN 수 초과")

    if _get_subquery_depth(tree) > MAX_SUBQUERY_DEPTH:
        raise ValueError("서브쿼리 깊이 초과")

    # LIMIT 자동 보정
    limit_node = tree.find(exp.Limit)
    if limit_node is None:
        tree = tree.limit(DEFAULT_LIMIT)
    elif int(limit_node.expression.this) > MAX_LIMIT:
        limit_node.set("expression", exp.Literal.number(MAX_LIMIT))

    return tree.sql(dialect="postgres")  # AST → SQL 재생성
```

검증 항목:

| 규칙                | 방어 대상                                                     |
| ------------------- | ------------------------------------------------------------- |
| SELECT만 허용       | INSERT/UPDATE/DELETE/DROP 차단                                |
| 단일 statement      | 세미콜론 기반 다중 문 공격                                    |
| 테이블 화이트리스트 | `pg_catalog`, `information_schema` 등 시스템 테이블 접근 차단 |
| JOIN 3개 제한       | Cartesian explosion으로 인한 DB 부하                          |
| 서브쿼리 2중첩 제한 | 과도한 재귀 쿼리 방지                                         |
| LIMIT 자동 보정     | 대량 데이터 반환 차단 (없으면 100, 초과 시 100으로 클램핑)    |

마지막에 `tree.sql(dialect="postgres")`로 AST를 다시 SQL 문자열로 찍어 내면, 원본 SQL에 숨겨 둔 주석이나 비표준 구문도 같이 정리된다.

### 결과

- intent 경로(템플릿 SQL)와 LLM 생성 경로 **모두** 같은 검증을 거친다 — 어느 경로로 들어와도 검증 강도는 같다.
- `validate_sql` 실패 시 재시도 없이 곧장 400으로 응답한다 — 실패한 쿼리를 "고쳐서 다시 시도"하는 루프가 없어 비용도 지연도 늘지 않는다.

---

## 공공 API 재호출 시 중복 적재 — 멱등 ETL과 해시 기반 source_id

### 문제

공공 데이터 API를 다시 부르면 똑같은 거래가 중복으로 들어왔다. API가 페이지네이션이라 같은 응답이 두 번씩 끼고, 스케줄러가 주기적으로 호출할 때마다 기존 데이터를 또 가져왔다.

### 원인

공공 API 응답에는 고유 식별자(PK)가 없다. 같은 거래를 다른 시점에 호출하면 ETL이 같은 데이터를 새 row로 또 적재했다.

### 기존 방식

```python
INSERT INTO sales_transactions (...) VALUES (%s, ...)
# ON CONFLICT 없음 → 재실행 시 중복 적재
```

### 수정 방식

거래마다 고유 키를 만들려고 거래 속성의 조합(시군구코드, 년, 월, 일, 아파트명, 층, 면적, 가격, 신고일)을 SHA-256으로 해시해 `source_id`로 썼다. 테이블에 `UNIQUE` 제약을 걸고 `ON CONFLICT DO NOTHING`으로 중복을 무시한다.

```python
# etl/load.py
def make_source_id(row) -> str:
    fields = [
        str(row.sigungu_code), str(row.deal_year), str(row.deal_month),
        str(row.deal_day), str(row.apartment_name), str(row.floor),
        str(row.exclusive_area), str(row.price), str(row.reg_date),
    ]
    return hashlib.sha256("|".join(fields).encode()).hexdigest()

INSERT_SALES_SQL = """
INSERT INTO sales_transactions (apartment_id, source_id, ...)
VALUES (%s, %s, ...)
ON CONFLICT (source_id) DO NOTHING
"""
```

같은 패턴을 regions(`UNIQUE(sido, sigungu, dong)`)와 apartments(`UNIQUE(apartment_name, region_id, jibun)`)에도 적용해 ETL 전체가 멱등하게 돌아간다.

```python
# 3단계 의존 관계: regions → apartments → sales_transactions
with psycopg.connect(DB_URL) as conn:
    with conn.cursor() as cur:
        # 1단계: regions 적재 + commit → region_id 매핑 조회
        cur.executemany(INSERT_REGIONS_SQL, region_values)
        conn.commit()
        cur.execute("SELECT region_id, sido, sigungu, dong FROM regions")
        region_map = {(r[1], r[2], r[3]): r[0] for r in cur.fetchall()}

        # 2단계: apartments 적재 (region_id FK 참조) + commit
        cur.executemany(INSERT_APARTMENTS_SQL, apt_values)
        conn.commit()

        # 3단계: sales_transactions 배치 적재 (1000건 단위)
        for batch in batches:
            cur.executemany(INSERT_SALES_SQL, batch)
            conn.commit()
```

### 결과

- ETL을 몇 번 다시 돌려도 데이터 건수가 그대로다 — `ON CONFLICT DO NOTHING`이 기존 데이터를 무시한다.
- 각 단계를 커밋한 뒤 다음 단계에서 FK 매핑을 조회하는 흐름이라, 단계마다 어떤 FK에 의존하는지 코드에 그대로 보인다.

---

## 취소 거래 필터링 비효율 — Partial Index 적용

### 문제

거의 모든 조회 쿼리에 `WHERE is_canceled = FALSE` 조건이 붙는데, 일반 인덱스는 취소 거래까지 다 끌고 다녀 무거웠다.

### 원인

일반 B-Tree 인덱스는 `is_canceled` 값과 무관하게 전체 row를 인덱싱한다. 정작 비즈니스 쿼리 대부분은 유효 거래(`is_canceled = FALSE`)만 보는데도, 인덱스 단계에서 취소건을 미리 떼어낼 수 없었다.

### 기존 방식

```sql
CREATE INDEX idx_sales_date ON sales_transactions (deal_date DESC);
CREATE INDEX idx_sales_price ON sales_transactions (price);
```

### 수정 방식

Postgres의 Partial Index를 써서 `is_canceled = FALSE`인 row만 인덱싱했다.

```sql
-- 유효 거래만 인덱싱 (취소건 제외)
CREATE INDEX idx_sales_active_date
    ON sales_transactions (deal_date DESC)
    WHERE is_canceled = FALSE;

CREATE INDEX idx_sales_active_price
    ON sales_transactions (price)
    WHERE is_canceled = FALSE;

CREATE INDEX idx_sales_active_year_month
    ON sales_transactions (deal_year, deal_month)
    WHERE is_canceled = FALSE;
```

`deal_date DESC` 내림차순 인덱스로 "최근 거래"를 뽑을 때 역순 스캔 없이 인덱스 순서대로 읽는다. `(deal_year, deal_month)` 복합 인덱스는 월별 추이 집계(`GROUP BY deal_year, deal_month`)에 최적화.

### 결과

- 인덱스가 취소 거래를 물리적으로 들고 있지 않아 인덱스가 가벼워졌다. `WHERE is_canceled = FALSE` 쿼리가 들어오면 쿼리 플래너가 Partial Index를 알아서 골라 쓴다.
- 내림차순 인덱스(`deal_date DESC`) 덕분에 최근 거래를 뽑을 때 정렬 비용 없이 인덱스 순서대로 읽어 돌려준다.

---

## LLM 생성 쿼리의 무한 실행 — Statement Timeout + Graceful 실패 처리

### 문제

LLM이 만든 SQL 중 비효율적인 쿼리(예: 인덱스를 못 타는 full scan, 큰 집계) 한 건이 커넥션을 오래 붙들고 있어 풀이 동나곤 했다.

### 원인

AI가 만드는 SQL은 어떻게 나올지 모른다. sqlglot 검증으로 트리 검사로 구조는 막을 수 있지만, 쿼리 비용까지는 미리 가늠하기 어렵다. 타임아웃 없이 돌리면 쿼리 한 건이 전체 응답을 막을 수 있다.

### 수정 방식

`SET LOCAL statement_timeout`으로 쿼리별 타임아웃을 걸었다. `SET LOCAL`은 현재 트랜잭션에만 적용되니 옆 커넥션에는 번지지 않는다.

```python
# db/connection.py
def execute_query(
    sql: str,
    params: tuple | None = None,
    statement_timeout_ms: int = 5000,
) -> tuple[list[str], list[tuple]]:
    with get_db() as conn:
        with conn.cursor() as cur:
            timeout_sql = psql.SQL("SET LOCAL statement_timeout = {}").format(
                psql.Literal(statement_timeout_ms)
            )
            cur.execute(timeout_sql)
            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
        conn.commit()
    return columns, rows
```

라우터에서는 타임아웃과 DB 장애를 따로 잡아 처리한다.

```python
# routers/chat.py
try:
    columns, rows = execute_query(sql, params, statement_timeout_ms=10000)
except psycopg.errors.QueryCanceled as exc:
    raise HTTPException(status_code=504, detail="DB 쿼리 시간이 초과됐습니다") from exc
except (psycopg.errors.OperationalError, PoolTimeout):
    columns, rows = [], []
    warnings.append("데이터베이스 오류로 결과를 가져오지 못했습니다")
    db_error = True
```

에러 유형별 처리 전략:

| 예외                               | HTTP           | 동작                                       |
| ---------------------------------- | -------------- | ------------------------------------------ |
| `QueryCanceled`                    | 504            | 타임아웃 — 즉시 실패 반환                  |
| `OperationalError` / `PoolTimeout` | 200 + warnings | 빈 결과 + 경고 메시지, **캐시 저장 안 함** |

캐시는 DB 호출이 성공할 때만 넣는다. 그래서 실패 응답이 24시간 동안 굳어 있는 일이 없어졌다.

### 결과

- 10초가 넘는 쿼리는 알아서 끊긴다. 커넥션 풀이 비는 일도 막힌다.
- DB가 죽어도 서비스는 살아 있다. 경고를 달아 빈 결과를 돌려준다.
- `SET LOCAL` 덕분에 타임아웃 범위가 트랜잭션 단위로 갇혀 있어, 다른 요청에는 영향이 없다.

---

## 시뮬레이터 쿼리 — DISTINCT ON + Window Function 단일 패스 집계

### 문제

시뮬레이터에서 "예산 내 구매 가능한 아파트 목록"을 보여줄 때, 같은 아파트 거래가 여러 건이면 화면이 중복으로 가득 찼다. 게다가 총 건수를 알려면 COUNT 쿼리를 따로 한 번 더 던져야 했다.

### 원인

아파트 1개에 거래 이력이 수십 건 쌓여 있다. 단순 `WHERE price <= budget` 쿼리는 모든 이력을 다 돌려주고, 페이지네이션용 `total_count`를 알려면 같은 조건으로 `COUNT(*)`를 한 번 더 돌려야 했다.

### 수정 방식

Postgres의 `DISTINCT ON`으로 아파트별 최신 거래 1건만 뽑고, `COUNT(*) OVER()` Window Function으로 총 건수를 같은 쿼리에서 같이 받았다.

```sql
-- routers/simulate.py
WITH latest AS (
    SELECT DISTINCT ON (a.apartment_id)
        a.apartment_name, r.sigungu, r.dong,
        s.exclusive_area, s.floor, s.price, s.deal_date
    FROM sales_transactions s
    JOIN apartments a USING (apartment_id)
    JOIN regions r USING (region_id)
    WHERE s.is_canceled = FALSE AND s.price <= %s
    ORDER BY a.apartment_id, s.deal_date DESC
)
SELECT *, COUNT(*) OVER () AS total_count
FROM latest
ORDER BY deal_date DESC
LIMIT 200
```

`DISTINCT ON (a.apartment_id)` + `ORDER BY a.apartment_id, s.deal_date DESC` 조합으로 아파트마다 가장 최근 거래만 남기고, CTE 결과에 `COUNT(*) OVER()`를 붙여 집계 쿼리를 한 번 더 던지지 않고도 전체 건수를 같이 가져온다.

### 결과

- 아파트당 최신 거래 1건만 돌려준다 — 중복이 사라진다.
- DB를 한 번만 다녀와서 목록과 전체 건수를 같이 받아 온다.

---

## 캐시 키 충돌과 정규화 — 질문 해시 설계

### 문제

뜻이 같은 질문도 캐시에 안 걸렸다. "강남구 거래"와 " 강남구 거래 "가 다른 캐시 키로 떨어져 LLM과 DB를 쓸데없이 또 호출했다.

### 원인

질문 문자열을 그대로 캐시 키로 쓰면 공백 한 칸, 대소문자 차이만으로도 캐시 키가 갈린다.

### 수정 방식

질문을 정규화(소문자 + 공백 압축)하고, context를 정렬된 JSON으로 바꾼 뒤 SHA-256 해시를 캐시 키로 썼다.

```python
# services/query_cache.py
def _normalize_question(question: str) -> str:
    lowered = question.strip().lower()
    return re.compile(r"\s+").sub(" ", lowered)

def _normalize_context(context: dict | None) -> str:
    if not context:
        return "{}"
    return json.dumps(context, sort_keys=True, ensure_ascii=False)

def make_cache_key(last_question: str, context: dict | None) -> str:
    normalized_q = _normalize_question(last_question)
    normalized_ctx = _normalize_context(context)
    raw = f"{normalized_q}\x00{normalized_ctx}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

TTLCache(maxsize=1000, ttl=24h)를 쓰고, 모든 접근에 `threading.Lock`을 걸어 동시에 들어와도 깨지지 않게 했다. 키에는 히스토리 전체를 넣지 않고 마지막 질문과 context만 담았더니 히트율이 올랐다.

### 결과

- "강남구 거래", " 강남구 거래 ", "강남구 거래" 모두 같은 캐시 히트.
- 캐시가 맞으면 LLM도 DB도 한 번도 안 부른다 — 응답 시간이 짧아지고 API 비용도 같이 줄었다.
- DB 에러가 났을 때는 캐시 저장을 건너뛰니, 실패 응답이 24시간 동안 박혀 있는 일도 없다.
