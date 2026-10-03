-- PostgreSQL 18 읽기 전용 관측 묶음. psql -v ON_ERROR_STOP=1 권장.
-- seed v2의 전용 DB에서 실행. 타 사용자의 query 텍스트는 권한에 따라 가려집니다.
-- 아래 통계는 누적/비동기 갱신입니다. 전후를 별도 autocommit 문장으로 수집하세요.
-- 긴 READ ONLY transaction으로 묶으면 통계 snapshot과 xmin 관측을 왜곡할 수 있습니다.
SET search_path TO commerce, public;
SET TIME ZONE 'UTC';

-- I-00. 실행 환경과 통계 reset 시점: benchmark 증거에 함께 저장합니다.
SELECT version(), current_database(), current_setting('TimeZone') AS timezone;
SELECT name, setting, unit, source, pending_restart FROM pg_settings
WHERE name IN ('block_size', 'shared_buffers', 'work_mem', 'maintenance_work_mem',
    'effective_cache_size', 'random_page_cost', 'seq_page_cost', 'track_io_timing',
    'track_wal_io_timing', 'wal_level', 'synchronous_commit', 'full_page_writes',
    'autovacuum', 'default_statistics_target', 'io_method', 'shared_preload_libraries')
ORDER BY name;
SELECT datname, stats_reset, xact_commit, xact_rollback, blks_read, blks_hit,
       temp_files, temp_bytes, deadlocks FROM pg_stat_database
WHERE datname = current_database();

-- I-01. seed 검증. expected와 actual이 모두 같아야 합니다.
SELECT 'users' AS relation, 10000 AS expected, count(*) AS actual FROM users
UNION ALL SELECT 'products', 1000, count(*) FROM products
UNION ALL SELECT 'orders', 100000, count(*) FROM orders
UNION ALL SELECT 'order_items', 300000, count(*) FROM order_items;
SELECT min(ordered_at), max(ordered_at), count(DISTINCT ordered_at::date) AS distinct_utc_days,
       count(*) FILTER (WHERE ordered_at < timestamptz '2026-01-01 00:00:00+00'
          OR ordered_at >= timestamptz '2026-06-30 00:00:00+00') AS out_of_range
FROM orders; -- days=180, out_of_range=0
SELECT count(*) AS invalid_orders FROM (
    SELECT o.order_id FROM orders AS o LEFT JOIN order_items AS i USING (order_id)
    GROUP BY o.order_id, o.total_amount
    HAVING count(i.line_no) <> 3 OR o.total_amount <> sum(i.quantity * i.unit_price)
) AS mismatches; -- 0
SELECT user_id, status, count(*) FROM orders WHERE user_id = 42 GROUP BY user_id, status ORDER BY status;
SELECT status, shipping_country, count(*) FROM orders GROUP BY status, shipping_country ORDER BY 1, 2;

-- I-02. heap tuple의 물리 위치와 MVCC 헤더. ctid/xmin은 영속 비즈니스 키가 아닙니다.
SELECT ctid, xmin::text, xmax::text, order_id, status FROM orders ORDER BY order_id LIMIT 12;
SELECT c.relname, c.reltuples AS estimated_rows, c.relpages AS estimated_pages,
       c.relallvisible, age(c.relfrozenxid) AS frozen_xid_age,
       pg_size_pretty(pg_relation_size(c.oid)) AS main_fork,
       pg_size_pretty(pg_relation_size(c.oid, 'vm')) AS visibility_map,
       pg_size_pretty(pg_relation_size(c.oid, 'fsm')) AS free_space_map,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS including_indexes_toast
FROM pg_class AS c JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'commerce' AND c.relkind = 'r' ORDER BY c.relname;
-- relpages/relallvisible는 catalog 추정치입니다. 즉시 정확한 VM 상태와 같다고 보지 않습니다.

-- I-03. statistics → cardinality estimate → plan 선택의 연결.
SELECT tablename, attname, null_frac, n_distinct, correlation,
       most_common_vals, most_common_freqs
