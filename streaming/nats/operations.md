# NATS 운영 실습: pending·ACK·재전달·저장·quorum 진단

[트랙](README.md) · [공통 운영 계약](../../operations/README.md) · [장애 보고서](../../operations/incident-report-template.md)

고정 서버 2.15.0의 실제 상태를 관측하는 기본 실무 경로입니다. 원리 모형은 선택 부록이고 운영 gate의 대체물이 아닙니다. 기존 native runner의 10개 정확성 검사는 보존하되 모니터링·장애 회복을 검증한 것으로 확대하지 않습니다. 아래 실습은 신규 실행 결과가 아닌 수행 지침입니다.

## 1. 정상 baseline과 읽기 전용 진입점

[환경](environment.md)의 server/client 버전, process/cluster/account/stream/consumer 소유자와 topology, retention·replicas·consumer policy를 먼저 기록합니다. 준비된 소유 환경이 없으면 정제된 실제 상태 JSON·로그로 분석만 수행합니다. CLI는 별도 의존성이며 이 저장소의 Python runner가 설치하지 않습니다.

이미 소유한 단일 서버에 monitoring이 **loopback만** 바인딩되어 있을 때의 조회입니다. native runner는 짧게 실행·종료되므로 운영용 지속 관측 환경과 동일하지 않습니다. monitoring 포트는 기본 인증 경계가 없으므로 외부 bind를 추가하지 않습니다.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8222/varz'
Invoke-RestMethod 'http://127.0.0.1:8222/connz?limit=20'
Invoke-RestMethod 'http://127.0.0.1:8222/jsz'
Invoke-RestMethod 'http://127.0.0.1:8222/healthz'
```

인증된 학습용 CLI context가 **소유한 account/server**인지 먼저 확인하고 이름을 실제 소유 객체로 바꿔 조회합니다. context의 credential 원문을 보고서에 복사하지 않습니다. `info`는 publish·consume·ACK·purge 명령이 아닙니다.

```text
nats --context lab-owned stream info LAB_ORDERS --json
nats --context lab-owned consumer info LAB_ORDERS LAB_WORKER --json
```

CLI가 없으면 고정 SDK의 stream/consumer info API를 읽기 전용으로 호출합니다. `/jsz` 상세 account/stream/consumer 조회는 범위를 제한하고 pagination을 사용합니다. 대규모 전체 객체를 매 scrape마다 펼치지 않습니다. [monitoring endpoints](https://docs.nats.io/learn/monitoring/monitoring-endpoints), [NATS CLI](https://docs.nats.io/using-nats/nats-tools/nats_cli)

15초 간격·5분의 교육용 baseline에 server ID/시작 시각·stream/consumer 이름·관측 시각을 붙입니다. workload의 offered/accepted/업무 완료도 같은 창에 기록합니다. production 경보 기준은 처리 SLO와 정상 분포로 별도 결정합니다.

## 2. 지표 사전

| 신호 | 타입·단위 | 올바른 사용 |
| --- | --- | --- |
| ConsumerInfo `num_pending` | gauge, 아직 처음 전달되지 않은 대상 메시지 수 | consumer filter·시작 정책과 함께 해석; stream 전체 메시지 수가 아님 |
| `num_ack_pending` | gauge, 전달됐지만 ACK 미완료인 메시지 수 | MaxAckPending·처리 p95·ACK 오류를 대조; 이미 처리했으나 ACK 유실일 수도 있음 |
| `num_redelivered` | 현재 재전달 추적 상태의 gauge | **누적 재전달 횟수 counter가 아님. rate() 금지.** ACK 후 감소할 수 있음. 실제 재전달 이벤트율은 client delivery metadata로 별도 계측 |
| delivered / ack_floor | stream/consumer 두 sequence 좌표의 snapshot | 두 좌표를 혼합하거나 단순 차이를 전체 업무 미완료 건수로 취급하지 않음 |
| `/varz` connections / total_connections / slow_consumers | 현재 연결 gauge / 시작 이후 접속 counter / 서버 slow-consumer 감지 counter | counter는 동일 process의 reset-aware delta/seconds. SDK local pending 초과와 server slow consumer는 별도 |
| stream state messages / bytes | 보존된 메시지·bytes gauge | retention·max_age/max_bytes/max_msgs·discard와 비교. OS free disk·실제 file-store 점유는 별도 관측 |
| stream/consumer cluster leader·replica current/active/lag | 역할·복제 상태 snapshot; lag는 응답 스키마의 의미를 명시 | metadata/stream/consumer Raft 그룹을 구분. 특정 노드 healthz=200은 모든 그룹 quorum 증명이 아님 |

`num_redelivered`는 2.15.0 [consumer.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/consumer.go)의 `NumRedelivered: len(o.rdc)`와 ACK 처리 시 map 삭제를 기준으로 해석합니다. 특수 정책·버전 차이도 기록합니다. ACK 정책과 제한은 [Consumers](https://docs.nats.io/nats-concepts/jetstream/consumers), 상태 해석은 [JetStream health](https://docs.nats.io/learn/monitoring/jetstream-health)를 참고합니다. exporter 이름과 metric type은 실제 exposition으로 확인합니다.

## 3. 네 가지 장애 진단 카드

수동 opt-in 조건: 합성 전용 stream/consumer, 최대 100개·1 KiB 메시지, 최대 5분, 기존 설정과 소유 PID 기록, abort 담당자. 모니터링 데이터에도 subject·계정 정보가 있으므로 정제합니다. disk full, 공유 consumer purge/delete, 운영 ACK 누락, 무제한 부하를 금지합니다.

| 증상·제한 재현 | 경쟁 가설·검증 | 완화·원복 | 회복 판정 |
| --- | --- | --- | --- |
| `num_pending` 증가: 학습 worker에 bounded 처리 지연 | 입력 증가 / pull 요청 중단 / filter 오류 / MaxAckPending 포화. pending·ack_pending·num_waiting·client fetch/handler 로그·accepted 원장 대조 | 지연 제거, 원래 pull batch/concurrency 복원. ACK 완료 전에 강제 ACK하여 숫자를 낮추지 않음 | pending 추세 회복 + accepted ID가 업무 원장에 누락/중복 없이 반영 |
| 재전달과 중복 작업: 합성 메시지 하나의 ACK만 한 번 지연 | AckWait보다 긴 처리 / ACK 실패 / worker 재시작. delivery count·업무 commit·ACK 시각·consumer 설정 비교 | handler 회복·멱등 원장 확인 후 정상 ACK. AckWait 변경은 실제 tail 근거와 한 변수씩, 이후 원복 | gauge 감소뿐 아니라 같은 business ID 부작용 1회, ACK 대기·오류·tail 정상화 |
| slow-consumer 감지: 자체 client가 작은 bounded burst 동안 읽기를 잠시 지연 | SDK queue 포화 / server outbound backlog / reconnect / network. SDK callback·server slow_consumers delta·connz pending bytes·접속 수 대조 | burst 중단·읽기/drain 복구·원래 buffer 설정; 무조건 buffer 증대 금지 | 새 감지 이벤트 중단·연결 안정·JetStream replay 검산. Core에서 유실된 데이터는 자동 복원된다고 하지 않음 |
| publish timeout·저장 증가·replica 지연: 실제 용량 소진 대신 작은 fixture의 stream 한계만 선택 재현; quorum은 별도 다중 노드 | stream limit / disk·account 한도 / replica quorum / 잘못된 subject. PubAck 오류·stream config/state·그룹 leader·replica 상태 대조 | 부하 중단, 저장 정책의 예상 거절 확인; quorum 사건은 중단한 소유 노드만 복귀. timeout을 무조건 재전송하지 않음 | accepted·unknown outcome ID 확인, 새 publish/consume 성공과 저장량·replica 회복. R=1로 HA 통과 불가 |

MaxDeliver에 도달해도 자동 DLQ 이동으로 해석하지 않습니다. 처리 격리·재처리 담당자와 메시지/업무 원장을 별도 설계합니다. retention과 한도는 [Streams](https://docs.nats.io/nats-concepts/jetstream/streams), 복제는 [JetStream clustering](https://docs.nats.io/running-a-nats-service/configuration/clustering/jetstream_clustering)을 실제 설정과 대조합니다.

## 4. 모듈별 운영 증거

| 모듈 | 관측·진단 제출물 |
| --- | --- |
| NT01 | server info·연결·Core/JetStream·업무 완료 경계 |
| NT02 | subject/filter·subscription·권한과 실제 수신 원장 |
| NT03 | request timeout·no responder·queue worker 처리 원장 |
| NT04 | reconnect·SDK pending·server slow-consumer 시계열 |
| NT05 | retention config·messages/bytes·보존 집합 |
| NT06 | PubAck·duplicate·timeout별 accepted/unknown 원장 |
| NT07 | pending/ack_pending·delivered/ack_floor 좌표 |
| NT08 | delivery count·업무 commit·ACK·MaxDeliver 타임라인 |
| NT09 | metadata/stream/consumer 그룹별 leader/replica 상태 |
| NT10 | 복구 시각·보존 ID·consumer 상태·업무 ledger |
| NT11 | 합성 주체의 허용/거부와 관리 endpoint 접근 경계 |
| NT12 | 위 사건 2개·baseline·진단·원복·회복 evidence |
| NT13 | 관측 지표를 고정 source의 상태 map/자료구조와 연결 |
| NT14 | 한 개선의 실제 전후·두 사건·재현 보고서 |

운영 gate는 실제 baseline 1개, 다른 증상 2개, 경쟁 가설 검증, 완화/원복, 지표와 업무 결과의 회복을 요구합니다. 서버가 없는 경우 실측 자료 분석 gate와 실행 미완료를 구분합니다. CPU 모형·mock·native 정확성 테스트 개수만으로 운영 gate를 통과하지 않습니다.
