from typing import Dict, Any, Tuple, List

ALLOWED_SCHEMA = {
    "customers": {"id", "name", "email", "country", "status", "created_at"},
    "orders": {"id", "customer_id", "total_amount", "order_status", "purchase_date"},
    "products": {"id", "product_name", "price", "stock_count", "category"}
}

RELATIONSHIP_GRAPH = {
    ("orders", "customers"): "orders.customer_id = customers.id",
    ("customers", "orders"): "customers.id = orders.customer_id"
}

ALLOWED_OPERATORS = {
    "equals": "=",
    "greater_than": ">",
    "less_than": "<",
    "contains": "ILIKE"
}

ALLOWED_AGGREGATIONS = {
    "count": "COUNT",
    "sum": "SUM",
    "avg": "AVG"
}


def build_secure_query(blueprint: Dict[str, Any], tenant_id: str) -> Tuple[str, List[Any]]:
    primary_table = blueprint.get("target_table")
    if primary_table not in ALLOWED_SCHEMA:
        raise ValueError(f"Unauthorized or invalid target table: '{primary_table}'")

    tables_to_join = set()

    def resolve_table_context(field_string: str) -> str:
        if "." in field_string:
            parts = field_string.split(".")
            tbl, col = parts[0], parts[1]
            if tbl in ALLOWED_SCHEMA and col in ALLOWED_SCHEMA[tbl]:
                if tbl != primary_table:
                    tables_to_join.add(tbl)
                return f"{tbl}.{col}"
        if field_string in ALLOWED_SCHEMA[primary_table]:
            return f"{primary_table}.{field_string}"
        return ""

    aggregation_config = blueprint.get("aggregation") or {}
    agg_type = aggregation_config.get("type", "").lower() if aggregation_config.get("type") else ""
    agg_column = aggregation_config.get("column", "") if aggregation_config.get("column") else ""

    if agg_type in ALLOWED_AGGREGATIONS:
        sql_func = ALLOWED_AGGREGATIONS[agg_type]
        if agg_type == "count" and agg_column == "*":
            select_clause = "COUNT(*)"
        else:
            resolved_agg_col = resolve_table_context(agg_column)
            if not resolved_agg_col:
                raise ValueError(f"Invalid column '{agg_column}' provided for aggregation '{agg_type}'.")
            select_clause = f"{sql_func}({resolved_agg_col}) AS {agg_type}_{agg_column.replace('.', '_')}"
    else:
        projection_input = blueprint.get("projection_columns", [])
        safe_projections = [resolve_table_context(item) for item in projection_input if resolve_table_context(item)]
        select_clause = ", ".join(safe_projections) if safe_projections else f"{primary_table}.*"

    filter_clauses = []
    params = []

    for filter_item in blueprint.get("filters", []):
        raw_field = filter_item.get("column")
        operator_key = filter_item.get("operator")
        value = filter_item.get("value")

        resolved_col = resolve_table_context(raw_field)
        if not resolved_col or operator_key not in ALLOWED_OPERATORS:
            continue

        sql_op = ALLOWED_OPERATORS[operator_key]

        if operator_key == "contains":
            filter_clauses.append(f"AND {resolved_col} {sql_op} %s")
            params.append(f"%{value}%")
        else:
            filter_clauses.append(f"AND {resolved_col} {sql_op} %s")
            params.append(value)

    join_clauses = []
    for secondary_table in tables_to_join:
        relation_key = (primary_table, secondary_table)
        if relation_key in RELATIONSHIP_GRAPH:
            join_clauses.append(f"INNER JOIN {secondary_table} ON {RELATIONSHIP_GRAPH[relation_key]}")
        else:
            raise ValueError(f"No safe relational link established between '{primary_table}' and '{secondary_table}'.")

    from_segment = f"FROM {primary_table} " + " ".join(join_clauses)

    sql = f"SELECT {select_clause} {from_segment.strip()} WHERE {primary_table}.tenant_id = %s " + " ".join(filter_clauses)
    params.insert(0, tenant_id)

    for secondary_table in tables_to_join:
        sql += f" AND {secondary_table}.tenant_id = %s"
        params.append(tenant_id)

    if not agg_type:
        sorting = blueprint.get("sorting") or {}
        sort_column = sorting.get("column", "") if sorting.get("column") else ""
        resolved_sort_col = resolve_table_context(sort_column) if sort_column else ""
        direction = sorting.get("direction", "asc").lower() if sorting.get("direction") else "asc"

        if resolved_sort_col and direction in {"asc", "desc"}:
            sql += f" ORDER BY {resolved_sort_col} {direction.upper()}"

        pagination = blueprint.get("pagination") or {}
        try:
            limit = min(int(pagination.get("limit", 20)), 100)
            offset = max(int(pagination.get("offset", 0)), 0)
            sql += f" LIMIT {limit} OFFSET {offset}"
        except (ValueError, TypeError):
            sql += " LIMIT 20 OFFSET 0"

    return " ".join(sql.split()) + ";", params