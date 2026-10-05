# ML 원리와 논문 실험실

[ML → DL → LLM 경로](../ml-dl-llm-roadmap.md) · [기초 진단](../foundations.md)

데이터를 주면 모델이 학습한다는 설명에서 출발해 **목적함수·가정·특징·일반화·평가를 직접 검산**하는 과정입니다. 회귀/분류, margin과 regularization, tree/앙상블, 차원 축소/군집을 연결합니다. DL이나 LLM보다 오래된 알고리즘이라는 이유로 baseline을 생략하지 않습니다.

16주·8모듈·주 12시간, 약 192시간을 계획 예산으로 삼습니다. 논문 목록을 완독하는 것보다 작은 가설을 구현하고 실패 조건을 설명하는 것이 중요합니다. 기초 수학은 [별도 4주 보충](../foundations.md)으로 분리합니다.

## 먼저 실행하고 설명하기

```text
python -B ai/ml-paper-lab/labs/lab.py --lab all
python -B -m unittest discover -s ai/ml-paper-lab/labs -p test_lab.py -v
```

저장소 루트, Python 3.10 이상, 표준 라이브러리만 사용합니다. CPU에서 실제 작은 모델을 fitting하고 수치·분할 계약을 검사합니다. 네트워크·데이터 다운로드·GPU/API·Docker는 필요 없습니다. [환경](../paper-labs-environment.md)과 [실제 검증 기록](../paper-labs-validation.md)을 확인합니다.

| 자료 | 읽고 실행할 내용 |
| --- | --- |
| [논문 지도](papers.md) | 원전·선정 이유·읽을 부분·제공 LAB과 미구현 범위 |
| [커리큘럼](curriculum.md) | 8모듈·선수 조건·산출물·통과 기준 |
| [일반화와 실험 설계](lessons/01-generalization.md) | split·누출·bias/variance·모델 선택 |
| [지도학습과 목적함수](lessons/02-supervised.md) | OLS/ridge·logistic·margin·L1/L2 |
| [트리와 앙상블](lessons/03-ensembles.md) | 분할 기준·bagging·Random Forest·boosting 차이 |
| [표현과 DL 연결](lessons/04-representation.md) | PCA·k-means·feature와 representation learning |
| [CPU LAB 4개](labs/README.md) | ridge, classification, ensembles, representation |
| [공통 평가](../paper-labs-assessment.md) | 독립 정답·누출·실험/원논문 결과 분리·진입 관문 |

## 제공 범위

기본 코드는 작은 ridge/OLS·logistic 학습, CART 방식의 한 단계 stump와 bootstrap bagging, 2차원 PCA·k-means입니다. SVM 최적화기, Lasso solver, 전체 Random Forest/GBM, nested CV 실행기, 실제 산업 dataset benchmark를 제공하는 것은 아닙니다. 이들 기능도 논문·강의에서 동작·관측·제약을 배우며 직접 구현/추가 환경 과제로 표시합니다.

관측은 loss뿐 아니라 split별 오류, scale·계수 변화, probability와 threshold, tree 간 차이, reconstruction/inertia와 실패 사례를 함께 봅니다. 실행 결과가 좋다는 이유만으로 일반화나 원논문 결과를 재현했다고 하지 않습니다.

다음 단계는 [DL 논문 실험실](../dl-paper-lab/README.md)입니다. [ML→DL 관문](../ml-dl-llm-roadmap.md)을 통과한 뒤 모델의 특징을 사람이 정하는 경우와 hidden representation을 학습하는 경우를 비교합니다.
