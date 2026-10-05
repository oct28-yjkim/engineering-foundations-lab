# 수학 보충 LAB 검증 기록

[시작](README.md) · [실행](labs/README.md) · [자료 확인 범위](resources.md)

검증일: **2026-10-05**. Windows, CPython **3.12.14**, 표준 라이브러리에서 실행했습니다. Python 3.10 문법 파싱도 확인했지만 Python 3.10 runtime·다른 OS에서 실행했다는 뜻은 아닙니다. 아래 명령은 저장소 루트 기준이며 `python`은 해당 환경의 Python 실행 파일입니다.

## 실제 실행

```text
python -B ai/math-foundations/labs/lab.py --lab all
python -B -O ai/math-foundations/labs/lab.py --lab all
python -B -m unittest discover -s ai/math-foundations/labs -p test_lab.py
python -B -O -m unittest discover -s ai/math-foundations/labs -p test_lab.py
```

- `all`의 4개 LAB을 일반/최적화 모드에서 PASS 확인했습니다. `vectors`, `derivatives`, `probability`, `optimization` 개별 CLI도 각각 PASS입니다.
- **23개 테스트**가 일반 모드와 `-O` 모드에서 각각 통과했습니다. 핵심 검산은 Python의 제거 가능한 `assert`에 의존하지 않습니다.
- 테스트는 작은 입력의 독립 예상값과 부호/shape/분모/잘못된 입력을 검사하고, 핵심 실험에서 application 파일 I/O·socket을 차단한 상태도 확인합니다. Python 자체의 코드/표준 라이브러리 로딩을 금지했다는 뜻은 아닙니다.

| LAB | 실행에서 확인한 값·반례 |
| --- | --- |
| 벡터 | 내적 1, 행렬 곱 `[[2,2,-1],[6,4,-1]]`, 비단위 축 투영 `[3,0]`, 잔차 직교, shape 오류 거부 |
| 미분 | 연쇄법칙 gradient 약 -2, 공유 경로 약 26, 평균 half-MSE gradient 약 `[-1.5,-1]`; ReLU 0의 중앙차분 0.5는 도함수가 아님 |
| 확률 | Bayes `90/(90+495)=2/13`, 분포/표본분산 1/2, 평균 NLL 약 1.039721 nat, perplexity 약 2.828427 |
| 최적화 | 초기 손실 50.5, 작은/큰 학습률 첫 손실 0.49005/200.47045, 안정 경로 100 step 손실 약 0.066990, log-sum-exp 약 1000.313262 |

별도 검토에서 문서의 핵심 계산 19건과 행렬 곱을 다시 계산했고, 코드의 다른 입력 검산 6건·negative 입력 10건도 확인했습니다. 진단/재검산은 사람의 학습용 문제이며 자동 채점이나 숙련도 인증은 아닙니다.

## 범위와 한계

논문 식을 작은 숫자로 이해하는 검산입니다. 실제 데이터의 통계적 유의성·calibration, 신경망 학습·대규모 행렬 성능, 임의 정밀도·모든 극단값의 수치 안정성을 검증하지 않았습니다. CPU만으로 가능한 이 실습과 다른 도구의 실제 서비스 운영 LAB은 목적이 다릅니다.

외부 자료는 [공식 링크와 읽기 범위](resources.md)에 별도로 기록했습니다. 전체 강의 시청·교재 전체 검토를 뜻하지 않으며, MML PDF 본문은 확인 환경의 크기 제한으로 전체를 열지 못했습니다. LAB 실행에는 외부 자료 다운로드·패키지 설치·GPU·API 호출이 없었습니다.
