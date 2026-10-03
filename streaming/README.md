# Event Streaming Engineering — Zero to Hero

이 영역은 데이터를 보내는 API 사용법에서 출발해 **로그의 내구성, 처리 상태, 재시도, 복제, 복구의 경계를 증명하는 능력**을 기릅니다. [Apache Kafka](kafka/README.md)와 [NATS Core·JetStream](nats/README.md) 트랙을 제공합니다. 어느 broker도 데이터베이스의 대체품이나 모든 연결의 정답으로 취급하지 않습니다. 업무 데이터의 보존·조회·전달 책임을 구분해 함께 설계합니다.

## 기술 선택과 비교

| 질문 | Kafka | Core NATS | NATS JetStream |
| --- | --- | --- | --- |
| 기본 사고 단위 | partition log·offset·consumer group | subject·interest·subscription·queue group | stream·subject·stateful consumer |
| 기본 전달/재처리 | 보존 log와 consumer 위치, 설정별 ACK/transaction 경계 | best-effort at-most-once; 서버 영속 replay 없음 | 보존 정책·ACK·재전달·dedup 조건을 설계 |
| 소비자 분배 | partition ownership 기반 기본 consumer 모델 | queue group 안에서 matching subscriber 선택 | pull/push consumer와 delivery/ACK 상태; Core queue와 동일하지 않음 |
| 업무 결과 확정 | 외부 DB transaction까지 자동 원자화하지 않음 | request reply/flush가 업무 성공을 자동 보장하지 않음 | PubAck/double ACK가 외부 업무 exactly-once를 자동 보장하지 않음 |
| 실습 시작 | 독립 단일 KRaft Compose | NATS CPU 모형 또는 owned loopback server | 같은 NATS server에서 JetStream을 켠 선택 fixture |

