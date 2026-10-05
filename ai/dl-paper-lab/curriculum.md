# DL 커리큘럼: 내부 계산을 검증하고 LLM으로 연결하기

[시작](README.md) · [원전 12편](papers.md) · [전체 경로](../ml-dl-llm-roadmap.md) · [환경](../paper-labs-environment.md) · [평가](../paper-labs-assessment.md)

**10모듈 × 2주 × 주 12시간 = 20주·240시간**의 계획 예산입니다. 모듈별 원문/수학 6h, 구현/실험 10h, 코드/반례 4h, 기록/리뷰 4h입니다. [ML 관문](../ml-paper-lab/curriculum.md)을 먼저 통과하고, 벡터·chain rule·조건부 확률이 불안하면 [기초 과정](../foundations.md)을 보충합니다. 시간 이수보다 독립 검산·진단·재현 증거가 진입 조건입니다.

`P` 제공 CPU 코드, `M` 수기/설계, `E` 별도 구현/환경 확장입니다. 명령은 저장소 루트에서 `python -B ai/dl-paper-lab/labs/lab.py --lab <ID>`이며, 이 과정은 대규모 tensor engine이나 완전한 논문 학습기 모음이 아닙니다.

| 모듈·주차 | 선수 조건·원전 | 목적 → 내부 계산 | 실행/관측 → 제약·통과 증거 |
| --- | --- | --- | --- |
| DL-M01 · 1–2 | ML split/loss·미분, DL01 | 고정 특징에서 학습된 표현으로; 계산 그래프·위상 순서·chain rule | `P backprop`: 공유 노드 gradient·유한차분·XOR MLP. 모든 사용 경로의 미분이 합산되는 이유, 비선형성 제거의 한계를 설명 |
| DL-M02 · 3–4 | M01, DL07/DL01 | parameter 업데이트·SGD/Momentum/Adam 상태·bias correction | `P optimization`: 목적함수 감소·한 step oracle·gradient 누적/초기화. `M` 학습률 과대/상태 누락 진단. Adam과 AdamW를 구별하고 loss reduction을 고정 |
| DL-M03 · 5–6 | M01·배열 shape, DL02 | locality·parameter sharing·receptive field·cross-correlation | `P convolution`: 실제 3-tap 필터 fitting·gradient·heldout·경계 반례. `M` LeNet layer shape. 1D 선형층을 전체 CNN 학습이라 부르지 않음 |
| DL-M04 · 7–8 | M02–03·기댓값/분산, DL08/DL09 | stochastic regularization·batch statistics·학습/추론 mode | `M` dropout mask 열거·BN mean/variance·γ/β와 inference state. `E` layer 구현/ablation. train/eval 혼동과 작은 batch 반례를 먼저 예측; 기본 runner 미구현 표시 |
| DL-M05 · 9–10 | M01/M04·Jacobian, DL10 | 깊이·최적화·잔차 경로와 shape projection | `M` plain/residual의 Jacobian·parameter/budget 비교. `E` tiny residual network 학습. 일반화와 최적화 실패를 구별하고 residual이 항상 유리하지 않은 조건 제시 |
| DL-M06 · 11–12 | M01–02·조건부 확률, DL03 | hidden state·weight sharing through time·BPTT·장기 의존성 | `P sequence`: Elman RNN 실제 학습·prefix 불변·gradient check. `M` time별 gradient 경로와 1997 LSTM gate. 현대 forget gate·원문의 truncation·제공 Elman 구별 |
| DL-M07 · 13–14 | M06·softmax/NLL, DL04 | token 조건부 확률·representation·학습/평가 단위 | `P sequence` 재사용: token CE·teacher-forced heldout·greedy rollout을 분리. `M` embedding과 고정 문맥 feed-forward LM 계산. 작은 순환 데이터가 자연어 일반화가 아님을 설명 |
| DL-M08 · 15–16 | M06–07, DL05/DL06 | encoder/decoder·정렬·가변 길이·teacher forcing·decoding | `M` EOS/PAD/target-shift 계약, additive score→context 수기 계산. `E` attention seq2seq. alignment와 causal 설명을 혼동하지 않고 길이/budget 통제 계획 제출 |
| DL-M09 · 17–18 | M04/M08·행렬 곱, DL11/DL12 | scaled attention·multi-head·position·causal/MLM 목적 | `M` Q/K/V shape·mask·encoder/decoder/BERT 비교. 다음 LLM `attention` LAB은 연결 실습으로 별도 표시. whole Transformer/BERT 학습은 `E`; PAD/미래 정보 누출 반례 작성 |
| DL-M10 · 19–20 | M01–09 핵심 관문 | 한 원리를 검증 가능한 연구 주장으로 만들기 | 네 LAB 하나의 대조군+변경1개+ablation+실패 fixture 또는 실행 가능한 기본에 대한 재현 보고서. scope·seed·reduction·상태·split·미실행 확장을 공개하고 DL→LLM 관문 방어 |

