# OpenSearch 운영 실습: 요청 실패·검색 가시성·shard·자원 압력

[트랙](README.md) · [엔진 준비](labs/README.md) · [공통 운영 방법](../../operations/README.md) · [장애 보고서](../../operations/incident-report-template.md)

기본 실습은 실제 OpenSearch의 API·지표·검색 결과를 연결하는 것입니다. BM25 등 수식 모형은 선택 보조 자료이며 cluster 진단 역량을 대신하지 않습니다. 아래 절차는 실습 명세이고 이 문서를 작성하면서 서버 장애를 실행한 기록은 아닙니다.

## 기본 LAB: 정상 동작에서 장애 복구까지

[입구](labs/README.md)에서 합성 문서의 색인·검색·정렬·집계를 확인하고, mapping/analyzer·ACK/GET/search·refresh 경계를 설명합니다. [관측 LAB](labs/observation.md)으로 node/index stats·client 지연·Profile을 읽고 단일 노드·cache·표본 수·보안의 한계를 확인한 뒤 [단계형 사건](labs/incidents.md)을 시작합니다. 28주 심화는 선수 조건이 아닙니다.

실행 코드는 검색 누락·bulk 부분 실패·write block·replica 미할당·pagination 제한을 단계별로 남깁니다. 이 문서의 수동 API 절차는 같은 원인을 더 직접 조사하는 보충 경로이며 반드시 두 경로를 중복 실행할 필요는 없습니다. 추가 자원을 선택하면 [3→4노드 실습](labs/scaling-incidents.md)에서 배치·복귀·routing 문제를 다룹니다. 작성된 기대값과 실제 실행은 [검증 기록](labs/incident-validation.md)에서 구분합니다.

## 1. 읽기 전용 기준선

기준은 저장소의 **3.9.0**이며 실제 응답·Lucene/plugin·image digest·heap·container budget을 기록합니다. 공식 `latest` 문서는 바뀔 수 있으므로 현재 버전과 API 응답 schema를 확인합니다. [실습 환경](labs/README.md)은 인증/TLS가 없는 개인 loopback 환경이며 원격/공유/실제 데이터에 사용하지 않습니다. private local Docker context 확인 후 사용자가 직접 실행합니다.

아래 `curl.exe`는 Windows 예시입니다. macOS/Linux에서는 `curl`을 사용합니다. 인증이 필요한 별도 환경의 secret은 명령/history에 넣지 않습니다. curl은 HTTP 오류 시에도 body를 출력할 수 있으므로 상태 코드를 함께 확인합니다.

```text
curl.exe --noproxy "*" --max-time 10 http://127.0.0.1:19200/
curl.exe --noproxy "*" --max-time 10 "http://127.0.0.1:19200/_cluster/health?level=indices"
curl.exe --noproxy "*" --max-time 10 "http://127.0.0.1:19200/_nodes/stats/jvm,process,fs,thread_pool,breaker?human=false"
curl.exe --noproxy "*" --max-time 10 "http://127.0.0.1:19200/_cat/shards?format=json&bytes=b"
```

기존 index 이름과 query를 외부에 공개하지 않고 제출물은 학습용 index에 한정합니다. 기준선은 같은 query·동시성에서 10초 간격·5분입니다. node restart/counter reset을 표시하며 노드별 차이를 평균으로 숨기지 않습니다.

| 지표 | 형식·단위·관측 창 | 경쟁 원인을 좁히는 방식 |
| --- | --- | --- |
| `jvm.mem.heap_used_percent` | gauge, %; 10초 추세 | GC 회복 추세·native/page cache·container OOM은 별도 |
| GC `collection_count/time_in_millis` | counter, 건/ms; 60초 Δ | 긴 pause와 request latency·실패율 연결 |
| thread_pool `queue/active` | gauge, task 개 | pool별로 분리; queue 증가와 거부는 다름 |
| thread_pool `rejected` | counter, 거부 건; Δ/60초 | 누적 0이 아니라고 현재 장애로 판정하지 않음 |
| breaker `estimated_size_in_bytes/limit_size_in_bytes` | gauge, byte | breaker별 구분; 실제 전체 RSS와 같지 않음 |
| breaker `tripped` | counter, 건; Δ/60초 | payload·aggregation·동시성·heap과 같이 확인 |
| fs `available_in_bytes` | gauge, byte; 추세·사용 가능 비율 | disk watermark 설정·allocation 사유와 연결 |
| unassigned shard 수 | gauge, shard 개 | primary/replica·topology·allocation 사유 구별 |

