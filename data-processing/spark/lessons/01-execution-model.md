# 강의 1 — 실행은 언제, 어디에서, 몇 번 일어나는가

기준 Spark 4.0.4. 제공 실습은 [batch 과제](../labs/README.md); 이 강의의 cache·RDD·side-effect 변형은 추가 구현 과제입니다. LOCAL-SPARK와 CLUSTER-LAB을 구분합니다.

<a id="sp01"></a>
## SP01 — lazy plan에서 task attempt까지

### 원리

driver는 계획·스케줄링·결과 수집을 관리하고 executor는 task를 실행합니다. DataFrame 변환을 연결했다는 사실과 데이터가 모두 계산됐다는 사실은 다릅니다. 다만 schema 추론·metadata 조회 등은 계획 구성 중에도 I/O를 일으킬 수 있으므로 lazy를 “어떤 일도 하지 않는다”로 정의하지 않습니다. job/stage/task와 재시도 attempt는 서로 다른 식별자입니다. [공식 RDD 실행 모델](https://spark.apache.org/docs/4.0.4/rdd-programming-guide.html)을 출발점으로 삼습니다.

관찰 전에 다음 예측을 씁니다.

```text
입력 partition → filter/project → shuffle 의존 경계 → aggregate → 작은 결과
client API 호출 → driver 계획/스케줄링 → task attempts → 결과/commit
```

한 action에 정확히 한 job이 생긴다는 규칙을 외우지 않습니다. broadcast, 통계 수집, AQE materialization, `take`류의 점진적 조회로 UI에 나타나는 작업은 달라질 수 있습니다. 반대로 좁은 변환 여러 개가 한 stage의 task 안에서 연결될 수 있습니다. 이것은 실험에서 검증할 예측이지 임의 fixture에 고정된 job 수 정답이 아닙니다.

### 실험 계약

합성 주문 12개에 `event_id`, `customer_id`, 정수 `amount_cents`를 줍니다. 최소 1개 NULL customer와 중복 customer를 포함하고 event ID는 고유하게 만듭니다. 수동 원장에 고객별 건수·합계를 먼저 씁니다.

1. 명시적 schema로 읽고 filter·groupBy만 정의합니다. 계획과 job 현황을 보존합니다.
2. 작은 집계 결과만 `collect`해 oracle과 비교합니다. 전체 원문을 driver로 수집하지 않습니다.
3. 같은 action을 두 번 실행합니다. 계획 재사용과 계산 결과 저장을 분리합니다.
4. 집계 전 DataFrame을 `persist`하고 한 action으로 materialize한 뒤 반복합니다. 새 run에서는 `unpersist`하고 cold/warm 조건을 구별합니다.
5. `explain("formatted")`와 UI/event log의 SQL execution ID→job→stage→task attempt 연결을 그립니다.

**반례:** 출력 행이 작다는 이유로 입력 scan이 작다고 주장해 봅니다. 전체 합계 한 행도 전체 입력을 읽을 수 있습니다. 이어 projection/filter가 다른 두 query를 비교해 어떤 변화가 I/O를 줄였는지 분리합니다.

### 최소 통과

oracle에 모든 customer group과 NULL group이 일치해야 합니다. lazy/실행/cache materialization의 세 상태를 설명하고 action 전후 차이를 증거로 제출합니다. job 개수가 예측과 달랐다면 실제 계획과 auxiliary job을 추적합니다. Spark UI의 screenshot만 있고 입력과 결과가 없으면 미통과입니다.

<a id="sp02"></a>
## SP02 — lineage는 durable 업무 원장이 아니다

### 원리와 식

partition별 재계산은 같은 입력과 결정적 변환이라는 가정이 있어야 같은 결과를 냅니다. 좁은 의존성과 shuffle 의존성의 차이는 자식 partition이 어떤 부모 partition의 데이터를 요구하는가에 있습니다. 실행 중 cache block 소실, shuffle 파일 소실, driver 소실은 같은 장애가 아닙니다.

단순 작업 시간의 하한 모형을 직접 만듭니다.

```text
T ≥ max(총 유효 CPU 작업 / 병렬 slot 수, 가장 긴 의존 경로의 시간)
```

네트워크·scheduler overhead·spill·재시도가 빠진 하한입니다. partition 수를 두 배로 하면 시간이 반으로 준다는 예측이 이 식에서 나오지 않음을 설명합니다.

### 추가 구현 과제

1. 고정된 12개 정수로 RDD의 map/filter와 key별 reduce를 만들고 `toDebugString`으로 의존 경계를 표시합니다. RDD 과제는 classic 환경에서 수행합니다.
2. partition 1·2·8에서 입력 ID의 multiset과 최종 합계가 동일한지 검사합니다. 출력 순서는 계약에 넣지 않습니다.
3. `mapPartitions`가 외부 append를 수행한다는 가정으로 attempt를 두 번 실행하는 **오프라인 반례**를 만듭니다. 합계가 같아도 side-effect 원장에 중복이 생기는지 확인합니다.
4. `random`, 현재 시간, 변경되는 외부 lookup을 고정하지 않은 재계산을 넣습니다. seed만 고정한 것과 이벤트 ID에서 안정적으로 값을 유도한 것의 차이를 기록합니다.
5. CLUSTER-LAB을 선택했다면 새 격리 환경의 worker 하나를 중단하고 재계산 범위와 남은 입력 접근성을 관찰합니다. 자신의 학습용 프로세스만 대상으로 하고 공유 cluster는 금지합니다.

cache는 계산 비용을 줄이기 위한 수단이지 sink commit을 보존하는 장치가 아닙니다. checkpoint와 원본 source의 retention도 따로 설계합니다. 원본이 덮어쓰여 없어졌다면 lineage만으로 과거 데이터를 복구할 수 있다고 가정하지 않습니다.

### 소스·구술

[소스 지도](../source-reading.md)의 `RDD`, `Dependency`, `DAGScheduler`에서 “사용자 함수 저장→partition 요구→stage 생성→task 제출”을 추적합니다. 실패한 task가 다시 실행될 때 외부 결제 HTTP 요청도 자동으로 exactly-once가 되는지 질문하고 업무 멱등성 키의 위치를 설명합니다.

통과 조건은 3개 partition 설정의 ID 보존, narrow/wide 구분, 재시도 side effect의 중복 반례, local과 cluster 실패 범위 구별입니다. 실제 executor 장애를 실행하지 않았다면 설계 증거로만 표기합니다.
