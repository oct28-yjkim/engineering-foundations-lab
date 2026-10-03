# M07–M08. JOIN의 의미와 집계 상태의 비용

[커리큘럼](../curriculum.md) · 이전: [쿼리 엔진](03-query-engine.md) · 다음: [적재와 갱신](05-ingestion-and-correctness.md)

## M07 JOIN은 먼저 관계의 계약이다 LOCAL

**선수 조건:** M06, hash table, 정렬, 다대일/다대다 관계.

### 원리

JOIN key가 RHS에서 유일하지 않으면 `ALL`은 매칭 조합을 만들 수 있습니다. `ANY`는 조합 증가를 제한하는 다른 의미의 연산이며, 최신 차원 행을 결정하는 규칙을 대신하지 않습니다. LEFT JOIN의 미매칭 값이 default인지 NULL인지는 `join_use_nulls` 같은 설정과 타입을 확인합니다. 분모·합계가 달라지는 쿼리를 더 빠르다고 채택하지 않습니다. [JOIN 문법과 의미](https://clickhouse.com/docs/sql-reference/statements/select/join)

hash join은 build 쪽의 키·payload와 hash table overhead를 메모리에 유지하며 probe합니다. 비용 모델은 `입력 행 수 + 출력 조합 수`뿐 아니라 distinct key, 키 길이, payload, skew, hash table 확장까지 포함합니다. 정렬 기반 join은 정렬 비용과 이미 정렬된 입력 활용 가능성을, grace hash 계열은 partition과 임시 I/O를 고려합니다. 실제 build 쪽과 알고리즘은 planner와 설정으로 확인하며 SQL에서 오른쪽이라고 항상 같은 방식으로 실행된다고 단정하지 않습니다. [JOIN 알고리즘 개요](https://clickhouse.com/blog/clickhouse-fully-supports-joins-how-to-choose-the-right-algorithm-part5)

### 실험

```sql
CREATE TABLE ch_course.fact (id UInt32, user_id UInt32, cents UInt32)
ENGINE = Memory;
CREATE TABLE ch_course.dim (user_id UInt32, tier String)
ENGINE = Memory;
INSERT INTO ch_course.fact VALUES (1,10,100), (2,10,200), (3,20,300), (4,30,400);
INSERT INTO ch_course.dim VALUES (10,'free'), (10,'paid'), (20,'free');

SELECT f.id, f.cents, d.tier
FROM ch_course.fact AS f LEFT ALL JOIN ch_course.dim AS d USING (user_id)
ORDER BY f.id, d.tier SETTINGS join_use_nulls = 1;

SELECT f.id, f.cents, d.tier
FROM ch_course.fact AS f LEFT ANY JOIN ch_course.dim AS d USING (user_id)
ORDER BY f.id SETTINGS join_use_nulls = 1;
```

손으로 예상 결과를 작성한 뒤 ALL과 ANY의 행 수·합계를 비교합니다. ALL에서는 user 10의 두 fact가 각각 두 차원 행과 만납니다. ANY가 free/paid 중 어느 값을 택했는지 관찰하되 비즈니스상 최신 차원이라고 해석하지 않습니다. user 30의 미매칭 표현을 `join_use_nulls=0`과 비교합니다.

다음 크기 실험에서는 `numbers()`로 100,000행 fact와 10,000행의 유일한 key 차원을 만들고 동일 SELECT를 `join_algorithm='hash'`, `join_algorithm='full_sorting_merge'`로 비교합니다. 지원하는 JOIN 형태를 선택하고 EXPLAIN으로 실제 경로를 확인합니다. payload를 8B/256B로 바꾸고, 키 1개에 fact 50%를 몰아 skew도 추가합니다. 최대 메모리 256MiB와 최대 실행 시간 30초를 query 수준에서 적용하고 초과는 실패 증거로 보존합니다. 이 확장 데이터 생성과 반복 harness는 학습자가 작성할 과제입니다.

**기대 증거:** 작은 fixture의 정확한 관계 결과, 같은 의미를 유지한 두 알고리즘의 plan·memory·wall, skew의 영향. 지원하지 않는 알고리즘/형태 조합은 버전 조건을 명시하고 대체 조건을 기록합니다.

**실패 모드:** ANY로 중복 데이터를 숨김, 차원 unique 여부 미검증, “RHS가 작다”만으로 메모리 예측, GLOBAL JOIN의 broadcast 비용을 무시, denormalization에서 차원 갱신 의미 누락.

**제출·통과:** 4개 입력 fixture의 결과를 손계산과 대조, 알고리즘 2개 비교, 차원 최신성 계약. `HashJoin.cpp`에서 build/probe 책임을 찾고 예상 peak memory와 실제 차이의 원인을 설명합니다.

## M08 상태 병합과 근사 오차 LOCAL SOURCE

**선수 조건:** M07, 결합법칙·표본·상대오차.

### 원리

평균을 분산 집계할 때 부분 평균을 그냥 평균내면 각 부분의 행 수 차이를 잃습니다. 올바른 상태는 sum/count처럼 결합 가능한 정보입니다. 고유 사용자 수 역시 부분 distinct count를 더하면 중복 사용자를 두 번 셉니다. `*State`는 병합에 필요한 중간 표현, `*Merge`는 같은 종류의 상태를 합쳐 최종 값을 만드는 인터페이스입니다. state와 finalized scalar를 혼동하면 사전 집계의 정확성이 깨집니다. [AggregateFunction 타입](https://clickhouse.com/docs/sql-reference/data-types/aggregatefunction), [집계 combinator](https://clickhouse.com/docs/sql-reference/aggregate-functions/combinators)

`uniqExact`의 상태는 distinct 값 수에 따라 커집니다. `uniq`는 hash 값의 적응적 표본을 사용하는 근사 알고리즘이고 `uniqHLL12` 등 다른 함수는 다른 오차 특성을 가집니다. HLL의 상대 표준오차 공식을 모든 uniq 함수에 그대로 적용하지 않습니다. deterministic한 함수에 동일 데이터를 10번 넣는 것은 오차 분포의 독립 표본 10개가 아닙니다. [uniq](https://clickhouse.com/docs/sql-reference/aggregate-functions/reference/uniq), [uniqExact](https://clickhouse.com/docs/sql-reference/aggregate-functions/reference/uniqexact), [uniqHLL12](https://clickhouse.com/docs/sql-reference/aggregate-functions/reference/uniqhll12)

### 실험

```sql
SELECT sum(part_sum) / sum(part_count) AS weighted_average,
       avg(part_sum / part_count) AS average_of_averages
FROM values('part_sum Float64, part_count UInt64', (10,1), (180,9));

SELECT uniqExact(user_id) AS exact, uniq(user_id) AS approx,
       abs(toFloat64(approx) - exact) / nullIf(exact, 0) AS relative_error
FROM lab.events;

SELECT uniqMerge(s)
FROM
(
    SELECT event_type, uniqState(user_id) AS s
    FROM lab.events GROUP BY event_type
);
```

전체 `uniq(user_id)`와 상태 병합 결과를 대조하고, `sum(각 event_type별 uniqExact(user_id))`가 전체 exact와 같아야 한다는 잘못된 가정을 반박합니다. 부분 집계 fixture를 작게 만들어 동일 사용자 1명이 두 그룹에 걸치도록 합니다.

오차 실험은 exact 기준 cardinality 1,000 / 10,000 / 100,000과 서로 다른 값 집합 seed 10개를 사용합니다. 예를 들어 `cityHash64(number, toUInt64(seed))`로 집합을 바꾸되 exact도 같은 입력에서 계산해 hash 충돌까지 기준선에 포함합니다. 균등 입력과 많은 중복, 한 그룹에 distinct 값이 몰린 입력을 분리합니다. 정확한 입력·함수·seed마다 absolute/relative error와 state 비용을 측정하고 중간값·최대 관찰 오차를 보고합니다. 이 최대값은 수학적 worst-case 보장이 아닙니다.

고카디널리티 GROUP BY의 hash state가 메모리를 얼마나 사용하는지도 비교합니다. 외부 집계 spill은 임계값을 설정하고 query별 외부 처리 ProfileEvents나 임시 I/O 증거로 실제 발생을 확인합니다. 설정 여부와 실행 여부를 분리하고, 실험 예산을 넘겨 host OOM을 만들지 않습니다.

**SOURCE 과제:** `Aggregator.cpp`, `AggregatingTransform.cpp`, `AggregateFunctionUniq.h`에서 상태 생성·행 추가·부분 상태 병합·파괴 책임을 찾습니다. 소스 함수가 보장하는 결합과 부동소수점 연산 순서에 따른 차이를 구분합니다.

**기대 증거:** 평균 반례, 부분 고유값 합산 반례, 함수별 오차·메모리 비교. 근사 오차가 작은 한 번의 실험을 모든 입력의 보장으로 일반화하지 않습니다.

**제출·통과:** 30개 이상의 서로 다른 데이터 조건, exact 기준선, merge와 scalar 합산의 차이, 업무상 허용 오차 ADR. 금액 원장처럼 exact가 필요한 지표와 탐색 대시보드의 근사 지표를 구별합니다.