서버 `took`은 client end-to-end latency와 다릅니다. HTTP 200에서도 `_shards.failed`, `timed_out`, bulk item 오류를 확인합니다. 지표 출처: [Nodes Stats](https://docs.opensearch.org/latest/api-reference/nodes-apis/nodes-stats/).

## 2. 명시적으로 선택한 개인 fixture

아래 쓰기는 **개인 로컬 합성 index 실습을 선택한 경우만** 수행합니다. `ops-os-01`이 있으면 중단하고 새 이름으로 모든 요청을 바꿉니다. 기존 index를 덮어쓰거나 DELETE하지 않습니다. 최대 문서 10개·동시 요청 1개·요청 10초·사건 60초가 상한입니다. PowerShell의 JSON 인자 escape 차이를 피하기 위해 `Invoke-RestMethod`를 사용합니다.

```powershell
$opsEndpoint = 'http://127.0.0.1:19200'
$opsIndex = 'ops-os-01'
$opsDefinition = '{"settings":{"number_of_shards":1,"number_of_replicas":0,"refresh_interval":"-1"},"mappings":{"dynamic":"strict","properties":{"title":{"type":"text"},"price":{"type":"integer","coerce":false}}}}'
Invoke-RestMethod -Method Put -Uri "$opsEndpoint/$opsIndex" -ContentType 'application/json' -Body $opsDefinition -TimeoutSec 10
Invoke-RestMethod -Method Put -Uri "$opsEndpoint/$opsIndex/_create/1" -ContentType 'application/json' -Body '{"title":"diagnostic fixture","price":10}' -TimeoutSec 10
```

대상 식별은 앞의 GET `/`에서 cluster `engineering-foundations-opensearch-lab`·node `opensearch-lab`·3.9.0을 확인한 후 수행합니다. 식별 문자열은 실수 방지이며 인증이 아닙니다. 프록시를 설정한 환경에서는 loopback 우회를 확인하고 이 수동 예시를 원격 URL로 바꾸지 않습니다.

## 3. 실제로 재현할 세 가지 사건

### A. 쓰기는 성공했는데 search에 문서가 없다

```powershell
Invoke-RestMethod -Uri "$opsEndpoint/$opsIndex/_doc/1" -TimeoutSec 10
Invoke-RestMethod -Uri "$opsEndpoint/$opsIndex/_search" -TimeoutSec 10
Invoke-RestMethod -Method Post -Uri "$opsEndpoint/$opsIndex/_refresh" -TimeoutSec 10
Invoke-RestMethod -Uri "$opsEndpoint/$opsIndex/_search" -TimeoutSec 10
```

**가설:** refresh 지연, 잘못된 index/alias/routing, mapping/query 불일치. realtime GET과 search·index UUID/settings로 나눕니다. **조치:** 이 fixture에서만 명시적 refresh 후 비교하고 업무의 freshness SLO에 맞게 정책을 정합니다. 매 write마다 global refresh를 수행하지 않습니다. **롤백:** 자신의 index에만 원래 의도한 `refresh_interval`을 복원하거나 진단 fixture임을 기록해 보존합니다. **회복:** 정확한 ID=1·price=10 검색, shard 실패 0, timed_out=false. 가시성 회복이 전원 상실 내구성 증명은 아닙니다. 근거: [Refresh API](https://docs.opensearch.org/latest/api-reference/index-apis/refresh/).

### B. 색인 오류: mapping인가, 자원 거부인가?

```powershell
# 의도적 HTTP 400; PowerShell이 예외를 내는 것이 예상 결과
Invoke-RestMethod -Method Put -Uri "$opsEndpoint/$opsIndex/_create/2" -ContentType 'application/json' -Body '{"title":"invalid type","price":"not-an-integer"}' -TimeoutSec 10
```

**가설:** schema/type 오류 400, version conflict 409, overload 429, 연결 실패. HTTP status와 error type을 먼저 분리하고 retries로 숨기지 않습니다. mapping을 읽어 coerce/dynamic 계약을 확인합니다. **조치:** 입력을 `price:20`으로 수정해 같은 새 ID=2를 1회 create하고 refresh합니다. **롤백:** 기존 ID=1을 수정하지 않았음을 확인하고 잘못된 입력은 별도 오류 원장으로 보존합니다. **회복:** 문서 정확히 2개, price=10/20, 신규 오류 0. bulk에서는 최상위 HTTP 200이어도 item별 같은 분류가 필요합니다. 근거: [Bulk API](https://docs.opensearch.org/latest/api-reference/document-apis/bulk/).

### C. single node가 yellow: 데이터 손실인가?

```powershell
Invoke-RestMethod -Method Put -Uri "$opsEndpoint/$opsIndex/_settings" -ContentType 'application/json' -Body '{"index":{"number_of_replicas":1}}' -TimeoutSec 10
Invoke-RestMethod -Uri "$opsEndpoint/_cluster/health/$opsIndex" -TimeoutSec 10
Invoke-RestMethod -Method Post -Uri "$opsEndpoint/_cluster/allocation/explain" -ContentType 'application/json' -Body '{"index":"ops-os-01","shard":0,"primary":false}' -TimeoutSec 10
# 이 fixture의 원래 replica=0으로만 복원
Invoke-RestMethod -Method Put -Uri "$opsEndpoint/$opsIndex/_settings" -ContentType 'application/json' -Body '{"index":{"number_of_replicas":0}}' -TimeoutSec 10
```

새 suffix를 썼다면 explain body의 index도 일치시킵니다. **가설:** 동일 노드에 replica를 둘 수 없음, disk watermark, allocation filter, recovery 실패. allocation decider의 이유로 구분하고 색깔만 보지 않습니다. **조치/롤백:** 여기서는 자기 fixture 원래 replica=0만 복원합니다. 운영의 가용성 요구를 replica=0으로 낮춰 green을 만드는 대응과 다릅니다. **회복:** 자기 index primary STARTED·미할당 0·문서 2개, 다른 index 상태 불변. 별도 multi-node 환경이 없으므로 failover 검증은 미완료입니다. 근거: [Allocation Explain](https://docs.opensearch.org/latest/api-reference/cluster-api/cluster-allocation/).

## 4. 지연·429·heap 압력 사건: 한도 내 원인 검증

query 비용·동시성 초과·merge/disk 경합·GC를 경쟁 가설로 둡니다. 먼저 [관측 runner](labs/observation.md)로 실제 REST query 두 경로의 정답·client/took·Profile·전후 node/index stats를 비교합니다. 기본 2,000문서·variant별 20회·동시성 1이며 문서/요청 예산은 해당 문서에 고정합니다. 이 비교는 포화·429·OOM을 재현하지 않으며, 연속 추세가 필요하면 위 읽기 전용 기준선 수집을 별도로 수행합니다. 문제가 나오지 않으면 **미재현**으로 보고하며 문서/동시성을 무한 증대하거나 disk를 채우지 않습니다.

실제 거부를 의도적으로 재현하려면 별도 disposable cluster·heap/메모리/디스크 예산·요청 크기/수 상한·즉시 중단 조건을 작성해 실행을 선택합니다. **조치:** 불필요한 field/aggregation 제거, 유입 제한·backoff·batch 조절을 비교합니다. queue·breaker 한도를 바로 올리지 않습니다. **회복:** 신규 rejection Δ=0, queue 배출, 오류/latency가 같은 workload baseline 범위로 복귀, 정확한 검색 결과 유지. 부하 중지 후에도 heap 점유가 0이 되는 것을 요구하지 않습니다.

## 5. 통과와 남겨야 할 한계

실제 baseline + 사건 최소 2개 + 각각 경쟁 가설 2개·원본 관측·조치/되돌림·업무 결과 검산을 제출합니다. 가능하면 가시성/입력 오류와 allocation처럼 서로 다른 계층을 고릅니다. 모델/mock 테스트는 운영 완료와 무관하게 보조 검증으로 기록합니다. TLS/권한·snapshot restore·multi-node failover는 제공 단일 노드와 별도 관문이며 미실행을 완료로 표기하지 않습니다.
