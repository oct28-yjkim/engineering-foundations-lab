# M13–M14. 논문을 읽었다는 말 대신 재현 가능한 증거 남기기

[트랙 안내](../README.md) · [논문 지도](../papers.md) · [실습 범위](../labs/README.md) · [평가](../assessment.md)

각 모듈은 2주·24시간입니다. M13은 한 현상의 소스·최소 재현, M14는 이전 실험을 다듬는 **작은 연구 capstone**입니다. 28주 트랙의 마지막 4주에 거대 모델 학습과 전체 제품 플랫폼 구축을 새로 끼워 넣지 않습니다.

<a id="m13"></a>
## M13. 논문 주장 → 구현 경로 → 독립 oracle → 반증

### 먼저 주장 크기를 줄이기

“RAG를 이해했다” 대신 “같은 corpus와 exact-search oracle에서 index revision이 어긋나면 어떤 query가 틀어지는가?”처럼 한 개의 관측 가능한 문장으로 시작합니다. 논문 전체의 우월성을 증명하려고 하지 않습니다. 데이터·model·hardware·metric·budget 중 자신의 환경과 다른 조건을 적습니다.

[논문 검토 템플릿](../templates/paper-review.md)에 주장, 필요한 증거, 반증 조건, 구현 가정, 원문 확인 위치를 기록합니다. 공식 원문에서 실제로 확인한 section/figure만 기입하고 기억으로 번호를 만들지 않습니다. [논문 지도](../papers.md)의 연도는 최초 arXiv 공개 기준이며 학회 발표연도와 다를 수 있습니다. 읽은 정확한 arXiv revision/PDF hash를 추가로 고정합니다.

다음 네 수준은 서로 다른 산출물입니다.

| 수준 | 말할 수 있는 것 | 아직 말할 수 없는 것 |
| --- | --- | --- |
| READ | 원문과 가정을 설명함 | 코드를 실행했고 결과가 재현됨 |
| TOY | 작은 입력에서 식·불변식·평가기 계약을 검증함 | 논문의 모델 성능·GPU 속도 재현 |
| SCALED-DOWN | 축소 데이터/모델에서 정의한 가설을 시험함 | 원 실험의 수치와 순위가 동일함 |
| PAPER-REPRODUCTION | 고정한 원 실험 조건과 결과를 허용 오차로 대조함 | 다른 모델·데이터·제품으로의 일반화 |

일치하지 않는 조건이 있어도 연구 가치는 있습니다. 단, 그 차이를 결과 해석에서 제거하지 않습니다. “논문 재현 실패”와 “필요한 원 데이터/모델/예산이 없어 실행 불가”도 다른 상태입니다.

### 소스 추적 절차

원문 또는 저자 공식 project에서 연결한 구현을 출발점으로 삼습니다. 공식 구현이 없거나 현재 유지되는 package가 다른 알고리즘이면 그 사실을 기록하고 학습자 구현과 구별합니다. 소스는 별도 학습 checkout에 준비하고 tag/commit, dirty 상태, dependency lock, license, dataset/model 사용 조건을 적습니다. 소스 HEAD가 논문 발표 당시 구현이나 설치된 wheel과 동일하다고 가정하지 않습니다.

필요한 경로만 읽습니다. 예를 들어 retrieval이면 입력 전처리 → encoding → score → top-k/filter → metric, 학습이면 batch → mask/target → loss → gradient → update → evaluation을 연결합니다. **최소 5개 지점**에 파일·symbol·commit·입출력 shape/dtype·오류 조건을 붙입니다. 데이터 접근권한 검사처럼 논문 밖의 제품 요구사항은 별도 층으로 표시합니다.

빌드/테스트 명령은 선택한 정확한 revision의 CONTRIBUTING/README를 읽고 결정합니다. upstream 전체 테스트를 무작정 실행하면 모델 다운로드·대용량 데이터·GPU·네트워크·유료 서비스가 필요할 수 있습니다. 명령 실행 전 입력 파일·외부 endpoint·예상 자원·중단 조건을 확인하고 가장 작은 표적 테스트를 선택합니다. 이 repo는 외부 repository의 전체 runtime을 제공하지 않습니다.

### 연구 후보: 하나만 선택

