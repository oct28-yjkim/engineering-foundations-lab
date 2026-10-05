# 표현 학습과 DL로 넘어가는 이유

[과정](../curriculum.md) · [논문 ML08과 ML09](../papers.md) · [DL](../../dl-paper-lab/README.md)

## PCA는 무엇을 보존하는가

중심화한 X의 공분산에서 큰 eigenvalue의 eigenvector를 찾아 분산을 많이 보존하는 축으로 투영합니다. covariance의 `1/n`과 `1/(n−1)` convention은 eigenvalue 숫자에 영향을 주므로 기록합니다. basis의 부호가 반대여도 같은 부분공간입니다. 고유값이 같은 경우에는 basis 자체가 유일하지 않을 수 있습니다.

큰 분산이 예측에 중요한 신호라는 보장은 없습니다. 작은 분산 방향에 class 정보가 있거나 단위가 큰 feature가 지배하는 반례를 만듭니다. PCA fit에도 train-only 원칙이 적용됩니다. reconstruction error가 낮은 것과 분류·검색 품질이 좋은 것은 다른 질문입니다.

## k-means는 무엇을 최적화하는가

고정된 k에 대해 점을 가까운 중심에 할당하고 중심을 평균으로 갱신하며 within-cluster squared distance 합을 줄입니다. 전체 최적해를 보장하지 않고 초기값·scale·이상치·비구형 집단에 민감합니다. empty cluster 처리와 tie-break를 정해야 구현이 완성됩니다.

cluster 번호 0과 1이 바뀌어도 같은 partition일 수 있습니다. 평가에서는 번호 자체보다 함께 묶이는 관계나 적절한 label 정렬을 비교합니다. k가 커지면 inertia가 줄 수 있으므로 작은 inertia만으로 k를 고르거나 업무 의미가 좋다고 하지 않습니다.

```text
python -B ai/ml-paper-lab/labs/lab.py --lab representation
```

제공 코드는 **2차원 PCA와 작은 k-means**입니다. eigenvector 부호 불변·재구성/분산 관계와 cluster label 순열 불변을 확인합니다. high-dimensional randomized SVD·density clustering·대규모 최적화 구현은 아닙니다. ML08/ML09의 아이디어와 이 축소 구현의 선택을 구분합니다.

## feature engineering에서 representation learning으로

선형 모델은 주어진 feature의 조합을 학습합니다. PCA는 label 없이 표현을 구성합니다. DL의 hidden layer는 task loss가 역전파되어 표현 자체를 바꿉니다. 이 차이는 “차원이 크면 DL” 또는 “PCA 뒤에는 반드시 neural network”라는 규칙이 아닙니다.

XOR의 네 점 (0,0),(1,1)은 한 class, (0,1),(1,0)은 다른 class로 두면 단일 직선으로 완전히 나눌 수 없습니다. 사람이 interaction feature를 만들거나 비선형 kernel/tree를 쓰는 대안도 있습니다. MLP는 hidden nonlinearity를 학습하는 또 다른 대안입니다. 다음 [DL backprop LAB](../../dl-paper-lab/lessons/01-backprop-optimization.md)은 입력과 label을 −1/+1로 인코딩한 XOR 네 점을 실제 fitting합니다. 이를 미지 분포의 일반화 증명으로 취급하지 않습니다.

## ML 미니 연구

작은 합성 데이터의 scale·noise·상관 중 하나만 바꿉니다. raw-feature baseline과 하나의 변환을 같은 split에서 비교하고, PCA가 불리한 조건 또는 k-means의 의미 없는 군집을 기록합니다. 실험 대상은 새로 구현해야 하는 확장과 제공 runner의 회귀 테스트로 구분합니다.

최종 제출에는 데이터 생성 규칙, fit 정보 경계, objective와 업무 metric 차이, 독립 정답, 개선/악화 조건을 포함합니다. 이 보고서와 logistic gradient 검산이 [ML→DL 관문](../../ml-dl-llm-roadmap.md)의 핵심입니다.
