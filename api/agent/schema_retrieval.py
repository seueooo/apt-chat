"""Rule-based schema retrieval for Text-to-SQL agent.

목적:
    전체 스키마를 프롬프트에 박제하지 않기 위해, 유저 질문에서 관련 테이블 2~4개와
    필요한 컬럼만 추출한다. Embedding 없이 키워드 정규식만으로 동작.

규칙:
    - 반환 테이블 수 최대 4개 (현재 허용 테이블이 3개이므로 실질적으로 최대 3개)
    - 각 테이블은 primary key + 질문 매칭 컬럼만 포함 (전체 컬럼 반환 금지)
    - 매칭 실패 시 안전한 기본값 반환
    - SCHEMA_CATALOG는 etl/schema.sql과 1:1 일치
"""

import re

# --- Schema Catalog ------------------------------------------------------------
# 허용 테이블 3개의 컬럼 → 한국어 설명.
# 실제 etl/schema.sql의 컬럼명과 1:1 일치해야 한다.
SCHEMA_CATALOG: dict[str, dict[str, str]] = {
    "sales_transactions": {
        "transaction_id": "거래 PK",
        "apartment_id": "아파트 FK (apartments.apartment_id)",
        "deal_date": "거래일 (DATE)",
        "deal_year": "거래 연도 (INTEGER)",
        "deal_month": "거래 월 (INTEGER)",
        "exclusive_area": "전용면적 ㎡ (NUMERIC). 평 변환: ÷ 3.306",
        "floor": "층수 (INTEGER)",
        "price": "거래 가격 (INTEGER, 단위: 만원). 1억 = 10000",
        "price_per_pyeong": "평당 가격 (NUMERIC, 만원/평)",
        "is_canceled": "해제 거래 여부 (BOOLEAN). 기본적으로 FALSE로 필터링",
    },
    "apartments": {
        "apartment_id": "아파트 PK",
        "apartment_name": "아파트 이름 (TEXT)",
        "region_id": "지역 FK (regions.region_id)",
        "jibun": "지번 주소",
        "road_name": "도로명 주소",
        "build_year": "준공 연도 (INTEGER)",
    },
    "regions": {
        "region_id": "지역 PK",
        "sido": "시/도 (예: 서울특별시)",
        "sigungu": "시/군/구 (예: 강남구)",
        "dong": "읍/면/동",
        "sigungu_code": "법정동 시군구 코드",
    },
}

# --- Primary key 매핑 ---------------------------------------------------------
_PRIMARY_KEYS: dict[str, str] = {
    "sales_transactions": "transaction_id",
    "apartments": "apartment_id",
    "regions": "region_id",
}

# --- Keyword → (table, column) 매핑 -------------------------------------------
# 키워드 정규식이 매칭되면 해당 (테이블, 컬럼)을 결과에 추가.
_KEYWORD_RULES: list[tuple[str, str, str]] = [
    # 거래/매매 관련 → sales_transactions
    (r"거래|매매|실거래|체결", "sales_transactions", "deal_date"),
    (r"최근|최신|요즘", "sales_transactions", "deal_date"),
    (r"가격|금액|값|price", "sales_transactions", "price"),
    (r"평균|avg|mean", "sales_transactions", "price"),
    (r"최대|최고|max|제일\s*비싼", "sales_transactions", "price"),
    (r"최소|최저|min|제일\s*싼", "sales_transactions", "price"),
    (r"평당|per\s*pyeong", "sales_transactions", "price_per_pyeong"),
    (r"면적|평수|㎡|제곱미터|area", "sales_transactions", "exclusive_area"),
    (r"층|floor", "sales_transactions", "floor"),
    (r"월별|월간|monthly", "sales_transactions", "deal_month"),
    (r"연도|연별|연간|yearly", "sales_transactions", "deal_year"),
    (r"해제|취소|cancel", "sales_transactions", "is_canceled"),
    # 아파트 이름/단지
    (r"아파트|단지|apt|apartment", "apartments", "apartment_name"),
    (r"이름|명칭|name", "apartments", "apartment_name"),
    (r"준공|신축|구축|build", "apartments", "build_year"),
    (r"도로명", "apartments", "road_name"),
    (r"지번|주소", "apartments", "jibun"),
    # 지역
    (r"구|시|군|동|지역|동네", "regions", "sigungu"),
    (r"서울|경기|인천|부산|대구|광주|대전|울산|세종", "regions", "sido"),
    (r"[가-힣]{1,4}구\b", "regions", "sigungu"),
    (r"[가-힣]{1,4}동\b", "regions", "dong"),
]

