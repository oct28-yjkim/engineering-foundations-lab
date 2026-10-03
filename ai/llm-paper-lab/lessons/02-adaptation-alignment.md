# 02. 적응과 정렬: 무엇을 업데이트하고 무엇을 최적화하는가

[트랙 소개](../README.md) · [논문 목록](../papers.md) · [실행 환경과 CPU 실습](../labs/README.md) · [평가 기준](../assessment.md)

M03–M05, 총 6주 과정이다. 먼저 행렬 업데이트와 목적함수의 correctness를 검증한 후에 실제 언어모델 학습으로 확장한다. 제공 CPU 코드는 원논문 trainer가 아니며, GPU 학습과 인간 평가 데이터 수집은 학습자가 별도로 구현해야 한다.

원문 확인일: 2026-10-04. 읽기 기준은 P04 arXiv v2, P05 v1, P06 v1, P07 v3이다. 본문의 통과 기준과 소규모 실험은 이 Lab의 교육용 설계이며 논문의 benchmark 수치가 아니다.

## 공통 실험 계약

- 모델·tokenizer·dataset revision과 허용 라이선스를 고정한다. 사용자 대화나 사내 원문을 기본 학습 데이터로 사용하지 않는다.
- split은 prompt·문서·사용자 그룹 등 누출 단위로 나눈다. 같은 prompt의 chosen/rejected를 서로 다른 split으로 보내지 않는다.
- base model과 adapter, trainable parameter 수, optimizer state, activation, 임시 buffer의 메모리를 구분한다.
- 실험 전 GPU 메모리·시간·최대 step 상한을 적는다. 이 저장소는 모델 다운로드, API 결제, cloud GPU 생성을 자동 실행하지 않는다.
- 학습 loss, validation loss, 인간 선호, task correctness, 거절·안전성은 서로 다른 측정값으로 기록한다.

<a id="m03"></a>
## M03 · LoRA와 QLoRA — 5–6주

### 원리와 원문 경계

