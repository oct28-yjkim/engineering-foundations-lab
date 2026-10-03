# M11–M12. 집계 상태, materialized view, backfill, TTL

[커리큘럼](../curriculum.md) · 이전: [적재와 갱신](05-ingestion-and-correctness.md) · 다음: [분산과 복구](07-distributed-and-recovery.md)

## M11 삽입 블록과 집계 상태 LOCAL

**선수 조건:** M08의 state/merge, M10의 논리 최신 버전.

### 원리

incremental materialized view는 source에 들어오는 새 삽입 블록을 변환하여 target에 전달합니다. 이미 저장된 source 전체를 쿼리할 때마다 재평가하는 view가 아닙니다. 생성 이전 데이터, source mutation/삭제, Replacing의 background merge가 target의 과거 기여분을 자동 수정하지 않습니다. JOIN을 포함한다면 trigger가 되는 source와 조회되는 차원의 변경 시점도 계약에 포함합니다. [Incremental materialized views](https://clickhouse.com/docs/materialized-view/incremental-materialized-view)

따라서 모델을 먼저 선택합니다. 불변 이벤트의 합계는 state를 append하고 합칠 수 있습니다. “현재 고객 등급별 현재 주문 금액”처럼 원본 수정이 필요한 지표는 취소/보정 이벤트, 재계산, snapshot, 다른 view 방식 등을 검토합니다. `ReplacingMergeTree` raw에서 duplicate가 사라지는 것만으로 downstream sum의 중복 기여가 사라지지는 않습니다.

`AggregatingMergeTree`는 같은 정렬 키의 상태를 merge할 수 있지만 쿼리 시에도 `GROUP BY`와 `*Merge`로 아직 여러 part에 나뉜 상태를 합치는 계약을 사용합니다. 이미 합쳐진 한 row만 존재할 것이라고 가정하지 않습니다. 결과 `sum`과 `sumState`, `uniqExact`와 `uniqExactState`는 각각 scalar와 상태 타입의 차이가 있습니다. [AggregatingMergeTree](https://clickhouse.com/docs/engines/table-engines/mergetree-family/aggregatingmergetree)

### 실험

아래 전체 실험은 외부 writer가 없는 `ch_course`에서 한 번 실행합니다.

```sql
CREATE TABLE ch_course.mv_source
(id UInt64, user_id UInt64, bucket UInt8, cents UInt64)
ENGINE = MergeTree ORDER BY id;
INSERT INTO ch_course.mv_source VALUES (1,10,1,100);

CREATE TABLE ch_course.mv_target
(
    bucket UInt8,
    n AggregateFunction(count),
    users AggregateFunction(uniqExact, UInt64),
    revenue AggregateFunction(sum, UInt64)
)
ENGINE = AggregatingMergeTree ORDER BY bucket;

CREATE MATERIALIZED VIEW ch_course.mv_insert TO ch_course.mv_target AS
SELECT bucket, countState() AS n, uniqExactState(user_id) AS users,
       sumState(cents) AS revenue
FROM ch_course.mv_source GROUP BY bucket;

INSERT INTO ch_course.mv_source VALUES (2,10,1,200), (3,20,1,300);

SELECT bucket, count() AS n, uniqExact(user_id) AS users, sum(cents) AS revenue
FROM ch_course.mv_source GROUP BY bucket;
SELECT bucket, countMerge(n) AS n, uniqExactMerge(users) AS users,
       sumMerge(revenue) AS revenue
FROM ch_course.mv_target GROUP BY bucket;
```

이 시점 target에는 MV 이전 id=1의 기여가 없습니다. source 전체가 자동 반영된다고 예상했다면 모델을 수정합니다. writer가 없고 id=1을 아직 target에 넣지 않았다는 조건을 확인한 뒤 딱 한 번 과거 범위를 적재합니다.

```sql
INSERT INTO ch_course.mv_target
SELECT bucket, countState(), uniqExactState(user_id), sumState(cents)
FROM ch_course.mv_source WHERE id = 1 GROUP BY bucket;
```

위 두 SELECT로 다시 대조합니다. row count와 revenue는 exact equality가 필요하고 users도 이 예제의 `uniqExact`에서는 exact입니다. [기본 답안의 사전 집계](../sql/02_solutions.sql)와 타입·backfill 조건을 비교합니다. 어떤 구현이 `uniq`를 선택한다면 그 지표는 근사이며 count·sum과 허용 오차를 분리해야 합니다.

별도 scratch target에서 같은 backfill을 두 번 넣으면 count/sum이 왜 두 번 기여하는지 재현합니다. distinct 사용자 값이 같아 보이는 것이 전체 target의 멱등성 증거는 아닙니다. 마지막으로 `mv_source`의 cents 한 행을 mutation으로 바꾸고 완료를 기다린 뒤 source/target 차이를 관찰합니다. 이 fixture는 의도적으로 stale target을 만든 것이므로 운영 가능한 상태라고 표시하지 않습니다.

**기대 증거:** MV 전 삽입/후 삽입/backfill/중복 backfill/source mutation의 다섯 시점 비교. 이 작은 fixture에서는 최초 raw 합계 600, MV 생성 후 신규 기여 합계 500, 한 번 backfill 후 600이 논리 기대값입니다. 실행 완료 주장에는 실제 출력이 필요합니다.

**실패 모드:** raw FINAL 결과와 target sum이 저절로 일치한다고 생각, MV 존재만으로 모든 과거 데이터 반영, scalar 고유값 수를 합산, 타입 불일치 state를 섞음, target 직접 적재와 MV 경로를 중복 사용.

**제출·통과:** 다섯 시점 대조와 정상·stale 상태 판정, 수정 가능한 원본에 대한 집계 계약 ADR. 코드에서 INSERT의 view 전달 지점과 `AggregatingTransform`의 상태 생성 책임을 찾아 연결합니다.

## M12 backfill과 수명 주기의 경계 LOCAL OPS-DESIGN

**선수 조건:** M11, 범위 분할·멱등성·체크포인트.

### 원리

온라인 backfill의 핵심은 과거 범위와 live 범위가 누락 없이 전체를 덮고 서로 겹치지 않음을 증명하는 것입니다. event_time은 늦게 도착할 수 있어 cutoff 하나만으로 증명되지 않습니다. Kafka offset처럼 파티션마다 순서가 있는 ingestion 위치라면 경계는 하나의 시간보다 partition별 watermark 벡터가 될 수 있습니다. offset도 source→MV 처리가 어느 지점까지 완료되었는지와 결합해야 합니다.

간단하고 검증 가능한 오프라인 절차는 writer 정지·in-flight 완료 확인 → source 기준선 확정 → 빈 target에 한 번 backfill → 그룹별 정확성 대조 → live 시작입니다. 중간 실패 후에는 어느 범위가 원자적으로 반영되었는지 알아야 재시도할 수 있습니다. 부분 적재를 식별하지 못한다면 같은 집계 target에 무조건 다시 append하지 않습니다. staging target, 범위별 manifest, 검증된 partition 교체 같은 방안을 설계합니다. [Backfilling data](https://clickhouse.com/docs/data-modeling/backfilling)

TTL은 저장 수명 규칙을 background 작업에서 적용합니다. 시각을 지났다는 사실과 모든 행이 이미 디스크에서 제거되었다는 사실은 다릅니다. 법적/보안상 삭제 시한이 있다면 target, replica, backup의 잔존까지 포함한 별도 검증이 필요합니다. query에 시간 filter를 적용해 가시성을 제한하는 것과 물리 삭제도 구별합니다. [TTL](https://clickhouse.com/docs/guides/developer/ttl)

### LOCAL 실험

작은 disposable 테이블에서 시간과 물리 상태를 구별합니다.

```sql
CREATE TABLE ch_course.ttl_demo
(id UInt64, event_time DateTime('UTC'))
ENGINE = MergeTree ORDER BY (event_time, id)
TTL event_time + INTERVAL 60 SECOND;

INSERT INTO ch_course.ttl_demo VALUES
    (1, '2020-01-01 00:00:00'), (2, '2100-01-01 00:00:00');

SELECT now('UTC'), * FROM ch_course.ttl_demo ORDER BY id;
SELECT table, name, rows, active, modification_time
FROM system.parts
WHERE database = 'ch_course' AND table = 'ttl_demo'
ORDER BY name;
SELECT database, table, elapsed, progress
FROM system.merges WHERE database = 'ch_course';
```

시각이 지난 행이 첫 조회에 보일지 사라질지는 처리 시점에 영향을 받습니다. 충분한 관찰 시간을 정해 실제 시각과 상태를 기록하고, 그동안 TTL이 적용되지 않았다면 미적용 상태로 남깁니다. 필요하면 별도 실험에서 명시적인 TTL materialization의 비용을 관찰하되, 수동 작업 결과를 평소 TTL 지연이라고 보고하지 않습니다. 최신 날짜만 보이는 query와 저장된 전체 데이터 조회를 비교합니다.

### OPS-DESIGN 과제

온라인 전환 시나리오의 외부 writer·checkpoint 도구는 저장소에 제공되지 않습니다. 아래 명세를 먼저 작성하고 격리 환경에서 구현합니다.

| 단계 | 반드시 증명할 조건 | 실패 주입 |
| --- | --- | --- |
| 경계 확정 | 파티션별 ingestion watermark W, late event의 배정 규칙 | cutoff 뒤 과거 event_time 도착 |
| target 준비 | 스키마/함수 버전 일치, live 범위와 과거 범위 분리 | 일부 MV만 생성된 상태 |
| 과거 적재 | 처리 범위·완료 여부·검증 checksum/집계를 manifest에 기록 | batch 중단 후 재시작 |
| 검증·전환 | 모든 그룹 exact 지표 일치, 근사 지표는 사전 예산 안 | live writer가 검증 중 계속 입력 |
| rollback | 이전 경로 보존 기간, 재처리 위치, 중복 방지 | 전환 직후 target 지연·오류 |

**기대 증거:** local TTL 관찰표, 겹치지 않는 범위의 수식/그림, late arrival와 retry fixture, 실행했다면 원시 checkpoint 로그. 설계 문서만 있으면 “온라인 전환 설계 완료, 실행 미검증”이라고 기록합니다.

**실패 모드:** timestamp cutoff를 도착 순서로 착각, POPULATE 중 live write 경합을 무시, partial backfill 재시도 중복, source TTL이 target TTL도 결정한다고 오해, backup의 삭제 행 잔존 미고려.

**제출·통과:** raw/MV의 모든 그룹 대조, 중복·누락이 생기는 두 반례와 해결 증명, TTL 실제 지연 관찰. 온라인 완수 판정에는 정지·재개·retry의 실행 증거가 필요합니다.
