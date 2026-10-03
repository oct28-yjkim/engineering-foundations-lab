SET search_path TO commerce, public;

-- 1. 데이터 프로파일링
SELECT
    min(ordered_at) AS first_order,
    max(ordered_at) AS last_order,
    count(*) AS orders,
    count(DISTINCT user_id) AS purchasing_users,
    sum(total_amount) AS gross_amount
FROM orders;

-- 2. 월별 KPI
SELECT
    date_trunc('month', ordered_at)::date AS month,
    shipping_country,
    count(*) AS orders,
    count(DISTINCT user_id) AS customers,
    sum(total_amount) AS revenue,
    round(avg(total_amount), 2) AS avg_order_value
FROM orders
WHERE status IN ('paid', 'shipped')
GROUP BY month, shipping_country
ORDER BY month, shipping_country;

-- 3. 고객별 최근 주문 3건
SELECT u.user_id, u.email,
       recent.order_id, recent.status, recent.ordered_at, recent.total_amount
FROM users AS u
LEFT JOIN LATERAL (
    SELECT o.order_id, o.status, o.ordered_at, o.total_amount
    FROM orders AS o
    WHERE o.user_id = u.user_id
    ORDER BY o.ordered_at DESC
    LIMIT 3
) AS recent ON true
ORDER BY u.user_id, recent.ordered_at DESC;

-- 4. 월별 카테고리 매출 상위 3개
WITH monthly_category AS (
    SELECT
        date_trunc('month', o.ordered_at)::date AS month,
        p.category,
        sum(oi.quantity * oi.unit_price) AS revenue
    FROM orders AS o
    JOIN order_items AS oi USING (order_id)
    JOIN products AS p USING (product_id)
    WHERE o.status IN ('paid', 'shipped')
    GROUP BY month, p.category
), ranked AS (
    SELECT *, dense_rank() OVER (PARTITION BY month ORDER BY revenue DESC) AS rank
    FROM monthly_category
)
SELECT month, category, revenue, rank
FROM ranked
WHERE rank <= 3
ORDER BY month, rank, category;

-- 5. 복합 인덱스
EXPLAIN (ANALYZE, BUFFERS)
SELECT order_id, status, ordered_at, total_amount
FROM orders
WHERE user_id = 42
ORDER BY ordered_at DESC
LIMIT 20;

CREATE INDEX IF NOT EXISTS orders_user_ordered_idx
    ON orders (user_id, ordered_at DESC);

ANALYZE orders;

EXPLAIN (ANALYZE, BUFFERS)
SELECT order_id, status, ordered_at, total_amount
FROM orders
WHERE user_id = 42
ORDER BY ordered_at DESC
LIMIT 20;

-- 6. pending 주문용 partial index
EXPLAIN (ANALYZE, BUFFERS)
SELECT order_id, user_id, ordered_at, total_amount
FROM orders
WHERE status = 'pending'
  AND ordered_at < timestamptz '2026-04-01 00:00:00+00'
ORDER BY ordered_at
LIMIT 100;

CREATE INDEX IF NOT EXISTS orders_pending_ordered_idx
    ON orders (ordered_at)
    WHERE status = 'pending';

ANALYZE orders;

EXPLAIN (ANALYZE, BUFFERS)
SELECT order_id, user_id, ordered_at, total_amount
FROM orders
WHERE status = 'pending'
  AND ordered_at < timestamptz '2026-04-01 00:00:00+00'
ORDER BY ordered_at
LIMIT 100;

-- 7. covering index 대안
-- 5번의 기존 인덱스와 목적이 겹치므로 실제 환경에서는 둘을 모두 유지하지 말고 비교 후 선택합니다.
CREATE INDEX IF NOT EXISTS orders_user_ordered_cover_idx
    ON orders (user_id, ordered_at DESC)
    INCLUDE (order_id, status, total_amount);

-- Index-only scan은 필요한 열이 index에 있어도 visibility map 상태에 따라 heap 확인이 필요할 수 있습니다.

-- 8. 안전한 이체 예시
BEGIN;

-- 항상 작은 account_id부터 잠급니다.
SELECT account_id, balance
FROM accounts
WHERE account_id IN (1, 2)
ORDER BY account_id
FOR UPDATE;

DO $$
BEGIN
    IF (SELECT balance FROM accounts WHERE account_id = 1) < 100 THEN
        RAISE EXCEPTION 'insufficient funds';
    END IF;
END $$;

UPDATE accounts SET balance = balance - 100 WHERE account_id = 1;
UPDATE accounts SET balance = balance + 100 WHERE account_id = 2;
COMMIT;

-- 9. blocked session과 blocker
SELECT
    blocked.pid AS blocked_pid,
    blocked.wait_event_type,
    blocked.wait_event,
    blocker_pid,
    blocker.state AS blocker_state,
    blocker.query AS blocker_query,
    blocked.query AS blocked_query
FROM pg_stat_activity AS blocked
CROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS b(blocker_pid)
JOIN pg_stat_activity AS blocker ON blocker.pid = b.blocker_pid;

-- 10-a. dead tuples
SELECT schemaname, relname, n_live_tup, n_dead_tup,
       last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;

-- 10-b. 오래된 transaction
SELECT pid, usename, state, now() - xact_start AS transaction_age,
       wait_event_type, wait_event, left(query, 160) AS query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL AND pid <> pg_backend_pid()
ORDER BY xact_start;

-- 10-c. 누적 실행 시간이 큰 쿼리
SELECT calls,
       round(total_exec_time::numeric, 2) AS total_ms,
       round(mean_exec_time::numeric, 2) AS mean_ms,
       rows,
       left(query, 160) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- 10-d. scan이 없었던 user index 후보
-- 통계 reset 이후 충분한 대표 기간을 관찰한 뒤 판단해야 합니다.
SELECT schemaname, relname, indexrelname, idx_scan,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

