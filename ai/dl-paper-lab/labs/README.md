# DL 실행 실험실: 미분을 검증하고 작은 신경망을 실제 학습하기

[트랙](../README.md) · [논문 지도](../papers.md) · [커리큘럼](../curriculum.md)

Python 3.10 이상 표준 라이브러리로 실행합니다. GPU·API·계정·추가 패키지·데이터 다운로드가 필요 없습니다. [lab.py](lab.py)는 파일을 읽거나 쓰거나 네트워크를 사용하지 않으며 합성 데이터를 메모리에서 만듭니다. 원리를 계산만 하는 모형에 머물지 않고 **MLP, 공유 필터, 작은 RNN의 parameter를 loss의 gradient로 실제 갱신**합니다. 그렇다고 논문 전체 모델·원래 데이터셋·성능을 재현한 것은 아닙니다.

## 실행과 결과 계약

저장소 루트에서 실행합니다. `-B`는 Python의 bytecode cache 파일 생성도 막습니다.

```sh
python -B ai/dl-paper-lab/labs/lab.py --lab all
python -B ai/dl-paper-lab/labs/lab.py --lab backprop
python -B ai/dl-paper-lab/labs/lab.py --lab optimization
python -B ai/dl-paper-lab/labs/lab.py --lab convolution
python -B ai/dl-paper-lab/labs/lab.py --lab sequence
python -B -m unittest discover -s ai/dl-paper-lab/labs -p 'test_*.py'
python -B -O -m unittest discover -s ai/dl-paper-lab/labs -p 'test_*.py'
```

각 실험은 JSON 한 줄의 `expected`, `observed`, `scope`를 출력합니다. 성공은 exit 0, 검산/수치 실패는 `ERROR` 및 exit 1, 잘못된 CLI 선택은 exit 2입니다. `assert`에 기대지 않아 `-O`에서도 검산을 생략하지 않습니다. 여러 실험 중 뒤의 실험이 실패하면 앞의 `PASS`만 보고 전체 성공으로 판단하지 말고 **최종 exit code와 네 실험 결과**를 확인합니다.

seed는 `20261005`, 데이터·step 수·차원은 고정입니다. 실행 시간/처리량은 benchmark 지표로 사용하지 않습니다. JSON의 소수는 유효숫자 9자리로 표시하며 아주 작은 finite-difference 오차를 정밀도가 완벽한 0으로 반올림하지 않습니다. 운영체제·Python/libm 차이의 마지막 자릿수까지 동일하다고 보장하지 않습니다.

| 선택 | 실제 실행 | 독립 기대값·완료 기준 | 범위 제한 |
| --- | --- | --- | --- |
| `backprop` | 2→8→1 tanh MLP, 33 parameters, SGDM 300 step | 33좌표 중앙차분 `<1e-6`, train XOR 4/4·보류점 8/8, loss 감소, parameter 변경, 공유 graph gradient 13 | XOR 네 모서리를 모두 학습. 보류점은 같은 모서리 근방일 뿐 새로운 논리 조합이 아님 |
| `optimization` | 같은 이차 목적함수에 SGDM·Adam 각각 100 step | 최솟점 `(1,-2)`, 초기 loss의 1% 미만, Adam 첫 update·gradient 누적/초기화 | optimizer마다 고정 학습률이 다름. Adam 우월성/공정한 benchmark 아님 |
| `convolution` | 3-tap 공유 필터+bias, 4개 길이 6 신호, SGDM 300 step | 정답 필터 `(0.5,-1,0.25)`·bias `0.1`, 4좌표 중앙차분, 미학습 신호 오차 `<1e-4`, 경계 반례 | 선형 convolutional layer 하나. pooling·영상 분류·LeNet 전체는 미구현 |
| `sequence` | vocabulary 3, hidden 4 Elman RNN, 47 parameters, full BPTT, Adam 100 step | 47좌표 중앙차분, train CE 감소·parameter 변경, 보류 sequence 12/12 next-token, prefix 불변, 12-step greedy rollout | teacher forcing 평가와 생성 평가를 분리. LSTM/GRU·attention·Transformer 미구현 |

## 1. Backprop: 공유 경로의 gradient를 빠뜨리지 않기

`Value`는 scalar 하나와 부모 graph를 보관합니다. `+`, `*`, `tanh`, `exp`, `log`의 local derivative를 reverse topological order로 누적합니다. tensor·broadcasting·고차 미분·자동 memory 관리 최적화는 없습니다. forward와 backward 사이에는 parameter를 변경하지 않습니다.

`x=3`, `u=x*x`, `loss=u+u+x`이면 `d(loss)/dx=4x+1=13`입니다. 노드를 방문한 횟수와 gradient가 더해지는 경로 수는 다릅니다. 중복 edge를 제거하거나 gradient를 덮어쓰는 구현은 이 검사를 통과하지 못해야 합니다.

중앙차분은 `(L(w+ε)-L(w-ε))/(2ε)`, `ε=1e-5`입니다. 학습 전 각 parameter를 하나씩 교란하고 원래 값으로 복구합니다. 절대오차 `<1e-6`은 **이 작은 smooth fixture**의 기준입니다. 모든 scale·dtype·ReLU 비미분점에 같은 허용오차를 강요하지 않습니다. 단위 테스트는 autodiff 함수와 별도의 `math` 식으로 만든 oracle도 비교합니다.

훈련에는 XOR의 네 모서리만 사용합니다. 8개 근방 입력은 gradient 계산에 넣지 않습니다. 다만 이 보류점도 공개·고정된 교육용 검산 데이터이므로 실제 모델 선택 후의 독립 test set이나 일반화 통계라고 보고하지 않습니다.

## 2. Optimization: update 식과 실험 설계 분리

