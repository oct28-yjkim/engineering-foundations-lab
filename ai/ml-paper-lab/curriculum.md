# ML 커리큘럼: 데이터에서 검증 가능한 학습 주장까지

[시작](README.md) · [원전 11편](papers.md) · [전체 경로](../ml-dl-llm-roadmap.md) · [환경](../paper-labs-environment.md) · [평가](../paper-labs-assessment.md)

**8모듈 × 2주 × 주 12시간 = 16주·192시간**의 계획입니다. 각 모듈은 원문/수학 6h, 구현/실험 10h, 코드/반례 4h, 기록/리뷰 4h로 배분합니다. 부족한 선수 지식은 [기초 4주](../foundations.md)로 보충합니다. 기간은 전문가 자격이나 모든 논문 재현을 보장하지 않으며, 다음 단계 진입은 아래 관문으로 판단합니다.

`P` 제공 CPU LAB, `M` 수기·설계·보고서, `E` 별도 구현/환경 확장입니다. 논문을 읽는 과제와 동명의 알고리즘이 실행 코드에 있다는 주장을 구분합니다. 기본 명령은 저장소 루트의 `python -B ai/ml-paper-lab/labs/lab.py --lab <ID>`이며 자세한 계약은 [LAB 안내](labs/README.md)를 따릅니다.

| 모듈·주차 | 선수 조건·원전 | 목적 → 내부 계산 | 실행/관측 → 제약·통과 증거 |
| --- | --- | --- | --- |
| ML-M01 · 1–2 | Python 리스트·평균·확률, ML10/ML01 | 일반화 문제를 정의하고 train/validation/test, empirical risk, parameter/hyperparameter를 구별 | `P ridge`의 누출 반례를 관측. `M` 그룹/시간 split·기준 모델·평가 protocol 작성. 전처리 fit이 test를 보지 않는 데이터 흐름을 그리면 통과 |
| ML-M02 · 3–4 | M01·내적·미분, ML02 | OLS 정규방정식과 L2 penalty, bias/variance, intercept와 scaling | `P ridge`: 1차원 closed form·MSE를 독립 계산. `E` 다변량 공선성/조건수. λ가 test MSE를 악화시키는 예와 SSE/MSE penalty 차이를 설명 |
| ML-M03 · 5–6 | M02·로그·조건부 확률, ML01/ML04 | 선형 score → sigmoid 확률 → log loss → gradient, margin과 probability 차이 | `P classification`: 실제 logistic SGD·유한차분·heldout accuracy/Brier. `M` perceptron update와 SVM 제약. logistic 실행을 SVM 재현이라 부르지 않고 loss·threshold를 구별 |
| ML-M04 · 7–8 | M02–03, ML03/ML10 | L1/L2 기하·sparsity·model selection·과적합 | `P ridge` 재사용. `M` L1 제약 접점, fold 안 전처리, nested CV 설계. `E` Lasso solver. λ 선택은 validation 내부, test는 최종 1회 평가로 고정 |
| ML-M05 · 9–10 | M01·확률·분할, ML05/ML06 | 정보량/Gini → greedy split → bootstrap 평균 → decorrelation | `P ensembles`: 1D Gini stump·bootstrap·heldout 확률. `M` ID3 gain 검산. `E` 깊은 tree/node별 feature sampling/OOB. bagging·RF·ID3 차이와 평균이 개선되지 않는 경우 설명 |
| ML-M06 · 11–12 | M03/M05, ML07/ML11 | 순차적 잔차 보정과 독립 bagging 차이; discrimination과 calibration | `M` squared-loss boosting 한 단계·reliability 표·분리된 calibration set. `P classification`은 accuracy/Brier 대조만. `E` GBM·Platt/isotonic fit. 모델/보정기가 본 split을 감사 |
| ML-M07 · 13–14 | M02·고유벡터·거리, ML08/ML09 | 중심화·covariance·직교 투영; assignment/update와 local optimum | `P representation`: 2D PCA·batch Lloyd k-means·재구성 오차/inertia. 축 부호와 cluster label 순열 불변 비교. `M` 큰 분산과 예측 정보의 반례; 역사적 원전과 구현 차이를 기록 |
| ML-M08 · 15–16 | M01–07 핵심 관문 | 한 가설을 검증 가능한 미니 연구로 축소하고 학습된 특징으로 확장 | 네 LAB 중 하나에 변화 1개·대조군·ablation·실패 fixture를 추가하는 `E` 또는 실행 가능한 기존 코드로 `M` 실험 설계. 실제 실행/미실행 구분, 재현 보고서와 ML→DL 구술 관문 |

