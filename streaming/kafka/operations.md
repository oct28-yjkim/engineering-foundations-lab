# Kafka 운영 실습: lag를 발견한 뒤 무엇을 확인하는가

[트랙](README.md) · [공통 운영 계약](../../operations/README.md) · [장애 보고서](../../operations/incident-report-template.md)

기준은 저장소의 Kafka 4.3.1입니다. 기본 경로는 **실제 정상 상태 → 제한된 증상 재현 → 가설 비교 → 완화·원복 → 업무 복구 확인 → 내부 구현 추적**입니다. 알고리즘 모형은 보충 자료이며 실제 운영 관문을 대체하지 않습니다. 이 문서는 실행할 runbook이고 이번 문서 개편에서 장애를 실행한 결과는 아닙니다.

## 1. 사전 조건과 정상 baseline

[로컬 환경](labs/local-lab.md)의 소유한 단일 노드만 사용합니다. 먼저 Docker context·Compose project·cluster ID·topic/group 소유자·Kafka/client 버전·관측 시간을 기록합니다. 제공 단일 broker의 RF=1은 ISR 장애나 HA 실습 환경이 아닙니다. 운영 접속 정보·인증 파일·원문 payload를 수집하지 않습니다.

아래는 **이미 실행 중인 학습 환경의 읽기 전용 조회**입니다. 명령은 저장소 루트 기준입니다. 전체 목록에서 자신의 topic/group을 확인한 후 `--topic` / `--group`으로 범위를 좁힙니다. 존재하지 않는 group의 lag는 0으로 해석하지 않습니다.

```text
docker compose -f streaming/kafka/compose.yaml ps
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:19092 --describe
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --list
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-metadata-quorum.sh --bootstrap-server kafka:19092 describe --status
```

