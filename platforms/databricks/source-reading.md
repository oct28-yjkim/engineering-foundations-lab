# Databricks 소스·논문 지도: 공개 구현과 관리형 계약을 분리한다

[커리큘럼](curriculum.md) · [실습 범위](labs/README.md) · [연구 강의](lessons/07-research-capstone.md)

Databricks 전체가 하나의 공개 저장소는 아닙니다. 이 과정은 Delta Lake의 공개 protocol/구현을 실제로 추적하고, Spark는 [Spark 소스 지도](../../data-processing/spark/source-reading.md)와 연결하며, Photon·managed control plane·UC 운영 기능은 공식 문서·논문·승인된 실행 증거로 검토합니다. 공개 UC 구현과 managed UC의 기능 동등성을 가정하지 않습니다.

## 1. 고정 소스 기준과 runtime fingerprint

2026-10-04에 공식 Git ref와 recursive tree를 확인한 교육용 기준은 **Delta Lake v4.0.0**입니다. annotated tag object는 `a2f4a7194b070a033401a0bbf7f409e679038733`, 실제 commit은 **`6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2`**입니다. 아래 링크는 tag object가 아니라 실제 commit을 가리킵니다. 이것은 고정된 **source reading snapshot**이며 최신 release 추천, 설치 완료 또는 Databricks Runtime 내부 commit의 증명이 아닙니다.

