# Qdrant 기능 탐구 LAB

[기본 LAB](README.md) · [기능 지도](../feature-map.md) · [분산 기능](cluster.md)

사용하지 않는 기능도 **목적→실행→관측→제약/반례→대안**으로 배웁니다. 아래는 단일 노드에서 실행할 수 있는 수동 절차입니다. 작성 시 서버 실측은 미수행이며 예상값을 실제 결과로 바꾸어 기록합니다. tiny fixture로 ANN 성능·운영 복구를 입증하지 않습니다.

## 공통 준비

[환경](../environment.md)의 단일 노드 1.19.1과 PowerShell 7 새 터미널을 사용합니다. 실행당 새 이름으로 최대 4개 collection·7개 point·snapshot 1개만 만듭니다. 아래 명령을 한 번씩 실행하며 오류면 중단합니다. 전체 10분을 예산으로 하고 별도 부하나 자동 재시도는 넣지 않습니다.

```powershell
$ErrorActionPreference = 'Stop'
$qdBase = 'http://127.0.0.1:16333'
$qdPrefix = 'efl_qdrant_adv_' + [guid]::NewGuid().ToString('N')
$qdSource = $qdPrefix + '_source'
$qdTarget = $qdPrefix + '_target'
$qdMulti = $qdPrefix + '_multi'
$qdRestore = $qdPrefix + '_restore'
$qdAlias = $qdPrefix + '_read'
function Invoke-QdLab {
    param([string]$Method, [string]$Path, $Body = $null)
    $qdRequest = @{ Method=$Method; Uri=($qdBase + $Path); TimeoutSec=20; NoProxy=$true; MaximumRedirection=0 }
    if ($null -ne $Body) {
        $qdRequest.ContentType = 'application/json'
        $qdRequest.Body = ConvertTo-Json -InputObject $Body -Depth 30 -Compress
    }
    Invoke-RestMethod @qdRequest
}
if ((Invoke-QdLab GET '/').version -ne '1.19.1') { throw '서버 버전 불일치' }
$qdExisting = (Invoke-QdLab GET '/collections').result.collections.name
if (@($qdSource,$qdTarget,$qdMulti,$qdRestore) | Where-Object { $_ -in $qdExisting }) { throw '기존 이름 사용 금지' }
Invoke-QdLab PUT "/collections/$qdSource" @{vectors=@{size=2;distance='Dot'}}
Invoke-QdLab PUT "/collections/$qdSource/points?wait=true" @{points=@(
    @{id=1;vector=@(1,0);payload=@{revision='v1';offers=@(@{color='red';size='S'},@{color='blue';size='L'})}},
    @{id=2;vector=@(0,1);payload=@{revision='v1';offers=@(@{color='red';size='L'})}}
)}
```

점수의 oracle은 Dot product입니다. source의 `[1,0]` 검색은 ID 1 점수 1, ID 2 점수 0입니다. names와 baseline을 기록하고 실제 요청/응답은 합성 범위만 보존합니다. 함수는 로컬 요청 편의 함수이지 운영용 인증/인가 wrapper가 아닙니다.

## A. 배열 필터와 nested의 차이

서로 다른 배열 원소에서 조건을 각각 만족하는 것과 **같은 원소**가 두 조건을 만족하는 것을 구분합니다.

```powershell
$qdFlat = Invoke-QdLab POST "/collections/$qdSource/points/query" @{
    query=@(1,0);limit=2;params=@{exact=$true};with_payload=$true
    filter=@{must=@(@{key='offers[].color';match=@{value='red'}},@{key='offers[].size';match=@{value='L'}})}
}
$qdNested = Invoke-QdLab POST "/collections/$qdSource/points/query" @{
    query=@(1,0);limit=2;params=@{exact=$true};with_payload=$true
    filter=@{must=@(@{nested=@{key='offers';filter=@{must=@(
        @{key='color';match=@{value='red'}},@{key='size';match=@{value='L'}}
    )}}})}
}
$qdFlat.result.points | Select-Object id,score
$qdNested.result.points | Select-Object id,score
```

