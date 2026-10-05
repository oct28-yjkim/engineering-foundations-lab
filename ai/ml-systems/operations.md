# ML 시스템의 정상 관측과 장애 진단

[과정](curriculum.md) · [기본 LAB](labs/README.md) · [공식 자료와 독자 설계](references.md) · [검증 기록](validation.md)

모델 정확도만 보거나 모든 증상을 재학습으로 해결하지 않습니다. **입력 데이터 → feature/전처리 → 모델 artefact → 예측 응답 → label 연결 → 배포 판단**에서 어떤 계약이 깨졌는지 좁힙니다. 아래는 기본 LAB과 추가 운영 과제를 구분한 지침입니다. Stanford의 과제/정답을 복제한 문서가 아닙니다.

## 정상 기준선을 먼저 확보하기

저장소 루트에서 `python -B ai/ml-systems/labs/lab.py --plan`으로 범위를 확인한 뒤 `--run`을 선택합니다. runner는 전용 loopback 서비스에서 합성 요청을 검사하고 종료합니다. 외부 endpoint, 회사 모델/데이터, API credential을 받지 않습니다. 지속 관측 서버나 dashboard를 설치하는 명령이 아닙니다.

기준선에는 model/feature/preprocess version, 합성 입력의 예상 score/label, 요청 성공/거부 수, label이 확인된 건수와 분모를 기록합니다. 동일 입력을 같은 bundle에 주었을 때 결과가 일치하는지 확인하고 나서 잘못된 요청/불리한 candidate를 넣습니다. 단순 health 응답만으로 모델 정확성과 feature 최신성을 정상이라고 선언하지 않습니다.

## 관측 신호의 종류를 나누기

| 신호 | 답하는 질문 | 흔한 오해 |
| --- | --- | --- |
| 요청 수·오류 유형·응답 시간 | 서비스가 약속한 응답을 제공하는가? | HTTP 200이면 예측도 정답이라고 판단 |
| schema/type/version 거부·freshness | 입력과 bundle의 계약이 맞는가? | stale feature를 모델 성능 저하로만 판단 |
| label coverage·지연·join 누락 | 품질을 측정할 정답이 얼마나 도착했는가? | 아직 정답이 없는 예측을 정답/오답으로 임의 처리 |
| 전체/집단별 품질 | 어느 입력 집단에서 성능이 변했는가? | 전체 평균이 같으면 모든 집단도 같다고 판단 |
| feature/output 분포 | 입력이나 예측의 구성비가 바뀌었는가? | drift 경보만으로 품질 저하나 재학습 필요 확정 |
| 활성 model/bundle·변경 원장 | 어떤 코드/전처리/모델 조합이 응답했는가? | weight 파일만 되돌리면 모든 상태 복구라고 판단 |

기본 runner의 짧은 요청 시간은 기능 관측 자료입니다. 충분한 표본, 부하/동시성, warmup, 실제 payload 크기, tail·timeout·error 분모를 갖춘 latency SLO 시험이 아닙니다. 임계값은 fixture용 사전 gate이며 운영의 보편적 기준으로 복사하지 않습니다.

## 기본 실습에서 겪는 사건

### 1. 계약 오류와 feature 최신성

정상 입력에서 먼저 예상 결과를 확인합니다. 차원/타입, feature version, 시간 계약을 한 번에 하나씩 깨뜨려 명시적인 거부를 관찰합니다. 요청 수와 거부 원인을 분리하고 올바른 합성 값으로 수정한 후 다시 정상 예측을 확인합니다. 데이터가 틀렸는데 threshold나 모델을 바꾸는 것이 해결책은 아닙니다.

version이 같아도 실제 전처리 코드가 다를 수 있으므로 별도 parity 검사가 필요합니다. 기본 LAB의 version guard가 feature 의미의 전체 동등성, 모든 train-serving skew, 인증/인가를 검증하는 것은 아닙니다.

### 2. 과거 시점에서는 알 수 없던 feature

event time은 사건이 발생한 시점, available time은 시스템에서 그 정보를 사용할 수 있게 된 시점입니다. 과거 예측을 재현할 때 둘 다 prediction 시각보다 늦지 않아야 하는 fixture를 비교합니다. 과거 event가 늦게 수집된 경우도 당시에는 몰랐던 정보입니다.