FROM pg_stats WHERE schemaname = 'commerce' AND tablename = 'orders'
  AND attname IN ('user_id', 'status', 'ordered_at', 'shipping_country') ORDER BY attname;
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT order_id, status, ordered_at, total_amount FROM orders
WHERE user_id = 42 ORDER BY ordered_at DESC, order_id DESC LIMIT 20;
-- actual rows는 loops와 함께 읽습니다. shared hit은 OS cache hit 비율이 아닙니다.
SELECT relname, heap_blks_read, heap_blks_hit, idx_blks_read, idx_blks_hit
FROM pg_statio_user_tables WHERE schemaname = 'commerce' ORDER BY relname;
SELECT backend_type, object, context, reads, hits, evictions, stats_reset
FROM pg_stat_io ORDER BY backend_type, object, context;

-- I-04. Index Only Scan, HOT, vacuum을 연결할 누적 증거.
SELECT s.relname, s.indexrelname, pg_get_indexdef(s.indexrelid) AS definition,
       s.idx_scan, s.idx_tup_read, s.idx_tup_fetch,
       i.indisvalid, i.indisready, i.indisprimary, i.indisunique
FROM pg_stat_user_indexes AS s JOIN pg_index AS i ON i.indexrelid = s.indexrelid
WHERE s.schemaname = 'commerce' ORDER BY s.relname, s.indexrelname;
SELECT relname, n_live_tup, n_dead_tup, n_tup_upd, n_tup_hot_upd,
       n_mod_since_analyze, last_vacuum, last_autovacuum, last_analyze, last_autoanalyze
FROM pg_stat_user_tables WHERE schemaname = 'commerce' ORDER BY relname;
SELECT * FROM pg_stat_progress_vacuum; -- 보통 0행. 실패를 의미하지 않습니다.

-- I-05. heavyweight lock과 transaction 상태. PID별 wait graph의 간선입니다.
SELECT pid, state, xact_start, backend_xid, backend_xmin, wait_event_type, wait_event,
       pg_blocking_pids(pid) AS blockers, left(query, 160) AS query
FROM pg_stat_activity WHERE datname = current_database() ORDER BY xact_start NULLS LAST;
SELECT l.pid, l.locktype, l.mode, l.granted, l.relation::regclass AS relation,
       l.transactionid, l.virtualxid
FROM pg_locks AS l JOIN pg_stat_activity AS a ON a.pid = l.pid
WHERE a.datname = current_database() ORDER BY l.pid, l.granted, l.locktype;

-- I-06. WAL/체크포인트/복제. 이 파일은 WAL switch/reset/checkpoint를 실행하지 않습니다.
SELECT pg_is_in_recovery(), pg_current_wal_lsn(); -- primary 전용; standby에서는 replay LSN 사용
SELECT wal_records, wal_fpi, wal_bytes, wal_buffers_full, stats_reset FROM pg_stat_wal;
SELECT * FROM pg_stat_checkpointer;
SELECT application_name, state, sync_state, sent_lsn, write_lsn, flush_lsn, replay_lsn
FROM pg_stat_replication; -- 기본 single-node 구성에서는 0행
SELECT slot_name, slot_type, active, restart_lsn, confirmed_flush_lsn, wal_status
FROM pg_replication_slots; -- 기본 구성에서는 0행; 관측을 위해 slot을 만들지 않습니다.

-- 선택 관측: extension이 설치된 전용 DB에서만 아래 SELECT의 주석을 해제합니다.
-- 이 파일은 extension 설치, VACUUM, ANALYZE, checkpoint, 데이터 변경을 수행하지 않습니다.
SELECT name, installed_version, default_version FROM pg_available_extensions
WHERE name IN ('pageinspect', 'pg_visibility', 'pg_buffercache', 'pg_stat_statements') ORDER BY name;
-- SELECT * FROM page_header(get_raw_page('commerce.orders', 0));
-- SELECT lp, lp_flags, t_xmin, t_xmax, t_ctid, t_infomask, t_infomask2
-- FROM heap_page_items(get_raw_page('commerce.orders', 0));
-- SELECT * FROM pg_visibility_map_summary('commerce.orders'::regclass);
-- SELECT * FROM pg_buffercache_summary();
-- SELECT queryid, calls, rows, total_exec_time, shared_blks_hit, shared_blks_read,
--        temp_blks_written, wal_bytes FROM pg_stat_statements
-- WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
-- ORDER BY total_exec_time DESC LIMIT 10;

-- 공식 참고: https://www.postgresql.org/docs/18/monitoring-stats.html
-- https://www.postgresql.org/docs/18/pageinspect.html
-- https://www.postgresql.org/docs/18/pgvisibility.html
