# K07–K08. 전달 의미와 Kafka 트랜잭션

[커리큘럼](../curriculum.md) · 이전: [Consumer](03-consumer-groups.md) · 다음: [KRaft와 운영](05-kraft-operations.md)

이 강의의 Java 애플리케이션은 구현 과제입니다. 제공 smoke script가 idempotence·transaction·외부 DB exactly-once를 검증한다고 해석하지 않습니다.

## K07 idempotence와 업무 멱등성 BUILD

**선수 조건:** K05–K06, 중복·재시도·consumer ownership.

### 동작 원리

같은 논리 입력이 두 번 전달되어도 효과가 한 번과 같다면 그 연산을 해당 범위에서 멱등하다고 할 수 있습니다. Kafka idempotent producer는 producer identity와 sequence로 **내부 retry**의 중복 append를 방지하는 계약을 제공합니다. 애플리케이션이 새 `send()` 호출로 동일 주문 결제를 두 번 보낸 것은 다른 요청입니다. payload나 business key를 비교해 없애 주지 않습니다. producer process가 재시작한 뒤 무엇이 유지되는지도 transactional.id의 유무와 구별해야 합니다. [KafkaProducer 계약](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html)

at-most-once/at-least-once/exactly-once라는 말은 “어디부터 어디까지 어떤 효과인가”가 있어야 의미가 있습니다. consumer가 외부 PostgreSQL에 쓰고 offset을 따로 commit한다면 두 commit 사이 crash가 있습니다. stable event_id의 중복 방지 기록과 업무 변경을 **같은 PostgreSQL transaction**에 넣는 방식으로 재처리 효과를 제어할 수 있지만 Kafka의 임의 offset commit과 하나의 원자적 commit이 되는 것은 아닙니다. 최종 결과와 retry 가능성을 따로 검증합니다.

ClickHouse에 쓰는 경우에는 unique constraint를 가정하지 않습니다. insert dedup의 범위·보관 기간, Replacing의 논리 최신값, 집계 target의 중복 기여를 각각 검토합니다. 목표가 latest-state인지 모든 이벤트 합계인지에 따라 oracle도 달라집니다. 외부 시스템의 보장을 Kafka EOS라는 이름으로 생략하지 않습니다.

### 실험과 oracle

K03 producer를 확장하여 아래 조건을 독립 topic/run으로 비교합니다. idempotence와 충돌하는 client 설정을 주었을 때 설정 오류가 나는지 실제 설정 검증도 포함합니다.

| 조건 | 입력 | 확인할 것 |
| --- | --- | --- |
| 앱 정상 입력 | 고유 event_id 10,000개 | 입력과 소비 multiset 일치 |
| 앱 재전송 | 동일 event_id 100개를 새 send로 다시 전송 | idempotence만으로 제거되지 않는 business duplicate |
| 전송 retry | 테스트 proxy/격리 network로 응답 경로 지연·유실 | producer retry·sequence·최종 중복 여부; timeout은 unknown으로 분류 |
| process 재시작 | 마지막 ACK 불명 위치에서 앱 복구 | producer session과 업무 재전송 경계 |

network failure injection은 기본 Compose에 제공되지 않습니다. 시간 제한·원복 절차가 있는 테스트 proxy 또는 별도 격리 환경을 구현해야 해당 조건을 실행 완료로 판정합니다. 단순 `sleep()` 후 같은 payload를 보내는 것은 네트워크 내부 retry 실험이 아닙니다.

sink 확장에서는 1,000개의 금액 이벤트를 처리합니다. 잘못된 버전 A는 “잔액 증가 후 offset commit”을 수행하고 그 사이 중단합니다. 버전 B는 event_id unique 원장 등록과 잔액 증가를 같은 DB transaction에서 처리하고, 성공 후 Kafka offset을 commit합니다. replay 후 distinct event_id·각 ID 적용 횟수·잔액을 독립적으로 대조합니다. checkpoint만 옮겨 A의 결과를 맞추지 않습니다.

**기대 증거:** producer 내부 retry와 새 send의 차이, ACK/unknown 목록, broker 위치, sink 적용 횟수. “exactly-once 설정을 켰다”라는 문장 대신 실제 범위와 실패 가정을 제시합니다.

**실패 모드:** event_id를 매 retry 새로 생성, 중복 기록만 별도 transaction으로 쓰기, dedup window 밖 replay 미검증, sink 오류를 DLQ에 보낸 뒤 원장 불변식 누락, timeout을 확정 미저장으로 취급.

**소스 방향·통과:** producer sequence/epoch 관리와 broker `ProducerStateManager`를 [소스 지도](../source-reading.md)에서 연결합니다. business duplicate 반례 1개와 수정된 sink oracle, 미구현 failure injection 범위를 제출합니다.

## K08 Kafka transaction과 read_committed BUILD

**선수 조건:** K07, transaction coordinator·fencing·가시성.

### 동작 원리

