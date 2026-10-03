# Spark 28주 심화 커리큘럼

14모듈 × 2주 × 주 12시간 = 약 336시간입니다. 모듈당 원리·공식 자료 6시간, 실험 10시간, 소스 추적 4시간, 결과·구술 4시간으로 시작합니다. 미통과 항목의 보충과 실제 클러스터 준비는 별도 시간이 필요합니다.

## 모듈 지도

| 모듈 / 주 | 선수 조건 | 핵심 질문 | 제출·최소 통과 |
| --- | --- | --- | --- |
| SP01 / 1–2 | Python·SQL | [lazy execution·job/stage/task](lessons/01-execution-model.md#sp01) | action 전후 계획·job 원장; 호출 1회=job 1개라는 반례 |
| SP02 / 3–4 | SP01, 함수·파일 | [RDD lineage·partition](lessons/01-execution-model.md#sp02) | narrow/wide dependency, replay 가능한 입력 계약·side effect 반례 |
| SP03 / 5–6 | SP02, 관계대수 | [Catalyst](lessons/02-sql-catalyst.md#sp03) | analyzed/optimized/physical 계획, NULL·ANSI·중복 oracle |
| SP04 / 7–8 | SP03, JVM/Python | [codegen·UDF·Arrow](lessons/02-sql-catalyst.md#sp04) | built-in/UDF 대조, 변환·batch 경계, 동일한 결과 계약 |
| SP05 / 9–10 | SP03, hashing | [shuffle·join](lessons/03-shuffle-joins.md#sp05) | join cardinality·shuffle byte·memory 예산; 잘못된 broadcast 반례 |
| SP06 / 11–12 | SP05 | [AQE·skew](lessons/03-shuffle-joins.md#sp06) | initial/final 계획·task 분포·무효 대조군; salting 보존성 |
| SP07 / 13–14 | SP04–SP06, GC | [memory·spill](lessons/04-memory-io.md#sp07) | heap/Python/off-heap/driver 분리; OOM 가설 3개 배제 |
| SP08 / 15–16 | SP07, 컬럼 저장 | [Parquet·파일 배치](lessons/04-memory-io.md#sp08) | 동일 행·다른 파일 배치 3개, pruning과 실제 읽기량 대조 |
| SP09 / 17–18 | SP03, event time | [watermark](lessons/05-structured-streaming.md#sp09) | 도착 순서별 window 원장; 지연 보장의 단방향 성질 |
| SP10 / 19–20 | SP09, transaction | [state·checkpoint·delivery](lessons/05-structured-streaming.md#sp10) | commit 간격 실패·재시작·중복 검출; sink 경계 설명 |
| SP11 / 21–22 | SP01–SP10 | [deployment·Connect·관측](lessons/06-operations.md#sp11) | driver/client/executor 배치·ID 매핑·권한 없는 UI 접근 부정 시험 |
| SP12 / 23–24 | SP10–SP11 | [복구·비용·보안](lessons/06-operations.md#sp12) | 재생/권한/비용 상한, RPO·RTO와 미검증 영역 |
| SP13 / 25–26 | SP01–SP12, Scala | [소스·논문 반증](lessons/07-research-capstone.md#sp13) | 5symbol·2자료구조·1회귀 테스트, 논문 가정 차이 |
| SP14 / 27–28 | SP13 | [2주 최소 연구](lessons/07-research-capstone.md#sp14) | 한 pipeline·두 실패·독립 oracle·재실행 보고서 |

## 실험을 통과시키는 기준

[공통 실험 방법](../../databases/shared/experiment-method.md)을 따릅니다. 작은 fixture의 정확성은 먼저 손으로 계산한 ledger 또는 별도의 순차 구현으로 검사합니다. 비교 대상 두 구현이 같은 집계 코드를 호출하면 독립 oracle이 아닙니다. 실수 합계는 허용 오차·누적 순서·NaN/NULL 정의를 먼저 고정하고 돈은 정수 최소 화폐 단위나 명시적 decimal을 씁니다.

성능 실험은 결과가 같다는 gate를 통과한 뒤에 진행합니다. warm-up·cache·JIT·입력 순서·partition 수·AQE·executor 수·Python worker 조건을 기록하고 A/B 순서를 섞습니다. 초기에는 조건별 20개 이상의 독립 측정 구간을 수집하되 그 숫자만으로 p99 신뢰성을 보장하지 않습니다. task가 100개인 job의 task latency와 사용자 100개 요청의 응답 latency도 구별합니다.

```text
run_id / data_fingerprint / spark_version / source_commit / java / python
API mode(classic|connect) / ANSI / timezone / AQE / input+shuffle partitions
input bytes+rows+key histogram / logical+physical plan / job+stage+task attempts
shuffle read+write / spill / GC / peak executor+driver memory / output fingerprint
stream query id+run id / batch id / source offsets / watermark / state rows
sink commit identity / fault injection boundary / expected+actual differences
```

로그·계획에는 합성 값만 포함합니다. 실행 계획의 literal, JDBC URL, event log에 credential이나 원문 문서가 들어가지 않도록 별도로 검토합니다.

## Gate와 완료 상태

- G1, SP01–SP04: 계획 단계·분산 실행·SQL 의미·언어 경계. 정확성을 깨뜨리는 최적화 주장을 반례로 기각합니다.
- G2, SP05–SP08: 데이터 이동·skew·memory·I/O. 하나의 knob와 하나의 시간 값으로 원인을 단정하지 않습니다.
- G3, SP09–SP12: 시간·state·복구·권한·운영. local 재시작과 분산 장애의 증거 범위를 분리합니다.
- G4, SP13–SP14: 소스 근거와 제한된 연구. source-only 테스트, 실제 Spark, 실제 클러스터 결과를 각각 표시합니다.

[평가표](assessment.md)는 정확성 25, 원리·소스 25, 실험·반증 25, 운영·재현성 25점입니다. 총 80점 이상, 모든 영역 15점 이상, 필수 gate를 함께 만족해야 합니다. 클러스터 환경이 없으면 CLUSTER-DESIGN만 통과할 수 있고 CLUSTER-LAB은 미검증으로 남깁니다.

## 매 모듈 보고서

업무 질문 → 실패 모델 → 입력과 기대값 → 실제 실행 범위 → 결과/metrics/plan → 경쟁 가설 → 소스 근거 → 미완료 항목 순서로 작성합니다. 명령이 종료 코드 0을 반환했다는 사실은 정확성·EOS·권한 통과를 대신하지 않습니다. SP14 뒤의 [Databricks 확장](../../platforms/databricks/README.md)은 선택이며 Spark 28주의 자동 연장이 아닙니다.
