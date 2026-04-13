from services.loan_calculator import calculate_loan


def test_basic_calculation():
    """기본 계산: 연봉 5000만, 저축 1억, 30년, 3.9%, DSR 40%."""
    result = calculate_loan(salary=5000, savings=10000, loan_years=30)
    assert "max_loan" in result
    assert "monthly_payment" in result
    assert "total_budget" in result
    assert result["total_budget"] == result["max_loan"] + 10000
    assert result["max_loan"] > 0
    assert result["monthly_payment"] > 0


def test_low_salary():
    """낮은 연봉 → 대출 한도 작아야 함."""
    low = calculate_loan(salary=2000, savings=5000, loan_years=30)
    high = calculate_loan(salary=8000, savings=5000, loan_years=30)
    assert low["max_loan"] < high["max_loan"]


def test_longer_loan_higher_amount():
    """대출 기간 길수록 → 대출 가능액 커야 함."""
    short = calculate_loan(salary=5000, savings=10000, loan_years=10)
    long = calculate_loan(salary=5000, savings=10000, loan_years=30)
    assert short["max_loan"] < long["max_loan"]


def test_zero_savings():
    """저축 0 → total_budget == max_loan."""
    result = calculate_loan(salary=5000, savings=0, loan_years=30)
    assert result["total_budget"] == result["max_loan"]


def test_monthly_payment_within_dsr():
    """월 상환액이 DSR 한도 이내인지 확인."""
    salary = 5000
    dsr_limit = 40
    result = calculate_loan(salary=salary, savings=10000, loan_years=30, dsr_limit=dsr_limit)
    max_annual = salary * (dsr_limit / 100)
    max_monthly = max_annual / 12
    assert result["monthly_payment"] <= max_monthly + 1  # 반올림 오차 허용


def test_zero_interest_rate():
    """금리 0% 예외 처리."""
    result = calculate_loan(salary=5000, savings=10000, loan_years=30, interest_rate=0.0)
    assert result["max_loan"] > 0
    # 0% 금리: DSR 한도 내 연간 상환액 × 대출 기간 = 대출원금
    expected = int(5000 * 0.4 / 12 * 30 * 12)
    assert result["max_loan"] == expected
