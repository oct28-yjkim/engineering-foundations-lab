# ML systems 실행 LAB: 계약 위반을 찾고 모델을 되돌리기

[트랙](../README.md) · [커리큘럼](../curriculum.md) · [운영·진단](../operations.md)

이 LAB은 **실제 HTTP 요청 → 정상 예측 → 잘못된 feature 거부 → 수정 후 회복 → candidate의 slice 품질 저하 확인 → baseline rollback 검증**을 수행합니다. Python 3.10+ 표준 라이브러리만 사용하며 GPU·Docker·외부 API·계정·추가 패키지를 요구하지 않습니다. 합성 logistic artefact 두 개는 코드에 고정된 weight이며, 여기서 학습하거나 사전학습 모델을 내려받지 않습니다.

## 실행 전: plan과 실제 실행의 차이

저장소 루트에서 다음을 실행합니다. `-B`는 Python bytecode cache 파일 생성도 막습니다.

```sh
python -B ai/ml-systems/labs/lab.py
python -B ai/ml-systems/labs/lab.py --plan
```

두 명령은 계획 JSON만 출력합니다. 파일 I/O·서버 생성·socket bind/connect·모델 추론 요청은 하지 않습니다. **서비스 실행은 아래 명시적인 선택 명령에서만** 발생합니다.

```sh
python -B ai/ml-systems/labs/lab.py --run
python -B -O ai/ml-systems/labs/lab.py --run
```

실제 실행은 `127.0.0.1`의 OS가 선택한 임시 포트에 서버를 열고, 고정 합성 요청을 순차 처리한 뒤 context의 `finally` 경로에서 shutdown·socket close·thread 종료를 확인합니다. 사용자가 endpoint·host·port·모델 경로·API key를 지정하는 옵션은 없습니다. `http.client`가 loopback IP에 직접 연결하며 proxy 환경변수를 쓰거나 redirect를 따라가지 않습니다. 같은 호스트의 다른 사용자로부터 보호하는 보안 sandbox는 아니므로 공유 서버·원격 노출·운영 데이터에 사용하지 않습니다.

정상은 exit 0, 실행/검산 오류는 `ERROR` JSON·exit 1입니다. socket 권한이나 환경 때문에 시작할 수 없으면 `loopback_environment_unavailable`로 실패하며 mock 결과로 성공을 대신하지 않습니다. core 검산은 `assert`를 사용하지 않아 `-O`에서도 유지됩니다. 통과 JSON의 `server_closed:true`를 확인합니다.

## 제공한 서비스와 제한

| 항목 | 제공 범위 |
| --- | --- |
| 요청 | `POST /predict`, JSON body 최대 2,048 bytes, feature 정확히 2개 |
| 모델 | `baseline-v1`: weights `(2,0)`; `candidate-v2`: `(2,-4)`; 둘 다 bias 0 |
| 계약 | `feature_version=signals-v1`, `preprocessing_version=identity-v1`, feature 순서 `(signal,channel_indicator)` |
| 전처리 | identity. 다른 scaler/배포 artefact 다운로드·학습 없음 |
| freshness | 합성 prediction time 100, feature age 0–30; 머신 시각이 아님 |
| 범위 | feature 값은 유한한 int/float, 절댓값 8 이하; bool은 숫자로 받지 않음 |
| 예산 | 실제 기본 실행 48요청, client/server 요청 상한 64, 응답 최대 4,096 bytes |
| 시간 | server socket 작업 timeout 1초, client I/O 최대 2초, 다음 요청 진입 시 session 예산 20초 검사 |
| 관측 | 요청·준비된 응답·오류 reason·model version별 count, handler latency 표본과 p95 |
| 보안·수명 | raw feature/header/예외문 로그 없음, 비밀 없음, 파일 저장 없음, 종료 후 상태 폐기 |

시간 예산은 이 소유한 bounded fixture를 위한 것입니다. 모든 I/O를 합친 엄밀한 전체 deadline이나 악의적 slow client에 대한 production 방어를 구현한 것은 아닙니다. TLS·인증·인가·multiworker·배포 API·지속 storage·HA·실제 feature store·모니터링 stack·재학습 시스템은 제공하지 않습니다.

