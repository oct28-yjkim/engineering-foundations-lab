# 일반화와 실험 설계

[ML 과정](../curriculum.md) · [논문 ML10과 ML11](../papers.md) · [실습](../labs/README.md)

## 무엇을 학습하는가

학습 데이터의 평균 손실을 줄이는 것과 미래 데이터의 오류를 줄이는 것은 다른 문제입니다. 경험 위험은 관측한 표본 위에서 계산하지만 실제 관심은 배포 시점의 분포에 있습니다. 일반화 논의에는 표본의 독립성, 학습/배포 분포 관계, 가설 공간과 선택 절차가 들어갑니다. 학습 loss가 감소했다는 사실만으로 이 조건들을 검증할 수 없습니다.

먼저 **예측 시점에 이용 가능한 정보**를 적습니다. 고객 이탈을 예측하면서 이탈 이후의 상담 결과를 feature로 넣거나, 한 사람의 여러 행을 train/test에 나누면 문제 정의 자체가 바뀝니다. 데이터가 적다는 이유로 정보 경계를 제거하지 않습니다.

## 학습과 평가의 상태 흐름

원본 단위/시간 정의 → split 고정 → train에서 전처리 fit → train 학습 → validation 선택 → 선택을 고정한 final test 순서입니다. 교차검증에서는 각 fold마다 전처리·특징 선택·모델을 다시 fit합니다. 바깥 평가와 안쪽 선택을 분리하는 nested CV는 별도 구현 과제이며 제공 runner에 포함하지 않습니다.

고정 train/validation/test는 유일한 정답이 아닙니다. 시간 예측에는 시간 순서가, 동일 사람의 새 행 예측에는 group 단위가 필요할 수 있습니다. random split과 시간 split의 차이가 “어느 방법이 더 정확한가”보다 “무엇을 추정하는가”의 차이라는 점을 설명합니다. ML10의 비교 조건을 현재 업무에 자동 적용하지 않습니다.

## 실행하고 관측하기

```text
python -B ai/ml-paper-lab/labs/lab.py --lab ridge
python -B ai/ml-paper-lab/labs/lab.py --lab classification
```

첫 실험에서 train-only scaler와 의도적으로 test 값을 포함한 scaler를 비교합니다. 누출한 경로가 반드시 더 좋은 점수를 내야 하는 것은 아닙니다. 확인할 불변식은 **test 값 변경이 학습된 전처리 상태를 바꾸지 않아야 한다**는 정보 경계입니다. 이 비교를 real-data 성능 개선 실험으로 보고하지 않습니다.

둘째 실험에서는 accuracy뿐 아니라 log loss와 Brier score를 읽습니다. 표본 100개 중 positive가 1개일 때 항상 negative로 예측하면 accuracy는 99%지만 positive recall은 0입니다. 이는 수기 반례이며 합성 runner의 데이터 수와 혼동하지 않습니다. threshold를 바꾸면 의사결정은 바뀌지만 확률 예측 자체가 개선된 것은 아닙니다.

## bias와 variance를 관찰하는 법

모델이 너무 제한적이어서 패턴을 못 잡는 것, 데이터가 조금 바뀌면 모델이 크게 흔들리는 것, 관측 노이즈가 있는 것은 구분할 현상입니다. 제곱 손실의 bias/variance 분해를 모든 metric에 그대로 적용하지 않습니다. 학습 곡선은 데이터 수·model capacity·regularization을 하나씩 바꾸고 train/validation 곡선을 함께 기록하는 추가 과제입니다.

seed 하나를 바꿔 좋아진 결과를 선택하는 것은 모델 선택입니다. 동일 seed 반복은 버그 재현에 유용하지만 통계적 반복 표본을 늘려주지 않습니다. 여러 실험을 비교할 때는 split을 짝지어 고정하고 모든 실패 run을 포함합니다.

## 흔한 증상과 진단

| 증상 | 먼저 가를 원인 | 확인/조치와 재검산 |
| --- | --- | --- |
| validation이 비현실적으로 좋음 | 중복·group 누출·target 이후 feature | split 원장과 전처리 fit 대상 확인, 격리된 새 평가로 비교 |
| train만 좋고 test가 나쁨 | 과적합·분포 이동·전처리 불일치 | 시점/slice/feature 분포와 학습곡선을 분리 조사 |
| accuracy는 같고 서비스 실패 증가 | 클래스 비율·비용·threshold 변화 | confusion matrix·확률 metric·업무 비용을 함께 비교 |
| seed마다 순위가 뒤집힘 | 작은 표본·불안정 최적화·선택 편향 | 사전 seed 목록과 동일 예산 반복, 결론 보류 가능 |

완료 결과물은 “누출 없는 baseline” 보고서입니다. ML10/ML11에서 읽은 주장 하나, 자신의 split 단위, 실패해야 할 누출 반례, 이 데이터로는 말할 수 없는 결론을 적습니다. [공통 평가](../../paper-labs-assessment.md)의 필수 관문을 적용합니다.
