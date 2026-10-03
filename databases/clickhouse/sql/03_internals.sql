-- ClickHouse 26.8 읽기 전용 관측 묶음. 기본 single-node seed v2를 사용합니다.
-- ALTER/OPTIMIZE/SYSTEM FLUSH LOGS/통계 reset/설정 변경을 실행하지 않습니다.
-- SELECT/EXPLAIN도 CPU/IO를 소비하고 query_log에 남습니다. 관측 비용을 기록하세요.

-- I-00. 실행 환경. 같은 결과를 다른 version/settings에서 일반화하지 않습니다.
SELECT version(), timezone(), currentDatabase();
SELECT name, value, changed, readonly FROM system.settings
WHERE name IN ('max_threads', 'max_memory_usage', 'max_bytes_before_external_group_by',
    'max_bytes_before_external_sort', 'join_algorithm', 'use_query_cache',
    'use_query_condition_cache', 'optimize_move_to_prewhere', 'log_queries',
    'log_query_threads', 'log_profile_events') ORDER BY name;
SHOW CREATE TABLE lab.events;

-- I-01. seed 불변식: 500000/500000/50000/100000/180, 시작 Jan1, 끝 Jun29.
SELECT count() AS rows, uniqExact(event_id) AS event_ids, uniqExact(user_id) AS users,
       uniqExact(session_id) AS sessions, uniqExact(event_date) AS utc_days,
       min(event_time), max(event_time),
       countIf(event_type != 'purchase' AND revenue != 0) AS invalid_revenue_rows
FROM lab.events;
SELECT count() AS invalid_sessions FROM (
    SELECT session_id FROM lab.events GROUP BY session_id
    HAVING count() != 5 OR uniqExact(user_id) != 1 OR uniqExact(country) != 1
       OR uniqExact(device) != 1 OR uniqExact(event_time) != 5
       OR max(event_time) - min(event_time) != 240
); -- 0
SELECT event_type, device, count() AS events FROM lab.events
GROUP BY event_type, device ORDER BY event_type, device;
-- 각 event type이 모든 device에 분포해야 합니다. 합성 분포는 실제 운영 통계가 아닙니다.

-- I-02. part / partition / mark / granule. 8192는 항상 실제 행 수인 상수가 아닙니다.
SELECT name, partition, part_type, rows, marks, level, bytes_on_disk,
       data_compressed_bytes, data_uncompressed_bytes, primary_key_bytes_in_memory,
       round(rows / nullIf(marks, 0), 1) AS average_rows_per_mark
FROM system.parts WHERE database = 'lab' AND table = 'events' AND active
ORDER BY partition, name;
-- adaptive granularity, 마지막 granule, part type에 따라 rows/marks가 달라집니다.
SELECT partition, count() AS active_parts, sum(rows) AS rows, sum(marks) AS marks,
       formatReadableSize(sum(bytes_on_disk)) AS disk
FROM system.parts WHERE database = 'lab' AND table = 'events' AND active
GROUP BY partition ORDER BY partition;

-- I-03. 열별 압축/정렬 키. 압축률을 codec 하나의 효과로 단정하지 마세요.
SELECT name, type, is_in_partition_key, is_in_sorting_key, is_in_primary_key,
       data_compressed_bytes, data_uncompressed_bytes,
       round(data_uncompressed_bytes / nullIf(data_compressed_bytes, 0), 2) AS compression_ratio,
       compression_codec
FROM system.columns WHERE database = 'lab' AND table = 'events' ORDER BY position;

-- I-04. partition pruning / primary index pruning / PREWHERE를 별도 층으로 읽습니다.
EXPLAIN indexes = 1
SELECT count(), sum(revenue) FROM lab.events
WHERE event_type = 'purchase' AND event_date >= toDate('2026-02-01')
  AND event_date < toDate('2026-03-01');
EXPLAIN indexes = 1
SELECT count(), sum(revenue) FROM lab.events
WHERE device = 'mobile' AND event_date >= toDate('2026-02-01')
  AND event_date < toDate('2026-03-01');
-- 금액까지 읽는 동일 SELECT를 별도로 실행하여 log와 비교합니다.

