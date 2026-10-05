# DL 논문 지도: 계산 그래프에서 언어모델까지

[시작](README.md) · [10모듈 커리큘럼](curriculum.md) · [실행 LAB](labs/README.md) · [앞 단계 ML](../ml-paper-lab/papers.md) · [다음 단계 LLM](../llm-paper-lab/papers.md)

12편을 구조·최적화·일반화·시퀀스의 네 축으로 읽습니다. `P`는 제공 CPU 코드의 축소 계산/학습, `M`은 수기/설계 과제, `E`는 별도 구현·환경 확장입니다. 논문 전체 학습기를 구현했다고 표시하지 않으며, GPU/API는 선택 사항입니다.

출처는 저자·학회·저널 원문을 우선했고 2026-10-05에 아래 지정 구간을 확인했습니다. DL01은 저자 보관본과 판독 가능한 원문 사본을 함께 제공합니다. DL02는 PDF 글꼴 추출 문제로 서지·초록·일부 그림 label 확인에 한정되며 본문 확인을 추가해야 합니다. preprint 최초 공개와 학회 출판 연도를 구분합니다. “확인”은 지정한 원문 구간/서지의 확인이지 전 페이지 완독·수치 재현 완료를 뜻하지 않습니다.

## DL01 · 역전파와 학습된 표현