## 1. 정상 추론 → 계약 위반 → 수정·회복

baseline의 `(1,0)` 입력은 logit 2, 확률 `0.8807970779778823`, 예측 1이어야 합니다. 독립 수치 oracle과 model/feature/preprocessing version을 확인합니다. fresh timestamp 95에서 시작합니다.

| 의도적 실패 | 응답 | 수정 후 검산 |
| --- | --- | --- |
| 허용되지 않은 schema field | 400 `schema_mismatch` | 정확한 네 field로 수정, 200·baseline 확률 복원 |
| bool을 feature로 전달 | 422 `type_mismatch` | 유한 숫자로 수정, 같은 결과 |
| feature 하나만 전달 | 422 `dimension_mismatch` | 두 feature 계약 복구 |
| timestamp 60으로 age 40 | 409 `stale_feature` | 허용된 신선한 fixture 95로 복구 |
| 과거 feature version | 409 `feature_version_mismatch` | artefact의 feature 계약과 일치시킴 |
| 다른 preprocessing version | 409 `preprocessing_version_mismatch` | 실제 적용한 전처리와 artefact 계약 일치 |

각 실패 뒤에 정상 요청을 다시 보내고 200·모델 버전·동일 확률을 검산합니다. 운영 데이터에서 freshness를 회복하려고 timestamp만 거짓으로 바꾸라는 뜻이 아닙니다. 실제 시스템에서는 적절한 시점의 feature를 다시 얻고 data lineage를 확인해야 합니다. duplicate JSON key·NaN·미래 timestamp·잘못된 Content-Type·body 상한·request budget도 거부하며 테스트가 확인합니다.

## 2. Aggregate는 통과해도 중요한 slice가 망가질 수 있다

평가 fixture는 `core` 10개, `edge` 2개이며 label은 모두 알려져 있습니다. 이 fixture는 학습 데이터도, 운영 traffic도 아닙니다.

1. baseline 12요청에서 전체 12/12, edge 2/2를 얻습니다.
2. **격리된 로컬 평가를 위해서만** 메모리 pointer를 candidate로 바꾸고 같은 12개를 평가합니다. 운영 승격이 아닙니다.
3. candidate는 전체 11/12≈0.9167로 사전에 정한 aggregate 하한 0.9를 통과하지만 edge는 1/2=0.5로 떨어집니다. baseline 대비 slice accuracy 하락을 0.05까지만 허용하는 gate가 `slice_regression:edge`로 승격을 거부합니다.
4. controller를 baseline으로 복원한 후 동일 12응답의 probability·prediction·모델/feature/preprocessing version이 이전 baseline과 같은지 확인합니다.

상태 이력은 `baseline-v1 → candidate-v2 → baseline-v1`입니다. callback이나 외부 deployment API를 호출하지 않습니다. “전체 지표가 충분해 보이는 candidate도 slice 회귀로 거부”하는 **결정론적 검산**이지, 표본 두 개로 검증한 통계적 canary 정책이 아닙니다. 실제 rollout에는 표본 수·불확실성·label delay·guardrail·노출 방식·승인·모델/feature 호환성 정책을 별도로 설계해야 합니다.

## 3. Point-in-time, feature 품질, label coverage를 분리

이 절은 순수 Python fixture이며 serving endpoint 뒤에 feature store가 구축되어 있는 것은 아닙니다. prediction time 100에 대해 다음 두 조건을 모두 만족하는 최신 feature를 선택합니다.

```text
event_time <= prediction_time
available_time <= prediction_time
```

event 90·available 92·value 1은 사용할 수 있습니다. event 95·available 105·value 99는 “과거 event”여도 당시에 도착하지 않았으므로 사용할 수 없습니다. event time만 비교하면 99를 선택하는 누출이 발생하고, 올바른 PIT 선택은 1입니다. event 110도 제외합니다. 같은 entity/event/available 시점의 중복 버전은 입력 순서로 승자를 고르지 않고 거부합니다. 실제 CDC/version ordering 계약 전체는 미구현입니다.

다음 비율의 분모를 섞지 않습니다.

