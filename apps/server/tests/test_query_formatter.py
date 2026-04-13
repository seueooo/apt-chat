"""query_formatter — detect_visualization / format_warnings 단위 테스트."""

from services.query_formatter import detect_visualization, format_warnings

# --- detect_visualization -----------------------------------------------------


def test_detect_line_for_time_series():
    """deal_year + deal_month + 수치 → line chart."""
    columns = ["deal_year", "deal_month", "avg_price"]
    rows = [(2024, 1, 100000), (2024, 2, 105000), (2024, 3, 110000)]
    result = detect_visualization(columns, rows)
    assert result is not None
    assert result["type"] == "line"
    assert "y" in result
    assert result["y"] == "avg_price"


def test_detect_bar_for_category():
    """sigungu + 수치 (30건 이하) → bar chart."""
    columns = ["sigungu", "avg_price"]
    rows = [("강남구", 200000), ("서초구", 180000), ("송파구", 150000)]
    result = detect_visualization(columns, rows)
    assert result is not None
    assert result["type"] == "bar"
    assert result["x"] == "sigungu"
    assert result["y"] == "avg_price"


def test_detect_bar_skipped_when_too_many_rows():
    """카테고리형이라도 30건 초과면 bar 차트 반환하지 않음."""
    columns = ["sigungu", "cnt"]
    rows = [(f"region_{i}", i) for i in range(31)]
    assert detect_visualization(columns, rows) is None


def test_detect_none_for_plain_table():
    """시계열/카테고리 컬럼 없음 → None."""
    columns = ["apartment_name", "deal_date"]
    rows = [("래미안", "2024-01-01")]
    assert detect_visualization(columns, rows) is None


def test_detect_none_for_empty_rows():
    """빈 결과 → None."""
    assert detect_visualization(["sigungu", "cnt"], []) is None


# --- format_warnings ----------------------------------------------------------


def test_warning_result_limited_100():
    """100건 결과 → '결과가 제한됨' 경고."""
    sql = "SELECT * FROM sales_transactions WHERE is_canceled = FALSE LIMIT 100"
    rows = [(i,) for i in range(100)]
    warnings = format_warnings(sql, rows, "강남구 거래")
    assert any("제한" in w for w in warnings)


def test_warning_no_rows():
    """0건 결과 → '데이터 없음' 경고."""
    sql = "SELECT * FROM sales_transactions WHERE is_canceled = FALSE"
    warnings = format_warnings(sql, [], "강남구 거래")
    assert any("데이터 없음" in w or "없음" in w for w in warnings)


def test_warning_missing_is_canceled_filter():
    """is_canceled 필터 미포함 → '해제 거래 포함 가능' 경고."""
    sql = "SELECT price FROM sales_transactions"
    warnings = format_warnings(sql, [(100,)], "평균 가격")
    assert any("해제" in w for w in warnings)


def test_no_warning_for_normal_result():
    """정상 결과 (is_canceled 포함, 0 < 건수 < 100) → 경고 없음."""
    sql = "SELECT price FROM sales_transactions WHERE is_canceled = FALSE LIMIT 10"
    rows = [(100,), (200,)]
    warnings = format_warnings(sql, rows, "평균 가격")
    assert warnings == []
