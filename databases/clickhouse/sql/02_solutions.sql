-- 1. 데이터 프로파일링
SELECT
    min(event_time) AS first_event,
    max(event_time) AS last_event,
    count() AS events,
    uniqExact(user_id) AS users,
    uniqExact(session_id) AS sessions
FROM lab.events;

-- 2. 일별 KPI
SELECT
    event_date,
    uniqExact(user_id) AS dau,
    uniqExact(session_id) AS sessions,
    countIf(event_type = 'purchase') AS purchases,
    sumIf(revenue, event_type = 'purchase') AS revenue
FROM lab.events
GROUP BY event_date
ORDER BY event_date;

-- 3. 전환 퍼널
SELECT
    country,
    uniqExactIf(user_id, event_type = 'page_view') AS viewers,
    uniqExactIf(user_id, event_type = 'add_to_cart') AS cart_users,
    uniqExactIf(user_id, event_type = 'purchase') AS buyers,
    round(100 * buyers / nullIf(viewers, 0), 2) AS view_to_purchase_pct
FROM lab.events
GROUP BY country
ORDER BY view_to_purchase_pct DESC;

-- 4. 사용자별 최근 이벤트
SELECT
    user_id,
    argMax(event_type, event_time) AS latest_event_type,
    max(event_time) AS latest_event_time
FROM lab.events
GROUP BY user_id
ORDER BY user_id
LIMIT 100;

-- 5. 월별 매출 상위 2개 국가
WITH monthly AS
(
    SELECT
        toStartOfMonth(event_time) AS month,
        country,
        sum(revenue) AS revenue
    FROM lab.events
    WHERE event_type = 'purchase'
    GROUP BY month, country
)
SELECT month, country, revenue, rank
FROM
(
    SELECT *, dense_rank() OVER (PARTITION BY month ORDER BY revenue DESC) AS rank
    FROM monthly
)
WHERE rank <= 2
ORDER BY month, rank, country;

-- 6. 정렬 키와 pruning
EXPLAIN indexes = 1
SELECT count()
FROM lab.events
WHERE event_type = 'purchase'
  AND event_time >= '2026-02-01'
  AND event_time < '2026-03-01';

EXPLAIN indexes = 1
SELECT count()
FROM lab.events
WHERE device = 'mobile'
  AND event_time >= '2026-02-01'
  AND event_time < '2026-03-01';

-- event_type은 ORDER BY 선두 열이므로 primary index pruning에 유리합니다.
-- device는 정렬 키에 없어서 같은 기간에도 더 많은 granule을 읽을 수 있습니다.

-- 7. Map 다루기
SELECT
    properties['campaign'] AS campaign,
    count() AS events,
    sumIf(revenue, event_type = 'purchase') AS purchase_revenue
FROM lab.events
GROUP BY campaign
ORDER BY events DESC;

-- 8. 코호트 재방문
WITH activity AS
(
    SELECT DISTINCT user_id, toStartOfWeek(event_date) AS activity_week
    FROM lab.events
),
cohorts AS
(
    SELECT user_id, min(activity_week) AS cohort_week
    FROM activity
    GROUP BY user_id
)
SELECT
    cohort_week,
    dateDiff('week', cohort_week, activity_week) AS week_number,
    uniqExact(user_id) AS active_users
FROM activity
INNER JOIN cohorts USING (user_id)
GROUP BY cohort_week, week_number
ORDER BY cohort_week, week_number;

-- 9. 사전 집계
-- unique users는 일별 부분 결과를 단순 합산하면 중복 사용자가 이중 계산됩니다.
-- AggregateFunction 상태를 저장하고 uniqMerge로 읽습니다.
DROP VIEW IF EXISTS lab.daily_metrics_mv;
DROP TABLE IF EXISTS lab.daily_metrics;

CREATE TABLE IF NOT EXISTS lab.daily_metrics
(
    event_date Date,
    country LowCardinality(String),
    device LowCardinality(String),
    events SimpleAggregateFunction(sum, UInt64),
    users AggregateFunction(uniq, UInt32),
    purchases SimpleAggregateFunction(sum, UInt64),
    revenue SimpleAggregateFunction(sum, Decimal(12, 2))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, country, device);

CREATE MATERIALIZED VIEW IF NOT EXISTS lab.daily_metrics_mv
TO lab.daily_metrics
AS
SELECT
    event_date,
    country,
    device,
    count() AS events,
    uniqState(user_id) AS users,
    countIf(event_type = 'purchase') AS purchases,
    sumIf(revenue, event_type = 'purchase') AS revenue
FROM lab.events
GROUP BY event_date, country, device;

-- view 생성 이전의 기존 데이터는 자동 집계되지 않으므로 명시적으로 backfill합니다.
INSERT INTO lab.daily_metrics
SELECT
    event_date,
    country,
    device,
    count() AS events,
    uniqState(user_id) AS users,
    countIf(event_type = 'purchase') AS purchases,
    sumIf(revenue, event_type = 'purchase') AS revenue
FROM lab.events
GROUP BY event_date, country, device;

SELECT
    event_date,
    country,
    device,
    sum(events) AS events,
    uniqMerge(users) AS users,
    sum(purchases) AS purchases,
    sum(revenue) AS revenue
FROM lab.daily_metrics
GROUP BY event_date, country, device
ORDER BY event_date, country, device
LIMIT 100;

-- 10-a. active parts
SELECT table, count() AS active_parts, sum(rows) AS rows,
       formatReadableSize(sum(bytes_on_disk)) AS disk
FROM system.parts
WHERE database = 'lab' AND active
GROUP BY table
ORDER BY table;

-- 10-b. memory-heavy recent SELECTs
SELECT event_time, query_duration_ms, read_rows,
       formatReadableSize(memory_usage) AS memory, query
FROM system.query_log
WHERE type = 'QueryFinish' AND query_kind = 'Select'
  AND query NOT LIKE '%system.query_log%'
ORDER BY memory_usage DESC
LIMIT 5;

-- 10-c. unfinished mutations
SELECT database, table, mutation_id, command, parts_to_do, latest_fail_reason
FROM system.mutations
WHERE database = 'lab' AND NOT is_done;
