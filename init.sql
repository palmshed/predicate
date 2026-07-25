CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    country VARCHAR(50) NOT NULL,
    status VARCHAR(20) CHECK (status IN ('active', 'churned')) DEFAULT 'active',
    created_at DATE DEFAULT CURRENT_DATE,
    tenant_id VARCHAR(50) NOT NULL DEFAULT 'tenant_alpha'
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id) ON DELETE CASCADE,
    total_amount FLOAT NOT NULL,
    order_status VARCHAR(20) CHECK (order_status IN ('completed', 'pending', 'refunded')) DEFAULT 'pending',
    purchase_date DATE DEFAULT CURRENT_DATE,
    tenant_id VARCHAR(50) NOT NULL DEFAULT 'tenant_alpha'
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    price FLOAT NOT NULL,
    stock_count INT NOT NULL,
    category VARCHAR(50) NOT NULL,
    tenant_id VARCHAR(50) NOT NULL DEFAULT 'tenant_alpha'
);

INSERT INTO customers (name, email, country, status, created_at, tenant_id) VALUES
('John Doe', 'john@example.com', 'USA', 'active', '2026-01-15', 'tenant_alpha'),
('Alice Schmidt', 'alice@example.de', 'Germany', 'active', '2026-03-22', 'tenant_beta'),
('Raj Patel', 'raj@example.in', 'India', 'churned', '2025-11-05', 'tenant_alpha');

INSERT INTO orders (customer_id, total_amount, order_status, purchase_date, tenant_id) VALUES
(1, 250.50, 'completed', '2026-07-20', 'tenant_alpha'),
(1, 45.00, 'pending', '2026-07-24', 'tenant_alpha'),
(2, 520.00, 'completed', '2026-07-18', 'tenant_beta'),
(3, 12.99, 'refunded', '2026-02-10', 'tenant_alpha');

INSERT INTO products (product_name, price, stock_count, category, tenant_id) VALUES
('Enterprise AI License', 999.00, 50, 'Software', 'tenant_alpha'),
('Developer Keyboard', 149.99, 120, 'Hardware', 'tenant_beta'),
('Data Engineering Guidebook', 29.95, 400, 'Books', 'tenant_alpha');

CREATE INDEX IF NOT EXISTS idx_customers_tenant ON customers(tenant_id);
CREATE INDEX IF NOT EXISTS idx_orders_tenant ON orders(tenant_id);
CREATE INDEX IF NOT EXISTS idx_products_tenant ON products(tenant_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    user_prompt TEXT NOT NULL,
    compiled_sql TEXT NOT NULL,
    execution_parameters TEXT NOT NULL,
    cache_hit BOOLEAN NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_executed_at ON audit_logs(executed_at);