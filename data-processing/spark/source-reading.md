# Spark 소스·논문 읽기 지도

검증일: 2026-10-04. 공식 `apache/spark` 태그 `v4.0.4`는 commit **`c7d67e3f5d4c9d88a480367b44fc54d26adf99ab`**입니다. 아래 구현·테스트 경로는 해당 commit의 recursive Git tree에서 확인했습니다. tree 응답은 truncated=false였습니다. source 존재 확인과 source 테스트 실행은 다릅니다. 이 문서 작성 환경에서는 Spark build·JVM 테스트를 실행하지 않았습니다.

[공식 태그 ref](https://api.github.com/repos/apache/spark/git/ref/tags/v4.0.4), [고정 source tree](https://github.com/apache/spark/tree/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab), [Spark 4.0.4 문서](https://spark.apache.org/docs/4.0.4/).

## 버전 계약

읽는 source SHA와 실행하는 PySpark wheel/JAR·Java·Python·Scala·Hadoop 의존성 버전을 따로 기록합니다. `spark.version`이 같아도 배포 patch나 connector·vendor engine이 다를 수 있습니다. Databricks Runtime의 Spark 버전 숫자가 같다고 Photon·Unity Catalog·vendor patch 전체가 이 OSS source와 같다는 뜻은 아닙니다.

`master`, `latest`, 가변 줄 번호 대신 commit 고정 파일과 symbol을 기록합니다. 예를 들어 4.0.4의 `streaming/MicroBatchExecution.scala` 경로를 이후 버전에도 그대로 쓰지 말고 이동 여부를 확인합니다. 소스 읽기는 local 설치를 요구하지 않지만 BUILD를 선택하면 공식 빌드 도구·dependency 다운로드·시간·disk 예산을 별도로 마련해야 합니다.

## 구현 지도

| 모듈 | 고정 파일 | 추적할 질문 |
| --- | --- | --- |
| SP01–02 | [RDD.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/core/src/main/scala/org/apache/spark/rdd/RDD.scala) | transformation의 partition/dependency와 compute 경계는 어디인가? |
| SP02 | [Dependency.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/core/src/main/scala/org/apache/spark/Dependency.scala) | narrow와 shuffle의 부모 요구 관계는 무엇인가? |
| SP01–02 | [DAGScheduler.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/core/src/main/scala/org/apache/spark/scheduler/DAGScheduler.scala) | submitJob→handleJobSubmitted→submitStage에서 어떤 이벤트와 stage 상태를 다루는가? |
| SP01/11 | [TaskSchedulerImpl.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/core/src/main/scala/org/apache/spark/scheduler/TaskSchedulerImpl.scala) | resource 제안과 task attempt를 어떻게 연결하는가? |
| SP03 | [QueryExecution.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/QueryExecution.scala) | analyzed, optimizedPlan, sparkPlan, executedPlan의 LazyTry 경계와 준비 단계는? |
| SP03 | [Analyzer.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/analysis/Analyzer.scala) | 이름·타입 해석과 오류는 최적화 이전 어디에서 결정되는가? |
| SP03 | [Optimizer.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/Optimizer.scala) | rule batch·fixed point와 semantic 전제조건은? |
| SP04 | [WholeStageCodegenExec.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/WholeStageCodegenExec.scala) | 어떤 연산자가 경계를 만들고 코드 생성 연결을 끊는가? |
| SP04 | [ArrowEvalPythonExec.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/python/ArrowEvalPythonExec.scala) | batch와 JVM/Python 결과 변환 경계는? |
| SP05 | [SortShuffleManager.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/core/src/main/scala/org/apache/spark/shuffle/sort/SortShuffleManager.scala) | shuffle handle과 writer 선택이 어떤 조건을 쓰는가? |
| SP06 | [AdaptiveSparkPlanExec.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/adaptive/AdaptiveSparkPlanExec.scala) | StageSuccess/StageFailure 이후 materialized 정보가 계획에 어떻게 반영되는가? |
| SP06 | [OptimizeSkewedJoin.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/adaptive/OptimizeSkewedJoin.scala) | 지원 join·byte threshold·분할 조건은? |
| SP07 | [UnifiedMemoryManager.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/core/src/main/scala/org/apache/spark/memory/UnifiedMemoryManager.scala) | execution/storage 경계와 퇴거 가능한 범위는? |
| SP07 | [BlockManager.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/core/src/main/scala/org/apache/spark/storage/BlockManager.scala) | block 저장·조회·소실·원격 fetch와 메모리 소유는? |
| SP08 | [ParquetFileFormat.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/parquet/ParquetFileFormat.scala) | read schema와 filter가 reader에 어떻게 전달되는가? |
| SP09 | [EventTimeWatermarkExec.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/streaming/EventTimeWatermarkExec.scala) | 입력 event-time 통계를 어디서 모으는가? 실제 state 제거는 다른 operator 경로까지 찾아야 한다. |
| SP10 | [MicroBatchExecution.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/streaming/MicroBatchExecution.scala) | offset log와 commit log의 최신 batch가 다를 때 재시작은 무엇을 하는가? |
| SP10 | [FileStreamSink.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/streaming/FileStreamSink.scala) | 파일 output과 metadata commit, 재실행 batch 판정은? |
| SP10 | [ForeachBatchSink.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/streaming/sources/ForeachBatchSink.scala) | addBatch→사용자 batchWriter 호출에서 외부 transaction 책임은 누구에게 있는가? |
| SP10 | [HDFSBackedStateStoreProvider.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/streaming/state/HDFSBackedStateStoreProvider.scala) | state version·delta·snapshot의 commit/abort 경계는? |
| SP10 | [RocksDBStateStoreProvider.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/main/scala/org/apache/spark/sql/execution/streaming/state/RocksDBStateStoreProvider.scala) | local state와 durable checkpoint의 관계는? |
| SP11 | [SparkConnectService.scala](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/connect/server/src/main/scala/org/apache/spark/sql/connect/service/SparkConnectService.scala) | RPC·session·실행 요청의 경계는? |

이 표의 질문은 읽기 과제입니다. 모든 경로를 실행해 검증했다는 목록이 아닙니다. 각 trace는 실제 실행 모드의 public API에서 시작하고 다음 호출을 코드에서 확인합니다. 이름이 유사한 classic/Connect 구현을 바꿔 읽지 않습니다.

## 회귀 테스트 진입점

| 테스트 | 실험에 연결할 조건 |
| --- | --- |
| [DAGSchedulerSuite](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/core/src/test/scala/org/apache/spark/scheduler/DAGSchedulerSuite.scala) | 성공·실패·stage 재제출의 event 순서 |
| [AdaptiveQueryExecSuite](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/test/scala/org/apache/spark/sql/execution/adaptive/AdaptiveQueryExecSuite.scala) | 최종 plan 검증, AQE 설정과 대조군 |
| [StreamingAggregationSuite](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/test/scala/org/apache/spark/sql/streaming/StreamingAggregationSuite.scala) | watermark·집계·output mode·재시작 fixture |
| [ForeachBatchSinkSuite](https://github.com/apache/spark/blob/c7d67e3f5d4c9d88a480367b44fc54d26adf99ab/sql/core/src/test/scala/org/apache/spark/sql/execution/streaming/sources/ForeachBatchSinkSuite.scala) | 사용자 callback·batch ID·실패 처리 |

BUILD를 선택할 때만 [공식 빌드 안내](https://spark.apache.org/docs/4.0.4/building-spark.html)에 맞춰 **별도 Spark source checkout**에서 테스트를 실행합니다. 이 교육 저장소의 root에서 upstream 빌드 명령을 실행하지 않습니다. 실제 선택한 test 이름·발견된 test 수·실패·skip·환경을 남기고 0 tests를 성공으로 세지 않습니다. 전체 suite는 많은 RAM·disk·시간을 사용할 수 있으므로 한 fixture의 의미를 읽고 작은 범위부터 실행합니다. 여기서는 별도 설치나 빌드를 자동 수행하지 않습니다.

## 논문과 source를 엮는 보고서

- [RDD, NSDI 2012](https://www.usenix.org/conference/nsdi12/technical-sessions/presentation/zaharia): coarse-grained 변환의 재계산 가정을 `RDD`·`Dependency`와 연결합니다. 변경되는 외부 source나 side effect를 반례로 넣습니다.
- [Spark SQL, SIGMOD 2015](https://people.csail.mit.edu/matei/papers/2015/sigmod_spark_sql.pdf): Catalyst의 extensible rule 관점을 현재 analyzer/optimizer와 비교합니다. 당시 benchmark 수치와 4.0.4 local 결과를 직접 등치하지 않습니다.
- [Structured Streaming, SIGMOD 2018](https://people.eecs.berkeley.edu/~matei/papers/2018/sigmod_structured_streaming.pdf): incremental query와 progress/commit 가정을 현재 micro-batch·sink source로 옮깁니다. 기본 engine 모델과 외부 임의 side effect의 보장을 나눕니다.

제출 형식은 `논문 주장 → 가정 → source symbol 5개 → 관측 지표 → 반례 → 작은 테스트 → 결론의 적용 범위`입니다. 소스에 존재한다는 것과 해당 물리 계획에서 호출됐다는 것은 서로 다른 증거입니다.
