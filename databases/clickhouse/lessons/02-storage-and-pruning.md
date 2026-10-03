# M03–M04. MergeTree 저장 구조와 읽기 범위 선택

[커리큘럼](../curriculum.md) · 이전: [기초](01-foundations-and-types.md) · 다음: [쿼리 엔진](03-query-engine.md)

## M03 part에서 열을 읽는 경로 LOCAL

**선수 조건:** M02. 정렬, 이진 탐색, 압축 블록과 파일 offset.

### 원리

삽입 데이터는 정렬되어 part로 기록되고 background merge가 여러 part를 새 part로 대체합니다. 한 INSERT가 항상 정확히 한 part라는 가정은 하지 않습니다. 블록 분할과 파티션 경계가 영향을 줍니다. 서로 다른 파티션의 part는 일반적인 background merge로 합쳐지지 않습니다.

`ORDER BY`는 part 내부의 정렬 규칙입니다. `PRIMARY KEY`는 sparse index에 저장할 키를 결정하며 별도로 지정하면 정렬 키의 prefix여야 합니다. 생략하면 정렬 키를 사용합니다. 어느 쪽도 유일성 제약이 아닙니다. sparse index는 행의 위치를 하나씩 저장하지 않고 읽을 후보 granule 범위를 찾는 데 쓰입니다. mark는 열 데이터의 위치를 찾는 정보이며, 압축 블록 경계와 논리적 granule 경계가 항상 같지는 않습니다.