## 강의 연결과 초심자 진행법

- M01/M04: [일반화와 실험 설계](lessons/01-generalization.md). 표본·분할·누출을 먼저 배우고 모델 복잡도로 넘어갑니다.
- M02–04: [지도학습과 목적함수](lessons/02-supervised.md). 숫자 2–4개로 한 번 계산 → 코드의 같은 값을 추적 → 다른 입력의 반례 순서입니다.
- M05–06: [트리와 앙상블](lessons/03-ensembles.md). 독립 학습/평균과 순차 보정의 데이터 의존성을 구별합니다.
- M07–08: [표현과 DL 연결](lessons/04-representation.md). 고정 feature map과 label을 이용해 함께 학습하는 표현의 차이를 설명합니다.

수식이 막히면 먼저 symbol·dimension·입력/출력·목적함수 한 줄을 적습니다. 코드가 통과했지만 설명할 수 없다면 seed나 데이터 한 점을 바꾸기 전에 결과를 예측해 봅니다. 논문 초록/서지만 확인 가능한 ML03/ML07/ML08과 부분 판독 ML09의 읽기 한계는 [논문 지도](papers.md)에 표시했습니다.

## 제공 코드와 고급 확장의 경계

| 기본 제공 `P` | 반드시 이해하되 자동 제공하지 않는 `M/E` |
| --- | --- |
| 1차원 OLS/ridge, train-only scaler와 누출 대조 | 다변량 QR/SVD solve·조건수·Lasso/KKT·regularization path |
| binary logistic SGD, gradient check, accuracy/Brier | perceptron/SVM solver·kernel·PR/ROC·threshold 비용·확률 보정 fit |
| 1차원 Gini stump와 bootstrap bagging | ID3 entropy·깊은 CART·feature-subsampled RF·OOB·GBM |
| 2차원 PCA와 batch Lloyd k-means | 고차원 SVD·whitening·online MacQueen·k-means++·안정성 연구 |
| 고정된 작은 train/heldout fixture | nested CV 실행기·그룹/시간 split·실데이터 불균형·분포 이동 benchmark |

채택 판단은 “항상 최신 모델”이 아니라 데이터 양·선형성·해석성·계산/지연 비용·확률 품질로 내립니다. 예를 들어 작은 표본에서는 큰 모델보다 정규화된 선형 baseline을 먼저 검증할 수 있고, 축소된 PCA가 label 정보를 지우면 비채택이 타당합니다. 선택 이유와 반례를 함께 제출합니다.

## ML → DL 관문

아래를 모두 설명하고 [공통 평가](../paper-labs-assessment.md)의 증거를 제출한 뒤 [DL 과정](../dl-paper-lab/curriculum.md)으로 이동합니다.

1. 학습 목적과 평가 지표를 분리하고 baseline·분할·전처리 fit 범위를 재현할 수 있다.
2. ridge 계수 또는 logistic gradient를 코드 출력과 독립적인 계산으로 검산한다.
3. penalty·scale·sample reduction 변경이 같은 hyperparameter의 의미를 바꿈을 설명한다.
4. accuracy가 같아도 확률 품질이 다르고, bagging/RF/boosting은 다른 알고리즘임을 보인다.
5. PCA/k-means의 비식별성·초기화·데이터 가정과 실패 조건을 설명한다.
6. 원논문 결과·우리 예상값·측정값·미실행 확장을 구분한 최소 보고서를 제3자가 다시 실행한다.

다중 seed 신뢰구간·외부 dataset·더 나은 baseline·통계적 검정·이론 증명은 연구 깊이를 늘리는 후속 과제입니다. 2주 M08에 이들을 모두 완료했다고 처리하지 않습니다. 실제 실행 상태와 제한은 [검증 기록](../paper-labs-validation.md)에 남깁니다.
