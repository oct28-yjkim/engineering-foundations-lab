-- PostgreSQL 18 / seed v2. psql -v ON_ERROR_STOP=1 로 실행합니다.
-- 기존 데이터를 삭제하거나 덮어쓰지 않습니다. 이전 seed는 마지막 검증에서
-- 실패하므로 별도의 새 실습 volume/database에 v2를 준비하세요.
BEGIN;
SET LOCAL TIME ZONE 'UTC';
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
    line_no smallint NOT NULL CHECK (line_no > 0),
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

-- 서로 다른 salt의 MD5 앞 32 bit를 재현 가능한 합성 분포에만 사용합니다.
-- 암호학/실제 트래픽 모델이 아닙니다. user_id와 status의 modulo 상관을 피합니다.
INSERT INTO commerce.users (user_id, email, country_code, created_at, marketing_opt_in)
SELECT g, 'user' || g || '@example.com',
       (ARRAY['KR', 'US', 'JP', 'DE', 'SG'])[
           (('x' || substr(md5(g::text || ':country'), 1, 8))::bit(32)::bigint % 5)::int + 1],
       timestamptz '2025-01-01 00:00:00+00'
           + (('x' || substr(md5(g::text || ':signup'), 1, 8))::bit(32)::bigint % 31536000)
             * interval '1 second',
       (('x' || substr(md5(g::text || ':marketing'), 1, 8))::bit(32)::bigint % 3) = 0
FROM generate_series(1, 10000) AS g
ON CONFLICT DO NOTHING;

INSERT INTO commerce.products (product_id, sku, name, category, current_price, stock, active)
SELECT g, 'SKU-' || lpad(g::text, 5, '0'), 'Product ' || g,
       (ARRAY['books', 'electronics', 'home', 'sports', 'beauty'])[
           (('x' || substr(md5(g::text || ':category'), 1, 8))::bit(32)::bigint % 5)::int + 1],
       (500 + ('x' || substr(md5(g::text || ':price'), 1, 8))::bit(32)::bigint % 49501) / 100.0,
       100 + (g % 900), g % 20 <> 0
FROM generate_series(1, 1000) AS g
ON CONFLICT DO NOTHING;

-- 아래 price 식은 integer cents → numeric 경로입니다. float를 거치지 않습니다.
-- 주문 시점 가격은 current_price의 80~120%; 이후 catalog 가격 변경과 구별합니다.
CREATE TEMP TABLE lab_seed_lines ON COMMIT DROP AS
SELECT g::bigint AS order_id, line_no::smallint,
       p.product_id,
       (1 + ('x' || substr(md5(g::text || ':' || line_no || ':qty'), 1, 8))::bit(32)::bigint % 4)::smallint AS quantity,
       round(p.current_price *
           (80 + ('x' || substr(md5(g::text || ':' || line_no || ':discount'), 1, 8))::bit(32)::bigint % 41)
           / 100, 2) AS unit_price
FROM generate_series(1, 100000) AS g
CROSS JOIN generate_series(1, 3) AS line_no
JOIN commerce.products AS p ON p.product_id =
    1 + ('x' || substr(md5(g::text || ':' || line_no || ':product'), 1, 8))::bit(32)::bigint % 1000;

INSERT INTO commerce.orders (order_id, user_id, status, ordered_at, total_amount, shipping_country)
SELECT t.order_id, u.user_id,
       (ARRAY['pending', 'paid', 'shipped', 'cancelled'])[
           (('x' || substr(md5(t.order_id::text || ':status'), 1, 8))::bit(32)::bigint % 4)::int + 1],
       timestamptz '2026-01-01 00:00:00+00'
           + (('x' || substr(md5(t.order_id::text || ':order-time'), 1, 8))::bit(32)::bigint % 15552000)
             * interval '1 second',
       t.total_amount, u.country_code
FROM (
    SELECT order_id, sum(quantity * unit_price) AS total_amount
    FROM lab_seed_lines GROUP BY order_id
) AS t
JOIN commerce.users AS u ON u.user_id = (t.order_id * 13) % 10000 + 1
ON CONFLICT DO NOTHING;

INSERT INTO commerce.order_items (order_id, line_no, product_id, quantity, unit_price)
SELECT order_id, line_no, product_id, quantity, unit_price FROM lab_seed_lines
ON CONFLICT DO NOTHING;
INSERT INTO commerce.accounts (account_id, owner_name, balance)
VALUES (1, 'Alice', 1000.00), (2, 'Bob', 1000.00)
ON CONFLICT DO NOTHING;

DO $$
BEGIN
    IF (SELECT count(*) FROM commerce.users) <> 10000
       OR (SELECT count(*) FROM commerce.products) <> 1000
       OR (SELECT count(*) FROM commerce.orders) <> 100000
       OR (SELECT count(*) FROM commerce.order_items) <> 300000
       OR (SELECT count(DISTINCT ordered_at::date) FROM commerce.orders) <> 180
       OR EXISTS (SELECT 1 FROM commerce.orders
                  WHERE ordered_at < timestamptz '2026-01-01 00:00:00+00'
                     OR ordered_at >= timestamptz '2026-06-30 00:00:00+00')
       OR EXISTS (
           SELECT o.order_id FROM commerce.orders AS o
           LEFT JOIN commerce.order_items AS i USING (order_id)
           GROUP BY o.order_id, o.total_amount
           HAVING count(i.line_no) <> 3 OR o.total_amount <> sum(i.quantity * i.unit_price)
       )
    THEN
        RAISE EXCEPTION 'seed v2 invariant failed; existing rows were NOT reset. Use a new lab database/volume or investigate manually.';
    END IF;
END $$;
ANALYZE commerce.users;
ANALYZE commerce.products;
ANALYZE commerce.orders;
ANALYZE commerce.order_items;
COMMIT;