SGDM은 `v_t = μ v_(t-1) + g_t`, `w_t = w_(t-1) - η v_t`입니다. 이 실험의 momentum은 gradient 평균에 `(1-μ)`를 곱하는 다른 표기와 구분합니다.

Adam은 `m_t=β1 m_(t-1)+(1-β1)g_t`, `v_t=β2 v_(t-1)+(1-β2)g_t²`, `m̂=m_t/(1-β1^t)`, `v̂=v_t/(1-β2^t)`, `w -= η m̂/(sqrt(v̂)+ε)`입니다. weight decay·AdamW·AMSGrad·scheduler·gradient clipping은 구현하지 않았습니다.

동일 graph에서 `backward()`를 두 번 호출하면 **leaf gradient는 누적**, 중간 node gradient는 매번 초기화됩니다. `x=2`, `x²`에서 `4 → 8`, `zero_grad` 후 `4`를 확인합니다. accumulation은 의도적인 microbatch 합산에 쓸 수 있지만 이 full-batch 학습 loop에서는 매 step 초기화해야 합니다.

고정 목적함수는 `(x-1)² + 4(y+2)²`, 초기점은 `(4,-3)`입니다. SGDM과 Adam의 감소 곡선/종점을 관찰하되 서로 다른 학습률과 하나의 목적함수만으로 범용 순위를 주장하지 않습니다. 이 fixture에서는 SGDM의 마지막 loss가 더 작을 수 있으며 이는 실패가 아닙니다.

## 3. Convolution: 공유 parameter와 경계 조건

계산식은 `y_i = Σ_k w_k x_(i+k) + b`입니다. 신경망 라이브러리의 일반적인 **cross-correlation** 표기이며 kernel을 뒤집는 수학적 convolution과 구분합니다. valid padding·stride 1이고 activation은 없습니다.

네 훈련 신호의 정답은 autodiff helper와 별도의 수치 식으로 만듭니다. 단위 테스트에서 signal `(1,2,4,8)`, kernel `(2,-1)`, bias `0.5`의 출력이 `(0.5,0.5,0.5)`인지, 출력 합의 kernel gradient가 `(7,14)`인지도 확인합니다. 공유 weight의 gradient는 모든 위치의 기여를 합쳐야 합니다.

오른쪽 zero-fill shift 후의 valid 결과와 원래 출력을 오른쪽 shift한 결과는 **내부 위치에서는 같지만 경계에서 다릅니다**. translation equivariance는 padding·cropping·stride·출력 정의를 명시해야 하는 성질이지 모든 유한 배열에서 무조건 성립하는 문장이 아닙니다.

추가 연구는 같은 oracle을 유지한 다중 channel·activation·pooling 구현입니다. 제공 코드의 성공을 영상 분류나 LeNet 논문 실험 완료로 기록하지 않습니다.

## 4. Sequence: causal 계산과 teacher forcing을 구별하기

Elman RNN은 `h_t=tanh(W_x one_hot(x_t)+W_h h_(t-1)+b_h)`, `logits_t=W_y h_t+b_y`로 계산합니다. 초기 hidden state는 각 sequence마다 0으로 재설정합니다. CE는 peak를 빼는 log-sum-exp로 안정화하며, next token을 정답으로 하여 모든 시간축의 공유 parameter에 BPTT gradient를 누적합니다. 이 작은 graph에서는 truncated BPTT를 쓰지 않습니다.

훈련은 `0,1,2,0,…` 길이 10 한 sequence입니다. 보류 sequence는 phase와 길이를 바꾸지만 **같은 transition 규칙**을 사용합니다. teacher forcing은 이전 정답 token을 넣는 조건부 평가이고, 별도 greedy rollout은 자기 예측을 다음 입력으로 사용합니다. 둘을 하나의 accuracy로 합치지 않습니다.

두 입력의 prefix가 같고 suffix만 다르면 prefix 출력은 정확히 같아야 합니다. 이 검사는 미래 입력을 우연히 섞는 구현을 잡지만 좋은 장기 기억을 증명하지 않습니다. 이 주기 패턴은 직전 token 하나만으로 풀 수 있으므로 RNN의 memory 장점·긴 context·자연어 일반화를 입증하지 않습니다. LSTM의 gate/CEC, GRU, attention과 Transformer는 [논문 지도](../papers.md)에서 별도 구현·반증 과제로 이어집니다.

## 검증·제출물

[test_lab.py](test_lab.py)는 손계산·독립 수치 미분·shared graph·gradient 누적·필터 방향·shift 경계·CE 안정화·BPTT·prefix causality·invalid input·seed·CLI를 검사합니다. 네 실제 학습 실험을 socket 및 application file access가 막힌 조건에서도 실행합니다. 이 mock 차단은 OS 수준 보안 sandbox를 제공한다는 의미가 아닙니다.

제출에는 Python/OS·commit·명령·exit code·네 JSON과 다음 내용을 포함합니다.

1. 미분식 및 독립 oracle, ε를 바꿨을 때 오차 변화.
2. 초기/최종 loss·실제 parameter 변경·훈련 입력과 보류 입력 구분.
3. 공유 edge 누락, zero_grad 생략, kernel 반전, 미래 token 누출 중 하나의 의도적 실패와 원복.
4. 구현하지 않은 tensor 기능·모델 구조·논문 결과 및 이 실험으로 주장할 수 없는 일반화 범위.

완료 판정은 단위 테스트 개수나 elapsed time이 아니라 **계산 정확성 → 실제 학습 → 독립 검산 → 범위 설명**입니다. 원본 논문 성능·대규모 데이터 학습·GPU 효율은 이 CPU fixture의 검증 범위가 아닙니다.
