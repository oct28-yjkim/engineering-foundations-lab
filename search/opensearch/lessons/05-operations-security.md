# 05. 운영·권한·복구 — 빠른 검색보다 먼저 지킬 계약

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

OS09는 resource와 관측, OS10은 권한·수명주기·복원 계약을 다룹니다. 두 주 안에 모든 운영 기능을 production 수준으로 구축하라는 뜻은 아닙니다. 전체 실패 모델을 설계하고 작은 대표 실험을 선택합니다. 기본 단일 노드 환경의 Security 비활성 설정은 합성 데이터 실습용이며 이 강의의 SECURITY-LAB을 통과시키지 않습니다.

<a id="os09"></a>
## OS09 · heap·native memory·cache·merge·backpressure

### 내부 동작

JVM heap, direct/native allocation, thread stack, mmap과 OS page cache, 컨테이너 memory limit을 구분합니다. heap을 늘리면 모든 메모리 문제가 해결되는 것이 아니며 page cache의 여유를 줄일 수 있습니다. vector engine별로 graph·vector의 저장/조회 경로도 다르므로 전체 k-NN 메모리를 언제나 heap 또는 언제나 native라고 단정하지 않습니다.

request/query/fielddata cache는 대상·무효화·수명주기가 다릅니다. cache hit ratio 상승 자체가 업무 latency 개선의 증명은 아닙니다. merge는 segment 수와 삭제 공간에 영향을 주지만 indexing·search와 CPU/I/O 예산을 경쟁합니다. disk watermark, allocation, backlog와 recovery가 얽히면 한 node의 병목이 전체 부하 이동을 유발할 수 있습니다.

