# M01–M02. 결과의 의미, 자료 표현, 비용 모델

[커리큘럼](../curriculum.md) · 다음: [저장 구조](02-storage-and-pruning.md)

## M01 실행 환경과 비용 모델 LOCAL

**선수 조건:** 없음. SQL이 처음이면 SELECT → WHERE → GROUP BY → JOIN → window 순으로 기본 연습을 먼저 풉니다. 각 단계에서 입력 행·출력 행을 종이에 적습니다.

### 원리

SQL의 기본 입력은 중복이 존재할 수 있는 행의 집합입니다. `GROUP BY`는 관찰된 그룹만 반환하므로 데이터가 없는 날짜를 자동 생성하지 않습니다. `count()`와 `count(nullable_column)`은 NULL 처리에서 다르고, 정렬을 요청하지 않은 결과의 순서는 계약이 아닙니다. 집합만 비교한 “퍼널”은 같은 사용자가 방문 후 구매했는지를 보장하지 않습니다. 정확한 질문 정의가 성능 최적화에 앞섭니다.

열 지향 저장은 한 행의 모든 필드를 함께 읽는 대신 필요한 열을 선택해 읽을 기회를 제공합니다. 값의 유사성은 압축을 돕고, 연속 메모리의 여러 값에 같은 연산을 적용하면 분기와 함수 호출을 줄일 수 있습니다. 그러나 JOIN hash table, 문자열 parsing, 고카디널리티 집계는 CPU·메모리를 더 많이 쓸 수 있습니다. “열 지향이면 항상 빠르다”는 예측 모델이 아닙니다.

첫 비용 모델은 `시간 ≈ 읽기·복호화/압축해제·표현식·집계·결과 전송의 임계 경로`입니다. 병렬 작업의 시간을 단순 합산하지 않습니다. 반환 행 수가 작아도 읽은 행 수와 중간 상태가 클 수 있고, `count()`는 메타데이터 최적화로 원본 열을 읽지 않을 수도 있습니다. 저장 매체의 바이트, ClickHouse가 보고한 읽기 바이트, 클라이언트 전송 바이트를 분리합니다.

### 실험