[P04 LoRA](https://arxiv.org/html/2106.09685v2)는 frozen weight `W0`에 학습 가능한 저랭크 업데이트를 더한다.

```text
W0: [d_out, d_in]
A:  [r, d_in]           B: [d_out, r]
W_effective = W0 + (alpha/r) B A
y = W0 x + (alpha/r) B (A x)
trainable parameters = r (d_in + d_out)   # bias 등은 제외
```

base weight 자체가 저랭크라는 주장이 아니다. 원문의 초기화는 A를 random, B를 zero로 두어 시작 시 업데이트를 0으로 만든다. 같은 arithmetic 조건에서 merge된 weight와 두 경로의 합은 같은 함수다.

[P05 QLoRA](https://arxiv.org/html/2305.14314v1)는 양자화된 frozen base와 학습 가능한 adapter를 결합한다. NF4 저장, quantization constant의 추가 양자화, memory spike를 다루는 paged optimizer가 핵심이다. 저장 dtype과 matmul 계산 dtype이 다르므로 “모든 학습을 4-bit로 한다”는 설명은 틀리다. 일반적인 int4 반올림은 NF4 구현이 아니다.

### 5주차: CPU 저랭크 모형과 독립 검사

```powershell
python ai/llm-paper-lab/labs/lab.py --lab lora
```

제공 검사는 작은 선형층의 merge 동치, parameter 수, B=0 초기 상태의 A/B finite-difference gradient다. optimizer step은 제공하지 않는다. [실습 문서](../labs/README.md)를 확인하고 아래 학습·양자화 비교는 학습자가 확장한다.

1. base weight와 trainable 배열을 분리하고 한 step 전후 hash/값을 비교한다. adapter만 학습했는지 실제로 확인한다.
2. 작은 입력에서 분기형 forward와 merge형 forward를 독립 계산한다. tolerance를 실행 전에 정하고, merge를 두 번 적용하는 오류를 고의 주입해 테스트가 잡는지 확인한다.
3. target delta가 rank 1인 합성 회귀와 더 높은 rank인 합성 회귀를 별도 생성한다. 후자의 잔차를 rank 1 구현 버그와 혼동하지 않는다.
4. rank만 비교할 때 `alpha/r`가 바뀌는 교란을 기록한다. 고정 alpha와 고정 alpha/r 두 실험의 질문은 다르다.
5. A와 B를 모두 zero로 두는 대조군을 만들고, chain rule로 첫 gradient가 왜 사라지는지 설명한다. 모든 실험이 이 초기화를 기본으로 쓰지는 않는다.
6. 추가 양자화 모형을 작성한다면 scale·codebook·metadata까지 바이트 수를 세고, NF4가 아니면 파일명과 결과에 `uniform toy quantization`으로 표시한다.

### 6주차: 선택적 GPU 확장

학습자 구현 대상이다. 실제 kernel 설치·학습 명령은 제공하지 않는다.

| 비교군 | 바꾸는 것 | 비교를 위해 고정할 것 |
| --- | --- | --- |
| Base → LoRA | adapter 학습 유무 | base/tokenizer, task test, decode 조건 |
| LoRA rank sweep | rank 또는 scaling 중 하나 | target layers, token budget, seeds |
| BF16 LoRA → QLoRA | base 저장 방식 | dataset, adapter targets, 학습·평가 token |
| QLoRA ablation | NF4·double quantization·optimizer 하나 | 나머지 quantization와 학습 설정 |

full fine-tuning이 자원 내에서 가능할 때만 baseline으로 넣는다. 실행 불가능하면 `미실행`이며, 문헌 수치를 같은 그래프의 자체 측정값으로 혼합하지 않는다. peak **allocated/reserved** GPU memory, host memory, step time, throughput, validation task 품질을 기록한다. optimizer offload가 OOM을 줄여도 page 이동 비용은 별도 측정한다.

### 반례·통과·실패

- **통과:** frozen base와 merge 동치가 검증되고, rank·scaling·target layer를 구분하며, 양자화 storage와 compute dtype을 따로 설명한다.
- **실패:** parameter 감소율을 총 VRAM 감소율로 사용하거나, toy 행렬의 오차 감소를 실제 모델 품질 보존이라고 보고한다.
- GPU에서는 NaN, OOM, adapter 미연결, trainable base 유출, 잘못된 tokenizer template를 실패로 보존한다. 실패한 run을 조용히 제거하지 않는다.

제출물: parameter/memory 장부, merge 테스트, 합성 target 생성식, rank ablation, 실제 실행 여부가 적힌 GPU 확장 계획.

<a id="m04"></a>
## M04 · SFT, reward model, RLHF — 7–8주

### 원리와 목적함수

[P06 InstructGPT](https://arxiv.org/html/2203.02155v1)는 demonstration 기반 SFT, 출력 선호 비교로 학습한 reward model, PPO 기반 policy 개선을 구분한다. 원문은 특정 prompt·평가자 분포의 선호를 다루므로 보편적 인간 가치나 사실 정확성의 완성을 증명한 것이 아니다. pretraining mix가 있는 설정과 없는 설정도 구분해서 읽는다.

다음은 학습용 표기이며 원문 전체 PPO 구현을 대체하지 않는다. `x`는 prompt, `y_w/y_l`은 선호/비선호 completion이다.

```text
SFT:       minimize - E[sum_t log pi_theta(y_t | x, y_<t)]
RM pair:   minimize - E[log sigmoid(r_phi(x,y_w) - r_phi(x,y_l))]
RL target: maximize E[r_phi(x,y)] - beta * KL(pi_theta || pi_ref)
```

SFT의 token mask, RM의 comparison loss, RL의 sampling policy와 reference는 각각 다른 데이터 경로다. reward가 높아지는 것과 실제 목표를 잘 달성하는 것은 동치가 아니다.

### 7주차: 목적함수·데이터 분리 실습

이 모듈의 SFT/RM/PPO trainer는 제공하지 않는다. 다음은 작은 수치·데이터 검증 과제다.

1. 합성 prompt 20개와 각 completion 후보 3개를 만든다. `정답`, `문장 길이`, `근거 유무`를 별도 label로 둔다. 숫자는 교육용 fixture 크기다.
2. 같은 prompt의 비교쌍을 모두 한 split에 둔다. 비교쌍 수를 독립 prompt 수로 세면 안 되는 이유를 적는다.
3. 길이만 reward로 쓰는 고의로 잘못된 RM을 만든다. 긴 오답이 짧은 정답보다 높은 점수를 받는 반례를 만들어 offline scorer가 실제 목표를 대신할 수 없음을 보인다.
4. 두 보상에 같은 상수를 더해도 pairwise 확률이 같은지 확인한다. RM 절대 점수 5와 다른 RM의 절대 점수 5를 직접 비교하지 않는다.
5. label 순서를 뒤집은 fixture, tie, 평가자 불일치, parsing 실패를 정상 pair와 구분해 저장한다. tie를 임의 chosen으로 강제하지 않는다.
6. loss를 계산할 때 prompt와 padding의 token을 어떻게 제외할지 명시한다. 이 마스킹 계약과 데이터 schema를 별도 단위 테스트로 검증한다.

### 8주차: 선택적 실제 학습과 보상 악용 감사

- SFT only와 SFT+선호 학습을 같은 base, 같은 test, 명시한 학습 자원으로 비교한다. RM/PPO를 구현하지 않았으면 RLHF 재현으로 제출하지 않는다.
- PPO 확장은 rollout policy, old policy, reference policy, value model의 역할을 코드 위치까지 추적한다. PPO clipping과 reference KL 제약을 같은 것으로 취급하지 않는다.
- reward 증가에 대해 task correctness, 길이, 반복, 생성 다양성, 명시적 안전 테스트, 분포 밖 prompt 결과를 같이 본다.
- KL 계수·학습률·reward scale을 한 번에 바꾸지 않는다. KL이 커지는 run은 미리 정한 중단 기준에 따라 멈추고 원인을 기록한다.
- 평가자는 비교 모델을 모르게 하고 출력 순서를 무작위화한다. 합성 label만 사용했으면 인간 선호 평가로 부르지 않는다.
- 실제 사람의 평가를 수집할 경우 목적·보관·개인정보·보상 방침을 먼저 정한다. 기본 lab에는 외부 사람에게 연락하거나 데이터를 전송하는 과정이 없다.

### 통과 기준

SFT/RM/RL의 데이터·loss·reference 경계를 설명하고, 보상이 개선됐지만 정답률이 떨어지는 반례를 검출해야 한다. held-out prompt 분리나 실제 목표 평가 없이 train reward만 제시하면 실패한다. 원논문의 비공개 학습 데이터와 인력 평가 조건을 자신의 공개·합성 데이터로 대체한 한계를 명시한다.

제출물: 데이터 lineage, 목적함수 분해, leakage 검사, reward-hacking 반례, 평가자 지침 초안, 학습·평가 분포 차이 문서.

<a id="m05"></a>
## M05 · DPO의 유도와 구현 감사 — 9–10주

### 원리와 식

[P07 DPO](https://arxiv.org/html/2305.18290v3)는 KL 정규화된 정책 최적화의 reward-policy 관계를 이용해 선호 확률을 policy log-ratio로 표현한다. Bradley-Terry 형태와 reference가 전제이며, 별도 reward model/PPO loop를 학습하지 않는 것이 선호 label·reference가 필요 없다는 뜻은 아니다.

```text
z = beta * [log pi_theta(y_w|x) - log pi_ref(y_w|x)
          - log pi_theta(y_l|x) + log pi_ref(y_l|x)]
loss = -log sigmoid(z) = softplus(-z)
d loss / d z = sigmoid(z) - 1
```

completion log-probability는 조건부 token log-probability의 **합**이다. 평균으로 바꾸면 길이에 관한 다른 목적함수다. prompt/padding 마스킹, EOS 처리, truncation과 reference가 모두 이 값에 영향을 준다. beta는 목적함수의 계수이지 모든 학습 run에 동일한 empirical KL 상한을 보장하는 장치가 아니다.

### 9주차: CPU scalar loss 검증

```powershell
python ai/llm-paper-lab/labs/lab.py --lab dpo
```

제공 모형은 scalar 목적함수 검사다. 실제 LLM forward/backward나 인간 선호 개선을 실행하지 않는다. 아래는 독립 검산·확장 과제다.

1. policy와 reference log-probability가 같으면 `z=0`, `loss=log(2)`인지 확인한다.
2. 동일 reference에서 chosen의 policy 상대 log-probability만 늘릴 때 loss가 감소하는지 확인한다.
3. finite difference와 analytic gradient를 비교한다. 작은 float64 값에서 허용오차를 정하되, 극단값은 stable softplus가 NaN/overflow 없이 동작하는지 별도 검사한다.
4. chosen/rejected를 바꾼 오류, reference 항을 제거한 오류, beta 부호 오류를 각각 주입하고 무엇이 검출하는지 기록한다.
5. `log-prob 합`과 `길이 평균` 두 scorer를 길이가 다른 completion에 적용한다. 이는 DPO 변형의 효과 실험이지 동일 구현의 numerical 오차가 아니다.
6. 같은 prompt라도 tokenizer template·EOS 정책이 다른 reference log-prob cache를 거부하도록 cache manifest를 설계한다.

### 10주차: 선택적 GPU 확장과 반증

- 고정 SFT checkpoint에서 시작해 reference를 freeze하고, 같은 held-out prompt의 SFT baseline과 비교한다.
- beta sweep, label noise, chosen 길이 편향, reference 변경 중 하나씩 바꾼다. test set으로 beta를 고르지 않는다.
- train preference accuracy, held-out preference accuracy, reference 대비 log-ratio, 실제 generation task 정확도·길이·거절률을 분리한다.
- 같은 labeler/judge로 train label과 최종 평가를 모두 만들었다면 독립 검증이 아니라는 한계를 적는다. 사람이 검토한 오류 표본이나 독립 정답 과제를 추가한다.
- 대화 전체와 마지막 assistant 응답만 학습하는 설정은 다르다. 적용된 chat template, loss mask, truncation 뒤 chosen/rejected의 유효 token 수를 검증한다.

### 통과 기준

- **통과:** scalar loss의 경계값·gradient 검사가 있고, reference·token mask·length 처리를 명시한다. 성능이 개선되지 않아도 올바른 대조군과 실패 원인 분석이 있으면 통과한다.
- **실패:** DPO loss 감소를 진실성·무해성 보장으로 설명하거나, chosen과 rejected가 truncation 뒤 동일해진 pair를 조용히 학습하거나, reference에 gradient가 들어간 것을 놓친다.

제출물: 목적함수 유도, finite-difference 결과, 고의 오류 검출표, 데이터 편향 분석, 실제 학습 여부와 원논문 대비 변경점.
