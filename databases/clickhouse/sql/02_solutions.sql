-- ClickHouse 26.8 / seed v2. 9번은 lab.daily_metrics_v2/MV를 생성합니다.
-- 9번 backfill은 writer가 멈춘 단독 실습 DB에서만 실행하세요.
-- 모든 SQL을 자동 실행하기 전 해당 절의 전제를 확인하세요. 자동 DROP/초기화는 없습니다.

-- 1. exact와 approximate를 같은 population에서 비교합니다.
SELECT min(event_time) AS first_event, max(event_time) AS last_event,
       count() AS events, uniqExact(user_id) AS exact_users,
       uniqExact(session_id) AS exact_sessions, uniq(user_id) AS approx_users,
       uniqCombined64(user_id) AS approx_combined_users,
       abs(toFloat64(approx_users) - exact_users) / nullIf(exact_users, 0) AS relative_error
FROM lab.events;
-- 이 한 번의 오차가 모든 cardinality/distribution의 오차 상한을 증명하지 않습니다.

-- 2. date spine은 event가 하나도 없는 날도 출력합니다.
WITH daily AS (
    SELECT event_date, uniqExact(user_id) AS dau, uniqExact(session_id) AS sessions,
           countIf(event_type = 'purchase') AS purchases,
           sumIf(toDecimal128(revenue, 2), event_type = 'purchase') AS purchase_revenue
    FROM lab.events GROUP BY event_date
), calendar AS (
    SELECT toDate('2026-01-01') + toIntervalDay(number) AS event_date FROM numbers(180)
)
SELECT c.event_date, ifNull(d.dau, 0) AS dau, ifNull(d.sessions, 0) AS sessions,
       ifNull(d.purchases, 0) AS purchases,
       ifNull(d.purchase_revenue, toDecimal128(0, 2)) AS purchase_revenue
FROM calendar AS c LEFT JOIN daily AS d ON c.event_date = d.event_date
ORDER BY c.event_date;

-- 3-a. 기간 내 사용자 도달률: 순서/세션/시간 제한을 확인하지 않는 지표입니다.
SELECT country, uniqExactIf(user_id, event_type = 'page_view') AS viewers,
       uniqExactIf(user_id, event_type = 'add_to_cart') AS cart_users,
       uniqExactIf(user_id, event_type = 'purchase') AS buyers,
       round(100.0 * buyers / nullIf(viewers, 0), 2) AS buyer_to_viewer_user_pct
FROM lab.events GROUP BY country ORDER BY country;

-- 3-b. 국가·사용자·세션 내 30분 순서 퍼널. 중간 search 등은 허용합니다.
-- strict_order를 추가하면 중간 search 때문에 다른 결과가 됩니다.
WITH sessions AS (
    SELECT country, user_id, session_id,
           windowFunnel(1800, 'strict_increase')(
               event_time, event_type = 'page_view',
               event_type = 'add_to_cart', event_type = 'purchase') AS level
    FROM lab.events GROUP BY country, user_id, session_id
)
SELECT country, countIf(level >= 1) AS viewed_sessions,
       countIf(level >= 2) AS cart_sessions, countIf(level = 3) AS purchased_sessions,
       round(100.0 * purchased_sessions / nullIf(viewed_sessions, 0), 2) AS session_conversion_pct
FROM sessions GROUP BY country ORDER BY country;

-- 4. time 동률을 event_id로 결정하고 같은 row의 값들을 묶습니다.
SELECT user_id,
       argMax(tuple(event_type, event_time), tuple(event_time, event_id)) AS latest_event
FROM lab.events GROUP BY user_id ORDER BY user_id LIMIT 100;

-- 5. 상위 2순위는 동률을 포함합니다.
WITH monthly AS (
    SELECT toStartOfMonth(event_time) AS month, country,
           sum(toDecimal128(revenue, 2)) AS purchase_revenue
    FROM lab.events WHERE event_type = 'purchase' GROUP BY month, country
)
SELECT month, country, purchase_revenue, rank
FROM (
    SELECT *, dense_rank() OVER (PARTITION BY month ORDER BY purchase_revenue DESC) AS rank
    FROM monthly
)
WHERE rank <= 2 ORDER BY month, rank, country;
-- 최대 2행만 필요하면 row_number() OVER (... ORDER BY purchase_revenue DESC, country).

-- 6. partition vs primary index가 제거한 parts/granules를 각각 기록합니다.
EXPLAIN indexes = 1
SELECT count() FROM lab.events
WHERE event_type = 'purchase' AND event_time >= toDateTime('2026-02-01', 'UTC')
  AND event_time < toDateTime('2026-03-01', 'UTC');

EXPLAIN indexes = 1
SELECT count() FROM lab.events
WHERE device = 'mobile' AND event_time >= toDateTime('2026-02-01', 'UTC')
  AND event_time < toDateTime('2026-03-01', 'UTC');
-- 실제 read_rows와 elapsed는 각 SELECT를 별도로 실행하고 query_log에서 확인합니다.

-- 7. 누락 key와 빈 문자열을 구분합니다.
SELECT mapContains(properties, 'campaign') AS has_campaign,
       properties['campaign'] AS campaign, count() AS events,
       sumIf(toDecimal128(revenue, 2), event_type = 'purchase') AS purchase_revenue
FROM lab.events GROUP BY has_campaign, campaign ORDER BY events DESC;

-- 8. 최초 관측 활동 cohort, UTC 월요일. 미관측 기간을 이탈 0으로 채우지 않습니다.
WITH activity AS (
    SELECT DISTINCT user_id, toMonday(event_date) AS activity_week FROM lab.events
), cohorts AS (
    SELECT user_id, min(activity_week) AS cohort_week FROM activity GROUP BY user_id
)
SELECT cohort_week, dateDiff('week', cohort_week, activity_week) AS week_number,
       uniqExact(user_id) AS active_users
