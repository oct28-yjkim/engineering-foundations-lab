# OpenSearch 확장·복제 장애 실습 — 실제 3→4노드

[실습 입구](README.md) · [운영 진단](../operations.md) · [별도 cluster Compose](../compose.cluster.yaml)

목표는 “노드를 늘리면 해결된다”를 외우는 것이 아니라 **복제본 자리 부족, allocation 설정 오류, 한 노드 이탈, routing 편중을 구분하고 복구하는 것**입니다. 단일 노드 정확성 실습을 마친 뒤 순서대로 수행합니다. 각 카드에서 예상 → 관측 → 경쟁 가설 → 조치 → 정확한 문서 검산을 기록합니다.

**검증 상태(2026-10-04): 아래 명령은 수동 수행 지침이며 실제 클러스터 기동·장애·복구를 실행한 결과가 아닙니다.** 기대값과 실측값을 구별하고 환경이 없으면 미수행으로 표시합니다. Compose 구문 검사는 동작/복제 검증을 대신하지 않습니다.

## 0. 범위와 비용

- 기존 `compose.yaml`/19200/volume과 별도 프로젝트입니다. 기존 서버나 실제 데이터에는 사용하지 않습니다. 모든 명령은 저장소 루트, **PowerShell 7 이상**에서 실행합니다.
- 기본 3개 노드 각각 memory limit 2GiB, heap 512MiB, CPU 1개입니다. 기본 memory limit 합계 6GiB, 선택 4번째 노드 포함 8GiB이며 Docker VM/OS/다른 프로세스 여유가 추가로 필요합니다. limit 합계가 예약량이나 충분한 호스트 메모리 보장은 아닙니다. 여유가 없으면 이 실습을 시작하지 않습니다.
- HTTP는 `127.0.0.1:19210` 하나만 공개하며 transport host port는 없습니다. 보안 플러그인/TLS/인증을 끈 **개인 로컬 합성 데이터 환경**입니다. 같은 호스트/컨테이너 네트워크 접근까지 차단하는 경계가 아니므로 공유 서버·포트 포워딩·운영에 쓰지 않습니다.
- `os-a/b/c`는 cluster-manager-eligible + data + ingest, 선택 `os-d`는 data + ingest입니다. 노드 4개가 되어도 manager 후보는 3개입니다. 전용 manager/다중 AZ 토폴로지를 재현하지 않습니다.
- 최초 bootstrap 목록은 `os-a,b,c`만 사용합니다. `os-d`는 기존 cluster에 join하며 bootstrap 설정이 없습니다. 이 파일은 **새 프로젝트/새 volume용**입니다. 실제 클러스터 확장/이전/재부트스트랩에 복사하지 않습니다. cluster UUID를 잃었을 때 volume 삭제나 강제 bootstrap으로 고치지 않습니다. [공식 bootstrap 설명](https://docs.opensearch.org/latest/tuning-your-cluster/discovery-cluster-formation/bootstrapping/)
- 자동 설치·host sysctl 변경·disk 채우기·무제한 부하·전체 index 설정 변경·volume 삭제는 없습니다. Docker daemon이 꺼졌거나 `vm.max_map_count`/메모리 조건이 부족하면 로그를 확인하고 여기서 멈춥니다. [공식 Docker 조건](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/)
- 최대 **4개 신규 index, 합성 문서 73개**입니다. 고정 ID는 각 신규 index 안에서만 사용합니다. 재실행은 새 UUID를 쓰므로 데이터가 누적됩니다. 이름·용량·실행 일시를 원장에 남깁니다. HTTP 요청별 timeout 70초, 대기 API 60초를 두며 무한 재시도하지 않습니다. 전체 절차에는 전역 자동 종료 타이머가 없습니다.

## 1. 기동·식별·정상 기준선

`up`은 이미지 다운로드·컨테이너/network/volume 생성을 수행합니다. 먼저 예산과 프로젝트 격리를 확인한 뒤 직접 실행합니다. 원래 single-node Compose와 함께 기동할 필요는 없습니다.

```powershell
docker version
docker compose -f search/opensearch/compose.cluster.yaml config --quiet
docker compose -f search/opensearch/compose.cluster.yaml up -d --wait os-a os-b os-c
if ($LASTEXITCODE -ne 0) { throw 'Cluster startup failed; inspect logs, do not continue.' }
docker compose -f search/opensearch/compose.cluster.yaml ps
docker compose -f search/opensearch/compose.cluster.yaml logs --tail=60 os-a os-b os-c
```

다음 helper는 이 문서 전용 loopback URL을 고정합니다. redirect/proxy를 사용하지 않습니다. cluster 식별자는 실수 방지 장치이지 인증은 아닙니다. 이후 모든 코드 블록은 **같은 PowerShell 세션**에서 순서대로 실행합니다. 실패하면 다음 블록으로 넘어가지 않고 해당 카드의 복구 명령부터 확인합니다.

```powershell
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 or later is required.' }
$osLabBase = 'http://127.0.0.1:19210'
$osLabIndexNames = @()
$osCreatedIndices = @{}
function Invoke-OsLab {
    param([ValidateSet('Get','Put','Post')][string]$Method, [string]$Path, $Body)
    if (-not $Path.StartsWith('/') -or $Path.StartsWith('//')) { throw 'Use a local API path.' }
    $apiPath = $Path.Split('?')[0]
    if ($Method -ne 'Get') {
        $parts = $apiPath.TrimStart('/').Split('/')
        $target = $parts[0]
        $creating = $Method -eq 'Put' -and $parts.Count -eq 1
        $explain = $Method -eq 'Post' -and $apiPath -eq '/_cluster/allocation/explain'
        $searching = $Method -eq 'Post' -and $parts.Count -eq 2 -and $parts[1] -eq '_search'
        if ($explain) {
            if ($null -eq $Body -or $Body.index -notin $osLabIndexNames) { throw 'Explain must name this run index.' }
        } else {
            if ($target -notin $osLabIndexNames) { throw 'Request outside this run index list.' }
            if ($creating) {
                if ($osCreatedIndices.ContainsKey($target)) { throw 'Already created; do not recreate.' }
            } elseif (-not $searching) {
                $allowed = ($Method -eq 'Put' -and $parts.Count -eq 2 -and $parts[1] -eq '_settings') -or
                    ($Method -eq 'Post' -and $parts.Count -eq 2 -and $parts[1] -eq '_refresh') -or
                    ($Method -eq 'Put' -and $parts.Count -eq 3 -and $parts[1] -eq '_create' -and
                     $parts[2] -match '^doc-([1-9]|1[0-9]|2[0-4])$')
                if (-not $allowed -or -not $osCreatedIndices.ContainsKey($target)) {
                    throw 'Mutation requires a confirmed fresh run index and an allowed route.'
                }
                Assert-OsLabOwnership $target
            }
        }
    }
    $request = @{
        Uri = $osLabBase + $Path; Method = $Method; TimeoutSec = 70
        MaximumRedirection = 0; NoProxy = $true; ErrorAction = 'Stop'
    }
    if ($null -ne $Body) {
        $request.ContentType = 'application/json'
        $request.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 20 -Compress))
    }
    Invoke-RestMethod @request
}
$identity = Invoke-OsLab Get '/'
if ($identity.cluster_name -ne 'engineering-foundations-opensearch-cluster-lab' -or
    $identity.version.distribution -ne 'opensearch' -or $identity.version.number -ne '3.9.0' -or
    $identity.name -ne 'os-a' -or [string]::IsNullOrEmpty($identity.cluster_uuid) -or
    $identity.cluster_uuid -eq '_na_') { throw 'Unexpected lab server; stop.' }
$osLabUuid = $identity.cluster_uuid
$initialHealth = Invoke-OsLab Get '/_cluster/health?wait_for_nodes=3&wait_for_status=yellow&timeout=60s'
if ($initialHealth.timed_out -or $initialHealth.number_of_nodes -ne 3 -or
    $initialHealth.number_of_data_nodes -ne 3) { throw 'Expected exactly three baseline nodes.' }
$nodeInfo = Invoke-OsLab Get '/_nodes?filter_path=nodes.*.name,nodes.*.roles'
$nodeRows = @($nodeInfo.nodes.PSObject.Properties | ForEach-Object { $_.Value })
if ((($nodeRows.name | Sort-Object) -join ',') -ne 'os-a,os-b,os-c' -or
    @($nodeRows | Where-Object { $_.roles -contains 'cluster_manager' }).Count -ne 3) {
    throw 'Unexpected node names or manager roles.'
}
$nodeRows | Format-Table name,roles
$osRun = [guid]::NewGuid().ToString('N')
$osIndex = "efl-scale-$osRun"
$osBadIndex = "efl-allocation-$osRun"
$osSkewIndex = "efl-skew-$osRun"
$osBalancedIndex = "efl-balanced-$osRun"
$osLabIndexNames = @($osIndex,$osBadIndex,$osSkewIndex,$osBalancedIndex)
$osIndex, $osBadIndex, $osSkewIndex, $osBalancedIndex
```

Index 생성과 검산 함수를 준비합니다. `create`의 `acknowledged=false` 또는 응답 유실은 생성 여부가 불확정이므로 아래 함수는 후속 쓰기를 허용하지 않고 중단합니다. `shards_acknowledged=false`도 “index가 없다”가 아닙니다. 재생성하지 말고 `Invoke-OsLab Get "/${osIndex}/_mapping"`처럼 **해당 사건의 exact 이름**으로 mapping/meta·settings·health를 읽어 확인합니다. 자동 재시도나 확인 목록 강제 등록은 하지 않습니다. 생성 응답의 index·ack와 run marker가 확인된 신규 index만 이후 변경을 허용하고, 매 mutation 전에 marker를 다시 읽습니다. 이 장치는 실수 방지이며 인증/동시 관리자 차단이 아닙니다. [Create Index 응답 의미](https://docs.opensearch.org/latest/api-reference/index-apis/create-index/)

```powershell
function Assert-OsLabOwnership {
    param([string]$Index)
    if ($Index -notin $osLabIndexNames) { throw 'Index outside this run.' }
    $ownership = Invoke-OsLab Get "/${Index}/_mapping"
    $entry = $ownership.PSObject.Properties[$Index]
    if (@($ownership.PSObject.Properties).Count -ne 1 -or $null -eq $entry -or
        $entry.Value.mappings._meta.lab -ne 'efl-scaling-v1' -or
        $entry.Value.mappings._meta.run_id -ne $osRun) { throw 'Index ownership marker mismatch.' }
}
function New-OsLabIndex {
    param([string]$Index, [hashtable]$Settings, [bool]$RequireRouting = $false)
    if ($Index -notin @($osIndex,$osBadIndex,$osSkewIndex,$osBalancedIndex)) { throw 'Index outside this run.' }
    $mapping = @{
        dynamic = 'strict'
        _meta = @{lab='efl-scaling-v1'; run_id=$osRun}
        properties = @{ seq = @{type='integer'}; category = @{type='keyword'}; value = @{type='integer'} }
    }
    if ($RequireRouting) { $mapping._routing = @{required=$true} }
    $created = Invoke-OsLab Put "/${Index}?wait_for_active_shards=0&timeout=10s" @{settings=$Settings; mappings=$mapping}
    if ($created.acknowledged -ne $true -or $created.index -ne $Index) {
        throw "Creation unconfirmed for $Index; read its exact mapping/settings/health before any decision."
    }
    Assert-OsLabOwnership $Index
    $osCreatedIndices[$Index] = $true
    $created
}
function Wait-OsLabGreen {
    param([string]$Index)
    if ($Index -notin $osLabIndexNames) { throw 'Index outside this run.' }
    $primaryCount = if ($Index -eq $osBadIndex) { 1 } else { 4 }
    $health = Invoke-OsLab Get "/_cluster/health/${Index}?wait_for_status=green&wait_for_no_relocating_shards=true&wait_for_no_initializing_shards=true&timeout=60s"
    $actualSettings = (Invoke-OsLab Get "/${Index}/_settings?flat_settings=true").PSObject.Properties[$Index].Value.settings
    if ($health.timed_out -or $health.status -ne 'green' -or $health.unassigned_shards -ne 0 -or
        $health.active_primary_shards -ne $primaryCount -or $health.active_shards -ne (2 * $primaryCount) -or
        $actualSettings.'index.number_of_shards' -ne [string]$primaryCount -or
        $actualSettings.'index.number_of_replicas' -ne '1') {
        throw "Index did not recover: $Index"
    }
    $health
}
function Assert-OsLabDocs {
    param([string]$Index, [object[]]$Expected)
    $result = Invoke-OsLab Post "/${Index}/_search?allow_partial_search_results=false" @{
        size=100; track_total_hits=$true; sort=@(@{seq='asc'}); query=@{match_all=@{}}
    }
    $hits = @($result.hits.hits)
    if ($result.timed_out -or $result._shards.failed -ne 0 -or
        $result.hits.total.relation -ne 'eq' -or $result.hits.total.value -ne $Expected.Count -or
        $hits.Count -ne $Expected.Count) { throw 'Search failed, partial, timed out, or wrong count.' }
    for ($i=0; $i -lt $Expected.Count; $i++) {
        if ($hits[$i]._id -ne "doc-$($Expected[$i].seq)" -or
            $hits[$i]._source.seq -ne $Expected[$i].seq -or
            $hits[$i]._source.category -ne $Expected[$i].category -or
            $hits[$i]._source.value -ne $Expected[$i].value) { throw "Wrong ID/business fields at row $i." }
    }
    "PASS $Index : exact IDs and seq/category/value ($($Expected.Count) documents)"
}
$osExpected = @(1..24 | ForEach-Object { @{seq=$_; category='synthetic'; value=($_ * 10)} })
New-OsLabIndex $osIndex @{number_of_shards=4; number_of_replicas=1}
Wait-OsLabGreen $osIndex
foreach ($doc in $osExpected) {
    $created = Invoke-OsLab Put "/${osIndex}/_create/doc-$($doc.seq)?wait_for_active_shards=all&timeout=10s" $doc
    if ($created.result -ne 'created' -or $created._shards.failed -ne 0) { throw 'Document create failed.' }
}
Invoke-OsLab Post "/${osIndex}/_refresh"
Assert-OsLabDocs $osIndex $osExpected
Invoke-OsLab Get "/_cat/shards/${osIndex}?format=json&h=index,shard,prirep,state,docs,node"
Invoke-OsLab Get '/_nodes/stats/jvm,process,fs,thread_pool?filter_path=nodes.*.name,nodes.*.jvm.mem.heap_used_percent,nodes.*.process.cpu.percent,nodes.*.fs.total.available_in_bytes,nodes.*.thread_pool.write.rejected,nodes.*.thread_pool.search.rejected'
```

기준선은 primary 4 + replica 4 = active copy 8개, exact index green, 문서 ID `doc-1`…`doc-24`, `seq=n/category=synthetic/value=10n`입니다. CPU/heap는 gauge, `rejected`는 프로세스 수명 누적 counter입니다. 사건 전후 UTC 시각과 node ID를 남기고 restart/reset을 고려합니다. shard docs는 replica까지 합산하면 중복이므로 primary만 비교합니다. 정상 기준선이 틀리면 장애를 주입하지 않습니다.

## 2. 사건 A — 노드 3개인데 replica를 3개로 올리니 yellow

**현상/경쟁 가설:** CPU 부족, 디스크 watermark, 노드 미등록, allocation filter, 같은 shard copy를 놓을 서로 다른 data node 부족. replica 수는 primary를 제외한 추가 copy 수입니다. 이 fixture에서는 primary 1 + replica 3을 위해 서로 다른 data node 4개가 필요합니다. replica 추가는 primary shard 수를 늘리지 않습니다.

```powershell
Invoke-OsLab Put "/${osIndex}/_settings" @{index=@{number_of_replicas=3}}
$yellow = Invoke-OsLab Get "/_cluster/health/${osIndex}?wait_for_status=yellow&wait_for_no_initializing_shards=true&timeout=60s"
if ($yellow.timed_out -or $yellow.status -ne 'yellow' -or $yellow.active_primary_shards -ne 4 -or
    $yellow.unassigned_shards -ne 4 -or $yellow.number_of_data_nodes -ne 3) {
    throw 'Expected four unassigned replicas on three data nodes; inspect the actual cause.'
}
Invoke-OsLab Post '/_cluster/allocation/explain?include_disk_info=true' @{index=$osIndex; shard=0; primary=$false}
Invoke-OsLab Get "/_cat/shards/${osIndex}?format=json&h=index,shard,prirep,state,docs,node"
Assert-OsLabDocs $osIndex $osExpected
```

`allocation/explain`의 node별 decider를 읽습니다. 같은 copy가 이미 있는 노드에는 `same_shard`가 거부해야 합니다. disk/filter 같은 다른 거부도 있으면 이 가설만으로 결론 내리지 않습니다. 읽기가 성공해도 요청한 replica 수를 충족한 것은 아닙니다. 일시적인 allocation 진행 상태 때문에 정확한 수가 다르면 실패로 기록하고 설정·shard 상태를 읽습니다. 상태가 안정된 뒤 **관측 GET과 explain만 한 번 더** 수행할 수 있으나 설정 재주입·새 index 생성·무한 polling으로 통과시키지 않습니다. [Allocation Explain](https://docs.opensearch.org/latest/api-reference/cluster-api/cluster-allocation/)

**복구 선택:** 예산이 부족하면 replica를 원래 1로 되돌리고 green·정확성 검산 후 다음 사건으로 갑니다. 예산과 `os-d` 추가를 직접 승인했다면 아래 확장 경로를 수행합니다. 두 경로를 동시에 실행할 필요는 없습니다.

```powershell
# 선택 확장: 추가 memory limit 2GiB / CPU 1개, 새 volume 생성
docker compose -f search/opensearch/compose.cluster.yaml --profile expansion up -d --wait os-d
if ($LASTEXITCODE -ne 0) { throw 'Expansion failed; inspect logs and restore replica=1.' }
$expanded = Invoke-OsLab Get "/_cluster/health/${osIndex}?wait_for_nodes=4&wait_for_status=green&wait_for_no_relocating_shards=true&wait_for_no_initializing_shards=true&timeout=60s"
if ($expanded.timed_out -or $expanded.status -ne 'green' -or $expanded.number_of_nodes -ne 4 -or
    $expanded.number_of_data_nodes -ne 4 -or $expanded.active_shards -ne 16 -or
    $expanded.unassigned_shards -ne 0) { throw 'Expansion has not allocated all sixteen copies.' }
$expandedNodes = Invoke-OsLab Get '/_nodes?filter_path=nodes.*.name,nodes.*.roles'
$expandedRows = @($expandedNodes.nodes.PSObject.Properties | ForEach-Object { $_.Value })
if (@($expandedRows | Where-Object { $_.roles -contains 'cluster_manager' }).Count -ne 3 -or
    @($expandedRows | Where-Object { $_.name -eq 'os-d' -and $_.roles -contains 'data' -and $_.roles -notcontains 'cluster_manager' }).Count -ne 1) {
    throw 'Unexpected expansion roles.'
}
Assert-OsLabDocs $osIndex $osExpected
Invoke-OsLab Get "/_cat/shards/${osIndex}?format=json&h=index,shard,prirep,state,docs,node"
```

다음 원복 블록은 확장을 수행했든 생략했든 실행합니다. 확장 오류로 중단했을 때도 예산/로그를 확인한 후 같은 exact index에 적용할 수 있습니다.

```powershell
# 확장 수행/생략 모두 공통: 원래 replica 설정으로 복구
Invoke-OsLab Put "/${osIndex}/_settings" @{index=@{number_of_replicas=1}}
Wait-OsLabGreen $osIndex
Assert-OsLabDocs $osIndex $osExpected
```

확장에 성공했다면 `os-d`는 이후 카드 동안 유지합니다. 종료 시 같이 stop합니다. 이 사건은 **copy 배치 가능성**을 검증하며 처리량 향상·검색 지연 개선은 측정하지 않습니다. 예산 부족/확장 미수행이면 확장 통과로 기록하지 않습니다. 원복 기준은 replica 1, active copy 8개, unassigned 0, 정확한 24개 문서입니다.

## 3. 사건 B — 노드는 정상인데 새 index만 red

**현상/경쟁 가설:** 없는 노드 이름을 require filter로 지정한 신규 index는 primary조차 배치되지 않습니다. 노드 장애·disk watermark·부트스트랩 실패와 구분해야 합니다. 기존 index에 강제 이주 설정을 걸지 않고 **빈 신규 index 하나**로 재현합니다. red 상태 동안 cluster health도 red가 될 수 있어 Compose healthcheck가 unhealthy로 표시되는 것은 이 카드의 예상 영향입니다.

```powershell
New-OsLabIndex $osBadIndex @{
    number_of_shards=1; number_of_replicas=1
    'routing.allocation.require._name'='efl-no-such-node'
}
$bad = Invoke-OsLab Get "/_cluster/health/${osBadIndex}?timeout=10s"
if ($bad.status -ne 'red' -or $bad.active_primary_shards -ne 0) { throw 'Expected an unassigned primary.' }
Invoke-OsLab Get "/${osBadIndex}/_settings?flat_settings=true"
Invoke-OsLab Post '/_cluster/allocation/explain?include_disk_info=true' @{index=$osBadIndex; shard=0; primary=$true}
Invoke-OsLab Get '/_nodes?filter_path=nodes.*.name,nodes.*.roles'
Assert-OsLabDocs $osIndex $osExpected

# 복구 대상은 방금 만든 exact index 하나뿐이다. cluster-wide settings는 변경하지 않는다.
Invoke-OsLab Put "/${osBadIndex}/_settings" @{index=@{'routing.allocation.require._name'=$null}}
Wait-OsLabGreen $osBadIndex
$osBadExpected = @(@{seq=1; category='synthetic'; value=10})
Invoke-OsLab Put "/${osBadIndex}/_create/doc-1?wait_for_active_shards=all&timeout=10s" $osBadExpected[0]
Invoke-OsLab Post "/${osBadIndex}/_refresh"
Assert-OsLabDocs $osBadIndex $osBadExpected
Assert-OsLabDocs $osIndex $osExpected
```

실제 결과의 `filter` decider와 `efl-no-such-node` 조건을 연결합니다. 존재하는 노드를 계속 추가해도 잘못된 이름 조건은 해결되지 않습니다. index 생성이 `acknowledged=true`여도 shard 준비와 데이터 요청 성공을 따로 검증해야 합니다. 복구는 require 조건을 `null`로 해제한 해당 index green, primary 1 + replica 1, 정확한 `doc-1`의 필드, 기존 24개 문서 보존입니다. 실패 시 새 index에 데이터를 더 넣거나 모든 index filter를 해제하지 않습니다. [Index allocation filtering](https://docs.opensearch.org/latest/api-reference/index-apis/shard-allocation/) · [Index 설정 변경](https://docs.opensearch.org/latest/api-reference/index-apis/update-settings/)

## 4. 사건 C — 한 노드 중지, 조회와 cluster-manager quorum 확인

**사전 조건:** 사건 B의 red를 복구했고 모든 실습 index는 replica 1/green입니다. `os-a`는 HTTP 입구이므로 중지하지 않습니다. 세 manager 후보 중 **os-c 하나만** 중지합니다. 다른 프로세스가 멈췄거나 노드 수가 예상과 다르면 진행하지 않습니다.

```powershell
Wait-OsLabGreen $osIndex
Wait-OsLabGreen $osBadIndex
$beforeStop = Invoke-OsLab Get '/_cluster/health?wait_for_status=green&timeout=60s'
if ($beforeStop.timed_out -or $beforeStop.number_of_nodes -notin @(3,4)) { throw 'Unexpected baseline.' }
$osBeforeStopCount = [int]$beforeStop.number_of_nodes
Invoke-OsLab Get '/_cluster/state?filter_path=cluster_manager_node,master_node,metadata.cluster_coordination.last_committed_config'
$osIncidentError = $null
$osRecoveryError = $null
try {
    docker compose -f search/opensearch/compose.cluster.yaml stop os-c
    if ($LASTEXITCODE -ne 0) { throw 'Stop failed; inspect actual container state.' }
    $remaining = $osBeforeStopCount - 1
    $degraded = Invoke-OsLab Get "/_cluster/health/${osIndex}?wait_for_nodes=${remaining}&wait_for_status=yellow&timeout=60s"
    if ($degraded.timed_out -or $degraded.number_of_nodes -ne $remaining -or
        $degraded.active_primary_shards -ne 4 -or $degraded.status -eq 'red') {
        throw 'Expected surviving active primaries; inspect before further changes.'
    }
    $remainingInfo = Invoke-OsLab Get '/_nodes?filter_path=nodes.*.name,nodes.*.roles'
    $remainingRows = @($remainingInfo.nodes.PSObject.Properties | ForEach-Object { $_.Value })
    if (@($remainingRows | Where-Object { $_.roles -contains 'cluster_manager' }).Count -ne 2 -or
        $remainingRows.name -contains 'os-c') { throw 'Unexpected remaining manager candidates.' }
    Invoke-OsLab Get '/_cluster/state?filter_path=cluster_manager_node,master_node,metadata.cluster_coordination.last_committed_config'
    Invoke-OsLab Get "/_cat/shards/${osIndex}?format=json&h=index,shard,prirep,state,docs,node"
    $read = Invoke-OsLab Get "/${osIndex}/_doc/doc-1"
    if (-not $read.found -or $read._source.seq -ne 1 -or $read._source.category -ne 'synthetic' -or
        $read._source.value -ne 10) { throw 'Realtime document read failed.' }
    Assert-OsLabDocs $osIndex $osExpected
    Assert-OsLabDocs $osBadIndex $osBadExpected
} catch {
    $osIncidentError = $_
} finally {
    # 정상 예외 경로에서도 동일 노드 복귀와 실제 회복을 확인한다.
    # 셸 강제 종료/host 중단까지 보장하는 자동 복구 장치는 아니다.
    try {
        docker compose -f search/opensearch/compose.cluster.yaml start os-c
        if ($LASTEXITCODE -ne 0) { throw 'os-c restart failed; inspect logs before continuing.' }
        $restored = Invoke-OsLab Get "/_cluster/health?wait_for_nodes=${osBeforeStopCount}&wait_for_status=green&wait_for_no_relocating_shards=true&wait_for_no_initializing_shards=true&timeout=60s"
        if ($restored.timed_out -or $restored.status -ne 'green' -or $restored.unassigned_shards -ne 0 -or
            $restored.number_of_nodes -ne $osBeforeStopCount) { throw 'Cluster has not recovered.' }
        if ((Invoke-OsLab Get '/').cluster_uuid -ne $osLabUuid) { throw 'Cluster UUID changed; stop.' }
        Wait-OsLabGreen $osIndex
        Wait-OsLabGreen $osBadIndex
        Assert-OsLabDocs $osIndex $osExpected
        Assert-OsLabDocs $osBadIndex $osBadExpected
    } catch {
        $osRecoveryError = $_
    }
}
if ($null -ne $osRecoveryError) {
    if ($null -ne $osIncidentError) { Write-Warning 'The incident also failed; its original error remains in $osIncidentError.' }
    throw $osRecoveryError
}
if ($null -ne $osIncidentError) { throw $osIncidentError }
```

**해석:** 노드 이탈 후 일시적인 yellow/relocation이 가능하며 남은 노드에 replica를 다시 놓아 green이 먼저 될 수도 있습니다. yellow가 반드시 60초 유지된다고 가정하지 않습니다. `os-c`가 당시에 manager였다면 선출을, 아니었다면 manager 유지 상태를 기록합니다. 두 후보 생존·cluster state·정확한 조회로 관측한 범위를 설명하되, quorum을 잃는 두 노드 중지는 수행하지 않습니다. HTTP 단일 입구 장애, 프로세스 강제 kill, 네트워크 partition, AZ 손실, 디스크 손실·snapshot DR를 증명한 실험은 아닙니다. 클라이언트 retry/latency SLO 검증도 별도입니다. [Discovery와 quorum 문서 입구](https://docs.opensearch.org/latest/tuning-your-cluster/discovery-cluster-formation/) · [Cluster Health](https://docs.opensearch.org/latest/api-reference/cluster-api/cluster-health/)

## 5. 사건 D — 노드를 늘렸는데 특정 routing 편중은 그대로

이 카드는 실제 index의 **데이터 편중**을 재현합니다. 문서 24개로 CPU 병목/hot-thread/429를 재현했다고 주장하지 않습니다. “노드 개수”, “primary shard 개수”, “routing 분산”이 다른 레버라는 점을 직접 확인합니다. 카드 A에서 확장을 생략해도 3개 data node에서 수행할 수 있지만 “확장 후 실측”으로 제출하지 않습니다.

```powershell
New-OsLabIndex $osSkewIndex @{number_of_shards=4; number_of_replicas=1} $true
Wait-OsLabGreen $osSkewIndex
foreach ($doc in $osExpected) {
    $created = Invoke-OsLab Put "/${osSkewIndex}/_create/doc-$($doc.seq)?routing=one-tenant&wait_for_active_shards=all&timeout=10s" $doc
    if ($created.result -ne 'created' -or $created._shards.failed -ne 0) { throw 'Routed create failed.' }
}
Invoke-OsLab Post "/${osSkewIndex}/_refresh"
Assert-OsLabDocs $osSkewIndex $osExpected
$skewShards = Invoke-OsLab Get "/_cat/shards/${osSkewIndex}?format=json&h=shard,prirep,state,docs,node"
$skewPrimary = @($skewShards | Where-Object { $_.prirep -eq 'p' })
$skewPrimary | Format-Table
if ($skewPrimary.Count -ne 4 -or @($skewPrimary | Where-Object { [int]$_.docs -gt 0 }).Count -ne 1 -or
    ($skewPrimary | Measure-Object -Property docs -Sum).Sum -ne 24) { throw 'Expected a single populated primary.' }
$routedGet = Invoke-OsLab Get "/${osSkewIndex}/_doc/doc-1?routing=one-tenant"
if (-not $routedGet.found -or $routedGet._source.value -ne 10) { throw 'Routed GET failed.' }

# 적용 후보 비교: 별도 새 index에 원본 fixture를 ID routing으로 다시 넣는다.
# 기존 routing index/애플리케이션/alias를 바꾸는 운영 migration이 아니다.
New-OsLabIndex $osBalancedIndex @{number_of_shards=4; number_of_replicas=1}
Wait-OsLabGreen $osBalancedIndex
foreach ($doc in $osExpected) {
    $created = Invoke-OsLab Put "/${osBalancedIndex}/_create/doc-$($doc.seq)?wait_for_active_shards=all&timeout=10s" $doc
    if ($created.result -ne 'created' -or $created._shards.failed -ne 0) { throw 'Comparison create failed.' }
}
Invoke-OsLab Post "/${osBalancedIndex}/_refresh"
Assert-OsLabDocs $osBalancedIndex $osExpected
$balancedShards = Invoke-OsLab Get "/_cat/shards/${osBalancedIndex}?format=json&h=shard,prirep,state,docs,node"
$balancedPrimary = @($balancedShards | Where-Object { $_.prirep -eq 'p' })
$balancedPrimary | Format-Table
if (@($balancedPrimary | Where-Object { [int]$_.docs -gt 0 }).Count -lt 2 -or
    ($balancedPrimary | Measure-Object -Property docs -Sum).Sum -ne 24) {
    throw 'Expected multiple populated primaries; record actual routing distribution.'
}
Assert-OsLabDocs $osSkewIndex $osExpected
```

**진단과 조치 판단:** 노드별 CPU만 보지 말고 primary별 docs·store bytes·indexing/search counters를 확인합니다. 같은 routing 값은 같은 primary에 모이며 노드 추가만으로 그 routing을 여러 primary로 나누지 않습니다. 반면 replica로 검색을 분산할 수 있으므로 “추가 노드는 항상 무의미하다”고 결론 내리지 않습니다. 비교 index의 ID routing이 완전히 균등해진다는 보장도 없습니다.

운영에서는 tenant locality, 정확한 GET/update/delete routing, 권한 경계, dual-write/backfill, 검산, alias 전환과 rollback을 검토해야 합니다. 이 작은 카드의 복구/비교 완료 조건은 두 index의 정확한 24개 업무 문서 일치, 원본 routing index 보존, 비교 index에 둘 이상의 populated primary 관측입니다. 기존 index의 routing을 즉석에서 바꾸거나 routing 없이 update하지 않습니다. 실제 성능 개선은 동일 부하/시간 창/오류율로 별도 측정해야 합니다. [Search shard routing](https://docs.opensearch.org/latest/search-plugins/searching-data/search-shard-routing/) · [Routing metadata와 CRUD 일관성](https://docs.opensearch.org/latest/mappings/metadata-fields/routing/)

## 6. 증거·종료

각 사건마다 환경/version/digest/commit, cluster UUID, exact index 목록, UTC 시작/종료, node 역할, health/shard 상태, allocation decider, 가설 기각 근거, 조치, 원복, ID·업무 필드 비교를 기록합니다. green·문서 count만으로 통과시키지 않습니다. 정상/장애/복구의 관측을 [사건 보고서](../../../operations/incident-report-template.md)에 남깁니다.

```powershell
docker compose -f search/opensearch/compose.cluster.yaml --profile expansion ps
docker compose -f search/opensearch/compose.cluster.yaml --profile expansion logs --tail=60
docker image inspect opensearchproject/opensearch:3.9.0 --format '{{json .RepoDigests}}'
docker compose -f search/opensearch/compose.cluster.yaml --profile expansion stop
```

마지막 명령은 이 별도 프로젝트의 노드만 중지하고 volume을 보존합니다. `down -v`, wildcard index 삭제, 시스템 데이터 디렉터리 삭제는 제공하지 않습니다. 같은 volume로 다시 시작하면 이전 index와 replica/routing 설정도 남습니다. 새 run을 시작하기 전 기존 장애 원복·노드 수·디스크 여유를 확인합니다. `os-d`가 계속 존재하는 4노드 상태에서는 사건 A의 “3노드인데 copy 4개” 전제가 성립하지 않으므로 무작정 반복하지 않습니다. 학습용 데이터 정리는 소유권과 보존 필요를 확인한 별도 결정입니다.
