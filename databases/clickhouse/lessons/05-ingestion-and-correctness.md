# M09–M10. 적재 응답, 병합, 갱신의 정확성

[커리큘럼](../curriculum.md) · 이전: [JOIN과 집계](04-joins-and-aggregation.md) · 다음: [MV와 수명 관리](06-materialization-and-lifecycle.md)

## M09 삽입 응답부터 병합 부채까지 LOCAL

**선수 조건:** M03의 part, M06의 자원 모델, timeout/retry.

### 원리

작은 INSERT마다 정렬·메타데이터·part 생성의 고정 비용을 지불하면, 새 part의 생성 속도가 병합으로 part를 줄이는 속도를 앞설 수 있습니다. 적재 순간의 rows/s만 보고 판단하면 나중에 쌓이는 merge 비용을 놓칩니다. 같은 총행 수를 batch 크기·빈도·파티션 분산도를 바꿔 비교해야 합니다. merge는 읽기/쓰기/CPU/여유 디스크를 소비합니다. [Insert 전략](https://clickhouse.com/docs/best-practices/selecting-an-insert-strategy)

비동기 insert는 서버 버퍼에 모았다가 flush합니다. `wait_for_async_insert=1`은 해당 flush가 처리된 결과를 기다리는 응답이고, `0`의 응답은 flush 전 버퍼 수용 단계일 수 있어 이후 오류·프로세스 손실에 대한 관찰과 재처리가 필요합니다. 둘을 같은 내구성 보장이라고 쓰지 않습니다. 기다린다는 설정 하나가 모든 replica, 임의 매체 장애, 다른 shard까지의 전역 트랜잭션을 제공하지도 않습니다. [Asynchronous inserts](https://clickhouse.com/docs/optimize/asynchronous-inserts)

재시도 시에는 세 층을 구별합니다. 전송 요청이 중복인지, block deduplication의 동일성·윈도우 조건에 맞는지, 업무 event_id가 중복인지입니다. 단일 `MergeTree`와 `ReplicatedMergeTree`의 중복 제거 설정/저장 위치는 같지 않을 수 있습니다. 버전·table settings·token·버퍼링을 확인하고 수명 제한 없는 exactly-once라고 주장하지 않습니다. MV를 함께 사용할 때는 원본과 target을 모두 검사합니다. [재시도 deduplication](https://clickhouse.com/docs/guides/developer/deduplicating-inserts-on-retries)

### 실험

먼저 기본 단일 삽입과 async 응답을 작은 데이터로 확인합니다.

```sql
CREATE TABLE ch_course.ingest
(event_id UInt64, arrived_at DateTime64(3, 'UTC'), payload String)
ENGINE = MergeTree ORDER BY event_id;

INSERT INTO ch_course.ingest VALUES (1, now64(3), 'sync');
INSERT INTO ch_course.ingest
SETTINGS async_insert = 1, wait_for_async_insert = 1
VALUES (2, now64(3), 'async-wait');

SELECT event_id, arrived_at, payload FROM ch_course.ingest ORDER BY event_id;
SELECT name, rows, level, bytes_on_disk
FROM system.parts
WHERE database = 'ch_course' AND table = 'ingest' AND active;
SELECT name, value FROM system.settings
WHERE name IN ('async_insert', 'wait_for_async_insert', 'deduplicate_insert',
               'deduplicate_insert_select', 'async_insert_deduplicate', 'insert_deduplicate');
```

일반 SELECT로 보는 session setting은 앞선 query 한정 setting과 다를 수 있습니다. query에 실제 적용한 값을 실험 manifest에 남깁니다. 고정 소스 기준 26.8의 `deduplicate_insert`는 과거 `insert_deduplicate`/`async_insert_deduplicate`보다 우선하는 통합 설정이므로 오래된 두 값만 보고 판단하지 않습니다. INSERT SELECT에는 별도 모드도 확인합니다. [26.8 Settings 구현](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Core/Settings.cpp)

별도 테이블 3개에서 **동일한 총 100,000행**을 1,000/10,000/100,000행 batch로 전송합니다. 모든 batch에 서로 겹치지 않는 event_id 범위를 부여합니다. generation/클라이언트 전송 시간을 포함하는 end-to-end와 query server 시간을 분리합니다. active parts는 끝난 시점뿐 아니라 적재 중에도 기록하고 merge가 계속 진행되는 사실을 남깁니다. 100,000개의 한 행 요청을 무제한 반복하는 부하를 만들지 않습니다.

async `wait=0`의 유실 가능성은 [격리된 장애 실험 설계]로 작성합니다. ACK 직후 process crash와 flush 직후 응답 유실을 나누고 event_id 원장을 대조합니다. 현재 단일 학습 DB에 무계획 kill을 실행하지 않습니다. 별도 폐기 가능한 인스턴스에서 재현했을 때만 실행 완료로 표시합니다.

**기대 증거:** 총행·distinct event_id 불변식, 시간별 part 수, merge 진행과 적재 지연, 응답 상태도. part 수가 정확히 INSERT 수가 될 것이라고 답을 정하지 않습니다.

**실패 모드:** timeout을 미적재로 단정하고 다른 payload로 재시도, ack 후 flush 오류 미수집, 파티션 분산 증가를 batch 문제로 오판, `OPTIMIZE FINAL`을 상시 치료로 사용, 높은 insert 처리량을 지속 가능 처리량으로 보고.

**제출·통과:** batch 3조건 비교, retry identity 계약, 응답 유실/프로세스 장애 상태표. `AsynchronousInsertQueue`에서 flush 트리거와 완료/예외 전달 경로를 source commit과 함께 설명합니다.

## M10 Replacing 버전과 갱신의 정확성 LOCAL

**선수 조건:** M09, 불변 part·논리 버전·삭제 표시.

### 원리

`ReplacingMergeTree`는 같은 **ORDER BY 키**의 행을 merge 과정에서 선택합니다. primary key 유일성 검사나 INSERT 시 즉시 upsert가 아닙니다. version이 있으면 가장 큰 version을 기준으로 선택하고 동률에는 엔진의 tie 규칙이 적용됩니다. 비즈니스 순서가 중요하면 같은 key/version의 서로 다른 payload가 발생하지 않도록 upstream 계약을 만듭니다. 늦게 도착했다고 더 최신 버전인 것은 아닙니다. [ReplacingMergeTree](https://clickhouse.com/docs/engines/table-engines/mergetree-family/replacingmergetree)

`FINAL`은 읽을 때 해당 엔진의 최종화 의미를 적용하는 것이며 디스크의 part를 강제로 하나로 합치는 명령이 아닙니다. physical merge가 완료되기 전에도 논리 결과를 얻는 방법이지만 CPU·메모리·읽기 비용을 측정해야 합니다. key의 일부를 변경하면 같은 엔티티의 새 버전이 다른 key가 되어 남을 수 있습니다. 파티션 경계를 건너는 버전은 background merge로 만나지 않으므로 partition 선택과 FINAL 관련 설정을 검토합니다.

삭제는 tombstone을 최신 버전으로 남겨 오래된 이벤트의 재등장을 막는 모델을 사용할 수 있습니다. `ReplacingMergeTree(version, is_deleted)`와 단순 `ReplacingMergeTree(version)` + 별도 삭제 열은 같은 계약이 아닙니다. 아래 실습은 후자를 사용해 최종 버전 선택 뒤 필터를 명시합니다. tombstone cleanup은 늦은 낮은 버전이 더는 오지 않는지, replica가 동기화되었는지 등 추가 조건이 필요하며 무조건 수행하지 않습니다.

### 실험

```sql
CREATE TABLE ch_course.entity_versions
(
    entity_id UInt64, version UInt64, deleted UInt8, payload String
)
ENGINE = ReplacingMergeTree(version) ORDER BY entity_id;

INSERT INTO ch_course.entity_versions VALUES (1,1,0,'old'), (2,1,0,'live');
INSERT INTO ch_course.entity_versions VALUES (1,3,0,'new'), (2,2,1,'tombstone');
INSERT INTO ch_course.entity_versions VALUES (1,2,0,'late-old');

SELECT * FROM ch_course.entity_versions ORDER BY entity_id, version;
SELECT * FROM ch_course.entity_versions FINAL ORDER BY entity_id;
SELECT * FROM ch_course.entity_versions FINAL WHERE deleted = 0 ORDER BY entity_id;

-- 동률 정책의 실험. 업무에서 의존할 결정 규칙으로 쓰지 않습니다.
INSERT INTO ch_course.entity_versions VALUES (3,7,0,'tie-a');
INSERT INTO ch_course.entity_versions VALUES (3,7,0,'tie-b');
SELECT * FROM ch_course.entity_versions FINAL WHERE entity_id = 3;
```

첫 세 INSERT 뒤 FINAL은 entity 1의 version 3과 entity 2의 version 2를 선택해야 합니다. deleted 필터를 적용하면 entity 2는 제외됩니다. 이 기대값은 fixture의 논리 불변식이며 실제 실행 로그를 별도 첨부합니다. 일반 SELECT의 행 수는 자동 merge 시점에 따라 달라질 수 있으므로 “반드시 5행”이라고 통과 조건을 만들지 않습니다. `argMax` 대안에는 version 동률·전체 row 선택·NULL semantics를 포함한 계약이 필요합니다.

갱신 비용은 별도 작은 plain MergeTree 테이블로 관찰합니다.

```sql
CREATE TABLE ch_course.mutation_demo (id UInt64, x UInt64)
ENGINE = MergeTree ORDER BY id;
INSERT INTO ch_course.mutation_demo SELECT number, number FROM numbers(10000);
ALTER TABLE ch_course.mutation_demo UPDATE x = x + 1 WHERE id < 10
SETTINGS mutations_sync = 1;
SELECT countIf(id < 10 AND x = id + 1), countIf(id >= 10 AND x = id)
FROM ch_course.mutation_demo;
SELECT mutation_id, command, parts_to_do, is_done, latest_fail_reason
FROM system.mutations
WHERE database = 'ch_course' AND table = 'mutation_demo';
```

`ALTER ... UPDATE` mutation, lightweight DELETE, 지원되는 버전의 lightweight UPDATE/patch part는 서로 다른 경로입니다. 26.8에서 활성화된 기능과 제한을 확인하고 “모든 갱신이 전체 테이블을 다시 쓴다”거나 “lightweight이면 공짜”라고 일반화하지 않습니다. [Update mutations](https://clickhouse.com/docs/managing-data/update_mutations), [Lightweight deletes](https://clickhouse.com/docs/guides/developer/lightweight-delete)

**기대 증거:** 늦은 버전·동률·삭제의 3개 fixture, FINAL 전후 논리 결과와 part 상태, mutation 완료/실패 상태. mutation submit 완료, 적용 완료, 디스크 공간 회수를 분리합니다.

**실패 모드:** 삭제 행을 최종 버전 결정 전에 제거하여 과거 버전 부활, 잘못된 ORDER BY 변경, version 동률 충돌, tombstone 조기 cleanup, mutation backlog와 일반 merge 경쟁.

**제출·통과:** 세 fixture의 정확성 증명, mutation 완료 확인, 쓰기/읽기 비용의 선택 ADR. `ReplacingSortedAlgorithm`에서 version 비교와 삭제 상태 처리를 추적하고 두 인자 엔진으로 옮길 때 계약 차이를 설명합니다.
