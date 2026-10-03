# K03–K04. Producer의 상태와 복제된 로그

[커리큘럼](../curriculum.md) · 이전: [저장 구조](01-log-storage.md) · 다음: [Consumer](03-consumer-groups.md)

## K03 producer buffer부터 ACK까지 LOCAL BUILD

**선수 조건:** K02, Java Future·callback·thread·buffer.

### 동작 원리

`send()`는 serialization·metadata·buffer 확보를 거쳐 비동기 전송에 필요한 상태를 만들며, 반환 자체가 broker 저장 성공을 뜻하지 않습니다. partition별 batch에 모인 데이터는 sender의 network request로 전달되고 응답에 따라 callback/Future가 완료됩니다. 반대로 serialization 오류나 buffer/metadata 대기는 호출 thread에서 관찰할 수 있습니다. enqueue 시간과 callback 완료 시간, exception 경로를 나누어 측정합니다. [KafkaProducer API](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html)

`batch.size`와 `linger.ms`는 채울 기회와 대기 비용을 조절합니다. active partition이 많으면 작은 batch가 여러 곳에 흩어질 수 있습니다. `buffer.memory`는 무한 queue가 아니며 sink보다 입력이 빠르면 대기/실패가 발생합니다. `delivery.timeout.ms`, request timeout, 최대 blocking 시간은 적용 단계가 다르므로 한 개의 “timeout”으로 기록하지 않습니다. [Producer 설정](https://kafka.apache.org/43/configuration/producer-configs/)

producer의 내부 retry는 전송 결과를 모르는 상황에서 일어날 수 있습니다. idempotence는 producer identity·epoch·sequence와 broker 상태를 사용하지만 임의의 같은 JSON을 자동 식별하는 기능이 아닙니다. callback에서 timeout을 받았다고 그 event가 broker에 절대 없다고 단정하지 않습니다. 미확정 응답은 최종 원장과 대조할 상태입니다.

### 제공 LOCAL 관찰

[smoke script](../labs/scripts/01-smoke.sh)의 입력·검증 로직을 읽고 producer 종료와 consumer oracle 사이의 경계를 표시합니다. console producer로 입력한 상태와 event가 소비된 상태를 구분합니다. 서비스가 healthy여도 client가 잘못된 advertised 주소를 받으면 전송이 실패할 수 있다는 것을 endpoint 표로 설명합니다.

### BUILD 실험: callback 원장

Java producer를 직접 작성하는 과제입니다. 완성 프로그램은 저장소에 포함되지 않습니다. client dependency를 4.3.1로 고정하고 다음 event를 100,000개 생성합니다.

```text
event_id = run_id + sequence
key = customer_id (100개의 균등 key, 별도 실험은 1개 key에 50% 집중)
value = source_version + event_time + payload
ledger = enqueue_ns, callback_ns, topic, partition, offset, exception_type
```

호출마다 `get()`로 직렬화하지 말고 bounded in-flight 전송으로 기준선을 구성합니다. 종료 시 모든 완료/실패를 수집하고 `sent = acknowledged + failed/unknown`을 원장으로 검사합니다. 유입률을 무제한으로 높이지 말고 record/초와 최대 큐 크기를 사전 선언합니다.

한 변인씩 비교합니다: linger 0/5/20ms, payload 100B/1KiB, compression 없음/lz4. 시간상 모든 조합이 어렵다면 먼저 linger 3조건을 완료하고 다른 변인은 후속 실험으로 명시합니다. warm-up 뒤 각 조건 20개 이상 측정 구간을 사용하고 throughput뿐 아니라 ACK p50/p95, 오류율, batch 크기, buffer 대기, network bytes, CPU를 비교합니다. payload 반복도가 compression 효율에 미치는 영향도 설명합니다.

**반증 과제:** “linger가 증가하면 latency는 항상 그만큼 느려진다”를 부하 조건별로 시험합니다. 개선이 관찰되면 queueing/요청 효율이라는 가설과 다른 동시 변화 여부를 조사합니다. 다른 호스트의 wall-clock 차이를 producer 내부 monotonic 시간과 섞지 않습니다.

**기대 증거:** callback 원장, 성공한 event_id multiset, retries/unknown 분류, 설정 3조건과 실제 metrics. broker 내부 append 순간을 직접 측정하지 않았으면 callback 시간을 append 시간이라 이름붙이지 않습니다.

**실패 모드:** send 반환을 성공 처리, callback 오류 누락, 지연된 callback에서 오랜 blocking 처리, 무제한 futures 보관, 같은 event_id를 다른 payload로 retry, client 병목을 broker 한계로 판단.

**소스 방향·통과:** `KafkaProducer`→`RecordAccumulator`→`Sender`→`NetworkClient`에서 경계 4개를 찾고 buffer 소유권·완료 경로·예외 분기 하나씩 설명합니다. 100,000개 입력의 ACK/최종 기록 대조와 세 조건 비교가 필요합니다.

## K04 복제 가시성과 리더 전환 CLUSTER-DESIGN

**선수 조건:** K03, crash·network partition·quorum.

### 동작 원리

partition에는 leader와 replica가 있고 follower가 로그를 가져옵니다. replication factor는 배치된 복제본 수, ISR은 동기화 상태를 관리하는 집합입니다. `acks=all`을 “설정된 모든 replica” 또는 “고정 과반수”라고 번역하지 않습니다. ACK 판단과 `min.insync.replicas`의 제약, 현재 ISR, 오류/리더 전환 조건을 함께 봅니다. `acks=1`의 leader ACK와 replicated commit을 같은 보장으로 취급하지 않습니다. [Kafka replication 설계](https://kafka.apache.org/43/design/design/#replication)

log end offset은 해당 로그의 다음 append 위치이며 high watermark는 소비 가시성과 연결되는 복제 경계입니다. transaction의 last stable offset은 또 다른 경계입니다. 관측 도구가 inclusive/exclusive 중 어떤 convention을 쓰는지 기록합니다. page cache에 기록된 사실, ISR에 복제된 사실, 물리 매체 장애를 견디는 사실도 구분합니다.

4.3 과정에서는 과거의 “ISR 밖이면 언제나 unsafe leader” 설명을 그대로 쓰지 않습니다. Eligible Leader Replicas는 특정 조건에서 안전하게 선출 가능한 추가 상태를 추적하며 새 클러스터의 feature 상태에 따라 적용됩니다. ELR과 strict min ISR의 high watermark 진행 규칙을 확인합니다. unclean leader election과 ELR을 같은 것으로 취급하지 않습니다. [ELR 공식 설명](https://kafka.apache.org/43/operations/eligible-leader-replicas/)

### 추가 구축 실험

기본 Compose의 RF1로는 수행할 수 없습니다. 격리된 **broker 3개와 controller quorum**을 구축하고 topic RF3, `min.insync.replicas=2`, producer `acks=all`을 명시합니다. controller 수·data replica 수·물리 failure domain을 각각 그림에 표시합니다. host 하나의 컨테이너 6개는 protocol 실험이며 host 장애 내성을 증명하지 않습니다.

100,000개 event_id 원장과 ACK 결과를 보존하고 각 장애를 별도 run에서 주입합니다.

| 조건 | 반증할 주장 | 관찰과 oracle |
| --- | --- | --- |
| follower 1개 중단 | replica 하나가 없으면 모든 쓰기가 중단된다 | ISR 변화·ACK·timeout·최종 ID 대조 |
| follower 2개 중단 | acks=all이면 어떤 상황에도 성공한다 | minISR/ELR feature·오류·HW 진행 상태 |
| leader 중단과 전환 | producer timeout은 항상 미저장이다 | leader epoch·retries·unknown ID의 실제 위치 |
| 느린 follower/일시 단절 후 복귀 | process up이면 즉시 in-sync다 | 복제 지연·ISR/ELR 전이·catch-up 완료 |

전환 중 같은 source sequence가 업무 순서대로 보이는지와 중복이 생기는지를 별도로 검사합니다. configuration을 바꿔 `acks=1`과 비교할 경우 새 topic/run에 한정하고 손실 가능성이 있는 설정의 범위를 명시합니다. unclean election이나 로그 훼손을 기본 환경에서 실행하지 않습니다.

**기대 증거:** 장애 전/중/후 리더·ISR·ELR·HW/LEO, client ACK/unknown 원장, 복구 후 per-partition event 집합. acknowledged record 보존과 availability를 함께 평가합니다. 복구 후 count만 같고 다른 ID가 섞인 경우 실패입니다.

**실패 모드:** RF를 minISR로 오해, data replication과 controller Raft quorum 혼동, 새 노드가 뜨자마자 catch-up 완료라고 판단, ACK 원장 없는 유실 주장, 단일 노드 성능으로 RF3 처리량 예측.

**소스 방향·통과:** `ReplicaManager`, `Partition`, follower fetch 경로, leader/ISR 변경 코드를 [소스 지도](../source-reading.md)에서 추적합니다. 네 장애의 실측과 원복 증거가 있어야 실행 통과입니다. 설계만 했다면 남은 구축·관찰 항목을 표시합니다.
