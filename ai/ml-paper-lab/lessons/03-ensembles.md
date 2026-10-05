# 트리의 분할과 앙상블의 차이

[과정](../curriculum.md) · [논문 ML05부터 ML07](../papers.md) · [실습](../labs/README.md)

## 트리는 어떤 계산을 하는가

binary 분류 노드에서 Gini impurity는 `1−Σpₖ²`입니다. 분할 후보마다 왼쪽/오른쪽 impurity를 표본 수로 가중하고 가장 작은 후보를 고릅니다. 각 자식 impurity의 단순 평균은 크기가 다른 분할을 잘못 비교합니다. threshold는 정렬된 서로 다른 값 사이에 두며, 같은 점수 후보의 tie-break도 재현성 계약입니다.

ML05의 ID3는 정보 이득/entropy를 읽기 위한 원전입니다. 기본 코드는 수치 feature 한 개의 **Gini 기반 CART-style stump**로서 ID3 전체 구현이 아닙니다. 선택 기준, 연속/범주형 입력, missing 값, pruning을 구분합니다.

```text
python -B ai/ml-paper-lab/labs/lab.py --lab ensembles
```

split threshold·leaf 확률·예측과 bootstrap으로 얻은 stump들의 확률 평균을 비교합니다. leaf의 비율 추정과 final label threshold도 다른 단계입니다. 작은 완전 분리 데이터에서는 single stump가 이미 최선일 수 있어 bagging이 더 나빠질 수 있습니다.

## bagging Random Forest boosting

| 방법 | 다음 모델이 보는 것 | 집계와 핵심 가정 | 제공 상태 |
| --- | --- | --- | --- |
| bagging | 원 train에서 bootstrap 재표본 | 여러 추정의 평균/투표, 오차 상관이 높으면 이득 제한 | 작은 stump ensemble 실행 코드 |
| Random Forest | bootstrap 및 분할 때 feature 부분집합 등 | tree의 강도와 다양성을 함께 조절 | ML06 읽기·추가 구현 |
| gradient boosting | 현재 ensemble loss의 gradient 관련 목표 | 이전 모델을 보완하는 순차적 additive model | ML07 읽기·추가 구현 |

bootstrap은 test set을 재표본해서 학습하라는 뜻이 아닙니다. OOB 표본은 해당 tree의 학습에 사용되지 않은 train 원소이지만, OOB로 반복 튜닝하면 최종 독립 평가와 같은 지위를 갖지 않습니다. 동일 고객 여러 행이 있을 때 bootstrap 단위도 고민해야 합니다.

제곱 손실 boosting에서는 음의 gradient가 residual과 연결되지만 모든 loss에서 원래 y와 예측의 단순 차이를 학습하는 것은 아닙니다. shrinkage·tree depth·stage 수가 함께 용량을 정합니다. xgboost/lightgbm 등 특정 library의 동작을 이 기초 설명만으로 학습했다고 하지 않습니다.

## 관측하고 반증하기

먼저 tree 간 예측 차이와 틀리는 표본의 겹침을 관찰합니다. tree 수만 늘렸는데 개선이 없으면 표본 수·깊이·feature 다양성·noise·오차 상관을 구분합니다. feature importance는 인과 효과가 아니며 높은 cardinality/상관 feature에서 해석이 흔들릴 수 있습니다. permutation 분석도 validation에서 수행하고 상관 구조와 측정 조건을 기록합니다.

수동 추가 과제는 동일 split에서 stump depth 제한을 완화하거나 feature 후보 수 하나를 바꾸는 것입니다. tree 수·깊이·feature 수를 동시에 바꾸면 개선 원인을 분리하기 어렵습니다. train/validation·model size·예측 시간도 함께 측정합니다.

완료 기준은 stump 분할 점수 손계산, bagging이 실패/악화하는 사례, RF와 boosting의 상태 흐름 비교, 표본 단위와 정보 경계를 지키는 보고서입니다. 기본 fixture PASS를 ML06/ML07의 benchmark 재현으로 표시하지 않습니다.
