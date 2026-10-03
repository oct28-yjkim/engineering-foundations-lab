# 실행 바이너리와 연결하는 ClickHouse 소스 읽기

파일 목록을 읽었다는 사실보다 한 현상의 입력→상태 변화→출력을 설명하는 것을 목표로 합니다. 아래 경로는 공식 저장소의 **`v26.8.1.2041-lts`**, commit **`537693a9b20b947a3cf0c4ac90c7c966eee963c9`**에서 확인한 탐색 출발점입니다. [릴리스 태그](https://github.com/ClickHouse/ClickHouse/tree/v26.8.1.2041-lts), [고정 commit](https://github.com/ClickHouse/ClickHouse/tree/537693a9b20b947a3cf0c4ac90c7c966eee963c9)

이는 학습용 소스 기준점이며 현재 Docker가 반드시 이 patch를 실행한다는 의미가 아닙니다. `26.8` 이미지 태그는 이동할 수 있습니다. 실제 runtime을 확인하지 않고 소스와 일치한다고 판정하지 않습니다. 최신 공식 문서는 이후 릴리스의 기능/기본값을 포함할 수 있으므로 런타임 설정과 해당 tag의 구현을 대조합니다.

## 실행 바이너리와 소스 맞추기

1. SQL에서 정확한 버전과 build metadata를 수집합니다.

```sql
SELECT version();
SELECT name, value FROM system.build_options
WHERE name ILIKE '%VERSION%' OR name ILIKE '%GIT%';
```

2. 저장소 루트에서 실제 실행 컨테이너의 image ID와 digest를 확인합니다. build metadata에서 commit이 나오지 않으면 미확인이라고 기록하고 공식 image/release metadata를 더 조사합니다.

```text
docker inspect efl-clickhouse --format "{{.Image}}"
docker image inspect clickhouse/clickhouse-server:26.8 --format "{{json .RepoDigests}}"
```

태그가 이동했으면 두 명령의 이미지 대상이 다를 수 있으므로 첫 명령의 image ID를 두 번째 명령에도 적용해 **실행 중인 이미지**의 digest를 확인합니다. `RepoDigests`가 없는 로컬 빌드도 별도 표시합니다.

3. 소스 탐색만 시작하려면 아래 고정 tag를 별도 디렉터리에 가져올 수 있습니다. 실제 runtime 버전이 다르면 공식 태그 목록에서 일치하는 태그를 선택합니다. suffix를 추측해 존재하지 않는 URL을 만들지 않습니다.

```text
git clone --depth 1 --branch v26.8.1.2041-lts https://github.com/ClickHouse/ClickHouse.git clickhouse-source-26.8
git -C clickhouse-source-26.8 rev-parse HEAD
git -C clickhouse-source-26.8 describe --tags --exact-match
```

위 참조 clone에서 HEAD는 명시한 commit과 일치해야 합니다. runtime이 다른 patch면 이 clone은 **비교용 기준점**이고, 실제 버전의 별도 checkout에서 경로·symbol을 재확인합니다. symbol이 이동했다면 `rg --files src`, `rg -n "symbol" src`로 찾고 변경된 경로를 기록합니다. master 링크를 runtime 구현의 증거로 사용하지 않습니다.

## 코드 지도

링크는 검증한 release tag를 가리킵니다. 제출 시에는 자신이 실제 읽은 commit SHA와 symbol의 permalink를 기록합니다. 함수명을 외우기보다 책임을 좁혀 읽습니다.

| 모듈 | 실제 소스 경로 / 출발 symbol | 읽으면서 답할 질문 |
| --- | --- | --- |
| M02 | [`src/Columns/ColumnVector.h`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Columns/ColumnVector.h) / `ColumnVector` | 값 배열은 어떻게 보관하며 filter/복사는 어디서 일어나는가? |
| M02 | [`src/Columns/ColumnNullable.h`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Columns/ColumnNullable.h) / `ColumnNullable` | 값과 null map의 크기 불변식은 무엇인가? |
| M02 | [`src/Columns/ColumnLowCardinality.h`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Columns/ColumnLowCardinality.h) / `ColumnLowCardinality` | 사전의 수명과 index의 타입은 어떻게 연결되는가? |
| M02 | [`src/Compression/CompressionCodecDelta.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Compression/CompressionCodecDelta.cpp) / Delta codec | 값 변환과 일반 압축은 어느 경계에서 결합되는가? |
| M03 | [`src/Storages/MergeTree/MergeTreeDataWriter.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/MergeTree/MergeTreeDataWriter.cpp) / `MergeTreeDataWriter` | partition 분리, 정렬, part 기록의 책임은 어디인가? |
| M03 | [`src/Storages/MergeTree/MergeTreeDataPartWide.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/MergeTree/MergeTreeDataPartWide.cpp) / `MergeTreeDataPartWide` | marks/index가 읽기 경로에 제공하는 정보는 무엇인가? |
| M03 | [`src/Storages/MergeTree/MergeTreeIndexGranularityAdaptive.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/MergeTree/MergeTreeIndexGranularityAdaptive.cpp) / adaptive granularity | granule별 rows를 어떻게 표현하고 합산하는가? |
| M03 | [`src/Storages/MergeTree/MergeTreeIndexGranularityInfo.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/MergeTree/MergeTreeIndexGranularityInfo.cpp) / granularity info | part 형식과 row/byte 제한은 어떻게 연결되는가? |
| M04 | [`src/Storages/MergeTree/KeyCondition.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/MergeTree/KeyCondition.cpp) / `KeyCondition` | predicate를 범위에서 가능/불가능으로 판정하는 조건은 무엇인가? |
| M04 | [`src/Storages/MergeTree/MergeTreeSelectProcessor.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/MergeTree/MergeTreeSelectProcessor.cpp) / `MergeTreeSelectProcessor` | 읽기 task와 pipeline 출력 chunk는 어떻게 연결되는가? |
| M05 | [`src/Parsers/ParserSelectQuery.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Parsers/ParserSelectQuery.cpp) / `ParserSelectQuery` | SQL 구조가 AST가 되는 지점과 타입 해석을 구별할 수 있는가? |
| M05 | [`src/Analyzer/Resolve/QueryAnalyzer.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Analyzer/Resolve/QueryAnalyzer.cpp) / `QueryAnalyzer` | alias·식별자·함수 타입을 언제 해석하는가? |
| M05 | [`src/Planner/Planner.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Planner/Planner.cpp) / `Planner` | query tree에서 실행 단계가 만들어지는 경계는 어디인가? |
| M05 | [`src/Processors/QueryPlan/QueryPlan.h`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Processors/QueryPlan/QueryPlan.h) / `QueryPlan` | plan step의 연결과 pipeline 구축은 같은 자료구조인가? |
| M06 | [`src/Processors/IProcessor.h`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Processors/IProcessor.h) / `IProcessor::Status`, `prepare`, `work` | 입력 필요·출력 차단·작업 준비 상태는 어떻게 다르는가? |
| M06 | [`src/Processors/Executors/PipelineExecutor.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Processors/Executors/PipelineExecutor.cpp) / `PipelineExecutor` | 작업 준비 상태가 executor 실행으로 이어지는 과정은? |
| M07 | [`src/Interpreters/HashJoin/HashJoin.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Interpreters/HashJoin/HashJoin.cpp) / `HashJoin` | ALL/ANY와 key/payload 보관 방식은 어떻게 연결되는가? |
| M08 | [`src/Interpreters/Aggregator.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Interpreters/Aggregator.cpp) / `Aggregator` | group key와 aggregate state의 메모리 수명은 누가 관리하는가? |
| M08 | [`src/Processors/Transforms/AggregatingTransform.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Processors/Transforms/AggregatingTransform.cpp) / `AggregatingTransform` | 입력 chunk를 소비하고 부분 상태를 전달하는 단계는? |
| M08 | [`src/AggregateFunctions/AggregateFunctionUniq.h`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/AggregateFunctions/AggregateFunctionUniq.h) / uniq state implementation | exact/approx 상태의 크기와 merge 계약은 어떻게 다른가? |
| M09 | [`src/Interpreters/AsynchronousInsertQueue.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Interpreters/AsynchronousInsertQueue.cpp) / `AsynchronousInsertQueue` | flush 트리거, 완료 통지, 예외 전달은 어디인가? |
| M09 | [`src/Core/Settings.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Core/Settings.cpp) / `deduplicate_insert` | 이전 dedup 설정보다 우선하는 모드와 INSERT SELECT의 조건은? |
| M10 | [`src/Storages/MergeTree/MergeTreeDataMergerMutator.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/MergeTree/MergeTreeDataMergerMutator.cpp) / `MergeTreeDataMergerMutator` | 새 part를 만드는 merge/mutation의 비용과 완료 경계는? |
| M10 | [`src/Processors/Merges/Algorithms/ReplacingSortedAlgorithm.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Processors/Merges/Algorithms/ReplacingSortedAlgorithm.cpp) / `ReplacingSortedAlgorithm` | 같은 sorting key에서 version 비교·tie·삭제 표시의 책임은? |
| M11 | [`src/Interpreters/InterpreterInsertQuery.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Interpreters/InterpreterInsertQuery.cpp) / `InterpreterInsertQuery` | INSERT pipeline에서 dependent view로 이어지는 호출을 어디서 찾는가? |
| M13 | [`src/Storages/StorageReplicatedMergeTree.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/StorageReplicatedMergeTree.cpp) / `StorageReplicatedMergeTree` | local data part와 Keeper metadata 변경은 어떻게 연결되는가? |
| M13 | [`src/Storages/MergeTree/ReplicatedMergeTreeQueue.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/MergeTree/ReplicatedMergeTreeQueue.cpp) / `ReplicatedMergeTreeQueue` | replica 작업 완료·재시도·미처리 상태는 무엇인가? |
| M13 | [`src/Storages/Distributed/DistributedSink.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Storages/Distributed/DistributedSink.cpp) / `DistributedSink` | shard 라우팅, 로컬 큐, 원격 전송의 응답 경계는? |
| M13 | [`src/Coordination/KeeperStateMachine.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Coordination/KeeperStateMachine.cpp) / `KeeperStateMachine` | Raft log가 state machine에 적용될 때 변경되는 상태는? |
| M14 | [`src/Backups/BackupsWorker.cpp`](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Backups/BackupsWorker.cpp) / `BackupsWorker` | backup/restore 작업 상태와 데이터 검증은 어느 층에서 책임지는가? |

## 깊이 읽는 세 가지 경로

1. **한 SELECT:** parser → analyzer → planner → QueryPlan → read processor → aggregate transform → executor. 해당 쿼리에 적용되지 않은 경로도 표시합니다. 전체 엔진의 유일한 call graph라고 주장하지 않습니다.
2. **한 논리 갱신:** insert → part → version 선택 → FINAL 또는 background merge → query 결과. 동률·tombstone·지연 데이터의 입력을 바꾸며 분기 조건을 확인합니다.
3. **한 분산 실패:** Distributed 전송 → replica 작업 → Keeper coordination → timeout/retry → 최종 state. protocol 확인과 실제 데이터 가시성을 별도로 측정합니다.

각 경로에서 최소 5개 symbol, 2개 자료구조, 1개 소유권/동기화 경계, 1개 오류 분기, 1개 반례를 제출합니다. “호출될 것 같다”는 부분은 가설로 표시하고 동적 추적이나 주변 호출부로 확인합니다.

## 빌드·디버깅 확장 SOURCE

이 저장소는 ClickHouse 소스 빌드 환경이나 debugger image를 포함하지 않습니다. [공식 빌드 안내](https://clickhouse.com/docs/development/build)를 따라 Linux 개발 환경·도구chain·submodule·디스크 예산을 별도 준비합니다. release tag에 맞는 안내와 빌드 설정을 기록하고 설치·빌드 로그를 남깁니다.

먼저 기능 변경 없이 자신의 바이너리 버전·commit을 확인합니다. 작은 query 한 개를 trace하고 optimized build와 debug/sanitizer build의 시간은 같은 성능 표본으로 섞지 않습니다. 심화 산출물은 작은 regression test, 동일 버전의 bug 최소 재현, 또는 구현을 단순화한 teaching engine 중 하나입니다. source patch를 택했다면 실패하던 입력, 수정, 해당 test와 관련 회귀 test, 성능 영향까지 제출합니다. 버그를 발견하지 않았는데 버그 수정이라고 제목을 붙이지 않습니다.
