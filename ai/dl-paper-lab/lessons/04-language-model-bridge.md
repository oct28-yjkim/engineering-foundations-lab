# 작은 언어모델에서 LLM으로 연결하기

[DL 과정](../curriculum.md) · [논문 DL04 DL11 DL12](../papers.md) · [기존 LLM M01](../../llm-paper-lab/lessons/01-transformers-scaling.md)

## 분류에서 다음 token 확률로

binary logistic의 손실을 vocabulary 분류로 넓히면 softmax cross entropy가 됩니다. 언어모델은 `p(x₁,…,x_T)=Πₜp(xₜ|x_<ₜ)`로 sequence 확률을 분해합니다. token embedding은 token ID를 연속 표현으로 연결하는 학습 parameter이며, pretrained embedding을 반드시 다운로드해야 한다는 뜻은 아닙니다. DL04의 신경 확률 언어모델은 이러한 표현과 확률 모델을 함께 학습하는 연결 고리로 읽습니다.

입력 [A,B,C], 정답 [B,C,D]의 위치를 표로 적습니다. 위치 t의 loss 계산에 정답 xₜ₊₁을 입력 문맥으로 넣지 않아야 합니다. 별도 sequence를 붙일 때 state/mask 경계, padding을 loss에 포함하는지, loss를 유효 token 수로 나누는지 확인합니다. label shift 오류는 모델이 작아도 치명적입니다.

## NLL perplexity 그리고 생성 품질

평균 token NLL이 자연로그 단위이면 perplexity는 `exp(NLL)`입니다. tokenizer·vocabulary·평가 문서·token 길이·mask가 같아야 해석 가능한 비교가 됩니다. perplexity 감소가 지시 수행·사실성·권한 준수 개선과 같은 뜻은 아닙니다. 이는 기존 LLM 과정에서 task 지표·검색·정렬 평가를 별도로 배우는 이유입니다.

기본 DL `sequence`는 실제 tiny RNN 학습입니다. 기존 LLM `attention`은 **주어진 작은 값의 attention 수학/불변식 모형**이고 Transformer 학습기가 아닙니다. 두 실행의 차이를 먼저 구분합니다.

```text
python -B ai/dl-paper-lab/labs/lab.py --lab sequence
python -B ai/llm-paper-lab/labs/lab.py --lab attention
```

## Transformer를 읽을 때 추적할 shape

한 sequence의 X가 T×d이면 projection으로 Q,K가 T×dₖ, V가 T×dᵥ가 됩니다. `QKᵀ/sqrt(dₖ)`는 T×T score, key 축 softmax 이후 V를 곱하면 T×dᵥ입니다. causal mask에서 허용하지 않는 미래 위치의 확률이 0이 되는지 확인합니다. mask를 value에만 곱하거나 softmax 뒤 renormalization 없이 가리는 것은 다른 계산입니다.

multi-head는 여러 subspace의 attention 결과를 결합하는 구조입니다. positional 정보, residual, normalization, feed-forward block, cross attention을 별도로 추적합니다. [Transformer 원문](https://arxiv.org/abs/1706.03762)은 encoder-decoder 번역 구조이며 현대 decoder-only LLM과 동일한 구성이라고 쓰지 않습니다. scaling/학습 data/서빙은 다음 과정에서 더합니다.

## BERT와 causal LM을 혼동하지 않기

DL12에서는 bidirectional context를 사용하는 masked-language-model objective와 downstream adaptation을 읽습니다. 모든 언어모델에 같은 causal mask와 next-token label을 적용하지 않습니다. 어떤 token을 보게 하고 어디에 loss를 주는지가 학습 문제를 정합니다. 원 BERT의 objective와 이후 encoder 모델 변형도 구분합니다. BERT 학습/모델 다운로드는 제공 CPU 코드에 없습니다.

## 이어지는 LLM 과정

| DL에서 넘겨주는 개념 | 다음 LLM 모듈 | 새로 배울 경계 |
| --- | --- | --- |
| embedding·causal attention·NLL | M01–02 구조/스케일링 | decoder-only·in-context·compute/data budget |
| parameter와 gradient·optimizer 상태 | M03–05 적응/정렬 | frozen/학습 parameter·preference·reference 모델 |
| activation/sequence 메모리 | M06–07 추론 | KV cache·IO·batch serving·검증 기반 생성 |
| representation과 평가 split | M08–09 검색/문맥 | retrieval와 생성 품질·정보 접근·context budget |
| metric·반증·실패 보존 | M10–14 추론/평가/연구 | tool 실행·budget·오염·독립 평가·재현 패키지 |

Transformer는 DL11과 LLM P01에 같은 논문으로 등장합니다. DL에서는 계산 구조와 정보 경계를, LLM에서는 학습·스케일·사용 조건을 다시 검토합니다. 별도의 새 원전으로 중복 집계하지 않습니다.

DL 마지막 미니 연구는 잘못된 shift/mask 반례 하나, parameter 변경 전후 결과, teacher-forced/rollout 구분, 주장 가능한 범위를 담습니다. GPU 없이 이 관문을 통과할 수 있지만 실제 Transformer 학습·대규모 pretraining·논문 benchmark를 완료한 것은 아닙니다. 다음 단계는 [기존 LLM 전체 안내](../../llm-paper-lab/README.md)입니다.
