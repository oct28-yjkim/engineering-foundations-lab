# 분산 데이터 처리 실험실

데이터를 읽고 변환하는 코드와, 그것을 partition·task·stage·shuffle·state·commit으로 실행하는 시스템을 함께 공부합니다. 첫 과정은 [Apache Spark](spark/README.md)이며 실행 엔진과 SQL·배치·스트리밍을 다룹니다. 관리형 플랫폼의 권한·배포·비용·복구는 [Databricks](../platforms/databricks/README.md)에서 이어집니다.

두 기술은 같은 제품이 아닙니다. Apache Spark 로컬 실행은 Databricks Runtime·Photon·Unity Catalog·Lakeflow의 관리형 동작을 증명하지 않습니다. Delta Lake의 테이블 transaction도 임의의 외부 서비스·여러 테이블을 아우르는 업무 transaction과 같지 않습니다.

## 경로

| 경로 | 제공·학습 범위 |
| --- | --- |
| [실제 Spark 관측·진단](spark/operations.md) | SQL/DAG·stage/task·skew·spill·GC·streaming backlog, 원리 모형은 선택 부록 |
| [Spark 심화](spark/curriculum.md) | 28주·14모듈·7강, 실행 계획·셔플·메모리·스트리밍·운영·소스 |
| [Databricks 심화](../platforms/databricks/curriculum.md) | 28주·14모듈·7강, Delta·Unity Catalog·Lakeflow·Photon·배포·복구 |
| [Lakehouse 통합 연구](../capstones/governed-lakehouse.md) | 선택 8주, 정합성·권한·재처리·비용·별도 대상 복원 |

처음에는 공통 SQL·Python·OS를 보충하고 Spark부터 진행합니다. Databricks 사용자라면 플랫폼의 첫 모듈과 함께 Spark plan·partition 기초를 병행할 수 있습니다. 이미 익힌 부분은 독립 oracle와 반례로 진단한 뒤 넘어갑니다.

기존 [Kafka](../streaming/kafka/README.md)는 source offset·재처리, [PostgreSQL](../databases/postgresql/README.md)은 원본 transaction과 CDC, [ClickHouse](../databases/clickhouse/README.md)는 분석 저장·집계 비교에 연결합니다. [LLM 논문 실험](../ai/llm-paper-lab/README.md)의 corpus·평가 데이터 준비에도 적용할 수 있지만 모델 품질과 데이터 파이프라인 성공을 별개로 평가합니다.