[공식 release 호환표](https://docs.delta.io/releases/)에서 실행하려는 Spark/Delta 조합을 별도로 확인합니다. 이 저장소의 기본 로컬 Spark4.0.4와 소스읽기 tag의 build dependency를 억지로 같은 값으로 바꾸지 않습니다. DBR·serverless는 제품 release/environment를 따로 기록합니다. Photon 내부 코드·managed SHA가 공개되지 않으면 unknown입니다.

별도 source checkout의 `git rev-parse HEAD`, `git status --short`, `git describe --tags --always`, Java/Scala/sbt/Python/Spark, test selector와 결과를 남깁니다. upstream build는 의존성 다운로드·파일 생성·CPU/메모리 사용을 동반하며 이 과정에서 실행하지 않았습니다. 공개 ref를 조회하는 읽기 전용 예시는 다음과 같습니다.

~~~text
git ls-remote https://github.com/delta-io/delta.git "refs/tags/v4.0.0*"
~~~

annotated tag의 `^{}`로 끝나는 행이 실제 commit인지 확인합니다. GitHub tree API가 tag를 해석해 주더라도 tag SHA를 raw-file permalink의 commit으로 사용하지 않습니다.

## 2. 구현 경로와 질문

| 모듈/경계 | 고정 구현 | 추적할 불변식 |
| --- | --- | --- |
| D03 reader/writer 계약 | [PROTOCOL.md](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/PROTOCOL.md) | feature와 protocol version에 따라 reader/writer가 확인할 조건은 무엇인가? |
| D03 table 진입 | [DeltaLog.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/main/scala/org/apache/spark/sql/delta/DeltaLog.scala) | log 경로·cache·snapshot update와 commit 시작이 어디서 연결되는가? |
| D03 읽기 상태 | [Snapshot.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/main/scala/org/apache/spark/sql/delta/Snapshot.scala) | active file·metadata·protocol·stats가 어떤 version의 상태인가? |
| D03 OCC | [OptimisticTransaction.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/main/scala/org/apache/spark/sql/delta/OptimisticTransaction.scala) | read set, write actions, 재시도, commit 후 hook을 구분할 수 있는가? |
| D03 충돌 | [ConflictChecker.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/main/scala/org/apache/spark/sql/delta/ConflictChecker.scala) | 다른 writer의 어떤 변화가 자신의 가정을 무효화하는가? |
| D04 mutation | [MergeIntoCommand.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/main/scala/org/apache/spark/sql/delta/commands/MergeIntoCommand.scala) | matching·data rewrite·commit의 단계를 분리하고 source 중복을 어디서 다루는가? |
| D04 retention | [VacuumCommand.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/main/scala/org/apache/spark/sql/delta/commands/VacuumCommand.scala) | 후보 file 계산·safety·dry-run과 실제 삭제의 경계는 어디인가? 읽기 과제이며 실행 지시 아님 |
| D07/08 source | [DeltaSource.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/main/scala/org/apache/spark/sql/delta/sources/DeltaSource.scala) | table version·source offset·schema 변경·admission control이 어떻게 연결되는가? |
| D07/08 초기 snapshot | [DeltaSourceSnapshot.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/main/scala/org/apache/spark/sql/delta/files/DeltaSourceSnapshot.scala) | snapshot 파일을 stream의 초기 입력으로 읽는 순서와 경계는 무엇인가? |
| D07/08 sink | [DeltaSink.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/main/scala/org/apache/spark/sql/delta/sources/DeltaSink.scala) | batch ID·query identity와 table transaction은 어떻게 연결되는가? 외부 부작용까지 포함하는가? |

첫 연구는 Delta sink의 commit 완료와 driver가 성공을 확인하는 시점 사이를 고릅니다. source replay와 table의 transaction marker를 따라가되 외부 HTTP 전송을 같은 atomic transaction으로 표시하지 않습니다. Auto Loader의 관리형 `cloudFiles` 내부를 이 공개 DeltaSource 구현으로 대신 설명하지 않습니다.

## 3. 테스트를 먼저 읽고 assertion으로 돌아온다

| 고정 테스트 | 반드시 확인할 조건 |
| --- | --- |
| [DeltaLogSuite.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/test/scala/org/apache/spark/sql/delta/DeltaLogSuite.scala) | test fixture storage, log/snapshot/cache lifecycle, failure expectation |
| [OptimisticTransactionSuite.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/test/scala/org/apache/spark/sql/delta/OptimisticTransactionSuite.scala) | read/write dependency·concurrency barrier·expected exception·retry |
| [MergeIntoSuiteBase.scala](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/spark/src/test/scala/org/apache/spark/sql/delta/MergeIntoSuiteBase.scala) | NULL·duplicate source·matching clause·result oracle; base trait와 실제 concrete suite 구분 |

테스트3개를 읽고 그중1개를 줄인 regression을 작성합니다. fixture가 local file system인지 mock object store인지 명시하고 cloud concurrent writer 안전성 증거로 확대하지 않습니다. `MergeIntoSuiteBase` 같은 base만 선택해0개 test를 실행하는 실수를 피합니다.

[고정 build.sbt](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/build.sbt)의 `spark` project와 [기여 안내](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/CONTRIBUTING.md)를 검토한 뒤 별도 checkout/toolchain에서 실행 후보를 정합니다. Unix/WSL 등 해당 build wrapper를 지원하는 환경에서의 **미실행 후보**는 다음과 같습니다. Windows PowerShell에서 바로 검증됐다는 뜻이 아닙니다.

~~~text
build/sbt "spark/testOnly org.apache.spark.sql.delta.OptimisticTransactionSuite"
~~~

다운로드 용량·test 임시 디렉터리·외부 endpoint를 사전에 확인하고 개인 cloud credential이 test에 전달되지 않게 합니다. 실제 build 성공·선택 test 수·skip/failure를 기록하기 전까지 미검증입니다. `testOnly`는 테스트 범위를 줄일 뿐 아무 부작용도 없다는 뜻이 아닙니다.

## 4. 필수 논문 세 편과 실험 연결

원문은 링크로 읽고 PDF를 이 저장소에 무단 복제하지 않습니다. 아래는 주장과 실험 질문이며 논문의 수치 결과를 자신의 재현 결과로 제시하지 않습니다.

| 논문 | 출판 정보·원문 | 읽을 초점·작은 재현 |
| --- | --- | --- |
| Delta Lake: High-Performance ACID Table Storage over Cloud Object Stores | Armbrust et al., PVLDB13(12),2020, [학회 원문](https://www.vldb.org/pvldb/vol13/p3411-armbrust.pdf), DOI10.14778/3415478.3415560 | table metadata/log와 object bytes, OCC, metadata 비용. D03 snapshot 모델과 D04 재시도를 연결 |
| Lakehouse: A New Generation of Open Platforms that Unify Data Warehousing and Advanced Analytics | Armbrust et al., CIDR2021, [학회 원문](https://www.vldb.org/cidrdb/papers/2021/cidr2021_paper17.pdf) | 직접 접근 format과 관리 기능의 역할. 데이터 사본 축소 가설에 freshness·격리·다중 engine 운영비 반례를 제시 |
| Photon: A Fast Query Engine for Lakehouse Systems | Behm et al., SIGMOD2022, [저자 공개 원문](https://people.eecs.berkeley.edu/~matei/papers/2022/sigmod_photon.pdf), DOI10.1145/3514221.3526054 | vectorized native execution과 Spark semantics 호환. D09 workload별 native/fallback과 cold/warm을 분리 |

각 논문에 대해 문제1문장, 가정3개, 주장1개, independent oracle, 반례, 축소 재현과 원논문 재현의 차이, 현재 runtime에서 달라진 점을 제출합니다. [LLM 논문 실험실](../../ai/llm-paper-lab/README.md)의 원리 모델/실모델 분리 원칙과 같습니다. 이 세 편을 읽었다고 최신 managed 기능의 모든 동작이 확인되는 것은 아닙니다.

## 5. 관리형 계약의 확인 지점

- D03–04: [isolation](https://docs.databricks.com/aws/en/optimizations/isolation), [CDF](https://docs.databricks.com/aws/en/delta/delta-change-data-feed), [history](https://docs.databricks.com/aws/en/tables/history). protocol/기능 조건과 보존 창을 실제 table과 대조합니다.
- D05–06: [UC 권한](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/privileges-reference). 상속·owner·실제 run identity와 cloud IAM 경로를 분리합니다.
- D07–08: [Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader), [pipeline Python](https://docs.databricks.com/aws/en/ldp/developer/python-dev). 로컬 Spark4.0.4의 file stream이나 DeltaSource를 managed 구현과 동일시하지 않습니다.
- D09–12: [Photon](https://docs.databricks.com/aws/en/compute/photon), [billing](https://docs.databricks.com/aws/en/admin/system-tables/billing), [Bundles](https://docs.databricks.com/aws/en/dev-tools/cli/bundle-commands). feature on, actual operator, 실제 청구, 원격 배포 성공은 별도 증거입니다.

이 링크들은 AWS 제품 문서입니다. Azure/GCP는 해당 cloud·region·SKU·release의 문서와 실행 권한을 다시 확인합니다. 2026-10-04 확인 이후 이름·preview 상태·지원 runtime은 바뀔 수 있으므로 수행 날짜와 version을 연구 노트에 고정합니다.