Kafka transaction은 여러 partition의 output과 consumer group offset을 함께 commit하거나 abort하는 처리 단위를 만들 수 있습니다. consumer가 `read_committed`를 사용해야 abort된 transactional record를 업무 결과에서 제외하는 계약을 얻습니다. 이는 모든 partition을 동시에 읽는 데이터베이스 snapshot을 의미하지 않습니다. 서로 다른 partition의 poll은 다른 시점에 도착할 수 있으므로 애플리케이션이 전역 일관 snapshot을 자동으로 얻는다고 주장하지 않습니다. [Transaction 설계](https://kafka.apache.org/43/design/design/#using-transactions)

LEO, HW, LSO는 이 교재에서 모두 **exclusive 경계**로 다룹니다. read_committed는 LSO보다 작은 범위에서 commit 여부를 확인하여 사용자 record를 반환하고 abort record를 제외합니다. LSO는 HW와 첫 미완료 transaction의 시작 위치에 의해 제한됩니다. 앞쪽 transaction이 열려 있으면 뒤쪽 non-transactional record도 일시적으로 보이지 않을 수 있습니다. read_uncommitted도 임의의 미복제 로그 끝까지 읽는다는 의미는 아닙니다. [Consumer isolation 설정](https://kafka.apache.org/43/configuration/consumer-configs/#isolation.level)

`transactional.id`는 논리 producer의 복구와 fencing 경계를 제공합니다. 동시에 독립 실행해야 하는 worker들이 같은 값을 공유하면 서로를 fence할 수 있습니다. 반대로 매 재시작마다 무작위 ID를 만들면 논리 worker 복구 계약을 바꿉니다. 4.3의 transaction protocol과 feature level은 과거 버전의 epoch/partition 등록 설명과 다를 수 있어 실제 client·broker 조합을 기록합니다. [Transaction protocol](https://kafka.apache.org/43/operations/transaction-protocol/)

### BUILD 실험 1: 가시성의 네 상태

Java producer 2개와 consumer 2개를 구현합니다. transactional producer는 `initTransactions()` 후 `beginTransaction()`을 사용하고 다른 producer는 필요하면 non-transactional 후속 record를 넣습니다. consumer는 각각 read_committed/read_uncommitted로 같은 범위를 읽습니다. 모두 새 run/topic에서 수행합니다.

| 상태 | fixture | oracle |
| --- | --- | --- |
| commit | T1: event A/B 후 commit | committed reader에서 A/B 모두 eventually 관찰 |
| abort | T2: event C/D 후 abort | committed reader에서 C/D 제외, uncommitted와 대조 |
| open | T3: event E 후 열린 채 대기, 뒤에 event F | LSO 제한과 F의 지연; commit/abort 후 진행 |
| fencing | 같은 transactional.id의 두 번째 producer 초기화 | 구 producer 오류 분류·close, 중복된 업무 효과 없음 |

“eventually”의 관찰 제한 시간을 사전 정하고 timeout을 실패/미확정으로 분리합니다. console consumer로 바깥 결과를 보조 관찰할 수 있지만 transaction 생성과 상태 제어는 직접 작성한 프로그램이 담당합니다. consumer별 start offset과 isolation 설정을 증거에 남깁니다. transactional control record 때문에 offsets 사이에 빈 번호가 있어도 곧바로 업무 데이터 유실이라고 판단하지 않습니다.

### BUILD 실험 2: consume-transform-produce

다음은 구현 순서를 설명하는 의사코드입니다. 컴파일 가능한 완성 예제가 아닙니다.

```text
consumer: enable.auto.commit=false, isolation.level=read_committed
producer: logical worker별 transactional.id
poll input -> beginTransaction
각 record를 검증하고 deterministic output 생성 -> output send
partition별 연속 처리 완료 next-offset 계산
sendOffsetsToTransaction(nextOffsets, consumer.groupMetadata())
commitTransaction
```

입력 10,000개에서 `output.value = input.value * 2`처럼 단순하고 독립적인 oracle을 먼저 사용합니다. commit 직전 중단, commit 응답 유실/재연결, rebalance 중 처리의 세 경우를 추가합니다. abort하면 client의 이미 진행된 position은 자동으로 “업무 처리 전 상태”가 되었다고 가정하지 않습니다. committed position으로 seek하거나 consumer를 재생성하는 복구 경로를 구현하고 반복 입력을 transaction으로 재처리합니다. 예외는 retriable/abort 필요/fatal-fenced 등 API 계약에 맞게 구분하고 무조건 계속하지 않습니다.

**기대 증거:** input ID와 committed output ID의 정확한 대응, committed next-offset, abort 흔적과 visible output 구별, transaction state/epoch 로그. external HTTP 호출·DB side effect는 이 Kafka transaction에 자동 포함되지 않음을 별도 표로 보여 줍니다.

**실패 모드:** auto commit과 transactional offset 혼용, output transaction만 쓰고 입력 offset을 따로 commit, 모든 worker의 같은 transactional.id, abort 뒤 client position을 복구하지 않음, read_uncommitted 결과로 EOS 판정, 전역 snapshot 보장 주장.

**소스 방향·통과:** client `TransactionManager`, server transaction coordinator, log producer state와 visibility 경로를 연결합니다. 네 가시성 fixture와 consume-transform-produce 중단 시나리오의 oracle이 통과해야 합니다. RF1 성공은 multi-broker durability 검증과 분리합니다.
