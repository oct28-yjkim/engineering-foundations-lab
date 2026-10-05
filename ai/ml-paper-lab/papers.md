# ML 논문 지도: 가정·목적함수·일반화

[시작](README.md) · [8모듈 커리큘럼](curriculum.md) · [실행 범위](labs/README.md) · [공통 평가](../paper-labs-assessment.md)

아래 11편은 중요 개념을 연결하는 원전 목록이지 모든 ML 분야를 망라한 목록은 아닙니다. 확률적 생성모형·Bayesian inference·강화학습·인과추론·온라인 학습은 후속 분야로 남습니다. 읽는 순서는 연대순보다 커리큘럼의 선수 관계를 따릅니다.

**실행 표기**: `P`는 제공 Python 코드로 작은 계산/학습을 실행, `M`은 수기 계산·보고서 과제, `E`는 별도 구현/환경 확장입니다. `P`도 원논문 규모·데이터·benchmark 재현을 뜻하지 않습니다. 논문당 “주장 1개 → 독립 예상값 → 대조군 → 실패 조건”을 정합니다.

**출처 확인 범위(2026-10-05)**: 저자·학회·출판사 원문 또는 원논문의 기관 보관 사본을 우선했습니다. ML03·ML07은 초록/서지 중심, ML08은 기관 서지 중심, ML09는 원문 일부 문단·식까지 확인했습니다. 해당 항목에 본문 접근 한계를 명시했으며 미확인 식 번호를 만들지 않았습니다. 나머지도 아래 지정 구간 확인이지 전 페이지 검토/실험 재현 완료 선언은 아닙니다.

## ML01 · Perceptron

