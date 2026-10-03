CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE SCHEMA IF NOT EXISTS commerce;

CREATE TABLE IF NOT EXISTS commerce.users (
    user_id bigint PRIMARY KEY,
    email text NOT NULL UNIQUE,
    country_code char(2) NOT NULL,
    created_at timestamptz NOT NULL,
    marketing_opt_in boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS commerce.products (
    product_id bigint PRIMARY KEY,
    sku text NOT NULL UNIQUE,
    name text NOT NULL,
    category text NOT NULL,
    current_price numeric(12, 2) NOT NULL CHECK (current_price >= 0),
    stock integer NOT NULL CHECK (stock >= 0),
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS commerce.orders (
    order_id bigint PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES commerce.users(user_id),
    status text NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
    ordered_at timestamptz NOT NULL,
    total_amount numeric(12, 2) NOT NULL CHECK (total_amount >= 0),
    shipping_country char(2) NOT NULL
);

CREATE TABLE IF NOT EXISTS commerce.order_items (
    order_id bigint NOT NULL REFERENCES commerce.orders(order_id) ON DELETE CASCADE,
    line_no smallint NOT NULL,
    product_id bigint NOT NULL REFERENCES commerce.products(product_id),
    quantity smallint NOT NULL CHECK (quantity > 0),
    unit_price numeric(12, 2) NOT NULL CHECK (unit_price >= 0),
    PRIMARY KEY (order_id, line_no)
);

CREATE TABLE IF NOT EXISTS commerce.accounts (
    account_id bigint PRIMARY KEY,
    owner_name text NOT NULL,
    balance numeric(14, 2) NOT NULL CHECK (balance >= 0)
);

INSERT INTO commerce.users (user_id, email, country_code, created_at, marketing_opt_in)
SELECT
    g,
    'user' || g || '@example.com',
    (ARRAY['KR', 'US', 'JP', 'DE', 'SG'])[(g % 5) + 1],
    timestamptz '2025-01-01 00:00:00+00' + ((g * 97) % 31536000) * interval '1 second',
    g % 3 = 0
FROM generate_series(1, 10000) AS g
ON CONFLICT DO NOTHING;

INSERT INTO commerce.products (product_id, sku, name, category, current_price, stock, active)
SELECT
    g,
    'SKU-' || lpad(g::text, 5, '0'),
    'Product ' || g,
    (ARRAY['books', 'electronics', 'home', 'sports', 'beauty'])[(g % 5) + 1],
    5 + (g % 5000) / 10.0,
    100 + (g % 900),
    g % 20 <> 0
FROM generate_series(1, 1000) AS g
ON CONFLICT DO NOTHING;

INSERT INTO commerce.orders (order_id, user_id, status, ordered_at, total_amount, shipping_country)
SELECT
    g,
    ((g * 13) % 10000) + 1,
    (ARRAY['pending', 'paid', 'shipped', 'cancelled'])[(g % 4) + 1],
    timestamptz '2026-01-01 00:00:00+00' + ((g * 37) % 15552000) * interval '1 second',
    10 + (g % 20000) / 10.0,
    (ARRAY['KR', 'US', 'JP', 'DE', 'SG'])[(g % 5) + 1]
FROM generate_series(1, 100000) AS g
ON CONFLICT DO NOTHING;

INSERT INTO commerce.order_items (order_id, line_no, product_id, quantity, unit_price)
SELECT
    ((g - 1) / 3) + 1,
    ((g - 1) % 3) + 1,
    ((g * 17) % 1000) + 1,
    (g % 4) + 1,
    5 + (g % 5000) / 10.0
FROM generate_series(1, 300000) AS g
ON CONFLICT DO NOTHING;

INSERT INTO commerce.accounts (account_id, owner_name, balance)
VALUES (1, 'Alice', 1000.00), (2, 'Bob', 1000.00)
ON CONFLICT DO NOTHING;

ANALYZE commerce.users;
ANALYZE commerce.products;
ANALYZE commerce.orders;
ANALYZE commerce.order_items;

