CREATE DATABASE IF NOT EXISTS lab;

CREATE TABLE IF NOT EXISTS lab.events
(
    event_id UInt64,
    event_time DateTime,
    event_date Date MATERIALIZED toDate(event_time),
    user_id UInt32,
    session_id String,
    event_type LowCardinality(String),
    country LowCardinality(String),
    device LowCardinality(String),
    revenue Decimal(12, 2),
    duration_ms UInt32,
    properties Map(String, String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_type, event_date, user_id, event_time)
SETTINGS index_granularity = 8192;

INSERT INTO lab.events
SELECT
    number + 1 AS event_id,
    toDateTime('2026-01-01 00:00:00')
        + toIntervalSecond((number * 37) % (180 * 24 * 60 * 60)) AS event_time,
    toUInt32((number * 13) % 50000 + 1) AS user_id,
    concat('session-', toString(intDiv(number, 5))) AS session_id,
    arrayElement(
        ['page_view', 'page_view', 'page_view', 'search', 'add_to_cart', 'purchase'],
        toUInt32(number % 6 + 1)
    ) AS event_type,
    arrayElement(['KR', 'US', 'JP', 'DE', 'SG'], toUInt32(number % 5 + 1)) AS country,
    arrayElement(['mobile', 'desktop', 'tablet'], toUInt32(number % 3 + 1)) AS device,
    if(event_type = 'purchase', toDecimal64((number % 20000 + 100) / 100.0, 2), toDecimal64(0, 2)) AS revenue,
    toUInt32(50 + number % 5000) AS duration_ms,
    map(
        'campaign', arrayElement(['organic', 'search', 'social', 'email'], toUInt32(number % 4 + 1)),
        'app_version', concat('1.', toString(number % 8))
    ) AS properties
FROM numbers(500000)
WHERE NOT EXISTS (SELECT 1 FROM lab.events LIMIT 1);

