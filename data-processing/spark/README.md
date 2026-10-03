# Apache Spark — 실행 원리부터 분산 데이터 시스템 연구까지

DataFrame을 작성하는 수준에서 출발해 **왜 이 계획이 선택됐는지, 어떤 데이터가 이동했는지, 재실행 후 결과가 왜 맞는지**를 증명하는 28주·14모듈·약 336시간 과정입니다. API 사용량보다 정확성, 병목의 인과관계, 복구 조건, 소스 코드와 실측의 일치를 평가합니다.

Spark는 실행 엔진입니다. Parquet은 파일 형식이고 Delta Lake는 별도의 테이블 계층이며, Databricks는 Spark를 포함하는 관리형 플랫폼입니다. 이 트랙을 이수했다고 Photon·Unity Catalog·Databricks 권한이나 관리형 서비스 복구까지 검증한 것은 아닙니다. 플랫폼 확장은 [Databricks 과정](../../platforms/databricks/README.md)에서 구분합니다.

## 시작 순서

1. [공통 기초](../../databases/shared/foundations.md)의 SQL·OS·분산 실패 모델을 진단합니다. Python iterator·예외·가상환경, JVM heap/GC, Scala case class·pattern matching은 필요에 따라 별도 보충합니다.
2. [실습 안내](labs/README.md)에서 OFFLINE과 LOCAL-SPARK의 차이를 확인합니다.
3. [28주 커리큘럼](curriculum.md)을 따라 7개 강의와 14개 실험 보고서를 작성합니다.
4. [소스·논문 지도](source-reading.md)로 관찰한 현상의 구현 경계를 찾습니다.
5. [평가](assessment.md)에서 실행·설계·미검증 증거를 구별합니다.

저장소 루트에서 별도 패키지 없이 시작합니다. 이 명령은 Spark 실행이 아닌 Python 표준 라이브러리의 교육용 모형입니다.

```text
python data-processing/spark/labs/offline_lab.py --lab all
```

실제 PySpark `batch`·`streaming` 과제 코드는 별도로 제공합니다. Java·PySpark 준비 및 출력 경로 등은 [실습 안내](labs/README.md)를 먼저 따릅니다. Java나 PySpark가 없는 환경에서 이 과제의 실행 성공을 주장하지 않습니다.

## 버전과 실행 범위

교재의 고정 기준은 **Spark/PySpark 4.0.4**, 소스는 태그 `v4.0.4`의 `c7d67e3f5d4c9d88a480367b44fc54d26adf99ab`입니다. 최신 전체 계열이라는 뜻이 아니라 반복 가능한 실습 기준입니다. Spark 4.0.4 자체는 Python 3.9+를 지원하지만 이 저장소 코드는 Python 3.10+를 요구합니다. Java는 17 또는 21, Scala 소스는 2.13 기준입니다. [공식 환경](https://spark.apache.org/docs/4.0.4/)과 [설치 문서](https://spark.apache.org/docs/4.0.4/api/python/getting_started/install.html)를 확인합니다.

| 범위 | 검증할 수 있는 것 | 이 범위만으로 증명하지 못하는 것 |
| --- | --- | --- |
| OFFLINE | partition skew·집계 병합·watermark·비용의 명시적 단순 모형 | Catalyst·AQE·Spark watermark 실제 구현, 클러스터 속도 |
| LOCAL-SPARK | 실제 DataFrame 계획·합성 데이터 결과·파일 스트림 재시작 | executor 호스트 장애, 다중 AZ, 네트워크 분할, 원격 object store 보장 |
| BUILD | 별도 소스 빌드·회귀 테스트·수정안 | Databricks의 비공개 엔진이나 실제 배포 동작 |
| CLUSTER-DESIGN / CLUSTER-LAB | 장애 가정 설계 / 별도 격리 클러스터 실측 | 설계만 작성하고 실행까지 통과했다는 주장 |

강의의 AQE·UDF·GC·보안·장애 주입은 **학습자가 추가 구현하는 과제**입니다. 제공되는 `batch`·`streaming` 스크립트가 모든 강의 실험을 자동 실행하지 않습니다. 기본 실습은 외부 계정, 클라우드 비용, GPU, 모델 API가 필요 없습니다. 실제 클러스터·클라우드는 명시적으로 선택한 확장입니다.

## 무엇을 연결하는가

- PostgreSQL의 SQL·통계·실행 계획 지식을 분산 최적화·shuffle 비용으로 확장합니다.
- Kafka의 offset·업무 ID를 Spark checkpoint·sink commit과 대조합니다. Kafka source 연결 자체는 기본 실습에 포함되지 않습니다.
- ClickHouse의 정렬·컬럼 저장과 Parquet의 파일·row group·pruning을 비교하되 같은 인덱스라고 부르지 않습니다.
- [LLM 논문 실험](../../ai/llm-paper-lab/README.md)의 학습·평가 데이터 전처리에 적용합니다. 중복 문서·split leakage·재처리로 바뀐 corpus fingerprint를 검사하고, Spark 자체가 모델 품질을 보장한다고 가정하지 않습니다.

SP14는 2주 안에 끝낼 **작은 batch/streaming 연구 한 건**입니다. 기존 DB·Kafka·ClickHouse 통합이나 실제 Databricks 이관은 별도 후속 프로젝트이며 28주에 숨겨 넣지 않습니다.
