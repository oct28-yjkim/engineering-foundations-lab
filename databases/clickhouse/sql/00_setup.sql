-- ClickHouse 26.8 / seed v2. 동시 writer가 없는 새 실습 database에서 실행합니다.
-- 기존 데이터가 있으면 INSERT를 건너뛰고 불변식을 검증합니다. 데이터 자동 삭제 없음.
-- ClickHouse 다중 문장은 전체가 하나의 transaction이 아닙니다.
CREATE DATABASE IF NOT EXISTS lab;
CREATE TABLE IF NOT EXISTS lab.events
(
    event_id UInt64,
    event_time DateTime('UTC'),
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

-- 100000 sessions × 5 events = 500000 rows, 50000 users × 2 sessions.
-- 동일 session은 user/country/device가 일정하고 60초 간격으로 발생합니다.
-- salt별 cityHash64로 상태/기기/국가의 우연한 modulo 상관을 줄입니다.
-- 균등 합성 데이터입니다. production skew/hot key/지연 이벤트는 별도 실험에서 만듭니다.
INSERT INTO lab.events
    (event_id, event_time, user_id, session_id, event_type,
     country, device, revenue, duration_ms, properties)
WITH
    intDiv(number, 5) AS session_no,
    number % 5 AS step,
    toUInt32((session_no * 13) % 50000 + 1) AS uid,
    cityHash64(concat(toString(session_no), ':stage')) % 100 AS stage,
    multiIf(step = 0, 'page_view',
            step = 1, 'search',
            step = 2 AND stage < 55, 'add_to_cart',
            step = 3 AND stage < 55, 'add_to_cart',
            step = 4 AND stage < 20, 'purchase',
            'page_view') AS event_kind,
    100 + cityHash64(concat(toString(session_no), ':amount')) % 20000 AS cents
SELECT
    number + 1,
    toDateTime('2026-01-01 00:00:00', 'UTC')
        + toIntervalSecond(
            (cityHash64(concat(toString(session_no), ':day')) % 180) * 86400
            + cityHash64(concat(toString(session_no), ':second')) % 85200 + step * 60),
    uid,
    concat('session-', toString(session_no)),
    event_kind,
    arrayElement(['KR', 'US', 'JP', 'DE', 'SG'],
        cityHash64(concat(toString(uid), ':country')) % 5 + 1),
    arrayElement(['mobile', 'desktop', 'tablet'],
        cityHash64(concat(toString(session_no), ':device')) % 3 + 1),
    if(event_kind = 'purchase',
        toDecimal64(cents, 2) / toDecimal64(100, 0), toDecimal64(0, 2)),
    toUInt32(50 + cityHash64(concat(toString(number), ':duration')) % 5000),
    map('campaign', arrayElement(['organic', 'search', 'social', 'email'],
            cityHash64(concat(toString(session_no), ':campaign')) % 4 + 1),
        'app_version', concat('1.', toString(cityHash64(concat(toString(session_no), ':version')) % 8)))
FROM numbers(500000)
WHERE NOT EXISTS (SELECT 1 FROM lab.events LIMIT 1);

-- throwIf 출력 0은 통과입니다. 이전 seed/부분 적재/변경된 데이터는 조사해야 합니다.
SELECT throwIf(count() != 500000 OR uniqExact(event_id) != 500000
    OR uniqExact(user_id) != 50000 OR uniqExact(session_id) != 100000
    OR uniqExact(event_date) != 180
    OR min(event_date) != toDate('2026-01-01') OR max(event_date) != toDate('2026-06-29')
    OR countIf(event_type != 'purchase' AND revenue != 0) != 0,
    'seed v2 invariant failed; use a new lab database/volume or investigate existing data')
FROM lab.events;

SELECT throwIf(count() != 0, 'seed v2 session invariant failed; existing rows were NOT reset')
FROM (
    SELECT session_id
    FROM lab.events
    GROUP BY session_id
    HAVING count() != 5 OR uniqExact(user_id) != 1 OR uniqExact(country) != 1
       OR uniqExact(device) != 1 OR uniqExact(event_time) != 5
       OR max(event_time) - min(event_time) != 240
);
