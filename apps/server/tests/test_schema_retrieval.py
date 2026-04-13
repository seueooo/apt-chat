"""schema_retrieval 단위 테스트.

규칙 검증:
- 반환 테이블 수 <= 4
- 각 테이블의 컬럼 수 < SCHEMA_CATALOG의 전체 컬럼 수 (primary key + 매칭된 컬럼만)
- 매칭 실패 시 기본값 반환
- SCHEMA_CATALOG는 허용 3개 테이블만 포함
"""

from agent.schema_retrieval import (
    KEYWORD_TO_TABLES,
    SCHEMA_CATALOG,
    retrieve_relevant_schema,
)


def test_catalog_contains_only_allowed_tables():
    """SCHEMA_CATALOG는 sales_transactions / apartments / regions 3개 테이블만 포함."""
    assert set(SCHEMA_CATALOG.keys()) == {"sales_transactions", "apartments", "regions"}


def test_catalog_has_real_columns():
    """카탈로그 컬럼은 실제 apps/etl/schema.sql 스키마의 컬럼명과 일치."""
    sales_cols = set(SCHEMA_CATALOG["sales_transactions"].keys())
    # 핵심 컬럼
    assert {"deal_date", "price", "is_canceled", "exclusive_area"}.issubset(sales_cols)
    # plan이 경고한 잘못된 컬럼명 금지
    assert "apt_name" not in SCHEMA_CATALOG["apartments"]
    assert "apartment_name" in SCHEMA_CATALOG["apartments"]
    assert "sigungu" in SCHEMA_CATALOG["regions"]


def test_retrieve_returns_at_most_4_tables():
    """허용 테이블이 3개뿐이므로 반환은 어떤 경우에도 4개 이하."""
    for question in [
        "강남구 최근 거래 5건",
        "송파구 평균 가격",
        "전체 아파트 목록",
        "잠실 지역 월별 추이",
        "",
    ]:
        result = retrieve_relevant_schema(question)
        assert len(result) <= 4


def test_retrieve_recent_transactions_case():
    """'강남구 최근 거래 5건' — sales_transactions + regions 필수."""
    result = retrieve_relevant_schema("강남구 최근 거래 5건")
    assert "sales_transactions" in result
    # 지역 매칭이 있어야 regions 포함
    assert "regions" in result


def test_retrieve_average_price_case():
    """'송파구 평균 가격' — sales_transactions의 price + regions."""
    result = retrieve_relevant_schema("송파구 평균 가격")
    assert "sales_transactions" in result
    assert "price" in result["sales_transactions"]
    assert "regions" in result


def test_retrieve_apartment_list_case():
    """'전체 아파트 목록' — apartments 필수."""
    result = retrieve_relevant_schema("전체 아파트 목록")
    assert "apartments" in result
    assert "apartment_name" in result["apartments"]


def test_retrieve_columns_subset_of_catalog():
    """반환된 컬럼 수가 CATALOG 전체 컬럼 수보다 작거나 같아야 함 (전체 나열 금지 검증)."""
    result = retrieve_relevant_schema("강남구 최근 거래")
    for table, cols in result.items():
        full_cols = set(SCHEMA_CATALOG[table].keys())
        assert set(cols).issubset(full_cols)
        # 일반적인 질문에서는 모든 컬럼이 나오지 않아야 함 (명시적 컬럼 선택)
        assert len(cols) < len(full_cols)


def test_retrieve_fallback_default():
    """매칭 실패 (의미 없는 질문) 시 기본값 반환."""
    result = retrieve_relevant_schema("asdfzzzz")
    assert "sales_transactions" in result
    assert "deal_date" in result["sales_transactions"]
    assert "price" in result["sales_transactions"]
    assert "is_canceled" in result["sales_transactions"]
    assert "apartments" in result
    assert "apartment_name" in result["apartments"]
    assert "regions" in result
    assert "sigungu" in result["regions"]


def test_primary_keys_included_when_table_referenced():
    """테이블이 선택되면 primary key가 포함되어야 함 (JOIN 가능하도록)."""
    result = retrieve_relevant_schema("강남구 최근 거래")
    if "sales_transactions" in result:
        assert "transaction_id" in result["sales_transactions"]
    if "apartments" in result:
        assert "apartment_id" in result["apartments"]
    if "regions" in result:
        assert "region_id" in result["regions"]


def test_keyword_mapping_exists():
    """KEYWORD_TO_TABLES는 dict[str, list[str]] 형태."""
    assert isinstance(KEYWORD_TO_TABLES, dict)
    for keyword, tables in KEYWORD_TO_TABLES.items():
        assert isinstance(keyword, str)
        assert isinstance(tables, list)
        for t in tables:
            assert t in SCHEMA_CATALOG
