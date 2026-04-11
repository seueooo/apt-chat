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
    interest_rate: float = Field(default=3.9, ge=0, le=30)
    dsr_limit: float = Field(default=40, gt=0, le=100)


@router.post("/api/simulate")
def simulate(req: SimulateRequest):
    loan = calculate_loan(
        salary=req.salary,
        savings=req.savings,
        loan_years=req.loan_years,
        interest_rate=req.interest_rate,
        dsr_limit=req.dsr_limit,
    )

    # 조건 리스트 방식 — f-string에 동적 SQL 삽입 방지
    conditions = ["s.is_canceled = FALSE", "s.price <= %s"]
    params_list = [loan["total_budget"]]

    if req.region != "서울 전체":
        conditions.append("r.sigungu = %s")
        params_list.append(req.region)

    where_clause = " AND ".join(conditions)
    params = tuple(params_list)

    # 아파트별 최신 거래 1건만 추출 + 같은 CTE에서 count
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
        WHERE {where_clause}
        ORDER BY a.apartment_id, s.deal_date DESC
    )
    SELECT *, COUNT(*) OVER () AS total_count
    FROM latest
    ORDER BY deal_date DESC
    LIMIT 200
    """

    columns, rows = execute_query(sql, params, statement_timeout_ms=10000)

    apartments = []
    affordable_count = 0
    for row in rows:
        apt = dict(zip(columns, row))
        affordable_count = apt.pop("total_count")
        apt["deal_date"] = str(apt["deal_date"])
        apt["margin"] = loan["total_budget"] - apt["price"]
        apartments.append(apt)

    return {
        **loan,
        "affordable_count": affordable_count,
        "apartments": apartments,
    }
