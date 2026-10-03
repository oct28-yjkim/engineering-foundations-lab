# K09–K10. KRaft 제어 상태와 운영 복구

[커리큘럼](../curriculum.md) · 이전: [트랜잭션](04-transactions.md) · 다음: [Streams와 Connect](06-streams-connect.md)

## K09 KRaft는 어떤 상태에 합의하는가 LOCAL CLUSTER-DESIGN

**선수 조건:** K04, Raft log/term·다수결·fencing·snapshot.

### 동작 원리

KRaft controller quorum은 topic·partition 배치·broker 등록·설정 등 **클러스터 metadata**의 상태 전이를 관리합니다. 일반 data partition의 record를 모두 controller metadata log에 저장하는 구조가 아닙니다. broker가 data partition을 복제하는 ISR/ELR 경로와 controller의 Raft 합의를 분리해야 장애를 올바르게 해석할 수 있습니다. [KRaft 운영](https://kafka.apache.org/43/operations/kraft/)

leader라는 단어도 역할을 붙여 사용합니다. controller quorum의 leader, data partition의 leader, group coordinator, transaction coordinator는 책임과 상태 저장 위치가 다릅니다. coordinator가 있다고 해서 그것이 controller라는 뜻은 아닙니다. group/transaction 상태의 내부 topic도 replication과 capacity 계획에서 빠뜨리지 않습니다.

| 역할 | 다루는 상태 | 질문 |
| --- | --- | --- |
| controller quorum | 클러스터 metadata log·snapshot·broker fencing | 어떤 변경이 합의되었고 누가 적용했는가? |
| data partition leader | 사용자 record와 follower 진행 | 어떤 offset까지 복제·가시화되었는가? |
| group coordinator | membership·assignment·committed offsets | 누가 어느 partition을 소유하고 어디서 재시작하는가? |
| transaction coordinator | transaction lifecycle·producer epoch·marker 진행 | 어느 transaction이 완료·중단·fenced되었는가? |

combined broker/controller는 학습 환경을 간단하게 하지만 같은 프로세스와 자원을 공유합니다. controller 전용 프로세스를 가진 다중 failure-domain 운영 구성과 장애 범위가 다릅니다. metadata snapshot은 user record 백업이 아니고, 사용자 로그만 있어도 모든 metadata/권한/ID가 자동 복구되는 것도 아닙니다.

### LOCAL 관찰

제공 [`00-inspect.sh`](../labs/scripts/00-inspect.sh)의 storage identity·설정·metadata quorum 출력을 읽습니다. 아래 명령은 읽기 전용 관찰입니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-metadata-quorum.sh --bootstrap-server kafka:19092 describe --status
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-metadata-quorum.sh --bootstrap-server kafka:19092 describe --replication
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-features.sh --bootstrap-server kafka:19092 describe
```

cluster ID, node ID, voters/observers, leader/epoch, metadata 진행 위치를 기록합니다. 표시되는 high watermark가 **metadata log의 것인지 data partition의 것인지** 반드시 이름에 붙입니다. K01 topic을 생성하기 전후의 metadata 진행과 topic describe를 비교합니다. offset 증가량이 사용자 event 개수와 일치하리라고 예상하지 않습니다.

실습 Compose는 static voter 방식으로 준비된 단일 quorum입니다. 동적 quorum 관련 최신 문서를 보고 `controller.quorum.voters`나 bootstrap 설정만 바꾸면 기존 storage가 자동 migration된다고 가정하지 않습니다. feature level, format 당시의 storage 상태, 추가/제거 절차는 해당 4.3 문서와 일치시킵니다. storage format은 기존 장애 해결용 만능 reset 명령이 아닙니다.

### CLUSTER-DESIGN 실험

controller 3개·broker 3개를 별도 프로세스로 추가 구축합니다. node ID, cluster ID, listener, metadata/data volume, 자원 제한, graceful/abrupt stop 방법을 명시합니다. 먼저 leader 하나 중단과 follower 하나 중단을 각각 수행한 뒤, 별도 run에서 controller 두 개를 중단합니다.

가설은 “quorum을 잃으면 모든 기존 fetch가 즉시 똑같이 실패한다”입니다. metadata를 변경하는 요청, 기존 leader에 produce/fetch하는 요청, 새 leader 선출이 필요한 요청을 따로 관찰해 이 단순화가 맞는지 검증합니다. 결과는 broker 상태·fencing·시간 경과에 의존하므로 특정 동작을 모든 조건에 일반화하지 않습니다. majority를 복원한 뒤 metadata와 data의 복구 상태를 각각 점검합니다.

**기대 증거:** 1개/2개 controller 장애의 request별 결과, quorum 상태와 epoch, broker registration/fencing, ACK 원장과 원복 상태. 3 voters 중 1개 장애와 2개 장애의 차이를 Raft 진행 조건과 연결합니다.

**실패 모드:** data RF3이면 controller도 3개라고 생각, 서로 다른 cluster ID로 노드 초기화, volume만 남기고 metadata identity 재생성, 새 topic의 같은 이름을 과거와 같은 identity로 취급, metadata quorum 도구 결과를 data lag로 보고.

**소스 방향·통과:** `KafkaRaftClient`, `QuorumController`, metadata loader/publisher, broker lifecycle manager를 [소스 지도](../source-reading.md)에서 추적합니다. controller commit→broker 적용의 최소 경로와 기존 요청/metadata 변경 요청의 차이를 설명하고 실제 장애 증거를 제출합니다. 단일 노드 관찰만이면 분산 gate는 남습니다.

## K10 관측 보안 용량과 복구 CLUSTER-DESIGN

**선수 조건:** K08–K09, SLO·CPU/메모리/디스크·인증/권한·RPO/RTO.

### 동작 원리

운영 관측은 증상을 원인으로 바로 이름붙이지 않는 일입니다. end-to-end 지연에는 producer buffer, broker queue, replication, consumer fetch, handler queue, sink commit이 섞여 있습니다. group lag가 줄어도 offset을 너무 일찍 commit했다면 업무 처리는 누락될 수 있습니다. 반대로 open transaction이 LSO를 제한하면 broker에 bytes가 있어도 committed reader는 기다립니다. [Monitoring](https://kafka.apache.org/43/operations/monitoring/)

관측은 application event timeline, client metrics, broker/controller metrics, OS/container metrics를 연결합니다. request queue/처리 시간, under-replicated·under-min-ISR 상태, leader 변화, disk 사용률·I/O 대기, producer buffer/retry, consumer 처리/commit 속도, transaction 지연을 후보로 삼되 사용 버전에서 실제 metric 이름·단위·범위를 확인합니다. 원격 JMX endpoint·exporter·수집 스택은 이 Compose에 구성되어 있지 않으므로 수집 경로·접근 범위를 별도 구성합니다.

보안은 인증과 권한을 구별합니다. TLS certificate의 이름과 advertised listener, SASL identity, topic/group/transactional-id ACL의 자원 범위를 함께 설계합니다. 단일 localhost PLAINTEXT lab의 동작을 인증이 설정된 환경의 증거로 사용하지 않습니다. [Listener 설정](https://kafka.apache.org/43/security/listener-configuration/), [ACL](https://kafka.apache.org/43/security/authorization-and-acls/)

### 실험 A: 관측과 용량

baseline producer/consumer를 준비하고 지연 위치를 한 곳씩 바꿉니다. producer를 느리게, consumer handler를 느리게, sink를 느리게 만든 세 조건에서 같은 lag/latency 대시보드가 무엇을 놓치는지 확인합니다. fault마다 안정된 입력률·최대 backlog·실행시간·중단 조건을 명시합니다.

1,000개 이상의 요청 원장과 최소 20개 측정 구간으로 정상/혼합 부하를 비교합니다. 예시 목표는 5,000 records/s, event→sink p95 5초이지만 사전에 host 예산에 맞게 정하며 문서 숫자를 달성 결과로 쓰지 않습니다. 기본 2GiB lab에서 대규모 capacity 한계를 찾는 부하는 별도 환경으로 옮깁니다.

용량의 출발식은 `측정된 저장 bytes/s × retention초 × replica수 + index/내부topic/여유/재배치 공간`입니다. compression 비율은 실제 입력으로 측정합니다. backlog B를 순처리율 μ−λ로 줄인다면 단순 catch-up 시간은 `B/(μ−λ)`이고 μ≤λ이면 정상 유입을 유지하면서 따라잡을 수 없습니다. 장애 복구 중 replication·compaction·Streams restore가 μ를 바꾸는지 검증합니다.

### 실험 B: 최소 권한

별도 보안 환경에서 producer A는 입력 topic 쓰기만, consumer B는 지정 group과 topic 읽기만, 운영자는 필요한 describe 권한만 부여합니다. 허용 요청 성공과 다른 topic/group/transactional ID 접근 거부를 각각 검증합니다. 인증 실패·권한 실패·network 실패를 구별하고 credential을 보고서에 기록하지 않습니다. transactional producer를 쓰면 필요한 transactional-id 권한도 검사합니다. ACL 설정 파일이 존재한다는 사실로 enforcement를 증명하지 않습니다.

### 실험 C: 복구와 재처리

사용자 record·metadata·group offsets·transaction state·connector/Streams state의 복구 범위를 먼저 정의합니다. replication은 잘못된 발행·보존기간 만료·논리 오류의 독립 과거 시점을 자동 보존하지 않습니다. MirrorMaker도 원격 복제·offset 변환·순환·운영 절차가 필요한 시스템이며 “다른 클러스터이므로 백업 완료”가 아닙니다. [Geo-replication](https://kafka.apache.org/43/operations/geo-replication-cross-cluster-data-mirroring/)

독립 환경에서 보존한 입력 또는 선택한 복제/백업 절차로 복구합니다. 다른 cluster/topic identity에 옮긴 뒤 source offset을 그대로 target offset으로 쓰지 않습니다. offset translation 또는 event_id 기준의 재처리 위치를 증명합니다. source id/version, group별 적용 결과, stateful 집계, tombstone·retention 경계를 대조합니다.

RTO는 사고 선언부터 업무 oracle 통과까지, RPO는 확인한 입력 중 실제 복구 가능한 경계로 계산합니다. process healthy 시각에서 타이머를 끝내지 않습니다. runbook에 어떤 기준이면 cutover를 취소하는지 포함합니다.

**기대 증거:** 세 지연 위치의 metrics/원장, 용량·catch-up 계산과 실측, 권한 positive/negative 결과, 독립 복구 transcript와 ID별 정합성. 복구 도구를 아직 구축하지 않았으면 설계 상태로 남깁니다.

**실패 모드:** 평균 지연만 측정, 무조건 partition 증가, latency 시간 축 혼동, disk 경보 없이 retention만 축소, 내부 topic RF 누락, 새로운 cluster의 offset을 과거와 동일시, replica=backup이라고 판단.

**소스 방향·통과:** metrics의 갱신 위치, quota·request 처리·log retention 경로, metadata 복원 경계 중 하나를 source와 연결합니다. 실제 업무 상태로 복구했고 권한 제한이 동작한다는 증거가 있어야 운영 실행 gate를 통과합니다.
