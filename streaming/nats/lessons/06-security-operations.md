# 06. accounts·NKeys/JWT·권한·관측·용량·운영

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="nt11"></a>
## NT11: 인증된 연결에도 거부되어야 하는 작업이 있다

선수 조건: NT02, TLS, 인증/인가, 공개키 서명, 최소 권한. account 격리, 연결 인증, subject publish/subscribe 권한, JetStream API 권한, stream/consumer 제한을 서로 다른 경계로 설계합니다. [NATS Security Deep Dive](https://docs.nats.io/learn/security/)

### 원리와 내부동작

정적 user/password 또는 token, NKey challenge/response, operator/account/user JWT 기반 구성을 별도로 비교합니다. NKey public key, private seed, 서명된 JWT, credentials 파일을 같은 비밀로 취급하지 않습니다. 공개해도 되는 claim과 반드시 보호할 seed/private key를 식별합니다. 인증 성공은 특정 subject의 publish·subscribe·관리 API 사용을 모두 허용한다는 뜻이 아닙니다.

account import/export, service reply 권한, inbox namespace, wildcard allow/deny의 적용 지점을 분석합니다. 기능을 연결하기 위해 `>` 전체나 모든 JetStream API를 허용하는 설계의 범위를 계산합니다. leaf/gateway/route/client/monitoring endpoint의 인증과 TLS 요구가 같다고 가정하지 않습니다.

가설 H11: “TLS로 연결한 같은 조직 사용자라면 subscription 목록을 숨기는 것만으로 다른 tenant의 데이터도 보호된다.”

### 실험

1. SECURITY-OPS 전용 환경에 합성 account A/B와 publisher/worker/operator 역할만 만듭니다. 실제 조직 operator seed·SSO·NATS credential은 사용하지 않습니다. 기본 LOCAL-NATIVE의 loopback·임시 password·단일 신원 fixture를 이 실험의 tenant/운영 보안 증거로 쓰지 않습니다.
2. 실행 전에 주체×publish/subscribe/request/JetStream 관리×subject/account의 허용·거부 행렬을 작성합니다. 정상 한 건만 통과시키지 말고 다른 tenant subject, 넓은 wildcard, 관리 API, 임의 reply subject를 음성 대조군으로 추가합니다.
3. NKey/JWT 확장은 잘못된 서명, 만료, 잘못된 account 연결, revocation·갱신 시점의 재연결을 시험합니다. unsigned claim을 읽는 CPU predicate와 실제 verifier 결과를 구별합니다.
4. TLS 확장에서는 올바른 CA/이름·잘못된 CA/이름·만료 인증서의 기대 결과를 먼저 고정합니다. 실패를 없애기 위해 verification을 끄지 않습니다. 로컬 공개 예제 credential은 운영 credential로 재사용하지 않습니다.
5. account 간 import/export를 최소 한 방향으로 구성하고 반대 방향·다른 subject를 거부하는지 확인합니다. 원래 publish subject와 mapping 이후 subject 중 어느 지점에서 어떤 권한이 평가되는지 소스와 실제 결과로 답합니다.
6. 설정·로그·trace·진단 artifact에서 seed, password, credential 파일 내용이 노출되는지 검사합니다. 보관하는 증거는 alias와 공개 fingerprint 수준으로 제한합니다. 실제 secret 발급/회전 연구는 [OpenBao](../../../security/openbao/README.md) 또는 [Vault](../../../security/vault/README.md)와 별도 통합합니다.

독립 oracle: 연결 성공 여부가 아니라 각 주체의 명시적 접근 행렬입니다. 권한 거부 시 business handler가 실행되지 않았는지, 다른 account consumer가 데이터 payload를 받지 않았는지 독립 원장으로 확인합니다. “응답이 없었다” 하나만으로 권한 거부라고 판정하지 않습니다.

실패 조건: 과도한 wildcard, 잘못된 inbox 권한, management API 우회, 오래된 credential, 권한 축소 후 남은 연결, import/export 역방향 노출, 모니터링 endpoint 외부 노출. 모든 위협 실험은 소유한 격리 자산에 한정합니다.

소스 과제: `server/auth.go`, `server/accounts.go`와 client publish/subscribe permission 검사 경로를 추적합니다. `CONNECT` 인증 이후 각 operation의 권한 검사가 어디에서 다시 수행되는지 표시하고 deny 시험 하나를 실행합니다.

제출물·통과: 자산/주체/연결 경계, 최소 12칸의 허용·거부 행렬, rotation/취소 시점 원장, redaction 확인. loopback·subject naming·암호화 중 하나만으로 tenant authorization을 증명하면 미통과입니다.

<a id="nt12"></a>
## NT12: 가장 높은 처리량이 아니라 증명 가능한 운영 한계를 찾는다

선수 조건: NT04–11, 통계, latency percentile, capacity planning. 관측은 client·server·stream·consumer·업무 시스템에서 각각 수행합니다. 처리량 숫자에 어떤 완료 조건이 붙었는지가 benchmark의 핵심입니다. [Monitoring & Observability](https://docs.nats.io/learn/monitoring/)

### 원리와 내부동작

offered, client-accepted, PubAck-confirmed, delivered, business-committed, ACK-confirmed rate를 분리합니다. Core fire-and-forget과 file-backed R=3 JetStream의 숫자를 같은 의미로 비교하지 않습니다. payload byte 수, publish concurrency, batching, durability/replica 설정, TLS, consumer ACK 정책, error budget을 기록합니다.

client queue·server pending·stream bytes·consumer pending/redelivery·replica lag·CPU/RSS·disk/network를 연결합니다. 지연은 대기/전송/서버 수락/전달/업무/ACK 확인으로 분해합니다. 평균만 보지 않고 tail·오류·timeout·누락·backlog를 함께 평가합니다. 부하 생성기가 대기하느라 느린 요청을 아예 만들지 않는 coordinated omission도 검토합니다.

가설 H12: “publisher 처리량이 증가하고 CPU가 낮으면 시스템 여유 용량도 증가했다.”

### 실험

1. CPU 모형이 아닌 전용 실제 환경에서 짧은 baseline을 만듭니다. 메시지 수·최대 시간·최대 저장량·concurrency·중단 조건을 실행 전에 고정합니다. 장시간 무제한 benchmark를 기본 실습으로 사용하지 않습니다.
2. payload, batch, worker 수, AckWait 중 하나만 바꿉니다. 같은 retained/committed ID oracle을 유지하며 offered→committed 각 rate와 p50/p95/p99·오류율을 기록합니다.
3. 느린 downstream 또는 작은 MaxAckPending을 적용하고 publisher 수치와 backlog의 관계를 관측합니다. end-to-end latency가 커지는 동안 publisher 수치만 좋아진 경우를 찾아냅니다.
4. publish 재시도와 consumer redelivery가 동시에 생기는 제한된 장애에서 “유용한 업무 완료”와 “전송 시도”의 비율을 계산합니다. retry storm을 막는 budget/backoff와 경보 조건을 설계합니다.
5. monitoring·system event·advisory의 관측 권한과 외부 노출을 확인합니다. 전체 subject 목록·payload·tenant 이름을 무제한 metric label이나 로그에 넣지 않습니다. health green과 업무 backlog 정상 여부를 별도 경보로 둡니다.
6. 운영 runbook에 startup 검증, config 변경, client drain/lame duck, 저장량 경보, 재전달 폭증, quorum 상실, rollback을 넣습니다. 자동 remediation은 권한과 삭제 위험을 따로 승인받는 설계로 남깁니다.

독립 oracle: 사전에 정한 업무 ID 집합과 completion timestamp, 생성 예정 시각과 실제 전송 시각입니다. 관측 도구가 놓친 timeout을 percentile에서 제거하지 않습니다. 작은 표본의 p99는 불안정하므로 표본 수·반복 횟수·환경 변동·계측 overhead를 함께 보고합니다.

실패 조건: 부하 발생기 CPU 병목, client/서버 clock 차이, warm cache만 측정, 오류를 제외한 percentile, queue 무한 증가, 높은 metric cardinality, 운영 자격 증명이 섞인 trace. 불확실한 결과는 “성능 개선 미확인”으로 남깁니다.

소스 과제: `server/monitor.go`와 JetStream/consumer 상태·advisory 생성 경로를 추적합니다. 같은 지표 이름이 gauge/counter/누적 최대치 중 무엇인지 실제 구현으로 확인하고 restart에 따른 reset을 기록합니다.

제출물·통과: 재현 가능한 workload manifest, 완료 의미를 맞춘 비교표, 지연/오류/자원 분석, 중단 조건과 runbook. OFFLINE loop의 속도를 NATS 처리량이라고 보고하거나 오류를 버린 높은 throughput만 제출하면 미통과입니다.
