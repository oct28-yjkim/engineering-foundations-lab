# 01. Transformer와 scaling: 수식에서 실험 계약까지

[트랙 소개](../README.md) · [논문 목록](../papers.md) · [실행 환경과 CPU 실습](../labs/README.md) · [평가 기준](../assessment.md)

이 문서는 M01–M02, 총 4주 과정이다. 논문을 읽은 뒤 구현의 invariant를 검증하고, 원래 결과가 성립했던 조건과 자신의 실험 조건을 비교한다. 아래 숫자형 실습 기준은 **이 Lab의 교육용 기준**이지 원논문의 성능 수치가 아니다.

원문 확인일: 2026-10-04. 읽기 기준은 P01 arXiv v7, P02 v4, P03 v1이며, 아래 원문 링크의 버전을 실험 기록에 적는다. GPT-3 논문은 연구 대상이지 현재 특정 API 사용 안내가 아니다.

## 시작 전 진단

- 행렬 곱의 shape, chain rule, softmax와 cross-entropy를 종이에 계산한다.
- train/validation/test의 역할과 tokenizer 학습 데이터의 누출 가능성을 설명한다.
- 파라미터 수, FLOPs, GPU 메모리, wall-clock time이 서로 다른 예산임을 설명한다.
- 같은 seed라도 장치·kernel·연산 순서가 달라지면 완전 동일 결과가 아닐 수 있음을 기록한다.

모르는 항목이 있으면 작은 벡터·행렬 예제로 먼저 보완한다. 저장소의 공통 데이터베이스 기초 과정이 이 수학·Python 선수지식을 대신하지는 않는다.

<a id="m01"></a>
## M01 · Attention과 in-context learning — 1–2주

### 읽을 질문과 핵심 원리

