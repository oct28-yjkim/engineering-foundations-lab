-- psql -v ON_ERROR_STOP=1 권장. seed v2 전용 실습 DB에서 실행하세요.
-- 5~7번은 이름이 지정된 실습 인덱스 3개를 생성합니다. 8번 이체는 ROLLBACK합니다.
-- 재실행은 기존 인덱스를 보존하므로 최초 before 결과를 재현하지 않습니다.
SET search_path TO commerce, public;
SET TIME ZONE 'UTC';

-- 1. 모든 상태의 주문 금액: paid/shipped 매출과 구별합니다.
SELECT min(ordered_at) AS first_order, max(ordered_at) AS last_order,
       count(*) AS orders, count(DISTINCT user_id) AS ordering_users,
       sum(total_amount) AS all_status_order_amount
FROM orders;

-- 2. UTC 주문시점 기반의 실습용 매출. 결제시각/환불/세금/통화는 이 모델에 없습니다.
SELECT date_trunc('month', ordered_at)::date AS month, shipping_country,
       count(*) AS orders, count(DISTINCT user_id) AS customers,
       sum(total_amount) AS paid_shipped_order_revenue,
       round(avg(total_amount), 2) AS avg_order_value
FROM orders
WHERE status IN ('paid', 'shipped')
GROUP BY month, shipping_country
ORDER BY month, shipping_country;

-- 3. 인덱스 전에는 10명만: 전체 실행 시 사용자별 full scan이 반복될 수 있습니다.
SELECT u.user_id, u.email,
       recent.order_id, recent.status, recent.ordered_at, recent.total_amount
FROM users AS u
LEFT JOIN LATERAL (
    SELECT o.order_id, o.status, o.ordered_at, o.total_amount
    FROM orders AS o
    WHERE o.user_id = u.user_id
    ORDER BY o.ordered_at DESC, o.order_id DESC
    LIMIT 3
) AS recent ON true
WHERE u.user_id <= 10
ORDER BY u.user_id, recent.ordered_at DESC, recent.order_id DESC;
-- 5번 인덱스 생성 후 u.user_id <= 10을 제거하여 전체로 확대합니다.