Frank Rosenblatt, **The Perceptron: A Probabilistic Model for Information Storage and Organization in the Brain**, 1958, *Psychological Review* 65(6), 386–408. [원문 사본](https://homepages.math.uic.edu/~lreyzin/papers/rosenblatt58.pdf)

- **읽을 부분**: “The Organization of a Perceptron”의 감각·연합·반응 단위와 학습 가정. 당시의 확률적 장치와 오늘날 단일 선형 분류기를 구별합니다.
- **핵심 주장**: 고정 규칙만 설계하는 대신 경험에 따라 연결을 바꾸는 분류 구조를 다룹니다.
- **실험 연결**: `M` 두 점의 오분류 업데이트를 검산하고 XOR에 단일 직선이 실패함을 보입니다. `P classification`은 logistic SGD 비교 기준이며 perceptron 구현은 아닙니다.
- **한계/반례**: 선형 분리 가능성, 특징 표현, label noise가 중요합니다. 현대의 수렴 정리·변형 업데이트를 이 원문이 모두 제공한다고 하지 않습니다.

## ML02 · Ridge

Arthur E. Hoerl, Robert W. Kennard, **Ridge Regression: Biased Estimation for Nonorthogonal Problems**, 1970, *Technometrics* 12(1), 55–67. [원문 사본](https://homepages.math.uic.edu/~lreyzin/papers/ridge.pdf)

- **읽을 부분**: §1–3, 식 (2.1)의 `(XᵀX + kI)⁻¹Xᵀy`, 고유값 방향의 축소와 ridge trace.
- **핵심 주장**: 비직교 설계에서 계수 추정의 분산을 줄이기 위해 bias를 허용합니다.
- **실험 연결**: `P ridge`의 1차원 OLS/ridge 계수·heldout MSE·train-only scaling을 손으로 검산합니다. `E` 상관된 다변량 특징을 만들어 조건수와 계수 분산을 비교합니다.
- **한계/반례**: 기본 1차원 LAB은 다중공선성 재현이 아닙니다. SSE/MSE, 절편의 penalty 제외, 특징 scale을 고정해야 λ를 비교할 수 있습니다. 축소가 모든 holdout에서 이기는 것은 아닙니다.

## ML03 · Lasso

Robert Tibshirani, **Regression Shrinkage and Selection via the Lasso**, 1996, *JRSS Series B* 58(1), 267–288. [출판사 초록·서지](https://rss.onlinelibrary.wiley.com/doi/pdf/10.1111/j.2517-6161.1996.tb02080.x) · [원문 스캔](https://homepages.math.uic.edu/~lreyzin/papers/lasso.pdf)

- **읽을 부분**: 잔차 제곱합과 `Σ|βj| ≤ t` 제약을 정의하는 부분, simulation 비교. **이번 확인은 초록·서지까지이며 스캔 본문은 판독하지 못했습니다.** 학습자는 원문에서 해당 위치를 확인해 페이지를 기록합니다.
- **핵심 주장**: L1 제약은 일부 계수를 정확히 0으로 만들 수 있어 축소와 변수 선택을 연결합니다.
- **실험 연결**: `M` 2차원 L1/L2 제약과 등고선의 접점을 계산합니다. `E` coordinate descent와 KKT/subgradient 검사를 구현합니다. 제공 `ridge`는 Lasso solver가 아닙니다.
- **한계/반례**: 상관 특징의 선택 안정성과 scale에 주의합니다. 변수 선택 결과를 원인 변수 발견으로 해석하지 않습니다.

## ML04 · Support-vector networks

Corinna Cortes, Vladimir Vapnik, **Support-Vector Networks**, 1995, *Machine Learning* 20, 273–297. [출판사 원문](https://link.springer.com/content/pdf/10.1007/BF00994018.pdf)

- **읽을 부분**: §2 optimal hyperplanes, §3 soft margin, §4 feature-space 내적의 계산. margin·slack·dual multiplier의 역할을 추적합니다.
- **핵심 주장**: 마진 최적화와 특징 공간의 내적을 결합해 분류 경계를 구성합니다.
- **실험 연결**: `M` 작은 선형 분류 문제의 제약과 support vector를 검산합니다. `P classification`의 logistic loss와 margin 목적을 비교하되 SVM을 실행했다고 하지 않습니다.
- **한계/반례**: kernel·C·정규화와 데이터 크기가 결과/비용을 바꿉니다. margin 점수는 확률이 아니며, 확률 보정은 별도 검증이 필요합니다.

## ML05 · Decision trees

J. R. Quinlan, **Induction of Decision Trees**, 1986, *Machine Learning* 1, 81–106. [출판사 원문](https://link.springer.com/content/pdf/10.1007/BF00116251.pdf)

- **읽을 부분**: §3 induction task, §4 ID3와 information gain, noise·불완전 속성을 다루는 논의.
- **핵심 주장**: 속성에 따른 반복 분할을 통해 해석 가능한 분류 규칙을 구성합니다.
- **실험 연결**: `M` 작은 범주형 표의 entropy와 gain을 계산합니다. `P ensembles`는 수치형 1차원 Gini stump를 학습하므로 ID3와 split 기준·깊이가 다릅니다.
- **한계/반례**: 탐욕적 선택은 전역 최적을 보장하지 않습니다. 식별자 같은 다수 범주 특징, noise, 동일 특징/서로 다른 label을 반례로 둡니다.

## ML06 · Random forests

Leo Breiman, **Random Forests**, 2001, *Machine Learning* 45, 5–32. [저자 원문](https://www.stat.berkeley.edu/~breiman/randomforest2001.pdf)

- **읽을 부분**: §2 strength/correlation, §3 무작위 특징, §4 out-of-bag 추정과 variable importance 논의.
- **핵심 주장**: 개별 tree의 예측력과 tree 간 상관을 함께 고려하는 무작위 tree 앙상블을 다룹니다.
- **실험 연결**: `P ensembles`에서 bootstrap 표본과 확률 평균을 검산합니다. `E` 여러 특징·깊은 tree·node별 feature subsampling·OOB를 추가한 뒤 단순 bagging과 비교합니다.
- **한계/반례**: 제공 코드는 **bagged stumps이지 전체 Random Forest가 아닙니다**. 더 많은 tree가 모든 데이터에서 정확도를 높이지 않으며 importance를 인과적 설명으로 쓰지 않습니다.

## ML07 · Gradient boosting

Jerome H. Friedman, **Greedy Function Approximation: A Gradient Boosting Machine**, 2001, *The Annals of Statistics* 29(5), 1189–1232. [저자 업로드·초록](https://www.researchgate.net/publication/2424824_Greedy_Function_Approximation_A_Gradient_Boosting_Machine) · [출판 식별자](https://doi.org/10.1214/aos/1013203451)

- **읽을 부분**: function-space 최적화와 stagewise additive model, loss별 pseudo-residual 알고리즘. **초록·서지와 업로드 존재는 확인했으나 본문 알고리즘은 미판독**이므로 식 번호는 학습자가 원문 확인 후 기록합니다.
- **핵심 주장**: 함수 공간의 하강 방향을 약한 학습기로 근사하며 additive model을 순차 개선합니다.
- **실험 연결**: `M` 제곱오차의 음의 gradient 한 단계와 learning rate를 검산합니다. `E` stump boosting을 구현합니다. `P ensembles`의 독립 bootstrap bagging과 혼동하지 않습니다.
- **한계/반례**: loss·depth·학습률·stage 수를 분리해야 합니다. 이 논문을 읽었다고 XGBoost/LightGBM의 구현·분산 동작까지 배운 것은 아닙니다.

## ML08 · k-means의 원전

J. MacQueen, **Some Methods for Classification and Analysis of Multivariate Observations**, 1967, *Proceedings of the Fifth Berkeley Symposium*, Vol. 1, 281–297. [UC Berkeley 원전 보관 목록](https://digicoll.lib.berkeley.edu/record/113015?v=pdf)

- **읽을 부분**: k-means 분할 목적과 관측 도착에 따른 중심 갱신 절차. **기관 서지는 확인했으나 원문 본문 열람은 실패**했습니다. 세부 정리·수렴 조건·식 번호는 확인 전 인용하지 않습니다.
- **학습 질문**: 군집 내 제곱거리를 줄이는 것과 업무적으로 유용한 군집을 찾는 것은 왜 다른가? 온라인 갱신과 batch assignment/update를 구별할 수 있는가?
- **실험 연결**: `P representation`은 **batch Lloyd 방식**의 2차원 k-means이며 MacQueen 원 알고리즘의 복제가 아닙니다. inertia·초기 중심·중심/label 순열을 관측합니다.
- **한계/반례**: K·scale·초기화·empty cluster 처리가 필요합니다. 원문 접근이 해결될 때까지 역사적 알고리즘 비교는 조사 과제로 남기고 CPU 코드의 독립 계산만 평가합니다.

## ML09 · PCA의 기하학

Karl Pearson, **On Lines and Planes of Closest Fit to Systems of Points in Space**, 1901, *Philosophical Magazine* 2, 559–572. [원문 사본](https://pca.narod.ru/pearson1901.pdf) · [출판 식별자](https://doi.org/10.1080/14786440109462720)

- **읽을 부분**: 직교거리 기준의 closest fit, §6의 주축과 식 (xv)–(xvii). **원문 검색 색인의 일부 식·문단 확인에 한정**되며 전 본문 검토는 아닙니다.
- **학습 질문**: 종속변수 방향의 회귀 잔차와 모든 좌표를 대칭적으로 취급하는 투영 오차는 어떻게 다른가?
- **실험 연결**: `P representation`에서 중심화·2×2 covariance·고유벡터·재구성 오차를 검산합니다. 현대 표기 코드이며 역사적 계산 절차 그대로의 재현은 아닙니다.
- **한계/반례**: 축의 부호는 임의이고 큰 분산이 중요한 label 정보를 뜻하지 않습니다. 표준화 유무와 모집단/표본 covariance의 분모를 명시합니다.

## ML10 · 평가와 모델 선택

Ron Kohavi, **A Study of Cross-Validation and Bootstrap for Accuracy Estimation and Model Selection**, 1995, *IJCAI*, 1137–1145. [저자 원문](https://ai.stanford.edu/~ronnyk/accEst.pdf)

- **읽을 부분**: cross-validation/bootstrap 정의, stratification, 추정 bias/variance와 모델 선택 실험.
- **핵심 주장**: 추정 방식의 성질과 선택된 모델의 품질을 실제 학습 문제에서 비교해야 합니다.
- **실험 연결**: `P ridge`의 train-only preprocessing과 의도적 누출을 비교합니다. `M` 동일 row의 중복·사용자별 묶음·시간 순서를 반영한 split을 설계합니다. `E` nested CV 실행기는 직접 추가합니다.
- **한계/반례**: 이 논문의 비교가 모든 dataset의 최적 fold 수를 정하지 않습니다. test set을 반복 선택에 사용하거나 시간/그룹 의존성을 무시하면 추정이 깨집니다.

## ML11 · 확률의 품질과 calibration

Alexandru Niculescu-Mizil, Rich Caruana, **Predicting Good Probabilities with Supervised Learning**, 2005, *ICML*, 625–632. [저자 원문](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf)

- **읽을 부분**: §2 Platt/isotonic calibration, 식 (1)–(6), Figure 7의 calibration 표본 수.
- **핵심 주장**: 좋은 분류 정확도와 좋은 확률은 다르며 보정의 효과는 모델·보정 데이터에 의존합니다.
- **실험 연결**: `P classification`의 동일 accuracy/상이한 Brier 예를 검산합니다. `M` reliability 표를 작성하고 train/calibration/test 계약을 만듭니다. `E` Platt 또는 isotonic fit을 추가합니다.
- **한계/반례**: 기본 LAB에는 calibration fitter가 없습니다. 작은 표본에서 유연한 보정이 과적합할 수 있으며 한 분포의 calibration이 분포 이동 후에도 유지된다고 보장하지 않습니다.

## 읽기 산출물

각 논문에 원문 버전·확인한 페이지, 기호와 shape, 가정 3개, 우리 실험과 다른 조건 3개를 남깁니다. 원문 접근이 막힌 경우 **읽지 못한 부분**을 그대로 기록하고, 2차 요약을 읽은 것만으로 본문/증명 검토를 대체하지 않습니다. 본문 미확인 항목은 접근 가능한 원전으로 검토가 보완되기 전까지 논문 재현 완료로 평가하지 않습니다.
