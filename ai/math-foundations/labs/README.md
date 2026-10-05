# 손계산과 연결하는 수학 검산 LAB

[수학 시작](../README.md) · [12문항 진단](../diagnostic.md) · [보충 자료](../resources.md)

Python 3.10 이상 표준 라이브러리만 사용합니다. 기본은 **CPU에서 작은 수를 계산하는 오프라인 수학 실험**이고 모델 학습이나 서비스 운영 실험은 아닙니다. 파일·네트워크·설치·데이터 다운로드가 없습니다. 계산 결과를 보기 전에 손으로 예상값을 적습니다.

```text
python -B ai/math-foundations/labs/lab.py --lab all
python -B ai/math-foundations/labs/lab.py --lab derivatives
python -B -m unittest discover -s ai/math-foundations/labs -p test_lab.py -v
```

저장소 루트에서 실행하며 `vectors`, `derivatives`, `probability`, `optimization` 또는 `all`만 선택합니다. 진단 문항과 다른 숫자로 같은 개념을 검산합니다. 결과의 `expected`와 `observed`를 비교하고 차이가 허용되는 이유까지 설명해야 합니다. PASS 출력을 진단 문제의 이해 여부와 동일시하지 않습니다.

## 1. Vectors

내적 `[1,2]·[3,-1]=1`을 두 항으로 풀고, 행렬 X(2×2)와 W(2×3)의 결과가 2×3인지 먼저 적습니다. projection은 x=[3,4]를 축 [2,0]에 투영해 [3,0]을 얻습니다. 축을 단위벡터로 가정하지 않으므로 `(x·u)/(u·u)`가 필요합니다. 남은 residual=[0,4]와 축의 내적은 0이어야 합니다.

코드는 길이가 다른 벡터를 zip으로 조용히 자르지 않고 오류로 처리합니다. 비정형 행렬·0 방향·NaN·boolean 입력도 거부합니다. 이 계산은 embedding 의미 품질이나 실제 데이터의 PCA를 평가하는 실험이 아닙니다.

## 2. Derivatives

`L(w)=(2w−3)²/2`에서 w=1의 기울기는 −2입니다. `(L(w+h)−L(w−h))/(2h)`와 비교합니다. 공유 경로 `u=2w`, `L=u²+u`의 w=3 기울기 26도 검산합니다. 두 표본의 **평균 half-MSE**에서 w,b의 미분은 각각 −1.5,−1이며 sum/mean을 바꾸면 값도 달라집니다.

h를 1e-2부터 1e-8까지 바꾼 오차를 관찰하되, 작은 h가 항상 좋은 것은 아닙니다. ReLU의 0에서 central difference는 0.5지만 좌/우 기울기는 0/1이므로 미분 가능하지 않습니다. 0.5를 수학적 도함수의 정답으로 채택하지 않습니다. 실제 autodiff와 신경망 학습은 [DL backprop](../../dl-paper-lab/labs/README.md)에서 이어집니다.

## 3. Probability

합성 부품 10,000개 중 실제 결함 100개, 검사의 true-positive rate 0.9, false-positive rate 0.05를 가정합니다. true positive 90, false positive 495이므로 양성 중 결함일 확률은 `90/(90+495)=2/13`입니다. 가정한 비율로 만든 수기 표이지 실제 관측 데이터가 아닙니다. 검사 민감도와 양성의 신뢰도를 같은 확률로 쓰지 않습니다.

[1,3]의 population variance는 1, 표본 불편분산은 2입니다. 분모 n/n−1을 비교합니다. 정답 token 확률 0.5,0.25의 평균 NLL은 ln(8)/2 nats, perplexity는 √8입니다. 이 배열은 한 분포의 모든 확률이 아니라 서로 다른 평가 위치의 **정답 확률**입니다.

## 4. Optimization

`q(x,y)=(x²+100y²)/2`의 초기점 (1,1)에서 loss=50.5입니다. gradient step의 rate=0.01은 첫 loss를 0.49005로 줄이고 rate=0.03은 200.47045로 늘립니다. 두 방향의 curvature가 다른 상황이며 learning rate 숫자를 목적함수 scale과 분리해 고르지 않습니다.

100회 반복의 x는 0.99¹⁰⁰, y는 0입니다. 한 방향이 느리게 줄어드는 이유를 설명합니다. `exp(1000)`의 overflow와 peak를 뺀 log-sum-exp의 유한 결과도 비교합니다. 이 작은 이차식은 실제 신경망의 수렴·최적화기 순위·GPU 성능을 입증하지 않습니다.

## 오류와 제출

정답을 먼저 예상하고, 값·shape·단위·계산 순서 중 무엇을 잘못 이해했는지 기록합니다. 값이 다르면 threshold부터 넓히지 않습니다. 손계산, 코드의 식, 독립 테스트를 순서대로 대조합니다. [진단](../diagnostic.md)의 해당 영역과 재검산 문제로 돌아가 설명까지 맞춘 뒤 ML/DL로 복귀합니다.

수치 검산은 고정된 작은 입력 범위입니다. float64 기반 Python 실수의 한계, 극단 scale·큰 행렬·복잡한 모델·실데이터는 별도입니다. 실제 검사와 미검증 범위는 [검증 기록](../validation.md)에 남깁니다.