-- 4. 상위 3순위: 동률을 포함하여 3행보다 많을 수 있습니다.
WITH monthly_category AS (
    SELECT date_trunc('month', o.ordered_at)::date AS month, p.category,
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
SELECT month, category, revenue, rank FROM ranked
WHERE rank <= 3 ORDER BY month, rank, category;
-- 정확히 최대 3행: row_number() OVER (... ORDER BY revenue DESC, category).

-- 5. before는 이 인덱스가 없는 새 실습 DB에서만 의미가 있습니다.
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT order_id, status, ordered_at, total_amount FROM orders
WHERE user_id = 42 ORDER BY ordered_at DESC, order_id DESC LIMIT 20;

CREATE INDEX IF NOT EXISTS orders_user_ordered_idx
    ON orders (user_id, ordered_at DESC, order_id DESC);
ANALYZE orders;

EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT order_id, status, ordered_at, total_amount FROM orders
WHERE user_id = 42 ORDER BY ordered_at DESC, order_id DESC LIMIT 20;

-- 6. 조건부 인덱스: constant predicate와 정렬 tie-breaker를 일치시킵니다.
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT order_id, user_id, ordered_at, total_amount FROM orders
WHERE status = 'pending' AND ordered_at < timestamptz '2026-04-01 00:00:00+00'
ORDER BY ordered_at, order_id LIMIT 100;

CREATE INDEX IF NOT EXISTS orders_pending_ordered_idx
    ON orders (ordered_at, order_id) WHERE status = 'pending';
ANALYZE orders;

EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT order_id, user_id, ordered_at, total_amount FROM orders
WHERE status = 'pending' AND ordered_at < timestamptz '2026-04-01 00:00:00+00'
ORDER BY ordered_at, order_id LIMIT 100;

-- 7. 비교 후보: 두 인덱스가 공존하면 planner가 어느 것을 선택했는지 확인하세요.
CREATE INDEX IF NOT EXISTS orders_user_ordered_cover_idx
    ON orders (user_id, ordered_at DESC, order_id DESC) INCLUDE (status, total_amount);
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT order_id, status, ordered_at, total_amount FROM orders
WHERE user_id = 42 ORDER BY ordered_at DESC, order_id DESC LIMIT 20;
-- Index Only Scan도 all-visible bit가 꺼진 페이지에서는 heap 확인이 필요합니다.
-- VACUUM은 별도 운영 실습에서 실행합니다. IF NOT EXISTS는 인덱스 정의까지 검증하지 않습니다.

-- 8. 계좌 존재/잔액 검증 + 일정한 잠금 순서. 실습 결과는 rollback합니다.
BEGIN;
SELECT account_id, balance FROM accounts
WHERE account_id IN (1, 2) ORDER BY account_id FOR UPDATE;
DO $$
BEGIN
    IF (SELECT count(*) FROM accounts WHERE account_id IN (1, 2)) <> 2 THEN
        RAISE EXCEPTION 'both accounts must exist';
    END IF;
    IF (SELECT balance FROM accounts WHERE account_id = 1) < 100 THEN
        RAISE EXCEPTION 'insufficient funds';
    END IF;
END $$;
UPDATE accounts SET balance = balance - 100 WHERE account_id = 1;
UPDATE accounts SET balance = balance + 100 WHERE account_id = 2;
SELECT account_id, balance FROM accounts WHERE account_id IN (1, 2) ORDER BY account_id;
SELECT sum(balance) AS combined_balance FROM accounts WHERE account_id IN (1, 2);
ROLLBACK;
-- 영속 이체 실습은 별도 세션에서 COMMIT을 명시적으로 선택합니다.

-- 9. 관측 쿼리만 실행합니다. blocker 생성/해제는 별도 세션에서 수행합니다.
SELECT blocked.pid AS blocked_pid, blocked.wait_event_type, blocked.wait_event,
       blocker_pid, blocker.state AS blocker_state,
       blocker.query AS blocker_query, blocked.query AS blocked_query
FROM pg_stat_activity AS blocked
CROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS b(blocker_pid)
JOIN pg_stat_activity AS blocker ON blocker.pid = b.blocker_pid
WHERE blocked.datname = current_database();

-- 10-a. live/dead tuple은 추정치이며 정확한 count나 물리 bloat 비율이 아닙니다.
SELECT schemaname, relname, n_live_tup, n_dead_tup, last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables WHERE schemaname = 'commerce' ORDER BY n_dead_tup DESC;

-- 10-b. query 시간과 transaction 수명은 다릅니다.
SELECT pid, usename, state, now() - xact_start AS transaction_age,
       wait_event_type, wait_event, left(query, 160) AS query
FROM pg_stat_activity
WHERE datname = current_database() AND xact_start IS NOT NULL AND pid <> pg_backend_pid()
ORDER BY xact_start;

-- 10-c. compose의 shared_preload_libraries=pg_stat_statements가 필요합니다.
SELECT calls, round(total_exec_time::numeric, 2) AS total_ms,
       round(mean_exec_time::numeric, 2) AS mean_ms, rows, left(query, 160) AS query
FROM pg_stat_statements WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY total_exec_time DESC LIMIT 10;

-- 10-d. 사용량 0은 삭제 근거가 아닙니다. PK/UNIQUE/replica identity와 reset 시점을 확인합니다.
SELECT s.schemaname, s.relname, s.indexrelname, s.idx_scan,
       i.indisprimary, i.indisunique, i.indisreplident,
       pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size
FROM pg_stat_user_indexes AS s JOIN pg_index AS i ON i.indexrelid = s.indexrelid
WHERE s.schemaname = 'commerce' AND s.idx_scan = 0
ORDER BY pg_relation_size(s.indexrelid) DESC;