David E. Rumelhart, Geoffrey E. Hinton, Ronald J. Williams, **Learning Representations by Back-Propagating Errors**, 1986, *Nature* 323, 533–536. [저자 보관 PDF](https://www.cs.toronto.edu/~hinton/absps/naturebp.pdf) · [판독 가능한 원문 사본](https://gwern.net/doc/ai/nn/1986-rumelhart-2.pdf)

- **읽을 부분**: 식 (1)–(9)의 forward·오차·chain rule·가중치 갱신, hidden representation 예시.
- **핵심 주장**: 출력 오차의 미분을 내부 연결로 전달해 task에 유용한 hidden representation을 학습합니다.
- **실험 연결**: `P backprop`에서 scalar autodiff·공유 노드의 gradient 합산·유한차분·XOR MLP 학습을 확인합니다.
- **한계/반례**: XOR 예제는 원문 실험의 복제가 아니며 train loss 하락은 일반화 증거가 아닙니다. gradient 누락/중복·초기 대칭성·비선형성 제거를 진단합니다. 역전파의 역사 전체를 이 한 논문의 최초 발명으로 단순화하지 않습니다.

## DL02 · CNN과 문서 인식

Yann LeCun, Léon Bottou, Yoshua Bengio, Patrick Haffner, **Gradient-Based Learning Applied to Document Recognition**, 1998, *Proceedings of the IEEE* 86(11), 2278–2324. [공저자 서지](https://bottou.org/papers/lecun-98h) · [공저자 원문](https://leon.bottou.org/publications/pdf/ieee-1998.pdf) · [저자 업로드 초록](https://www.researchgate.net/publication/2985446_Gradient-Based_Learning_Applied_to_Document_Recognition)

- **읽을 부분**: convolutional network/LeNet-5 구조와 local receptive field·weight sharing·subsampling, 문서 인식 파이프라인. **이번 원문 본문은 글꼴 추출 손상으로 판독이 제한**되어 section/식 번호를 확정하지 않습니다.
- **핵심 주장**: 공간적 구조를 반영한 학습과 여러 처리 단계의 결합을 문서 인식에 적용합니다.
- **실험 연결**: `P convolution`은 공유 1D 필터의 실제 학습·gradient check·heldout 신호·경계 반례입니다. `M` LeNet-5 layer별 shape/parameter를 계산합니다.
- **한계/반례**: 기본 코드는 stride-1 valid cross-correlation 한 층이며 kernel-flip convolution·pooling·MNIST/LeNet 학습이 아닙니다. 내부 이동 관계가 padding/cropping 경계까지 정확히 성립하지 않습니다.

## DL03 · LSTM

Sepp Hochreiter, Jürgen Schmidhuber, **Long Short-Term Memory**, 1997, *Neural Computation* 9(8), 1735–1780. [저자/기관 원문](https://www.bioinf.jku.at/publications/older/2604.pdf)

- **읽을 부분**: §3 장기 gradient 문제, §4 memory cell, Appendix A.1의 state·input/output gate 갱신과 truncated derivative.
- **핵심 주장**: 특수한 내부 상태와 gate로 장기 오차 전달을 보존하는 학습 구조를 제안합니다.
- **실험 연결**: `P sequence`의 Elman RNN을 기준으로 `M` 3 timestep Jacobian과 memory-cell 경로를 비교합니다. `E` 지연 copy task와 LSTM 구현을 추가합니다.
- **한계/반례**: 제공 코드에는 LSTM이 없습니다. 1997년 원형에 현대적인 forget gate를 소급해서 넣지 않습니다. 원문의 특수 truncation과 오늘날 일반 autodiff BPTT 구현도 구별해야 합니다.

## DL04 · Neural probabilistic language model

Yoshua Bengio, Réjean Ducharme, Pascal Vincent, Christian Jauvin, **A Neural Probabilistic Language Model**, 2003, *JMLR* 3, 1137–1155. [저널 원문](https://jmlr.org/papers/volume3/bengio03a/bengio03a.pdf)

- **읽을 부분**: §1의 조건부 확률 분해·분산 표현, §2의 word feature/확률 함수 공동 학습.
- **핵심 주장**: 단어 표현과 다음 단어 확률을 함께 학습해 유사 문맥 사이의 통계적 정보를 공유합니다.
- **실험 연결**: `M` embedding lookup·logits·softmax·token NLL을 계산합니다. `P sequence`의 다음 token 목적과 비교합니다.
- **한계/반례**: 원문은 고정 길이 문맥의 feed-forward 모델이며 제공 Elman RNN과 다른 구조입니다. 작은 순환 token 데이터의 정답률로 자연어 perplexity나 의미 이해를 주장하지 않습니다.

## DL05 · Sequence to sequence

Ilya Sutskever, Oriol Vinyals, Quoc V. Le, **Sequence to Sequence Learning with Neural Networks**, 2014, *NIPS*. [원문](https://arxiv.org/pdf/1409.3215)

- **읽을 부분**: §2 모델과 조건부 시퀀스 확률, encoder/decoder, source 순서 반전, 실험의 decoding 조건.
- **핵심 주장**: 가변 길이 입력과 출력을 연결하는 encoder-decoder 학습을 번역에 적용합니다.
- **실험 연결**: `M` EOS·padding·teacher-forcing 입력/target을 표로 만들고 한 단계 생성과 구별합니다. `P sequence`는 단일 autoregressive Elman baseline뿐입니다.
- **한계/반례**: 제공 코드에는 encoder-decoder LSTM·beam search·번역 benchmark가 없습니다. 고정 벡터 bottleneck, 길이, decoding budget을 통제하지 않으면 모델 효과를 비교할 수 없습니다.

## DL06 · 정렬을 학습하는 attention

Dzmitry Bahdanau, Kyunghyun Cho, Yoshua Bengio, **Neural Machine Translation by Jointly Learning to Align and Translate**, arXiv **2014**, *ICLR 2015*. [원문](https://arxiv.org/pdf/1409.0473)

- **읽을 부분**: §3.1 decoder의 context·alignment weight, §3.2 bidirectional encoder, 길이에 따른 번역 비교.
- **핵심 주장**: 하나의 고정 벡터만 사용하는 대신 출력 시점마다 입력 annotation의 가중 조합을 사용합니다.
- **실험 연결**: `M` 세 입력과 두 출력의 score→softmax→context를 손으로 계산하고 PAD masking 반례를 만듭니다. `E` additive-attention seq2seq를 구현합니다.
- **한계/반례**: 이 구조는 Transformer의 scaled dot-product attention과 다릅니다. 정렬 가중치만으로 인과적 설명이나 추론 과정의 충실성을 보장하지 않습니다. 기본 RNN runner에는 attention이 없습니다.

## DL07 · Adam

Diederik P. Kingma, Jimmy Ba, **Adam: A Method for Stochastic Optimization**, arXiv **2014**, *ICLR 2015*. [원문](https://arxiv.org/pdf/1412.6980)

- **읽을 부분**: Algorithm 1, 1차/2차 moment·bias correction·epsilon과 update 식.
- **핵심 주장**: gradient의 이동 통계를 이용해 parameter별 갱신 크기를 조절합니다.
- **실험 연결**: `P optimization`에서 SGD/Momentum/Adam으로 작은 목적함수를 실제 최소화하고 첫 update를 독립 계산합니다. `M` checkpoint에 step/m/v가 필요한 이유를 설명합니다.
- **한계/반례**: 학습률·epsilon 위치·loss reduction을 고정해야 비교가 됩니다. 모든 목적에서 수렴/우월함을 보장하지 않으며 AdamW와 weight decay를 이 구현에 포함했다고 하지 않습니다.

## DL08 · Dropout

Nitish Srivastava, Geoffrey Hinton, Alex Krizhevsky, Ilya Sutskever, Ruslan Salakhutdinov, **Dropout: A Simple Way to Prevent Neural Networks from Overfitting**, 2014, *JMLR* 15, 1929–1958. [저널 원문](https://jmlr.org/papers/volume15/srivastava14a/srivastava14a.pdf)

- **읽을 부분**: §4 model description의 Bernoulli mask, §5 학습, train/test weight scaling.
- **핵심 주장**: 학습 중 일부 unit을 무작위로 제외하는 정규화가 과적합을 줄일 수 있습니다.
- **실험 연결**: `M` 두 unit의 모든 mask를 열거해 기대 activation과 분산을 계산합니다. `E` inverted dropout을 tiny MLP에 추가하고 train/eval mode를 비교합니다.
- **한계/반례**: dropout layer는 기본 코드에 없습니다. 원문의 test-time scaling과 현대 inverted scaling을 혼합하지 않으며 `E[f(x)] = f(E[x])`를 비선형 network에 일반화하지 않습니다.

## DL09 · Batch normalization

Sergey Ioffe, Christian Szegedy, **Batch Normalization: Accelerating Deep Network Training by Reducing Internal Covariate Shift**, 2015, *ICML / PMLR* 37, 448–456. [학회 원문](https://proceedings.mlr.press/v37/ioffe15.pdf)

- **읽을 부분**: Algorithm 1의 batch mean/variance·epsilon·γ/β와 inference에서 통계를 사용하는 절차.
- **핵심 주장**: 학습 중 activation 정규화와 학습 가능한 affine 변환을 사용합니다. internal covariate shift 감소는 **원문이 제시한 설명**이지 효과의 유일하고 확정된 원인으로 가르치지 않습니다.
- **실험 연결**: `M` 두 batch의 출력과 running statistics를 검산합니다. `E` train/eval·작은 batch·분포 이동 비교를 구현합니다.
- **한계/반례**: BN은 기본 코드에 없습니다. batch 축과 feature 축, 학습/추론 통계, 분산 정의를 명시해야 하며 LayerNorm과 같은 연산으로 취급하지 않습니다.

## DL10 · Residual learning

Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun, **Deep Residual Learning for Image Recognition**, arXiv **2015**, *CVPR 2016*. [원문](https://arxiv.org/pdf/1512.03385)

- **읽을 부분**: §3.1–3.2, 식 (1) `y = F(x) + x`, §4의 plain/residual 학습 오차 비교.
- **핵심 주장**: residual로 재매개화한 깊은 network가 해당 실험의 최적화 어려움을 줄입니다.
- **실험 연결**: `M` identity branch가 있는 Jacobian을 계산하고 shape 변경 시 projection을 검산합니다. `E` 같은 깊이/폭/budget의 tiny plain/residual network를 비교합니다.
- **한계/반례**: ResNet은 기본 코드에 없습니다. residual이 모든 gradient 문제를 제거하거나 depth 증가가 항상 일반화를 개선한다고 결론내리지 않습니다. 원문의 degradation 논의도 단순 vanishing-gradient 설명으로 환원하지 않습니다.

## DL11 · Transformer

Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin, **Attention Is All You Need**, 2017, *NIPS*. [원문](https://arxiv.org/pdf/1706.03762)

- **읽을 부분**: §3.2.1 식 (1)의 scaled dot-product attention, multi-head, positional encoding, encoder/decoder mask.
- **핵심 주장**: recurrence 없이 attention을 중심으로 encoder-decoder 시퀀스 모델을 구성합니다.
- **실험 연결**: `M` Q/K/V shape·softmax 축·causal/PAD mask를 검산합니다. 다음 [LLM 과정의 `attention`](../llm-paper-lab/labs/README.md)에서 축소 계산을 이어갑니다.
- **한계/반례**: DL 기본 runner에는 Transformer가 없습니다. 원문은 encoder-decoder이며 decoder-only LLM과 같지 않습니다. attention 계산 검증은 번역/언어모델 학습 재현이 아닙니다.

## DL12 · BERT

Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova, **BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding**, arXiv **2018**, *NAACL-HLT 2019*, 4171–4186. [학회 원문](https://aclanthology.org/N19-1423.pdf)

- **읽을 부분**: §3.1 MLM/NSP pretraining, §3.2 fine-tuning, 입력 embedding 구성과 task별 평가.
- **핵심 주장**: 양방향 문맥으로 사전학습한 표현을 여러 이해 task에 적응시킵니다.
- **실험 연결**: `M` 같은 문장에 MLM과 causal next-token loss의 관측/예측 위치를 표시합니다. `E` 작은 masked model과 causal model을 같은 데이터 계약에서 비교합니다.
- **한계/반례**: 모델 다운로드·BERT 학습·benchmark는 기본 제공하지 않습니다. 양방향 encoder를 그대로 좌→우 생성기로 보거나 원문의 NSP가 모든 후속 모델의 필수 요소라고 하지 않습니다.

## 논문을 실험으로 옮기는 계약

각 실험은 논문의 **가정/주장**, 제공 코드가 검증하는 **국소 원리**, 아직 검증하지 않은 **성능/스케일 주장**을 분리합니다. 모든 식의 shape와 reduction, optimizer 상태, train/eval mode, 데이터 split, teacher-forced 평가와 자체 생성 평가를 적습니다. 원문 표의 숫자를 우리 실행 결과 칸에 복사하지 않습니다.

Transformer는 이 과정과 기존 LLM 과정이 공유하는 연결 논문입니다. 중복된 새 논문으로 세지 않고, 여기서는 구조/계산을, 다음 단계에서는 스케일·적응·평가·서빙 제약을 더 깊게 다룹니다.
