# Spark 심화 과정 평가 기준

[커리큘럼](curriculum.md) · [실습 범위](labs/README.md) · [소스 지도](source-reading.md)

과정은 API 사용법보다 **논리 결과·물리 실행·상태·재시도의 경계를 증거로 설명하는 능력**을 평가합니다. CPU 모형, 실제 `local[2]`, 별도 cluster, 관리형 Databricks를 구분합니다. 하위 단계의 통과가 상위 환경의 내구성·성능·보안 검증을 대신하지 않습니다.

## 점수와 필수 게이트

정확성·원리/소스·실험/반증·운영/재현성 각 25점, 총 **80/100 이상·모든 영역 15/25 이상**과 아래 게이트 전부 통과가 선언한 범위의 완료 기준입니다.

| 영역 | 최소 증거 | 높은 수준의 증거 |
| --- | --- | --- |
| 정확성 25 | ID·집계·NULL·중복·순서 계약을 독립 oracle로 비교 | skew·late data·재시도·복원 뒤에도 같은 업무 불변식 검사 |
| 원리/소스 25 | 입력→logical/physical plan→stage/task→출력의 경계 | 고정 Spark revision의 관련 구현·테스트·실패 경로와 관찰 연결 |
| 실험/반증 25 | baseline·한 변인·원시 결과·음성 대조군 | AQE/partition/cache 등의 대안 설명 분리, 반복·slice·불확실성 |
| 운영/재현성 25 | 환경/설정·명령·실험 대상·비밀 제거·보존 기록 | 자원/시간 제한, 장애 중 관측, checkpoint/출력 정합 복구와 재현 |

1. **실행 범위:** 버전·master·실제 executor/driver 배치와 제공 코드 범위를 표시합니다. 로컬 task 병렬화를 다중 노드 장애 검증이라고 부르지 않습니다.
2. **정확성 우선:** count만 아니라 ID별 값·삭제·NULL·중복을 검사합니다. 평균을 병합할 때 sum/count를 보존하고 floating-point 허용 오차를 사전에 정합니다.
3. **관측과 추론:** action 전 계획, action 후 실제 plan/metrics와 추정치를 구분합니다. task 재시도 때문에 외부 효과가 중복될 수 있으며 성공한 job이 임의의 외부 transaction을 보장하지 않습니다.
4. **Streaming 계약:** source 재생·checkpoint·state·sink commit을 분리합니다. watermark 이후 데이터의 처리를 모든 operator에 동일한 규칙으로 일반화하지 않습니다. `foreachBatch`는 sink의 멱등성 계약 없이 exactly-once가 아닙니다.
5. **안전·복구:** 공유 checkpoint/output을 삭제하거나 운영 데이터로 장애를 유발하지 않습니다. runtime·query·state schema가 바뀐 재시작은 호환성 검토와 독립 검산이 필요합니다.
6. **증거 정직성:** 미실행을 PASS로 표시하지 않습니다. CPU 모형과 mock/AST 계약 테스트는 실제 Spark engine 실행과 별개입니다.

## 단계별 최소 결과물

| 범위 | 제출물 | 미검증 경계 |
| --- | --- | --- |
| OFFLINE | 4개 모형과 양성/음성 테스트, 가정 설명 | Spark scheduler·Delta log·실제 DBU 과금 |
| LOCAL-SPARK | 고정 환경, batch 결과·plan, file streaming 재시작 결과 | node loss·외부 source·cloud object store·분산 성능 |
| CLUSTER-EXTENSION | 실제 다중 process/node 설정·실패 이력·자원/보안 | 시험하지 않은 manager·workload·failure domain |
| MANAGED-EXTENSION | Databricks 별도 권한·runtime·비용·결과 | 다른 cloud·compute·SKU·runtime의 자동 일반화 |

SP01–04는 실행 경계·SQL 의미·계획, SP05–08은 shuffle/skew/memory/file 배치, SP09–10은 event time·state·source/sink, SP11–12는 운영·복구, SP13–14는 소스 연구·작은 통합 단면으로 평가합니다. 구체 module별 산출물은 [커리큘럼](curriculum.md)에 따릅니다.

## SP14의 2주 미니 캡스톤

앞서 만든 작은 fixture와 코드를 재사용하여 baseline, 변경 하나, 실패 조건 두 개를 묶습니다. batch plan/정합성 또는 streaming checkpoint/재시작 중 한 경로를 고릅니다. 전체 cluster·Kafka·Delta·Databricks·모델 학습을 새로 모두 구축하는 2주가 아닙니다.

동료는 입력의 임의 ID를 최대 10개(입력이 작으면 전체) 골라 처리/제외/중복/late/미확정 상태를 추적합니다. 구현이 잘못됐을 때 실패하는 테스트, 정상 실행, 실패 주입, 수정 또는 복구 후 결과를 제출합니다. 설계만 한 실패 조건은 실제 실행 gate를 대신하지 않습니다.

더 큰 통합은 선택 [8주 Lakehouse 캡스톤](../../capstones/governed-lakehouse.md)으로 분리합니다. 공통 [실험 보고서](../../databases/shared/templates/experiment-report.md)와 [장애 기록](../../databases/shared/templates/incident-review.md)을 사용하고 runtime 설정·입력/출력 경로·checkpoint ID·retention·권한 검증을 추가합니다.