[P01 원문](https://arxiv.org/html/1706.03762v7)의 attention, masking, encoder/decoder 구성을 읽는다. 길이 `n`, key 차원 `d_k`, value 차원 `d_v`에 대해 다음 shape를 직접 대조한다.

```text
Q, K: [n, d_k]       V: [n, d_v]
scores = Q K^T / sqrt(d_k) + mask      # [n, n]
A = row_softmax(scores)               # [n, n]
output = A V                         # [n, d_v]
```

독립·평균 0·분산 1인 성분을 가정하면 dot product 분산은 `d_k`이므로 scaling은 softmax 포화를 완화한다. decoder의 causal mask는 미래 key의 score를 softmax **전**에 제외한다. 원 Transformer는 encoder-decoder이며, 오늘의 decoder-only 모델 전체를 동일한 구조로 취급하지 않는다. Multi-head는 서로 다른 projection을 결합한다.

[P02 원문](https://arxiv.org/html/2005.14165v4)은 task 예시를 입력 문맥에 넣고, 평가 시 gradient update 없이 few-shot 성능을 측정한다. 이는 fine-tuning과 다른 실험이다. 논문의 오염 분석도 함께 읽고, 사전학습 데이터와 test의 중복이 관측된 성능에 어떤 대안 설명을 만드는지 적는다.

### 1주차: CPU 수치 검증

저장소 루트에서 제공되는 축소 모형을 실행한다. 코드가 포함한 검사는 [실습 문서](../labs/README.md)를 기준으로 확인하며, 아래 추가 실험은 학습자가 별도 작성한다.

```powershell
python ai/llm-paper-lab/labs/lab.py --lab attention
```

1. 입력·출력과 mask의 shape를 주석으로 복원하고, softmax 행 합과 causal 영역을 독립 계산한다.
2. 미래 token의 K/V를 크게 바꾼 뒤 이전 위치 출력의 불변성을 검사한다. 비교 허용오차는 float64 작은 배열 기준 `1e-10`처럼 실행 전에 정한다.
3. mask를 제거한 대조군에서는 같은 교란이 출력에 영향을 주는 입력을 만든다. 단순히 모든 V가 같은 fixture로 비교하면 잘못된 mask도 통과할 수 있다.
4. `exp(score-max(score))`와 naive exponential을 큰 score에서 비교한다. overflow, 전부 masked인 행, 길이 1을 정상 입력과 구분한다. 전부 masked인 행의 의미는 명시적으로 정의하거나 오류로 거부한다.
5. 추가 구현으로 차원별 score 분산과 attention entropy를 측정한다. seed별 분포를 보고, 단일 attention heatmap을 모델의 인과적 설명으로 부르지 않는다.

제공 코드는 attention 메커니즘의 일부를 보는 CPU 모형이다. Transformer 학습, tokenizer, optimizer, 번역 품질, GPT-3 few-shot 학습은 제공하지 않는다.

### 2주차: 선택적 실제 모델 비교 설계

모델·데이터의 라이선스와 저장 위치, 다운로드 크기, 자원 상한을 먼저 정한 후 학습자가 별도 환경에서 구현한다. GPU/API 요청이나 모델 다운로드가 이 저장소 명령으로 자동 실행되지는 않는다.

- 하나의 고정 모델·tokenizer revision으로 zero-shot/one-shot/few-shot을 비교한다. 같은 모델의 가중치 hash가 실행 전후 같은지 확인한다.
- 직접 만든 합성 분류 과제에 서로 겹치지 않는 demonstration pool과 test를 둔다. seed는 예시 **선택**, 예시 **순서**, 생성 **샘플링**을 따로 둔다.
- 올바른 예시, label을 섞은 예시, 과제와 무관한 예시를 비교한다. label leakage와 단순 format 모방을 분리할 수 있는 test를 만든다.
- context budget과 실제 입력 token 수를 기록한다. few-shot의 비용 증가를 숨기기 위해 test 질문을 잘라내지 않는다.
- exact match 또는 분류 정확도, 파싱 실패, abstention, 입력·출력 token, latency를 모두 저장한다. JSON 모양이 맞는 것을 정답으로 세지 않는다.
- 같은 test item 단위 paired 비교와 bootstrap 구간을 사용한다. 여러 예시 순서의 반복값을 서로 독립 test item처럼 부풀리지 않는다.

### 반례와 통과 기준

- **통과:** causal 교란 검사가 통과하고, 고의 mask 제거가 검사를 실패시키며, zero-shot/few-shot을 동일 split에서 비교하는 설계가 있다.
- **실패:** 작은 attention 함수 PASS를 Transformer/GPT-3 재현이라고 보고하거나, prompt에 test 정답을 넣거나, 예시 선택에 test 성능을 사용한다.
- 결과가 “few-shot이 개선되지 않음”이어도 통제·오차 분석이 완전하면 통과한다. 성능 향상 자체가 합격 조건은 아니다.

제출물: shape 추적표, 불변성·반례 테스트, 고정 prompt manifest, item별 원시 결과, 오염 점검, 원논문과 다른 조건 5개 이상.

<a id="m02"></a>
## M02 · Compute-optimal scaling — 3–4주

### 읽을 질문과 핵심 원리

[P03 원문](https://arxiv.org/html/2203.15556v1)의 IsoFLOP 비교와 parametric loss fitting을 읽는다. 파라미터 수 `N`, 학습 토큰 수 `D`, 계산 예산 `C`에 대해 다음은 논문에서 사용하는 근사 모델이다.

```text
C ≈ 6 N D
L_hat(N, D) = E + A / N^alpha + B / D^beta
```

`6ND`는 모든 architecture·sequence length의 정확한 비용식이 아니다. 논문은 별도 FLOP 산정도 설명한다. 고정 예산에서 모델을 크게 하면 볼 수 있는 토큰 수가 줄어드는 trade-off를 분석한다. 이 결과를 “모든 모델은 언제나 고정 토큰/파라미터 비율이면 최적”이라는 규칙으로 사용하지 않는다.

### 3주차: 손으로 최적점과 식별성 검증

제공 실행기에 scaling fit 기능은 없다. 다음은 학습자가 작성하는 소규모 수학 실습이다.

1. `D=C/(6N)`을 loss 식에 대입해 미분한다. 최적점에서 `alpha*A*N^-alpha = beta*B*D^-beta`인지 확인한다.
2. `N_opt ∝ C^(beta/(alpha+beta))`, `D_opt ∝ C^(alpha/(alpha+beta))`를 유도한다. 지수 두 개가 같은 조건을 설명한다.
3. 교육용 계수를 직접 정하고 양의 loss를 생성한 뒤 noise를 더한다. 생성 계수, noise seed, 탐색 구간을 함께 저장한다. 이 데이터는 **논문의 실제 학습 관측값이 아니다**.
4. 일부 예산 전체를 hold-out으로 남겨 fitting 결과를 예측 검증한다. 높은 fitting R²만으로 extrapolation을 정당화하지 않는다.
5. 좁은 N 범위, 큰 noise, 고정 D만 있는 데이터에서 계수 식별이 어떻게 무너지는지 비교한다. bootstrap을 할 때 한 학습 run의 여러 checkpoint를 독립 run으로 처리하지 않는다.

### 4주차: 선택적 GPU 축소 재현 설계

이 저장소는 pretraining trainer나 학습 corpus를 제공하지 않는다. 학습자가 구현할 때도 첫 목표는 원논문 수치 복원이 아니라 **고정 계산 예산의 비교가 공정한지** 확인하는 것이다.

| 항목 | 고정·기록할 내용 | 의도적 비교 |
| --- | --- | --- |
| 데이터 | tokenizer revision, 동일 train 분포와 hold-out, 중복 처리 | unique token과 반복 노출 token 분리 |
| 모델 | 동일 계열, 실제 parameter count, context length | 작은 N/많은 D와 큰 N/적은 D |
| 최적화 | token batch, optimizer, precision, clipping | 동일 schedule 적용과 budget별 schedule 보정 |
| 계산 | FLOP 추정식, 실제 token, 장치, elapsed time | IsoFLOP와 동일 wall-clock 비교를 별도 표로 |
| 평가 | 동일 hold-out token, loss 산식, checkpoints | final loss와 best validation checkpoint 분리 |

- 먼저 자원 상한 내 pilot 1개로 비용을 측정하고 본 실험 수를 확정한다. 미완료 run을 저성능 결과처럼 쓰지 않는다.
- 최소 여러 N과 D 조합을 두되 모델 크기만 바꾸고 learning-rate schedule이 중간에 잘리는 교란을 분석한다.
- train compute 최적화에 inference lifetime 비용을 추가하면 다른 목적함수임을 명시한다. 이것은 P03의 원래 결론을 그대로 재현하는 것이 아니라 별도 공학 질문이다.
- data quality, 중복, architecture, optimizer가 달라진 결과는 원논문 계수를 반증한 것으로 표현하지 않는다.

### 반례와 통과 기준

- **통과:** 근사 FLOP 식의 한계를 설명하고, toy fitting의 생성값·관측값·예측값을 분리하며, hold-out 예산에서 실패한 예측도 보고한다.
- **실패:** 합성 데이터를 fit한 결과를 실증 scaling law라 부르거나, 같은 wall-clock을 같은 FLOPs로 가정하거나, test loss로 학습 예산을 반복 선택한다.
- GPU를 쓰지 않으면 결과의 범위를 `수학·실험설계 검증`으로 제출한다. 실행하지 않은 GPU 결과 칸은 수치 대신 `미실행`으로 남긴다.

제출물: 최적점 유도, 비용 모델, 실험 행렬, raw run manifest, fit 잔차·hold-out 결과, downstream 품질과 loss의 차이, 총 소요 자원 상한.

## 다음 연결

[적응·정렬 과정](02-adaptation-alignment.md)에서는 파라미터 예산과 목적함수를, [효율적 추론 과정](03-efficient-inference.md)에서는 FLOPs 외의 메모리·IO·서빙 조건을 분해한다.
