# 04. 분산 검색·복제 — shard 경계에서 달라지는 의미

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

제공 LOCAL-ENGINE은 단일 노드·작은 fixture입니다. 이 강의의 다중 shard·replica·PIT·장애 주입은 별도 구현이며, CPU `distributed-topk`는 후보와 집계의 단순 모형입니다. 단일 프로세스의 목록 병합을 실제 coordinator·network·quorum 실험으로 부르지 않습니다.

<a id="os07"></a>
## OS07 · routing·query/fetch·top-k·집계·pagination

### 내부 동작과 중요한 구분

coordinating node는 대상 shard에 query를 전달하고 후보를 병합한 뒤 필요한 문서 fetch를 수행합니다. custom routing은 접근 범위·hot shard·문서 위치에 영향을 줍니다. write/read/update/delete가 같은 routing 계약을 사용하는지 확인하고 tenant routing을 tenant authorization으로 오인하지 않습니다.

**같은 전역 score와 tie 규칙을 쓴다면 각 shard의 정확한 local top-k를 합쳐 global top-k를 구할 수 있습니다.** 단순히 shard가 여러 개라는 이유로 정확성이 깨지는 것은 아닙니다. 후보를 k보다 적게 자르거나, shard별 통계가 달라지거나, ANN·hybrid 재정렬·bucket 집계 등 다른 연산이 추가되면 별도 분석이 필요합니다.

`query_then_fetch`의 shard-local term 통계와 `dfs_query_then_fetch`의 추가 통계 단계를 비교합니다. DFS는 모든 검색 품질 문제를 해결하는 switch가 아니며 latency와 지원 범위를 실제 query에서 확인합니다. [Search API](https://docs.opensearch.org/latest/api-reference/search-apis/search/)의 search type·partial result·timeout 계약을 읽습니다.

`terms` aggregation은 각 shard 후보 bucket을 병합하므로 전체 SQL GROUP BY와 같은 완전한 결과라고 가정하지 않습니다. `size`, `shard_size`, `sum_other_doc_count`, `doc_count_error_upper_bound`를 구분하고 count-descending 이외 정렬에서 오차 해석을 그대로 재사용하지 않습니다. [Terms aggregation](https://docs.opensearch.org/latest/aggregations/bucket/terms/)을 확인합니다.

### 추가 실험

1. 동일한 corpus를 한 shard와 여러 shard로 배치합니다. query·analyzer·similarity는 고정하고 routing에 따라 term 분포가 달라지게 구성합니다. ID 후보와 score·순위 차이를 따로 기록합니다.
2. 전역 고정 score의 정확한 top-k 대조군을 만든 뒤 shard당 후보를 k 미만으로 잘라 놓친 ID를 구합니다. 이 모형의 실패 가정을 실제 엔진 query에 그대로 덮어씌우지 않습니다.
3. 한 term이 여러 shard에서 2등이지만 전역 합계는 1등인 작은 집계 fixture를 만듭니다. `shard_size`를 늘린 전후 결과를 전체 순차 counter와 비교합니다. 오차 상한과 미반환 bucket의 존재도 적습니다.
4. 깊은 `from/size`, 단독 `search_after`, PIT와 `search_after`를 비교합니다. 동일한 sort 값이 여러 문서에 생기게 하여 안정적인 고유 tie-breaker를 포함합니다. `_id`를 바로 sort할 수 있다고 가정하지 말고 별도 keyword ID field를 설계합니다.
5. 페이지 사이에 write를 넣어 중복/누락을 ID ledger로 확인합니다. PIT의 만료·명시적 종료·segment 보존 비용을 기록합니다. PIT를 backup 또는 모든 index의 업무 transaction snapshot으로 부르지 않습니다. [공식 pagination](https://docs.opensearch.org/latest/search-plugins/searching-data/paginate/)을 읽습니다.

### 통과 기준

HTTP 200이어도 `_shards.failed`, `timed_out`, total-hit relation을 검사합니다. 부분 결과를 업무상 허용할지 명시하고 불허 경로는 실패로 처리합니다. 결과 후보를 잃은 단계가 shard retrieval, coordinator merge, fetch, filter, pagination 중 어디인지 증명합니다.

<a id="os08"></a>
## OS08 · document/segment replication·coordination·recovery

### 원리와 실패 모델

document replication과 segment replication은 replica의 작업·전송 단위가 다릅니다. 후자는 Lucene segment 복사와 replication checkpoint를 추적하므로 primary/replica의 search visibility를 동일한 순간으로 가정하지 않습니다. `refresh=true/wait_for`라는 client 옵션만으로 모든 replica의 read-after-write를 증명하지 않습니다. remote-backed storage는 별도 구성과 원격 저장소의 실패 모델을 추가합니다. [Segment replication](https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/segment-replication/index/)을 확인합니다.

cluster-manager의 voting configuration과 shard write replication은 다른 메커니즘입니다. quorum은 현재 voting configuration의 과반을 기준으로 판단하며 단순한 전체 data node 수나 replica 수의 과반과 같지 않습니다. `wait_for_active_shards` 역시 write 시작의 가용 copy 조건이지 임의의 업무 transaction commit quorum이 아닙니다. [Voting and quorum](https://docs.opensearch.org/latest/tuning-your-cluster/discovery-cluster-formation/voting-quorums/)에서 재구성 중인 구성도 확인합니다.

### 별도 CLUSTER-LAB 과제

1. 먼저 3개 cluster-manager-eligible node와 data 역할·replica·allocation failure domain을 설계합니다. 프로세스 세 개가 한 호스트에 있다면 호스트 장애 내성을 실험한 것이 아님을 명시합니다.
2. 정상 write의 ID·ACK·seq/term·primary/replica visibility를 관측합니다. document와 segment replication은 새 index 등 각 기능의 제약을 지키며 비교하고 불가능한 in-place 변환을 가정하지 않습니다.
3. 승인된 scratch cluster에서 primary process 상실, manager 소수/과반 상실, replica 지연 중 두 가지를 제한 시간·중단 조건과 함께 실행합니다. 공유 network나 운영 프로세스를 대상으로 하지 않습니다.
4. 재합류 후 cluster health뿐 아니라 ACK ledger의 값·업무 version·삭제와 search freshness를 검산합니다. primary term 변화·allocation explain·recovery 진행을 함께 보존합니다.
5. yellow/red의 의미를 shard 배치와 연결합니다. green이 업무 데이터 완전성·backup 존재·권한 안전성을 보장하지 않는 반례를 적습니다.

### 소스·구술

primary epoch 검증, in-sync copy 집합, checkpoint/recovery, cluster state publication의 경로를 별도로 찾습니다. “3개 replica니까 manager quorum도 3개”라는 설명, 과반 상실 뒤 새 cluster로 무조건 bootstrap하라는 복구안, data directory를 임의 복사해서 정합 복구했다는 설명은 미통과입니다. 실제 cluster가 없으면 타임라인·기대 결과·관측 지점을 CLUSTER-DESIGN으로 제출합니다.
