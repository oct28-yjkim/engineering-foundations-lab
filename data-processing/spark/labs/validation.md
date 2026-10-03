# Spark·Databricks 추가분의 검증 기록

검증일: 2026-10-04. Windows, CPython 3.12.14. 아래는 이 저장소에서 수행한 검증이며 학습자가 앞으로 수행할 과제와 구분한다.

| 검사 | 결과 | 의미와 한계 |
| --- | --- | --- |
| CPU 실험 4개, 일반 실행 | PASS | skew/집계, version merge, watermark, 가상 budget의 모형 계약 |
| 같은 CPU 실험의 `python -O` 실행 | PASS | 핵심 검사가 최적화로 제거되는 `assert`에 의존하지 않음 |
| `test_offline_lab.py` | 40개 PASS | 모형의 정상·경계·음성 입력; 실제 Spark/Delta 검증 아님 |
| `test_runner_contract.py` | 30개 PASS | 경로·버전·환경·파일·mock streaming·실패 처리; JVM 미사용 |
| `spark_runner.py --help` | PASS | 설치 없는 CLI 사용법 확인 |
| Python 3.10 문법으로 AST 파싱 | 4개 파일 PASS | 문법 검사이며 Python 3.10 런타임 실행을 대신하지 않음 |
| PySpark 미설치 상태의 실제 실행 요청 | 예상대로 ERROR, exit 1 | run directory 생성 없이 사전 조건 실패; 엔진 성공으로 세지 않음 |
| 기존 LLM paper lab 회귀 테스트 | 50개 PASS | 기존 CPU 모형 테스트와의 회귀 확인 |
| Delta SQL | 정적 검토만 | source/target conflict guard, tombstone, EXCEPT ALL 정답 검사를 검토; 관리형 SQL 미실행 |

재현 명령은 저장소 루트 기준이다. Python 3.10 문법 호환성과 실제 Python 3.10 런타임 실행은 별도 항목이며, 이 검증의 실제 Python은 3.12.14다.

```text
python -B data-processing/spark/labs/offline_lab.py --lab all
python -B -O data-processing/spark/labs/offline_lab.py --lab all
python -B -m unittest discover -s data-processing/spark/labs -p "test_*.py" -v
python -B data-processing/spark/labs/spark_runner.py --help
python -B -m unittest discover -s ai/llm-paper-lab/labs -p "test_*.py" -v
```

일부 Windows 제한 sandbox에서 Python 임시 폴더의 전용 ACL 때문에 파일쓰기 테스트가 접근 거부되었다. 이를 테스트 통과로 처리하지 않고, 승인된 일반 사용자 실행 범위에서 최종 전체 70개 테스트를 실행해 통과했다. 파일쓰기 테스트는 전용 `lab-workspaces/spark-contract-tests` 아래 자신이 만든 대상만 사용한다. 시스템 권한이나 ACL을 완화하지 않았다. Python 3.10/3.11의 junction 감지와 접근 거부 경계는 mock 계약으로도 확인했다.

## 아직 검증하지 않은 것

- Java·PySpark가 설치되지 않아 Spark 4.0.4 실제 배치/정상 스트리밍 재시작은 미실행이다.
- 실제 Delta engine, Databricks SQL·Runtime, Unity Catalog 권한, Photon, Auto Loader, cloud 비용과 복구는 미검증이다.
- Spark/Delta upstream 소스 경로·고정 ref 확인은 빌드나 upstream 테스트 성공이 아니다.
- 계정, cluster, warehouse, table, catalog 또는 기타 원격 리소스를 생성하지 않았다. 제품 설치·학습용 cloud/model API 실행·결제도 수행하지 않았다. 공식 문서·소스 확인을 위한 웹 조회는 실습 실행과 별개다.

실제 엔진 실습의 [준비·출력·범위](README.md)와 [Databricks SQL 사용 조건](../../../platforms/databricks/labs/README.md)을 따른 뒤, 성공·실패·skip을 구분한 새 검증 기록을 작성한다.
