# Qdrant 3노드 복제와 가용성 LAB

[기본 LAB](README.md) · [환경](../environment.md) · [운영](../operations.md)

목표는 **node 수, shard 수, replica 수, metadata consensus, point read/write consistency를 구분**하는 것입니다. 준비된 3노드 Compose와 아래 수동 REST 절차를 제공합니다. 작성 시 실제 엔진 실행은 미검증이며 네트워크 partition·AZ 손실·운영 HA 인증 실습은 아닙니다.

## 준비와 정상 상태

저장소 루트에서 실행합니다. 단일 노드 Compose와 합치지 않습니다. 총 container 한도 3GiB·3CPU 외에 OS/Docker 여유 자원을 확보하고 host port 16343–16345가 비어 있는지 확인합니다. 사용자 앱/실제 데이터를 연결하지 않습니다.

```text
docker compose -f search/qdrant/compose.cluster.yaml config --services
docker compose -f search/qdrant/compose.cluster.yaml up -d qdrant1
docker compose -f search/qdrant/compose.cluster.yaml up -d qdrant2 qdrant3
docker compose -f search/qdrant/compose.cluster.yaml ps
```

PowerShell 7에서 세 endpoint의 `/`, `/readyz`, `/cluster`를 읽습니다. 최대 60초 동안 직접 상태를 확인합니다. 3개의 서로 다른 peer ID, 같은 peer 집합과 leader, 정상 consensus를 얻기 전 collection을 만들지 않습니다. `depends_on`은 API/consensus 준비 완료를 뜻하지 않습니다.

```powershell
$ErrorActionPreference = 'Stop'
$qcPorts = @(16343,16344,16345)
foreach ($qcPort in $qcPorts) {
    Invoke-RestMethod -Uri "http://127.0.0.1:$qcPort/" -NoProxy -TimeoutSec 10
    Invoke-RestMethod -Uri "http://127.0.0.1:$qcPort/readyz" -NoProxy -TimeoutSec 10
    Invoke-RestMethod -Uri "http://127.0.0.1:$qcPort/cluster" -NoProxy -TimeoutSec 10
}
$qcName = 'efl_qdrant_cluster_' + [guid]::NewGuid().ToString('N')
function Invoke-QcLab {
    param([string]$Method,[string]$Path,$Body=$null,[int]$Port=16343)
    if ($Port -notin @(16343,16344,16345)) { throw 'LAB endpoint만 허용' }
    $qcRequest=@{Method=$Method;Uri="http://127.0.0.1:$Port$Path";NoProxy=$true;TimeoutSec=15;MaximumRedirection=0}
    if ($null -ne $Body) { $qcRequest.ContentType='application/json';$qcRequest.Body=ConvertTo-Json -InputObject $Body -Depth 20 -Compress }
    Invoke-RestMethod @qcRequest
}
if ((Invoke-QcLab GET '/collections').result.collections.name -contains $qcName) { throw '기존 이름 사용 금지' }
Invoke-QcLab PUT "/collections/$qcName" @{
    vectors=@{size=2;distance='Dot'};shard_number=3;replication_factor=3;write_consistency_factor=3
}
Invoke-QcLab GET "/collections/$qcName"
foreach ($qcPort in $qcPorts) { Invoke-QcLab GET "/collections/$qcName/cluster" -Port $qcPort }
```

정상 기대는 shard 3개 각각의 replica 3개, 총 9개 shard copy입니다. 각 peer에서 local/remote shard 상태와 transfer를 대조합니다. 최대 60초 내 모든 copy가 `Active`, transfer 없음, optimizer 오류 없음이 되지 않으면 logs/배치를 조사하고 장애를 넣지 않습니다. shard/peer ID는 실제 응답에서 읽고 번호를 추측하지 않습니다. peer ID는 uint64이므로 JavaScript 부동소수점으로 왕복 변환하지 않습니다.

```powershell
$qcPoints = @(1..6 | ForEach-Object { @{id=$_;vector=@($_,1);payload=@{tenant='synthetic';seq=$_}} })
Invoke-QcLab PUT "/collections/$qcName/points?wait=true&ordering=weak" @{points=$qcPoints}
Invoke-QcLab POST "/collections/$qcName/points/count" @{exact=$true}
Invoke-QcLab POST "/collections/$qcName/points/query?consistency=all" @{
    query=@(1,0);limit=6;params=@{exact=$true};with_payload=$true
}
```

예상 count=6, query ID 순서=6,5,4,3,2,1, Dot score=6,5,4,3,2,1입니다. 다른 포트에서도 같은 요청으로 ID/score를 검산합니다. latency는 client wall time과 server `time`을 나누고 `/metrics`·collection cluster 상태를 같은 시각에 기록합니다. 6-point 전수 조회는 처리량 benchmark가 아닙니다.

## 사건 1: 한 노드 이탈과 엄격한 쓰기 조건

정상 기준선 이후 **qdrant3 하나만** 정지합니다. 전체 LAB 10분, 정지 상태는 2분 이내를 예산으로 정합니다. collection/volume/peer를 삭제하지 않습니다.

```text
docker compose -f search/qdrant/compose.cluster.yaml stop qdrant3
```

생존 node의 `/cluster`와 collection `/cluster`를 읽어 consensus leader 변화와 replica 상태를 구분합니다. 3-copy 모두의 적용을 요구하는 write consistency 3에서 다음 요청을 **한 번만** 보냅니다.

