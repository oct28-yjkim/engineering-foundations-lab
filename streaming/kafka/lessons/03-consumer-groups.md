# K05–K06. 소비 위치, 처리 완료, 그룹 소유권

[커리큘럼](../curriculum.md) · 이전: [Producer와 복제](02-producer-replication.md) · 다음: [전달 의미와 트랜잭션](04-transactions.md)

## K05 poll 처리 완료 offset commit LOCAL BUILD

**선수 조건:** K03, 비동기 작업 완료·재시도·업무 부작용.

### 동작 원리

consumer가 `poll()`로 데이터를 받으면 client의 position이 진행할 수 있습니다. 애플리케이션의 DB 쓰기나 HTTP 호출이 끝났다는 뜻은 아닙니다. committed offset은 group이 재시작할 때 사용할 위치이며 **다음에 처리할 offset**을 저장하는 convention을 사용합니다. 마지막으로 처리한 offset을 저장하면 그 record를 다시 읽게 됩니다. [KafkaConsumer API](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html)

partition 0의 offset 10,11,12를 병렬 처리하여 10과12만 끝났다면 13을 commit하면 안 됩니다. 11을 건너뛰기 때문입니다. 완료된 최대 offset이 아니라 누락 없이 연속으로 완료된 경계를 추적해야 합니다. commit은 같은 group의 위치 관리이지 임의 외부 효과의 transaction commit이 아닙니다.

