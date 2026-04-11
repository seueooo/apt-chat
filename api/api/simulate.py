from fastapi import APIRouter
from pydantic import BaseModel, Field

from db.connection import execute_query
from services.loan_calculator import calculate_loan

router = APIRouter()


class SimulateRequest(BaseModel):
    salary: int = Field(ge=2000, le=50000)
    savings: int = Field(ge=0, le=50000)
    loan_years: int = Field(ge=10, le=40)
    region: str = "서울 전체"
    interest_rate: float = 3.9
    dsr_limit: float = 40


@router.post("/api/simulate")
def simulate(req: SimulateRequest):
    loan = calculate_loan(
        salary=req.salary,
        savings=req.savings,
        loan_years=req.loan_years,
        interest_rate=req.interest_rate,
        dsr_limit=req.dsr_limit,
    )

    # 아파트별 최신 거래 1건만 추출
    region_filter = ""
    params: tuple = (loan["total_budget"],)

    if req.region != "서울 전체":
        region_filter = "AND r.sigungu = %s"
        params = (loan["total_budget"], req.region)

    sql = f"""
    WITH latest AS (
        SELECT DISTINCT ON (a.apartment_id)
            a.apartment_name,
            r.sigungu,
            r.dong,
            s.exclusive_area,
            s.floor,
            s.price,
            s.deal_date
        FROM sales_transactions s
        JOIN apartments a USING (apartment_id)
        JOIN regions r USING (region_id)
        WHERE s.is_canceled = FALSE
          AND s.price <= %s
          {region_filter}
        ORDER BY a.apartment_id, s.deal_date DESC
    )
    SELECT * FROM latest ORDER BY deal_date DESC LIMIT 200
    """

    columns, rows = execute_query(sql, params, statement_timeout_ms=10000)

    apartments = []
    for row in rows:
        apt = dict(zip(columns, row))
        apt["deal_date"] = str(apt["deal_date"])
        apt["margin"] = loan["total_budget"] - apt["price"]
        apartments.append(apt)

    # affordable_count: LIMIT 전 아파트 수
    count_sql = f"""
    SELECT COUNT(DISTINCT a.apartment_id)
    FROM sales_transactions s
    JOIN apartments a USING (apartment_id)
    JOIN regions r USING (region_id)
    WHERE s.is_canceled = FALSE
      AND s.price <= %s
      {region_filter}
    """
    _, count_rows = execute_query(count_sql, params, statement_timeout_ms=10000)
    affordable_count = count_rows[0][0]

    return {
        **loan,
        "affordable_count": affordable_count,
        "apartments": apartments,
    }