```powershell
$qcCanary = @{id=99;vector=@(9,1);payload=@{tenant='synthetic';seq=99;purpose='availability-canary'}}
$qcTimer = [Diagnostics.Stopwatch]::StartNew()
$qcFailure = $null
try {
    Invoke-QcLab PUT "/collections/$qcName/points?wait=true&ordering=weak&timeout=3" @{points=@($qcCanary)}
    '정지/replica 상태와 실제 반영을 재확인: 성공이면 기대한 장애가 아직 미재현일 수 있음'
} catch {
    $qcFailure = $_
    $qcStatus = if ($null -ne $_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 'transport/timeout' }
    "요청 실패: status=$qcStatus elapsed_ms=$($qcTimer.ElapsedMilliseconds); point 99 반영 여부는 별도로 확인"
} finally {
    $qcTimer.Stop()
}
Invoke-QcLab POST "/collections/$qcName/points?consistency=majority" @{ids=@(99);with_payload=$true;with_vector=$true}
```

write 실패/timeout은 **어느 replica에도 반영되지 않았다는 뜻이 아닙니다**. `$qcFailure.ErrorDetails.Message`와 예외는 이 합성 환경에서 로컬로만 확인하고, 공유 기록에는 상태 코드·원인 분류·경과 시간만 옮깁니다. 네트워크 오류와 서버 거부를 구분하고 성공분·unknown을 남깁니다. client timeout만 늘리거나 새 ID로 무조건 재시도하지 않습니다. backend metadata consensus가 정상이어도 collection의 요구 replica 조건은 충족하지 못할 수 있습니다.

## 사건 2: 가용성 조건을 바꾸고 동일 ID로 회복

의도적으로 일관성 조건을 낮추는 학습용 변경입니다. 운영에서 무조건 적용할 해결책이 아니며, 두 생존 replica와 같은 payload의 ID 99를 사용합니다. config 변경에는 정상 metadata consensus가 필요합니다.

```powershell
Invoke-QcLab PATCH "/collections/$qcName" @{params=@{write_consistency_factor=2}}
Invoke-QcLab PUT "/collections/$qcName/points?wait=true&ordering=weak&timeout=5" @{points=@($qcCanary)}
Invoke-QcLab POST "/collections/$qcName/points?consistency=majority" @{ids=@(99);with_payload=$true;with_vector=$true}
Invoke-QcLab POST "/collections/$qcName/points/query?consistency=majority" @{query=@(1,0);limit=7;params=@{exact=$true}}
```

회복 oracle은 point 99의 정확한 값과 전체 ID **99,6,5,4,3,2,1**입니다. 요청 성공만으로 전체 replica 동기화를 선언하지 않습니다. 실패하면 반복 재전송하지 말고 node를 복귀시켜 원래 건강한 topology를 회복합니다.

```text
docker compose -f search/qdrant/compose.cluster.yaml start qdrant3
```

최대 60초 동안 3개 peer의 replica가 모두 Active, transfer 없음인지 관찰합니다. 정상화 뒤 read consistency `all`로 전체 7개 ID/값을 검산하고 write consistency를 3으로 복원합니다.

```powershell
foreach ($qcPort in $qcPorts) { Invoke-QcLab GET "/collections/$qcName/cluster" -Port $qcPort }
Invoke-QcLab POST "/collections/$qcName/points/query?consistency=all" @{query=@(1,0);limit=7;params=@{exact=$true};with_payload=$true}
Invoke-QcLab PATCH "/collections/$qcName" @{params=@{write_consistency_factor=3}}
Invoke-QcLab PUT "/collections/$qcName/points?wait=true&ordering=weak" @{points=@($qcCanary)}
Invoke-QcLab POST "/collections/$qcName/points/count" @{exact=$true}
```

최종 count=7, ID/값·원래 consistency 설정·9개 active copy를 확인합니다. 마지막 upsert는 새 업무 이벤트가 아니라 동일 ID/동일 값의 확인입니다. 이것은 모든 동시 writer·out-of-order 업데이트의 업무적 멱등성을 증명하지 않습니다.

## 확장·재배치에서 반드시 조사할 질문

- 노드 추가가 기존 shard를 자동 재분배하는가? collection shard/replica 설정과 실제 배치의 차이를 관찰합니다.
- `move_shard`와 `replicate_shard`가 source copy·replica 수·transfer 비용에 주는 차이는 무엇인가? 이 LAB은 자동 이동 명령을 실행하지 않습니다.
- custom shard key를 사용하면 tenant filter, shard selector, 인가 경계는 각각 무엇인가? tenant 하나가 큰 경우의 편중을 설계합니다.
- resharding/자동 rebalance는 현재 OSS·Cloud·배포 형태에서 어디까지 지원되는가? OpenAPI에 이름이 있다는 것만으로 제공 기능/운영 지원을 확정하지 않습니다.
- Raft metadata 합의와 point 업데이트의 `ordering`, `write_consistency_factor`, read `consistency`는 서로 어떤 질문에 답하는가?

이 항목들은 기본 3노드 사건의 실행 완료와 별도의 확장 상태입니다. [공식 분산 배포](https://qdrant.tech/documentation/scaling/distributed_deployment/), [일관성 설명](https://qdrant.tech/documentation/scaling/consistency-guarantees/)과 고정 [OpenAPI](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/docs/redoc/master/openapi.json)를 대조합니다.

종료는 아래 명령으로 합니다. 모든 named volume과 collection은 남습니다. 실패 시에도 강제 peer 제거·volume 삭제·재초기화로 성공처럼 만들지 않습니다.

```text
docker compose -f search/qdrant/compose.cluster.yaml stop
```
