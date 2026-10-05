# ML DL 추가와 LLM 연결 검증 기록

검증일 **2026-10-05**, Windows amd64, CPython **3.12.14**, Python 표준 라이브러리. 신규 ML/DL 코드를 실제 실행하고 기존 LLM 모형도 회귀 검사했습니다. 아래 숫자는 논문에서 옮긴 benchmark가 아니라 이 저장소의 고정 합성 fixture 실측입니다.

[학습 경로](ml-dl-llm-roadmap.md) · [환경](paper-labs-environment.md) · [ML LAB](ml-paper-lab/labs/README.md) · [DL LAB](dl-paper-lab/labs/README.md)

## 수행한 검사

| 검사 | 결과 | 의미/한계 |
| --- | --- | --- |
| ML `--lab all` | 4개 PASS | 1D 회귀/분류·stump bagging·2D PCA/k-means의 실제 fitting/계산 |
| DL `--lab all` | 4개 PASS | 작은 MLP·공유 필터·Elman RNN 학습과 optimizer update |
| ML 단위 테스트 | 일반 **38개**, `-O` **38개** PASS | 독립 정답·negative 입력·scale/상수 feature·범위 검사 |
| DL 단위 테스트 | 일반 **41개**, `-O` **41개** PASS | 손미분·유한차분·공유 graph·BPTT·학습·causal 조건 |
| 기존 LLM 회귀 | 모형 6개, 일반 **50개**·`-O` **50개** PASS | 기존 수학 모형 동작 유지, Transformer 학습 아님 |
| application I/O | ML/DL 테스트에서 socket·파일 접근 차단 후 기본 실행 PASS | 네트워크·데이터 다운로드 없음; OS 보안 sandbox 인증은 아님 |
| 개별 CLI 선택 | ML 4개·DL 4개 각각 실행 PASS | `all`과 개별 경로의 결과 구분 |
| Python 3.10 문법 | 새 Python 파일 4개 AST parse PASS | Python 3.10 runtime 실행은 하지 않음 |
| 서지·문서 연결 | ML 11·DL 12 ID, Markdown 324개·내부 링크 2,322개·fence 오류 0 | 외부 링크의 미래 가용성/전문 완독 보장 아님 |

새 테스트는 **79개**, 기존 LLM 회귀까지 **129개**입니다. 일반/최적화 모드에서 같은 suite를 반복한 것을 새로운 독립 테스트 258개라고 세지 않습니다. 단위 테스트 개수 자체가 논문 재현 범위를 뜻하지 않습니다.

## 실제 관측값

ML seed는 17, DL seed는 20261005입니다. 보류 입력은 코드에 공개된 교육용 fixture이고 대규모 통계 추정을 위한 독립 benchmark가 아닙니다.

| 실험 | 실측 | 해석 경계 |
| --- | --- | --- |
| ridge | OLS heldout MSE 0, α=2 ridge 약 4.08163, test 포함 scaler ridge 약 9.87654 | 누출/regularization이 반드시 점수를 높이는 것은 아님 |
| classification | 정규화 학습 loss 0.693147→0.088066, 보류 Brier 약 0.0330725 | 작은 분리 가능한 합성 데이터; calibration 전체 검증 아님 |
| ensembles | single stump Brier 0, 31-stump bagging 약 0.0236733 | bagging이 항상 더 좋다는 가정 없음 |
| representation | PCA eigenvalues 6.25/0, k-means inertia 4·2회 반복 | 2차원 fixture; semantic quality·전체 최적해 보장 아님 |
| backprop | XOR MSE 1.119219→0.00140889, train 4/4·근방 보류 8/8 | 학습하지 않은 새로운 XOR 조합의 일반화가 아님 |
| optimization | 목적함수 13→SGDM 약 1.91e-9 / Adam 약 0.000160051 | 서로 다른 고정 learning rate, optimizer 순위 benchmark 아님 |
| convolution | MSE 4.78→약 2.47e-13, 보류 신호 최대오차 약 8.11e-7 | 선형 공유 필터 한 층; 영상 분류/LeNet 재현 아님 |
| sequence | 학습 CE 1.096456→0.00322157, 보류 CE 약 0.0501105, teacher-forced 12/12 및 12-step rollout 일치 | 같은 3-symbol transition 규칙; 장기 기억·자연어 품질 증거 아님 |

DL의 fixture별 gradient 최대 절대오차는 약 2.08e-11~4.49e-11, ML logistic은 약 3.06e-11입니다. 이는 해당 smooth 함수·float 연산·유한차분 간격의 결과이며 모든 dtype/scale/non-smooth 지점에 그대로 적용하지 않습니다.

## 독립 검토에서 고친 항목

- PCA에서 절대 off-diagonal cutoff 때문에 작은 scale의 상관 방향을 잃던 계산을 angle 기반으로 수정했습니다. 크기 1e-9~1e6, 양/음 상관에서 정규화한 고유방정식 residual·재구성 오차를 회귀 검사합니다.
- constant feature도 α>0이면 ridge의 유일해가 생기는 경우를 허용했습니다. α=0 singular 거부와 α=2의 `(w,b)=(0,1.5)` 정답을 별도로 검사합니다.
- gradient norm clipping과 실제 parameter update 상한이 같지 않다는 설명을 보완했습니다. momentum/Adam 상태와 learning rate를 함께 봅니다.

## 재실행과 아직 하지 않은 것

명령은 [공통 환경](paper-labs-environment.md)에 있습니다. 일반 테스트 명령에 `-O`를 추가해 최적화 모드도 확인할 수 있습니다. 결과에는 자신의 실행일·Python/OS·code revision·명령·실측을 추가하고 이 기록을 새 실측으로 덮어쓰지 않습니다.

실데이터 다운로드, scikit-learn/PyTorch 비교, GPU·분산 학습, 외부 모델/API, SVM/Lasso/RF/GBM 전체 구현, dropout/BN/ResNet/LSTM/Transformer/BERT 학습, 원논문 benchmark 재현은 **미실행/미제공 확장**입니다. 기본 tiny model 학습 성공과 구별합니다. 기존 제품·Compose·회사 자원에는 접근하거나 변경하지 않았습니다.

서지와 읽을 구간은 [ML 원전 지도](ml-paper-lab/papers.md)·[DL 원전 지도](dl-paper-lab/papers.md)에 기록했습니다. 일부 오래된 원전의 초록/서지·부분 판독만 확인된 경우도 해당 항목에 명시했습니다. 접근 가능한 링크를 연결한 것과 전 페이지 판독·실험 재현은 같은 상태가 아닙니다.
