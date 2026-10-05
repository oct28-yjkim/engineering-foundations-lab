# 시퀀스 기억과 attention

[과정](../curriculum.md) · [논문 DL03 DL04 DL05 DL06](../papers.md) · [실습](../labs/README.md)

## RNN은 parameter를 시간에 공유한다

Elman형 recurrent layer는 `hₜ=tanh(Wₓxₜ+Wₕhₜ₋₁+b)`처럼 현재 입력과 이전 state를 결합합니다. Wₕ는 token마다 새로 생성되지 않습니다. 길이 T로 펼친 graph에서 같은 parameter의 gradient 기여를 합산하는 것이 BPTT의 핵심입니다. 긴 의존성을 다룰 때 반복되는 Jacobian 곱이 gradient의 소실/폭발과 연결될 수 있습니다.

```text
python -B ai/dl-paper-lab/labs/lab.py --lab sequence
```

기본은 합성 sequence의 다음 token을 학습하는 **작은 Elman RNN**입니다. 초기/최종 cross entropy, recurrent parameter의 finite difference, teacher-forced 예측과 별도 autoregressive rollout을 읽습니다. 반복 규칙의 next-token 문제는 짧은 문맥 baseline으로도 풀릴 수 있습니다. 긴 기억을 입증하려면 같은 최근 token인데 더 먼 문맥 때문에 정답이 달라지는 별도 task가 필요합니다.

## teacher forcing과 생성

학습에서 정답 과거 token을 입력하는 것과 생성에서 모델의 이전 출력을 다시 입력하는 것은 다른 데이터 흐름입니다. teacher-forced 정확도가 높아도 rollout의 오류가 누적될 수 있습니다. 길이·stop 조건·초기 prompt·sampling 정책을 고정하고 두 결과를 별도 metric으로 남깁니다.

독립 sequence 사이에 hidden state가 남아 있으면 split 경계가 깨지거나 순서 의존 오류가 생길 수 있습니다. state reset과 truncated BPTT의 detach를 구분합니다. 기본은 짧은 sequence의 전체 graph이며 긴 sequence의 truncated BPTT·checkpointing은 별도 구현 과제입니다.

## LSTM과 encoder decoder

MLP/RNN의 실패를 모두 layer 수로 해결하려 하지 않습니다. DL03에서는 memory cell과 gate를 통한 상태/gradient 경로를 읽습니다. **1997년 원문과 이후의 forget gate를 포함한 현대 LSTM을 같은 식으로 간주하지 않습니다.** 구현하려는 변형을 먼저 고정하고 parameter 수·state shape·gate 범위를 검산합니다. 기본 runner는 LSTM이 아닙니다.

DL05의 encoder-decoder는 입력과 출력 길이가 다른 sequence 변환을 다룹니다. 정보가 fixed-size 상태를 거쳐 decoder에 전달되는 경로를 그려보고, 입력 길이·순서·decoder 초기값이 무엇을 바꾸는지 질문합니다. 이 과제를 기본 periodic next-token task로 재현했다고 하지 않습니다.

DL06의 attention은 출력 단계에 따라 입력 표현의 가중 조합을 선택하는 경로로 읽습니다. attention weights는 입력에 대한 정보 접근을 보여주지만 인과적 설명이나 정답 근거임을 자동 보장하지 않습니다. additive attention, dot-product attention, self/cross attention을 구분한 뒤 다음 강의로 넘어갑니다.

## 관측과 실패 분석

- loss 정체: gradient 검사 → 작은 batch overfit → token/target shift → state reset → learning rate 순으로 좁힙니다.
- 길이가 길 때 발산: 길이별 gradient norm·activation·update를 확인합니다. norm clipping은 gradient norm을 제한하며 실제 parameter update는 momentum/Adam 상태와 learning rate에도 좌우됩니다. 잘못된 target/mask를 고치는 기능은 아닙니다.
- rollout만 실패: teacher forcing 차이·sampling·stop 조건·문맥 길이를 비교합니다.
- 미래 입력을 바꿨더니 과거 출력이 바뀜: causal 문맥·packing·입력/정답 위치를 확인합니다.

gradient clipping과 recurrent 최적화의 추가 원전은 [Pascanu 등의 연구](https://arxiv.org/abs/1211.5063)입니다. 핵심 목록 12편과 별도의 심화 읽기이며 clipping 구현/효과를 기본 코드가 검증했다고 표시하지 않습니다.

제출물은 unfold한 graph와 shared gradient, 입력/target 표, teacher-forced/rollout 차이, 장기 기억을 주장할 수 없는 이유, LSTM/attention의 별도 검증 설계입니다.
