# OpenSearch 기본 실습: 정상 동작을 이해하고 흔한 문제를 해결하기

[실습 입구](README.md) · [관측 실습](observation.md) · [확장 문제 실습](scaling-incidents.md) · [운영 runbook](../operations.md)

이 실습의 목표는 장애를 많이 만드는 것이 아니라 **정상 기능 확인 → 동작 원리 이해 → 정상 상태 관측 → 제약 확인 → 증상 진단 → 조치·복구 검증**을 한 번 경험하는 것입니다. 작은 합성 데이터로 실제 OpenSearch REST API를 사용합니다. Python에서 엔진 동작을 흉내 내는 CPU 모형이나 처리량 벤치마크가 아닙니다.

작성 시점에 아래 신규 시나리오를 실제 서버에서 실행하지 않았습니다. HTTP double 테스트는 요청 범위·단계 순서·검산 로직만 검증하며, 실서비스 동작의 실행 증거가 아닙니다. 사용자가 실행한 JSON 출력과 환경 정보를 별도 기록해야 합니다.

## 1. 정상 기능과 관측부터 시작

먼저 [로컬 환경 준비](README.md#1-실제-로컬-opensearch-390-준비)를 따라 제품별 Compose를 준비합니다. 아래 명령은 저장소 루트 기준이며, 컨테이너 시작이나 환경 변경을 runner가 대신하지 않습니다.

```text
python -B search/opensearch/labs/engine_lab.py --help
python -B search/opensearch/labs/engine_lab.py --run-local
```

기존 runner는 새 index에 6개 문서를 넣고 filter·text/keyword 검색·phrase·range·정렬·집계·OCC·bulk item 오류를 검산합니다. 그중 정상 검색 기대값을 먼저 확인한 후, 내구성과 검색 가시성, 요청 성공과 모든 item 성공이 왜 다른지도 읽습니다. 이 작은 fixture의 PASS는 운영 준비나 HA 보장이 아닙니다.

1. `_source`, `_id`, mapping과 실제 검색 결과를 나란히 확인합니다. text analyzer와 keyword exact match를 구분합니다.
2. [관측 실습](observation.md)으로 어떤 API에서 어떤 값을 수집하는지 익힙니다. 지표의 범위가 index인지 node인지, counter인지 현재 상태인지 기록합니다.
3. 한 번의 수치에 임계값을 붙이지 않고 같은 workload·환경에서 기준선을 만듭니다. 샘플 간격·요청 수·오류 분모를 남깁니다.
4. 그 뒤 아래 사건 하나를 골라 기능적으로 정상인 상태와 무엇이 달라졌는지 비교합니다.

## 2. 단계형 runner 사용법

[incident_lab.py](incident_lab.py)는 Python 3.10+ 표준 라이브러리로 실행합니다. 시나리오 목록과 도움말에는 네트워크 접근이 없습니다.

```text
python -B search/opensearch/labs/incident_lab.py --list
python -B search/opensearch/labs/incident_lab.py --help
```

각 사건은 **새 index 하나**를 사용합니다. `prepare`는 정상 fixture를 준비하고 지정한 증상을 재현한 뒤 멈춥니다. `observe`는 진단 증거를 읽고, `recover`에서만 조치하며, `verify`가 정확한 결과와 복구 조건을 검사합니다. 단계를 나누었으므로 자동 복구 전에 증거를 읽고 원인을 설명할 수 있습니다.

PowerShell 예시입니다. `refresh`를 다른 시나리오명으로 바꾸어 사용합니다. `$incidentRunId`에는 해당 `prepare`가 반환한 값만 넣습니다.

```powershell
$incidentScenario = 'refresh'
$incidentPrepared = python -B search/opensearch/labs/incident_lab.py --run-local --scenario $incidentScenario --step prepare
if ($LASTEXITCODE -ne 0) { throw 'prepare 실패: 출력과 index 상태를 먼저 확인하세요.' }
$incidentPrepared
$incidentResult = $incidentPrepared | ConvertFrom-Json
if ($incidentResult.status -ne 'PREPARED') { throw '증상 재현이 확인되지 않았습니다.' }
$incidentRunId = $incidentResult.run_id

python -B search/opensearch/labs/incident_lab.py --run-local --scenario $incidentScenario --step observe --run-id $incidentRunId
# OBSERVED 증거로 원인과 조치를 설명한 뒤, 다음 명령을 별도로 실행합니다.
python -B search/opensearch/labs/incident_lab.py --run-local --scenario $incidentScenario --step recover --run-id $incidentRunId
# RECOVERED는 조치 실행 결과입니다. 아래 검산까지 해야 복구를 확인합니다.
python -B search/opensearch/labs/incident_lab.py --run-local --scenario $incidentScenario --step verify --run-id $incidentRunId
```

각 명령 종료 코드와 `status`를 확인하고 **오류 뒤에 다음 단계들을 일괄 실행하지 않습니다.** 다른 셸에서는 `prepare` JSON의 32자리 소문자 16진수 `run_id`를 직접 복사합니다. `prepare`에 `--run-id`를 넣을 수 없고, 나머지 단계에는 반드시 필요합니다. runner는 결과 파일을 자동 생성하지 않습니다. JSON stdout을 실습 원장에 보존하면 됩니다.

| 단계 | 성공 상태 | 의미와 한계 |
| --- | --- | --- |
| `prepare` | `PREPARED` | 해당 기대 증상이 실제 응답에서 확인됨; 아직 복구 안 됨 |
| `observe` | `OBSERVED` | 복구 전 증상의 설정·문서·지표 또는 오류를 읽음; 쓰기·refresh하지 않음 |
| `recover` | `RECOVERED` | 해당 fixture의 설정·실패 문서 또는 질의 방식을 조치함; 최종 검산은 별도 |
| `verify` | `VERIFIED` | 정확한 문서 ID/값과 사건별 회복 조건이 맞음 |
| 어느 단계든 실패 | `ERROR`, 종료 코드 1 | 예상과 다른 상태. stage·run_id·index를 보존하고 진단하며 자동 삭제·재시도하지 않음 |

`observe`는 복구 **전** 조건을 검사합니다. 복구 후 다시 실행하면 증상이 없어져 오류가 날 수 있으며, 회복 결과는 `verify`로 확인합니다. `refresh`/`allocation`의 조치는 반복해도 같은 설정이지만, `bulk-errors`/`write-block` 복구를 다시 실행하면 이미 존재하는 문서 때문에 명확히 실패할 수 있습니다. 중간 실패 후 무작정 `prepare`를 반복하면 별도 index가 계속 남습니다.

## 3. 다섯 가지 기본 사건

| 시나리오 | 정상 기능 | 만나는 문제 | 첫 진단 질문 |
| --- | --- | --- | --- |
| `refresh` | 색인한 문서를 GET·검색으로 찾음 | GET은 되지만 검색은 0건 | 쓰기 실패인가, 검색 가시성 지연인가? |
| `bulk-errors` | 배치 요청의 각 문서가 색인됨 | HTTP 200인데 일부 문서 누락 | 요청 상태만 봤나, item별 결과를 봤나? |
| `write-block` | 기존 검색과 새 쓰기가 모두 됨 | 읽기는 되지만 쓰기는 차단됨 | 압력 rejection인가, index block인가? |
| `allocation` | primary가 정상이고 replica 요구도 충족됨 | primary는 살아 있지만 yellow | replica를 둘 자격 있는 다른 노드가 있는가? |
| `pagination` | 작은 페이지 검색이 됨 | 뒤쪽 페이지의 `from+size`가 실패 | 결과가 없는가, 질의 방식의 한계인가? |

### 3.1 `refresh`: 쓰기 성공과 검색 가시성을 구분

- **원리:** realtime GET과 검색 reader의 가시성 경계는 다릅니다. 이 사건은 `refresh_interval=-1`과 `refresh=false`로 자동/즉시 refresh를 끄고 `a1(value=1)`, `a2(value=2)`를 생성합니다. GET 두 건은 존재하고 검색은 0건이어야 합니다.
- **관측:** `index.refresh_interval`, realtime GET, `_search`의 정확한 total, index의 `refresh.total`·`refresh.total_time_in_millis`를 함께 봅니다. 검색 조건 오류·잘못된 index·쓰기 실패도 경쟁 가설이지만, 고정 fixture와 정확한 GET 값으로 범위를 좁힙니다.
- **조치:** 소유 index에만 명시적 refresh를 한 번 수행합니다. `recover`는 자동 refresh 설정을 켜지 않고 **`-1`을 유지**합니다.
- **복구 검산:** 정렬된 검색과 GET에 `a1=1`, `a2=2`가 정확히 있고 검색 total=2여야 합니다. reader 가시성 회복이지 translog fsync·노드 손실·디스크 내구성 검증은 아닙니다.
- **제약:** 운영에서 매 쓰기마다 강제 refresh하는 처방을 일반화하지 않습니다. 검색 신선도 요구, 비용과 정상 refresh 정책을 따로 설계해야 합니다. [Refresh API](https://docs.opensearch.org/latest/api-reference/index-apis/refresh/)

### 3.2 `bulk-errors`: 부분 실패만 분류하고 재처리

- **원리:** bulk item은 독립적으로 처리됩니다. `prepare`는 정상 `a1`, integer 필드에 문자열을 넣은 `a2`, 중복 `a1 create`를 한 배치로 보냅니다.
- **관측:** 전체 HTTP 200과 `errors=true`, item 상태 `[201, 400, 409]`를 같이 확인합니다. 각각 `mapper_parsing_exception`, `version_conflict_engine_exception`이어야 합니다. `observe`는 `a1`만 존재하는 상태와 stats를 읽으며, **bulk를 다시 보내지 않습니다**. 오류 분류 증거는 `prepare` JSON에 남습니다.
- **조치:** 잘못된 `a2`의 값을 정수 2로 고쳐 **실패한 a2만** 생성하고 refresh합니다. 성공한 `a1`을 재전송하거나 매핑 오류를 무한 재시도하지 않습니다. 중복 create의 409는 이미 존재하는 문서를 확인한 뒤 별도로 처리합니다.
- **복구 검산:** 정확히 `a1=1`, `a2=2`, total=2. 성공한 문서가 바뀌거나 중복 결과가 생기면 실패입니다.
- **제약:** 이 랩의 409는 중복 create입니다. 정상 워밍업의 stale OCC 409와 원인을 구분합니다. 실제 파이프라인의 backoff·DLQ·멱등성 키·대량 재처리는 별도 설계이며, `index_failed` 하나가 모든 클라이언트 item 실패를 완전히 대변한다고 가정하지 않습니다. [Bulk API](https://docs.opensearch.org/latest/api-reference/document-apis/bulk/)

### 3.3 `write-block`: 읽기는 되는데 쓰기만 막힐 때

- **원리:** 정상 `a1`을 색인·refresh한 뒤, 자체 index의 `index.blocks.read_only_allow_delete=true`를 설정합니다. `a2 create`가 HTTP 403 또는 429의 `cluster_block_exception`으로 실패해야 합니다.
- **관측:** 기존 `a1`은 검색되고 `a2`는 없습니다. `observe`는 block 설정·검색·GET·stats만 읽습니다. HTTP 429라는 숫자만으로 thread-pool 포화라고 결론 내리지 않고 오류 type과 설정을 함께 봅니다.
- **조치:** 해당 fixture의 block만 false로 되돌리고 `a2=2` 쓰기를 재시도한 후 refresh합니다.
- **복구 검산:** block=false, 검색과 GET에 정확히 두 문서가 존재해야 합니다.
- **제약:** **수동으로 block 상태를 만든 것이며 실제 disk-full/flood-stage 재현이 아닙니다.** 디스크를 채우거나 watermark를 낮추지 않습니다. 운영 disk pressure는 공간·증가율·shard 배치와 원인을 먼저 해결해야 하며, 원인을 그대로 둔 block 해제만으로 복구했다고 할 수 없습니다. [Index settings](https://docs.opensearch.org/latest/install-and-configure/configuring-opensearch/index-settings/)

### 3.4 `allocation`: 단일 노드에서 replica 요구가 충족되지 않을 때

- **원리:** primary 1개·replica 0개의 정상 fixture를 만든 뒤 replica를 1개 요구합니다. 단일 노드에는 같은 shard의 primary와 replica를 함께 둘 수 없습니다.
- **관측:** **해당 index만** 지정한 health에서 yellow·active primary=1·unassigned=1, allocation explain에서 `same_shard=NO`를 확인합니다. explain은 index·shard 0·primary=false를 명시하며 임의의 다른 unassigned shard를 가져오지 않습니다.
- **조치:** 이 랩에서는 처음의 단일 노드 선택인 replica=0으로 복귀합니다.
- **복구 검산:** 해당 index green·unassigned=0, 정확한 `a1=1`, `a2=2`가 유지되어야 합니다. stats에서 할당되지 않은 replica 때문에 successful shard 수가 total보다 작을 수 있어 실패 shard와 구별합니다.
- **제약:** **replica=0은 운영 HA 해법이 아닙니다.** green만 만들고 복제본을 없애면 장애 허용성은 회복되지 않습니다. 실제 운영에서는 노드/장애 도메인·disk·filter·awareness·복구 제약을 검토해야 합니다. 다른 노드가 추가되어 이 조건이 사라지면 랩은 예상 증상 재현에 실패합니다. [Allocation Explain API](https://docs.opensearch.org/latest/api-reference/cluster-api/cluster-allocation/)

### 3.5 `pagination`: 결과 창을 키우지 않고 질의 방식을 바꾸기

- **원리:** `p00`~`p19` 20건을 만들고 fixture의 `max_result_window=5`로 제한합니다. `from=5,size=5`는 창을 초과하므로 HTTP 400·`search_phase_execution_exception`과 root cause `illegal_argument_exception`이어야 합니다.
- **관측:** 설정과 실패 질의를 함께 확인합니다. 데이터 손실이나 인덱싱 실패로 오인하지 않습니다. 작은 제한은 오류를 적은 데이터로 재현하려는 것이며 OpenSearch의 기본값이라는 뜻이 아닙니다.
- **조치:** 유일한 keyword `doc_id` 오름차순으로 5개씩 읽고, 응답의 sort 값을 다음 `search_after`로 전달합니다. `recover`는 설정을 바꾸지 않고 이 올바른 읽기 패턴을 수행합니다.
- **복구 검산:** 4페이지에서 20개 ID와 값이 정확히 한 번씩 나오고, 마지막 후속 페이지는 비어야 합니다. `verify`는 작은 window가 그대로이고 이전 deep-offset 질의는 여전히 거부되며 search_after 경로만 성공하는지 검사합니다.
- **제약:** fixture는 **불변 데이터**이며 PIT를 만들지 않습니다. 유일한 정렬 키가 있어도 동시 갱신 중의 snapshot 일관성을 보장하지 않습니다. `recover`가 영구 상태를 바꾸지 않아 `verify` 자체로 올바른 패턴을 검산할 수도 있지만, 학습 순서는 실패 질의·관측·대안 비교를 모두 거칩니다. [Pagination 안내](https://docs.opensearch.org/latest/search-plugins/searching-data/paginate/)

## 4. 지표를 읽을 때의 공통 규칙

`observe`는 해당 index의 `docs,indexing,search,refresh,store` stats에서 primaries 값만 요약합니다. replica를 중복 집계하지 않으며, 실제 응답에 없는 필드는 만들어 채우지 않습니다. 이 runner에는 지속 수집·대시보드·부하 생성기가 없습니다. [관측 실습](observation.md)은 query 표본과 전후 stats를 비교하며, 연속 시계열은 [운영 runbook](../operations.md)의 별도 수집이 필요합니다.

| 출력 항목 | 해석 | 금지할 해석 |
| --- | --- | --- |
| `docs.count`, `docs.deleted` | 시점의 Lucene 문서 상태; 이 flat fixture의 검색 결과와 함께 비교 | 모든 사용자 질의의 결과 건수와 동일하다고 가정 |
| `store.size_in_bytes` | 자체 index의 primary store 크기, bytes | 호스트 전체 남은 디스크나 확장 용량으로 대체 |
| `index_total`, `index_failed`, `query_total`, `refresh.total` | 수집 범위 내 누적 작업 수; reset/범위 확인 후 차이 사용 | 값 하나를 초당 처리량으로 표기 |
| `*_time_in_millis` | 누적 소요 시간, ms | end-to-end p95/p99 또는 한 요청 지연으로 표기 |
| `shards.total/successful/failed` | stats 응답의 수집 범위와 실패 여부 | yellow의 미할당 replica를 API 실패로 단정 |
| health·설정·error type | 현재 상태와 오류 분류 증거 | 상태 하나만으로 원인 확정 또는 무조건 재시작 |

관측 요청 자체도 작업을 만들므로 query counter가 증가할 수 있습니다. 누적 값의 차이로 비율을 계산할 때 실제 경과시간과 분모를 기록하고, 노드 재시작/인덱스 재생성/범위 변경을 확인합니다. 관련 계약은 [Index Stats API](https://docs.opensearch.org/latest/api-reference/index-apis/stats/)와 [공통 운영 지침](../../../operations/README.md)을 따릅니다.

## 5. 실행 범위와 안전장치

| 항목 | 실제 구현 |
| --- | --- |
| 연결 | `http://127.0.0.1:19200` 고정; URL/index override 없음; 환경 proxy·redirect 미사용 |
| 대상 식별 | distribution=`opensearch`, version=`3.9.0`, cluster=`engineering-foundations-opensearch-lab`, node=`opensearch-lab` 확인 |
| 쓰기 범위 | `efl-os-incident-<scenario>-<32hex>` 신규 index; 1 primary, 기본 replica 0, 합성 문서 최대 20개 |
| 소유권 | 후속 단계 시작과 **기존 index에 대한 매 mutation 직전** `_mapping._meta`의 lab marker·scenario·run_id 확인 |
| 경로·body | 고정 REST 경로와 fixture body만 허용; global settings·arbitrary scripts·foreign bulk `_index` 없음 |
| 한 명령의 예산 | HTTP 최대 96회, 응답 최대 1MiB, 요청 payload 최대 32KiB, socket 작업당 5초 |
| 서버 측 제한 | 가능한 요청의 timeout 3초; search timeout 3초. 전체 wall-clock deadline 보장은 아님 |
| 보존 | 자동 index 삭제·파일 저장·cleanup 없음; 오류 출력에도 run_id/index 유지 |
| 수행하지 않는 것 | 서비스 시작, host 설정 변경, 실제 disk filling, 운영 계정/비밀 입력, cloud API, 부하/HA 실험 |

식별자와 `_meta`는 **실수 방지 장치이지 인증·인가 경계가 아닙니다.** 같은 호스트의 악의적인 서버나 동시에 설정을 바꾸는 관리자를 막지 못합니다. 운영 서버나 실제 데이터를 붙이지 않고, 여러 사람이 같은 fixture를 동시에 조작하지 않습니다. 반복 실행하면 보존 index가 누적되므로 원장에 index·run_id·시작/종료 상태를 기록하고 별도 정리 결정을 합니다.

## 6. 완료 조건과 다음 단계

각 사건에서 다음을 한 문단씩 남깁니다.

1. 정상 상태의 기능·정확한 기대 결과와 동작 원리.
2. 증상, 경쟁 가설 2개, 가설을 구분한 API/지표/오류 증거.
3. 조치가 바꾼 범위와 바꾸지 않은 범위, 실제 복구 검산 JSON.
4. 이 작은 환경으로 검증하지 못한 운영·확장 조건과 다음 확인 항목.

기본 5개를 익힌 뒤 [확장 문제 실습](scaling-incidents.md)에서 shard 배치·노드 복귀·routing 편중을 다룹니다. 작은 fixture로 자원 포화/처리량 개선을 재현했다고 하지 않습니다. 증상을 보는 순서와 가설을 검증하는 방식을 익힌 뒤 추가 예산을 정해 데이터량·복제·부하를 확장합니다. 작은 fixture의 실패/회복을 겪어 보았다는 것과 운영 규모를 감당한다는 것은 별도의 학습 성과입니다.
