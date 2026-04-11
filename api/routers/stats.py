from fastapi import APIRouter

from db.connection import execute_query

router = APIRouter()


@router.get("/api/regions")
def get_regions():
    sql = """
    SELECT r.sigungu,
           COUNT(DISTINCT r.dong) AS dong_count,
           COUNT(DISTINCT a.apartment_id) AS apartment_count
    FROM regions r
    JOIN apartments a USING (region_id)
    GROUP BY r.sigungu
    ORDER BY r.sigungu
    """
    columns, rows = execute_query(sql)
    regions = [dict(zip(columns, row)) for row in rows]
    return {"regions": regions}


@router.get("/api/stats")
def get_stats():
    sql = """
    SELECT
        COUNT(*) FILTER (WHERE is_canceled = FALSE) AS total_transactions,
        COUNT(DISTINCT apartment_id) FILTER (WHERE is_canceled = FALSE) AS total_apartments,
        MIN(deal_date) FILTER (WHERE is_canceled = FALSE) AS date_from,
        MAX(deal_date) FILTER (WHERE is_canceled = FALSE) AS date_to
    FROM sales_transactions
    """
    columns, rows = execute_query(sql)
    row = rows[0]
    return {
        "total_transactions": row[0],
        "total_apartments": row[1],
        "date_range": {
            "from": str(row[2]),
            "to": str(row[3]),
        },
    }
