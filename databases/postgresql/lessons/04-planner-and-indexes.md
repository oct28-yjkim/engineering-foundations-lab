# M07–08. 카디널리티 추정과 접근 경로

## M07. 실행 계획은 미래에 대한 추정이다

**선수 지식:** M01 SQL 의미, M05 snapshot, EXPLAIN 기본 출력. **범위:** S.

플래너는 가능한 plan/path와 추정 비용을 비교합니다. 비용은 ms 단위 실측치가 아니며 행 수, 페이지 수, selectivity와 비용 파라미터에 의존합니다. 여러 열의 조건을 독립적이라고 추정했는데 실제로 강하게 연관되어 있다면 cardinality 오차가 join 순서와 방법, 메모리·병렬 선택에 전파됩니다. MCV는 흔한 값, histogram은 나머지 분포, ndistinct는 서로 다른 값 수의 추정에 기여합니다. [추정 예제](https://www.postgresql.org/docs/18/row-estimation-examples.html), [플래너 통계](https://www.postgresql.org/docs/18/planner-stats.html).

`EXPLAIN ANALYZE`에서 여러 번 실행된 node의 rows/time은 loop당 평균으로 표시될 수 있습니다. 부모 시간에는 자식 시간이 포함되므로 node 시간을 모두 더하면 중복 계산됩니다. 먼저 실제로 많은 작업을 수행한 곳과 추정이 크게 틀어진 첫 지점을 찾습니다. [EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html).

### 실험 1: 독립성 가정의 반례

```sql
CREATE SCHEMA IF NOT EXISTS deep_lab;
CREATE TABLE deep_lab.m07_corr AS
SELECT g AS id, g % 100 AS a, g % 100 AS b,
       CASE WHEN g <= 99000 THEN 0 ELSE g END AS tenant_id,
       repeat(md5(g::text), 4) AS payload
FROM generate_series(1, 100000) g;
ANALYZE deep_lab.m07_corr;
SELECT attname, n_distinct, most_common_vals, most_common_freqs
FROM pg_stats WHERE schemaname='deep_lab' AND tablename='m07_corr';
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT * FROM deep_lab.m07_corr WHERE a=42 AND b=42;

CREATE STATISTICS deep_lab.m07_ab (dependencies, mcv) ON a, b FROM deep_lab.m07_corr;
ANALYZE deep_lab.m07_corr;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT * FROM deep_lab.m07_corr WHERE a=42 AND b=42;
```

`a=b`는 생성식으로 보장됩니다. 결과 행 수는 직접 COUNT로 검증하고, 통계 전후 `estimated rows / actual rows`를 기록합니다. 오차는 `max(estimate, actual)/max(min(estimate, actual),1)`처럼 정의를 명시합니다. 통계가 나아져도 동일한 scan이 최선이면 실행 시간은 거의 같을 수 있습니다. extended statistics가 모든 join 상관관계를 해결한다고 일반화하지 않습니다. [확장 통계](https://www.postgresql.org/docs/18/planner-stats.html#PLANNER-STATS-EXTENDED).

### 실험 2: parameter별 선택도와 plan cache

```sql
CREATE INDEX m07_tenant_idx ON deep_lab.m07_corr (tenant_id);
PREPARE m07_q(integer) AS SELECT * FROM deep_lab.m07_corr WHERE tenant_id=$1;
SET plan_cache_mode = force_custom_plan;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) EXECUTE m07_q(0);
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) EXECUTE m07_q(99999);
SET plan_cache_mode = force_generic_plan;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) EXECUTE m07_q(0);
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) EXECUTE m07_q(99999);
RESET plan_cache_mode;
DEALLOCATE m07_q;
```

강제 모드는 비교용 실험입니다. 운영 기본값으로 바로 적용하지 않습니다. custom/generic 계획의 planning 비용과 실행 비용을 함께 기록하고, 실제 드라이버·pool의 prepare 정책을 별도로 확인합니다. [PREPARE](https://www.postgresql.org/docs/18/sql-prepare.html), [계획 캐시 설정](https://www.postgresql.org/docs/18/runtime-config-query.html#GUC-PLAN-CACHE-MODE).

**예상 증거:** 상관 조건의 추정 오차 변화, 흔한 tenant와 희소 tenant의 서로 다른 선택도, plan cache 조건별 계획. 특정 scan이나 속도 향상은 보장하지 않습니다.

**실패 양상:** seq scan이라는 이유만으로 장애 판정, 먼저 `enable_seqscan=off`로 해결, estimate를 실측이라고 보고, stale statistics와 잘못된 SQL 의미를 같은 문제로 처리하기.

**산출물·통과:** 추정/실제/loops/filtered/buffers 표, 통계 전후 쿼리 결과 동등성, 설정 강제 없이 선택할 개선안 1개와 기각안 1개. 소스 `standard_planner`, `cost_seqscan`, `eqsel`에서 입력 통계가 비용/선택도로 바뀌는 경계를 찾습니다.

## M08. 인덱스의 구조·유지 비용·가시성

**선수 지식:** M03 페이지, M07 비용과 선택도. **범위:** S, B-tree 페이지 관찰은 E.

B-tree는 정렬된 key와 heap tuple 위치를 연결합니다. split과 중복 처리, 동시 접근을 위한 규칙이 있으므로 단순 이진 검색 배열과 다릅니다. 복합 인덱스는 정렬 순서가 중요하고, partial index는 predicate를 만족하는 행만 포함합니다. `INCLUDE`는 key 탐색 범위를 늘리는 것이 아니라 반환할 값을 싣는 기능입니다. index-only scan도 tuple 가시성을 판단해야 하며 VM이 충분하지 않으면 heap fetch가 필요합니다. [B-tree 구현 개요](https://www.postgresql.org/docs/18/btree.html), [partial index](https://www.postgresql.org/docs/18/indexes-partial.html), [index-only scan](https://www.postgresql.org/docs/18/indexes-index-only-scans.html).

### 실험 1: 조회 이득과 쓰기 비용 함께 측정

```sql
CREATE TABLE deep_lab.m08_orders AS SELECT * FROM commerce.orders;
ANALYZE deep_lab.m08_orders;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT order_id, ordered_at, status, total_amount FROM deep_lab.m08_orders
WHERE user_id=42 ORDER BY ordered_at DESC, order_id DESC LIMIT 20;

CREATE INDEX m08_cover ON deep_lab.m08_orders (user_id, ordered_at DESC, order_id DESC)
INCLUDE (status, total_amount);
VACUUM (ANALYZE) deep_lab.m08_orders;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT order_id, ordered_at, status, total_amount FROM deep_lab.m08_orders
WHERE user_id=42 ORDER BY ordered_at DESC, order_id DESC LIMIT 20;
SELECT pg_relation_size('deep_lab.m08_cover') AS index_bytes;

EXPLAIN (ANALYZE, BUFFERS, WAL, TIMING OFF)
UPDATE deep_lab.m08_orders SET total_amount=total_amount+1 WHERE user_id=42;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT order_id, ordered_at, status, total_amount FROM deep_lab.m08_orders
WHERE user_id=42 ORDER BY ordered_at DESC, order_id DESC LIMIT 20;
```

원본 commerce는 그대로 두고 복사본만 변경합니다. 현재 seed는 고객당 주문이 10건이므로 LIMIT 20을 써도 실제 반환은 10건입니다. UPDATE 뒤 heap fetch가 늘 수 있는 이유를 설명하고, vacuum 뒤 다시 확인합니다. VM·autovacuum·다른 세션 때문에 정확한 fetch 수는 달라질 수 있습니다. covering 전용 테이블과 좁은 인덱스 전용 테이블을 추가로 만들어 동일 업데이트의 WAL·index 크기를 비교하면 유지 비용을 분리할 수 있습니다.

### 실험 2: PostgreSQL 18 skip scan을 조건부로 이해하기

PG18 B-tree는 일부 선두 열 조건이 없더라도 skip scan으로 뒤쪽 열 조건을 활용할 수 있습니다. 선두 열의 distinct 수와 범위 비용에 따라 선택되므로 “leftmost 조건이 없으면 절대 못 쓴다”와 “항상 skip scan이 빠르다”는 둘 다 틀린 규칙입니다. [18 복합 인덱스](https://www.postgresql.org/docs/18/indexes-multicolumn.html).

```sql
CREATE TABLE deep_lab.m08_skip AS
SELECT g % 4 AS bucket, g AS event_id FROM generate_series(1, 100000) g;
CREATE INDEX m08_skip_idx ON deep_lab.m08_skip (bucket, event_id);
ANALYZE deep_lab.m08_skip;
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, TIMING OFF)
SELECT * FROM deep_lab.m08_skip WHERE event_id=54321;
```

별도 복사본에서 bucket을 `g % 10000`으로 바꾸고 동일 인덱스로 비교합니다. 전용 “Skip Scan” 노드 이름이 항상 출력된다고 가정하지 말고 index 조건, 검색 횟수 등 해당 버전의 EXPLAIN 출력과 buffer 작업량을 읽습니다. 자세한 기전은 동일 버전 `nbtsearch.c`에서 확인합니다.

**확장 과제:** 시간과 물리 순서의 상관이 높은 데이터에 BRIN, JSON/배열 포함 조건에 GIN, 범위 겹침에 GiST 후보를 제시합니다. 각 후보마다 지원 연산자·정확/손실성 재검사·쓰기 비용을 기록합니다. 인덱스가 “모든 필터를 빠르게 하는 기능”이 아님을 데이터 반례로 설명합니다. [인덱스 종류](https://www.postgresql.org/docs/18/indexes-types.html).

**예상 증거:** 안정 정렬된 동일 결과, scan/filter/buffer/heap fetch 변화, index bytes, UPDATE WAL, 선두 key distinct 수에 따른 계획 차이 또는 동일 계획의 합리적 이유.

**실패 양상:** INCLUDE 열 변경도 유지 비용이 있다는 점 누락, partial predicate와 parameter 계획의 함의 조건 무시, 낮은 scan 카운트만으로 제약 인덱스 삭제 판단, 높은 selectivity와 낮은 selectivity의 용어 혼동.

**산출물·통과:** 순차/복합/covering 또는 partial의 3가지 후보를 결과 동일성·읽기·쓰기·용량으로 비교합니다. index-only가 heap을 읽는 반례를 보이고, skip scan 미선택도 근거로 설명합니다. 소스 `nbtsearch.c`, `nbtinsert.c`, `nodeIndexonlyscan.c`의 연결을 [지도](../source-reading.md)에 따라 추적합니다.