- **수치:** attention mask나 확률 정규화 오류가 작은 행렬 oracle에서 드러나는가?
- **학습:** adapter/선호 loss의 부호·scale 변화가 손 계산 및 finite difference와 일치하는가?
- **검색:** 정답 문서 누락과 ANN의 exact-search 불일치를 다른 metric으로 구별하는가?
- **context:** 동일 query의 근거 위치만 바꾼 paired 차이가 특정 prompt/version에서도 남는가?
- **agent:** 잘못된 tool 요청 또는 반복 관측이 실행 전에 거부되고 budget 내 종료되는가?
- **평가:** parser 실패/누락 sample/중복 query를 주입하면 평가기가 성공으로 숨기지 않는가?

첫 입력은 행렬 몇 개, 문서 몇 개, 질문 몇 개로 줄입니다. 다만 원인인 concurrency·permission·floating point precision을 제거한 뒤 같은 현상을 재현했다고 주장하지 않습니다. 최소 재현이 원 현상을 잃었으면 축소 과정에서 사라진 조건을 돌아봅니다.

### 독립 oracle와 mutation

1. 구현을 실행하기 전에 expected result와 허용 오차를 고정합니다. 작은 값은 손 계산하고 실제 product metric은 사전 label/별도 solver로 검사합니다.
2. 테스트 대상 코드의 출력을 복사해 expected를 만들지 않습니다. 다른 코드라도 같은 잘못된 식/데이터를 공유하면 독립성이 약합니다.
3. 자신의 local 실험 copy에서 잘못된 mask·wrong sign·missing denominator·권한 filter 제거 중 관련 mutation 하나를 적용합니다.
4. 정확히 어떤 test가 실패해야 하는지 먼저 적고 실제 실패를 확인합니다. timeout처럼 무관한 이유로 실패한 결과는 mutation 탐지 성공이 아닙니다.
5. 복구 후 통과를 확인합니다. 각 run의 source hash, input hash, expected/actual, tolerance, stdout 요약, 실행 상태를 남깁니다.

upstream issue/PR·외부 연락은 필수가 아니며 자동으로 수행하지 않습니다. 먼저 비밀 없는 repro packet을 만들어 동료에게 전달할 준비를 합니다. benchmark 데이터·모델 가중치·서비스 token을 git에 넣지 않습니다.

### 24시간 진행·통과

원문/주장 분해 4시간, 소스 경로 5시간, 최소 재현/독립 oracle 7시간, mutation/복구 4시간, 결과·한계 리뷰 4시간입니다. 준비가 안 된 GPU/API 실행은 별도 준비 단계로 남깁니다. 실제 테스트 없이 코드만 읽었다면 READ까지만 표시합니다.

통과 증거는 고정된 source 경로 5개, 독립 oracle, 의도된 실패→복구, 재현 명령, 미검증 범위입니다. “PASS 출력이 있다”가 아니라 **어떤 잘못된 구현에서 실패하는 테스트인지** 설명해야 합니다.

<a id="m14"></a>
## M14. 2주 mini-capstone: 단일 가설의 재현·ablation·실패 한계

### 범위 계약

M01–M13에서 이미 만든 실험 중 하나만 고릅니다. 새 agent framework·프런트엔드·DB·cloud account를 동시에 도입하지 않습니다. 최소 결과물은 단일 가설, baseline, 한 변인의 ablation, 한 개의 실패 주입, 독립 검증, 한계가 담긴 작은 연구 패키지입니다.

예시는 다음 중 하나입니다.

| 주제 | 사전 등록할 가설 | 허용되는 작은 결론 |
| --- | --- | --- |
| Retrieval | corpus revision mismatch가 고정 query set의 특정 문서 누락을 만든다 | 이 corpus·ranker·revision에서의 failure |
| Evaluation | 실패 sample 제외가 paired 비교의 분모를 바꾸고 점수를 왜곡한다 | 작은 synthetic evaluator의 집계 계약 |
| Numerics | 특정 mask mutation이 attention oracle와 불일치한다 | 작은 입력·dtype·tolerance의 정확성 |
| Agent mock | 반복 observation이 있어도 최대 step에서 명시적으로 끝난다 | local 상태기계의 bounded 종료 |
| Model extension | 선택한 모델·prompt에서 근거 위치에 따라 paired 차이가 난다 | 실제 실행한 모델/질문 분포의 관측 |

CPU toy를 선택해도 충분합니다. 대신 실제 LLM, GPU kernel, 원 논문 benchmark의 개선을 입증했다고 포장하지 않습니다. 실제 모델 확장은 이미 실행 권한·비용·데이터 조건이 마련된 경우만 선택합니다. 2주라는 일정 때문에 secret/privacy/독립 oracle를 생략하지 않습니다.

