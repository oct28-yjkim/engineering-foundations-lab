# ML 시스템 LAB 검증 기록

[시작](README.md) · [실행·예상값](labs/README.md) · [관측·진단](operations.md)

검증일: **2026-10-05**. Windows, CPython **3.12.14**, Python 표준 라이브러리에서 실행했습니다. Python 3.10 문법 파싱은 통과했지만 다른 Python runtime·OS에서의 실행을 확인한 것은 아닙니다. 외부 API·클라우드·회사 데이터·credential·패키지 설치를 사용하지 않았습니다.

## 실행과 결과

저장소 루트에서 실행합니다. 기본/`--plan`은 I/O 없는 계획 출력이고, `--run` 및 아래 테스트 명령은 **실제 loopback 서버를 기동**합니다.

```text
python -B ai/ml-systems/labs/lab.py
python -B ai/ml-systems/labs/lab.py --plan
python -B ai/ml-systems/labs/lab.py --run
python -B -O ai/ml-systems/labs/lab.py --run
python -B -m unittest discover -s ai/ml-systems/labs -p test_*.py
python -B -O -m unittest discover -s ai/ml-systems/labs -p test_*.py
```

계획 출력, 일반 실행, `-O` 실행 모두 exit 0으로 완료했습니다. **45개 테스트가 일반·`-O` 모드에서 각각 통과**했습니다. 핵심 검산은 제거 가능한 `assert`에 의존하지 않습니다. 다음은 실제 HTTP 실행 결과입니다.

| 관측·검산 | 실제 결과 |
| --- | --- |
| 요청 | `127.0.0.1` 임시 포트로 48회, 정상 42회·의도적 계약 거부 6회 |
| 계약 | schema 400, type/dimension 422, stale/feature-version/preprocessing-version 409 |
| 회복 | 각 거부 직후 정상 입력으로 200, 확률 약 0.880797·baseline 버전 복원 |
| 기준 모델 | 전체 12/12, core 10/10, edge 2/2; 독립 literal oracle 대조 |
| 후보 모델 | 전체 11/12, core 10/10, edge 1/2; aggregate 하한 0.9 통과·slice gate 거부 |
| Gate·복귀 | `promote:false`, `slice_regression:edge`; baseline의 기존 12응답과 완전 일치 |
| 지표 | 요청/준비 응답 48, 의도적 오류 비율 6/48=0.125, latency 표본 48 |
| 종료 | `server_closed:true`; socket close와 소유 thread 종료 확인 |

HTTP 테스트에는 실제 timeout 뒤 정상 회복, 실패 응답 뒤 회복, malformed/큰 수치 입력·body 제한·요청 budget·cleanup도 포함됩니다. baseline 또는 후보의 일부 확률을 잘못 바꾸는 mutation 테스트는 예상 정답 검증이 전체 실행을 실패시키는지 확인합니다. redirect·응답 크기 등 일부 client 경계 테스트는 mock이며 실제 HTTP 통합 검사와 구별됩니다. 실행 도중 application 파일 I/O 및 비-loopback bind/connect 차단도 검사합니다.

## HTTP와 별도로 확인한 순수 fixture

- **Point-in-time:** prediction time 100에서 올바른 값은 1. event time만 확인하면 당시 미도착한 available time 105의 값 99를 선택하는 누출을 검출했습니다.
- **Label 지연:** coverage 2/4·관측 accuracy 2/2에서 label 도착 완료 후 coverage 4/4·accuracy 2/4로 바뀝니다. 미도착 label은 임의 정답으로 채우지 않습니다.
- **Drift:** 평균 절대 feature 1.5→3.5여도 accuracy 1 유지. 같은 입력에서 label 규칙을 반전하면 feature marginal은 같은데 accuracy 0입니다.

이 결과는 실제 feature store, stream processor, drift detector, label 수집 시스템의 통합 실행 기록이 아닙니다. 관련 구현은 기본 runner에 없습니다.

## 해석하지 말아야 할 것

모델은 사람이 정한 고정 합성 weight입니다. 새 학습·외부 artefact 다운로드를 수행하지 않았습니다. 후보 평가는 격리된 프로세스 내부 모델 pointer 전환이며 실제 운영 승격·다중 replica canary·인과적 A/B 실험이 아닙니다. 작은 slice 2개로 보편적인 승격 threshold나 통계적 유의성을 정할 수 없습니다.

관측 latency는 handler 진입부터 응답 구성까지이며 client/wire latency·동시성·부하·장기 tail을 측정하지 않습니다. 숫자는 실행마다 달라지므로 benchmark나 SLO 달성 증거로 사용하지 않습니다. TLS/IAM·내구성·HA·보안 격리·실트래픽 비용·자동 재학습·클라우드 배포도 미검증입니다.

변경 후 기존 ML 38개·DL 41개·LLM 50개 테스트도 각각 일반/`-O`에서 재실행해 통과했습니다. 이 회귀 결과를 기존 트랙의 논문 전체 재현이나 외부 환경 검증으로 확대하지 않습니다.
