import pytest

from app.compiler.sql_builder import build_secure_query


def test_successful_sql_generation():
    mock_blueprint = {
        "target_table": "orders",
        "projection_columns": ["id", "total_amount"],
        "filters": [{"column": "order_status", "operator": "equals", "value": "completed"}],
        "sorting": {"column": "total_amount", "direction": "desc"},
        "pagination": {"limit": 5},
    }

    sql, params = build_secure_query(mock_blueprint, tenant_id="tenant_alpha")

    assert "SELECT orders.id, orders.total_amount FROM orders" in sql
    assert "WHERE orders.tenant_id = %s" in sql
    assert "AND orders.order_status = %s" in sql
    assert "ORDER BY orders.total_amount DESC LIMIT 5" in sql
    assert params[0] == "tenant_alpha"
    assert params[1] == "completed"


def test_sql_injection_and_whitelist_defense():
    malicious_blueprint = {
        "target_table": "users; DROP TABLE customers; --",
        "projection_columns": ["password"],
    }

    with pytest.raises(ValueError) as excinfo:
        build_secure_query(malicious_blueprint, tenant_id="tenant_alpha")

    assert "Unauthorized or invalid target table" in str(excinfo.value)


def test_wildcard_fallback_on_empty_projections():
    minimal_blueprint = {"target_table": "products", "projection_columns": []}

    sql, _ = build_secure_query(minimal_blueprint, tenant_id="tenant_alpha")
    assert "SELECT products.* FROM products" in sql
    assert "WHERE products.tenant_id = %s" in sql


def test_multiple_filters_compilation():
    blueprint = {
        "target_table": "customers",
        "projection_columns": ["name", "email"],
        "filters": [
            {"column": "country", "operator": "equals", "value": "Germany"},
            {"column": "status", "operator": "equals", "value": "active"},
        ],
        "pagination": {"limit": 10},
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "AND customers.country = %s" in sql
    assert "AND customers.status = %s" in sql
    assert params[0] == "tenant_alpha"
    assert params[1] == "Germany"
    assert params[2] == "active"


def test_contains_operator_uses_ilike():
    blueprint = {
        "target_table": "customers",
        "filters": [{"column": "name", "operator": "contains", "value": "john"}],
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "ILIKE %s" in sql
    assert params[0] == "tenant_alpha"
    assert params[1] == "%john%"


def test_invalid_column_ignored():
    blueprint = {
        "target_table": "orders",
        "filters": [{"column": "nonexistent_column", "operator": "equals", "value": "test"}],
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "nonexistent_column" not in sql
    assert params[0] == "tenant_alpha"


def test_limit_capped_at_100():
    blueprint = {"target_table": "orders", "pagination": {"limit": 500}}

    sql, _ = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "LIMIT 100" in sql


def test_asc_sorting():
    blueprint = {"target_table": "products", "sorting": {"column": "price", "direction": "asc"}}

    sql, _ = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "ORDER BY products.price ASC" in sql


def test_cross_table_join():
    blueprint = {
        "target_table": "orders",
        "projection_columns": ["id", "total_amount"],
        "filters": [{"column": "customers.country", "operator": "equals", "value": "Germany"}],
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "INNER JOIN customers ON orders.customer_id = customers.id" in sql
    assert "AND customers.country = %s" in sql
    assert "AND customers.tenant_id = %s" in sql
    assert params[0] == "tenant_alpha"


def test_cross_table_projection():
    blueprint = {
        "target_table": "orders",
        "projection_columns": ["id", "customers.country"],
        "pagination": {"limit": 5},
    }

    sql, _ = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "orders.id" in sql
    assert "customers.country" in sql
    assert "INNER JOIN customers ON orders.customer_id = customers.id" in sql


def test_tenant_isolation_injected_for_tenant_beta():
    blueprint = {
        "target_table": "customers",
        "projection_columns": ["name"],
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_beta")

    assert "WHERE customers.tenant_id = %s" in sql
    assert params[0] == "tenant_beta"


def test_cross_table_tenant_isolation_both_tables():
    blueprint = {
        "target_table": "orders",
        "projection_columns": ["id", "customers.country"],
        "filters": [{"column": "customers.country", "operator": "equals", "value": "Germany"}],
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_beta")

    assert "orders.tenant_id = %s" in sql
    assert "customers.tenant_id = %s" in sql
    tenant_params = [p for p in params if p == "tenant_beta"]
    assert len(tenant_params) == 2
