def calculate_loan(
    salary: int,
    savings: int,
    loan_years: int,
    interest_rate: float = 3.9,
    dsr_limit: float = 40,
) -> dict:
    """DSR 기반 최대 대출 가능액 계산.

    Args:
        salary: 연봉 (만원)
        savings: 보유 현금 (만원)
        loan_years: 대출 기간 (년)
        interest_rate: 연 금리 (%)
        dsr_limit: DSR 한도 (%)

    Returns:
        {"max_loan": int, "monthly_payment": int, "total_budget": int}
    """
    # 1. DSR 기준 최대 연간 원리금 상환액
    max_annual_payment = salary * (dsr_limit / 100)

    # 2. 월 최대 상환액
    monthly_payment = max_annual_payment / 12

    # 3. 원리금균등상환 역산: P = M × ((1+r)^n - 1) / (r × (1+r)^n)
    n = loan_years * 12  # 총 개월수

    if interest_rate == 0:
        max_loan = monthly_payment * n
    else:
        r = interest_rate / 100 / 12  # 월 금리
        compound = (1 + r) ** n
        max_loan = monthly_payment * (compound - 1) / (r * compound)

    max_loan = int(max_loan)
    monthly_payment = int(monthly_payment)
    total_budget = savings + max_loan

    return {
        "max_loan": max_loan,
        "monthly_payment": monthly_payment,
        "total_budget": total_budget,
    }
