import pytest

from agent.validators import validate_sql

# --- SELECT만 허용 ---


def test_valid_select():
    result = validate_sql("SELECT * FROM sales_transactions")
    assert "SELECT" in result.upper()


def test_insert_rejected():
    with pytest.raises(ValueError, match="SELECT"):
        validate_sql("INSERT INTO sales_transactions (price) VALUES (100)")


def test_delete_rejected():
    with pytest.raises(ValueError, match="SELECT"):
        validate_sql("DELETE FROM sales_transactions")


def test_drop_rejected():
    with pytest.raises(ValueError, match="SELECT"):
        validate_sql("DROP TABLE sales_transactions")


# --- 단일 statement ---


def test_multi_statement_rejected():
    with pytest.raises(ValueError, match="단일"):
        validate_sql("SELECT 1; SELECT 2")


# --- 허용 테이블만 ---


def test_allowed_tables():
    result = validate_sql(
        "SELECT a.apartment_name FROM apartments a JOIN regions r ON a.region_id = r.region_id"
    )
    assert result


def test_forbidden_table():
    with pytest.raises(ValueError, match="허용되지 않은 테이블"):
        validate_sql("SELECT * FROM users")


def test_forbidden_table_in_subquery():
    with pytest.raises(ValueError, match="허용되지 않은 테이블"):
        validate_sql("SELECT * FROM apartments WHERE region_id IN (SELECT id FROM users)")


# --- LIMIT ---


def test_no_limit_adds_100():
    result = validate_sql("SELECT * FROM sales_transactions")
    assert "100" in result


def test_existing_limit_5_preserved():
    result = validate_sql("SELECT * FROM sales_transactions LIMIT 5")
    assert "5" in result


def test_limit_500_clamped_to_100():
    result = validate_sql("SELECT * FROM sales_transactions LIMIT 500")
    assert "500" not in result
    assert "100" in result


# --- JOIN 제한 ---


def test_3_joins_allowed():
    sql = """
    SELECT * FROM sales_transactions s
    JOIN apartments a ON s.apartment_id = a.apartment_id
    JOIN regions r ON a.region_id = r.region_id
    JOIN regions r2 ON r.region_id = r2.region_id
    """
    result = validate_sql(sql)
    assert result


def test_4_joins_rejected():
    sql = """
    SELECT * FROM sales_transactions s
    JOIN apartments a ON s.apartment_id = a.apartment_id
    JOIN regions r ON a.region_id = r.region_id
    JOIN regions r2 ON r.region_id = r2.region_id
    JOIN apartments a2 ON a.apartment_id = a2.apartment_id
    """
    with pytest.raises(ValueError, match="JOIN 수 초과"):
        validate_sql(sql)


# --- 서브쿼리 깊이 제한 ---


def test_subquery_depth_2_allowed():
    sql = """
    SELECT * FROM apartments
    WHERE region_id IN (
        SELECT region_id FROM regions
        WHERE sigungu IN (
            SELECT sigungu FROM regions WHERE sido = '서울특별시'
        )
    )
    """
    result = validate_sql(sql)
    assert result


def test_subquery_depth_3_rejected():
    sql = """
    SELECT * FROM apartments
    WHERE region_id IN (
        SELECT region_id FROM regions
        WHERE sigungu IN (
            SELECT sigungu FROM regions
            WHERE region_id IN (
                SELECT region_id FROM regions WHERE sido = '서울특별시'
            )
        )
    )
    """
    with pytest.raises(ValueError, match="서브쿼리 깊이 초과"):
        validate_sql(sql)