Circuit breaker는 특정 메모리 위험을 추정·제한하는 장치이지 모든 allocation·native memory·OS OOM을 막는 완전한 방벽이 아닙니다. limit을 올려 오류만 숨기지 않습니다. [Breaker 설정](https://docs.opensearch.org/latest/install-and-configure/configuring-opensearch/circuit-breaker/), [Nodes Stats](https://docs.opensearch.org/latest/api-reference/nodes-apis/nodes-stats/), [Index Stats](https://docs.opensearch.org/latest/api-reference/index-apis/stats/)에서 관측 단위와 counter reset을 확인합니다.

### 추가 실험

1. 실행 전 총 문서·요청·동시성·시간·디스크 사용량의 상한을 정합니다. production endpoint를 허용하지 않는 client를 사용합니다. 최대 부하로 시작하지 않습니다.
2. 동일 query의 warm/cold 조건을 명시하고 index 새 생성, 정상 warm-up, cache 수명 변화 중 안전한 방법으로 대조합니다. 공유 OS page cache를 강제로 비우지 않습니다.
3. 작은 bulk, 큰 bulk, 동시성 증가를 별도 축으로 바꿉니다. byte 크기·ACK/visibility latency·item 오류율·429·queue·GC·merge를 함께 기록합니다.
4. high-cardinality 집계 또는 많은 후보를 가진 query 하나를 선택합니다. 느린 query, 높은 GC, merge I/O, coordinator 병목의 경쟁 가설을 각각 어떤 관측으로 기각할지 적습니다.
5. rejected request에 bounded backoff를 추가하고 성공 throughput뿐 아니라 전체 retry amplification과 end-to-end completion을 비교합니다. queue를 무제한 늘리는 변경을 대조군으로 설계만 하고 실제 위험한 부하는 주입하지 않습니다.

### 통과 기준

검색 품질/정확성 동일성을 먼저 통과한 비교만 성능 결과로 채택합니다. 서버 `took`와 client latency, 노드 누적 counter와 shard 이동 뒤 reset, query profile과 비계측 run을 구별합니다. 큰 heap·많은 shard·큰 bulk를 맥락 없이 정답으로 제시하면 미통과입니다.

관측 제출물은 3개 이상의 경쟁 가설, 변경 하나, 지연 분포·오류율·resource 변화, 원래 설정으로 돌아갈 조건입니다. 실제 billing 정보가 없는 실험은 CPU·메모리·저장 byte·운영 시간을 비용 대용 지표로 표시하고 cloud 절감액을 지어내지 않습니다.

<a id="os10"></a>
## OS10 · TLS·인가·lifecycle·reindex·독립 복원

### 권한은 검색 filter와 다르다

TLS는 peer/hostname·인증서 신뢰 검증, authentication은 주체 식별, authorization은 허용 동작을 담당합니다. client가 보내는 `tenant_id` filter, custom routing, filtered alias는 그 자체로 사용자가 우회할 수 없는 인가 경계가 아닙니다. Dashboards tenant는 saved object 공간이며 모든 원본 문서의 tenant 격리와 동의어가 아닙니다. [Dashboards multi-tenancy](https://docs.opensearch.org/latest/security/multi-tenancy/tenant-index/)를 확인합니다.

DLS와 FLS는 읽기에서 문서·field를 제한하는 기능입니다. write/delete 권한이 있으면 숨겨진 데이터의 변경을 막는 별도 정책이 필요합니다. multi-field, 여러 role의 결합, DLS에 쓰이는 field와 FLS의 상호작용도 시험합니다. [DLS](https://docs.opensearch.org/latest/security/access-control/document-level-security/)와 [FLS](https://docs.opensearch.org/latest/security/access-control/field-level-security/)를 읽고 UI의 역할 목록만으로 통과 처리하지 않습니다.

### 권한 추가 실험

합성 tenant A/B 두 주체와 제한된 운영 주체를 만들고 서로 다른 실제 자격 증명으로 테스트합니다. A의 허용 문서를 읽는 양성 대조군이 성공한 뒤 B의 문서에 대한 search, GET, mget, aggregation, 직접 index 접근을 검사합니다. query filter를 제거·변경해도 정책이 유지되는지, 숨긴 field의 multi-field·highlight·허용된 조회 경로에 누출이 없는지 확인합니다. 허용하지 않은 write/delete도 별도 거부되어야 합니다.

인증 실패(401 계열)와 권한 실패(403 계열)·정책에 의한 결과 필터링은 같은 현상이 아닙니다. 비밀은 보고서에서 제거하되 어떤 주체와 role revision이 적용됐는지 남깁니다. 인증서 검증을 끈 요청의 성공을 TLS gate로 쓰지 않습니다. 기본 실습에서 이 환경을 제공하거나 실행한 것으로 간주하지 않습니다.

### lifecycle와 reindex 계약

alias는 이름 간접화, reindex는 데이터를 새 mapping/index로 복사하는 작업입니다. atomic alias 변경이 source write와 reindex를 하나의 transaction으로 묶지는 않습니다. 새 index 준비 → 기준 시점/변경 backlog 기록 → backfill → 순서·version을 지키는 catch-up → ID·삭제·query 검산 → 제한된 cutover → 관측 순서로 설계합니다. alias를 떼는 `remove`와 index를 파괴하는 `remove_index`를 구별하고 이전 index를 검증 없이 삭제하지 않습니다. [Alias API](https://docs.opensearch.org/latest/api-reference/alias/aliases-api/)의 action 의미를 확인합니다.

data stream은 append 지향 시계열의 write index/backing index 관리 모델입니다. 같은 업무 ID를 모든 backing index를 통틀어 자동 upsert해 주는 일반 문서 저장소로 취급하지 않습니다. ISM의 상태·전이·실패·재시도와 retention은 자동화 정책이며, 시간이 지났다는 이유만으로 snapshot 성공/복원 가능성이 증명되지는 않습니다. [Data streams](https://docs.opensearch.org/latest/im-plugin/data-streams/)와 [ISM](https://docs.opensearch.org/latest/im-plugin/ism/index/)을 참고합니다.

### 독립 복원 과제

1. source와 별도 새 target을 정하고 snapshot 대상·repository 권한·완료 상태·실패 shard·호환 버전을 기록합니다. repository 내부 파일을 수작업으로 삭제하지 않습니다.
2. snapshot은 모든 shard의 완벽한 단일 업무 transaction 시점이 아닐 수 있음을 전제로 원장의 checkpoint/업무 version과 연결합니다. [공식 snapshot·restore](https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/snapshots/snapshot-restore/)의 제약을 읽습니다.
3. target에 rename하여 복원하고 source index를 덮어쓰지 않습니다. global state·security index를 무분별하게 가져오지 않고 해당 Security plugin의 제한과 별도 보안 구성 복원 절차를 지킵니다.
4. count, ID별 version·삭제·문서 digest, 대표 query와 analyzer, alias/write routing, 두 주체의 권한을 확인합니다. replica가 존재한다는 사실은 독립 backup이 있다는 증거가 아닙니다.
5. 장애 인지부터 업무 검산 완료까지 RTO를, 원장과 비교한 잃거나 오래된 업무 ID를 RPO 증거로 기록합니다. 목표와 실측을 구별합니다.

OS10 제출은 권한 matrix·migration/DR 설계 전체와, 준비한 안전한 환경에서 수행한 대표 실험입니다. SECURITY-LAB과 RESTORE-LAB을 실행하지 못했다면 각각 미검증으로 남깁니다. 권한·복구 검증을 모두 마치지 않고 “운영 준비 완료”라고 선언하지 않습니다.