| 관측값 | fixture 결과 | 분모 |
| --- | --- | --- |
| feature 유효 비율 | 3/4 = 0.75 | 품질 검사 feature 표본 4개 |
| 초기 label coverage | 2/4 = 0.5 | 예측 ID 4개 |
| 초기 관측 label accuracy | 2/2 = 1.0 | 당시 도착한 label 2개만 |
| label 도착 완료 후 accuracy | 2/4 = 0.5 | 최종 label 4개 |
| 실제 HTTP response error rate | 6/48 = 0.125 | 준비된 HTTP 응답 48개 |

미도착 label을 음성 정답으로 대입하지 않습니다. label이 하나도 없으면 accuracy는 0이나 1이 아니라 `null`입니다. 초기의 좋아 보이는 정확도가 모델 개선을 뜻하지 않을 수 있고, label coverage가 높은 것 자체가 accuracy가 좋은 것도 아닙니다.

## 4. Drift와 성능 저하가 같은 사건은 아니다

covariate fixture의 `(-2,-1,1,2)`를 `(-4,-3,3,4)`로 바꾸면 mean absolute feature는 1.5→3.5로 달라지지만 동일 부호 규칙의 accuracy는 1을 유지합니다. 반대로 **X를 그대로 둔 채 label 규칙만 반전**하면 feature marginal은 같아도 accuracy는 1→0으로 떨어집니다.

이것은 drift detector나 자동 재학습 trigger를 구현한 결과가 아니라 두 명제를 반증하는 작은 독립 사례입니다. 실제 신호의 분포·대상 slice·sample size·label availability·업무 비용을 확인한 뒤 경보와 조치를 설계합니다.

## 지표 해석과 검증

`requests_seen`은 이 handler가 받은 요청, `responses_prepared`는 응답을 구성한 수이며 client가 응답을 수신했다는 증거는 아닙니다. 기본 실행에서는 client가 모든 응답을 받아 검산하므로 둘 다 48입니다. `error_responses=6`은 의도적인 계약 위반 거부이고, 정상 42개 모두 HTTP 200이라고 candidate 품질까지 정상이라는 뜻은 아닙니다. 실제 network/timeout 실패율은 별도 client 관측이 필요하며 실행 중 예상 밖 transport 실패는 전체 LAB 오류로 끝납니다.

`handler_p95_seconds`는 **handler 진입부터 응답 구성까지**의 monotonic 시간입니다. wire·client 지연, throughput, 장시간 tail, 동시 부하, SLO 준수 여부를 측정한 것이 아닙니다. 48개 표본 p95를 운영 benchmark로 인용하지 않습니다. 재실행 시 시간이 달라지는 것은 정상이고 요청·정답·실패 분류·복구 결과를 비교합니다.

다음 테스트 명령은 plan과 달리 **실제 loopback 서버를 반복 기동하고 종료**합니다. mock 테스트만 있는 것이 아닙니다. 서버가 허용되지 않은 환경에서는 실패를 미검증 상태로 보고합니다.

```sh
python -B -m unittest discover -s ai/ml-systems/labs -p 'test_*.py'
python -B -O -m unittest discover -s ai/ml-systems/labs -p 'test_*.py'
```

[test_lab.py](test_lab.py)는 literal 확률·계약 경계·PIT/label delay·slice gate·실제 HTTP 거부/수정·rollback·timeout 후 회복·budget·proxy 무시·외부 destination 차단·서버 cleanup/error path를 확인합니다. baseline 12/12 및 candidate의 전체/slice 정답은 별도 literal oracle로 검사하고, 예측을 바꿨을 때 반드시 실패하는 mutation 회귀 검사를 포함합니다. 지원하는 수치 범위를 벗어난 JSON 정수도 500이 아닌 계약 오류로 거부하고 정상 요청으로 회복하는지 확인합니다. 테스트 동안 bind는 `127.0.0.1:0`, connect는 `127.0.0.1`로 제한하고 application file I/O도 차단합니다. mock 기반 redirect/응답 상한 검사는 실제 HTTP 통합 검사와 구별합니다.

제출물은 plan, 실제 실행 command/exit code, JSON의 정상/실패/회복 비교, 서로 다른 지표의 분모, candidate 거부 사유와 rollback 정합성, 종료 확인 및 미구현 production 책임입니다. 외부 회사 시스템·실사용자 데이터·토큰을 붙이지 않습니다.