FROM activity INNER JOIN cohorts USING (user_id)
GROUP BY cohort_week, week_number ORDER BY cohort_week, week_number;

-- 9. OFFLINE 전용 incremental MV / 재실행 가능한 정상 완료 경로.
-- 전제: 이 전체 절 동안 source와 target에 다른 writer가 없어야 합니다.
-- target 일부만 채워진 실패 상태를 자동 복구하지 않습니다. 검증 실패 시 중단/조사합니다.
-- 기존 v1 target과 이름을 분리합니다. live ingest에서 NOT EXISTS는 중복 방지가 아닙니다.
CREATE TABLE IF NOT EXISTS lab.daily_metrics_v2
(
    event_date Date,
    country LowCardinality(String),
    device LowCardinality(String),
    event_count AggregateFunction(count),
    users AggregateFunction(uniqExact, UInt32),
    purchases AggregateFunction(sum, UInt64),
    revenue AggregateFunction(sum, Decimal(38, 2))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, country, device);

-- 합계가 0 또는 source 전체와 같은 경우만 진행합니다. 검증은 원자적 lock이 아닙니다.
SELECT throwIf(
    countMerge(event_count) != 0 AND countMerge(event_count) != (SELECT count() FROM lab.events),
    'nonempty partial/stale rollup; stop and inspect before backfill')
FROM lab.daily_metrics_v2;

CREATE MATERIALIZED VIEW IF NOT EXISTS lab.daily_metrics_v2_mv TO lab.daily_metrics_v2 AS
SELECT event_date, country, device,
       countState() AS event_count, uniqExactState(user_id) AS users,
       sumState(toUInt64(event_type = 'purchase')) AS purchases,
       sumState(toDecimal128(revenue, 2)) AS revenue
FROM lab.events GROUP BY event_date, country, device;

-- MV는 과거 rows를 읽지 않습니다. 비어 있는 target에만 오프라인 backfill합니다.
-- 모든 aggregate input/state type을 명시합니다. Decimal 금액을 Float로 변환하지 않습니다.
INSERT INTO lab.daily_metrics_v2
SELECT event_date, country, device,
       countState() AS event_count, uniqExactState(user_id) AS users,
       sumState(toUInt64(event_type = 'purchase')) AS purchases,
       sumState(toDecimal128(revenue, 2)) AS revenue
FROM lab.events
WHERE NOT EXISTS (SELECT 1 FROM lab.daily_metrics_v2 LIMIT 1)
GROUP BY event_date, country, device;

-- merge 완료 여부와 무관하게 *Merge + GROUP BY로 읽어야 합니다.
SELECT event_date, country, device, countMerge(event_count) AS events,
       uniqExactMerge(users) AS exact_users, sumMerge(purchases) AS purchases,
       sumMerge(revenue) AS purchase_revenue
FROM lab.daily_metrics_v2 GROUP BY event_date, country, device
ORDER BY event_date, country, device LIMIT 100;

-- 모든 dimension group의 raw vs rollup 정합성. throwIf=0이면 통과.
WITH raw AS (
    SELECT event_date, country, device, count() AS events, uniqExact(user_id) AS users,
           countIf(event_type = 'purchase') AS purchases,
           sum(toDecimal128(revenue, 2)) AS revenue
    FROM lab.events GROUP BY event_date, country, device
), rollup AS (
    SELECT event_date, country, device, countMerge(event_count) AS events,
           uniqExactMerge(users) AS users, sumMerge(purchases) AS purchases, sumMerge(revenue) AS revenue
    FROM lab.daily_metrics_v2 GROUP BY event_date, country, device
)
SELECT throwIf(countIf(ifNull(r.events, 0) != ifNull(a.events, 0)
        OR ifNull(r.users, 0) != ifNull(a.users, 0)
        OR ifNull(r.purchases, 0) != ifNull(a.purchases, 0)
        OR ifNull(r.revenue, toDecimal128(0, 2)) != ifNull(a.revenue, toDecimal128(0, 2))) != 0,
    'rollup differs from raw data; inspect missing/duplicated groups')
FROM raw AS r FULL OUTER JOIN rollup AS a
ON r.event_date = a.event_date AND r.country = a.country AND r.device = a.device
SETTINGS join_use_nulls = 1;

-- 10-a. physical active parts. merge 시 개수는 변하지만 logical count는 보존됩니다.
SELECT table, count() AS active_parts, sum(rows) AS physical_rows,
       formatReadableSize(sum(bytes_on_disk)) AS disk
FROM system.parts WHERE database = 'lab' AND active GROUP BY table ORDER BY table;

-- 10-b. 최근 하루 완료 SELECT 중 메모리 상위. log flush 전에는 빠질 수 있습니다.
SELECT event_time, query_id, query_duration_ms, read_rows, read_bytes,
       formatReadableSize(memory_usage) AS memory, query
FROM system.query_log
WHERE type = 'QueryFinish' AND query_kind = 'Select'
  AND event_time >= now() - INTERVAL 1 DAY
  AND has(databases, 'lab') AND query NOT LIKE '%system.query_log%'
ORDER BY memory_usage DESC LIMIT 5;

-- 10-c. 비어 있는 결과는 현재 진행 중인 mutation이 없다는 의미입니다.
SELECT database, table, mutation_id, command, parts_to_do, latest_fail_reason
FROM system.mutations WHERE database = 'lab' AND NOT is_done;
