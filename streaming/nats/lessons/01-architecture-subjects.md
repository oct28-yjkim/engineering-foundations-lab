# 01. 아키텍처·wire protocol·subject·interest routing

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="nt01"></a>
## NT01: 메시지를 보냈다는 말의 여러 의미

선수 조건: TCP byte stream, process memory, 비동기 callback, pub/sub. Core NATS의 관심 기반 전달과 JetStream의 저장·consumer 상태를 같은 동작으로 취급하지 않습니다. 과거 STAN의 별도 서버·client 동작은 이 과정의 JetStream 구현 근거가 아닙니다. [Core NATS 개념](https://docs.nats.io/learn/core-nats/), [JetStream 개념](https://docs.nats.io/concepts/jetstream)

### 원리와 내부동작

한 publish의 경로를 application→SDK buffer→socket→server parser→account/subject routing→subscription→callback으로 나눕니다. JetStream에서는 여기에 stream 수락·저장·replication·PubAck와 별도의 consumer 전달 상태가 추가됩니다. callback 시작은 업무 commit이 아닙니다. TCP 연결 성공은 subscription interest가 모든 필요한 경로에 반영됐다는 증거가 아닙니다.

wire protocol에서는 `INFO`, `CONNECT`, `PING/PONG`, `SUB/UNSUB`, `PUB/MSG`, header가 있는 `HPUB/HMSG`를 분리합니다. payload는 선언된 byte 길이로 해석하므로 payload 속 줄바꿈을 명령 구분자로 사용하는 parser는 잘못입니다. TCP 한 번의 read와 NATS 메시지 하나는 일대일 관계가 아닙니다. [공식 client protocol](https://docs.nats.io/reference/protocols/client)

### 가설과 실험

가설 H1: “SDK publish가 예외 없이 끝나면 구독자의 업무 처리도 끝났다.” 이 가설을 반증하는 것이 목표입니다.

1. 20개의 합성 ID를 미리 만든 뒤 송신 시도·publish 반환·수신 callback·업무 완료를 별도 목록에 적습니다. Core subscriber가 없는 경우와 등록 후 동기화한 경우를 비교합니다.
2. subscriber callback에 제한된 지연을 넣고 publish 반환과 `flush` 반환 시점의 업무 완료 목록을 비교합니다. 동기화 신호가 어느 연결까지 확인했는지 적습니다.
3. 같은 업무 ID를 JetStream에 publish하고 PubAck의 stream/sequence와 독립 consumer가 읽은 payload digest를 비교합니다. Core publish 경로와 JetStream publish API의 응답 계약을 구별합니다.
4. 종료·응답 유실을 주입할 때는 소유한 전용 프로세스만 사용합니다. 정확한 유실 시점 제어 장치가 없다면 timeout 관측을 “서버가 저장하지 않았다”는 증거로 바꾸지 않습니다.

독립 oracle: 실행 전에 만든 ID→digest 표와 별도의 완료 원장입니다. server의 메시지 수와 SDK 성공 횟수만 서로 비교하면 같은 누락을 놓칠 수 있습니다. 기대값에는 “수신되지 않아도 Core 계약 위반이 아님”과 “업무 미완료”를 따로 표시합니다.

실패 조건: subscriber 준비 전 발행, callback 예외, client buffer에만 남은 publish, reply 유실. CPU 모형은 실제 framing이나 socket을 검증하지 않으므로 이 실험을 OFFLINE 완료에 포함하지 않습니다.

소스 과제: 고정 tag의 `server/parser.go`에서 명령/길이/본문 상태 전이를 찾고 `server/client.go`의 처리 경로와 연결합니다. Python client의 parser와 callback dispatch를 [소스 지도](../source-reading.md)에서 대조합니다. 1byte씩 나눈 프레임과 여러 메시지를 한 read로 합친 경우를 기존 시험 또는 별도 회귀 시험으로 확인합니다.

제출물·통과: 각 시점의 의미·실패 가능성 표, ID 원장, 실제 프레임 한 개의 byte 길이 계산, parser 상태도. `flush`를 disk sync 또는 모든 subscriber 처리 완료라고 부르면 미통과입니다.

<a id="nt02"></a>
## NT02: subject namespace를 라우팅·권한·관측의 계약으로 설계한다

선수 조건: NT01, 집합, 트리, 문자열 tokenization. subject는 case-sensitive token 경로입니다. `*`는 정확히 한 token, 마지막 `>`는 한 개 이상을 매치합니다. publish에는 구체적 subject를 사용합니다. [공식 subjects](https://docs.nats.io/concepts/subjects)

### 원리와 내부동작

subscription matching 결과와 권한 허용 결과는 다른 계산입니다. 같은 이름이라도 account 경계가 다를 수 있습니다. 여러 matching subscription은 하나의 business operation과 같지 않고, queue group 이름은 저장 위치나 partition 번호가 아닙니다. namespace를 팀 이름만으로 설계하지 말고 tenant·업무 domain·event type·version·민감도·cardinality를 검토합니다.

server의 subject 자료구조에서 token별 탐색, wildcard 경로, matching 결과의 일반 subscription/queue 구분, 캐시 무효화 지점을 찾습니다. 전체 subject 문자열을 전수 검색한다고 가정하거나 특정 trie 구조를 모든 버전의 영구 계약으로 설명하지 않습니다.

### 가설과 실험

가설 H2: “`orders.>`는 `orders`까지 포함하며 wildcard를 늘려도 의미와 비용은 같다.”

1. `orders`, `orders.eu`, `orders.eu.created`, `orders.us.created`, `Orders.eu.created`를 고정 입력으로 만들고 `orders.*`, `orders.>`, `orders.*.created`, `>`의 기대 매칭 집합을 손으로 계산합니다. 예를 들어 `orders.*`는 이 목록에서 `orders.eu` 하나만 포함합니다.
2. 실제 subscription ID별 수신 원장을 기대 집합과 비교합니다. 선택 보충인 [원리 모형 `subject-routing`](../labs/offline.md)은 필요할 때만 사용하며 필수 실행이 아닙니다. 같은 client의 서로 다른 matching subscription을 임의로 한 개로 합치지 않습니다.
3. 실제 서버 추가 실험에서는 동일 pattern의 일반 subscriber 둘, 같은 queue의 worker 둘, 다른 queue의 worker 하나를 구분합니다. 일반 subscription별 수신과 queue별 총수의 oracle을 별도로 만듭니다. worker별 완전한 균등 분배는 합격 조건이 아닙니다.
4. namespace 변경에서 old/new subject를 동시에 구독하는 기간을 설계합니다. 한 업무 event를 두 subject로 발행하는 migration이 업무 중복을 만드는지 별도 operation key로 확인합니다.

독립 oracle: 서버/모형 matcher를 다시 호출하지 않는 수작업 truth table입니다. 구독 규칙 4개×subject 5개에 대해 expected match를 먼저 고정합니다. queue 실험은 전체 ID 집합과 queue별 전달 선택을 검사하되 장애 중 재발행/업무 재시도까지 한 번이라고 가정하지 않습니다.

실패 조건: 잘못된 중간 `>`, 비어 있는 token, publish wildcard, 대소문자 변경, subscription 등록/해제 시점의 경합. fixture의 보수적 입력 제한과 서버가 허용하는 전체 subject 문법을 구분합니다.

소스 과제: `server/sublist.go`의 insert/match/remove와 관련 시험을 추적합니다. subscription 변경 후 cache를 언제 무효화하는지 확인하고, 매우 넓은 wildcard와 높은 cardinality의 메모리 비용을 측정하는 별도 상한 실험을 설계합니다.

제출물·통과: 20칸 이상의 독립 truth table, namespace ADR, matching/authorization 분리도, queue별 ID 원장. “subject=Kafka partition”, “넓은 wildcard=권한 허용”이라는 설명은 미통과입니다.
