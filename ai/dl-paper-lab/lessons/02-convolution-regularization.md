# Convolution 일반화와 깊은 구조

[과정](../curriculum.md) · [논문 DL02 DL08 DL09 DL10](../papers.md) · [실습](../labs/README.md)

## parameter 공유가 만드는 가정

작은 kernel을 여러 위치에 공유하면 local pattern을 같은 가중치로 읽습니다. fully connected layer보다 parameter 수가 줄어드는 이유를 입력 길이·kernel 폭·channel 수로 손계산합니다. 실제 DL 코드에서 convolution이라 부르는 연산은 kernel을 뒤집지 않는 cross-correlation인 경우가 많으므로 식의 인덱스를 확인합니다.

1차원 valid 연산의 예로 x=[1,2,3,4], k=[1,−1]이면 출력은 [−1,−1,−1]입니다. `Σoutput`의 k에 대한 gradient는 [1+2+3,2+3+4]=[6,9]입니다. 위치마다 별도의 k를 만들면 공유 모델과 다른 함수가 됩니다.

```text
python -B ai/dl-paper-lab/labs/lab.py --lab convolution
```

기본은 **공유 선형 1D 필터 한 층을 실제 학습**하는 실험입니다. forward/gradient oracle, 학습 MSE, 보류 입력, 이동과 경계의 차이를 확인합니다. pooling·여러 channel·2D image·LeNet 전체·MNIST 성능을 제공한다고 해석하지 않습니다.

## equivariance와 invariance

입력이 이동했을 때 출력도 대응해서 이동하는 성질과, 출력이 완전히 같아지는 성질은 다릅니다. padding·stride·crop·finite boundary가 정확한 이동 관계를 깨뜨릴 수 있습니다. zero padding을 붙인 이동 입력에서 어디가 새 경계인지 표시하고 내부 위치와 경계를 분리해서 비교합니다. pooling이 모든 이동에 완전한 불변성을 보장하지도 않습니다.

## dropout BatchNorm residual을 배우는 수동 확장

아래는 **기본 runner 밖의 구현/관측 과제**입니다. 사용하지 않는 기능도 목적·상태·제약·미채택 이유를 설명해야 합니다.

| 기능 | 계산/상태 | 실험과 반례 |
| --- | --- | --- |
| dropout | 학습 중 확률 mask, train/eval 동작과 scale convention | 동일 입력 반복의 train 변동과 eval 결정성, mask RNG; 항상 개선되지 않음 |
| BatchNorm | batch 통계·학습 가능한 scale/offset·평가용 통계 | batch 구성/크기와 train/eval mismatch, 분산 산식·epsilon 확인 |
| residual | F(x)+x 또는 shape 정렬 projection | 동일 shape 블록의 gradient 경로 비교, skip 제거 ablation; skip만으로 안정 학습 보장 안 됨 |

BatchNorm 원문이 제시한 internal covariate shift 설명은 **저자의 동기/해석**과 실측 효과를 구별해 읽습니다. 자신이 그 인과 설명을 입증한 것처럼 쓰지 않습니다. [원문](https://arxiv.org/abs/1502.03167)

residual block의 Jacobian은 shape가 맞는 identity skip에서 `J_F+I`입니다. 신호의 직접 경로를 설명할 수 있지만 모든 깊이·초기화·optimizer에서 gradient가 건강하다는 보증은 아닙니다. [ResNet 원문](https://arxiv.org/abs/1512.03385)과 동일 parameter budget 여부·학습 곡선을 함께 비교합니다.

## 평가 모드도 모델 계약이다

validation이 실행 순서나 batch size에 따라 크게 달라지면 dropout/normalization 모드, 통계 업데이트, 전처리를 먼저 확인합니다. augmentation은 train과 evaluation의 정책을 구분합니다. seed를 고정했다고 학습/평가 상태 오류가 없어지지 않습니다.

완료 결과물에는 1D 필터의 손계산과 boundary 반례, ML의 regularization과 DL의 dropout/구조적 가정 차이, 확장 기능 하나의 동작/관측/제약 설계를 포함합니다. 원논문의 이미지 인식 결과는 별도 데이터·구조·학습 조건이 필요한 재현 단계로 남깁니다.
