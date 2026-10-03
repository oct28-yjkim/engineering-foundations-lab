# 04. consumer 상태·pull/push·ACK·재전달·업무 원장

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="nt07"></a>
## NT07: consumer는 읽기 API가 아니라 상태 기계다

선수 조건: NT06, sequence, state machine, worker pool. consumer는 stream의 선택된 메시지를 어떤 시작점과 정책으로 전달하고 확인할지 관리합니다. pull/push, durable/ephemeral, filter, 시작 위치, replay, ACK policy를 서로 독립된 축으로 정리합니다. [Pull consumers](https://docs.nats.io/learn/jetstream/pull-consumers), [Delivery and acknowledgment](https://docs.nats.io/learn/jetstream/delivery-and-acknowledgment)

### 원리와 내부동작

stream sequence는 저장된 메시지 위치, consumer sequence는 그 consumer의 전달 진행을 표현합니다. 재전달은 같은 stream 메시지에 새 전달 시도를 만들 수 있습니다. ACK floor는 단순히 가장 큰 ACK 번호가 아니므로 delivered와 floor의 간격만으로 유실 수를 계산하지 않습니다. filter가 있는 consumer에서는 stream sequence 사이에 원래 읽지 않는 메시지도 있습니다.

pull은 batch·expires·pending 요청·worker concurrency를, push는 deliver subject·수신자 상태·flow control/heartbeat 등 선택한 정책을 분석합니다. durable 이름의 존재와 consumer state의 저장/replication 방식은 별도로 확인합니다. ordered consumer는 일반 업무 worker의 explicit ACK consumer와 목적·제약이 다르므로 SDK별 구현을 따로 읽습니다.

가설 H7: “consumer를 늘리면 언제나 동일 작업이 분산되고, delivered와 ACK floor의 차이는 미처리 메시지 수다.”

### 실험

1. subject가 교차하는 메시지 1–8을 만들고 전체 stream 원장을 보관합니다. 전체 filter와 일부 filter의 consumer를 각각 생성해 stream/consumer sequence 대응표를 작성합니다.
2. 하나의 explicit-ACK durable pull consumer를 worker 둘이 공유하는 경우와 별도 durable 둘이 같은 stream을 읽는 경우를 비교합니다. 전자는 공유 전달 상태, 후자는 독립 진행이라는 가설을 ID 원장으로 검산합니다.
3. 작은 batch로 먼저 전달한 뒤 ACK 순서를 뒤집습니다. 미ACK 한 건을 남겨 delivered·ACK floor·pending 상태를 조회하고 최대 ACK 번호만으로 완료를 판정하는 잘못된 oracle과 비교합니다.
4. durable에 재연결하는 경우와 consumer를 삭제 후 같은 이름으로 재생성하는 경우를 분리합니다. 후자는 state continuity가 같은 작업이라고 가정하지 않습니다. 실험마다 새 전용 consumer만 생성·삭제합니다.
5. 빈 stream의 pull timeout, batch보다 적은 메시지, expires, worker 취소를 검사합니다. SDK가 빈 결과·예외·status를 어떻게 노출하는지 확인하고 정상적인 “현재 없음”과 권한/서버 오류를 한 예외 처리로 숨기지 않습니다.

독립 oracle: stream 원장과 consumer별 `{stream_seq, delivery_seq, attempt, ack_state}` 표입니다. consumer info 한 번만 읽는 것이 아니라 bounded polling 시점과 최종 정지 상태를 기록합니다. 두 consumer의 sequence를 하나의 global cursor로 합치지 않습니다.

실패 조건: filter 변경, 일부 ACK 누락, 같은 이름의 consumer 재생성, stale worker, pending pull 한계 초과, pull 취소 후 늦은 delivery. CPU 모형에 없는 durable lifecycle이나 heartbeat는 실제 실험 또는 설계 결과로 분리합니다.

소스 과제: `server/consumer.go`의 delivery selection·pending·ack floor 갱신과 consumer state 저장 경로를 찾습니다. client의 pull inbox/response status 정리 및 ordered consumer 재생성 경로를 비교하고, 관련 회귀 시험 하나를 실행합니다.

제출물·통과: 최소 8개 메시지의 두 sequence 대응표, 공유/독립 consumer 비교, 종료 후 남은 state, ACK floor 반례. durable을 “삭제·재생성해도 같은 처리 위치를 영원히 기억한다”로 설명하면 미통과입니다.

<a id="nt08"></a>
## NT08: ACK 정책이 아니라 commit 경계가 업무 중복을 결정한다

선수 조건: NT07, idempotent transaction, retry budget. ACK·NAK·in-progress·TERM의 의미를 분리합니다. timeout 기반 redelivery의 BackOff와 명시적 NAK delay는 다른 경로입니다. MaxAckPending은 전달 진행을 제한하며 MaxDeliver는 재전달 상한이지 자동 DLQ 이동 설정이 아닙니다. [ACK responses and redelivery](https://docs.nats.io/learn/jetstream/acknowledgment)

### 원리와 내부동작

`미전달→전달/pending→업무 처리→업무 commit→ACK 송신→서버 ACK 반영→확인 응답`을 그립니다. ACK 먼저 보내면 처리 전 crash 때 업무 누락이 생길 수 있고, commit 후 ACK 전에 crash하면 같은 메시지를 다시 처리할 수 있습니다. 두 시스템 사이의 이 간격은 publisher dedup이나 ACK 확인만으로 사라지지 않습니다.

explicit ACK를 기본 비교 대상으로 사용합니다. AckAll의 누적 범위, AckNone의 의미는 별도 실험으로 다루고 공유 worker에서 정책을 이름만 보고 바꾸지 않습니다. 늦은 ACK가 다른 worker의 재전달 이후 도착하는 경합도 업무 fence/원장 없이 안전하다고 가정하지 않습니다.

가설 H8: “확인 ACK를 쓰고 MaxDeliver를 설정하면 외부 DB는 정확히 한 번 갱신되고 실패 작업은 자동 격리된다.”

### 실험

1. [CPU `ack-redelivery`](../labs/offline.md)에서 ACK 누락·재전달·업무 dedup의 차이를 검산합니다. 가상 timer와 메모리 업무 원장을 실제 server/DB 내구성으로 일반화하지 않습니다.
2. 합성 ID 10건에 대해 ACK-before-work, work-before-ACK 두 잘못/불완전 설계의 crash 지점을 표로 만듭니다. 업무 commit 직후 종료와 ACK 응답 지연을 각각 독립 조건으로 사용합니다.
3. 실제 업무 DB 확장에서는 operation key의 unique constraint와 업무 변경을 같은 transaction에 묶고, 같은 key/다른 digest를 거부합니다. [PostgreSQL](../../../databases/postgresql/README.md)의 transaction/장애 실습과 연결하되 메모리 ledger 성공을 DB crash 검증으로 표시하지 않습니다.
4. AckWait보다 오래 처리하는 worker, bounded in-progress, 지연 NAK, BackOff를 각각 비교합니다. timer 경계의 delivery 횟수와 실제 업무 횟수를 분리하고 늦은 ACK 경합의 허용 결과를 먼저 적습니다.
5. MaxDeliver에 도달하는 poison 메시지를 만들고 advisory·consumer state·stream 내 존재를 확인합니다. 별도 quarantine/DLQ를 설계한다면 복사 확인→업무 격리 원장→ACK/TERM 처리 사이 장애와 중복을 검산합니다. TERM이 업무 성공이라는 표시가 되어서는 안 됩니다.

독립 oracle: 업무 ID별 최종 값·반영 횟수·digest, 각 delivery attempt와 ACK 관측 원장입니다. ACK가 확인된 메시지 수와 DB row 수만 같아서는 합격하지 않습니다. 누락 한 건+중복 한 건이 같은 count를 만들 수 있기 때문입니다.

실패 조건: commit 후 crash, ACK 유실, stale worker의 late ACK, 장시간 in-progress, 무한 NAK loop, redelivery 상한 도달, 격리 도중 crash. 테스트는 횟수·시간·payload 상한을 명시하고 운영 queue를 건드리지 않습니다.

소스 과제: `server/consumer.go`의 ACK 처리·pending timer·redelivery queue·MaxDeliver advisory와 client의 ACK confirmation 경로를 연결합니다. ACK floor, stream retention 삭제, 업무 원장을 각각 다른 상태 mutation으로 표시합니다.

제출물·통과: 최소 6개 crash 지점의 결과 표, late ACK 타임라인, poison 메시지 처리 ADR, 독립 업무 oracle. 검증 범위를 명시하지 않은 end-to-end exactly-once 주장 또는 “MaxDeliver=자동 DLQ”는 미통과입니다.