### 24시간 작업 예산

| 작업 | 시간 | 종료 조건 |
| --- | ---: | --- |
| 가설·비교·중단 조건 고정 | 3 | 결과를 보기 전 main metric과 반증 조건 기록 |
| 기존 harness 정리 | 5 | 한 명령·고정 input·version manifest |
| baseline·ablation 실행 | 6 | 모든 시도와 query별 결과 보존 |
| 실패 주입·독립 검증 | 4 | expected failure와 복구 확인 |
| 보고서·동료 재현 | 6 | 제한된 결론과 재실행 evidence |

새 실험 matrix가 커지면 변수 수를 줄입니다. 결과가 가설과 다를 때 baseline을 교체하거나 test를 dev로 바꾸지 않습니다. compute budget이 소진되면 부분 실행을 남기고 미실행 cell을 0점 또는 성공으로 채우지 않습니다.

### 필수 연구 패키지

[실험 보고서](../templates/experiment-report.md)에 다음을 작성합니다.

1. **원문 연결:** P번호, 실제 읽은 revision, 원 주장과 이번 축소 가설의 차이.
2. **환경:** repo/source SHA, Python/library/model/tokenizer revision, hardware/dtype, seed 정책, 데이터 hash, 사용 권한. 알 수 없는 provider 내부 구성은 unknown.
3. **실험 원장:** run/query/attempt ID, baseline/variant, 변경 변수, 전체 실패, 비용/지연 또는 미측정, 취소/timeout 처리.
4. **독립 증거:** 손 계산/정답기/수동 label, assertion, mutation에서 의도한 실패, 복구 결과.
5. **결과와 한계:** 절대값·차이·불확실성, 가장 강한 반례, 일반화할 수 없는 조건, 추가 실험 우선순위.
6. **재현 안내:** 새 환경에서 준비할 것, 정확한 cwd/명령, 생성 파일, 예상 실행 규모, 안전한 종료/보존 범위.

동료는 설명을 먼저 듣지 않고 같은 입력으로 결과를 확인합니다. 환경 설치 시간과 모델 다운로드를 실행 시간에서 숨기지 않습니다. 실행이 불가능한 환경이면 재현 가능한 부분과 불가능한 부분을 나눠 보고하고 완료 범위를 축소합니다.

### 통과와 연구 윤리

[공통 평가](../assessment.md)의 정확성·메커니즘/소스·실험/반증·운영/재현성 각 25점 규칙을 적용합니다. 높은 정확도가 데이터 leakage, 무단 데이터 전송, 미실행 결과, 관측하지 않은 GPU speedup, 제품 권한 우회를 상쇄하지 못합니다. null/negative result도 방법과 증거가 명확하면 유효한 결과입니다.

논문 표의 수치를 자신의 측정 열에 복사하지 않습니다. 예시/예상값/실제값을 분리합니다. 모델이 만든 코드·설명·평가 label도 검토 대상이며 저자·도구·데이터 출처를 남깁니다. 공식 benchmark 일부만 사용했다면 subset 선택 기준과 빠진 항목을 공개합니다.

## 선택 확장: 제품 통합은 별도 일정

mini-capstone을 끝낸 뒤 제품형 lab을 원하면 별도 범위·예산을 정합니다. 아래 연결은 설계 후보이며 이 장이 완성 앱이나 통합 환경을 제공하지는 않습니다.

- [PostgreSQL](../../../databases/postgresql/README.md): corpus/annotation/version 원장과 transaction.
- [Kafka](../../../streaming/kafka/README.md): index 갱신 event, 중복·재처리·삭제 반영 계약.
- [ClickHouse](../../../databases/clickhouse/README.md): query/attempt별 품질·지연·비용 분석과 집계 편향.
- [Supabase](../../../platforms/supabase/README.md): 사용자별 문서 접근, 실제 Auth/API/RLS 음성 검사.
- [Sentry](../../../observability/sentry/README.md): prompt·문서·credential을 유출하지 않는 실패 관측.

다섯 제품은 필수 선수 과정도 필수 full stack도 아닙니다. 권한 있는 문서만 retrieval/generation에 들어가는지, 삭제·버전 변경이 언제 반영되는지, 관측 로그가 근거를 노출하지 않는지를 별도의 시스템 계약으로 검증합니다. 제품 통합의 안정성을 논문 성능 재현과 혼동하지 않는 것이 마지막 학습 목표입니다.