이 비교는 동일한 durability·replication·payload 조건의 성능 순위가 아닙니다. NATS의 subject를 Kafka partition으로, consumer ACK를 committed offset과 같은 상태 구조로 치환하지 않습니다. 제품별 보장은 고정 버전·설정·실패 모델에서 검증합니다. [Core 개념](https://docs.nats.io/learn/core-nats/), [JetStream 개념](https://docs.nats.io/concepts/jetstream).

## NATS 트랙 구성

NATS는 **28주·14모듈·7강·336시간**의 선택 과정입니다. 아래 기존 PG/Kafka/CH 100주 경로에 자동 추가하지 않습니다. 공통 기초가 있다면 NATS만 먼저 진행할 수 있습니다.

- [시작 안내](nats/README.md), [커리큘럼](nats/curriculum.md), [평가표](nats/assessment.md)
- [CPU 모형 4개와 실제 서버 실습](nats/labs/README.md), [환경·안전 경계](nats/environment.md), [검증 기록](nats/labs/validation.md)
- [고정 소스·Raft 원전](nats/source-reading.md), [별도 선택 8주 전달·업무 복구 연구](../capstones/nats-delivery-recovery.md)

실제 fixture는 기존 NATS에 접속하지 않고 새 임시 저장소의 loopback 프로세스를 소유·종료합니다. Kafka/DB Compose를 시작할 필요가 없으며 자동 bridge·connector·CDC는 없습니다. NATS Streaming(STAN)은 이 과정의 JetStream과 다른 legacy 시스템입니다.

## 학습 경로

Kafka만 집중할 때는 [공통 기초](../databases/shared/foundations.md) 8주 + Kafka 28주를 기준으로 합니다. SQL·OS·네트워크·분산 시스템 진단을 통과한 부분은 줄일 수 있습니다. Java source를 읽고 작은 producer/consumer를 구현하는 준비도 필요합니다. 언어·빌드 기초가 부족하면 준비 시간을 추가합니다.

세 기술을 처음부터 순차 학습하는 확장 경로는 다음과 같습니다. 주 12시간 기준이며 모든 실험을 한 번에 성공한다는 보장은 없습니다.

| 순서 | 기간 | 핵심 질문 | 결과물 |
| --- | --- | --- | --- |
| 공통 기반 | 1–8주, 96h | 어떻게 정확성과 인과를 검증하는가? | 독립 oracle·반복 실험·실패 모델 |
| PostgreSQL | 9–36주, 336h | 원본 변경은 언제 commit되고 복구되는가? | MVCC/WAL/복제 추적·restore |
| Kafka | 37–64주, 336h | 어느 경계까지 쓰였고, 읽혔고, 처리됐는가? | log/group/transaction 추적·장애 이력 |
| ClickHouse | 65–92주, 336h | 재시도·늦은 변경에도 분석값이 맞는가? | MergeTree/집계/중복·보정 실험 |
| 통합 연구 | 93–100주, 96h | 전체 경로가 업무 계약을 지키는가? | CDC·정합성·복구·설계 방어 |

총 **100주·약 1,200시간**입니다. 기존 [DB 전용 72주 경로](../databases/README.md)도 유지합니다. 공통 기반과 통합 연구를 중복 계산하지 않으며, Kafka 트랙 K14의 설계 검토는 통합 연구 전체 구현을 대체하지 않습니다. 업무 우선순위에 따라 트랙 순서는 바꿔도 됩니다.

## Kafka 트랙 구성

- [학습 안내](kafka/README.md): 선행 지식, 읽기 순서, 실행 범위
- [28주·14모듈 커리큘럼](kafka/curriculum.md): 원리 → 실험 → 구현 → 장애 → 평가
- [로컬 실습](kafka/labs/local-lab.md): 단일 노드 KRaft, CLI 관측, 정확성 smoke
- [소스 탐색](kafka/source-reading.md): 고정 revision, 상태 전이, 실제 test를 따라 읽기
- [평가](kafka/assessment.md): 구술 문제·필수 gate·증거 기준
- [통합 캡스톤](../databases/shared/capstone.md): PostgreSQL → Kafka → ClickHouse 계약 검증

읽고 이해했다고 체크하는 대신 예측·실측·설명·반례를 함께 제출합니다. [공통 실험 방법](../databases/shared/experiment-method.md)과 [실험 보고서 양식](../databases/shared/templates/experiment-report.md)을 재사용합니다.

## 세 시스템에서 같은 단어가 다른 경계를 뜻한다

| 질문 | PostgreSQL | Kafka | ClickHouse |
| --- | --- | --- | --- |
| 어디까지 진행했는가? | WAL LSN, transaction 상태 | topic-partition offset, consumer commit, LSO 등 | 적재 batch·part, 업무 version, 조회 가시성 |
| 성공 응답이 무엇을 증명하는가? | transaction/동기 복제 설정의 응답 조건 | acks·ISR·transaction·실패 모델에 따른 조건 | insert/복제·적재 설정에 따른 조건 |
| 재처리가 무엇을 바꾸는가? | constraint·transaction·멱등성 키 설계에 따름 | producer 중복 제거와 업무 중복은 별개 | latest state·dedup 범위·집계 모델에 따름 |
| 무엇으로 맞음을 판단하는가? | 원본 업무 상태·금액·제약 | event identity, partition별 이력·처리 기록 | 동일 기준점의 상태·순매출 대조 |

위 위치들은 서로 같은 숫자 체계가 아닙니다. PG의 LSN, Kafka offset, 업무 version을 변환식 하나로 일치시키지 않습니다. 이벤트에 매핑을 보존하고, 전체 파이프라인의 검증 기준점을 명시합니다. Kafka offset commit만으로 ClickHouse 반영을 증명할 수도 없습니다.

## 환경 범위와 안전

Kafka Compose는 DB Compose와 독립적이며 로컬 loopback에만 포트를 공개합니다. 학습용 평문 연결이므로 운영 배포 예제가 아닙니다. 제공되는 것은 단일 broker/controller이며 다중 노드 복제·장애 허용·외부 sink exactly-once의 증거가 아닙니다. 분산 실습은 별도 격리 환경, 중단 조건, 데이터 보존 계획을 먼저 구성합니다.

공식 동작 계약의 출발점은 [Apache Kafka 4.3 문서](https://kafka.apache.org/43/)입니다. 구체적인 API·설정과 source는 해당 교재의 고정 버전에 맞추고, 문서의 기대 결과를 실측 결과로 제출하지 않습니다.
