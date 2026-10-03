# NATS CPU 실험: 라우팅, 중복, 재전달, 보존 경계

[실습 시작점](README.md) · [트랙](../README.md) · [코드](offline_lab.py) · [테스트](test_offline_lab.py)

검토 기준일 **2026-10-04**. 이 코드는 NATS 서버·SDK·호환성 시험이 아니라, 서로 혼동하기 쉬운 네 가지 상태를 분리한 교육용 모델이다. Python 3.10+ 표준 라이브러리만 사용한다. 네트워크, 파일, 외부 프로세스, Docker, 클라우드, API key가 필요 없다. 실험의 논리 시간은 실행 시간이나 서버 성능과 무관하다.

트랙의 실제 엔진 기준은 nats-server **2.15.0**, Python SDK **nats-py 2.16.0**이다. CPU 모델이 이 버전의 전체 동작을 복제한다는 의미가 아니다. 공식 문서는 rolling이므로 [환경·버전 기준](../environment.md)과 고정 소스도 함께 읽는다.

## 실행과 독립적인 예상값

저장소 루트에서 실행한다. `python`은 실제 Python 3.10+ 실행 파일을 가리켜야 한다.

```powershell
python -B streaming/nats/labs/offline_lab.py --list
python -B streaming/nats/labs/offline_lab.py --lab all
python -B -m unittest discover -s streaming/nats/labs -p test_offline_lab.py -v
python -B -O -m unittest discover -s streaming/nats/labs -p test_offline_lab.py
```

기본 호출은 도움말만 출력한다. `--lab subject-routing`처럼 하나만 실행할 수도 있다. `-B`는 bytecode cache 생성도 막는다. 런타임 검증에 `assert`를 쓰지 않으므로 최적화 모드 `-O`에서도 입력 거부가 유지된다.

| 실험 | 손으로 계산할 핵심 oracle | 해석 |
| --- | --- | --- |
| `subject-routing` | 일반 구독 2개 + 서로 다른 queue group 2개 = 전달 대상 4개 | fan-out과 queue 내 선택을 구분한다 |
| `publish-dedup` | PubAck `(seq, duplicate)`가 `(1,false) → (1,true) → (2,false)` | 같은 ID도 유한 window 밖에서는 새 저장이 가능하다 |
| `ack-redelivery` | stream sequence `1 → 1 → 2`, consumer sequence `1 → 2 → 3` | 재전달도 새 delivery이며 새 stream record는 아니다 |
| `retention-gates` | 모두 ACK 후 Limits 1건 / Interest 0건, WorkQueue는 ACK와 age로 각각 삭제 | 처리 상태와 저장 수명은 다른 축이다 |

테스트의 리터럴 예상값은 구현 함수를 다시 호출해서 만들지 않는다. CLI 자체도 전체 출력이 손으로 계산한 독립 oracle와 같은지 타입까지 확인하고, 틀리면 성공 JSON 없이 종료 코드 1을 반환한다. `true`, `1`, `1.0`은 혼동하지 않는다. 결과 동일성, invalid-input 원자성, 경계 시간, immutable snapshot, 반례와 고의로 깨뜨린 CLI 결과를 확인한다. **95개 CPU 테스트**가 Python 3.12.14에서 일반·`-O` 모드 각각 통과했다. 실제 엔진 검증은 [별도 기록](validation.md)을 확인한다.

## 1. subject-routing: 어느 구독에 복사본이 가는가

