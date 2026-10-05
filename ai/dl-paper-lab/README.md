# DL 원리와 논문 실험실

[전체 경로](../ml-dl-llm-roadmap.md) · [앞 단계 ML](../ml-paper-lab/README.md) · [다음 단계 LLM](../llm-paper-lab/README.md)

ML의 손실·평가·일반화 위에 **학습 가능한 표현, 계산 그래프, 역전파, 구조적 가정**을 추가합니다. 수식만 계산하는 단계와 실제 작은 network를 학습하는 단계를 구분하면서 MLP → convolution → recurrent/attention → 언어모델로 이동합니다.

20주·10모듈·주 12시간, 약 240시간을 계획 예산으로 둡니다. GPU를 쓰기 전에 tiny network에서 forward·backward·optimizer·데이터 계약을 확인합니다. ML의 split/metric 원칙은 그대로 유지합니다.

## 바로 실행

```text
python -B ai/dl-paper-lab/labs/lab.py --lab all
python -B -m unittest discover -s ai/dl-paper-lab/labs -p test_lab.py -v
```

Python 표준 라이브러리 CPU 경로입니다. 모델·dataset·framework를 내려받지 않으며 실제 작은 network의 parameter를 업데이트합니다. [환경](../paper-labs-environment.md)·[실행 안내](labs/README.md)·[검증 기록](../paper-labs-validation.md)을 먼저 확인합니다.

| 자료 | 역할 |
| --- | --- |
| [논문 지도](papers.md) | 역전파·CNN·RNN/언어모델·최적화·정규화·attention 원전 |
| [커리큘럼](curriculum.md) | ML 선수 조건부터 LLM 진입까지 10모듈 |
| [역전파와 최적화](lessons/01-backprop-optimization.md) | graph·gradient 누적·SGDM/Adam·학습 실패 |
| [Convolution과 일반화](lessons/02-convolution-regularization.md) | parameter 공유·경계·dropout/BN·residual |
| [시퀀스와 attention](lessons/03-sequence-attention.md) | BPTT·LSTM·teacher forcing·정렬과 causal 조건 |
| [언어모델과 LLM 연결](lessons/04-language-model-bridge.md) | token NLL·embedding·mask·Transformer/BERT·다음 과정 |
| [CPU LAB 4개](labs/README.md) | backprop, optimization, convolution, sequence |
| [공통 평가](../paper-labs-assessment.md) | gradient oracle·실제 학습·heldout·논문 재현 경계 |

## 기본과 확장 구분

기본은 작은 scalar autodiff, XOR MLP, optimizer 계산, 공유 1D 필터, Elman형 RNN입니다. LeNet/ResNet/LSTM/Transformer/BERT 전체 학습기, GPU tensor engine, dropout/BatchNorm layer, 대규모 자연어 pretraining은 아닙니다. 논문에 등장하는 구조를 모두 자동 구현했다고 표시하지 않습니다.

framework로 옮기는 과제는 별도 환경에서 같은 초기값·loss reduction·dtype·데이터를 고정하고 output/gradient/한 step을 맞추는 것부터 시작합니다. GPU/API는 선택 확장이며 CPU 실습 통과만으로 논문 benchmark나 실무 모델 품질을 주장할 수 없습니다.

마지막에는 [DL→LLM 관문](../ml-dl-llm-roadmap.md)을 통과하고 기존 LLM M01로 이어집니다. Transformer 원문을 DL에서 구조 관점으로 읽고 LLM에서 학습/스케일/서빙 관점으로 다시 읽는 것이며 중복된 새 논문으로 세지 않습니다.
