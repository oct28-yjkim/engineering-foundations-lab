# Qdrant 정상 관측과 문제 진단

[기본 LAB](labs/README.md) · [고급 기능](labs/advanced.md) · [분산 LAB](labs/cluster.md)

<a id="basic-lab"></a>

## 정상 기준선부터 시작

collection 설정→point/vector/payload→인덱스와 query→원래 ID/점수의 정답을 확보합니다. `upsert` 응답, WAL/적용 상태, 조회 결과, optimizer/index build 완료, replica 상태는 같은 완료점이 아닙니다. 서버 health만 정상이라고 검색 정확성까지 통과시키지 않습니다.

| 단계 | 먼저 할 일 | 증거 |
| --- | --- | --- |
| 정상 기능 | basic runner로 6-point 원장과 exact/filtered query 비교 | version·collection·ID·score·payload·정확 count |
| 원리 | distance/normalization·named vector·filter·query plan·segment 경계 설명 | 손으로 계산한 정답, 요청→관측 경로 |
| 모니터링 | API 응답·collection info·metrics·logs를 같은 시각에 읽기 | 요청 종류·단위·분모·정상 구간·누락 |
| 제약 | tiny data full scan, 무인증 단일 노드, candidate truncation 확인 | index가 있다는 것과 사용됐다는 것 구분 |
| 사건 | 차원 오류·타입 불일치·잘못된 named vector에서 두 개 선택 | 400/0건과 실제 원장 비교, 경쟁 원인 |
| 회복 | 입력/쿼리를 고치고 같은 ID·score·payload 재검산 | 원래 6개와 count·검색 결과 복구 |

## 직접 수집하는 최소 관측

아래 collection은 **본인 runner가 출력한 이름**만 입력합니다. 다른 트랙/회사 endpoint를 사용하지 않습니다. PowerShell 7에서 실행하며 query 없이 상태를 먼저 읽습니다.