소유한 group 이름을 실제 값으로 바꿉니다. 조회는 offset reset이 아닙니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --describe --group lab-owned-group
```

동일 합성 workload에서 15초 간격으로 5분간 baseline을 잡고 workload·partition·key 분포를 고정합니다. 이는 교육용 관측 창이지 운영 경보 임계값이 아닙니다. 지표 수집 실패, 재시작, consumer 부재는 별도 이벤트로 표시합니다. JMX 수집기는 제공 Compose에 설치되어 있지 않습니다. JMX가 필요한 과제는 인증·접근 제한된 별도 수집 경로를 준비하고, 외부에 무인증 JMX/RMI 포트를 열지 않습니다.

## 2. 지표 사전과 해석

| 신호·수집 위치 | 타입·단위·관측 창 | 함께 확인할 것 |
| --- | --- | --- |
| group CLI의 CURRENT-OFFSET/LOG-END-OFFSET/LAG | partition별 시점 snapshot; lag는 offset 차이 | 누적 counter도 정확한 업무 미처리 건수도 아님. compaction·transaction·commit 시차·업무 원장 확인 |
| consumer JMX `records-lag-max` | consumer client의 현재 최대 fetch lag, records | committed group lag와 다른 관측점. client-id·partition·수집 창 기록 |
| `kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions` | broker별 gauge, partitions | ISR이 할당 replica보다 작은 partition 수. rollout과 지속 장애 구분 |
| 같은 type의 `UnderMinIsrPartitionCount` | gauge, partitions | 실제 min.insync.replicas·acks·ELR feature 설정과 produce 오류 대조 |
| `kafka.controller:type=KafkaController,name=OfflinePartitionsCount` | controller gauge, partitions | active controller 역할과 leader 없는 partition 식별; scrape 부재를 0 처리하지 않음 |
| `kafka.network:type=RequestMetrics,name=TotalTimeMs,request=Produce` 및 RequestQueueTimeMs/LocalTimeMs/RemoteTimeMs | timer/histogram, ms | queue·leader 처리·복제 대기 분해. exporter가 노출하는 percentile 창을 확인하고 p99끼리 합산하지 않음 |
| JMX `RequestsPerSec`·`ErrorsPerSec` | meter의 Count는 누적, rate 속성은 requests/s 또는 errors/s | exporter가 raw counter를 내보내면 reset-aware rate를 적용. 이미 rate인 속성에 rate를 재적용하지 않음 |

위 JMX 이름은 [Kafka 4.3 Monitoring](https://kafka.apache.org/43/operations/monitoring/) 기준입니다. Prometheus metric 이름은 exporter 설정에 따라 달라지므로 고정 이름을 추측하지 않습니다. lag가 작아도 처리 전에 offset을 commit했다면 업무 손실이 숨을 수 있습니다.

## 3. 네 가지 장애 진단 카드

각 카드의 재현은 사용자가 소유한 **합성 전용 topic/group**, 최대 1,000개·1 KiB 메시지, 최대 5분, 기존 설정 백업과 중단 담당자가 있는 경우에만 수동 선택합니다. 실제 cluster가 없으면 topology 장애는 설계/자료 분석으로 남깁니다. disk 채우기, 운영 offset reset, replica 강제 제거, unclean election 활성화는 하지 않습니다.

| 증상·안전한 재현 | 경쟁 가설과 검증 순서 | 완화·원복 | 복구 증거 |
| --- | --- | --- | --- |
| group lag 증가: 학습 consumer 처리에만 제한된 지연 삽입 | 입력 증가 / hot partition / downstream 지연 / rebalance. partition별 lag, 처리·commit 시각, assignment, handler p95와 broker produce latency를 같은 창에서 대조 | 지연 제거, 원래 concurrency로 원복. partition 수보다 무조건 consumer 증설하지 않음 | lag 감소뿐 아니라 입력 ID→업무 결과 누락/중복 검산, 처리 tail이 baseline 범위로 회복 |
| URP·UnderMinISR 증가: 별도 RF=3 격리 환경에서 follower 하나만 중단 | follower disk/network / ISR catch-up / 계획된 이동. leader·ISR·replica별 로그와 produce 오류·RemoteTimeMs 대조 | 중단한 동일 follower 복귀. min ISR 낮춰 성공처럼 만들지 않음 | ISR 회복, 승인된 event ID 보존, produce 오류·latency 정상화. RF=1이면 미실행 |
| offline partition 또는 metadata 명령 timeout: 승인된 다중 노드 fixture만 | data leader 부재 / controller quorum 부재 / client endpoint 오류. metadata quorum과 topic leader를 별도 확인 | 마지막 변경 취소, 원래 voter/노드 복구. metadata 디렉터리 재포맷 금지 | leader와 quorum뿐 아니라 produce/consume 및 ID 원장 검산. healthcheck만으로 종료하지 않음 |
| produce p99 증가: 동일 총량에서 학습 producer concurrency만 제한적으로 증가 | broker queue / replica wait / quota / client batch 대기. 요청 분해·producer callback·throttle·disk/GC 대조 | 부하를 baseline으로 낮추고 batch/concurrency 설정 원복; 원인 확인 후 한 설정씩 재평가 | 오류 포함 전체 요청 분모, 성공/실패/불확실 요청 원장, p95/p99·처리량·queue 회복 |

이 표는 진단을 위한 실험 설계입니다. 실제 실행값을 예상값으로 채우지 않습니다. [consumer 운영 명령](https://kafka.apache.org/43/operations/basic-kafka-operations/), [KRaft 운영](https://kafka.apache.org/43/operations/kraft/)을 설치 버전과 대조합니다.

## 4. 모듈별 운영 증거

| 모듈 | 원리·소스와 함께 제출할 관측 산출물 |
| --- | --- |
| K01 | event ID·partition·offset·업무 처리시각의 정상 원장 |
| K02 | log 크기·segment·retention 설정과 시간별 보존 집합 |
| K03 | callback latency·오류·retry·queue/batch 조건 비교 |
| K04 | leader/ISR/min ISR 타임라인과 ACK·오류 대조 |
| K05 | committed offset·처리 위치·업무 commit 분리 |
| K06 | assignment/rebalance 로그와 partition lag 변화 |
| K07 | 앱 재시도와 업무 중복 원장, consumer 오류 분모 |
| K08 | transaction 상태·read_committed 가시성·LSO 경계 |
| K09 | controller quorum·epoch·data leader 별도 지도 |
| K10 | 위 장애 카드 2개·runbook·원복·복구 증거 |
| K11 | Streams task/state restore 진행과 출력 fingerprint |
| K12 | connector/task 상태·source 위치·sink freshness |
| K13 | 관측한 병목/오류를 고정 source의 분기·회귀 시험에 연결 |
| K14 | 동일 baseline·두 사건·개선 전후·업무 복구 요약 |

기본 운영 gate는 실제 정상 baseline 1개, 서로 다른 증상 2개, 경쟁 가설 배제, 변경/원복 기록, 업무 결과와 지표의 회복 증거입니다. HA 등 별도 환경이 필요한 관문은 추가로 유지됩니다. 환경이 없으면 정제된 실측 자료로 분석 gate만 통과하며 실행 gate는 미완료입니다.
