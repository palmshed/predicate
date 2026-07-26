"""seed initial data

Revision ID: 002_seed
Revises: 001_initial
Create Date: 2026-07-26

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_seed'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Seed customers
    op.execute("""
        INSERT INTO customers (name, email, country, status, created_at, tenant_id) VALUES
        ('John Doe', 'john@example.com', 'USA', 'active', '2026-01-15', 'tenant_alpha'),
        ('Alice Schmidt', 'alice@example.de', 'Germany', 'active', '2026-03-22', 'tenant_beta'),
        ('Raj Patel', 'raj@example.in', 'India', 'churned', '2025-11-05', 'tenant_alpha')
    """)

    # Seed orders
    op.execute("""
        INSERT INTO orders (customer_id, total_amount, order_status, purchase_date, tenant_id) VALUES
        (1, 250.50, 'completed', '2026-07-20', 'tenant_alpha'),
        (1, 45.00, 'pending', '2026-07-24', 'tenant_alpha'),
        (2, 520.00, 'completed', '2026-07-18', 'tenant_beta'),
        (3, 12.99, 'refunded', '2026-02-10', 'tenant_alpha')
    """)

    # Seed products
    op.execute("""
        INSERT INTO products (product_name, price, stock_count, category, tenant_id) VALUES
        ('Enterprise AI License', 999.00, 50, 'Software', 'tenant_alpha'),
        ('Developer Keyboard', 149.99, 120, 'Hardware', 'tenant_beta'),
        ('Data Engineering Guidebook', 29.95, 400, 'Books', 'tenant_alpha')
    """)


def downgrade() -> None:
    op.execute("DELETE FROM products")
    op.execute("DELETE FROM orders")
    op.execute("DELETE FROM customers")
