import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"sales_transactions", "apartments", "regions"}
MAX_LIMIT = 100
DEFAULT_LIMIT = 100
MAX_JOINS = 3
MAX_SUBQUERY_DEPTH = 2


def _get_subquery_depth(node, current=0) -> int:
    """재귀적으로 서브쿼리 최대 깊이를 계산."""
    max_depth = current
    for sub in node.find_all(exp.Subquery):
        # 직접 자식 서브쿼리만 (이미 방문한 상위는 건너뜀)
        if sub.parent_select is not node:
            continue
        inner = sub.find(exp.Select)
        if inner:
            max_depth = max(max_depth, _get_subquery_depth(inner, current + 1))
    return max_depth


def validate_sql(sql: str) -> str:
    """검증 통과 시 정규화된 SQL 반환, 실패 시 ValueError raise."""

    # 다중 statement 체크
    statements = sqlglot.parse(sql, dialect="postgres")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise ValueError("단일 SQL statement만 허용됩니다.")

    tree = statements[0]

    # SELECT만 허용
    if not isinstance(tree, exp.Select):
        raise ValueError("SELECT 문만 허용됩니다.")

    # 허용 테이블 체크 (서브쿼리 포함)
    for table in tree.find_all(exp.Table):
        table_name = table.name
        if table_name and table_name not in ALLOWED_TABLES:
            raise ValueError(f"허용되지 않은 테이블: {table_name}")

    # JOIN 개수 제한
    joins = list(tree.find_all(exp.Join))
    if len(joins) > MAX_JOINS:
        raise ValueError(f"JOIN 수 초과: {len(joins)}개 (최대 {MAX_JOINS}개)")

    # 서브쿼리 깊이 제한
    depth = _get_subquery_depth(tree)
    if depth > MAX_SUBQUERY_DEPTH:
        raise ValueError(f"서브쿼리 깊이 초과: {depth}단계 (최대 {MAX_SUBQUERY_DEPTH}단계)")

    # LIMIT 처리
    limit_node = tree.find(exp.Limit)
    if limit_node is None:
        tree = tree.limit(DEFAULT_LIMIT)
    else:
        limit_val = limit_node.expression
        if isinstance(limit_val, exp.Literal) and limit_val.is_int:
            current = int(limit_val.this)
            if current > MAX_LIMIT:
                limit_node.set("expression", exp.Literal.number(MAX_LIMIT))

    return tree.sql(dialect="postgres")
