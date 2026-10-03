# M09–10. 실행기의 자원 소비와 버전 정리

## M09. node 하나의 속도에서 동시 실행의 비용까지

**선수 지식:** M04 buffer/WAL, M07–08 plan/index. **범위:** S. AIO backend 변경을 포함한 재시작 비교는 별도 격리 설정이 필요한 확장 실험입니다.

executor의 상위 node는 하위 node에서 tuple을 받아 필터·조인·정렬·집계를 수행합니다. Nested Loop는 inner 실행을 반복하고, Hash Join은 build/probe 및 필요시 batch 처리를, Merge Join은 정렬된 입력을 이용합니다. LIMIT가 하위의 모든 작업을 항상 줄여 주지는 않습니다. 정렬처럼 결과를 내기 전 입력을 모아야 하는 연산이 있기 때문입니다. [executor 구현 개요](https://www.postgresql.org/docs/18/executor.html).

`work_mem`은 연결 하나의 전체 메모리 제한이 아닙니다. 여러 sort/hash 연산과 여러 worker, 여러 동시 query에 적용되는 예산이 겹칠 수 있고 hash에는 `hash_mem_multiplier`도 관여합니다. parallel hash 등의 공유 메모리를 고려하면 단순 곱셈도 정확한 RSS 예측은 아닙니다. 계획별 활성 연산·worker·동시성을 이용한 보수적인 예산표와 실제 프로세스 메모리를 함께 봅니다. [자원 설정](https://www.postgresql.org/docs/18/runtime-config-resource.html).

### 실험 1: 정렬 spill을 계획과 I/O로 확인

M07의 `deep_lab.m07_corr`를 사용합니다. 각 설정에서 워밍업 후 예비 3회, 최종 비교는 20회 이상 수행합니다. 같은 EXPLAIN 옵션을 유지하고 캐시 상태를 기록합니다.

```sql
SHOW hash_mem_multiplier;
SET max_parallel_workers_per_gather = 0;
SET jit = off;
SET work_mem = '64kB';
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT id, payload FROM deep_lab.m07_corr ORDER BY payload, id;

SET work_mem = '32MB';
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT id, payload FROM deep_lab.m07_corr ORDER BY payload, id;
RESET work_mem;
RESET jit;
RESET max_parallel_workers_per_gather;
```

Sort Method, Memory/Disk, temp read/write, rows, execution time을 기록합니다. 큰 예산에서도 spill이 남는다면 tuple 폭·정렬 메모리 overhead·실제 데이터 크기를 조사합니다. 임의의 global work_mem 확대를 처방하지 않습니다. 같은 결과 정렬인지 확인할 때는 데이터 hash 또는 소규모 subset 직접 비교를 별도로 수행합니다.

이후 두 개의 동일 크기 학습 테이블을 `id`로 join하고 통계가 있는/없는 경우를 비교합니다. hash batch 증가 또는 nested loop의 loops 증가가 나타나지 않으면 데이터 크기·선택도를 한 변수씩 바꿉니다. plan을 강제로 만든 결과는 플래너가 자연스럽게 선택한 결과와 구별해 기록합니다.

### 실험 2: 병렬성·AIO가 자동으로 빠름을 뜻하지 않는다

```sql
SHOW io_method;
SHOW effective_io_concurrency;
SELECT backend_type, object, context, reads, read_bytes, writes, write_bytes,
       hits, evictions, stats_reset
FROM pg_stat_io ORDER BY backend_type, object, context;

SET max_parallel_workers_per_gather = 0;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT a, sum(length(payload)) FROM deep_lab.m07_corr GROUP BY a;
SET max_parallel_workers_per_gather = 2;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT a, sum(length(payload)) FROM deep_lab.m07_corr GROUP BY a;
RESET max_parallel_workers_per_gather;
```

설정 값 2가 worker 2개 실행을 보장하지 않습니다. Workers Planned/Launched, leader 참여, 전체 rows와 worker별 분포를 읽습니다. 데이터가 작아 serial을 고르면 비용상 합리적인 결과일 수 있습니다. 임시 테이블은 병렬 scan 실험에 부적합한 제약이 있으므로 이 강의는 일반 학습 테이블을 사용합니다. [병렬 동작](https://www.postgresql.org/docs/18/how-parallel-query-works.html), [병렬 제약](https://www.postgresql.org/docs/18/parallel-safety.html).

PG18 AIO는 sequential/bitmap heap scan, vacuum 등의 read 경로를 개선하기 위한 기반입니다. 캐시에 이미 있는 작은 데이터에서는 유의미한 차이가 없을 수 있습니다. `io_method`, 빌드·OS 지원, 장치 동시성을 기록한 뒤 sync/worker/io_uring 중 지원되는 조건을 별도 클러스터에서 비교합니다. 모든 작업·플랫폼에서 같은 향상을 기대하지 않습니다. PG18 `pg_stat_io`의 `read_bytes/write_bytes`를 사용하며 이전 버전의 `op_bytes` 가정을 그대로 복사하지 않습니다. [18 릴리스 노트](https://www.postgresql.org/docs/18/release-18.html), [I/O 통계](https://www.postgresql.org/docs/18/monitoring-stats.html#MONITORING-PG-STAT-IO-VIEW), [AIO 소스 설계](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/storage/aio/README.md).

**예상 증거:** sort 방식과 temp I/O의 변화, 병렬 계획 선택 여부/worker 수, 환경별 AIO 가능 범위. `pg_stat_io`는 누적·범위별 통계이고 단일 query 비용이라고 단정하지 않습니다.

**실패 양상:** worker 수만 늘려 CPU 경합 악화, 작은 query에 병렬 시작 비용 무시, work_mem을 connection limit로 오해, timing 계측 overhead를 성능 회귀로 해석, cold disk I/O와 shared read 혼동.

**산출물·통과:** 두 memory 조건의 분포와 plan 증거, 동시 query 20개를 가정한 자원 예산표, 병렬을 사용/기각한 근거를 제출합니다. 하나의 spilled sort와 하나의 join을 `tuplesort.c`/`nodeHashjoin.c` 경로에 연결하고 최종 비교는 조건별 20회 이상 원본 기록을 남깁니다.

## M10. HOT·pruning·vacuum·freeze는 다른 책임이다

**선수 지식:** M03–06, M09. **범위:** S, raw page의 HOT chain 관측은 E.

UPDATE의 새 버전을 같은 페이지에 두고 인덱스 참조를 재사용할 수 있으면 HOT의 이점이 생깁니다. 관련 인덱스 컬럼을 변경하지 않고 같은 페이지에 공간이 있어야 하는 조건이 중요합니다. summarizing index(BRIN)에는 예외가 있으므로 “어떤 인덱스 열이든 바꾸면 무조건 불가”라고 외우지 않습니다. fillfactor를 낮추면 공간 여유를 늘릴 수 있으나 용량·cache 비용도 늘어납니다. [HOT](https://www.postgresql.org/docs/18/storage-hot.html).

pruning은 안전하게 버전 연결을 줄이고 페이지 공간을 회수합니다. VACUUM은 heap/index 정리, VM 및 freeze 관리 등의 작업을 수행하고 ANALYZE는 플래너 통계를 수집합니다. 오래된 snapshot, slot의 xmin/catalog_xmin, 준비된 transaction 등은 정리할 수 있는 horizon에 영향을 줄 수 있습니다. dead tuple 추정치가 존재해도 지금 제거 가능한 버전인지 구분해야 합니다. [routine vacuum](https://www.postgresql.org/docs/18/routine-vacuuming.html).

### 실험 1: HOT 후보와 인덱스 추가의 영향

```sql
CREATE TABLE deep_lab.m10_hot (
  id integer PRIMARY KEY, marker integer NOT NULL, payload text NOT NULL
) WITH (fillfactor=70);
INSERT INTO deep_lab.m10_hot
SELECT g, 0, repeat('x', 64) FROM generate_series(1, 10000) g;
ANALYZE deep_lab.m10_hot;
UPDATE deep_lab.m10_hot SET marker=marker+1 WHERE id<=1000;
```

쓰기 transaction을 끝낸 뒤 세션을 잠시 idle로 두고 **별도 관찰 세션의 새 transaction**에서 누적 통계를 읽습니다. 통계가 아직 반영되지 않았으면 갱신 후 다시 관찰하고 시간도 기록합니다. 강의에서는 클러스터 전체 통계를 reset하지 않습니다.

```sql
SELECT relname, n_tup_upd, n_tup_hot_upd, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables WHERE relid='deep_lab.m10_hot'::regclass;
```

이제 `CREATE INDEX m10_marker_idx ON deep_lab.m10_hot(marker);` 후 같은 UPDATE를 반복합니다. 전후 카운터의 **차분**으로 HOT 비율을 계산하고 autovacuum·pruning의 개입을 기록합니다. 누적 비율을 두 번째 구간의 비율이라고 쓰지 않습니다. 일정한 HOT 비율은 보장하지 않으며, 인덱스 추가 전후의 차이를 공간 조건과 함께 해석합니다.

### 실험 2: 긴 snapshot이 정리에 미치는 영향

먼저 별도 테이블을 준비합니다.

```sql
CREATE TABLE deep_lab.m10_horizon AS
SELECT g AS id, 0 AS value FROM generate_series(1, 10000) g;
ANALYZE deep_lab.m10_horizon;
```

A:

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT sum(value) FROM deep_lab.m10_horizon;
-- snapshot을 유지한다.
```

B는 autocommit으로:

```sql
UPDATE deep_lab.m10_horizon SET value=1;
VACUUM (VERBOSE, ANALYZE) deep_lab.m10_horizon;
SELECT relname, n_live_tup, n_dead_tup FROM pg_stat_user_tables
WHERE relid='deep_lab.m10_horizon'::regclass;
SELECT pid, backend_xmin, xact_start FROM pg_stat_activity
WHERE datname=current_database();
```

A에서 같은 SUM을 재확인한 뒤 `COMMIT;`합니다. B에서 VACUUM을 다시 실행하고 verbose 출력의 제거 가능/불가능 버전, relation 크기, VM 관련 결과를 비교합니다. n_dead_tup은 추정이며 통계 시점·다른 정리 작업의 영향을 받습니다. 파일이 줄지 않아도 재사용 공간이 생길 수 있습니다.

### freeze와 wraparound 조사

```sql
SELECT datname, age(datfrozenxid), mxid_age(datminmxid)
FROM pg_database ORDER BY age(datfrozenxid) DESC;
SELECT oid::regclass AS relation, age(relfrozenxid), mxid_age(relminmxid)
FROM pg_class WHERE oid IN ('deep_lab.m10_hot'::regclass, 'deep_lab.m10_horizon'::regclass);
VACUUM (FREEZE, VERBOSE) deep_lab.m10_horizon;
```

FREEZE를 했으니 모든 age가 0이 된다고 가정하지 않습니다. tuple의 freeze 상태와 relation의 oldest-unfrozen 경계가 어떻게 다른지 설명합니다. 실제 wraparound를 일으키려고 대량 XID를 소진하지 말고 현재 설정·age·증가율로 남은 여유를 추정하는 경보 설계서를 만듭니다. PG18의 eager freezing·autovacuum 관련 변경은 실제 설정과 18 문서를 확인하며 이전 버전 튜닝 공식을 그대로 적용하지 않습니다. [vacuum 설정](https://www.postgresql.org/docs/18/runtime-config-vacuum.html).

**예상 증거:** 구간별 HOT update 비율, 유지 snapshot 전후 vacuum 결과, XID/MultiXact age, 공간 재사용과 파일 축소의 차이. E 실험에서는 M03의 pageinspect를 자기 테이블에 적용하여 HOT chain/flag를 소스와 대조합니다.

**실패 양상:** VACUUM FULL을 매일 실행하기, autovacuum을 꺼서 부하를 숨기기, ANALYZE와 VACUUM을 동일시하기, HOT를 항상 보장된다고 설명하기, replication slot 보유 horizon을 누락하기.

**산출물·통과:** HOT가 줄어드는 반례, snapshot 유지/해제 두 구간의 정리 증거, autovacuum 예산과 경보 기준을 제출합니다. 소스 `heap_vacuum_rel`과 `heap_page_prune_and_freeze`의 역할 차이와 제거해도 되는 버전의 판정 근거를 설명합니다.