`matches(pattern, subject)`는 token 단위로 판정한다. 발행 subject는 literal이고, `*`는 token 하나, 마지막 `>`는 하나 이상의 나머지 token을 받는다. 그래서 `orders.>`는 `orders.created`를 받지만 `orders` 자체는 받지 않는다. `orders` 문자열 prefix만 비교하면 틀린 결과가 나온다. [공식 subject 규칙](https://docs.nats.io/concepts/subjects)

`route(subject, members, turn)`의 모델 규칙:

1. matching 일반 구독마다 하나씩 전달 대상을 만든다. 동일 subject를 서로 다른 구독으로 두 번 구독하면 두 구독을 별개로 센다.
2. matching queue group마다 해당 group의 matching member 하나를 선택한다.
3. 출력은 이름 정렬이며, group 안에서는 `turn % matching_member_count`로 예시 member를 고른다.
4. matching 구독이 없으면 빈 tuple이다. 나중 구독을 위한 저장·재전송은 이 모델에 없다.

3번은 재현성을 위한 **모델의 선택 규칙**이다. 서버가 round-robin 공정성, 전역 순서, 균등 부하 또는 처리 성공을 보장한다는 뜻이 아니다. Core queue group은 JetStream consumer의 durable 상태와도 다르다.

### 반례 과제

- `orders.*`, `orders.>`, `orders.*.>`에 `orders`, `orders.us`, `orders.us.created`를 각각 대입하고 3×3 결과를 먼저 적는다.
- 같은 queue 이름을 가진 두 member 중 하나의 filter를 `payments.*`로 바꾼다. 선택 후보가 실제 matching member로 좁혀지는지 확인한다.
- 구독 전체를 queue group 하나로 묶은 결과와, audit 일반 구독을 남긴 결과를 비교한다. 업무 처리 copy와 감사 copy의 책임은 같은가?
- 출력의 `bad_control_zero_token_tail_would_match=true`는 의도적으로 잘못된 prefix matcher다. 정상 판정의 반례가 사라지면 검증이 약해진 것이다.

모델의 추가 제한: subject 256자·32 token, subscription 256개까지다. 빈 token, 공백·제어문자, wildcard가 섞인 literal token을 거부한다. 구독/queue 이름은 ASCII 영숫자·`_`·`-` 64자까지다. 이 제한을 서버 전체의 문법/최대값으로 인용하지 않는다. Unicode literal은 정규화하지 않는다. 계정·permission·route·leafnode·mapping·slow consumer·reconnect는 구현하지 않았다.

## 2. publish-dedup: ID window는 업무 영구 중복 방지가 아니다

`DedupPublisher(window=10)`는 stream 하나를 나타낸다. `publish(subject, payload, now, message_id)`는 저장 sequence와 duplicate 표시를 돌려준다. `Nats-Msg-Id`에 해당하는 ID는 해당 stream 전체에서 비교한다. window 안의 재발행은 기존 sequence를 돌려주고 새 body를 저장하지 않는다. header 없이 같은 body를 다시 보내면 새 메시지다. [공식 publishing과 PubAck](https://docs.nats.io/learn/jetstream/publishing)

이 모델의 시간 구간은 `[최초 수락 시각, 최초 수락 시각 + window)`이다. 시각 `0, 9, 10`에서 ID `id-1`을 보내면 sequence는 `1, 1, 2`다. duplicate 호출이 최초 수락 시각을 갱신하지 않는다. 이것은 경계를 선명하게 만들기 위한 정수 시간 모델이다. 실제 서버의 timer 정밀도, 정리 시점, concurrent publish, 저장 실패, 기대 sequence 조건, restart 시 복구는 별도 실험 대상이다.

두 번째 호출에서 body를 `changed-body`로 바꿔도 기존 `order-1`이 남는다. ID 충돌은 payload 비교 오류로 친절하게 드러나지 않을 수 있다. producer는 동일 ID가 동일 의도를 뜻하도록 설계해야 한다. 이 모델은 저장 제한 없이 모든 nonduplicate publish가 성공했다고 가정하며, PubAck 유실 자체를 구현하지는 않는다.

### 업무 효과와 비교

`BusinessCounter.apply(tenant, key, intent)`는 **별도의** 합성 업무 저장소다. tenant+business key를 기준으로 효과와 기록을 원자적으로 반영한다고 가정한다. 같은 의도면 재호출 효과가 없고, 다른 의도로 key를 재사용하면 거부한다. 이는 원자성이 구현되었다는 증거가 아니라, 데이터베이스 실험에서 검증해야 할 가정이다.

시각 10 이후 stream에 저장된 두 메시지에 단순 counter를 적용하면 효과가 2회다. 업무 key를 적용하면 1회다. 이 차이를 PubAck나 consumer ACK가 대신 해결하지 않는다. 반대로 publisher에서 중복으로 버린 변경 body는 업무 저장소까지 도착하지 않으므로 그 충돌을 이 counter가 검출해 주지도 않는다.

### 반례 과제

1. window를 1로 줄이고, 재시도 ID를 매번 새로 만들고, ID를 아예 생략하는 세 변형을 비교한다.
2. 동일 ID를 같은 stream의 서로 다른 subject에 보낸다. 업무 영역별 ID namespace가 필요한 이유를 설명한다.
3. 같은 business key를 다른 tenant에서 사용한다. 독립 업무가 잘못 억제되지 않아야 한다.
4. 효과 적용 후 key 기록 전에 crash하는 실제 저장소 구현을 설계한다. 이 CPU 모델은 그 crash를 구현하지 않았으므로 DB transaction/outbox/inbox가 별도로 필요한 이유를 적는다.

payload는 최대 4096바이트의 immutable `bytes`이며 빈 payload도 허용한다. ID의 64자 ASCII 제한은 모델 전용이다. hash, 재전송 backoff, external transaction, publisher failover, 무한 기간 dedup을 구현하지 않는다.

## 3. ack-redelivery: delivery 수와 업무 완료 수가 다르다

`ConsumerLedger`는 고정된 stream sequence 목록에 대해 explicit ACK와 한 번에 한 건의 pull만 모델링한다. `Delivery`에는 `stream_sequence`, `consumer_sequence`, `attempt`, `deadline` 네 값이 있다. 같은 stream message를 다시 전송해도 consumer delivery sequence는 증가한다.

이 모델에서 `MaxAckPending`은 미완료 메시지 수의 상한이고, 이미 pending인 메시지의 재전달은 별도 새 slot을 쓰지 않는다. `now >= deadline`이면 재전달 후보다. `MaxDeliver`를 소진한 항목은 다음 `pull()`의 timer 처리에서 exhausted로 분류되며 stream 목록은 그대로다. 자동 DLQ도 없다. [ACK·재전달 제어](https://docs.nats.io/learn/jetstream/acknowledgment)

| 논리 시각 | 조작 | 관찰 |
| --- | --- | --- |
| 0 | 첫 pull | stream 1 / consumer 1 / attempt 1 / deadline 5 |
| 1 | 다시 pull | `max_pending=1`이므로 새 stream 2 전달 중지 |
| 5 | 다시 pull | stream 1 / consumer 2 / attempt 2 |
| 6 | 첫 attempt의 늦은 ACK 후 pull | stream 1 pending 해제, stream 2 / consumer 3 |
| 11 | stream 2 ACK 없이 pull | stream 2 재전달 |
| 16 | 또 ACK 없이 pull | stream 2 exhausted, stream 저장 목록은 `(1,2)` |

늦은 ACK를 받았더라도 이미 dispatch된 두 번째 worker의 업무 효과가 취소되는 것은 아니다. 예제의 같은 주문 효과는 단순 구현이면 2회, 가정된 atomic business key 저장소를 쓰면 1회다.

### AckFloor로 가장하지 않는 이유

`settled_prefix`는 주어진 stream sequence 목록을 앞에서부터 훑다가 최초 미ACK 메시지 직전까지의 마지막 sequence를 돌려주는 **교육용 값**이다. 입력이 `(10,20)`이고 20만 ACK하면 0, 둘 다 ACK하면 20이다. 이는 서버의 `AckFloor`가 아니다. 실제 `AckFloor`는 consumer/stream sequence pair이며 필터, 삭제, 재전달, pending 및 서버 구현 경로를 함께 읽어야 한다. CPU 출력 이름에도 `not_server_ack_floor`를 넣었다.

### 좁게 고정한 상태 전이

- 시계는 감소하지 않는 정수다. 대기 thread나 sleep이 없고 `pull()`에서만 만료 처리를 한다.
- 여러 재전달 후보 중 작은 stream sequence를 먼저 고른다. 서버 scheduling 계약이 아니다.
- ACK는 이 모델에서 발급된 **consumer delivery sequence**로 요청한다. 오래된 attempt의 ACK도 같은 메시지를 완료할 수 있게 모델링하며 exhausted 상태에서도 수락한다. 이를 모든 실제 race에서의 성공 보장으로 해석하지 않는다.
- `backoff=(2,7)`이면 timeout 대기는 `2,7,7,…`이며 `ack_wait`를 대체한다. NAK는 구현하지 않았으므로 timeout BackOff를 NAK 지연으로 읽지 않는다.
- stream sequence는 양의 정수·오름차순·중복 없음이며 gap은 허용한다. 입력 최대 4096개다. 이 모델의 pending/delivery 설정은 양수만 허용한다. 실제 서버의 `-1` 등 unlimited sentinel은 지원하지 않는다.

### 반례 과제

1. 두 메시지를 동시에 전달한 뒤 두 번째를 먼저 ACK한다. `settled_prefix`가 먼저 이동하면 안 된다.
2. `max_deliver=1`로 낮춘다. 업무 미완료 항목이 stream에서 사라지거나 성공 처리된 것으로 분류되면 안 된다.
3. ACK 유실 대신 업무 실패를 주입했을 때 같은 재시도 전략이 안전한지 구분한다.
4. 실제 서버에서 `AckFloor` pair, pending, redelivery count를 수집하고 모델과 다른 값을 기록한다. 차이를 숨기지 말고 누락된 상태를 설명한다.

AckAll/AckNone, NAK/TERM/progress ACK, 여러 worker의 실제 race, push flow control, pull expiry, consumer 삭제·재생성, filter, ack persistence, Raft는 제외했다. 이 코드를 SDK 대체물이나 SLO 측정기로 쓰지 않는다.

## 4. retention-gates: ACK와 stream 보존을 별도로 판정한다

`RetentionStore`는 시작할 때 consumer 이름/filter를 고정하고 `publish → deliver → ack`의 증거를 따로 기록한다. `deliver()`는 이 메시지가 해당 consumer에 전달되었다는 가정된 사건이지 SDK pull이나 처리 성공이 아니다. Core queue group을 이 consumer 목록에 넣으면 거부한다.

| 정책 | 모델의 ACK 삭제 조건 | ACK가 없을 때 |
| --- | --- | --- |
| `limits` | ACK로 삭제하지 않음 | MaxAge 또는 MaxMsgs/DiscardOld까지 유지 |
| `interest` | matching consumer가 모두 ACK하면 삭제; matching consumer가 0이면 즉시 제거 | 한 consumer라도 미완료면 남지만 limit이 우선할 수 있음 |
| `workqueue` | 해당 메시지를 담당하는 consumer의 ACK로 삭제 | consumer가 아직 없어도 저장; limit은 여전히 적용 |

이는 static consumer 집합과 단순 저장 제한에 대한 모델이다. WorkQueue consumer filter의 교집합은 허용하지 않으며, 여러 worker가 consumer 하나를 공유하는 것과 여러 독립 consumer를 만드는 것을 구분한다. [공식 retention 정책](https://docs.nats.io/learn/jetstream/retention-policies)

모든 정책에 `max_age`와 `max_messages`를 적용한다. `DiscardOld`만 구현하므로 미ACK여도 오래된 메시지를 제거할 수 있다. `max_age=5`일 때 시각 0의 메시지는 시각 5의 `advance()`에서 제거한다. publish도 먼저 age 처리를 한 뒤 새 메시지를 넣고 count를 제한한다. 이 순서를 테스트의 독립 oracle로 고정했다.

### 반례 과제

1. Interest에서 audit consumer만 ACK를 멈춘다. 다른 consumer가 모두 끝났어도 저장이 남는지 확인한다.
2. consumer 없는 Interest와 WorkQueue에 각각 발행한다. 같은 0 consumer가 정반대 보존 결과를 만드는 이유를 설명한다.
3. 모든 정책에서 `max_messages=1`로 놓고 미ACK 두 건을 발행한다. 첫 메시지 손실이 ACK 완료를 의미하지 않는다는 것을 삭제 reason으로 증명한다.
4. `max_age` 경계에서 ACK한다. 이미 limit으로 지워진 record를 ACK가 되살리지 않아야 한다.
5. 동일 subject에 WorkQueue consumer 두 개를 만들려는 설계를 고쳐라. worker pool과 consumer filter 분할 중 업무 요구에 맞는 것을 선택한다.

실제 소비 진행 상태는 앞의 `ConsumerLedger`와 자동 연결하지 않았다. 따라서 이 모델의 repeated `deliver()`를 실제 consumer가 ACK된 메시지를 다시 전달한다는 증거로 사용하면 안 된다. consumer 동적 생성·삭제, retention 변경, MaxBytes/MaxMsgsPerSubject, DiscardNew, purge, mirror/source, per-message TTL, rollup, 실제 파일 회수 시점은 제외했다. 삭제 이력은 관찰용 메모리에 남으며 실제 저장 압축이나 공간 회수를 흉내 내지 않는다.

## 입력 경계와 제출 기준

숫자 인자는 bool, float, NaN/Infinity, 문자열을 정수로 암묵 변환하지 않는다. collection과 ID를 검증한 뒤 hash/sort하므로 `[]`나 `{}`를 잘못 넣어도 의미 없는 TypeError 대신 `ModelError`로 거부한다. 잘못된 입력은 clock/record를 먼저 변경하지 않아야 한다. public snapshot은 tuple과 frozen dataclass다. 이 검증을 보안 인증이나 tenant ACL이라고 주장하지 않는다.

각 실험 제출물은 다음 다섯 가지를 포함한다.

1. 실행 전 직접 계산한 oracle와 선택한 논리 시각.
2. 정상 trace와 의도적인 bad control 하나.
3. stream 저장, consumer 전달, 업무 효과를 서로 다른 counter로 센 결과.
4. 이 모델이 보장하지 않는 것 세 가지와 실제 엔진에서 검증할 가설.
5. 재전달/보존 실패가 발생했을 때 탐지 신호와 업무 복구 방법.

CPU 통과는 원리 검증이다. 실제 wire 형식, 인증, 영속성, 장애 복구, throughput, quorum, 운영 readiness의 증명은 아니다.