예상: flat은 **1,2**, nested는 **2만**입니다. 같은 count인지보다 실제 ID 집합을 비교합니다. 잘못된 필터를 nested로 바꾸는 것이 조치이고 source payload를 답에 맞추어 편집하지 않습니다. payload index가 있어도 잘못된 논리식은 자동 수정되지 않습니다. [공식 filtering](https://qdrant.tech/documentation/concepts/filtering/)

## B. Multivector MaxSim과 single-vector 비교

문서당 여러 벡터를 보관하고 query 벡터별 최대 유사도를 합산하는 작은 반례입니다. 실제 ColBERT 모델/토큰화/의미 품질을 검증하는 실험이 아닙니다.

```powershell
Invoke-QdLab PUT "/collections/$qdMulti" @{vectors=@{late=@{
    size=2;distance='Dot';multivector_config=@{comparator='max_sim'};hnsw_config=@{m=0}
}}}
Invoke-QdLab PUT "/collections/$qdMulti/points?wait=true" @{points=@(
    @{id=1;vector=@{late=@(@(1,0),@(0,1))}},
    @{id=2;vector=@{late=@(,@(1,0))}}
)}
$qdLate = Invoke-QdLab POST "/collections/$qdMulti/points/query" @{
    query=@(@(1,0),@(0,1));using='late';limit=2;params=@{exact=$true}
}
$qdLate.result.points | Select-Object id,score
```

예상: ID 1은 `max(1,0)+max(0,1)=2`, ID 2는 `1+0=1`입니다. `m=0`은 이 named vector의 HNSW 생성을 끄는 선택입니다. late interaction을 항상 전체 corpus에 실행하는 것이 좋은 설계라는 뜻이 아닙니다. 첫 단계 후보 수·문서 벡터 수가 재랭킹 비용에 미치는 영향을 별도 데이터로 측정합니다. [공식 vectors](https://qdrant.tech/documentation/concepts/vectors/)

## C. Strict mode 제한과 복구

허용 query limit을 1로 제한하여 정상 요청과 거부를 구분합니다. limit은 이 LAB의 임의 안전 기준이며 제품의 보편적 상한이 아닙니다.

```powershell
Invoke-QdLab PATCH "/collections/$qdSource" @{strict_mode_config=@{enabled=$true;max_query_limit=1}}
$qdRejected = $false
try {
    Invoke-QdLab POST "/collections/$qdSource/points/query" @{query=@(1,0);limit=2}
} catch {
    if ($null -eq $_.Exception.Response) { throw }
    $qdStatus = [int]$_.Exception.Response.StatusCode
    if ($qdStatus -lt 400 -or $qdStatus -ge 500) { throw }
    $qdRejected = $true
    "제한 요청 HTTP $qdStatus; 실제 diagnostic이 max_query_limit 거부인지 로컬에서 확인"
}
if (-not $qdRejected) { throw '예상한 제한을 재현하지 못함' }
Invoke-QdLab POST "/collections/$qdSource/points/query" @{query=@(1,0);limit=1}
Invoke-QdLab PATCH "/collections/$qdSource" @{strict_mode_config=@{enabled=$false}}
Invoke-QdLab POST "/collections/$qdSource/points/query" @{query=@(1,0);limit=2;params=@{exact=$true}}
```

정상 limit=1은 ID 1, 복원 뒤 limit=2는 ID 1,2여야 합니다. 4xx만으로 올바른 원인을 확정하지 말고 message·설정·endpoint를 대조합니다. collection info의 실제 strict 설정도 확인합니다. 운영에서 문제를 해결하기 위해 제한을 무조건 끄라는 뜻이 아닙니다. unindexed filtering·batch/rate/timeout 제한은 각각 독립 조건이며 하나의 quota로 합치지 않습니다. [strict mode](https://qdrant.tech/documentation/ops-configuration/administration/#strict-mode)

## D. Alias 원자적 전환과 원복

새 collection을 준비한 뒤 읽기 alias를 바꿉니다. alias 이름은 위에서 생성한 고유 이름이며 기존 alias를 사용하지 않습니다.

```powershell
if ((Invoke-QdLab GET '/aliases').result.aliases.alias_name -contains $qdAlias) { throw '기존 alias 사용 금지' }
Invoke-QdLab PUT "/collections/$qdTarget" @{vectors=@{size=2;distance='Dot'}}
Invoke-QdLab PUT "/collections/$qdTarget/points?wait=true" @{points=@(@{id=11;vector=@(1,0);payload=@{revision='v2'}})}
Invoke-QdLab POST '/collections/aliases' @{actions=@(@{create_alias=@{collection_name=$qdSource;alias_name=$qdAlias}})}
Invoke-QdLab POST "/collections/$qdAlias/points/query" @{query=@(1,0);limit=2;params=@{exact=$true}}
Invoke-QdLab POST '/collections/aliases' @{actions=@(
    @{delete_alias=@{alias_name=$qdAlias}},@{create_alias=@{collection_name=$qdTarget;alias_name=$qdAlias}}
)}
Invoke-QdLab POST "/collections/$qdAlias/points/query" @{query=@(1,0);limit=2;params=@{exact=$true}}
Invoke-QdLab POST '/collections/aliases' @{actions=@(
    @{delete_alias=@{alias_name=$qdAlias}},@{create_alias=@{collection_name=$qdSource;alias_name=$qdAlias}}
)}
Invoke-QdLab POST "/collections/$qdAlias/points/query" @{query=@(1,0);limit=2;params=@{exact=$true}}
```

기대 ID 집합은 **{1,2}→{11}→{1,2}**입니다. 두 alias 동작을 **한 요청**에 넣는 이유를 설명합니다. alias 전환은 데이터 복사·dual write·embedding 모델 호환성·전체 client의 캐시 무효화가 아닙니다. dimension을 바꾸는 실제 모델 migration에는 writer/reader 계약과 평가가 먼저 필요합니다. 이전 collection은 확인 없이 삭제하지 않습니다. [collection aliases](https://qdrant.tech/documentation/manage-data/collections/#collection-aliases)

## E. Snapshot 생성과 다른 이름으로 복원

위 source는 2개 point인 상태여야 합니다. source의 쓰기를 멈추고 snapshot을 1개만 만듭니다. **기존 collection에 복원하지 않고**, 새 `$qdRestore`에만 복원합니다. 설정·payload·point·검색 결과를 따로 검산합니다.

```powershell
$qdSnapshot = (Invoke-QdLab POST "/collections/$qdSource/snapshots").result
if ($qdSnapshot.name -notmatch '^[A-Za-z0-9_.-]+\.snapshot$') { throw 'snapshot 이름 확인 필요' }
$qdSnapshot | Select-Object name,size,checksum,creation_time
if ((Invoke-QdLab GET '/collections').result.collections.name -contains $qdRestore) { throw '복원 대상은 새 이름이어야 함' }
$qdRecovery = @{
    location="http://127.0.0.1:6333/collections/$qdSource/snapshots/$($qdSnapshot.name)"
    priority='snapshot'
}
if ($qdSnapshot.checksum) { $qdRecovery.checksum=$qdSnapshot.checksum }
Invoke-QdLab PUT "/collections/$qdRestore/snapshots/recover?wait=true" $qdRecovery
Invoke-QdLab POST "/collections/$qdRestore/points/count" @{exact=$true}
Invoke-QdLab POST "/collections/$qdRestore/points" @{ids=@(1,2);with_payload=$true;with_vector=$true}
Invoke-QdLab POST "/collections/$qdRestore/points/query" @{query=@(1,0);limit=2;params=@{exact=$true}}
```

snapshot URL의 `127.0.0.1:6333`은 **복원하는 Qdrant 컨테이너 자신**입니다. host의 16333과 다릅니다. 외부 URL·다른 사람이 준 snapshot은 사용하지 않습니다. timeout이면 성공/실패가 미확정이므로 새 요청을 반복하기 전에 collection과 snapshot recovery 상태를 확인합니다. 예상 count=2, ID/payload/vector와 exact 점수는 원본과 같습니다. alias mapping은 별도로 조회하여 snapshot의 보존 범위를 확인하며 자동 복원됐다고 가정하지 않습니다.

같은 서버에서 clone 복원이 성공해도 host 손실 복구·원격 보관·버전 간 복원·분산 collection 전체 백업을 입증하지 못합니다. source/restore를 모두 보존하고, 삭제는 학습 증거 보존 후 별도 선택합니다. [공식 snapshot](https://qdrant.tech/documentation/operations/snapshots/), [복원 API](https://api.qdrant.tech/api-reference/snapshots/recover-from-snapshot)

## 추가 기능의 다음 실험

- **Quantization·memory tier:** exact 무압축 기준과 동일 corpus/query·filter로 Recall@k, score 오차, 메모리/IO, cold/warm latency를 비교합니다. 설정 수락만으로 속도 개선을 주장하지 않습니다. 1.19의 `memory`와 deprecated `on_disk`를 혼용하지 않고 실제 설정을 기록합니다.
- **HNSW·optimizer:** 실제 index build 완료·indexed vector 수와 planner 조건을 먼저 확인합니다. 작은 데이터에서 full scan이 선택되는 것은 정상일 수 있습니다. 필터 selectivity·ef·후보 수를 한 번에 하나만 바꿉니다.
- **보안:** API key/read-only key·TLS·JWT RBAC는 별도 보안 환경에서 실제 거부 행렬로 검증합니다. 위 무인증 LAB의 tenant 필터로 대신하지 않습니다.

위 추가 항목은 이 파일의 실행 블록에 포함되지 않습니다. [기능 지도](../feature-map.md)·[커리큘럼](../curriculum.md)에서 환경과 완료 상태를 따로 관리합니다. 기능을 채택하지 않더라도 작은 반례나 공식 계약 조사와 선택 근거는 남깁니다.