# --- 외부 공개용 KEYWORD_TO_TABLES --------------------------------------------
# 각 키워드가 매핑되는 테이블 목록. 테스트/디버깅 용도로 노출.
KEYWORD_TO_TABLES: dict[str, list[str]] = {}
for _pattern, _table, _col in _KEYWORD_RULES:
    KEYWORD_TO_TABLES.setdefault(_pattern, [])
    if _table not in KEYWORD_TO_TABLES[_pattern]:
        KEYWORD_TO_TABLES[_pattern].append(_table)


MAX_TABLES = 4


def _default_schema() -> dict[str, list[str]]:
    """매칭 실패 시 기본값."""
    return {
        "sales_transactions": [
            "transaction_id",
            "apartment_id",
            "deal_date",
            "price",
            "is_canceled",
        ],
        "apartments": ["apartment_id", "apartment_name", "region_id"],
        "regions": ["region_id", "sigungu"],
    }


def retrieve_relevant_schema(question: str) -> dict[str, list[str]]:
    """유저 질문에서 관련 테이블/컬럼을 추출.

    Args:
        question: 자연어 질문 (한국어 허용).

    Returns:
        {테이블명: [컬럼 목록]} 형태. 각 테이블은 primary key + 매칭된 컬럼만 포함.
        매칭 실패 시 안전한 기본값 반환.
    """
    if not question or not question.strip():
        return _default_schema()

    # 테이블별 매칭 점수와 선택된 컬럼 추적
    matched: dict[str, set[str]] = {}
    scores: dict[str, int] = {}

    for pattern, table, column in _KEYWORD_RULES:
        if re.search(pattern, question, flags=re.IGNORECASE):
            matched.setdefault(table, set()).add(column)
            scores[table] = scores.get(table, 0) + 1

    if not matched:
        return _default_schema()

    # JOIN 가능성을 위한 FK 보강:
    # - sales_transactions가 선택되었고 apartments/regions 중 하나라도 매칭되면
    #   apartment_id(FK) 포함 유지 (primary key 로직으로 이미 포함됨)
    # - apartments가 선택되었고 regions가 매칭되면 region_id(FK) 포함
    if "apartments" in matched and "regions" in matched:
        matched["apartments"].add("region_id")
    if "sales_transactions" in matched and "apartments" in matched:
        matched["sales_transactions"].add("apartment_id")

    # 점수 상위 4개만 남김 (현재 허용 테이블이 3개이므로 실질적으로 전체)
    top_tables = sorted(matched.keys(), key=lambda t: -scores.get(t, 0))[:MAX_TABLES]

    result: dict[str, list[str]] = {}
    for table in top_tables:
        cols = matched[table]
        # Primary key 항상 포함 (JOIN 가능하도록)
        pk = _PRIMARY_KEYS.get(table)
        if pk:
            cols.add(pk)
        # 존재하는 컬럼만 필터링 (오매핑 방어)
        valid = [c for c in cols if c in SCHEMA_CATALOG[table]]
        # 카탈로그 순서 유지
        catalog_order = list(SCHEMA_CATALOG[table].keys())
        valid.sort(key=catalog_order.index)
        result[table] = valid

    return result
