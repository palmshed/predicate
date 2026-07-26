"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-07-26

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(100), unique=True, nullable=False),
        sa.Column("country", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.Date, server_default=sa.func.current_date()),
        sa.Column("tenant_id", sa.String(50), nullable=False, server_default="tenant_alpha"),
    )
    op.create_index("idx_customers_tenant", "customers", ["tenant_id"])

    # Create orders table
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id", ondelete="CASCADE")),
        sa.Column("total_amount", sa.Float, nullable=False),
        sa.Column("order_status", sa.String(20), server_default="pending"),
        sa.Column("purchase_date", sa.Date, server_default=sa.func.current_date()),
        sa.Column("tenant_id", sa.String(50), nullable=False, server_default="tenant_alpha"),
    )
    op.create_index("idx_orders_tenant", "orders", ["tenant_id"])

    # Create products table
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_name", sa.String(150), nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("stock_count", sa.Integer, nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("tenant_id", sa.String(50), nullable=False, server_default="tenant_alpha"),
    )
    op.create_index("idx_products_tenant", "products", ["tenant_id"])

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("user_prompt", sa.Text, nullable=False),
        sa.Column("compiled_sql", sa.Text, nullable=False),
        sa.Column("execution_parameters", sa.Text, nullable=False),
        sa.Column("cache_hit", sa.Boolean, nullable=False),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_audit_logs_tenant", "audit_logs", ["tenant_id"])
    op.create_index("idx_audit_logs_executed_at", "audit_logs", ["executed_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("products")
    op.drop_table("orders")
    op.drop_table("customers")
