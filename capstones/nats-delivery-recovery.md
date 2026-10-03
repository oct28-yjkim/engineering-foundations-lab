# 선택 8주 연구: NATS 전달 경계와 업무 복구

[NATS 28주 트랙](../streaming/nats/README.md)의 NT14 2주 미니 연구와 **별도의 선택 8주·주 12시간·96시간** 프로젝트입니다. 둘을 같은 완료 기준으로 합산하지 않습니다. 학습자가 허가된 격리 환경과 애플리케이션을 구현하며, 이 문서는 완성된 production deployment를 제공하지 않습니다.

## 문제와 범위

합성 주문 또는 LLM 작업 요청을 처리하는 시스템을 설계합니다. Core NATS request/reply는 즉시 응답 경로, JetStream은 재시도 가능한 작업 보관 경로로 검토하되 둘이 반드시 필요한 것은 아닙니다. 업무 상태의 authoritative store는 선택한 PostgreSQL/MySQL 원장이며, browser/agent의 요청 성공·PubAck·delivery·business commit·consumer ACK를 별도 사건으로 기록합니다.

기본 데이터는 `operation_id`, `tenant_id`, `payload_hash`, `attempt`, `result_hash`, `business_status`입니다. 외부 모델/API·유료 cloud·실결제·실고객 데이터를 사용하지 않습니다. LLM 작업은 결정적 CPU 함수로 대체할 수 있고 GPU/API는 별도 승인한 확장입니다. [MCP 경계 연구](mcp-tool-boundary-recovery.md)와 연결할 때도 tool call ID와 업무 멱등성 key를 같다고 가정하지 않습니다.

## 연구 불변식

1. 동일 tenant·operation key·동일 payload의 성공 업무 effect는 최대 1개다. 같은 key·다른 payload는 조용히 성공 처리하지 않고 충돌을 보고한다.
2. publish 요청 수, PubAck 완료 수, stream 잔존 수, delivery attempt 수, business commit 수, ACK 확인 수는 각각 관측한다. 서로 같은 숫자일 필요가 없다.
3. 업무 commit 뒤 ACK 응답이 사라져 재전달되어도 DB 불변식이 유지된다. client timeout은 업무 미실행의 증거가 아니다.
4. 처리되지 않은 작업의 보존 계약은 stream 정책·limit·consumer lifecycle·backup 범위에 종속된다. MaxDeliver 도달을 자동 DLQ 보존으로 취급하지 않는다.
5. 다른 tenant는 PUB/SUB/reply/management API/업무 조회 어느 경로에서도 자산을 읽거나 변경하지 못한다. subject 이름만으로 권한을 보장하지 않는다.
6. 복원 시 stream/consumer/DB/idempotency 원장의 복구 시점을 대조한다. 한쪽 snapshot만 복원한 상황에서도 중복·누락을 탐지한다.

## 8주 계획

| 주 | 구현·실험 | 독립 제출물·통과 기준 |
| --- | --- | --- |
| 1 | 실패 모델, 업무 상태 machine, client/stream/DB 책임, 비용·보존 예산 확정 | ACK timeline·허용/금지 결과·재현 데이터·version manifest |
| 2 | 최소 producer/worker/DB 원장, outbox 또는 publish 복구 전략 | 정상 100건의 event/row/hash 교차검산; dual-write 실패 지점 명시 |
| 3 | dedup window 내부/외부, 다른 ID·같은 operation, key payload 충돌 | producer dedup와 DB unique/transaction의 역할 분리; effect 중복 0 |
| 4 | commit 전후 worker 종료, ACK/응답 유실, max pending·poison message | 재시도/격리/운영 재처리 정책과 손실 없는 증거; 자동 DLQ라고 오기하지 않음 |
| 5 | 선택 3-node JetStream, minority/majority loss, leader 전환 | 성공 응답 집합·복원 결과 대조. 1노드만 실행 시 HA 부분은 미검증 표시 |
| 6 | accounts·PUB/SUB/reply·management 제한, 제한적 API 호출 실패 | tenant A/B 허용·거부 matrix, secret 없는 관측 증거, 우회 경로 음성 대조군 |
| 7 | snapshot + DB backup, 새 독립 대상 restore, backlog 재개 | RPO/RTO 정의·실측, hash/row 차이·복구 지점 불일치 해결, 원본 무변경 |
| 8 | 동일 부하 반복, hot subject/느린 worker, Kafka 대안 리뷰 | 정확성 유지한 p95/p99·오류율·자원 사용; ADR·runbook·재현 명령·구술 방어 |

3-node는 세 failure domain을 자동 의미하지 않습니다. 노트북의 세 process/container 실험은 process/network-level 장애로만 보고합니다. 운영 클러스터나 실제 신원의 revoke/purge를 대상으로 하지 않습니다.

## 반드시 주입할 실패

`request accepted → outbox commit → publish → PubAck → delivery → business commit → ACK sent → ACK response`에서 최소 네 경계를 선택합니다. 같은 workload seed와 고정 key 집합으로 정상군·실패군을 비교합니다. 업무 효과를 만들기 전에 ACK하는 나쁜 대조군, 비영속 메모리 set만으로 idempotency를 구현한 대조군도 포함합니다. 대조군의 잘못된 설계를 운영용 코드로 채택하지 않습니다.

timeout과 강제 종료는 정확한 process/connection에만 적용하고 시작 전 종료·재기동·보존 계획을 작성합니다. evidence에 실제 credentials·개인정보·모델 원문을 기록하지 않습니다. failure injection의 적용 대상·기간·cleanup 소유권이 불명확하면 실행하지 않습니다.

## 최종 평가

정확성·업무 불변식 30, 장애/복구 증거 25, tenant/권한 15, 소스 연결·최소 반례 15, 재현성·운영 판단 15의 100점 rubric을 사용합니다. 85점 이상이면서 업무 effect 중복, 복구 후 미설명 누락, tenant 오허용, 민감 정보 커밋이 없어야 통과합니다. 단일 서버만 실행하고 quorum 검증을 완료했다고 쓰면 해당 영역은 미통과입니다.

최종 답변해야 할 질문은 “NATS가 빠른가?”가 아니라 **“어떤 실패까지 어떤 자산을 보존하고, 어떤 결과를 모를 때 어떻게 다시 판단하는가?”**입니다. [Kafka](../streaming/kafka/README.md)와 비교할 때 동일 payload·내구성·복제·ACK·소비 모델로 조건을 맞추고 일반적인 우열로 확대하지 않습니다.
