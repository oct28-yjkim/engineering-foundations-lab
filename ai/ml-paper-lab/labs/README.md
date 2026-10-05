# ML 논문을 작은 실제 실험으로 연결하기

이 LAB은 모형의 결과를 하드코딩해 보여주는 시뮬레이터가 아닙니다. 합성 데이터로 **OLS/Ridge 적합, logistic SGD 학습, bootstrap stump 학습, PCA·k-means 계산**을 실제 수행하고 별도 oracle과 비교합니다. 다만 논문의 원래 데이터·규모·성능을 재현하는 코드는 아닙니다. [논문 지도](../papers.md)의 ML01–ML11 중 연결되는 질문을 선택하고, 제공 코드와 추가 재현 과제를 구분합니다.

## 실행과 경계

Python 3.10+ 표준 라이브러리만 사용합니다. CPU에서 짧게 실행되며 파일 읽기·쓰기, 네트워크, 패키지 설치, 데이터 다운로드, 모델/API 호출이 없습니다. 출력은 stdout JSON입니다. 정상 실행은 exit 0, 검증/인자 오류는 `FAIL` JSON과 exit 1입니다. 핵심 검증에 Python `assert`를 사용하지 않습니다.

저장소 루트에서 실행합니다.

```text
python ai/ml-paper-lab/labs/lab.py --lab all
python ai/ml-paper-lab/labs/lab.py --lab ridge
python ai/ml-paper-lab/labs/lab.py --lab classification --seed 17 --epochs 120
python ai/ml-paper-lab/labs/lab.py --lab ensembles --seed 17 --trees 31
python ai/ml-paper-lab/labs/lab.py --lab representation --seed 17 --iterations 50
python -m unittest discover -s ai/ml-paper-lab/labs -p test_lab.py -v
python -O -m unittest discover -s ai/ml-paper-lab/labs -p test_lab.py
```

| 인자 | 기본값 | 허용 범위·의미 |
| --- | --- | --- |
| `--lab` | `all` | `ridge`, `classification`, `ensembles`, `representation`, `all` |
| `--seed` | 17 | 0–2³²−1, 전역 RNG가 아닌 실험별 `random.Random` |
| `--epochs` | 120 | 1–500, logistic 학습의 epoch 수; epoch당 6 SGD step |
| `--trees` | 31 | 1–101, bootstrap stump 개수; 각 표본은 6회 복원추출 |
| `--iterations` | 50 | 1–100, k-means Lloyd 반복 상한; 미수렴은 `converged:false` |

샘플은 코드 안에 고정되어 있으며 임의 파일·대규모 배열·외부 경로 인자는 없습니다. 함수 수준 샘플 상한도 128개입니다. JSON의 `elapsed_seconds`는 이번 실행의 내부 측정값이지 성능 benchmark나 보장 시간은 아닙니다. 같은 seed·인자·Python 환경에서는 `results`를 비교하며 실행 시간까지 같다고 요구하지 않습니다.

## 1. Ridge: 정규화가 언제나 좋은가?

학습 데이터는 x=`[-2,-1,0,1,2]`, y=`2x+1`, held-out은 x=`[3,4]`입니다. 학습 x에서만 평균·모표준편차를 구해 양쪽을 변환합니다. 목적함수는 **SSE + αw²**, 절편은 벌점에서 제외합니다. 평균 손실을 쓰는 다른 구현의 α와 숫자만 비교하지 않습니다.

1. 학습 평균 0·표준편차 √2, 변환한 학습 평균 0을 확인합니다.
2. α=0의 OLS와 α=2의 Ridge를 실제 적합합니다. 표준화 좌표에서 계수 절댓값이 줄어드는지 확인합니다.
3. OLS의 held-out MSE는 0, Ridge는 `200/49 ≈ 4.08163`입니다. 이 noiseless fixture에서는 Ridge가 더 나쁩니다.
4. 반례에서만 held-out x까지 scaler fit에 넣습니다. 평균이 1, 학습 z 평균이 −0.5가 되고 Ridge의 held-out MSE는 `800/81 ≈ 9.87654`로 달라집니다.
5. 같은 반례의 OLS 예측은 변하지 않습니다. 절편이 있는 무벌점 1D 선형 회귀는 이 affine scaling 변화에 불변입니다. **정보 누출이면 모든 알고리즘의 숫자가 반드시 좋아지거나 바뀐다는 주장을 하지 않습니다.**

관측할 것: scaler의 fit 대상, 계수의 좌표계, train/held-out 경계, 목적함수의 합/평균, 벌점을 받는 파라미터. 추가 과제는 잡음·상관 feature·validation fold를 도입하는 것이며 현재 코드는 다변량 회귀·교차검증·모델 선택을 구현하지 않습니다.

## 2. Classification: 좋은 정확도가 좋은 확률인가?

0/1 레이블 6개로 logistic 모델의 가중치·절편을 SGD로 학습합니다. sigmoid의 양/음수 분기와 안정적인 softplus 형태의 log loss를 사용합니다. 큰 logit에 무조건 `exp(z)`를 호출하지 않습니다.

