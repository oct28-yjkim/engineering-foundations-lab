# ClickHouse Lab

대규모 이벤트를 실시간에 가깝게 분석하는 업무를 가정합니다. 문법 암기보다 ClickHouse의 저장 구조에 맞춰 스키마와 쿼리를 설계하는 능력을 목표로 합니다.

## 학습 목표

- 열 지향 저장소와 벡터화 실행이 분석 쿼리에 유리한 이유를 설명한다.
- `MergeTree`의 part, background merge, sparse primary index, granule을 설명한다.
- 조회 패턴을 근거로 자료형, `ORDER BY`, `PARTITION BY`를 설계한다.
- 실행 통계와 `EXPLAIN`으로 읽은 행·바이트·granule을 비교한다.
- materialized view와 집계 테이블의 정확성·신선도 비용을 판단한다.
- part 폭증, mutation, 메모리 초과 등 대표 운영 문제를 조사한다.

## 4주 학습 로드맵

| 주차 | 주제 | 산출물 |
| --- | --- | --- |
| 1주 | 열 지향 저장, MergeTree, 기본 집계 | KPI 쿼리와 용어 정리 |
| 2주 | 자료형, 정렬 키, 파티션 | 스키마 설계 결정 기록 |
| 3주 | 실행 계획, pruning, materialized view | 측정 전후 비교표 |
| 4주 | 시스템 테이블, 장애 시나리오, 미니 프로젝트 | 운영 runbook과 대시보드 설계 |

## 0. 환경 확인

```bash
docker compose up -d clickhouse
docker compose exec clickhouse clickhouse-client \
  --user lab --password lab_password --database lab
```

접속 후 다음을 확인합니다.

```sql
SELECT version();
SELECT count() FROM events;
SELECT min(event_time), max(event_time) FROM events;
```

초기 데이터는 50만 건의 합성 이벤트입니다. 외부 데이터 다운로드 없이 동일한 결과를 재현할 수 있습니다.

## 1. 아키텍처와 저장 구조

### 반드시 설명할 수 있어야 하는 것

- 열 지향 저장은 필요한 열만 읽어 I/O를 줄이고, 유사 값이 모여 압축 효율이 높습니다.
- `MergeTree` 테이블에 insert된 블록은 immutable data part가 되고 background merge로 합쳐집니다.
- ClickHouse의 primary key는 일반적인 OLTP DB처럼 행의 유일성을 보장하지 않습니다. 정렬된 데이터에서 읽지 않아도 되는 granule을 건너뛰기 위한 sparse index입니다.
- 작은 insert를 지나치게 많이 보내면 part 수가 증가하여 병합 부담과 지연이 커집니다. 애플리케이션 배치 또는 비동기 insert를 검토합니다.

### 관찰 실습

```sql
SELECT
    table,
    count() AS active_parts,
    sum(rows) AS rows,
    formatReadableSize(sum(bytes_on_disk)) AS disk
FROM system.parts
WHERE database = 'lab' AND active
GROUP BY table
ORDER BY table;

SELECT database, table, elapsed, progress, num_parts
FROM system.merges
WHERE database = 'lab';
```

## 2. 데이터 모델링

### 자료형

- 값의 범위를 만족하는 가장 작은 정수형을 선택합니다.
- 반복되는 문자열 차원에는 `LowCardinality(String)`을 검토합니다.
- 금액은 부동소수점 오차가 문제가 되면 `Decimal`을 사용합니다.
- `Nullable`은 별도 null-map 저장 비용이 있으므로 “값 없음”이 실제 의미일 때 사용합니다.

### `ORDER BY`

`ORDER BY`는 물리 정렬과 sparse index의 효율을 결정하는 가장 중요한 스키마 선택입니다.

1. 실제 쿼리의 빈번한 필터 열을 후보로 정합니다.
2. 복합 키에서는 앞쪽 열부터 사용할수록 pruning이 유리합니다.
3. 시계열 범위 조건을 고려하되 무조건 시간 열을 첫 번째에 놓지는 않습니다.
4. UUID처럼 매우 높은 cardinality 열을 선두에 놓기 전에 쿼리 패턴을 검증합니다.

현재 `events`는 다음 패턴을 가정합니다.

```sql
WHERE event_type = 'purchase'
  AND event_time >= ...
  AND event_time < ...
```

따라서 `(event_type, event_date, user_id, event_time)` 순으로 정렬됩니다. `user_id`만으로 조회하는 요구가 많다면 별도 projection, materialized view, 또는 다른 정렬 키의 테이블이 나을 수 있습니다.

### `PARTITION BY`

파티션은 주로 데이터 수명 관리와 대량 삭제·교체의 단위입니다. 파티션 수를 과도하게 늘리면 part 수와 메타데이터 비용이 증가합니다. “쿼리에 날짜 조건이 있다”만으로 일 단위 파티션을 선택하지 말고 월 단위 등 충분히 굵은 단위부터 검토합니다.

## 3. SQL 분석과 성능 측정