## 강의 연결

- M01–02: [역전파와 최적화](lessons/01-backprop-optimization.md). forward 한 번 → gradient 수기 계산 → finite difference → 실제 parameter update 순서로 진행합니다.
- M03–05: [Convolution과 일반화](lessons/02-convolution-regularization.md). 구조적 가정과 경계, train/eval 상태, residual을 같은 모델의 성능 마법으로 뭉뚱그리지 않습니다.
- M06/M08: [시퀀스와 attention](lessons/03-sequence-attention.md). 입력/target 시간 인덱스와 상태 초기화를 먼저 확인합니다.
- M07/M09–10: [언어모델과 LLM 연결](lessons/04-language-model-bridge.md). 조건부 확률, 정보 접근, token 단위 평가를 기존 LLM 과정으로 가져갑니다.

## 정상 동작·관측·실패 진단

| 상황 | 먼저 관측하는 것 | 분리 실험과 복구 기준 |
| --- | --- | --- |
| loss가 내려가지 않음 | parameter가 실제 바뀌는가, gradient가 0/비정상인가, learning rate/reduction은 같은가 | 작은 batch 과적합·독립 gradient oracle로 데이터/미분/optimizer를 분리. 감소만으로 heldout 성공 처리하지 않음 |
| 한 step 뒤 값이 예상과 다름 | 공유 노드의 경로 수, gradient 누적, momentum/m/v/step | `backprop`/`optimization`의 독립 예상값과 대조. zero-grad와 optimizer state 보존을 검산 |
| convolution 이동 결과 불일치 | 입력/출력 크기·stride·padding·경계 처리 | `convolution`의 내부 위치와 경계 반례를 구별. 무조건 구현 오류나 완전한 이동 불변이라 하지 않음 |
| train은 좋지만 eval이 나쁨 | split·중복·mode·dropout/BN 상태·전처리 | `M/E` train/eval 상태·분포 이동을 분리. 기본 runner에 없는 layer를 관측한 것처럼 보고하지 않음 |
| 시퀀스 score가 의심스럽게 좋음 | target shift·미래 token 접근·state reset·teacher forcing | `sequence` prefix 불변과 별도 rollout 확인. 길이만 다른 동일 순환 전이의 heldout은 미지 의미/전이 일반화가 아님 |
| 더 깊은 모델이 나쁨 | train/heldout loss를 함께 보고 parameter·compute·초기화 통제 | `M/E` 최적화 난도와 overfit을 분리한 plain/residual 대조; 작은 장난감 결과를 대규모 우월성으로 외삽하지 않음 |

## 제공 코드와 별도 환경

기본 실행은 scalar autodiff 기반 XOR MLP, 작은 목적함수의 SGD/Momentum/Adam, 공유 1D 선형 필터, tiny Elman RNN입니다. dropout/BN/residual/LSTM/encoder-decoder/Transformer/BERT 전체 구현·학습은 제공하지 않습니다. 단, 기능을 사용하지 않더라도 **목적 → 계산/상태 → 관측 → 제약/반례 → 채택/비채택**을 수기로 설명하는 과제는 필수입니다.

framework/GPU 확장은 먼저 같은 입력·가중치·dtype·loss reduction·epsilon으로 output/gradient/한 step 동치를 확인합니다. 속도를 측정하려면 warm-up·동기화·device·batch·메모리 조건을 기록하고 정확성 검증과 성능 benchmark를 분리합니다. API 호출이나 대규모 다운로드는 기본 과정에 필요하지 않습니다.

## DL → LLM 관문

1. chain rule과 공유 parameter의 gradient 합산을 수기/유한차분/코드로 대조한다.
2. forward 계산·backward 계산·optimizer 상태를 구분하고 한 step 오류를 진단한다.
3. train/validation/test, regularization, mode/state가 예측과 평가를 바꾸는 이유를 설명한다.
4. convolution의 parameter 공유·경계와 RNN의 시간별 공유·상태 초기화를 설명한다.
5. embedding/logits/softmax/token NLL의 shape·reduction을 쓰고 teacher forcing과 생성 평가를 분리한다.
6. additive attention과 scaled dot-product attention, encoder/decoder, MLM과 causal LM의 정보 접근을 비교한다.
7. 실측과 예상·원논문 수치를 구분하고 실패 fixture와 제한을 포함한 보고서를 다른 사람이 재실행한다.

통과하면 [기존 LLM M01](../llm-paper-lab/curriculum.md)로 이동합니다. 전체 ML16주+DL20주+LLM28주는 64주·768시간의 계획이며 기초 선택 4주를 더하면 68주·816시간입니다. 연구 전문성은 추가 원전·실데이터·다중 seed·반례·독립 재현·새 가설 검증으로 계속 확장합니다. M10은 24시간 미니 연구이지 대규모 사전학습을 끝내는 약속이 아닙니다. 실제 검증 결과는 [공통 검증 기록](../paper-labs-validation.md)을 따릅니다.
