# 02. fan-out·queue·request/reply·client 수명과 backpressure

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="nt03"></a>
## NT03: 전달 패턴과 업무 실행 의미를 분리한다

선수 조건: NT02, callback, timeout, idempotency. pub/sub은 관심 있는 구독에 전달하고 queue group은 같은 그룹에서 메시지를 받을 멤버를 선택합니다. request/reply는 reply subject를 이용한 상호작용이지 분산 트랜잭션이 아닙니다. [Queue groups](https://docs.nats.io/concepts/queue-groups), [Request-Reply](https://docs.nats.io/concepts/request-reply)

### 원리와 내부동작

일반 fan-out, Core queue group, JetStream 공유 durable consumer를 세 가지로 비교합니다. queue group 자체에는 JetStream의 저장·ACK·redelivery 원장이 없습니다. request의 inbox 생성/구독, 요청 publish, 응답 상관, timeout 정리, 늦은 응답 처리를 client 구현에서 찾습니다. no responders를 감지할 수 있는 조건과 단순 응답 지연을 구분합니다.

가설 H3: “request가 timeout이면 responder의 업무도 실행되지 않았으므로 새 ID로 retry하면 안전하다.”

### 실험

1. 합성 주문 12개의 operation key·payload digest·원래 응답을 미리 정합니다. responder는 업무 반영 원장과 응답 송신 원장을 따로 작성합니다. 여기서 원장은 실험용이며 crash-durable DB의 대체물이 아닙니다.
2. 무응답자, 정상 응답자, 업무 반영 후 응답만 지연하는 응답자를 비교합니다. client가 보는 오류와 responder의 최종 업무 상태를 독립 확인합니다.
3. timeout retry를 새 operation key로 하는 잘못된 대조군과 같은 key로 하는 설계를 비교합니다. 같은 key에 다른 payload를 넣으면 조용히 이전 결과를 반환하지 않고 충돌로 처리하는 계약을 설계합니다.
4. worker 둘을 같은 queue에 넣고 한 worker를 처리 도중 종료합니다. Core queue의 자동 durable 재전달을 기대하지 않습니다. JetStream 확장은 NT07–08에서 같은 workload로 비교합니다.
5. 여러 responder가 있을 때 첫 reply만 사용하는 API와 여러 응답을 수집하는 별도 계약을 구분합니다. 종료된 inbox의 늦은 응답을 새로운 request의 성공으로 잘못 연결하지 않는지 확인합니다.

독립 oracle: client 요청 수가 아니라 operation key별 업무 반영 횟수·digest·최종 응답입니다. 정상 요청 12건의 기대 업무 집합과 retry 횟수를 분리합니다. no responders와 timeout의 정확한 SDK exception type은 고정 client에서 확인하고 이름을 추측하지 않습니다.

실패 조건: 처리 후 reply 유실, 중복 request, 지연 reply, responder 종료, 잘못된 reply subject 권한. 실제 DB가 없는 원장에서는 프로세스 재시작 후 중복 억제를 증명할 수 없다고 표시합니다.

소스 과제: Python client의 request multiplexer, inbox subscription, pending request 정리와 server의 queue delivery 선택 경로를 [소스 지도](../source-reading.md)에서 찾습니다. 두 request의 응답 순서를 바꾼 시험을 추가하고 correlation과 business idempotency를 서로 다른 symbol에 연결합니다.

제출물·통과: 요청/업무/응답의 세 원장, 실패 타임라인, retry ADR. “queue에서 한 worker를 골랐으니 업무가 정확히 한 번 완료됐다”는 설명은 미통과입니다.

<a id="nt04"></a>
## NT04: 빠른 client보다 경계가 명확한 client를 만든다

선수 조건: NT03, TCP framing, event loop, bounded queue. reconnect는 연결을 다시 맺는 기능이고, drain은 진행 중 작업과 송신을 정리하기 위한 절차입니다. 둘 다 모든 장애에서 부작용의 원자적 완료를 보장하지 않습니다. [Resilient clients](https://docs.nats.io/learn/resilient-clients/)

### 원리와 내부동작

read loop·parser·subscription pending queue·callback executor·write buffer·flusher·reconnect loop를 그립니다. `publish` 반환, socket write, PONG, callback 완료, `drain` 완료 시점을 분리합니다. client별 reconnect buffer와 subscription pending 한계는 기본값을 암기하지 말고 실제 설정·source·실행 결과를 기록합니다.

backpressure의 위치는 publisher, client outgoing buffer, server pending bytes, subscriber pending queue, worker concurrency, downstream DB pool로 나눕니다. 무제한 버퍼는 유실을 없애는 것이 아니라 장애를 메모리 고갈로 바꿀 수 있습니다. slow consumer는 client 측 관측과 server 측 연결 종료를 구별해야 합니다.

가설 H4: “reconnect buffer를 늘리면 유실과 지연 문제가 사라지고 drain은 언제나 끝난다.”

### 실험

1. 100개 이하 합성 메시지로 정상 baseline을 만들고 callback 지연 한 가지만 바꿉니다. offered/received/completed와 pending 메시지/byte 수를 같이 기록합니다.
2. client pending 한계를 작게 설정하고 slow consumer 경고·오류 callback·수신 ID 차이를 확인합니다. server slow consumer 실험은 별도 전용 서버에서 작은 자원 상한으로 수행하며 조직 broker에 부하를 보내지 않습니다.
3. 소유한 서버를 제한된 시간 중단했다가 다시 시작합니다. disconnect/reconnect callback, 재구독, buffer 수락/거부, 최종 ID 집합을 검사합니다. Core의 단절 구간을 JetStream replay처럼 설명하지 않습니다.
4. callback이 정상 완료하는 경우와 deadline을 넘기는 경우에 `drain`/종료를 비교합니다. 종료 예산을 미리 정하고, 강제 종료된 업무는 완료가 아니라 불확실/미완료로 남깁니다.
5. parser 시험에서는 header/body를 여러 chunk로 나누고 두 프레임을 합칩니다. invalid length와 과대 frame은 제한된 byte fixture로 검사합니다. 실제 서버를 crash시키는 무제한 fuzz는 기본 과정 범위가 아닙니다.

독립 oracle: 사전에 만든 ID 목록과 bounded worker 완료 원장입니다. rate 계산에는 wall time, 대기 시간, 오류/누락 수를 포함합니다. reconnect callback이 한 번 발생했다는 사실만으로 모든 message가 회복됐다고 판정하지 않습니다.

실패 조건: callback의 event loop 차단, 오래된 request reply, reconnect buffer 초과, drain timeout, 최대 payload 초과. 각 오류가 caller에게 전달되는지 또는 별도 error callback으로 나타나는지 기록합니다.

소스 과제: nats-py의 `_read_loop`, reconnect·flusher·subscription dispatch 관련 실제 symbol을 고정 tag에서 검색합니다. private symbol 이름은 API 계약이 아니므로 source revision과 함께 제출합니다. parser 시험 하나와 reconnect/drain 시험 하나를 직접 실행해 실패 경로를 설명합니다.

제출물·통과: buffer 소유권과 상한 지도, 정상/중단/종료 타임라인, ID 원장, 미완료 작업의 처리 정책. CPU 실행 결과를 실제 TCP fragmentation이나 reconnect 검증이라고 표시하면 미통과입니다.
