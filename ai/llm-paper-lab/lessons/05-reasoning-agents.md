# M10–M11. 추론 전략·도구 사용을 검증 가능한 시스템으로 만들기

[트랙 안내](../README.md) · [논문 지도](../papers.md) · [실습 범위](../labs/README.md) · [평가](../assessment.md)

각 모듈은 2주·24시간입니다. 이 장의 모델 비교와 agent harness는 **학습자가 구현하는 확장**이며 완성된 agent나 API 호출 코드를 제공한다는 뜻이 아닙니다. 기본 과제는 synthetic 데이터와 부작용 없는 local mock으로 설계합니다. 모델/도구 사용 권한과 비용 한도가 준비되기 전에는 외부 요청을 실행하지 않습니다.

<a id="m10"></a>
## M10. Chain-of-Thought와 Self-Consistency: 정답률·집계·계산 예산

### 논문에서 제품 가설까지

[P14 Chain-of-Thought Prompting](https://arxiv.org/abs/2201.11903)은 중간 풀이가 포함된 예시를 prompt에 주는 방법을 연구합니다. [P15 Self-Consistency](https://arxiv.org/abs/2203.11171)는 다양한 출력을 sampling하고 답변을 집계하는 decoding 접근입니다. 두 논문의 결과는 특정 모델·데이터·prompt 조건의 관측이며 모든 모델의 성능 향상 보장이 아닙니다.

핵심 질문은 “풀이를 길게 출력했는가?”가 아니라 **같은 문제 분포와 자원 예산에서 검증 가능한 정답이 늘었는가?**입니다. 공개 생성 풀이·설명·action trace는 관측 가능한 출력일 뿐 실제 내부 추론 과정의 충실한 기록이라고 취급하지 않습니다. 비공개 chain-of-thought 추출을 요구하거나 API가 제공하지 않는 내부 추론을 측정했다고 쓰지 않습니다. 모델이 지원하는 공개 답변·짧은 근거·도구 결과로 평가합니다.

### 먼저 손으로 깨뜨리는 다수결

정규화된 최종 답을 `a`, sample을 `j=1..n`이라 하면 학습용 집계는 `count(a)=sum_j 1[normalize(output_j)=a]`의 최댓값을 고릅니다. parser 실패, 동률, 정답 형식 위반을 사전에 정의합니다. 다수결 신뢰도 `max count / n`은 독립적인 정답 확률이 아닙니다.

다음은 학습자가 작성할 집계기 unit test의 최소 fixture입니다. 모델이 만든 결과가 아니라 **직접 정한 모형 입력**입니다.

| raw 최종 답 | oracle | 확인할 계약 |
| --- | --- | --- |
| `42`, `42.0`, `42` | 숫자형 정답 42 | task가 허용한 숫자 정규화 후 집계 |
| `41`, `41`, `42` | 정답 42 | 다수결이 확신 있게 틀릴 수 있음 |
| `A`, `B` | 동률 정책은 abstain | 임의 tie-breaking을 숨기지 않음 |
| 유효 JSON, 잘린 JSON, 설명만 있는 출력 | parser 실패는 별도 상태 | 실패 sample을 조용히 삭제하지 않음 |
| 같은 잘못된 답을 5번 복제 | 독립 시행 아님 | sample 수와 유효 다양성의 분리 |

문제에 따라 `1/2`와 `0.5`는 같지만 `01`과 `1`이라는 식별자는 다릅니다. 정규화 규칙을 dev에서 정하고 test 정답을 보고 고치지 않습니다. 가능한 정답 집합이 여러 개인 경우 하나의 문자열만 정답으로 두는 평가 오류부터 해결합니다.

### 학습자 모델 실험

직접 작성한 짧은 산술/기호 조작 문제를 entity와 숫자 seed 기준으로 분리합니다. 정답은 별도의 명시적 solver로 만들고 solver를 손 계산 사례로 검사합니다. 생성 모델 자신에게 정답을 만들고 채점까지 맡기지 않습니다.

1. 직접 답변 1회, 공개 풀이 예시를 준 답변 1회, 여러 sample의 정규화 집계를 비교합니다. 예시와 test의 숫자/템플릿 근접 중복을 확인합니다.
2. 최초 실험은 같은 모델/revision·input·출력 형식을 사용합니다. sample 수를 늘리는 조건에는 총 token/요청/지연 예산을 별도 기록합니다.
3. “같은 sample 수”와 “같은 총 계산/비용 예산” 비교를 따로 보고합니다. provider가 compute나 숨은 token을 공개하지 않으면 관측 가능한 사용량만 비교하고 정확한 동일 compute라고 부르지 않습니다.
4. greedy 1회와 stochastic 다회 비교에서 temperature·top-p·seed 지원 여부가 바뀌는 사실을 명시합니다. seed 고정이 분산 서비스의 완전한 결정성을 보장하지 않습니다.
5. 독립 평가기는 정답률, parser 실패, abstention, query별 변동, 비용·지연을 산출합니다. 비용 때문에 timeout된 시도까지 원장에서 보존합니다.

### Ablation·반증·통과

sample 수, prompt 예시 수, 풀이 예시 정확성, 집계 정규화 중 하나만 먼저 바꿉니다. 잘못된 풀이 예시, irrelevant 예시, 단위가 다른 답, correlated wrong majority를 주입합니다. sample별 결과를 고른 뒤 좋은 것만 묶는 방식은 self-consistency 평가가 아닙니다.

1주차에는 논문 비교·정답 solver·집계 test에 12시간을 쓰고, 2주차에는 사전 등록한 bounded 실험·오류 분류·paired 통계에 12시간을 씁니다. 실제 모델을 실행하지 않았다면 집계 계약 검증까지만 통과했다고 표시합니다. “답변 수를 늘리면 무조건 좋아진다”는 가설을 기각할 수 있는 데이터를 제출하는 것이 핵심입니다.

최소 산출물: 두 논문의 다른 개입 위치, 독립 정답기, parser 단위 테스트, query별 전체 시도 원장, 동률/실패 정책, 동일 예산 비교 설계, 원 논문과의 차이. 공개 풀이의 자연스러움을 정답률이나 내부 reasoning의 신뢰도 대신 사용하면 통과하지 못합니다.

<a id="m11"></a>
## M11. ReAct와 Toolformer: inference 제어와 tool 학습의 차이

### 서로 다른 연구 질문

[P16 ReAct](https://arxiv.org/abs/2210.03629)는 설명·행동·환경 관측을 교차하는 접근을 다룹니다. [P17 Toolformer](https://arxiv.org/abs/2302.04761)는 API 사용 예시를 생성하고 유용성을 걸러 모델 학습에 사용하는 접근입니다. 전자는 단순히 도구 수가 많다는 뜻이 아니며, 후자는 현대 function-calling API나 수작업 router를 사용하는 것과 같지 않습니다.

[Toolformer 방법 본문](https://arxiv.org/html/2302.04761v1)을 읽고 후보 생성 → 안전한 실행 → 후속 token loss 비교 → 필터 → 학습을 구별합니다. loss 감소는 학습 데이터 필터의 신호이며 도구의 보안·정확성·업무 효용을 자동 증명하지 않습니다. 소형 fixture의 수치 계산만 구현했다면 모델 학습을 재현했다고 부르지 않습니다.

### 외부 행동보다 먼저 제어 계약

학습자가 구현할 local harness에는 `query_id`, `step`, `action_id`, `tool`, `arguments`, `observation`, `status`를 두고 다음 상태를 명시합니다: 입력 수신 → 요청 검증 → 허용 도구 실행 → 관측 기록 → 다음 행동 또는 종료. model 출력은 실행 명령이 아니라 **검증 전 요청**입니다.

도구는 합성 문서를 검색하는 read-only 함수와 제한된 숫자 연산기로 시작합니다. 숫자 연산은 검증된 숫자와 allowlist 연산자만 받고 `eval`/shell/임의 Python 실행을 사용하지 않습니다. 허용하지 않은 URL·파일경로·tool 이름은 실행 전에 거부합니다. 실메일·결제·운영 DB·사용자 파일 변경 도구는 기본 실험에서 제외합니다.

각 실행에 최대 step·도구 호출 수·wall time·출력 bytes·재시도 횟수를 둡니다. local mock이거나 무과금 fixture여도 예산 초과 동작을 테스트합니다. 모델 설명에 “안전하다”라고 적혀 있는 것은 권한 검사를 대신하지 못합니다.

### A. ReAct에서 영감을 받은 local 실험

초기에는 scripted policy를 사용해 상태기계가 예상대로 실패/종료하는지 확인합니다. scripted 성공은 모델 agent 성능 증거가 아닙니다. 이후 허가된 모델 adapter를 학습자가 추가하면 no-tool, action-only, observation을 사용하는 agent를 같은 과제/예산으로 비교합니다. 모델에서 제공되는 공개 설명만 기록하며 숨은 reasoning 접근은 가정하지 않습니다.

독립 oracle는 정답 문서 ID/값, 실제 도구 실행 원장, 허용된 resource 목록, 종료 조건입니다. 최종 답이 맞아도 허용되지 않은 도구를 호출했으면 보안 실패입니다. 설명상 실행했다는 주장과 실제 executor의 기록을 따로 비교합니다.

| 실패 주입 | 기대하는 제어 동작 | 확인하는 증거 |
| --- | --- | --- |
| tool timeout/빈 결과 | 제한 재시도 또는 명시적 실패 | 시도 수와 종료 상태 |
| 문서에 도구 호출을 강요하는 문구 | 문서는 비신뢰 데이터로 유지 | 허용하지 않은 action 실행 0회 |
| schema가 틀린 arguments | executor에 도달하기 전 거부 | 검증 오류와 실행 원장 |
| 오래된 observation 재전송 | provenance/version을 확인 | query/action ID 연결 |
| 반복되는 같은 검색 | step 한도에서 종료 | 성공처럼 포장하지 않은 budget exhaustion |
| synthetic write mock의 응답 유실 | 같은 action ID로 중복 효과 방지 | 독립 상태 version/적용 횟수 |

마지막 항목은 **mock state만** 바꿉니다. idempotency key 존재만으로 충분하지 않고 key와 payload 일치, 상태 변경과 원장의 atomicity, retry 결과의 의미를 정의합니다. 생성 agent에 임의 실행 권한을 주는 실험은 하지 않습니다.

### B. Toolformer의 loss 필터를 손으로 검증하기

학습자에게 주어진 synthetic loss를 `L_no_call`, `L_call_without_result`, `L_with_result`로 둡니다. 원문의 비교 구조를 작은 모형으로 옮겨 `delta=min(L_no_call,L_call_without_result)-L_with_result`가 사전 정의 threshold 이상인지 판정합니다. `2.0,1.8,1.2`, threshold `0.5`이면 keep, `2.0,1.1,1.2`이면 discard입니다. 후자는 API 이름/인자만으로 이미 주어진 정보의 효과를 비교하는 이유를 보여 줍니다.

이는 **실제 token probability를 측정하지 않은 손 계산 fixture**입니다. 학습 확장을 하려면 원문에 맞는 loss 가중치·token 위치·모델 likelihood 접근·후보 생성·데이터 filtering을 구현해야 합니다. loss를 제공하지 않는 API에 이 측정을 했다고 주장하지 않습니다. 학습 corpus, 도구 결과, 평가 문제 사이의 answer leakage와 미래 정보 유입을 별도 감사합니다.

### 2주 범위와 통과

1주차: 논문 차이·허용 도구 계약·scripted harness·독립 원장. 2주차: 실패 주입·bounded 모델 adapter 실험 또는 미실행 설계·loss fixture·리뷰. 수백만 API 호출을 만들거나 Toolformer 전체 학습을 24시간 과제로 포함하지 않습니다.

통과 증거는 상태기계, 예산 제한, 최소 4개 음성 테스트, 실제 실행과 모델 주장 대조, loss 손 계산, 원 논문 대비 축소 범위입니다. task success, unauthorized action, loop/timeout, tool error, 비용을 따로 보고합니다. 재현되지 않은 성능 수치와 사람이 읽기 쉬운 trace를 “검증된 내부 사고”로 바꾸어 설명하지 않습니다.

Sentry는 비밀 제거 후 오류/trace를 수집하는 선택 확장이고, Supabase의 RLS는 retrieval/tool backend 권한의 선택 구현입니다. 문서의 tenant tag나 agent prompt가 DB 권한을 대신하지 않습니다. Kafka·PostgreSQL을 붙이기 전에 local mock에서 command/observation 계약부터 검증합니다.