연습 문제는 [`sql/01_exercises.sql`](sql/01_exercises.sql), 비교용 답안은 [`sql/02_solutions.sql`](sql/02_solutions.sql)에 있습니다.

각 쿼리에서 다음 값을 기록합니다.

```sql
SELECT
    query_duration_ms,
    read_rows,
    formatReadableSize(read_bytes) AS read_bytes,
    result_rows,
    formatReadableSize(memory_usage) AS memory
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query_kind = 'Select'
  AND event_time >= now() - INTERVAL 10 MINUTE
  AND query NOT LIKE '%system.query_log%'
ORDER BY event_time DESC
LIMIT 10;
```

분석 도구:

```sql
EXPLAIN indexes = 1
SELECT count()
FROM events
WHERE event_type = 'purchase'
  AND event_time >= '2026-02-01'
  AND event_time <  '2026-03-01';

EXPLAIN PIPELINE
SELECT country, sum(revenue)
FROM events
WHERE event_type = 'purchase'
GROUP BY country;
```

## 4. 사전 집계

증분 materialized view는 원본 테이블에 새로 insert되는 블록만 처리하는 insert trigger에 가깝습니다. 과거 데이터가 자동으로 역산되지 않는다는 점이 핵심입니다.

적용 전에 확인합니다.

- view 생성 전 데이터의 backfill 절차가 있는가?
- 재처리 시 중복 결과가 생기지 않는가?
- 원본의 update/delete가 집계 결과에 어떻게 반영되는가?
- 집계 대상 테이블 엔진과 `*State`/`*Merge` 함수가 일치하는가?
- 조회 비용을 insert 시점으로 옮겼을 때 적재 지연은 허용 가능한가?

## 5. 운영과 트러블슈팅

### 기본 조사 쿼리

```sql
-- 최근 실패 쿼리
SELECT event_time, user, query_duration_ms, exception, query
FROM system.query_log
WHERE type = 'ExceptionWhileProcessing'
ORDER BY event_time DESC
LIMIT 10;

-- 오래 실행 중인 mutation
SELECT database, table, mutation_id, command, create_time,
       parts_to_do, is_done, latest_fail_reason
FROM system.mutations
WHERE database = 'lab' AND NOT is_done
ORDER BY create_time;

-- 테이블별 압축률
SELECT table,
       formatReadableSize(sum(data_uncompressed_bytes)) AS uncompressed,
       formatReadableSize(sum(data_compressed_bytes)) AS compressed,
       round(sum(data_uncompressed_bytes) / sum(data_compressed_bytes), 2) AS ratio
FROM system.columns
WHERE database = 'lab'
GROUP BY table
ORDER BY table;
```

### 장애 시나리오

1. **Too many parts**: insert 배치 크기·빈도와 `system.parts`를 먼저 확인합니다. 강제 merge를 상시 해결책으로 사용하지 않습니다.
2. **메모리 초과**: `system.query_log`의 peak memory, 큰 `GROUP BY`/`JOIN`/정렬, 동시성을 확인합니다. 제한을 높이기 전에 읽는 데이터와 집계 cardinality를 줄입니다.
3. **mutation 장기 실행**: 대상 part 수, 디스크 여유, 다른 merge와의 경쟁을 확인합니다. ClickHouse에서 잦은 행 단위 update/delete는 데이터 모델 부적합 신호일 수 있습니다.
4. **조회 지연 증가**: 같은 query id의 `read_rows`, `read_bytes`, part 수, 정렬 키 적합성, 최근 스키마·데이터 분포 변화를 비교합니다.

## 6. 미니 프로젝트

“최근 30일 커머스 퍼널 대시보드”를 설계합니다.

필수 결과물:

- 요구 쿼리 5개와 허용 지연·신선도 정의
- raw event 스키마와 `ORDER BY` 선택 근거
- 시간/국가/기기별 방문→장바구니→구매 전환율
- 일별 매출 집계 materialized view
- 원본과 집계 결과를 대조하는 정확성 쿼리
- part 수, 적재 지연, 실패 쿼리, 디스크 사용량 운영 대시보드 초안

## 학습 체크리스트

- [ ] 50만 건 데이터에서 기본 집계 4개를 작성했다.
- [ ] 정렬 키 조건 포함/미포함 쿼리의 `read_rows`를 비교했다.
- [ ] 자료형과 압축률을 확인했다.
- [ ] materialized view를 만들고 backfill 문제를 설명했다.
- [ ] `system.parts`, `system.query_log`, `system.mutations`를 조사했다.
- [ ] 미니 프로젝트의 설계 의사결정을 문서화했다.

## 공식 참고 자료

- [ClickHouse documentation](https://clickhouse.com/docs)
- [MergeTree table engine](https://clickhouse.com/docs/engines/table-engines/mergetree-family/mergetree)
- [Choosing a primary key](https://clickhouse.com/docs/best-practices/choosing-a-primary-key)
- [Incremental materialized views](https://clickhouse.com/docs/materialized-view/incremental-materialized-view)
- [System tables](https://clickhouse.com/docs/operations/system-tables)