1. [README 시작 절차](../README.md#시작)로 버전과 seed를 확인합니다. `sql/01_exercises.sql`의 기본 문제에서 5개 쿼리를 직접 작성하고 결과 의미를 한 문장씩 적습니다.
2. 아래 세 쿼리를 실행합니다. 주석 식별자는 반복 측정마다 다른 번호로 바꾸고 query log에서 실제 `query_id`를 확보합니다. client가 지원하면 `--query_id`를 직접 부여합니다.

```sql
SELECT /* m01_count_r1 */ count() FROM lab.events;
SELECT /* m01_sum_r1 */ sum(duration_ms) FROM lab.events;
SELECT /* m01_map_r1 */ sum(length(properties['campaign'])) FROM lab.events;

SELECT query_id, query_duration_ms, read_rows, read_bytes, result_rows,
       result_bytes, memory_usage
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query LIKE '%/* m01_%'
  AND query NOT LIKE '%system.query_log%'
ORDER BY event_time_microseconds DESC
LIMIT 15;
```

3. 다음 작은 반례를 손으로 계산한 뒤 실행합니다.

```sql
SELECT count(), count(x), sum(x), uniqExact(x)
FROM values('x Nullable(UInt8)', (1), (1), (NULL));

SELECT user_id, event_type, event_time
FROM lab.events
WHERE user_id = 1
ORDER BY event_time, event_id
LIMIT 30;
```

4. 방문 이전 구매, 같은 timestamp의 두 이벤트, 활동 없는 날짜를 각각 fixture로 정의합니다. 실제 발생 시각 순서를 검증할 수 있는 식별자와 tie-breaker가 있는지 판단합니다. 현재 `00_setup.sql`의 생성식과 기존 볼륨의 seed 버전을 확인하고 이벤트 종류·기기·사용자 사이 상관과 세션 순서를 검사합니다. 합성 데이터를 실제 트래픽 분포라고 해석하지 않습니다.

**기대 증거:** 고정된 속도 수치가 아니라 쿼리별 읽기·반환·메모리 차이와 실행 계획입니다. 메타데이터 최적화 때문에 읽은 행이 줄었다면 원인을 설명합니다. `system.query_log`가 없거나 기록되지 않으면 설정·권한을 확인하고 미수집으로 기록합니다.

**실패 모드:** 빈 날짜 누락, 0과 NULL 혼동, `argMax` 동률을 유일한 최신 이벤트로 해석, 순서 없는 사용자 집합 비율을 순차 퍼널로 해석. [기본 답안](../sql/02_solutions.sql)은 자신의 계약에 맞는지 검토할 대상으로 사용합니다.

**제출·통과:** 5개 KPI의 정의와 결과, 위 3개 반례, 실행 manifest. 반환 행=읽은 행이라는 가정을 버리고 각 비용 지표가 측정하지 못하는 것까지 5분 안에 설명하면 통과합니다.

## M02 자료형은 정확성과 비용의 계약 LOCAL

**선수 조건:** M01, 정수 범위·부동소수점 근사·문자열 인코딩.

### 원리

정수 폭은 단순 저장량만이 아니라 허용 범위의 계약입니다. 범위를 좁히려면 현재 최댓값뿐 아니라 증가량·잘못된 입력·집계 결과 타입까지 고려합니다. `Decimal`은 지정된 scale의 십진 표현이며 “어떤 연산도 자동으로 안전”한 타입은 아닙니다. 반올림·overflow·나눗셈의 타입과 scale을 확인합니다. Float에서 Decimal로 변환하기 전에 이미 생긴 이진 표현 오차는 원래 입력을 복원해 주지 않습니다.

`Nullable`은 값과 null map을 함께 표현하고, `LowCardinality`는 사전과 참조를 사용합니다. 사전 부호화의 이익은 값 반복도와 연산에 의존합니다. 문자열 고유값 수가 입력 행 수에 가까워지는 경우까지 비교해야 합니다. 컬럼 codec은 그 표현에서 반복·차분 같은 구조를 이용할 수 있지만, 정렬 키를 바꾸면 압축 특성도 함께 바뀝니다. 타입 비교에서는 정렬 키와 입력 데이터는 고정합니다. [Nullable](https://clickhouse.com/docs/sql-reference/data-types/nullable), [LowCardinality](https://clickhouse.com/docs/sql-reference/data-types/lowcardinality)

### 실험

실험 이름이 없는 상태에서 한 번 생성합니다. 아래는 동일 데이터를 담는 두 표현입니다.

```sql
CREATE TABLE ch_course.types_plain
(
    id UInt64, country String, t UInt32 CODEC(LZ4)
) ENGINE = MergeTree ORDER BY id;

CREATE TABLE ch_course.types_encoded
(
    id UInt64, country LowCardinality(String), t UInt32 CODEC(Delta, ZSTD(1))
) ENGINE = MergeTree ORDER BY id;

INSERT INTO ch_course.types_plain
SELECT number, arrayElement(['KR','US','JP'], number % 3 + 1),
       toUInt32(number)
FROM numbers(100000);
INSERT INTO ch_course.types_encoded SELECT * FROM ch_course.types_plain;

SELECT table, name, type, data_compressed_bytes, data_uncompressed_bytes
FROM system.columns
WHERE database = 'ch_course' AND table IN ('types_plain', 'types_encoded')
ORDER BY name, table;

SELECT toTypeName(sum(toUInt8(1))),
       toDecimal64('0.10', 2) + toDecimal64('0.20', 2),
       toFloat64(0.1) + toFloat64(0.2);
```

테이블 전체 차이에는 country 표현과 t codec이라는 두 변인이 있으므로 열별로 비교합니다. 독립적인 인과를 보여 주는 추가 실험에서는 country만, codec만 바꾼 대조 테이블도 생성합니다.

두 테이블에서 `count()`, `sum(id)`, `sum(t)`, `GROUP BY country` 결과를 대조하고 `GROUP BY country`와 `sum(t)`를 각각 5회 측정합니다. 이어서 같은 생성식의 country만 `concat('u-', toString(number))`로 바꾼 새 실험 테이블로 높은 cardinality를 시험합니다. 0으로 나누지 않도록 압축률을 계산하고 낮은 cardinality에서 얻은 결론이 유지되는지 확인합니다.

**경계 과제:** UInt8의 255/256, 음수의 unsigned 변환, NULL, 빈 문자열, Decimal의 scale 차이, `DateTime`과 명시적 UTC의 `DateTime64`를 비교합니다. 자동 cast가 오류를 내는지 값을 바꾸는지 기록하고 입력 검증 책임을 정합니다. 금액 데이터는 문자열→Decimal 또는 정수 최소 단위에서 생성하고 Float 경유 변환과의 차이를 검사합니다.

**기대 증거:** 행 수와 논리 결과 일치, 열별 압축 크기, 쿼리별 메모리와 시간. 입력 크기나 압축률의 고정 답은 없습니다. 작은 데이터에서 차이가 보이지 않으면 측정 분해능·part 형식·사전 비용의 가설을 제출합니다.

**실패 모드:** 압축률은 좋지만 CPU 포화, Nullable의 의미를 잃는 default 치환, 타임존으로 인한 날짜 경계 변경, 집계형 overflow, 잘못된 cast. 압축은 정확성을 대체하지 않습니다.

**제출·통과:** 낮은/높은 cardinality 비교표, 단일 변수 추가 대조, 3종 이상의 경계값, 타입 선택 ADR. `src/Columns/ColumnVector.h`와 `src/Compression/CompressionCodecDelta.cpp`를 [소스 절차](../source-reading.md)로 추적하여 메모리 표현부터 저장 표현까지 설명합니다.

## 보충 읽기

- [ClickHouse architecture](https://clickhouse.com/docs/development/architecture)
- [Decimal](https://clickhouse.com/docs/sql-reference/data-types/decimal)
- [Selecting data types](https://clickhouse.com/docs/best-practices/select-data-types)
