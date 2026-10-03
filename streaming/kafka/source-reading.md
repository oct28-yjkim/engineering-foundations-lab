# Kafka 4.3.1 소스 읽기: 요청, 로그, 상태 전이, 복구

소스 탐색의 단위는 파일 수가 아니라 **검증할 주장**입니다. “이 요청은 언제 성공으로 응답하는가”, “어느 offset까지 읽을 수 있는가”, “재시작하면 외부 부작용이 반복되는가”를 정한 뒤 client 입력 → protocol 요청 → broker/coordinator 상태 → 영속 기록 → 관측 결과로 추적합니다. [커리큘럼](curriculum.md), [로컬 환경](labs/local-lab.md), [평가 관문](assessment.md)을 함께 사용합니다.

## 기준 버전과 실제 실행 환경

공식 Apache 저장소에서 확인한 기준은 다음과 같습니다.

| 항목 | 값 |
| --- | --- |
| release tag | `4.3.1` |
| annotated tag object | `a07059eb9b5bac1bfdbb1e74313f2fae4ca20fd9` |
| 실제 commit, peeled tag | `26b251a451ce941d3d7a55e6487bcb7f16b5ad48` |
| 고정 소스 | [Apache Kafka commit](https://github.com/apache/kafka/tree/26b251a451ce941d3d7a55e6487bcb7f16b5ad48) |

태그 object SHA와 실제 소스 commit SHA는 다릅니다. 아래 지도는 읽기 편의를 위해 `4.3.1` 링크를 사용하며, 재현 보고서에서는 위 commit과 로컬 checkout을 대조합니다. upstream 소스 기준이 같아도 Docker 이미지의 빌드 옵션·JDK·라이브러리·설정까지 같다는 뜻은 아닙니다. 제공 이미지의 tag/digest, broker와 client 버전, `metadata.version`, feature 상태, effective config를 따로 기록합니다. `4.3.1`이라는 이미지 이름만으로 배포 바이너리와 소스의 완전한 동일성을 주장하지 않습니다.

읽기 전용 확인 예시:

```bash
git ls-remote https://github.com/apache/kafka.git refs/tags/4.3.1 'refs/tags/4.3.1^{}'
git rev-parse HEAD
git describe --tags --always
git status --short
java -version
```

Git 확인은 **Kafka 소스 checkout 안에서** 수행합니다. 학습 저장소 engineering-foundations-lab의 HEAD를 Kafka source SHA로 기록하지 않습니다. 로컬 broker 점검은 저장소 루트에서 다음을 사용합니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/00-inspect.sh
```

이 스크립트의 관측과 source build/test는 서로 다른 증거입니다. 컨테이너 내부 bootstrap은 `kafka:19092`, host에서 실행하는 client는 `localhost:9092`를 사용하며, host용 주소를 container 내부 client에 그대로 쓰지 않습니다.

## 검증된 구현 경로

아래 경로는 공식 `4.3.1` 원본 또는 해당 commit의 Git tree에서 존재를 확인했습니다. 줄 번호 대신 클래스·메서드와 commit을 기록합니다. 실제 source를 수정하거나 실행했다는 의미는 아닙니다. 첫 탐색에서는 각 경로의 caller/callee 한 단계와 상태 변경 한 개만 추적합니다.

### K01–04: produce, 저장, 복제

| 경로·출발점 | 추적할 불변식과 연결할 실험 |
| --- | --- |
| [`clients/src/main/java/org/apache/kafka/clients/producer/KafkaProducer.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/producer/KafkaProducer.java) · `send` | API 반환·Future 완료·callback 실행을 구분. 전송 timeout 뒤 실제 기록 여부를 확인 |
| [`clients/src/main/java/org/apache/kafka/clients/producer/internals/RecordAccumulator.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/producer/internals/RecordAccumulator.java) · `RecordAccumulator` | partition별 batch/버퍼와 drain 조건. batch.size·linger·압축·buffer exhaustion 비교 |
| [`clients/src/main/java/org/apache/kafka/clients/producer/internals/Sender.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/producer/internals/Sender.java) · `Sender` | 요청 생성, 응답 분류, retry, delivery deadline. app 재전송과 client 내부 retry 차이 |
| [`clients/src/main/java/org/apache/kafka/clients/NetworkClient.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/NetworkClient.java) · `send`, `poll` | socket readiness, in-flight request, correlation, timeout·disconnect의 응답 완료 경로 |
| [`storage/src/main/java/org/apache/kafka/storage/internals/log/UnifiedLog.java`](https://github.com/apache/kafka/blob/4.3.1/storage/src/main/java/org/apache/kafka/storage/internals/log/UnifiedLog.java) · `lastStableOffset`, `fetchOffsetSnapshot` | log start/end, HW, LSO와 transaction state의 관계. 열린 transaction이 읽기를 막는 경계 |
| [`storage/src/main/java/org/apache/kafka/storage/internals/log/LocalLog.java`](https://github.com/apache/kafka/blob/4.3.1/storage/src/main/java/org/apache/kafka/storage/internals/log/LocalLog.java) · `LocalLog` | segment 집합, append·roll·truncate의 책임. 파일 크기와 offset을 같은 단위로 읽지 않기 |
| [`storage/src/main/java/org/apache/kafka/storage/internals/log/LogSegment.java`](https://github.com/apache/kafka/blob/4.3.1/storage/src/main/java/org/apache/kafka/storage/internals/log/LogSegment.java) · `LogSegment` | record batch, offset/time index와 실제 파일 위치. index는 전체 record 복제본인가? |
| [`storage/src/main/java/org/apache/kafka/storage/internals/log/LogCleaner.java`](https://github.com/apache/kafka/blob/4.3.1/storage/src/main/java/org/apache/kafka/storage/internals/log/LogCleaner.java) · `LogCleaner` | cleanable/uncleanable 경계, key별 과거 버전 정리, tombstone. compaction을 즉시 중복 제거·백업으로 해석하는 반례 |
| [`core/src/main/scala/kafka/server/ReplicaManager.scala`](https://github.com/apache/kafka/blob/4.3.1/core/src/main/scala/kafka/server/ReplicaManager.scala) · `ReplicaManager` | append/fetch 요청과 replica 상태의 연결. ACK 조건·ISR·HW·leader epoch를 같은 것으로 취급하지 않기 |
| [`core/src/main/scala/kafka/cluster/Partition.scala`](https://github.com/apache/kafka/blob/4.3.1/core/src/main/scala/kafka/cluster/Partition.scala) · `Partition` | partition별 leader/follower·ISR·HW 상태와 append/fetch 판정. min ISR 조건의 위치 |
| [`core/src/main/scala/kafka/server/ReplicaFetcherThread.scala`](https://github.com/apache/kafka/blob/4.3.1/core/src/main/scala/kafka/server/ReplicaFetcherThread.scala) · `ReplicaFetcherThread` | follower fetch·append·epoch/truncation 경로. 노드 기동과 catch-up 완료의 차이 |

4.3.1에서는 위 로그 구현 경로가 Java의 `storage` 모듈에 있습니다. 과거 블로그의 Scala 경로를 찾지 못했다는 이유로 기능이 없어졌다고 판단하지 않습니다. compaction 후 남은 record의 offset을 재번호 매긴다고 가정하지 않고, 소비자가 gap을 어떻게 통과하는지 관측합니다.

### K05–08: consumer protocol, coordinator, transaction

| 경로·출발점 | 추적할 불변식과 연결할 실험 |
| --- | --- |
| [`clients/src/main/java/org/apache/kafka/clients/consumer/ConsumerConfig.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/consumer/ConsumerConfig.java) · `GROUP_PROTOCOL_CONFIG` | 실제 protocol·설정 기본값과 유효성. 기존 client heartbeat 설정이 새 protocol에서도 적용되는가? |
| [`clients/src/main/java/org/apache/kafka/clients/consumer/internals/ConsumerDelegateCreator.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/consumer/internals/ConsumerDelegateCreator.java) · `create` | `group.protocol=consumer`가 AsyncKafkaConsumer를 선택하는 분기와 classic 경로 비교 |
| [`clients/src/main/java/org/apache/kafka/clients/consumer/internals/ClassicKafkaConsumer.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/consumer/internals/ClassicKafkaConsumer.java) · `ClassicKafkaConsumer` | classic poll/network/coordinator 흐름. 오래된 rebalance 설명이 어느 구현에 해당하는가? |
| [`clients/src/main/java/org/apache/kafka/clients/consumer/internals/AsyncKafkaConsumer.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/consumer/internals/AsyncKafkaConsumer.java) · `AsyncKafkaConsumer` | application/network event 경계. poll 호출, 처리 완료, offset commit을 분리 |
| [`clients/src/main/java/org/apache/kafka/clients/consumer/internals/ConsumerMembershipManager.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/consumer/internals/ConsumerMembershipManager.java) · `ConsumerMembershipManager` | member epoch·assignment reconciliation. 해제된 partition에서 이전 작업이 계속 쓰는 문제 |
| [`group-coordinator/src/main/java/org/apache/kafka/coordinator/group/GroupMetadataManager.java`](https://github.com/apache/kafka/blob/4.3.1/group-coordinator/src/main/java/org/apache/kafka/coordinator/group/GroupMetadataManager.java) · `GroupMetadataManager` | broker-side membership·target/current assignment와 coordinator record. client 계획과 서버 상태를 대조 |
| [`group-coordinator/src/main/java/org/apache/kafka/coordinator/group/OffsetMetadataManager.java`](https://github.com/apache/kafka/blob/4.3.1/group-coordinator/src/main/java/org/apache/kafka/coordinator/group/OffsetMetadataManager.java) · `OffsetMetadataManager` | commit/fetch 및 내부 offset record. 현재 position과 복구용 committed offset이 다른 이유 |
| [`clients/src/main/java/org/apache/kafka/clients/producer/internals/TransactionManager.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/producer/internals/TransactionManager.java) · `TransactionManager` | producer ID/epoch/sequence, transactional state, retryable/abortable/fatal 구분과 fencing |
| [`storage/src/main/java/org/apache/kafka/storage/internals/log/ProducerStateManager.java`](https://github.com/apache/kafka/blob/4.3.1/storage/src/main/java/org/apache/kafka/storage/internals/log/ProducerStateManager.java) · `ProducerStateManager` | broker의 producer/sequence·미완료 transaction·snapshot 복구 상태. 내부 retry 판정과 업무 중복의 차이 |
| [`core/src/main/scala/kafka/coordinator/transaction/TransactionCoordinator.scala`](https://github.com/apache/kafka/blob/4.3.1/core/src/main/scala/kafka/coordinator/transaction/TransactionCoordinator.scala) · `TransactionCoordinator` | transaction 상태 기록·완료 처리·marker 전파. producer API 성공과 소비 가시성 경계 |

4.3 문서에서 `group.protocol` 기본값은 `classic`이며 `consumer`를 지정하면 새로운 protocol 경로를 사용합니다. heartbeat/session timeout의 설정 주체도 달라지므로 둘을 같은 실험 결과로 묶지 않습니다. [공식 consumer 설정](https://kafka.apache.org/43/configuration/consumer-configs/).

Offset은 이 과정의 구현 추적에서 **exclusive 경계**로 통일합니다. LEO는 다음 append 위치, HW는 복제 관점의 읽기 경계, LSO는 `UnifiedLog.lastStableOffset()`에서 아직 결정되지 않은 transaction의 첫 offset과 HW를 고려한 경계입니다. 보통의 같은 로그 상태에서 `LSO <= HW <= LEO`를 확인하되, 서로 다른 broker·시점의 값을 하나의 snapshot처럼 비교하지 않습니다. `offset < LSO`인 record도 aborted transaction이면 `read_committed`의 결과에서 제외될 수 있습니다. 경계값을 record 건수로 해석하지 않습니다.

강화된 transaction protocol은 `transaction.version=2`와 이를 지원하는 producer 조합을 확인합니다. 이 경로에서는 transaction마다 producer epoch를 올려 이전 transaction의 늦은 요청이 다음 transaction에 섞이는 경우를 방어합니다. protocol 변경 인지는 연결/재연결과 다음 transaction 경계에 연관되며 진행 중 transaction을 임의로 새 protocol로 바꾼다고 해석하지 않습니다. 동일 API 이름이어도 과거의 epoch 설명을 그대로 적용하지 않는 이유입니다. [공식 transaction protocol](https://kafka.apache.org/43/operations/transaction-protocol/).

### K09–12: metadata quorum, Streams, Connect

| 경로·출발점 | 추적할 불변식과 연결할 실험 |
| --- | --- |
| [`raft/src/main/java/org/apache/kafka/raft/KafkaRaftClient.java`](https://github.com/apache/kafka/blob/4.3.1/raft/src/main/java/org/apache/kafka/raft/KafkaRaftClient.java) · `KafkaRaftClient` | quorum election, epoch, commit와 snapshot. metadata quorum과 data partition 복제의 별도 역할 |
| [`metadata/src/main/java/org/apache/kafka/controller/QuorumController.java`](https://github.com/apache/kafka/blob/4.3.1/metadata/src/main/java/org/apache/kafka/controller/QuorumController.java) · `QuorumController` | controller 요청→metadata record→적용. active controller 상태와 영속 로그를 구분 |
| [`metadata/src/main/java/org/apache/kafka/controller/ReplicationControlManager.java`](https://github.com/apache/kafka/blob/4.3.1/metadata/src/main/java/org/apache/kafka/controller/ReplicationControlManager.java) · `ReplicationControlManager` | partition 등록·leader/ISR/ELR 변경. feature 활성 상태가 선출 조건에 미치는 영향 |
| [`streams/src/main/java/org/apache/kafka/streams/processor/internals/StreamTask.java`](https://github.com/apache/kafka/blob/4.3.1/streams/src/main/java/org/apache/kafka/streams/processor/internals/StreamTask.java) · `StreamTask` | task 입력·처리·punctuation·commit 상태. event time과 wall clock, 입력 offset과 출력 가시성 |
| [`streams/src/main/java/org/apache/kafka/streams/processor/internals/ProcessorStateManager.java`](https://github.com/apache/kafka/blob/4.3.1/streams/src/main/java/org/apache/kafka/streams/processor/internals/ProcessorStateManager.java) · `ProcessorStateManager` | state store 등록·changelog·checkpoint·restore. local store 제거 후 무엇으로 상태를 복원하는가? |
| [`connect/runtime/src/main/java/org/apache/kafka/connect/runtime/WorkerSourceTask.java`](https://github.com/apache/kafka/blob/4.3.1/connect/runtime/src/main/java/org/apache/kafka/connect/runtime/WorkerSourceTask.java) · `WorkerSourceTask` | source record 전송과 source offset commit의 경계. snapshot/CDC 위치와 Kafka offset 구별 |
| [`connect/runtime/src/main/java/org/apache/kafka/connect/runtime/ExactlyOnceWorkerSourceTask.java`](https://github.com/apache/kafka/blob/4.3.1/connect/runtime/src/main/java/org/apache/kafka/connect/runtime/ExactlyOnceWorkerSourceTask.java) · `ExactlyOnceWorkerSourceTask` | 지원 connector·worker 설정·transaction 경계 확인. 클래스 존재만으로 모든 source의 EOS 보장 주장 금지 |
| [`connect/runtime/src/main/java/org/apache/kafka/connect/runtime/WorkerSinkTask.java`](https://github.com/apache/kafka/blob/4.3.1/connect/runtime/src/main/java/org/apache/kafka/connect/runtime/WorkerSinkTask.java) · `WorkerSinkTask` | sink put/flush/preCommit와 offset 관리. 외부 DB commit 뒤 장애가 나면 무엇이 반복되는가? |
| [`connect/runtime/src/main/java/org/apache/kafka/connect/runtime/distributed/DistributedHerder.java`](https://github.com/apache/kafka/blob/4.3.1/connect/runtime/src/main/java/org/apache/kafka/connect/runtime/distributed/DistributedHerder.java) · `DistributedHerder` | connector/task assignment·재설정·재시작. REST 성공과 실제 task 정상 상태 차이 |

ELR은 “Kafka 4.x이면 같은 기본값”으로 취급하지 않습니다. 실제 4.3.1의 feature 상태, broker/topic 설정, ISR/ELR 목록과 선출 이력을 함께 기록합니다. 선출을 바꾸는 설정은 해당 버전의 [broker 설정](https://kafka.apache.org/43/configuration/broker-configs/)과 위 controller 코드로 검증합니다. 단일 combined broker/controller 구성에서는 quorum 상실과 RF=3 leader 선출을 실행 검증할 수 없습니다.

Streams/Connect의 exactly-once 범위가 HTTP 결제·메일·외부 DB에 자동 확장되지는 않습니다. 외부 시스템의 transaction·idempotency·unique key·checkpoint 저장 위치를 별도 모델링하고, 해당 connector의 구현과 source system 계약까지 추적해야 합니다.

## K13: 빌드와 검증된 테스트 출발점

4.3.1의 [공식 README](https://github.com/apache/kafka/blob/4.3.1/README.md)는 JDK 17과 25로 빌드/테스트하며, clients/Streams는 Java release target 11, 나머지는 17로 설정한다고 설명합니다. Scala는 2.13을 사용합니다. 이는 학습용 source build에 JDK 11이면 충분하다는 뜻이 아닙니다. [Gradle wrapper](https://github.com/apache/kafka/blob/4.3.1/gradle/wrapper/gradle-wrapper.properties)는 **9.2.1**을 지정합니다. 시스템 Gradle을 임의로 바꾸기보다 checkout의 wrapper를 사용합니다.

필요 환경은 JDK 17 또는 25, Git, shell, wrapper/dependency를 받을 네트워크·저장 공간, 테스트 프로세스용 메모리입니다. 최초 빌드가 의존성 다운로드 때문에 실패했는지 테스트 assertion 때문에 실패했는지 구별합니다. 제공 Compose에는 Kafka source checkout, IDE, debugger, Connect/Streams 앱이 자동으로 준비되지 않습니다. Windows에서는 WSL2/Linux의 별도 소스 작업 디렉터리를 사용할 수 있습니다.

Kafka source checkout에서:

```bash
./gradlew --version
./gradlew jar
./gradlew clients:test --tests org.apache.kafka.clients.producer.internals.RecordAccumulatorTest
./gradlew clients:test --tests org.apache.kafka.clients.producer.internals.SenderTest
```

다음 테스트 클래스는 모두 위 commit의 실제 경로를 확인했습니다. 전체를 무조건 실행하는 대신 연구 질문에 맞는 1–2개를 선택합니다. 테스트가 많은 클래스를 반복하는 시간과 비용도 측정합니다.

| 실제 테스트 소스 | 선택 실행 task | 읽을 관점 |
| --- | --- | --- |
| [`clients/src/test/java/org/apache/kafka/clients/producer/internals/RecordAccumulatorTest.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/test/java/org/apache/kafka/clients/producer/internals/RecordAccumulatorTest.java) | `clients:test --tests org.apache.kafka.clients.producer.internals.RecordAccumulatorTest` | batch/drain·모의 시간·버퍼 전제 |
| [`clients/src/test/java/org/apache/kafka/clients/producer/internals/SenderTest.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/test/java/org/apache/kafka/clients/producer/internals/SenderTest.java) | `clients:test --tests org.apache.kafka.clients.producer.internals.SenderTest` | 응답·retry·실패 분류의 mock 경계 |
| [`clients/src/test/java/org/apache/kafka/clients/consumer/internals/ConsumerMembershipManagerTest.java`](https://github.com/apache/kafka/blob/4.3.1/clients/src/test/java/org/apache/kafka/clients/consumer/internals/ConsumerMembershipManagerTest.java) | `clients:test --tests org.apache.kafka.clients.consumer.internals.ConsumerMembershipManagerTest` | 새 group protocol의 membership 전이 |
| [`raft/src/test/java/org/apache/kafka/raft/KafkaRaftClientTest.java`](https://github.com/apache/kafka/blob/4.3.1/raft/src/test/java/org/apache/kafka/raft/KafkaRaftClientTest.java) | `raft:test --tests org.apache.kafka.raft.KafkaRaftClientTest` | 제어된 시간·응답 순서 아래 quorum 상태 |
| [`streams/src/test/java/org/apache/kafka/streams/processor/internals/StreamTaskTest.java`](https://github.com/apache/kafka/blob/4.3.1/streams/src/test/java/org/apache/kafka/streams/processor/internals/StreamTaskTest.java) | `streams:test --tests org.apache.kafka.streams.processor.internals.StreamTaskTest` | task·commit·복구 전제 |
| [`connect/runtime/src/test/java/org/apache/kafka/connect/runtime/WorkerSinkTaskTest.java`](https://github.com/apache/kafka/blob/4.3.1/connect/runtime/src/test/java/org/apache/kafka/connect/runtime/WorkerSinkTaskTest.java) | `connect:runtime:test --tests org.apache.kafka.connect.runtime.WorkerSinkTaskTest` | sink 호출과 offset 처리 순서 |

task 앞에는 `./gradlew`를 붙입니다. 모듈 이름은 같은 태그의 [settings.gradle](https://github.com/apache/kafka/blob/4.3.1/settings.gradle)과 일치시켰습니다. 테스트 경로 확인과 테스트 실행 성공은 다릅니다. 문서 작성 시 위 테스트를 실행한 결과를 제공하는 것은 아니며 학습자가 자신의 로그·XML/HTML 결과·실행 건수를 제출해야 합니다. `UP-TO-DATE`, `SKIPPED`, 필터에 맞는 테스트 0개를 성공 증거로 쓰지 않습니다. 재실행이 필요하면 선택 task에 `--rerun-tasks`를 사용합니다.

### 최소 재현 → 구현 → 회귀 검증

1. K03 batch, K06 membership, K08 열린 transaction 중 한 현상을 작은 입력·단일 질문으로 줄입니다. topic/group/transactional.id와 client 버전을 기록합니다.
2. API에서 보이는 결과를 먼저 확인합니다. CLI 출력만으로 확인할 수 없는 retry/fencing/transaction 상태는 별도 Java 앱 또는 해당 모듈 테스트가 필요합니다.
3. 선택 코드의 입력 상태, 소유 thread, 큐/lock, 바뀌는 필드, 영속 record, 반환/오류를 1쪽에 씁니다. 모든 함수가 직접 연속 호출된다고 가정하지 말고 network/event 경계를 표시합니다.
4. 관련 테스트를 그대로 실행해 baseline을 확보합니다. 실제 broker가 없는 mock test라면 그 사실을 기록합니다. debugger 옵션은 `./gradlew help --task clients:test` 등으로 확인하고 해당 테스트 JVM에만 연결합니다.
5. 현상을 만드는 입력 A와 경계를 넘는 입력 B를 비교합니다. 예: batch가 채워진/비어 있는 경우, revoke된/할당된 partition, commit/abort된 transaction. 두 경로의 stack·상태·응답 차이를 보관합니다.
6. 실제 결함이면 실패하는 최소 회귀 테스트를 먼저 추가합니다. 정상 동작이면 관측된 계약을 검증하는 테스트/설명으로 제출합니다. 정상 코드를 억지로 수정하지 않습니다.
7. 변경된 경로와 연관 테스트를 다시 실행하고, mock의 제한 때문에 필요한 별도 multi-broker/외부 sink 시험을 [평가표](assessment.md)에 미완료로 표시합니다.

필수 source note는 `runtime/source fingerprint → 주장 → 입력 A/B → 실제 stack/상태 → 소스 분기 → 보장 범위 → 반례 → 테스트 결과`입니다. 한 줄의 코드 주석을 운영 보장 전체로 확대하지 않고, 관측 사실과 코드에서의 추론을 분리합니다.
