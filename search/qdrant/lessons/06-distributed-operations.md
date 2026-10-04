# 06. 복제, 확장, 장애의 경계

[과정](../curriculum.md) · [분산 수동 LAB](../labs/cluster.md) · [운영](../operations.md)

<a id="qd11"></a>
## QD11 — peer, shard, replica, quorum을 각각 센다

분산 모드는 노드 사이에 collection 정보를 조정하고 shard 데이터를 배치하는 환경입니다. metadata consensus와 point update 복제는 같은 경로/보장이 아닙니다. peer 수·shard 수·replication factor·write consistency factor·read consistency를 각각 기록합니다. [공식 distributed deployment](https://qdrant.tech/documentation/scaling/distributed_deployment/)와 [consistency guarantees](https://qdrant.tech/documentation/scaling/consistency-guarantees/)를 근거로 합니다.

[cluster 절차](../labs/cluster.md)의 3프로세스 환경에서 먼저 모두 정상인 기준선을 확보합니다. 같은 host의 프로세스 정지는 AZ/스토리지/전원 장애와 다릅니다. 통신 partition·디스크 손상은 기본 실험에 포함하지 않습니다.

1. 모든 peer의 `/cluster`와 collection cluster 상태에서 leader/term·shard 배치·replica 상태를 읽습니다. 포트가 열렸다는 증거만으로 정상이라 하지 않습니다.
2. replication 설정에 맞게 기대 복제 수를 손으로 적고 실제 배치와 대조합니다. distributed mode를 켠 것만으로 자료가 복제됐다고 가정하지 않습니다.
3. 절차가 지정한 peer 하나만 정지하고 read/write 결과·대기·실패를 기록합니다. 결과를 만들기 위해 다른 peer를 연달아 끄지 않습니다.
4. 재시작 뒤 replica 상태/transfer와 point ID/값/query를 검산합니다. metadata가 안정됐다고 데이터 복구까지 끝났다고 단정하지 않습니다.

`ordering=weak/medium/strong`은 write 순서와 가용성 선택이고 `wait`와 다른 옵션입니다. `read consistency`는 읽을 replica와 결과 합치 규칙의 선택입니다. API의 `majority`와 `quorum` 이름만 보고 같다고 취급하지 말고 [고정 schema](../source-reading.md)의 정의를 비교합니다. 단일 노드에서 이 옵션을 받아들였다는 사실은 장애 보장의 검증이 아닙니다.

제출: metadata/data 두 시간선, 설정별 예상 read/write 결과, 실제 결과와 차이, 재합류 후 ledger. 강한 옵션이 multi-collection transaction이나 모든 외부 writer의 업무 순서를 자동 보장한다고 설명하면 미통과입니다.

<a id="qd12"></a>
## QD12 — 노드 추가는 자동 용량 재배치가 아니다

목적은 hot shard·부하·메모리 부족의 원인에 맞는 확장을 고르는 것입니다. 새 peer가 생겨도 기존 데이터가 저절로 이동했다고 가정하지 않습니다. 수동 replica 이동/복제, custom shard key, 자동 rebalance, resharding은 서로 다른 작업입니다.

| 증상 | 경쟁 가설·관측 | 제한 조치·회복 기준 |
| --- | --- | --- |
| 한 peer만 느림 | shard 배치/tenant skew·cold cache·optimizer·I/O | 전체 replica 수부터 늘리지 말고 원인별 한 조치; ID/recall/latency 재검산 |
| write timeout 증가 | client 동시성·index backlog·replica 지연·consistency | batch/concurrency/retry budget 제한, uncertain write 재조회 |
| 노드 추가 후 변화 없음 | 실제 shard 배치·query fan-out·병목 위치 | 이동 계획과 여유 공간 확인, 완료 상태·실제 분산량 검산 |
| tenant별 간섭 | custom key 분포·큰 tenant·필터/index | 격리 단위/작은 tenant 공유와 큰 tenant 분리 대안 비교 |

custom sharding·shard transfer의 실제 호출은 새 bounded fixture를 준비하는 추가 과제입니다. resharding/자동 rebalancing은 공식 문서의 Cloud 범위와 현재 서비스 조건을 확인해야 하며 **제공 self-host Compose의 보장으로 쓰지 않습니다**. 소스에 resharding 코드가 존재한다는 이유만으로 운영 지원 경로가 같다고 추론하지 않습니다.

client 측 확장은 SDK 버전/timeout/retry 정책, 연결 수, batch 크기, 재시도 횟수·총시간 상한을 명시합니다. 4xx 입력/strict-mode 오류와 일시적 transport 실패를 같은 재시도로 처리하지 않습니다. timeout 이후 새 ID를 부여하면 중복 business 객체가 생길 수 있습니다. 자동 retry를 켜기 전에 QD03 원장을 통과합니다.

기본 runner는 이 규모/장애를 자동 발생시키지 않습니다. 추가 실험은 요청 수·시간·디스크/메모리·동시성 상한과 중단 조건부터 작성합니다. replica 이동 중 검색 품질과 write 정합을 계속 검산하고 미확정 결과를 누락하지 않습니다.

제출: 확장 전후 배치도, workload 분모, 경쟁 가설 3개, 되돌릴 수 있는 조치, 선택하지 않은 확장 방식의 이유. 운영 완료에는 실제 증거가 필요하며 설계만 있으면 `RESEARCH/SEPARATE`입니다.
