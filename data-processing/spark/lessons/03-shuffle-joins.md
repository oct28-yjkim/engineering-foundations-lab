# 강의 3 — 데이터 이동과 긴 꼬리가 만드는 실행 시간

기준 Spark 4.0.4. [오프라인 partition-skew 모형](../labs/README.md)은 key 분포를 설명할 뿐 Spark의 hash 함수·AQE·network를 실행하지 않습니다. 이 강의의 join·AQE 실험은 추가 PySpark 구현 과제입니다.

<a id="sp05"></a>
## SP05 — join의 비용보다 먼저 cardinality를 계산한다

### 원리와 독립 oracle

key `k`의 왼쪽 행 수를 `Lk`, 오른쪽 행 수를 `Rk`라 하면 일반 equi inner join의 pair 수는 NULL을 제외한 `Σk Lk·Rk`입니다. many-to-many 결과가 폭증한 상황은 단순 shuffle 설정으로 없앨 수 없습니다. 업무가 실제로 one-to-many를 요구했다면 dimension의 유일성을 검증해야 합니다.

합성 left `(l1,A),(l2,A),(l3,B)`와 right `(r1,A),(r2,A),(r3,B),(r4,C)`의 pair 원장은 A 4개+B 1개=5개입니다. 오른쪽을 임의로 dedup하면 cardinality와 의미가 바뀝니다. key뿐 아니라 `left_id,right_id` pair를 보존합니다.

shuffle join은 양쪽 key를 같은 실행 partition으로 모아야 합니다. broadcast 방식은 작은 쪽의 복제·materialization 비용과 executor별 memory를 감수합니다. 출력 cardinality, 필터 선택도, 직렬화 후 크기, 통계 오차를 함께 고려합니다. hint가 모든 join 유형에 강제 적용된다는 가정은 피합니다. 지원 조건은 [4.0.4 join·AQE 문서](https://spark.apache.org/docs/4.0.4/sql-performance-tuning.html)에서 확인합니다.

### 추가 실험 계약

1. 먼저 5개 pair fixture를 통과시킵니다. 다음으로 key 분포를 유지한 1만·10만 행으로 확장합니다. 크기는 로컬 자원 예산에 맞춰 상한을 둡니다.
2. AQE를 명시적으로 끈 baseline에서 auto broadcast 조건을 통제하고 실제 SortMergeJoin/Exchange가 생기는지 확인합니다. plan 이름이 예상과 다르면 데이터를 바꾸기 전에 왜 그런지 기록합니다.
3. 작은 dimension에 명시적 broadcast를 적용하고 pair 원장·집계를 대조합니다. broadcast wait·build size·shuffle read/write를 수집합니다.
4. dimension을 넓은 문자열 컬럼으로 확대합니다. row 수가 같아도 byte 비용이 달라지는지 봅니다. 실패를 유발하도록 무제한 확대하지 않습니다.
5. join 전 projection/filter를 적용한 후보와 비교합니다. 독립 oracle은 필터를 반영한 원본 pair 정의에서 만들며 최적화 코드와 공유하지 않습니다.

### 반례와 최소 통과

“broadcast threshold 아래니까 반드시 안전하다”를 반박할 수 있어야 합니다. source 파일 크기·논리 추정 크기·hash relation memory·여러 concurrent task의 memory는 동일하지 않습니다. 평균 task 시간과 최대 task 시간을 함께 제출합니다. 두 plan에서 정답이 같고, byte 이동·복제 memory·critical path 중 무엇을 줄였는지 근거를 제시해야 통과입니다.

<a id="sp06"></a>
## SP06 — AQE는 관측 이후의 의사결정이다

### 원리

실행 전 추정과 stage materialization 뒤 통계는 서로 다른 정보입니다. AQE는 runtime 통계를 이용해 선택 가능한 계획 일부를 바꿉니다. query가 다 끝난 뒤의 final plan과 action 이전 initial plan을 함께 보존해야 합니다. 작은 입력에서 skew 최적화가 나타나지 않는다면 절대 byte 기준·중앙값 배수·지원 join 형태 등 전제조건부터 검사합니다.

교육용 skew 지표는 `max(partition_rows) / mean(partition_rows)`로 시작합니다. 그러나 실제 AQE는 이 한 식으로 동작하지 않으며 row width가 달라지면 row 수와 byte skew도 달라집니다. task 시간 skew는 GC·노드 성능·I/O 대기 때문에 key skew 없이도 생깁니다.

### 2×2 추가 실험

균등/치우침 입력 × AQE off/on을 구성합니다. 모든 조건은 동일한 최종 pair 원장과 집계를 가져야 합니다. 치우친 데이터에서는 한 hot key에 70%를 배치하되 dimension cardinality는 통제합니다.

1. 조건별 seed, row 수, row width, 초기 shuffle partition, cores를 고정합니다.
2. action 전 initial plan과 실제 결과를 소비한 뒤 final plan을 기록합니다. coalesced partition·split 여부와 task 수를 관측합니다.
3. 테스트에서만 작은 임계값을 명시해 rule 활성화를 유도할 수 있습니다. 변경 전후 설정과 원래 기본값을 기록하고 그 값을 production 권장치로 배포하지 않습니다.
4. skew rule이 작동하지 않는 control도 남깁니다. “AQE on인데 빨라지지 않았다”는 결과도 유효합니다.
5. 동일 run의 stage별 input/output bytes, p50/p95/max task time, spill, scheduler overhead를 비교합니다.

### Salting 반증

추가 도전은 hot key의 left 행을 안정적인 `left_id` 기반 salt로 나누고 right hot-key 행을 모든 salt로 복제한 뒤 join하는 것입니다. 나중에 salt를 제거하여 원래 pair multiset과 정확히 비교합니다. 양쪽을 독립적으로 임의 salt하면 유효한 pair가 사라지고, cold key까지 무차별 복제하면 불필요한 비용이 생깁니다. outer join·NULL·집계의 salting은 별도 의미 검증 없이 일반화하지 않습니다.

### 소스·최소 통과

[AdaptiveSparkPlanExec·OptimizeSkewedJoin·AdaptiveQueryExecSuite](../source-reading.md)의 stage 완료 이벤트→통계→rule→최종 plan을 읽습니다. 활성/비활성 조건을 각각 하나씩 재현하고 두 조건 모두 정답을 보존해야 합니다. local wall-clock만으로 분산 network 개선 수치를 주장하면 미통과입니다. salting은 선택 확장이지만 수행했다면 pair 중복·누락 0이 필수입니다.
