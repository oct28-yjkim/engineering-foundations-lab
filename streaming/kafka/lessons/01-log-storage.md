# K01–K02. 이벤트 로그와 저장 구조

[커리큘럼](../curriculum.md) · 다음: [Producer와 복제](02-producer-replication.md)

## K01 이벤트와 partition의 계약 LOCAL

**선수 조건:** 없음. topic, key, value, producer, consumer의 용어부터 아래 작은 입력으로 정의합니다.

### 동작 원리

Kafka의 partition은 record가 추가되는 순서 있는 로그입니다. consumer가 읽었다고 해당 record를 즉시 제거하지 않으므로, 다른 group이나 새 처리 로직이 보관된 데이터를 다시 읽을 수 있습니다. 이때 위치인 offset과 업무상 정체성인 event_id를 구별해야 합니다. 같은 event_id를 다시 전송하면 다른 offset에 나타날 수 있고, 서로 다른 partition의 같은 offset은 같은 record가 아닙니다.

key는 직렬화된 bytes와 partition 선택 정책을 거쳐 배치 위치에 영향을 줍니다. 같은 설정과 partition 수를 유지하며 같은 key를 일관되게 보내는 계약을 먼저 정의합니다. partition 수 증가, serializer 변경, 명시 partition 지정, 다른 partitioner를 쓰는 producer는 그 계약을 바꿀 수 있습니다. null key도 “항상 round-robin”이라고 외우지 말고 사용 client의 실제 정책을 확인합니다. [Producer 설정](https://kafka.apache.org/43/configuration/producer-configs/)

로그 순서가 업무 발생 시각 순서를 자동으로 보장하지는 않습니다. 다른 producer에서 전송 지연이 발생할 수 있고, consumer가 여러 record를 병렬 처리하면 완료 순서도 바뀝니다. 주문 단위 상태 전이를 재현하려면 order_id별 source_version 같은 비교 규칙을 별도로 정의합니다. timestamp만으로 분산 시스템의 유일한 순서를 만들지 않습니다.

### 작은 실행 실험

먼저 [제공 smoke 실습](../labs/local-lab.md)을 수행해 설치 문제와 개념 실험을 분리합니다. 다음 명령은 **저장소 루트**에서 별도 topic을 생성합니다. 이미 같은 이름이 있으면 새 suffix를 선택합니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:19092 --create --topic k01-orders-exp1 --partitions 3 --replication-factor 1
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:19092 --describe --topic k01-orders-exp1
docker compose -f streaming/kafka/compose.yaml exec kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:19092 --topic k01-orders-exp1 --reader-property parse.key=true --reader-property key.separator="|"
```

마지막 명령은 대화형 입력입니다. `order-1|event-001,version=1,created`처럼 `|` 왼쪽에 key, 오른쪽에 값을 입력합니다. 주문 3개 × 변경 4개, 총 12개 event를 입력하고 EOF 또는 세션 종료로 producer를 마칩니다. 원장에는 각 event_id와 예상 주문별 version 순서를 미리 적습니다. 마지막 event를 **별도의 새 send로 한 번 더** 넣어 business duplicate도 만듭니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:19092 --topic k01-orders-exp1 --from-beginning --max-messages 13 --timeout-ms 10000 --formatter-property print.key=true --formatter-property print.partition=true --formatter-property print.offset=true --formatter-property print.timestamp=true
```

출력 전역 순서와 partition별 offset 순서를 나누어 표로 정리합니다. 입력한 13개와 distinct event_id 12개가 맞는지 확인합니다. 출력 13개라는 사실만으로 보존을 판단하지 말고 **event_id의 multiset**을 대조합니다. 같은 key들의 partition이 일치하는지, key 값이 partition 개수와 일대일 대응하는지 확인합니다. 서로 다른 key가 같은 partition으로 갈 수 있습니다.

**반증 과제:** “같은 event_id면 broker가 한 번만 저장한다”와 “topic 전체 순서는 모든 consumer에게 하나”를 반박합니다. BUILD 확장에서는 명시 partition과 source_version을 가진 Java producer로 도착 순서/업무 순서를 의도적으로 다르게 만듭니다.

**기대 증거:** 입력 원장, describe 출력, key/partition/offset/event_id 대응표, business duplicate 위치. broker를 실행하지 못했으면 예상표와 실제표를 구분합니다.

**실패 모드:** bootstrap 성공 뒤 advertised 주소 연결 실패, 여러 experiment를 같은 topic에 섞음, 출력 개수만 검사, key를 unique constraint처럼 취급, partition 수를 늘린 뒤 과거와 같은 위치를 가정.

**소스 방향:** [소스 지도](../source-reading.md)에서 `KafkaProducer`, `RecordAccumulator`, partition 선택 코드, record metadata를 찾습니다. partition 결정 전후에 key가 객체인지 bytes인지, offset은 누가 부여하는지 설명합니다.

**제출·통과:** 12개 event 원장과 1개 재전송, multiset 일치, 순서 보장/비보장 경계 3개. 같은 key를 다른 두 producer가 동시에 보낼 때 추가로 필요한 업무 계약도 말할 수 있어야 합니다.

## K02 segment index retention compaction LOCAL BUILD

**선수 조건:** K01, 파일 byte 위치·이진 탐색·page cache·압축.

### 동작 원리

partition의 로그는 여러 segment로 나뉘고 활성 segment에 추가합니다. logical offset을 파일의 byte 위치로 찾으려면 segment와 sparse offset index를 거쳐 실제 batch를 읽는 과정이 필요합니다. 최신 record batch는 base offset, offset delta, timestamp, producer 정보, CRC 등 버전 있는 형식을 사용합니다. **record offset을 파일 byte offset으로 계산하지 않습니다.** segment 이름의 숫자 역시 파일 크기가 아닙니다. [Message format](https://kafka.apache.org/43/implementation/message-format/)

순차 append와 batch는 요청·I/O의 고정 비용을 여러 record에 나눕니다. page cache와 파일 전송 최적화는 JVM heap 전체에 데이터를 쌓는 설계와 다릅니다. compression은 CPU·네트워크·저장량에 서로 다른 효과를 주며, TLS와 client/broker 경로에 따라 복사 비용도 달라집니다. ACK의 설정을 바꾸는 것과 매 record를 물리 매체에 fsync하는 것을 혼동하지 않습니다.

delete retention은 보관 기간/크기에 따라 segment를 제거하는 정책이고 compaction은 같은 key의 이전 값을 정리하는 정책입니다. 둘 다 “즉시 한 key 한 row”를 만드는 unique index가 아닙니다. compaction 후 offset에 구멍이 생길 수 있고 transaction control record도 offset을 사용하므로 end-start를 사용자 event 수로 일반화하지 않습니다. null value의 tombstone은 빈 문자열과 다른 삭제 의미를 가지며 보관·청소 조건에 영향을 받습니다. [Topic 설정](https://kafka.apache.org/43/configuration/topic-configs/)

### 실험

LOCAL에서는 직접 만든 별도 topic에 짧은 segment/retention 설정을 사용하고 시간별 시작/끝 offset과 `kafka-log-dirs.sh --describe`의 크기를 관찰합니다. 이 실험의 입력은 잃어도 되는 합성 데이터만 사용합니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:19092 --create --topic k02-retention-exp1 --partitions 1 --replication-factor 1 --config cleanup.policy=delete --config retention.ms=60000 --config segment.ms=10000 --config segment.bytes=1048576
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-log-dirs.sh --bootstrap-server kafka:19092 --describe --topic-list k02-retention-exp1
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:19092 --topic k02-retention-exp1 --time earliest
docker compose -f streaming/kafka/compose.yaml exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:19092 --topic k02-retention-exp1 --time latest
```

K01의 producer 방식으로 시각·event_id가 있는 record를 여러 구간에 걸쳐 전송합니다. 실제 broker의 `log.retention.check.interval.ms`와 segment roll 조건을 확인한 뒤 **검사 주기와 roll/retention 시간을 포괄하는 관찰 창**을 정합니다. 예를 들어 검사 주기가 5분이면 3분 관찰은 부족하므로 10분 이상에서 시작하되 삭제 완료의 보장 시간으로 삼지는 않습니다. append·segment roll·retention 검사 주기 때문에 60초에 정확히 삭제된다고 예상하지 않습니다. 관찰 창 안에 제거되지 않았으면 실제 설정·활성 segment·timestamp를 조사하고 미관찰로 남깁니다. 설정값을 결과 시간으로 복사하지 않습니다.

BUILD 과제에서는 key A의 v1/v2/tombstone, key B의 v1, 그리고 수천 개 반복 key를 별도 compact topic에 생성합니다. 진짜 null value는 ByteArray/String serializer의 null 인자로 전송하고 문자열 `"null"`과 대조합니다. cleaner 전후를 소비해 key별 최신 상태 oracle로 환원합니다. snapshot 이후부터 소비하는 경우 tombstone이 이미 청소되면 과거 상태를 어떻게 잘못 복원할 수 있는지 작은 반례를 만듭니다. cleanup을 기다렸지만 관찰되지 않은 경우 test fixture의 크기·dirty ratio·segment 조건부터 검토합니다.

파일 inspection은 [로컬 안내](../labs/local-lab.md)의 실제 log dir에서 **해당 실험 topic**만 식별해 수행합니다. `kafka-dump-log.sh`로 batch/offset/index를 읽는 심화 과제를 수행하되 운영 파일을 편집하거나 truncation으로 결과를 맞추지 않습니다. 원시 파일 해석은 해당 record format과 runtime 버전을 연결합니다.

**기대 증거:** segment/file 크기와 logical offset의 차이, 시간별 earliest/latest, compaction 전후의 논리 상태와 삭제 tombstone. 단일 snapshot만으로 cleaner가 이미 끝났다고 판단하지 않습니다.

**실패 모드:** retention=즉시 삭제, 압축 bytes와 record 수 혼동, null/빈 값 혼동, compact topic을 유일성 제약처럼 조회, 오래된 snapshot을 tombstone 보관기간 밖에서 재생.

**소스 방향·통과:** `UnifiedLog`, `LocalLog`, `LogSegment`, `OffsetIndex`, `LogCleaner`의 실제 버전 경로를 [소스 지도](../source-reading.md)에서 찾습니다. offset→segment→index→batch 읽기 그림과 compaction oracle, 복구 가능 기간 ADR을 제출합니다.
