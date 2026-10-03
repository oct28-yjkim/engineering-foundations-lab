# S09–S10 — 수집 파이프라인, backlog, 재처리와 저장 일관성

이 강의는 **설치되어 있지 않은 스택을 실행했다고 가정하지 않습니다.** `SELF-HOST-DESIGN`이 기본이며, 실제 검증은 별도 격리 배포를 학습자가 준비한 경우에만 수행합니다. SaaS에서는 내부 broker/consumer/DB에 접근할 수 있다는 가정을 하지 않습니다.

## S09. 하나의 수집 요청이 여러 시스템을 통과하는 이유

### 선수 조건과 원리

S04, queue·consumer·batch의 기초가 필요합니다. Kafka 전체 과정을 마치지 않았다면 [Kafka 로그·복제](../../../streaming/kafka/lessons/02-producer-replication.md)의 ACK/복제 경계와 [consumer](../../../streaming/kafka/lessons/03-consumer-groups.md)의 offset만 보충합니다. ClickHouse는 batch 저장과 비동기 조회 가시성의 개념부터 시작합니다.

Sentry backend, Relay, Snuba, Symbolicator는 서로 다른 책임을 가집니다. Relay는 수집·검증·정규화·제한 등 ingress 경로에 관여하고, Kafka는 처리 단계를 분리하는 로그/queue 역할을 맡습니다. 오류 전처리와 symbolication은 stack을 해석하고 grouping에 필요한 정보를 보완합니다. Snuba는 특정 분석 데이터의 수집/조회 경로와 ClickHouse를 연결합니다. 사용자·조직·프로젝트 등 메타데이터와 일부 원본 저장, 첨부파일·artifact 등 blob은 모두 같은 테이블에 저장되는 것이 아닙니다. [Architecture overview](https://develop.sentry.dev/application-architecture/overview/)

이 설명은 책임 지도이지 모든 버전·신호의 단일 topology가 아닙니다. 현재 self-hosted data-flow 문서는 taskbroker/taskworker 등 구성 요소와 오류 처리 경로를 보여 줍니다. 다른 문서의 오래된 queue 명칭을 현재 deployment의 프로세스 이름으로 덮어쓰지 않습니다. error·span·log·Replay·profile은 서로 다른 topic, consumer, 저장 경로를 가질 수 있습니다. 오류 경로를 복사해 모든 신호를 설명하면 잘못된 장애 분석이 됩니다. [Self-hosted data flow](https://develop.sentry.dev/self-hosted/data-flow/)

핵심 경계는 최소 여섯 개입니다. 수집 HTTP 응답, durable queue 기록, 처리 완료, 분석 저장, 검색 가시성, issue/알림 갱신을 별도로 둡니다. 같은 `event_id`가 모든 topic·row·API에서 동일한 형태로 보존된다고 가정하지 않고 단계별 상관 ID와 schema를 확인합니다. 서로 다른 저장소의 상태는 한 번의 SQL transaction으로 함께 바뀌지 않을 수 있습니다.

### 실험 A: 선택 revision의 실제 graph 만들기 — `SELF-HOST-DESIGN`

입력은 선택한 self-hosted tag/commit의 Compose, 이미지 manifest, backend/Relay/Snuba의 revision과 관련 command/config입니다. `main`을 읽었다면 이를 학습용 source snapshot으로 표시하고 runtime과 같다고 쓰지 않습니다.

1. error, span, log, Replay, attachment 중 최소 세 유형을 선택합니다. 지원되지 않는 유형은 제외 이유와 기능 검증 근거를 기록합니다.
2. 각 유형에 ingress→queue→processor→store→query graph를 작성합니다. 프로세스·topic·consumer group·table·blob 경로는 실제 설정에서 확인한 것만 기입합니다.
3. 각 edge에 payload 단위, ID, ACK 의미, retry/drop, retention, credential boundary, 관측 지표를 표시합니다.
4. 명시적인 “unknown” 칸을 둡니다. SaaS 내부를 공개 self-hosted 코드만으로 확정하지 않습니다.

oracle은 소스·배포 설정의 교차 일치입니다. 문서에 있는 컴포넌트가 선택 Compose에 없거나 command가 다르면 차이를 설명해야 합니다. source graph를 runtime 검증으로 주장하지 않습니다. gate는 세 신호의 graph와 최소 여섯 경계, image/commit 근거, 유형별 차이 두 가지입니다.

### 실험 B: 합성 ID의 단계별 관측 — 별도 배포 시 `SELF-HOST-DESIGN` 실행 확장

전용 synthetic project에 100개 event를 낮은 속도로 보내기 전에 입력 원장과 각 단계에서 사용할 read-only 조회를 준비합니다. 이 교재는 계정·DSN·배포를 만들지 않습니다. 운영 cluster에 직접 topic/DB를 수정하지 않습니다.

단계별 최초 관측 시각과 결과를 수집합니다. 수신 성공 수와 검색 결과 수를 즉시 비교하여 loss라고 단정하지 말고, freshness window와 일관성 계약을 둡니다. 내부 queue 접근이 불가능하면 HTTP 응답과 API 조회 사이 구간을 “내부 원인 미확인”으로 남깁니다. 같은 run의 ID 집합과 payload hash를 비교하고, 단순 count 일치만으로 잘못된 내용의 대체를 놓치지 않습니다.

산출물은 phase timeline, read-only query, raw response, ID별 확인 상태입니다. 관측하지 못한 경계는 명시하며, UI screenshot만 제출하지 않습니다. 실험하지 않았다면 단계별 예상 실패 상태와 어떤 측정이 필요한지까지 설계 산출물로 제출합니다.

## S10. backlog가 없어도 사용자는 오래된 데이터를 볼 수 있다

### 선수 조건과 원리

S09, 집합 비교, queue 처리율을 이해해야 합니다. consumer lag는 특정 로그의 특정 offset 경계 차이입니다. 처리 중인 batch, 다른 downstream queue, 색인/조회 지연, 잘못된 project·시간 조건은 해당 lag 값에 드러나지 않을 수 있습니다. “lag=0이면 정상”이라는 운영 규칙은 수집부터 조회까지의 freshness를 놓칩니다.

처리율 `μ`, 유입률 `λ`, backlog `B`인 단순 정상 모델에서 `μ > λ`일 때 따라잡기 시간은 대략 `B/(μ-λ)`입니다. 실제로는 병목 이동, batch 크기, retry, skew, merge 부하, 다른 유형의 경쟁이 있으므로 모델 값과 측정을 구별합니다. retention이 만료되면 재처리에 필요한 원본이 사라질 수 있습니다. retention을 크게 하는 것과 독립된 백업·복구 가능성은 다른 문제입니다.

재처리는 원본 payload를 다시 읽어 후속 결과를 만들 수 있지만, 버전·grouping 규칙·artifact·schema가 바뀌면 처음과 다른 결과가 나올 수 있습니다. event 원본, issue grouping, session 집계, metric 집계, 알림은 중복 처리의 영향이 다릅니다. Kafka ACK나 consumer offset commit만으로 모든 downstream side effect의 exactly-once를 주장하지 않습니다.

### 실험: 세 가지 실패 행렬 — `OFFLINE` 모델 / 별도 격리 배포 확장

입력은 event 1,000개와 발생/송신 시각 원장입니다. 유형별 event ID와 내용 hash, 기대 검색 집합을 보관합니다. 장애 주입은 정상 복구 가능한 시험 배포에서만 수행합니다. 아래는 이미 제공된 자동 장애 스크립트가 아니라 구현해야 할 요구사항입니다.

| 장애 | 독립적으로 관찰할 증거 | 반증할 잘못된 주장 |
| --- | --- | --- |
| ingest 뒤 처리 consumer 일시 중단 | ingress ACK, 해당 lag, downstream count, freshness age | ACK가 왔으므로 검색도 완료 |
| 저장/조회 의존성 지연 또는 접근 실패 | consumer 상태·retry·오류, query 결과, 다른 저장소 metadata | Kafka lag 하나로 전체 파이프라인 건강 판정 |
| 선택 cohort의 중복 재처리 | 원본 ID/hash 집합, raw row와 issue/metric/알림의 별도 영향 | event 중복 방지가 모든 side effect 중복 방지 |

OFFLINE에서는 상태 전이 simulator를 만들고 실패 지점별 가능한 상태를 열거합니다. 실제 배포에서는 stop/restart의 정확한 서비스와 의존성을 선택 revision에서 확인하고, 데이터 볼륨 삭제나 임의 consumer offset reset을 기본 절차로 쓰지 않습니다. 사고 전에 수집한 기준 offset/config 없이 재처리 범위를 추정하지 않습니다.

oracle은 cohort별 `missing = expected - observed`, `unexpected = observed - expected`와 ID별 발생 횟수·내용 hash입니다. 기대가 event 수인데 관측이 issue 수인 비교는 금지합니다. 늦게 온 입력은 deadline 전에는 pending, deadline 후에는 breach로 분류하며 영구 loss와 지연을 구별합니다. retry로 다시 만들어진 event_id가 달라질 수 있으면 logical ID도 함께 사용합니다.

### 복구·retention 설계와 gate

backlog가 증가하는 동안 현재 유입·유효 처리율·가장 오래된 미처리 사건의 age를 기록합니다. 세 개의 처리율 시나리오에 대해 따라잡기 가능 여부를 계산하고, retention 안에 따라잡지 못하는 반례를 포함합니다. upstream 제한, degraded mode, 합성 health signal, escalation 기준을 작성합니다. 데이터 양을 무작정 줄여 오류가 없어 보이게 하는 것은 복구가 아닙니다.

세 장애 모두 정상 예상값·실패 증거·복구 후 oracle을 제시하면 설계 gate를 통과합니다. 실제 검증 gate는 별도의 실행 원시 증거가 필요합니다. 복구 후 count뿐 아니라 ID 집합·내용·grouping/집계 side effect를 확인해야 합니다. [소스 지도](../source-reading.md)에서 consumer commit 위치, processor retry, storage insert, query 경계를 한 경로씩 추적합니다.
