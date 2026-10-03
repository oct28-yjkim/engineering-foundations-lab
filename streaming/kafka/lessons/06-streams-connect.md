# K11–K12. 상태 있는 처리와 외부 시스템 연결

[커리큘럼](../curriculum.md) · 이전: [KRaft와 운영](05-kraft-operations.md) · 다음: [연구와 캡스톤](07-research-capstone.md)

## K11 Streams의 시간 state store와 복구 BUILD

**선수 조건:** K08, 집계 상태·JOIN·event time·처리 순서.

### 동작 원리

Kafka Streams는 애플리케이션 안에서 실행되는 라이브러리입니다. topology의 작업은 input partition과 연결되는 task로 나뉘며 thread/instance에 배정됩니다. 무조건 instance를 늘린다고 task의 병렬 처리 한계가 사라지지는 않습니다. key 변경·groupBy·join에 필요한 repartition은 데이터 이동과 내부 topic 비용을 만들 수 있습니다. topology description으로 실제 경계를 확인합니다. [Streams architecture](https://kafka.apache.org/43/streams/architecture/)

KStream은 이벤트 흐름, KTable은 key별 변경되는 상태를 표현하는 관점입니다. null value와 duplicate event의 의미도 연산에 따라 달라집니다. count/sum은 같은 이벤트를 두 번 보면 효과가 커질 수 있고, key별 최신값은 입력 순서·timestamp·사용 API의 계약과 연결됩니다. “Streams를 사용하면 business duplicate가 자동 제거”되는 것은 아닙니다.

event time, processing/wall-clock time, Streams의 stream-time 진행을 구별합니다. window와 grace는 늦은 입력의 처리 범위를 결정하며, 잠시 wall-clock이 지났다는 사실만으로 같은 event-time 결론을 낼 수 없습니다. TimestampExtractor가 payload의 업무 시각을 쓰는지 broker record timestamp를 쓰는지 명시합니다. [Streams core concepts](https://kafka.apache.org/43/streams/core-concepts/)

state store는 단순한 cache로만 취급하지 않습니다. aggregate/join 상태, changelog 복제, restore, standby, local disk와 checkpoint가 시작 시간·메모리·정확성에 영향을 줍니다. Kafka 내부 processing guarantee와 임의의 외부 REST/DB 호출은 별개입니다. [Streams 설정](https://kafka.apache.org/43/configuration/kafka-streams-configs/)

### BUILD 실험: event-time oracle

Kafka Streams 4.3.1과 test-utils를 고정한 Java 프로젝트를 작성합니다. 저장소에는 완성 topology가 없으며 다음 fixture와 예상 상태가 구현 요구사항입니다.

key A의 event timestamp를 epoch 기준 +5초, +15초, +8초 순서로 넣고 30초 tumbling window, 10초 grace의 count를 만듭니다. 같은 window의 세 event는 서로 다른 ID입니다. 이후 +70초 입력으로 stream-time을 진행시킨 뒤 과거 +8초 event를 **새 ID**로 한 번 더 보냅니다. window 종료·grace 밖의 처리가 어떻게 되는지 해당 API 계약과 대조합니다. event-time 경계 바로 전/정확히 경계/바로 뒤도 별도 fixture로 둡니다.

`TopologyTestDriver`로 expected window/key/count와 late-record 결과를 검증합니다. timestamp 진행과 `advanceWallClockTime`을 별도 실험으로 사용하고 서로 바꿔 쓰지 않습니다. test driver는 broker network·rebalance·replication을 검증하는 환경이 아니므로 그 범위를 명시합니다. [Streams testing](https://kafka.apache.org/43/streams/developer-guide/testing/)

### BUILD 실험: 실제 state 복원

broker topic을 사용한 topology를 추가 실행하고 application.id·input partition·state.dir·internal topic 설정을 기록합니다. 초기 10,000개 event를 처리해 state와 output oracle을 보존합니다. 한 instance를 중단한 뒤 **새 state directory**의 instance로 재시작하여 changelog 기반 restore를 관찰합니다. 기존 state directory를 재사용한 빠른 재시작과 구별합니다. state 파일을 무계획 삭제하지 않고 run별 디렉터리를 분리합니다.

정상/복원 중 유입을 비교하고 restore bytes·시간·output 가시성·backlog를 측정합니다. `exactly_once_v2`를 사용하는 실험이라면 input/output/state commit 경계와 실패 주입을 검증하며 external side effect는 포함하지 않습니다. 추가로 동일한 input event_id를 두 번 넣어 business dedup가 별도 문제임을 확인합니다.

**기대 증거:** topology graph, test-driver의 deterministic oracle, event-time/wall-clock 반례, state 복원 전후 결과, internal topic과 restore metrics. compact된 changelog의 end-offset 차이를 state key 수라고 계산하지 않습니다.

**실패 모드:** grace를 wall-clock timeout으로 해석, key serde 변경 후 과거 state 재사용, 같은 application.id의 다른 topology를 무계획 배포, reset 도구로 input/output/state 정합성 파괴, local state 백업만으로 전체 복구 주장.

**소스 방향·통과:** `StreamThread`, `StreamTask`, state manager, changelog reader, cache/store 계층을 [소스 지도](../source-reading.md)에서 연결합니다. 늦은 이벤트·복원·business duplicate 세 fixture와 state oracle이 필요합니다.

## K12 Connect CDC와 외부 sink의 경계 INTEGRATION-DESIGN

**선수 조건:** K10–K11. PostgreSQL WAL/transaction 기초는 이 절의 DB 확장에서 보충할 수 있습니다.

### 동작 원리

Connect의 worker는 connector/task의 실행·재배치·설정/상태/offset 관리 구조를 제공합니다. source connector는 외부 위치에서 Kafka record를 만들고 sink connector는 Kafka record를 외부 시스템에 적용합니다. framework가 있다고 모든 connector가 같은 exactly-once·schema·retry 계약을 제공하는 것은 아닙니다. distributed worker의 내부 topic과 task 상태도 복제·권한·복구 계획에 포함됩니다. [Connect user guide](https://kafka.apache.org/43/kafka-connect/user-guide/)

source exactly-once 지원은 worker 모드·설정·connector 구현의 계약을 확인해야 합니다. source position을 output transaction과 묶는 지원과 외부 DB 전체 transaction을 Kafka에서 자동 재현하는 것은 다른 주장입니다. sink는 특히 외부 commit과 Kafka offset 사이의 불명 상태를 검증해야 합니다. [Connect administration](https://kafka.apache.org/43/kafka-connect/administration/)

PostgreSQL CDC에서는 snapshot과 streaming 변화의 경계, replication slot·WAL 보관, source transaction/LSN, delete의 식별 정보, schema evolution이 중요합니다. `updated_at > last_seen` polling은 commit 순서·같은 timestamp·삭제의 반례가 있습니다. Debezium을 선택한다면 connector 버전과 PG 지원 범위를 따로 고정하고 connector 문서의 snapshot·offset 계약을 확인합니다. Kafka 4.3.1과 connector 호환성을 이름만으로 추정하지 않습니다. [Debezium PostgreSQL connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)

### 추가 구축 명세

현재 Kafka Compose에 Connect worker·Debezium plugin·PostgreSQL logical decoding 설정·ClickHouse sink는 포함되어 있지 않습니다. 먼저 선택한 connector/version·plugin 설치·worker 설정·내부 topic RF·접속 권한·schema 형식을 manifest로 작성합니다. [공통 통합 연구](../../../databases/shared/capstone.md)의 실제 구축 단계와 합쳐 수행할 수 있습니다.

fixture는 주문 1,000개와 생성/결제/취소/부분환불/삭제를 포함합니다. 각 이벤트에 stable event_id, order_id, source position/version, schema version을 보존합니다. 원본 원장은 order별 최신 상태·순매출을 독립적으로 계산합니다. source transaction을 여러 topic으로 분리했다면 sink가 언제 일관된 상태로 공개하는지도 정의합니다.

| 실험 | 주입 지점 | oracle |
| --- | --- | --- |
| snapshot 경합 | snapshot 진행 중 같은 주문 update/delete | snapshot+stream의 누락/중복, 최종 order 상태 |
| source task 중단 | Kafka write와 source offset 확인 사이 | connector 재시작 후 stable ID별 record 흐름 |
| sink 중단 | 외부 commit 직후 Kafka offset commit 이전 | 재처리 후 최종 금액·상태·중복 적용 횟수 |
| schema 변경 | optional field 추가, 타입/의미 변경 | reader 호환·DLQ·재처리 정책; 조용한 필드 유실 없음 |
| source 지연 | connector가 WAL을 소비하지 못함 | slot/WAL 증가·저장 예산·복구 후 catch-up |

처리 불가능 record를 DLQ에 보냈으면 “성공 처리 수”에 조용히 포함하지 않습니다. 원본 위치·오류 종류·재처리 횟수·수동 결정이 추적되는지 검사합니다. record header와 변환(SMT)이 stable identity나 source version을 지우지 않는지도 확인합니다.

ClickHouse target은 append event, latest state, 사전 집계를 분리해 평가합니다. CDC의 여러 version을 그대로 `sum(amount)`하면 매출을 중복 계산할 수 있으므로 delta 이벤트·수정 가능 상태에서 재집계·명시적 rebuild 중 계약을 선택합니다. raw Replacing의 merge가 downstream MV의 과거 기여분을 자동 지우지 않는다는 반례를 포함합니다.

**기대 증거:** source position→Kafka topic/partition/offset→sink commit의 대응표, snapshot 경계 기록, retry/DLQ/스키마 변경 로그, 모든 order의 oracle. topic count만으로 CDC 정확성을 판단하지 않습니다.

**실패 모드:** Connect status RUNNING을 데이터 신선도로 판단, task 수 증가가 단일 source 병렬성 한계를 해결한다고 추측, WAL 보관량 미관찰, sink dedup 기간 밖 replay, snapshot/stream 경계 미정, optional field 추가와 의미 변경을 같은 호환성으로 처리.

**소스 방향·통과:** worker source/sink task, offset backing store, 선택한 connector의 snapshot/stream 코드, sink commit 경로를 연결합니다. 다섯 조건은 실제 구축 시 실행 gate이며 이번 모듈에서 설계만 했으면 [K14](07-research-capstone.md)의 설계 리뷰와 후속 통합 연구에 남은 항목을 명시합니다.
