# Spark 실험실: 원리 모델 → 실제 로컬 엔진 → 선택 플랫폼 확장

**기본은 CPU·Python 표준 라이브러리다.** Java, Spark, Docker, GPU, API 키, Databricks 계정 없이 4개 원리 모델을 실행한다. 실제 Spark 엔진은 별도의 선택 단계이며, 모델의 성공을 엔진·Delta Lake·Databricks의 검증 결과로 바꾸어 기록하지 않는다.

| 단계 | 제공물 | 직접 검증하는 범위 | 검증하지 않는 범위 |
| --- | --- | --- | --- |
| `OFFLINE` | [offline_lab.py](offline_lab.py), [test_offline_lab.py](test_offline_lab.py) | 명시한 수학·업무 계약의 결정론적 반례 | Spark 실행계획·분산 장애·Delta 트랜잭션 |
| `LOCAL-SPARK` | [spark_runner.py](spark_runner.py) | 6행 배치 및 파일 소스 스트리밍의 정상 재시작 | 분산 클러스터·Kafka·강제 종료 복구·Databricks |
| `CONTRACT-TEST` | [test_runner_contract.py](test_runner_contract.py) | 설정·경로·fixture·실패 처리의 정적/mock 계약 | PySpark/JVM 실제 실행 |
| `PLATFORM-OPTIONAL` | [Databricks 실험 가이드](../../../platforms/databricks/labs/README.md) | 학습자가 별도 승인한 격리 환경의 실제 증거 | 이 저장소가 계정·리소스·결제를 자동 생성한다는 의미 |

## 1. 설치 없이 시작

저장소 루트에서 Python 3.10 이상으로 실행한다. 전체 데이터는 합성이며 원리 실험은 파일을 읽거나 쓰지 않고 네트워크를 사용하지 않는다. Python 자체의 일반적인 import 캐시는 별개다.

```bash
python data-processing/spark/labs/offline_lab.py --lab all
python -m unittest discover -s data-processing/spark/labs -p "test_offline_lab.py" -v
```

선택 실행값은 `partition-skew`, `merge`, `watermark`, `budget`, `all`이다. `assert` 최적화 제거에 의존하지 않으므로 `python -O`에서도 실험의 핵심 검사 조건은 실행한다.

### A. partition-skew: 부하와 응답시간을 구분

합성 240행을 SHA-256 기반의 **자체** 4개 파티션으로 배치한다. Spark의 Murmur3 해시를 재현한 것이 아니다. hot key만 8개 salt로 분리한 뒤, 원래 key별 `(sum, count)`를 재결합한다. 전후 파티션 행 수와 결과의 일치가 관측값이다.

- salt는 업무 key를 바꾸는 것이 아니라 부분 집계의 내부 key다. 2단계 집계로 원래 key의 결과를 복원한다.
- 부분 집계 `(sum=100,count=1)`과 `(sum=0,count=9)`의 전체 평균은 `10`이다. 부분 평균을 단순 평균하면 `50`으로 틀린다.
- 파티션 행 수의 균등함은 실행시간 단축의 증명이 아니다. 직렬화·셔플·부분 집계 overhead, 값 크기, executor 자원, hot key의 실제 분포를 측정해야 한다.
- 선택 실험: salt 수 1/2/4/8/16을 비교하고, 모든 key에 무조건 salt를 적용했을 때 늘어나는 중간 key 수를 기록한다. median·distinct·ordered aggregation에도 같은 재결합식이 성립하는지 반례를 찾아라.

### B. merge: 버전·동률·삭제의 업무 계약

이 실험은 SQL `MERGE` 구현이 아니다. `(key, business_version)`을 사용하는 별도의 애플리케이션 계약이다. 동일 key에서는 가장 큰 버전이 남고, 관측 가능한 동일 버전의 payload가 충돌하면 거부한다. 동일 배치를 다시 넣어도 상태는 바뀌지 않는다.

