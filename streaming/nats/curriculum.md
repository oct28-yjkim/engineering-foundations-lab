# NATS 28주 심화 커리큘럼

14모듈 × 2주 × 주 12시간 = **336시간**입니다. 모듈당 원리·공식 자료 6시간, 실험 10시간, 소스 추적 4시간, 분석·구술 4시간을 권장합니다. 실제 cluster·인증 기반·별도 DB를 구축하는 시간은 추가입니다.

## 모듈 지도

기본은 [운영 가이드](operations.md)의 실제 baseline → pending/ACK/stream/접속 관측 → 장애 가설 → 완화·원복·업무 복구 → source 추적입니다. [모듈별 운영 증거](operations.md#4-모듈별-운영-증거)를 아래 원리 제출물과 함께 평가합니다. CPU 모형은 선택 부록이며 선수 조건·운영 수료 조건이 아닙니다. 모형 수계산 대신 실제 상태와 독립 업무 원장으로 같은 원리를 설명할 수 있습니다.

| 모듈 / 주 | 선수 조건 | 원리·내부동작의 질문 | 최소 제출물 |
| --- | --- | --- | --- |
| NT01 / 1–2 | TCP·프로세스·pub/sub | [Core·JetStream·프로토콜 경계](lessons/01-architecture-subjects.md#nt01) | wire/저장/업무 완료의 서로 다른 시점과 반례 |
| NT02 / 3–4 | 01, 집합·트리 | [subject·wildcard·interest routing](lessons/01-architecture-subjects.md#nt02) | 수작업 matching 표·다중 subscription·queue oracle |
| NT03 / 5–6 | 02, 비동기 처리 | [fan-out·queue·request/reply](lessons/02-delivery-clients.md#nt03) | 요청/응답/업무 원장·timeout의 불확실 결과 |
| NT04 / 7–8 | 03, TCP·버퍼·event loop | [framing·reconnect·drain·backpressure](lessons/02-delivery-clients.md#nt04) | 분할 입력·buffer 한계·slow consumer·종료 증거 |
| NT05 / 9–10 | 04, 파일·인덱스 | [stream·retention·file/memory store](lessons/03-streams-publishing.md#nt05) | 보관 집합·정책별 삭제 원인·disk 경계 |
| NT06 / 11–12 | 05, 재시도·트랜잭션 | [PubAck·dedup·기대 sequence](lessons/03-streams-publishing.md#nt06) | 유한 window·응답 유실·잘못 재사용한 ID 반례 |
| NT07 / 13–14 | 06, 상태 기계 | [pull/push·durable·consumer 상태](lessons/04-consumers-ack.md#nt07) | stream/consumer sequence·ACK floor·filter 비교 |
| NT08 / 15–16 | 07, 실패 모델 | [ACK·backoff·재전달·업무 원장](lessons/04-consumers-ack.md#nt08) | commit/ACK 사이 실패·MaxDeliver·격리 재처리 결과 |
| NT09 / 17–18 | 05–08, 합의 기초 | [Raft 그룹·quorum·토폴로지](lessons/05-raft-recovery.md#nt09) | 그룹별 leader/voter 지도·분할의 진행/거부 원장 |
| NT10 / 19–20 | 09, backup·RPO/RTO | [snapshot·restore·이전·복구](lessons/05-raft-recovery.md#nt10) | 원본과 분리한 복구·메시지/consumer/업무 검산 |
| NT11 / 21–22 | 02, TLS·인증·권한 | [accounts·NKeys/JWT·subject/API 권한](lessons/06-security-operations.md#nt11) | 주체×작업×subject 허용/거부·키 수명·노출 검사 |
| NT12 / 23–24 | 04–11, 통계·용량 | [관측·지연 분해·제한·운영](lessons/06-security-operations.md#nt12) | offered/accepted/completed 부하·오류율·tail·복구 SLO |
| NT13 / 25–26 | 01–12, source test | [KV·Object Store·소스·Kafka 비교](lessons/07-source-research.md#nt13) | 5symbol·2자료구조·1test·CAS/청크/보장 경계 |
| NT14 / 27–28 | 13, 앞선 fixture | [2주 최소 연구](lessons/07-source-research.md#nt14) | 한 경로·한 개선·실패 2개·독립 검산·재현 보고서 |

## 모든 모듈의 실험 계약

업무 질문 → 보장 대상 → 가설 → 불변식 → 실패 모델 → 수작업 oracle → baseline → 한 변인 변경 → 관측 → 경쟁 가설 → 소스 근거 → 한계 순으로 제출합니다. [공통 실험 방법](../../databases/shared/experiment-method.md)을 재사용합니다.

```text
run_id / server version+source revision / client version / OS / transport
account alias / subject / subscription or queue alias / stream / consumer
publish attempt / message ID / business operation key / payload digest
PubAck stream+sequence+duplicate / timeout or unknown-outcome reason
delivery stream sequence / consumer sequence / delivery count / ACK outcome
expected retained IDs / expected business IDs / observed IDs / mismatches
stream limits+retention / consumer policy / dedup window / timeout bounds
replica group / leader / voters / fault target / fault timing / recovery timing
offered+accepted+delivered+committed+acked counts / error+latency+resource use
source symbols / test commands / sanitized evidence / untested boundaries
```

publish ID, stream sequence, consumer sequence, 업무 operation key는 서로 다른 축입니다. count가 같아도 ID 집합·payload digest·중복 부작용이 다를 수 있으므로 독립 원장으로 확인합니다. 출력이나 로그에 실제 토큰·JWT credential·NKey seed·인증서 private key·업무 개인정보를 남기지 않습니다.

시간 경계는 CPU 가상 시각, client monotonic 시각, 서버 시각, 관측 시각을 구분합니다. ACK deadline 직전/직후의 실제 서버 실험에는 허용 오차와 반복 횟수를 명시합니다. CPU 모형의 정확한 등호 경계를 실제 scheduler의 정시 실행 보장으로 해석하지 않습니다.

## 버전과 소스 읽기

기준은 server **2.15.0**, Python client **2.16.0**입니다. [소스 지도](source-reading.md)의 고정 tag와 시험을 사용합니다. 공식 rolling 문서, 특정 릴리스 구현, 이 저장소의 CPU 추상화를 세 층으로 구분합니다. 최신 문서에 있는 필드가 해당 서버/SDK 조합에서 지원되는지 실제 설정 조회와 최소 재현으로 확인합니다.

모든 소스 과제는 진입점·상태 자료구조·mutation 시점·오류 경로·실제 시험을 제출합니다. 함수 이름을 나열하는 것으로 완료하지 않습니다. storage write, Raft commit, disk sync, publish response, consumer ACK, 업무 DB commit의 상대 순서를 그리되 관측하지 못한 순서는 미확인으로 남깁니다.

## 단계별 Gate

- G1, NT01–04: wildcard 경계·관심 등록·queue의 역할·timeout·reconnect·drain. Core queue를 durable queue로 보거나 `flush`를 subscriber 업무 완료로 해석하면 미통과입니다.
- G2, NT05–08: retention·PubAck·유한 dedup·consumer 상태·재전달. MaxDeliver를 자동 DLQ 이동으로 보거나 ACK와 외부 DB commit을 원자적이라고 설명하면 미통과입니다.
- G3, NT09–12: 그룹별 quorum·독립 복구·권한·관측. R=3을 backup으로 보거나 loopback 평문 fixture를 운영 보안 검증으로 표시하면 미통과입니다.
- G4, NT13–14: 소스·KV/Object Store·비교·반증. CPU 결과를 실제 처리량으로 쓰거나 한 구현/장애의 결과를 전체 NATS 보장으로 일반화하면 미통과입니다.

[평가표](assessment.md)의 정확성·원리/소스·실험/반증·운영/재현성은 각 25점입니다. **80/100 이상, 각 15/25 이상, 필수 gate 전체 통과**가 선언 범위의 완료 기준입니다. 기본 운영 gate는 실제 baseline 1개·서로 다른 증상 2개·진단/완화/원복·지표와 업무 결과의 회복입니다. OFFLINE만 수행하면 원리 보충만 완료이며 운영 트랙 수료가 아닙니다. 실제 서버·HA·복구·인증의 미검증 범위는 각각 남깁니다.

NT14의 2주 연구는 기존 자산으로 결론 하나를 검증합니다. 새로운 DB·다중 지역·새 언어 SDK·운영 PKI를 동시에 추가하지 않습니다. 넓은 운영 통합은 별도 [8주 캡스톤](../../capstones/nats-delivery-recovery.md)으로 분리합니다.