`index_granularity=8192`를 “모든 granule은 8192행”이라고 읽지 않습니다. adaptive granularity는 행 수와 `index_granularity_bytes`를 함께 고려하고, 끝 granule이나 큰 행에서는 다른 크기가 됩니다. 마지막 mark 같은 형식상의 요소도 있어 `rows/marks`는 평균 관찰값일 뿐 정확한 granule 크기 명세가 아닙니다. Compact/Wide part는 파일 배치가 다릅니다. [MergeTree](https://clickhouse.com/docs/engines/table-engines/mergetree-family/mergetree)

### 실험

```sql
SHOW CREATE TABLE lab.events;
SELECT name, partition, part_type, rows, marks,
       data_compressed_bytes, data_uncompressed_bytes,
       primary_key_bytes_in_memory, bytes_on_disk
FROM system.parts
WHERE database = 'lab' AND table = 'events' AND active
ORDER BY partition, name;

SELECT name, value
FROM system.merge_tree_settings
WHERE name IN ('index_granularity', 'index_granularity_bytes',
               'min_rows_for_wide_part', 'min_bytes_for_wide_part');
```

`system.merge_tree_settings`는 설정의 기준값을 조사하는 도구이고 개별 테이블 override는 `SHOW CREATE TABLE`과 함께 확인합니다. 자신의 실행 버전에 열이 없으면 `DESCRIBE TABLE`로 확인하고 수정 내역을 기록합니다.

작은 테이블을 직접 만듭니다. 예제는 50,000행으로 제한합니다.

```sql
CREATE TABLE ch_course.granule_small
(id UInt64, payload String)
ENGINE = MergeTree ORDER BY id
SETTINGS index_granularity = 8192, index_granularity_bytes = 1048576;

CREATE TABLE ch_course.granule_wide
(id UInt64, payload String)
ENGINE = MergeTree ORDER BY id
SETTINGS index_granularity = 8192, index_granularity_bytes = 1048576;

INSERT INTO ch_course.granule_small
SELECT number, repeat('x', 8) FROM numbers(50000);
INSERT INTO ch_course.granule_wide
SELECT number, repeat('x', 1024) FROM numbers(50000);

SELECT table, part_type, sum(rows) AS rows, sum(marks) AS marks,
       rows / nullIf(marks, 0) AS rows_per_mark,
       sum(data_compressed_bytes), sum(data_uncompressed_bytes)
FROM system.parts
WHERE database = 'ch_course' AND table LIKE 'granule_%' AND active
GROUP BY table, part_type;
```

문자열이 잘 압축되는 것과 byte 기준 granularity 계산은 같은 문제가 아닙니다. 결과가 가설과 다르면 입력 block 크기, part 수, 버전의 granularity 구현을 조사합니다. part 생성 직후와 merge 이후의 차이도 기록하되 자동 merge 완료 시각은 가정하지 않습니다.

**기대 증거:** 실제 part 목록, 형식, rows/marks, 메모리 인덱스 크기. 각 part에서 predicate → primary index → mark range → 열의 압축 블록 → 필터로 이어지는 그림을 직접 작성합니다. [source-reading](../source-reading.md)의 `MergeTreeIndexGranularity*`, `MergeTreeDataPartWide`가 그림의 어느 단계인지 연결합니다.

**실패 모드:** primary key 중복을 오류로 예상, 파티션을 point lookup 인덱스로 사용, 너무 많은 파티션으로 작은 part 증가, mark와 한 행 포인터 혼동.

**제출·통과:** 작은/넓은 행의 대조, 1개 part 읽기 그림, granule 크기 예외 2개 설명. 같은 PK 행 2개를 작은 실험 테이블에 넣어 둘 다 존재함을 보여야 합니다.

## M04 정렬 키와 읽기 범위 선택 LOCAL

**선수 조건:** M03, 선택도·상관관계.

### 원리

범위 선택은 파티션, part의 범위 정보, primary index, 추가 skip index, 실제 행 필터 등 여러 단계에서 일어납니다. 선두 키의 범위를 좁히는 조건이 후속 키 활용에 도움이 되지만 “두 번째 키면 절대 사용하지 못한다”도 과도한 단순화입니다. 실제 `EXPLAIN indexes=1`의 조건과 선택된 granule을 읽습니다.

skip index는 각 데이터 범위에 대한 요약입니다. 요약이 predicate를 배제할 때 유용하며, 모든 범위가 모든 값을 포함하면 거의 아무것도 버리지 못합니다. Bloom filter의 false positive는 추가 읽기를 만들지만 정상 구현에서 false negative로 정답을 버리는 구조가 아닙니다. `PREWHERE`는 먼저 필요한 필터 열을 평가해 후속 열의 읽기를 줄일 기회이고, 인덱스처럼 모든 관련 범위를 처음부터 제거하는 개념과 구분합니다. [Data skipping indices](https://clickhouse.com/docs/best-practices/use-data-skipping-indices-where-appropriate), [PREWHERE](https://clickhouse.com/docs/sql-reference/statements/select/prewhere)

### 실험

같은 자료형·행·파티션을 사용하고 정렬 키만 바꿉니다.

```sql
CREATE TABLE ch_course.events_by_user AS lab.events
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (user_id, event_date, event_type, event_time);

INSERT INTO ch_course.events_by_user
(event_id, event_time, user_id, session_id, event_type,
 country, device, revenue, duration_ms, properties)
SELECT event_id, event_time, user_id, session_id, event_type,
       country, device, revenue, duration_ms, properties
FROM lab.events;

EXPLAIN indexes = 1
SELECT sum(duration_ms) FROM lab.events
WHERE user_id = 101 AND event_date >= '2026-02-01'
  AND event_date < '2026-03-01';

EXPLAIN indexes = 1
SELECT sum(duration_ms) FROM ch_course.events_by_user
WHERE user_id = 101 AND event_date >= '2026-02-01'
  AND event_date < '2026-03-01';
```

워크로드 3종을 양쪽에서 실행합니다: 사용자+날짜, 이벤트 종류+날짜, 국가+날짜. projection 추가 전 기준선을 확보하고 실제 결과 일치를 확인합니다. 각 쿼리의 선택된 Parts/Granules, `read_rows`, `read_bytes`, 시간, 메모리를 기록합니다. 동일 행이어도 현재 part 수가 다르면 이를 통제하거나 차이의 원인으로 기재합니다.

심화 과제로 별도 복사 테이블에 `country`의 set 또는 bloom skip index를 정의하고 materialize합니다. index 생성 자체는 기존 part에 자료가 생긴다는 뜻이 아니므로 materialization 상태를 조사합니다. 데이터가 각 granule에 거의 모든 국가를 담는 fixture와 국가별로 몰린 fixture를 비교합니다. 추가 인덱스의 공간·적재 비용도 기록합니다. projection은 또 다른 저장 표현과 유지 비용이 있으므로 동일한 평가표로 검토하며 26.8에서 제공되는 projection 기능과 최신 문서를 구별합니다.

**기대 증거:** 빠름/느림보다 “어느 단계에서 얼마의 읽기 후보가 제거되었는가”가 우선입니다. 같은 읽기 행에 시간만 달라졌으면 캐시·CPU·동시 작업을 조사합니다.

**실패 모드:** 키를 한 쿼리에만 맞춤, 고카디널리티 파티션, 효과 없는 skip index, `WHERE toString(key)=...` 같은 표현식의 활용 가능성을 추측, 무조건 `OPTIMIZE FINAL`로 비교 조건을 맞춰 실제 운영 비용을 숨김.

**제출·통과:** 2개 키 × 3개 워크로드의 계획·5회 측정과 같은 결과 증거, skip index가 무효한 반례, 정렬 키 ADR. 선택도가 같지만 정렬 상관이 달라 읽기량이 달라지는 이유를 설명합니다.