- tombstone도 버전을 가진 상태로 보존한다. `delete v3` 다음 `update v2`가 늦게 도착해도 부활하지 않는다.
- `update v4`에 의한 재생성은 이 예제에서는 허용한다. 업무가 금지한다면 계약 자체를 바꿔야 한다.
- source의 중복을 입력 순서로 임의 해결하지 않는다. 실제 Delta 실험에서는 원본 중복 검증, 선택 runtime의 `MERGE` semantics, 동시 writer 충돌, 트랜잭션 경계를 따로 측정한다.
- 최신 상태만 보관하므로 폐기된 과거 버전의 payload와 나중에 온 과거 payload의 불일치까지 증명하지는 못한다. 역사적 충돌 검증에는 별도의 immutable ledger가 필요하다.

### C. watermark: 도착 순서와 event time 분리

정수 초 단위·10초 tumbling window·5초 delay의 **명시적 단일 입력 모델**이다. batch 진입 시점의 `W = 이전 batch까지 관측한 최대 event time - 5`를 쓴다. 이 모델에서는 `t < W`만 버리고 `t == W`는 수용한다. `[start,end)`별 count를 만든 뒤 `end <= W`인 window를 내보내고 마지막에 max event time을 갱신한다.

1. `(e1,2),(e2,12)` 입력: 아직 watermark 없이 수용한다.
2. `(late,3),(boundary,7),(future,25)` 입력: 진입 `W=7`, `late`만 버린다.
3. 빈 batch: `W=20`, `[0,10)` count 2와 `[10,20)` count 1을 내보낸다. `[20,30)` count 1은 남는다.
4. 빈 batch를 반복해도 event time이 진행되지 않으므로 마지막 window는 닫히지 않는다.

이 모델의 경계 비교 연산, batch 시점, multi-input 정책을 Spark의 일반 보장으로 인용하지 않는다. Spark에서는 operator, output mode, trigger, watermark propagation, state cleanup을 고정하고 실제 `lastProgress`/state metrics와 소스로 반증해야 한다. event ID 중복 제거도 구현하지 않았으므로 같은 ID를 두 번 주면 두 번 센다. 임의 미래 heartbeat를 넣는 것은 실제 이벤트 의미와 지연 허용 범위를 바꾸므로 운영 처방으로 쓰지 않는다.

### D. budget: 비용 모델과 강제 중단은 다름

`units = (workers × worker_units_per_hour + driver_units_per_hour) × hours × attempts`로 계산한다. 각 시도가 같은 시간 동안 모든 자원을 사용한다고 가정한 **가상 자원 단위**다. DBU·통화 가격·청구 API가 아니다.

예시 `workers=2, hours=0.5, worker_rate=2, driver_rate=1, cap=4`는 한 번에 `2.5 units`, 전체 재시도 한 번을 더하면 `5 units`다. 첫 시도는 cap 이내이고 두 시도는 초과한다. 이 코드는 리소스를 생성하거나 중단하지 않는다. 저장소·네트워크·idle startup·최소 과금 단위는 제외되어 있다.

## 2. 실제 Spark 선택 실험의 고정 기준