기본은 작은 point-in-time 선택 함수와 반례입니다. 실제 stream watermark, 시간대·clock skew·정정 이벤트, DB as-of join, schema migration을 모두 구현하지 않습니다. [Kafka](../../streaming/kafka/README.md)·[PostgreSQL](../../databases/postgresql/README.md) 확장은 이 계약을 운영 저장소에서 다시 검증하는 선택 과제입니다.

### 3. 전체 평균 뒤에 숨은 candidate 악화

고정 baseline/candidate를 같은 입력·label로 비교하고 전체와 사전 정의한 집단별 metric을 계산합니다. 어느 집단에서 실패하는지 본 뒤 배포 gate를 판정합니다. candidate 노출과 rollback은 **이 process 내부의 교육용 controller**이며 실제 사용자 트래픽의 무작위 A/B test나 cluster 배포가 아닙니다.

복구는 baseline 이름만 출력하는 것으로 끝나지 않습니다. 같은 정상 요청을 HTTP로 다시 보내 model/feature 계약과 예측이 기준선으로 돌아왔는지 확인합니다. 실제 운영에서는 모델 외에 전처리·cache·writer/reader 호환성·진행 중 요청까지 복구 범위를 정의해야 합니다.

### 4. Label 지연과 drift 오진

품질은 label이 도착한 예측에 대해서만 계산하고, 전체 예측 수·label 확인 수·coverage를 함께 보존합니다. labeled subset이 전체를 대표한다고 가정하지 않습니다. 아직 label이 없으면 품질을 unknown으로 남기고 요청 성공률과 섞지 않습니다.

입력 분포가 달라도 품질이 유지되는 예, 입력 marginal이 같아도 정답 관계가 바뀌는 예를 구별합니다. 재학습 전에 계약 실패·label 오류·평가 집계·배포 변경을 조사합니다. 기본 fixture는 모든 drift 통계나 실무 탐지기를 제공하지 않습니다.

## 추가 운영 과제

다음은 기본 runner 이후 직접 구성할 과제입니다. 수행하지 않았으면 설계/미실행으로 표시합니다.

1. **Batch vs online:** 같은 bundle/input의 parity를 확인하고 freshness·처리량·대기 시간 요구를 비교합니다. queue·retry·idempotency를 정의합니다.
2. **Artefact와 lineage:** source/dataset/split/feature/model/전처리 revision 및 평가 결과를 연결합니다. manifest/hash와 접근 권한 검증, load 실패·schema migration 복구를 설계합니다.
3. **배포 안전성:** shadow/canary/blue-green의 관측·노출·rollback 조건을 비교하고 label 지연 중 승격 조건을 정합니다. 작은 offline gate가 causal online 이득의 증거는 아닙니다.
4. **자원과 비용:** 모델 로딩·batch·cache·worker·동시성 변화 하나씩만 비교합니다. OOM/timeout은 폐기 환경에서 제한된 budget으로 재현하며 cloud 생성은 자동 수행하지 않습니다.
5. **Feedback와 재학습:** 모델의 결정 때문에 어떤 label이 관측되지 않는지 기록합니다. retraining trigger·승인·holdout·lineage·rollback 없이 drift→자동 배포로 연결하지 않습니다.
6. **Privacy·보안·공정성:** raw input/label을 로그에 남기지 않고 허용된 관측 집단과 접근 권한을 정의합니다. 성별 등 민감 속성 사용은 임의로 도입하지 않으며 현재 합성 집단은 실제 인구집단을 뜻하지 않습니다.

## 설계 리뷰에 가져갈 한 장

업무 결정과 비ML 기준선, 예측 시점/label 지연, feature 정보 경계, offline/online 평가 단위, serving SLO·budget, bundle 호환성, rollback 범위, 보안/보존 정책, 담당자·승인 경로, 미확정 가정 열 가지를 [설계 리뷰 양식](templates/design-review.md)에 적습니다. 각 선택에 대안 하나와 실패 조건 하나를 붙입니다. 필요하면 [공통 장애 보고서](../../operations/incident-report-template.md)를 재사용합니다.

LLM/RAG에서는 model에 tokenizer/prompt/template/retrieval/index version이 추가될 수 있습니다. [LLM 평가](../llm-paper-lab/lessons/06-evaluation.md)·[Qdrant](../../search/qdrant/operations.md)·[OpenSearch](../../search/opensearch/operations.md)의 관측 경계와 연결하되, 검색 성공·생성 정답·도구 실행 성공을 하나의 지표로 합치지 않습니다.