```powershell
$qdObserved = Read-Host '이번 실행의 efl_qdrant_<32hex> 이름'
if ($qdObserved -notmatch '^efl_qdrant_[0-9a-f]{32}$') { throw 'runner collection 이름만 허용' }
$qdInfo = Invoke-RestMethod -Uri "http://127.0.0.1:16333/collections/$qdObserved" -NoProxy -TimeoutSec 10
$qdInfo.result | Select-Object status,optimizer_status,points_count,indexed_vectors_count,segments_count,payload_schema
$qdMetrics = (Invoke-WebRequest -Uri 'http://127.0.0.1:16333/metrics' -NoProxy -TimeoutSec 10).Content
$qdMetrics -split "`n" | Select-String '^(# (HELP|TYPE) (rest_responses|memory_|snapshot_)|rest_responses|memory_|snapshot_)'
```

```text
docker compose -f search/qdrant/compose.yaml logs --tail 80 qdrant
docker compose -f search/qdrant/compose.yaml stats --no-stream
```

요청 전/후 같은 관측을 수집합니다. 기본 /metrics의 실제 HELP/TYPE·label을 확인하며 metric prefix와 per-collection 옵션을 바꾸면 시계열 계약도 달라집니다. 제공 runner는 일부 unlabelled instance 지표만 요약합니다. 여기서 전체 모니터링 stack이나 자동 경보가 배포되는 것은 아닙니다. [공식 monitoring](https://qdrant.tech/documentation/ops-monitoring/monitoring/)

| 신호 | 의미와 수집 | 해석의 한계 |
| --- | --- | --- |
| REST 응답 수/실패 | `/metrics`의 `rest_responses_total`, `rest_responses_fail_total`와 실제 label; 동일 요청 종류의 구간 delta | 의도한 400과 운영 오류 구분; process reset 처리; collection info/list/snapshot endpoint 전체가 이 지표에 포함된다고 가정하지 않음 |
| 요청 지연 | client wall time·서버 response time·duration histogram을 분리 | 평균은 p95/p99가 아님; 작은 표본의 percentile로 SLO 판정 금지 |
| collection/index 상태 | `status`, `optimizer_status`, `segments_count`, `indexed_vectors_count`, 설정과 payload_schema | point/vector/index count가 서로 다름; exact count API로 업무 cardinality 확인 |
| 메모리·IO | `/metrics`의 실제 memory 계열·host/container stats·query의 지원되는 usage 필드 | RSS·allocator·page cache·cgroup 한도는 다른 값, usage를 곧 청구 비용으로 해석하지 않음 |
| snapshot | 생성/복원 running gauge와 created counter, 파일 size/checksum, 독립 복원 결과 | 파일 생성 성공은 RPO/RTO·재해 복구 성공이 아님 |
| 분산 | 각 peer `/cluster`, collection `/cluster`: shard copy·state·transfer·leader·pending | Raft metadata 상태와 point consistency는 다름; 단일 노드 `/cluster`에 의존하지 않음 |
| 검색 품질 | 고정 query/judgment·exact oracle의 Recall@k/nDCG·필터 누출·freshness | 처리량 개선과 의미 품질 개선은 별도; tenant filter는 인증이 아님 |

## 흔한 문제와 복구 판단

| 증상 | 먼저 구분할 원인 | 제한된 조치와 회복 oracle |
| --- | --- | --- |
| 400 dimension/name 오류 | collection vector schema·using·embedding revision·빈/잘못된 벡터 | 계약에 맞는 입력/이름으로 재전송; reject된 ID 부재/반영 여부와 원래 count 확인 |
| filter 이후 0건·tenant 누출 | payload 타입·배열/nested·필드 경로·누락 filter·인덱스와 논리 혼동 | 원본 payload와 query predicate 비교; 작은 기대 ID 집합으로 정답 확인 |
| exact는 맞는데 ANN 후보 누락 | query 조건 일치·index build·ef·candidate limit·quantization/rescore | 동일 입력에서 하나만 변경; Recall@k와 latency/메모리를 함께 비교 |
| 검색/업로드가 느림 | optimizer backlog·segments·payload index 부재·cold IO·큰 payload·concurrency | 정상 소량 기준선으로 축소 후 병목 확인; memory/ef/동시성 무작정 확대 금지 |
| strict mode/429/timeout | 실제 status/diagnostic·collection limit·client budget·replica 조건 | 잘못된 요청은 수정, 일시 오류는 상한 있는 정책 설계; timeout은 unknown으로 남기고 ID/업무 version 확인 |
| alias 전환 뒤 결과가 다름 | alias 대상·writer target·dimension/model/filter·배포 revision | 이전 collection을 보존한 상태로 alias 원복, reader/writer 각각 결과 검산 |
| 한 노드 이탈 후 쓰기 오류 | metadata quorum·replica Active 수·write consistency·ordering·read 조건 | 노드 복귀가 우선; 학습용 조건 변경의 부작용 기록, 모든 copy와 원래 값을 재검산 |
| snapshot은 있는데 복원 실패 | 버전/파일 무결성·접근 경로·용량·priority·대상 collection·분산 snapshot 범위 | 새 격리 대상에서 복구; 원본 덮어쓰기 금지, 설정/ID/payload/vector/검색 결과 독립 비교 |

문제 빈도 순위의 통계를 제공하는 것은 아닙니다. 실무에서 대비할 대표 유형을 선정한 카드입니다. 인덱스 삭제·force peer 제거·대량 reindex·quota 해제·전체 cache/volume 삭제를 첫 조치로 사용하지 않습니다.

## 확장 판단과 종료

벡터 수만 아니라 dimension, named/multivector 수, payload·index, replica 수, query selectivity·candidate 크기, working set·IO·build 비용을 기록합니다. RAM 예산과 실제 metric을 비교하고 quantization·memory tier·shard 이동의 비용/정확성/운영 복잡성을 함께 평가합니다. 작은 fixture의 6건 성공을 서비스 capacity로 외삽하지 않습니다.

[기능 지도](feature-map.md)의 로컬 기능 LAB과 별도 부하/보안/분산 과제를 나눕니다. 해당 실행의 정상→사건→회복 ID·시간·상태·제약을 [보고서](../../operations/incident-report-template.md)에 남기고 [검증 기록](labs/validation.md)의 작성 시 상태와 혼동하지 않습니다.