`auto.offset.reset`은 매 시작마다 시작 위치를 강제하는 옵션이 아닙니다. 유효한 committed offset이 없거나 더 이상 그 위치를 사용할 수 없는 조건에서 적용됩니다. earliest도 이미 retention으로 사라진 데이터를 복구하지 못합니다. lag 역시 offset 경계 차이이며 compaction·control record·open transaction·처리 중 queue 때문에 업무 미처리 건수와 다를 수 있습니다. [Consumer 설정](https://kafka.apache.org/43/configuration/consumer-configs/)

### LOCAL 관찰

K01의 topic을 대상으로 새 group을 사용합니다. 아래 실습은 auto commit을 꺼서 replay가 별도 상태라는 점을 관찰합니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:19092 --topic k01-orders-exp1 --group k05-no-commit-exp1 --from-beginning --max-messages 5 --timeout-ms 10000 --command-property enable.auto.commit=false --formatter-property print.partition=true --formatter-property print.offset=true --formatter-property print.value=true
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --describe --group k05-no-commit-exp1
```

그룹 상태는 프로세스 생존·commit 유무에 따라 offset이 없거나 group이 없다고 나올 수 있습니다. 이를 메시지 손실이라고 판단하지 않습니다. 같은 consumer 명령을 다시 실행하고 각 partition의 첫 위치와 event_id를 비교합니다. 여러 partition을 동시에 읽으면 처음 출력된 5개가 전역적으로 똑같다는 계약은 없으므로 partition별로 대조합니다. `--from-beginning`을 이미 유효한 offset이 있는 다른 group의 강제 reset 명령으로 사용하지 않습니다.

### BUILD 실험: crash 위치와 oracle

수동 commit Java consumer와 작은 durable 처리 원장을 직접 구현합니다. consumer 객체는 기본적으로 여러 thread에서 자유롭게 공유할 수 있는 객체가 아닙니다. poll/commit을 담당하는 owner thread와 worker의 결과 전달을 명확히 나눕니다. worker를 쓰면 partition별 contiguous completion 경계를 구현합니다.

| 중단 위치 | 단순 구현에서 가능한 문제 | 독립 oracle |
| --- | --- | --- |
| offset commit 후 업무 처리 전 | 다시 읽지 못해 side effect 누락 | input event_id와 sink 적용 ID 차집합 |
| 업무 처리 후 offset commit 전 | 같은 record 재처리·중복 효과 | sink event_id 중복·금액 증가량 |
| 처리 일부 완료 후 rebalance | 이전 owner와 새 owner의 중복/잘못된 commit | partition ownership epoch와 commit timeline |

기본 입력 1,000개를 one-partition topic에 넣고 각 조건을 독립 run으로 재현합니다. 두 번째 단계에서 three-partition topic으로 확장합니다. sink는 append-only 파일만 사용하는 모형과 실제 transaction DB를 구별합니다. 파일 write가 OS buffer에 있는 상태를 durable commit이라고 이름붙이지 않습니다.

**기대 증거:** poll position, 처리 완료 집합, committed next-offset, sink 원장의 네 상태를 같은 timeline에 표시합니다. process 종료 방식·재시작 시각·group.id·reset 정책을 기록합니다. 끝 count가 같아도 누락과 중복이 상쇄될 수 있어 ID별 적용 횟수를 검사합니다.

**실패 모드:** poll=처리 완료, commitSync=DB commit, auto commit을 켜 둔 채 worker가 병렬 처리, max completed offset만 commit, 이전 실행 group을 재사용해 첫 데이터를 놓침, commit 실패를 무시.

**소스 방향·통과:** `KafkaConsumer`의 delegate, `SubscriptionState`, fetch/commit manager를 [소스 지도](../source-reading.md)에서 찾아 position과 committed state가 구별되는 지점을 설명합니다. 세 중단 위치의 실제 반례와 수정 후 oracle 통과를 제출합니다.

## K06 classic과 consumer group protocol LOCAL BUILD

**선수 조건:** K05, membership·ownership·heartbeat.

### 동작 원리

일반 consumer group은 구독 partition을 member에게 할당합니다. 정상적인 group assignment에서 같은 partition의 현재 owner는 하나지만 외부 부작용의 stale worker까지 broker가 자동 중지시키지는 않습니다. 여러 group은 독립적으로 같은 topic을 읽을 수 있고, 3개 partition에 4개 consumer를 두면 모든 consumer가 유용한 작업을 가지리라는 보장은 없습니다.

Kafka 4.3.1에서도 `group.protocol` 기본값은 `classic`입니다. 새 `consumer` 프로토콜은 server-side assignment와 점진적 reconciliation 경로를 사용하며 heartbeat/session 설정의 책임도 다릅니다. classic의 client `heartbeat.interval.ms`, `session.timeout.ms`를 consumer 프로토콜에 같은 방식으로 적용하지 않습니다. 실제 client 설정과 broker group 설정을 기록합니다. [Consumer rebalance protocol](https://kafka.apache.org/43/operations/consumer-rebalance-protocol/)

heartbeat는 member 생존을, poll interval은 애플리케이션 처리 진척과 관련된 제약을 관찰하는 데 사용됩니다. static membership은 불필요한 재할당을 줄일 기회를 주지만 processing crash를 영구적으로 숨기는 기능은 아닙니다. static member의 max-poll 초과와 dynamic member의 동작·시간 경계를 동일하게 단정하지 않습니다. [Consumer 설정](https://kafka.apache.org/43/configuration/consumer-configs/)

### LOCAL 실험

K01 topic에 console consumer를 같은 group으로 1개→2개→4개 띄웁니다. 각 프로세스는 별도 terminal에서 실행하고 종료 시간을 기록합니다. 그룹 protocol을 명시합니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -e "KAFKA_HEAP_OPTS=-Xms32m -Xmx128m" kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:19092 --topic k01-orders-exp1 --group k06-classic-exp1 --command-property group.protocol=classic --command-property enable.auto.commit=false --from-beginning --formatter-property print.partition=true --formatter-property print.offset=true
docker compose -f streaming/kafka/compose.yaml exec -T -e "KAFKA_HEAP_OPTS=-Xms32m -Xmx128m" kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --describe --group k06-classic-exp1 --members --verbose
```

위 `-e`는 추가 CLI JVM의 heap 예산이며 broker 설정을 바꾸지 않습니다. 기본 Compose의 2GiB 제한에서 여러 CLI를 실행할 때 JVM heap 외 메모리도 확인합니다. 가입·정상 종료·재가입 전후의 assignment를 보존합니다. 다른 새 group `k06-consumer-exp1`과 `group.protocol=consumer`로 같은 실험을 반복합니다. classic group에 일부 member의 protocol만 바꿔 무계획 migration을 시도하지 않습니다. protocol migration은 별도 호환성·broker 설정 과제로 다룹니다.

총 member 수보다 active partition owner 수와 partition별 처리 공백을 봅니다. console 출력은 애플리케이션의 처리 완료 시간을 주지 않으므로 그 지표를 수집했다고 주장하지 않습니다.

### BUILD 실험

K05 consumer에 assignment/revocation/lost callback 또는 현재 protocol의 대응 상태를 기록하고 partition별 처리 queue를 붙입니다. 하나의 handler를 일부러 느리게 하고 max-poll 조건을 넘겼을 때 assignment와 commit이 어떻게 바뀌는지 검증합니다. `pause()`가 처리 queue의 backpressure에 어떻게 도움을 주는지, pause 중에도 필요한 polling/liveness를 어떻게 유지하는지 설계합니다.

revocation 시에는 미완료 작업을 어떻게 취소·대기·재처리할지 정하고, 이미 소유권을 잃은 경우 무조건 commit을 시도하지 않습니다. 외부 DB에는 stable event_id나 fencing 가능한 업무 계약을 둡니다. `group.instance.id` 실험에서는 동시 실행한 두 instance가 같은 ID를 공유하는 잘못된 설정도 별도 fixture로 확인합니다.

**기대 증거:** 시간별 member/partition/epoch/처리/commit 대응표, classic/consumer 두 protocol에서 관찰한 차이, 처리 중 rebalance의 ID별 oracle. 시간이 짧은 몇 번의 실행으로 항상 특정 밀리초 내 재할당된다고 일반화하지 않습니다.

**실패 모드:** group.id를 client.id와 혼동, partition보다 member만 늘림, heartbeat 설정만 늘려 무한 정체를 숨김, cooperative 동작을 “중단 없음”으로 해석, 재할당 후 stale worker가 DB 갱신.

**소스 방향·통과:** `ClassicKafkaConsumer`, `AsyncKafkaConsumer`, membership/heartbeat manager, server group coordinator의 책임을 연결합니다. ownership timeline과 두 protocol의 정상·느린 처리·재시작 결과를 제출하고 명세에 없는 시간 보장을 하지 않습니다.