-- I-05. logical plan과 병렬 processor pipeline은 서로 다른 표현입니다.
EXPLAIN PLAN
SELECT country, uniqExact(user_id), sum(revenue) FROM lab.events
WHERE event_type = 'purchase' GROUP BY country;
EXPLAIN PIPELINE
SELECT country, uniqExact(user_id), sum(revenue) FROM lab.events
WHERE event_type = 'purchase' GROUP BY country;

-- I-06. background merge 관측. 짧은 merge는 수집 사이에 끝날 수 있습니다.
SELECT database, table, elapsed, progress, num_parts, total_size_bytes_compressed,
       rows_read, rows_written, memory_usage
FROM system.merges WHERE database = 'lab';
SELECT database, table, mutation_id, command, create_time, parts_to_do, is_done, latest_fail_reason
FROM system.mutations WHERE database = 'lab' ORDER BY create_time DESC;
-- mutations=0, merges=0은 정상 idle 상태에서도 나옵니다.

-- I-07. query_id로 실제 read_rows/bytes/memory/ProfileEvents 연결.
-- query_log는 비동기로 flush됩니다. 동일 이름 카운터도 버전/설정 의미를 확인하세요.
SELECT event_time, query_id, query_duration_ms, read_rows, read_bytes, result_rows,
       memory_usage, ProfileEvents['SelectedParts'] AS selected_parts,
       ProfileEvents['SelectedMarks'] AS selected_marks,
       ProfileEvents['UserTimeMicroseconds'] AS cpu_user_us,
       ProfileEvents['SystemTimeMicroseconds'] AS cpu_system_us,
       ProfileEvents['OSReadBytes'] AS os_read_bytes,
       left(query, 180) AS query
FROM system.query_log
WHERE type = 'QueryFinish' AND event_time >= now() - INTERVAL 1 DAY
  AND has(databases, 'lab') AND query NOT LIKE '%system.query_log%'
ORDER BY event_time DESC LIMIT 20;
-- CPU 합계/벽시계 비율, selected marks/read rows, disk/cache를 구분합니다.
-- log 자체 미구성/권한 부족은 이 SELECT의 실패 원인이므로 환경 상태와 함께 기록합니다.

-- I-08. 프로세스/메모리/누적 event. 관측 시점과 단위를 함께 저장하세요.
SELECT query_id, elapsed, read_rows, read_bytes, memory_usage, left(query, 180) AS query
FROM system.processes WHERE query NOT LIKE '%system.processes%' ORDER BY elapsed DESC;
SELECT metric, value, description FROM system.metrics
WHERE metric IN ('MemoryTracking', 'Query', 'Merge', 'BackgroundMergesAndMutationsPoolTask');
SELECT event, value, description FROM system.events
WHERE event IN ('SelectedRows', 'SelectedBytes', 'SelectedMarks', 'InsertedRows',
    'MergedRows', 'Query', 'OSReadBytes', 'OSWriteBytes') ORDER BY event;

-- I-09. exact/approx 및 Decimal/state type을 직접 확인합니다.
SELECT uniqExact(user_id) AS exact_users, uniq(user_id) AS approx_users,
       uniqCombined64(user_id) AS approx_combined_users,
       toTypeName(sum(toDecimal128(revenue, 2))) AS decimal_sum_type,
       toTypeName(sumState(toDecimal128(revenue, 2))) AS revenue_state_type,
       toTypeName(uniqExactState(user_id)) AS users_state_type
FROM lab.events;
-- finalized daily distinct 합 ≠ 전체 distinct. daily states를 Merge해야 합니다.
SELECT sum(daily_users) AS sum_of_daily_distinct,
       (SELECT uniqExact(user_id) FROM lab.events) AS period_distinct
FROM (SELECT event_date, uniqExact(user_id) AS daily_users FROM lab.events GROUP BY event_date);

-- 공식 참고: https://clickhouse.com/docs/operations/system-tables/parts
-- https://clickhouse.com/docs/operations/system-tables/query_log
-- https://clickhouse.com/docs/sql-reference/statements/explain
-- https://clickhouse.com/docs/engines/table-engines/mergetree-family/aggregatingmergetree