교재 기준은 **Apache Spark/PySpark 4.0.4 + Java 17 또는 21 + 이 코드의 Python 3.10 이상**이다. Spark upstream의 Python 지원 하한과 이 코드의 문법 하한은 다른 계약이다. Databricks Runtime 번호와 Apache Spark 버전을 동일시하지 않는다. 다른 버전은 먼저 별도 환경에서 지원 매트릭스와 실패 결과를 기록하고 교재 핀을 변경한다. [Spark 4.0.4 공식 문서](https://spark.apache.org/docs/4.0.4/), [PySpark 설치](https://spark.apache.org/docs/4.0.4/api/python/getting_started/install.html)를 확인한다.

아래는 학습자가 **설치를 선택했을 때만** 실행하는 수동 명령이다. `pip install`은 패키지 다운로드와 디스크 사용을 동반한다. Java는 조직에서 승인한 JDK 배포판으로 별도 설치한다. 이 저장소가 설치하지 않는다.

PowerShell:

```powershell
python -m venv lab-workspaces/spark-venv
& .\lab-workspaces\spark-venv\Scripts\python.exe -m pip install "pyspark==4.0.4"
java -version
& .\lab-workspaces\spark-venv\Scripts\python.exe data-processing/spark/labs/spark_runner.py --help
& .\lab-workspaces\spark-venv\Scripts\python.exe data-processing/spark/labs/spark_runner.py --lab all --explain
```

Linux/macOS/WSL:

```bash
python3 -m venv lab-workspaces/spark-venv
lab-workspaces/spark-venv/bin/python -m pip install 'pyspark==4.0.4'
java -version
lab-workspaces/spark-venv/bin/python data-processing/spark/labs/spark_runner.py --lab all --explain
```

처음에는 전용 환경이 새 경로인지 확인하고, 기존 venv가 있다면 재사용 여부와 버전을 검토한다. Windows에서 Hadoop native/filesystem 관련 문제가 나면 traceback을 보존하고 승인된 Linux/WSL 환경과 비교한다. 출처 불명의 `winutils.exe`를 내려받거나 시스템 권한을 느슨하게 만드는 것을 해결책으로 삼지 않는다.

### 실행 전·후 경계

- `--help`에는 PySpark/JVM이 필요 없다. 실제 실행에서 의존성이 없거나 버전이 다르면 `ERROR`, exit code 1이다. 자동 설치·조용한 skip·가짜 `PASS`는 없다.
- `local[2]`만 사용한다. `SPARK_REMOTE`, `SPARK_CONNECT_MODE_ENABLED`, `SPARK_HOME`, `PYSPARK_GATEWAY_PORT`, `PYSPARK_GATEWAY_SECRET`, custom `PYSPARK_SUBMIT_ARGS`가 있는 환경은 거부한다. 빈 전용 Spark conf directory를 써서 학습자의 cluster 설정이나 기존 gateway를 가져오지 않는다.
- 실제 엔진은 로컬 JVM/Python 통신을 사용한다. **오프라인 모델의 no-network 성질과 다르며**, 외부 클러스터·cloud storage·API는 연결하지 않는다. Spark UI도 끈다.
- 기본 출력은 cwd와 무관하게 저장소의 `lab-workspaces/spark/run-*` 새 폴더다. `--work-root`로 별도 전용 상위 폴더를 명시할 수 있다. filesystem/home/repository root 자체, 파일, symlink/junction을 통과하는 경로는 거부한다. 신뢰할 수 있는 단일 사용자 로컬 파일시스템을 전제로 하며 다중 사용자 경로 경쟁 공격을 방어하는 보안 sandbox는 아니다.
- fixture 파일과 manifest는 exclusive create이며 기존 파일에 덮어쓰지 않는다. input·checkpoint·sink·scratch·temp·warehouse를 run 하위에 둔다. OS/JVM의 일반적인 diagnostic/cache 동작까지 완전히 격리한 컨테이너는 아니다.
- 한 스트리밍 query의 대기 제한은 기본 120초, `--timeout-seconds 30`처럼 5~300초로 지정할 수 있다. 시간 초과는 성공이 아니다. `spark.sql.streaming.stopTimeout=30000`으로 query stop 대기를 30초로 설정한다. `spark.stop()`과 JVM 전체가 응답하지 않는 상황의 강제 kill 시간 한계까지 보장하지는 않는다. 필요 시 학습자가 자신이 시작한 프로세스만 확인해 종료한다.
- 실행은 작은 6행 데이터만 사용한다. JVM에는 시스템에 따라 수 GB 정도의 가용 메모리가 필요할 수 있다. 전체 운영 데이터로 바꾼 뒤 `collect()`를 그대로 사용하는 것을 금지한다.
- 정상/실패 모두 생성한 run을 자동 삭제하지 않는다. 경로를 확인하고 결과를 보존한 뒤 **본인이 생성한 run 폴더만** 정리한다. 이 문서는 재귀 삭제 명령을 제공하지 않는다.

### 배치의 독립 oracle

행은 `(1,a,10),(2,a,NULL),(3,b,5),(4,NULL,7),(5,a,10),(6,NULL,NULL)`이다. row ID는 서로 다르지만 `(key,amount)`에는 중복과 NULL이 있다.

| key | `count(*)` | `count(amount)` | `sum(amount)` |
| --- | --- | --- | --- |
| a | 3 | 2 | 20 |
| b | 1 | 1 | 5 |
| NULL | 2 | 1 | 7 |

dimension의 key가 `a,b,NULL`일 때 ordinary equality inner join의 row ID는 `1,2,3,5`, null-safe equality join은 `1,2,3,4,5,6`이다. literal oracle을 Spark 결과와 비교한다. AQE를 활성화하고 선택적으로 계획을 출력하지만, 6행 데이터로 AQE 성능 향상이나 실제 skew 최적화가 일어났다고 주장하지 않는다.

### 스트리밍의 정상 재시작 oracle

첫 3행을 JSON 파일에 쓰고 명시적 schema의 file source → parquet append sink를 `availableNow`로 종료까지 처리한다. query가 완전히 멈춘 뒤 다음 3행 파일을 추가하고 **같은 checkpoint와 sink**로 두 번째 query를 시작한다. 동일 query ID·새 run ID를 확인하고, 각 단계의 sink 전체가 literal oracle의 정확한 행 집합과 일치하는지 비교한다. Spark query가 실행 중일 때 fixture 파일을 반쯤 쓰는 실험은 하지 않는다.

이는 file source와 parquet sink의 **정상 종료/재시작 한 시나리오**다. 프로세스 강제 종료, checkpoint 손실, source 파일 덮어쓰기, Kafka offset 복구, `foreachBatch` 외부 쓰기, Delta sink, cloud object store 일관성, 업무 event 중복 제거를 검증하지 않는다. 관련 확장은 [커리큘럼](../curriculum.md)의 별도 실험으로 수행하고 sink별 보장 범위를 적는다.

## 3. 테스트·실행 증거를 나누어 기록

작성 시점의 실행 결과와 미검증 범위는 [검증 기록](validation.md)에 남겼다.

```bash
python -m unittest discover -s data-processing/spark/labs -p "test_*.py" -v
python data-processing/spark/labs/spark_runner.py --help
```

`test_runner_contract.py`는 실제 Spark를 실행하지 않는다. 작은 파일쓰기 테스트는 저장소의 `lab-workspaces/spark-contract-tests/test-*` 새 폴더만 사용하고 해당 테스트가 만든 파일만 정리한다. 일부 Windows 제한 sandbox는 Python `tempfile`의 전용 ACL 때문에 생성 직후의 폴더 접근을 거부할 수 있다. 이를 제품 코드 통과로 숨기지 말고 권한/환경 실패로 기록한다. 승인된 일반 사용자 환경에서 같은 테스트를 다시 실행해 구분한다.

작성 시점 검증 환경에는 Java와 PySpark가 없어 **`LOCAL-SPARK` 실제 엔진 실행은 미검증**이다. 오프라인 실험과 정적/mock 계약 테스트 통과는 그 범위로만 보고한다. 실제 실행을 완료하면 `manifest.json`, 명령, exit code, stdout/stderr, 물리 계획, resource 관측값, 실패 사례를 함께 제출한다. 로그에는 합성 데이터만 있어야 하며 환경 변수나 credential 전체를 수집하지 않는다.

## 4. 다음 실험 설계

1. 같은 fixture에서 `repartition`, `coalesce`, broadcast 선택의 **결과 동등성**을 먼저 비교한다. 이후 충분한 데이터와 반복 측정으로 성능을 다룬다.
2. 소스·sink별 실패 시점을 정의하고, 별도 전용 run에서 crash/replay를 설계한다. 기본 runner의 PASS를 장애 복구 증거로 복사하지 않는다.
3. Delta 확장은 Spark/Delta 호환 버전을 별도 고정한다. 기본 runner에 `--packages`를 몰래 추가하지 않는다. 중복 source, version tie, tombstone retention, 충돌 재시도 oracle을 실제 테이블 결과와 비교한다.
4. Databricks 확장은 compute 종류·Runtime·Unity Catalog 권한·storage 위치·종료 조건·예산을 먼저 승인한다. [플랫폼 트랙](../../../platforms/databricks/README.md)의 근거와 로컬 결과를 별도로 보관한다.