1. 초기 정규화 학습 손실 `log(2)`와 학습 후 손실을 비교합니다.
2. 해석적으로 계산한 gradient와 중심 유한차분을 대조합니다. 최대 오차 기준은 `1e-7`입니다.
3. held-out 4개에서 **벌점 없는 log loss, accuracy, Brier, positive recall**을 따로 봅니다. 정규화된 학습 손실과 held-out log loss를 같은 양으로 취급하지 않습니다.
4. 불균형 반례 `[0×19,1×1]`에서 상수 확률 0.01과 0.05를 비교합니다. 둘 다 accuracy=0.95, positive recall=0이지만 Brier는 각각 0.0491과 0.0475입니다. 분류 임계값은 0.5입니다.

기본 seed 17·120 epochs의 관측 예: 720 SGD step, 학습 손실 약 `0.08807`, held-out accuracy=1, Brier 약 `0.03307`, log loss 약 `0.15110`입니다. 작은 분리 가능한 fixture의 수치이며 일반화·현업 calibration·불균형 문제 해결의 증거가 아닙니다. LR scheduler, class weighting, 조기 종료, calibration fitting은 추가 과제입니다.

## 3. Ensembles: 복원추출과 split을 실제로 보기

1D CART-style stump가 모든 인접 feature 값 사이의 threshold를 검사하고 **표본 수로 가중한 Gini**가 최소인 split을 선택합니다. 동률이면 작은 threshold를 먼저 선택합니다. 각 잎의 양성 비율을 예측 확률로 씁니다.

1. 독립 toy oracle x=`[0,1,2,3]`, y=`[0,0,1,1]`의 threshold=1.5, weighted Gini=0을 검산합니다.
2. 6개 학습 데이터에서 6회 복원추출한 표본을 tree마다 만들고 stump를 적합합니다. `bootstrap_unique_counts`가 draw 수와 다른 이유를 설명합니다.
3. tree별 잎 확률을 평균합니다. hard-label 다수결과 다른 집계이며, 확률 0.4·0.8의 평균 0.6이라는 독립 검사가 있습니다.
4. single stump와 bagging의 held-out accuracy/Brier를 비교합니다. 기본 fixture에서는 둘의 accuracy가 1이지만 bagging Brier는 약 0.02367, single stump는 0입니다. 개선을 강제로 통과 조건에 넣지 않습니다.

**제공 범위는 bootstrap bagging of decision stumps입니다.** Random Forest의 feature subsampling·다층 CART·OOB 추정·GBM의 순차 residual fitting은 구현하지 않습니다. 관련 논문을 읽고 이 차이를 적는 것은 중요하지만, 그 독서가 해당 알고리즘의 실행 완료를 뜻하지는 않습니다.

## 4. Representation: 부호·cluster 번호 대신 불변량 확인

PCA는 2D 데이터를 중심화하고 모공분산(`/n`)의 두 고유값과 첫 고유벡터를 계산합니다. x=`[(1,2),(2,4),(3,6),(4,8)]`의 평균은 `(2.5,5)`, 고유값은 `(6.25,0)`입니다. 표본공분산(`/n−1`)의 고유값과 혼동하지 않습니다.

- 기준 방향 `(1,2)/√5`와 내적의 **절댓값**이 1인지 확인합니다. 고유벡터와 projection 부호를 함께 반전해도 재구성은 같습니다.
- k-means는 8개 점의 두 묶음으로 실행합니다. seed로 첫 중심을 선택한 후 farthest-first로 다음 중심을 선택하고 Lloyd assignment/update를 반복합니다. **k-means++의 확률적 초기화가 아닙니다.**
- 기대 중심은 순서와 무관하게 `(0.5,0.5)`, `(8.5,8.5)`, partition은 `{0,1,2,3}/{4,5,6,7}`, inertia=4입니다. cluster 번호를 바꿔도 같은 결과입니다.
- inertia의 비증가·iteration 상한·`converged`를 구분합니다. 상한 1에서는 중심이 기대값이어도 수렴 확인 반복을 완료하지 않아 `converged:false`입니다.

동일한 점만 있어 분산이 0인 PCA나 서로 다른 점보다 많은 cluster 요청은 명시적으로 거부합니다. 빈 cluster는 자동 수리하지 않고 실패로 보고합니다. 낮은 inertia는 의미적으로 좋은 표현·공정한 군집·전역 최적해를 보장하지 않습니다. scaling, 다른 초기화, 여러 seed, 비구형 군집 반례는 다음 과제입니다.

## 검증과 제출

테스트는 literal 해, 정상방정식 residual, 유한차분 gradient, 부호/label 불변성, 음성 fixture, seed 재현성, CLI 상한, socket 및 파일 I/O 차단을 검사합니다. 이는 테스트가 통과한 합성 범위의 정확성 증거이며 논문 수치·외부 라이브러리·실데이터 검증을 대신하지 않습니다.

제출물은 **논문 질문→제공/추가 구현 경계→손으로 계산한 oracle→seed·인자·실행 결과→한 변인 반례→아직 입증하지 않은 것** 순서로 작성합니다. 코드가 제공되지 않은 논문은 설계/독서 상태로 남기고, 원논문 재현과 작은 원리 확인을 구별합니다.
