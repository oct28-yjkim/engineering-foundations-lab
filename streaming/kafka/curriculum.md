# Kafka 28주 심화 커리큘럼

## 기본 실무 학습 경로

모든 모듈은 [운영 가이드](operations.md)의 **실제 정상 baseline → 지표·로그 관측 → 증상별 경쟁 가설 → 제한 재현 → 완화·원복·업무 복구 → 원리·소스 설명** 순서를 적용합니다. 28주·14모듈의 원리 깊이는 유지하며 [모듈별 운영 증거](operations.md#4-모듈별-운영-증거)를 기존 제출물에 함께 요구합니다. 알고리즘 모형은 선택 보충 자료이며 실제 broker/consumer 관측을 대체하지 않습니다.

운영 gate는 실제 baseline 1개와 다른 증상 2개의 진단·복구 증거입니다. 단일 노드에서 가능한 사건과 RF=3/controller quorum 등 별도 환경 사건을 구분하며, 미실행은 설계 또는 자료 분석으로만 기록합니다.

## 학습 운영

14개 모듈 × 2주 × 주 12시간, 약 336시간이 기준입니다. SQL/DB 두 트랙과 병렬 또는 순차로 진행할 수 있지만 공통 기반과 같은 보고서를 중복 이수할 필요는 없습니다. 일정은 예상치이며 module gate를 통과하지 못하면 실험·보충 시간을 늘립니다.

두 주의 24시간을 원리·공식 문서 6시간, 실험·Java 구현 10시간, 소스 추적 4시간, 결과·구술 4시간으로 배분합니다. Java가 처음이면 collection, exception, Future/callback, thread ownership, resource lifecycle을 별도로 보충합니다. Docker·셸·TCP, 파일과 page cache, 확률·백분위·장애 모델도 선수 지식입니다.

## 전체 경로

| 모듈 / 주 | 선수 조건 | 핵심 질문·실험 | 산출물과 통과 조건 |
| --- | --- | --- | --- |
| K01 / 1–2 | 없음; 셸 보충 | [로그와 partition](lessons/01-log-storage.md#k01-이벤트와-partition의-계약-local): 어떤 순서를 보장하는가? | 12개 event 원장, key/partition/offset 대조; 전역 순서 반례 |
| K02 / 3–4 | K01, 파일·배열 | [segment·index·retention](lessons/01-log-storage.md#k02-segment-index-retention-compaction-local-build) | segment 경계와 크기/논리 offset 구별, retention/compaction 비동기 증거 |
| K03 / 5–6 | K02, Java Future | [producer 경로](lessons/02-producer-replication.md#k03-producer-buffer부터-ack까지-local-build) | callback 원장, batch/linger 3조건, retries/timeout 분류 |
| K04 / 7–8 | K03, 장애 모델 | [복제·ISR·ELR](lessons/02-producer-replication.md#k04-복제-가시성과-리더-전환-cluster-design) | RF3/minISR2의 4개 장애와 ACK 대조; 단일 노드는 미검증 표시 |
| K05 / 9–10 | K03, 처리 상태 | [consumer position·commit](lessons/03-consumer-groups.md#k05-poll-처리-완료-offset-commit-local-build) | 처리/commit 사이 crash 3조건, 누락·중복 검출 |
| K06 / 11–12 | K05, coordination | [group와 rebalance](lessons/03-consumer-groups.md#k06-classic과-consumer-group-protocol-local-build) | 3partition/1·2·4consumer, ownership timeline, 두 protocol 비교 |
| K07 / 13–14 | K05–K06 | [전달 의미](lessons/04-transactions.md#k07-idempotence와-업무-멱등성-build) | producer retry와 앱 재전송 분리; DB side effect 중복 반례 |
| K08 / 15–16 | K07, atomicity | [transaction·LSO](lessons/04-transactions.md#k08-kafka-transaction과-read_committed-build) | commit/abort/open/fencing 4조건, read_committed oracle, offset 원자성 |
| K09 / 17–18 | K04, quorum | [KRaft metadata](lessons/05-kraft-operations.md#k09-kraft는-어떤-상태에-합의하는가-local-cluster-design) | metadata와 data plane 구분, controller 1/2개 장애 증거 |
| K10 / 19–20 | K08–K09 | [운영·보안·복구](lessons/05-kraft-operations.md#k10-관측-보안-용량과-복구-cluster-design) | SLO·disk·권한·재해복구 검증, RPO/RTO 실측 |
| K11 / 21–22 | K08, 집계·시간 | [Streams](lessons/06-streams-connect.md#k11-streams의-시간-state-store와-복구-build) | event-time oracle, grace/late event, state 복원, topology 테스트 |
| K12 / 23–24 | K10–K11, PG WAL | [Connect·CDC](lessons/06-streams-connect.md#k12-connect-cdc와-외부-sink의-경계-integration-design) | snapshot/stream 경계, task retry, source/sink offset·commit 대조 |
| K13 / 25–26 | K01–K12, Java 내부 | [최소 재현과 source](lessons/07-research-capstone.md#k13-현상에서-내부-구현까지-build) | 5symbol·2자료구조·오류 경계 trace, 회귀/teaching 구현 |
| K14 / 27–28 | K13; DB 지식은 선택 | [최소 시스템과 통합 설계](lessons/07-research-capstone.md#k14-최소-시스템과-통합-설계-build-integration-design) | Kafka 최소 슬라이스·실패 2종·설계 구술; 전체 DB 통합은 후속 8주 |

## 측정과 증거

[공통 측정 규칙](../../databases/shared/experiment-method.md)을 Kafka에 적용합니다. producer enqueue, callback ACK, broker append/replication, consumer fetch, handler 완료, DB commit 시각을 분리합니다. 여러 host의 시계 차이를 알지 못하면 wall-clock만으로 밀리초 인과를 단정하지 않습니다. client가 실제로 보낸 payload와 stable event_id를 보존합니다.

성능 탐색은 짧게 수행할 수 있지만 최종 비교는 warm-up 후 조건별 20회 이상의 구간 측정으로 시작합니다. tail SLO는 최소 1,000개 이상 요청 표본과 충분한 지속 부하를 별도 설계하고, 개수만으로 p99 신뢰성을 보장하지 않습니다. payload 크기·compression·key skew·partition 수·replication·client version·cache·JVM warm-up을 함께 기록합니다. 루프에서 `send().get()`를 매번 호출해 만든 직렬 부하와 비동기 다중 in-flight 부하는 다른 실험입니다.

Kafka 원장은 다음 구조를 권장합니다.

```text
run_id / event_id / business_key / source_version / expected_operation
producer_client_id / attempt / enqueue_time / callback_result
topic / partition / offset / producer 또는 transaction 식별 범위
consumer_group / member / poll_time / process_result / committed_next_offset
sink_commit_id / sink_state / 확인된 오류 / 재처리 여부
```

secret·credential을 원장에 남기지 않습니다. topic-partition-offset은 Kafka 안의 위치이고 업무 ID는 다시 발행되어도 유지할 수 있는 정체성입니다. 두 값을 모두 보존해야 재전송과 replay를 구별할 수 있습니다.

## 단계별 gate

- G1, K01–K04: 로그·저장·적재·복제. byte offset/record offset, ACK/복제, ISR/controller quorum 구분.
- G2, K05–K08: 처리·commit·transaction. 누락·중복 oracle, rebalance 경계, Kafka 내부 EOS와 외부 부작용의 구분.
- G3, K09–K12: 운영·state·CDC. failure domain, restore/replay, 보안 positive/negative 검사, snapshot 경계 검증.
- G4, K13–K14: 연구·통합 설계. 실제 source commit trace, Kafka 최소 시스템의 실행·장애 보고, 후속 통합의 보장/실험 계획. 전체 PG→Kafka→CH E2E 장애·복구는 [공통 8주 통합 연구](../../databases/shared/capstone.md)에서 수행하며 K14 설계 리뷰로 대체하지 않습니다.

설계 통과와 실행 통과를 분리합니다. 기본 Compose로 가능한 K01–K03/K05–K06의 일부를 끝냈어도 클러스터·transaction 애플리케이션·CDC 검증을 완료한 것은 아닙니다. 평가 점수는 [assessment.md](assessment.md)를 따르며 공통 기준은 4영역 각 25점, 총 80점 이상·각 15점 이상과 필수 gate입니다.

## 매 모듈의 제출 형식

1. 어떤 업무 보장을 검증하는지와 실패하면 영향을 받는 결과.
2. 입력 fixture·독립 oracle·정상/오류/불명 응답 분류.
3. 재현 환경·실행 명령·정확한 버전·설정·feature level.
4. 원시 로그·metrics·소스 연결과 경쟁 가설을 반박한 근거.
5. 선택한 설계·포기한 대안·가용성/정확성/비용의 상충.
6. 실제 완료·미완료 항목과 원복 상태.

낮은 lag, 프로세스 healthy, 오류 로그 없음 중 어느 하나도 전체 정확성의 oracle이 아닙니다. 업무별 ID·version·금액·상태 불변식이 끝까지 일치해야 합니다.
