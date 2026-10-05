# 지도학습의 목적함수와 최적화

[과정](../curriculum.md) · [논문 ML01부터 ML04 및 ML11](../papers.md) · [CPU LAB](../labs/README.md)

## 선형 회귀와 ridge

회귀의 선형성은 feature에 대한 선형 결합을 뜻합니다. x² 같은 feature를 사람이 추가할 수도 있지만, 그 변환 역시 train/evaluation 계약의 일부입니다. 제곱 오차는 큰 잔차에 큰 비용을 부여하므로 이상치와 목표 단위에 민감합니다.

제공 1차원 ridge는 **Σ(yᵢ−wxᵢ−b)² + αw²**를 최소화하고 intercept b에는 penalty를 주지 않습니다. 중심화한 데이터의 해는 `w=Σ(xᵢ−x̄)(yᵢ−ȳ)/(Σ(xᵢ−x̄)²+α)`, `b=ȳ−wx̄`입니다. loss를 평균으로 바꾸면 같은 숫자 α가 다른 regularization 세기를 뜻합니다. 여러 feature의 실제 solver는 inverse를 직접 만드는 방식보다 안정적인 분해를 검토해야 하며 제공 코드는 그 일반 solver가 아닙니다.

```text
python -B ai/ml-paper-lab/labs/lab.py --lab ridge
```

α=0의 독립 직선 정답, α 증가 때의 계수 shrinkage, train-only scale과 raw 단위의 예측을 비교합니다. 무잡음 직선처럼 OLS가 정확한 fixture에서는 ridge가 heldout 오류를 늘릴 수 있습니다. 이를 버그로 고쳐서 ridge가 이기게 만들지 않습니다. regularization은 특정 가정과 데이터 조건에서 선택하는 절충입니다.

## logistic 회귀와 확률

`z=w·x+b`, `p=1/(1+exp(-z))`로 binary 확률을 만듭니다. 한 표본의 NLL은 `softplus(z)−yz`이며 z에 대한 도함수는 `p−y`입니다. 큰 양/음 z에서 `log(1+exp(z))`를 그대로 계산하지 않고 안정한 식을 씁니다. 확률의 threshold와 손실을 구분합니다.

```text
python -B ai/ml-paper-lab/labs/lab.py --lab classification
```

초기/최종 loss, coefficient 변화, gradient의 유한차분 오차, heldout 확률 metric을 기록합니다. 예측 label이 같아도 확률이 0.51에서 0.99로 변하면 log loss는 크게 달라질 수 있습니다. Brier는 `(p−y)²`의 평균이며 calibration만을 단독 측정하는 지표는 아닙니다. calibration curve/binning·별도 보정 데이터 실험은 추가 과제입니다.

## perceptron과 margin을 비교하기

perceptron은 오분류에 반응하는 갱신 규칙을 통해 선형 분리를 학습합니다. 수렴 논의에 필요한 선형 분리 가정과 noisy/nonseparable 데이터에서의 동작을 구분합니다. 확률을 출력하는 logistic 회귀와 동일하지 않습니다.

soft-margin SVM의 한 convention은 `||w||²/2 + CΣmax(0,1−yᵢ(w·xᵢ+b))`, 여기서 y는 −1/+1입니다. C와 ridge α의 숫자를 직접 비교하지 않습니다. kernel은 similarity 계산으로 feature 공간의 내적을 바꾸지만 모든 임의 similarity가 적합한 kernel인 것은 아닙니다. support vector·margin·비분리 반례를 ML04에서 읽고 작은 수기 예로 검산합니다. **perceptron/SVM solver는 제공 runner 밖의 직접 구현 과제**입니다.

## L1과 L2를 왜 구분하는가

L2는 계수를 연속적으로 줄이고, L1은 특정 조건에서 정확히 0인 계수를 만들 수 있습니다. 표준화와 상관 feature가 선택/해석에 미치는 영향을 함께 봅니다. scalar 목적 `0.5(w−a)²+λ|w|`의 해 `sign(a)max(|a|−λ,0)`를 수기로 확인한 뒤 ML03의 다변량 문제와 비교합니다. 이 단일 식은 전체 Lasso 구현이 아닙니다.

## 실패를 분류하기

비유한 loss는 데이터·exp/log 범위·learning rate를, loss 정체는 gradient 부호/scale·feature scale·iteration budget을 먼저 봅니다. gradient 검산이 틀리면 optimizer 종류를 바꾸지 않습니다. 학습 성공 후에도 잔차의 시점/slice 구조, class별 오류, probability 품질을 확인합니다.

제출물은 목적함수 convention, 한 parameter의 손미분, finite difference, regularization이 불리한 반례, 선형 표현으로 해결할 수 없는 입력입니다. 다음 DL에서 바뀌는 것은 이 실험 기준이 아니라 **feature 표현도 학습한다는 점**입니다.
