# ML과 DL 논문 LAB의 실행 환경

[전체 경로](ml-dl-llm-roadmap.md) · [ML 실습](ml-paper-lab/labs/README.md) · [DL 실습](dl-paper-lab/labs/README.md) · [검증 기록](paper-labs-validation.md)

기본은 **Python 3.10 이상·표준 라이브러리·CPU·오프라인**입니다. Docker, NumPy, scikit-learn, PyTorch, GPU, 모델 API 키 없이 실행합니다. 실제 small-model fitting과 수치 검산이 포함되며 원논문의 대규모 benchmark 재현은 아닙니다. Python 설치는 자동 수행하지 않습니다.

저장소 루트에서 다음 명령을 실행합니다. `-B`는 Python bytecode cache 생성을 막습니다. 학습 데이터와 초기 조건은 코드 내 합성 fixture이고 기본 runner는 파일·모델 다운로드·네트워크 요청·checkpoint 저장을 하지 않습니다. stdout JSON을 기록하려면 사용자가 별도로 비밀 없는 실험 폴더를 선택합니다.

```text
python -B ai/ml-paper-lab/labs/lab.py --lab all
python -B ai/dl-paper-lab/labs/lab.py --lab all
python -B -m unittest discover -s ai/ml-paper-lab/labs -p test_lab.py -v
python -B -m unittest discover -s ai/dl-paper-lab/labs -p test_lab.py -v
```

Windows에서 `python`이 Store 별칭이면 설치된 실제 Python 경로를 사용합니다. 실행 가능한 lab 이름과 고정 학습 budget은 각각의 실습 안내를 봅니다. CLI가 노출하지 않은 `--epochs`, 외부 파일, device 옵션 등을 추측해 넣지 않습니다. 기본 실습은 제공 fixture와 iteration 수 안에서 끝나며, 더 큰 실험은 별도 변경으로 기록합니다.

## 범위와 실행 상태

| 구분 | 제공/준비 | 올바른 완료 표현 |
| --- | --- | --- |
| ML-CPU | ridge·logistic fitting, stump bagging, PCA·k-means 코드 | 해당 합성 fixture의 학습·계산·평가 검산 |
| DL-CPU | scalar autodiff와 작은 MLP·convolution·RNN, optimizer 비교 | 해당 작은 network의 gradient·업데이트·정해진 task 결과 |
| FRAMEWORK-EXTENSION | 학습자가 별도 환경에 구현/패키지 고정 | 같은 초기값·loss reduction·split에서 reference와 비교한 결과 |
| DATA-EXTENSION | 허가된 dataset·별도 split·다운로드 budget 필요 | 해당 데이터/관측 단위에 대한 일반화 검증 |
| GPU-EXTENSION | 선택 GPU/driver/framework/precision과 비용 상한 필요 | 실제 device에서 측정한 해당 조건의 품질·자원 결과 |
| PAPER-REPRODUCTION | 논문 조건·데이터/코드 revision·차이표 필요 | 재현한 주장 및 재현하지 못한 조건을 함께 보고 |

새 ML/DL 기본 코드와 기존 [LLM CPU 모형](llm-paper-lab/environment.md)은 서로 독립 실행합니다. 파일명이 같은 `lab.py`·`test_lab.py`이므로 각각의 `-s` 경로로 테스트하며, 한 Python process에서 모두 `import lab` 하는 통합 명령은 제공하지 않습니다.

## 확장 환경의 계약

기본 LAB을 돌리기 위해 패키지를 추가하지 않습니다. framework 확장을 선택하면 별도 venv, Python/framework 정확한 버전, 설치 출처와 lock, dataset hash, CPU/GPU·driver·dtype를 기록합니다. tutorial의 최신 설치 명령을 고정 버전이라고 보고하지 않습니다. GPU가 필요한지 먼저 메모리와 시간 budget으로 판단하며 유료 자원 생성이나 API 호출은 이 저장소가 자동 수행하지 않습니다.

실제 데이터를 추가할 때는 사람/세션/문서/시간의 독립 단위로 split합니다. 개인·회사 데이터, credential, 사용자 대화나 raw checkpoint에 포함된 민감 정보를 커밋하지 않습니다. 결과 파일을 외부 서비스에 업로드하는 기능도 기본 경로에 없습니다.

## 실행이 실패하면

문법/CLI 오류 → 허용된 명령과 Python 버전, 비유한 loss → 수치 입력과 step size, gradient 불일치 → loss reduction·parameter 공유·초기화, seed 재실행 불일치 → RNG 소비 순서를 먼저 확인합니다. 기대 threshold를 실제 결과에 맞춰 바꾸는 것은 복구가 아닙니다. 변경 전후 fixture·명령·실제 결과를 보존하고 [평가 규칙](paper-labs-assessment.md)에 따라 원인을 적습니다.
