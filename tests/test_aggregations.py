import pytest
from app.compiler.sql_builder import build_secure_query


def test_sum_aggregation_compilation():
    blueprint = {
        "target_table": "orders",
        "aggregation": {
            "type": "sum",
            "column": "total_amount"
        },
        "filters": [
            {"column": "order_status", "operator": "equals", "value": "completed"}
        ]
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "SELECT SUM(orders.total_amount) AS sum_total_amount FROM orders" in sql
    assert "WHERE orders.tenant_id = %s AND orders.order_status = %s" in sql
    assert "LIMIT" not in sql
    assert params == ["tenant_alpha", "completed"]


def test_count_wildcard_aggregation():
    blueprint = {
        "target_table": "customers",
        "aggregation": {
            "type": "count",
            "column": "*"
        },
        "filters": []
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_beta")

    assert "SELECT COUNT(*) FROM customers WHERE customers.tenant_id = %s" in sql
    assert params == ["tenant_beta"]


def test_avg_aggregation_compilation():
    blueprint = {
        "target_table": "products",
        "aggregation": {
            "type": "avg",
            "column": "price"
        },
        "filters": []
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "SELECT AVG(products.price) AS avg_price FROM products" in sql
    assert "WHERE products.tenant_id = %s" in sql
    assert "LIMIT" not in sql
    assert params == ["tenant_alpha"]


def test_invalid_aggregation_column_rejection():
    invalid_blueprint = {
        "target_table": "products",
        "aggregation": {
            "type": "avg",
            "column": "malicious_non_existent_field"
        },
        "filters": []
    }

    with pytest.raises(ValueError) as excinfo:
        build_secure_query(invalid_blueprint, tenant_id="tenant_alpha")

    assert "Invalid column" in str(excinfo.value)


def test_aggregation_with_cross_table_column():
    blueprint = {
        "target_table": "orders",
        "aggregation": {
            "type": "sum",
            "column": "orders.total_amount"
        },
        "filters": []
    }

    sql, params = build_secure_query(blueprint, tenant_id="tenant_alpha")

    assert "SUM(orders.total_amount)" in sql
    assert "WHERE orders.tenant_id = %s" in sql