# 강의 7 — 논문 주장을 실험 가능한 질문으로 바꾸기

SP13·SP14는 각각 2주입니다. upstream 전체 빌드, 다중 노드 장애, Databricks 이관까지 한 달에 필수로 몰아넣지 않습니다. 실행 가능한 작은 연구를 끝내고 큰 주장은 검증 범위를 명확히 남깁니다.

<a id="sp13"></a>
## SP13 — 현상→가설→소스→회귀

### 논문 세 편의 역할

| 논문 | 읽을 주장과 가정 | 직접 설계할 최소 실험 |
| --- | --- | --- |
| [RDD, NSDI 2012](https://www.usenix.org/conference/nsdi12/technical-sessions/presentation/zaharia) | 제한된 변환·lineage·재계산 가능한 데이터 | cache 재사용과 재계산 비용, 비결정적 함수로 가정 깨기 |
| [Spark SQL, SIGMOD 2015](https://people.csail.mit.edu/matei/papers/2015/sigmod_spark_sql.pdf) | 선언적 계획·rule 기반 확장성 | 같은 의미의 표현 2개, 최적화 전후 계획과 NULL 반례 |
| [Structured Streaming, SIGMOD 2018](https://people.eecs.berkeley.edu/~matei/papers/2018/sigmod_structured_streaming.pdf) | incremental query·progress/commit 모델 | bounded batch와 micro-batch 결과, commit 후 재시도 |

세 논문의 당시 cluster·Spark·비교 엔진·workload 조건을 오늘의 결과와 분리합니다. 로컬 12행 예제가 논문의 처리량 배수를 재현한 것은 아닙니다. paper claim을 ①원리 시연, ②선택 실험 재현, ③전체 benchmark 재현으로 나눠 완료 범위를 표시합니다.

### 24시간 안의 최소 연구

1. 기존 모듈의 한 현상을 고릅니다. 예: AQE를 켰지만 skew가 그대로임, NULL predicate 이동으로 잘못 예상한 join 결과, replay 후 sink 중복.
2. fixture를 최소화하고 기대값·실측값·환경을 적습니다. upstream bug로 단정하기 전에 계약·설정·버전 차이를 검토합니다.
3. [고정 소스 지도](../source-reading.md)를 따라 public entry point부터 5개 symbol, 2개 핵심 자료구조, 1개 오류/재시도 경계까지 추적합니다.
4. “내 가설이 틀리다면 관측되지 않아야 할 것”을 정하고 control case를 만듭니다.
5. BUILD 환경을 갖춘 경우 관련 upstream test를 선택 실행합니다. 없으면 별도 teaching model의 회귀 테스트와 source trace까지만 제출하고 source test는 미실행으로 남깁니다.

회귀 테스트는 수정 전 실패·수정 후 성공을 구분해야 합니다. 단순히 함수가 예외 없이 반환되거나 테스트가 0개 선택된 결과는 통과가 아닙니다. 실제 bug fix가 없어도 잘못된 가설을 증거로 기각한 연구는 유효합니다. 외부 issue·PR 발행은 학습 결과의 자동 단계가 아니며 별도 검토 후 결정합니다.

### 최소 통과

한 문장의 반증 가능한 가설, source commit, 정상/반례 fixture, 재현 명령, test 개수·실패 원인, 아직 모르는 조건을 제출합니다. source에서 비슷한 단어를 발견한 것과 실제 호출 경로를 입증한 것을 구분합니다.

<a id="sp14"></a>
## SP14 — 2주 최소 캡스톤

### 범위 선택

다음 중 **하나**를 선택합니다. 실제 Spark가 준비되지 않았으면 먼저 환경 준비를 보충하고, 오프라인 설계만으로 LOCAL-SPARK 완료를 주장하지 않습니다.

- 배치: 합성 문서 corpus의 ID·content hash·source version을 정규화하고 중복 처리·split leakage 방지 결과를 계산합니다. 실제 LLM 학습·embedding API는 포함하지 않습니다.
- 스트리밍: 작은 append-only 파일 source로 합성 주문 원장을 읽어 검증 가능한 output을 만들고 같은 checkpoint 재시작과 입력 schema 오류를 처리합니다. Kafka나 cloud 연결은 필수가 아닙니다.

### 주별 계획

| 시간 | 구현·검증 | 제출 |
| --- | --- | --- |
| 1주 앞 6시간 | 입력 schema·ID·중복/NULL·오류 처리 정책과 독립 oracle | 계약 1쪽, 고정 fixture, hand-calculated 작은 정답 |
| 1주 뒤 6시간 | 최소 Spark pipeline·plan·결과 비교 | 정상 실행 보고서, 작은 출력 fingerprint |
| 2주 앞 6시간 | 실패 2종, replay/재실행, 정답 불변식 검사 | 실패 경계 원장·누락/중복/정책 위반 diff |
| 2주 뒤 6시간 | source trace·자원 예산·한계·구술 | 재현 package, 미검증 목록, 후속 실험 계획 |

batch 실패 후보는 잘못된 type과 duplicate ID/동일 ID 다른 payload입니다. 실패 입력을 조용히 drop하지 말고 reject/quarantine 정책 및 개수를 검증합니다. streaming 실패 후보는 process 재시작과 schema 위반 파일입니다. 이 두 실패만으로 host 분리·분산 network 실패를 검증했다고 쓰지 않습니다.

### 필수 증거

1. 실행마다 새 학습 경로 또는 명시적으로 동일 checkpoint인 재시작 구간을 구분합니다. 사용자의 기존 경로를 overwrite하지 않습니다.
2. 입력 hash와 정확한 코드·Spark·Java·Python·설정 manifest를 보존합니다.
3. 외부 oracle과 결과를 event/document ID 수준으로 대조합니다. 합계가 우연히 같아지는 누락+중복 반례를 포함합니다.
4. 한 계획의 핵심 symbol을 source에서 설명하고 바뀐 설정이 그 경로에 영향을 주는지 확인합니다.
5. runtime·peak memory·출력 bytes와 비용 모델의 단위를 기록합니다. 합성 가격은 실제 청구서가 아닙니다.

### 완료와 다음 단계

[평가표](../assessment.md)의 공통 4영역 기준과 필수 gate를 적용합니다. 최소 캡스톤 완료는 전체 DB→Kafka→Spark→Lakehouse 시스템의 완료가 아닙니다. Databricks는 [별도 28주 트랙](../../../platforms/databricks/README.md)으로 확장하고, LLM corpus 품질은 [논문 실험 트랙](../../../ai/llm-paper-lab/README.md)의 평가 방법과 연결합니다. [거버넌스·Lakehouse 통합 연구 8주](../../../capstones/governed-lakehouse.md)는 새 범위·비용·권한·복구 목표를 정한 후 진행하는 선택 후속 프로젝트이며 SP14의 2주에 포함하지 않습니다.
