# ML과 DL을 시작하는 수학 및 실험 기초

[학습 경로](ml-dl-llm-roadmap.md) · [ML 시작](ml-paper-lab/README.md)

벡터·미분이 아직 낯설다면 **[수학 보충 경로](math-foundations/README.md)**부터 사용합니다. [진단 12문항](math-foundations/diagnostic.md)에서 틀린 영역을 찾고, 풀이가 있는 강의 → [무료 공식 자료](math-foundations/resources.md) → 다른 숫자의 재검산 문제 → [Python 수학 LAB](math-foundations/labs/README.md) 순서로 돌아옵니다. 정답만 맞추기보다 식의 의미와 계산 순서를 말로 설명합니다.

아래 선택 **4주·48시간**은 진단과 빠른 기초 순환의 계획이며, 처음 배우는 선형대수·미적분·확률론 전체를 4주에 끝낸다는 뜻이 아닙니다. 약한 영역은 보충 경로에서 1~2주 단위로 더 학습하고 재진단합니다. 이미 설명과 검산이 가능하면 바로 ML로 이동하며, 중간에 논문 식에서 막히면 해당 영역으로 돌아옵니다.

| 주 | 개념과 손계산 | 구현·통과 기준 |
| --- | --- | --- |
| 1 | 벡터·내적·행렬 곱·norm, shape·rank, 평균 제거 | X가 3×2, W가 2×4일 때 XW의 shape와 원소 하나를 손계산; feature scale이 거리와 penalty를 바꾸는 예 |
| 2 | 도함수·편미분·chain rule·gradient, log/exp | scalar loss의 analytic gradient와 central difference 비교; step 크기를 바꾸면 오차가 항상 줄지 않는 이유 |
| 3 | 조건부 확률·기댓값·분산, likelihood·log loss | 작은 분포의 합과 NLL, 독립과 비상관 구분; 표본 수와 관측 단위 기록 |
| 4 | train/validation/test, seed, baseline, 가설·반증 | split 후 전처리 fit, metric 분모와 실패 포함, 코드/조건/실측 분리 보고서 |

## 진단 문제와 검산 기준

**벡터:** x=(1,2), w=(3,-1), b=0.5이면 z=x·w+b=1.5입니다. 세 데이터에 같은 w를 적용할 때 parameter는 여섯 개가 아니라 두 개이며, 각 데이터의 gradient 기여를 합산하거나 평균합니다. batch 평균 여부는 learning rate 해석에도 영향을 줍니다.

**미분:** L(w)=(2w-3)²/2이면 dL/dw=2(2w-3), w=1에서 -2입니다. w를 작게 늘리면 loss가 감소해야 합니다. `h=1e-5`의 `(L(w+h)-L(w-h))/(2h)`와 비교하고, h가 너무 작을 때 부동소수점 반올림이 나타날 수 있음을 기록합니다. ReLU 꺾임에서는 central difference를 미분의 정답으로 가정하지 않습니다.

**확률:** 정답 token의 확률이 0.25이면 NLL은 `-ln(0.25)`≈1.3863 nats입니다. 같은 조건에서 두 token의 정답 확률이 0.5와 0.25이면 평균 NLL≈1.0397, perplexity≈2.8284입니다. tokenizer와 평가 token 집합이 다르면 perplexity 숫자를 단순 비교하지 않습니다.

**누출:** train 값 [0,2]의 평균은 1입니다. test 값 [100]을 더하면 전체 평균은 34가 됩니다. 이 평균을 전처리 학습에 사용하면 평가 데이터가 학습 파이프라인에 영향을 준 것입니다. test label을 사용하지 않았다는 사실만으로 누출이 없어지지 않습니다. 누출이 항상 점수를 올리는 것은 아니며, 문제는 정보 경계가 깨진 것입니다.

## 논문 식을 코드로 바꾸는 습관

기호마다 shape·단위·범위·학습 여부를 씁니다. `i`가 표본인지 feature인지, `t`가 optimizer step인지 token 위치인지 구분합니다. 미니배치 loss가 합인지 평균인지, bias가 regularization 대상인지, log 밑과 epsilon 위치가 무엇인지 구현 전에 고정합니다.

한 식을 옮긴 뒤에는 크기 2~4인 값으로 검산합니다. 원래 구현과 같은 버그를 가진 두 함수의 일치보다 손계산·독립 closed form·유한차분·불변식의 조합이 강한 근거입니다. 하나의 방법이 모든 오류를 잡지는 못합니다.

참고로 전처리의 정보 경계는 [scikit-learn 공식 누출 안내](https://scikit-learn.org/stable/common_pitfalls.html)와 대조합니다. 실제 기본 LAB은 scikit-learn을 설치하거나 호출하지 않습니다.
