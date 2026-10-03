# Kafka 완료 기준: 전달·가시성·외부 상태·복구를 따로 검증하기

이 과정은 Kafka API 사용에서 시작해 동작을 예측하고 장애 경계를 검증하는 능력을 평가합니다. 학습 기간이나 문서 열람으로 전문가 수준을 선언하지 않습니다. [14개 모듈](curriculum.md), [소스 지도](source-reading.md), [실습 안내](labs/local-lab.md)의 산출물과 아래 관문을 함께 적용합니다.

## 상태와 실행 범위

각 과제는 `미착수 → 설계 완료 → 실행 완료 → 동료 재현 완료`로 기록합니다. 구현이 필요한 SDK 앱·Streams·Connect·CDC와 다중 broker/controller 환경, 소스 빌드가 현재 준비되었는지 구별합니다. 제공 Compose의 단일 노드 smoke test는 생산자→topic→소비자 경로와 데이터 검산의 출발점이며, 복제 내구성·controller quorum·전체 EOS·외부 시스템 복구의 증명이 아닙니다.

강의의 `LOCAL`은 제공 단일 노드에서의 실행, `BUILD`는 별도 SDK 앱/소스 빌드, `CLUSTER-DESIGN`은 추가 클러스터를 구성하기 위한 설계, `INTEGRATION-DESIGN`은 외부 시스템 연동 설계입니다. 뒤의 두 표시는 설계 상태를 뜻하며 실제 환경을 만들어 실행 증거를 제출해야 해당 고급 실행 관문을 통과합니다.

설계서만 완성한 항목에는 예상 결과를 쓰되 실측 칸을 채우지 않습니다. 미실행과 실행 실패는 구별합니다. 고급 관문이 미실행이면 단일 노드 단계만 완료로 보고합니다.

## 점수와 필수 조건

**기본 운영 gate:** [운영 가이드](operations.md)에 따라 실제 정상 baseline 1개, 서로 다른 증상 2개, 지표·로그·업무 원장의 상관관계, 경쟁 가설 배제, 완화·원복, 업무 결과와 지표의 회복 증거를 제출합니다. 단순 smoke 성공이나 source reading만으로 통과하지 않습니다. 정제된 실측 자료 분석은 별도 분석 완료이고 직접 재현/복구 미실행을 숨기지 않습니다. 기존 다중 노드·transaction·CDC 관문은 유지합니다.

공통 체계와 동일하게 **총점 80점 이상, 각 영역 15점 이상, 해당 단계의 필수 관문 전부 통과**가 기준입니다. 높은 성능 점수로 데이터 손실이나 복구 실패를 상쇄할 수 없습니다.

| 영역 | 배점 | 평가할 증거 |
| --- | --- | --- |
| 정확성 | 25 | 독립 oracle로 event ID·payload·순서·누락/중복·최종 업무 상태를 검산. transaction 가시성과 외부 효과의 계약을 구분 |
| 원리·소스 | 25 | partition/offset, ACK·복제·가시성, group protocol, transaction·quorum·상태 복구를 반례와 정확한 source 경로로 설명 |
| 실험·반증 | 25 | 입력/설정 통제, 원본 로그·대조군·실패 조건, 예측/관측/추론 분리. throughput·tail·backpressure·용량/비용을 함께 비교하고 채택/기각 근거 제시 |
| 운영·재현성 | 25 | 버전·digest·feature/config·실행 순서, 장애/복원·실제 RPO/RTO·최소 권한·rollback 기준·runbook·동료 재현 |

성능 비교는 [공통 실험 방법](../../databases/shared/experiment-method.md)을 적용합니다. warmup 제외 조건별 20회 이상의 반복을 시작점으로 삼고, steady-state throughput과 tail latency에는 충분한 시간·요청량을 별도로 설계합니다. 실패·retry·timeout을 버리고 성공 요청만으로 분모를 줄이지 않습니다. 반복 횟수보다 독립적인 조건·대표 분포·오차 설명이 중요합니다.

## 모듈별 필수 관문

| 관문·모듈 | 실험과 제출물 | 통과 기준 |
| --- | --- | --- |
| G01 · K01 로그·순서 | exact ID oracle, partition/key/offset 출력, 같은 key와 다른 key의 순서 비교 | 모든 필수 ID와 payload를 검산. partition 내 순서와 topic 전역 순서를 구분하며 offset을 건수로 계산하지 않음 |
| G02 · K02 저장·정리 | segment/index/retention 관측, compact topic의 반복 key·tombstone 시간표 | cleanup이 즉시 수행된다고 가정하지 않음. compaction 뒤 offset gap·삭제 의미 설명. compaction을 중복 처리 방지·백업으로 제안하지 않음 |
| G03 · K03 producer | batch/linger·compression의 동일 입력 비교, ACK/error/callback 원장, SDK 기반 실패 실험 | app 재전송과 producer retry, idempotence와 업무 중복을 구분. timeout 요청의 최종 결과를 확인 |
| G04 · K04 복제 **다중 노드 필수** | RF=3 등 명시한 topology, ISR/ELR/leader epoch/HW, ACK 원장, broker 장애 기록 | 실제 min ISR·ACK·feature 상태별 성공/실패를 검산. 단일 노드 정지로 replicated failover를 입증했다고 쓰지 않음 |
| G05 · K05 offset·재처리 | 처리 전 commit/처리 후 commit의 crash 위치별 결과, group offset/position/업무 ledger | 손실·중복을 ID 집합과 외부 결과로 구별. committed offset은 다음 재개 위치라는 의미를 일관되게 사용 |
| G06 · K06 group protocol | `classic`/`consumer` 구성을 분리한 membership·assignment·rebalance 관측, 느린 처리/재시작 사례 | 실제 protocol과 heartbeat/session 설정 주체 확인. revoke 후 작업·offset commit 경계를 설명 |
| G07 · K07 전달 의미 | at-most/at-least/EOS 계약표, DB 또는 HTTP 부작용의 crash window 재현 | 외부 반영 뒤 offset commit 전 장애에서 중복을 찾고 inbox/멱등성 키 등록과 업무 변경을 같은 sink transaction에 묶거나 외부 API의 실제 멱등성 계약으로 불변식 유지 |
| G08 · K08 transaction | commit/abort/open transaction·fencing 실험, read_committed/uncommitted 결과, source 추적 | LSO/HW/LEO 경계와 aborted record 제외 설명. read-process-write transaction 범위와 외부 side effect 한계를 명시 |
| G09 · K09 KRaft **다중 controller 필수** | quorum 구성·voter/observer·epoch·leader·metadata 상태, controller 장애 주입·복구 | metadata quorum과 data replica 복제 구별. quorum 손실/복구 후 관리·읽기·쓰기 영향과 최종 metadata 검산 |
| G10 · K10 운영·보안·복구 **별도 환경 포함** | hot partition/consumer lag 등 장애 판별, TLS/ACL 허용·거절, 격리 복구/replay와 업무 검산 | 프로세스 healthy와 업무 복구를 분리. 실제 복구 완료시간·데이터 손실 범위·자격증명/권한 복원 확인 |
| G11 · K11 Streams **앱 구현 필수** | topology·keying·repartition·window/grace, changelog/state restore, 실패 후 출력 ledger | out-of-order 입력을 oracle로 검증. local state 삭제/재생성은 격리 복사본에서 수행. EOS 범위·state restore 완료를 출력으로 확인 |
| G12 · K12 Connect/CDC **worker·connector·외부 DB 필수** | connector/task 상태, source snapshot/stream 경계·offset, delete/schema 변경·재시작 검산 | source 위치/Kafka offset/sink 적용 위치를 구분. sink commit과 offset commit 사이 중복을 업무 키로 처리. task RUNNING만으로 통과 불가 |
| G13 · K13 source **빌드/테스트 필수** | 일치한 source SHA, baseline test, 입력 A/B의 분기/상태, 최소 회귀 테스트·로그 | 3경로의 thread/event/영속화 경계를 설명하고 최소 1경로를 debugger 또는 계측 테스트로 실행 검증 |
| G14 · K14 2주 미니 캡스톤 | Kafka consume-transform-produce 최소 앱·oracle·선택 실패 경계·source note·통합 설계 | Kafka 내부 입력/출력/offset 계약을 검산하고 기존 모듈 증거를 재사용. PG/CH 구현이나 8주 전체 프로젝트를 이 관문의 전제로 요구하지 않음 |

G04/G09/G10의 고급 복구, G11/G12, G13은 현재 Compose를 기동하는 것만으로 완료되지 않습니다. 아래 단계 보고와 관문 체크를 함께 제출합니다.

Transactional outbox를 사용하는 경우에는 source DB의 업무 변경과 발행 대상을 같은 transaction에 남기는 책임을 평가합니다. outbox만으로 sink의 부작용 중복이 제거되는 것은 아니므로 G07의 sink inbox/멱등성·원자적 업무 반영 관문을 별도로 통과해야 합니다.

- **입문 실습 완료:** 로컬 smoke oracle, G01 및 G02의 로컬 관측을 실행했습니다. 아직 전달 보장·장애조치를 검증한 단계가 아닙니다.
- **단일 노드 응용 완료:** 로컬에서 가능한 G03/G05–G08을 별도 SDK 앱으로 실행하고 G14의 로컬 부분을 검증했습니다. SDK 앱이 없으면 CLI smoke 결과로 이 단계를 대신하지 않습니다.
- **고급 시스템 검증 완료:** G01–G14를 모두 실행하고 다중 노드·외부 connector·source build·복구 증거 및 동료 재현을 통과했습니다.

## 반드시 구분할 숫자와 보장

| 항목 | 잘못된 해석 | 필요한 판정 |
| --- | --- | --- |
| LEO/HW/LSO | 모두 마지막 메시지 번호 또는 모두 ACK된 레코드 건수 | 같은 partition·시점·replica에서 exclusive 경계와 가시성을 비교. abort/control record·offset gap 고려 |
| consumer lag | 0이면 외부 DB·메일·결제도 완료 | lag 정의·isolation·LSO 정체·업무 적용 ledger를 분리 |
| producer timeout | broker에 기록되지 않았으므로 마음대로 다시 보내도 됨 | 불확정 결과로 분류하고 event ID/원장으로 저장·중복 여부 확인 |
| idempotent producer | 프로세스 재생성·업무 재전송까지 모두 중복 제거 | producer session/sequence와 app event key의 다른 책임을 검증 |
| transaction/EOS | Kafka 밖의 모든 부작용도 원자적 | consume/produce/offset 및 지원된 source 경계, 외부 시스템의 별도 보장 명시 |
| compaction | 마지막 값만 항상 남고 과거 복원도 가능 | 정리 시점·tombstone·보존 조건을 확인. 최신 상태 표현과 역사/백업을 구분 |
| ELR/ISR | 모든 4.x 버전에서 같은 설정·선출 | 4.3.1 feature/config와 실제 ISR/ELR 선출 이력에 근거 |
| controller quorum | data partition의 RF와 같은 개수·같은 역할 | metadata 합의와 partition 복제의 failure domain을 따로 그리기 |

## K14의 2주 미니 캡스톤

[K13–14 강의](lessons/07-research-capstone.md)의 Kafka consume-transform-produce 최소 슬라이스를 구현합니다. 외부 DB를 요구하지 않는 결정적 입력과 독립 oracle을 사용하고, 정상·abort·재시작/재처리 중 강의에서 정한 실패 경계를 검증합니다. 입력 event ID, 변환 출력, transaction/consumer offset의 관계를 확인하고 K03–K13에서 이미 얻은 장애·소스 증거를 재사용합니다.

새 다중 노드·CDC·분석 DB를 모두 2주 안에 처음부터 구축하는 과제가 아닙니다. PostgreSQL→Kafka→ClickHouse 흐름은 이 단계에서는 schema/offset/중복/삭제/복구 경계의 설계로 제출할 수 있습니다. 두 DB 트랙을 먼저 이수하지 않았더라도 K14의 Kafka 범위를 완수할 수 있습니다.

## 선택 확장: 전체 트랙 후 공통 8주 통합 캡스톤

이 절은 **K14의 2주 필수 구현과 별도**이며 모든 관련 트랙 뒤의 [공통 8주 통합 연구](../../databases/shared/capstone.md)에 적용합니다. 주문 변경 event를 Kafka로 전달하고 downstream에서 주문별 최종 상태·집계를 만드는 파이프라인을 사용합니다. 각 event는 `event_id`, `aggregate_id`, `aggregate_version`, payload/hash, event time을 갖고 외부 승인 원장에 남깁니다. offset을 업무 버전으로 대체하지 않습니다.

실패를 주입할 지점은 적어도 5개를 선택합니다: source DB commit 직후, producer 응답 전후, 소비 처리 전후, sink commit 직후/offset commit 직전, transaction commit/abort 경계, group reassignment, broker/controller 손실, Streams state restore 중단, Connect task 재시작. 선택한 지점마다 필요한 별도 환경과 중단 조건을 먼저 정의합니다.

최종 검사는 count 하나로 끝내지 않습니다. event ID의 누락/중복 집합, 주문별 최신 버전, 삭제 상태, 금액/상태별 합계, 외부 부작용 횟수, 선언한 지연/RPO/RTO를 대조합니다. 중복 event 수와 중복 업무 반영 횟수는 다른 값으로 기록합니다. ACK를 못 받은 event는 성공/실패의 어느 쪽에도 임의로 넣지 않고 불확정 상태를 최종 원장으로 해소합니다.

## 제출 구조와 증거 품질

```text
kafka-capstone/
  environment.txt          # broker/client/JDK/digest/source SHA, features
  contract.md              # ordering·delivery·visibility·failure 계약
  topology.md              # broker/controller/worker/source/sink 경계
  app/                     # 재현 가능한 SDK·Streams·connector 설정
  workload/                # 결정적 입력과 독립 oracle
  evidence/
    producer/              # callback/ACK/timeout·event ID
    consumer/              # protocol·assignment·position·commit
    broker/                # ISR/ELR·HW/LSO/LEO·quorum·자원
    external-state/        # source/sink 원장·중복/누락 차이
    benchmark/             # warmup·정상/실패/재시도 전체 기록
    recovery/              # 복구 입력·시간표·최종 검산
  source-notes.md           # 질문→구현→반례→테스트
  runbooks/                # 탐지·판별·조치·되돌림·업무 확인
  review.md                # 동료 재현 결과와 미검증 항목
```

위 구조는 범위에 맞춰 사용하는 제출 형식입니다. K14는 Kafka 내부 증거·앱·설계만 채우고 외부 시스템/전체 복원은 미실행으로 표시합니다. 공통 8주 프로젝트에서 이를 확장합니다. 이 저장소에 이미 측정 결과나 완성 앱이 제공된다는 뜻은 아닙니다. 비밀값은 기록하지 않고 설정 키·참조 위치·유효 principal과 검증 결과만 남깁니다. 원본 로그에서 오류를 제거한 요약만 제출하면 재현 관문을 통과하지 못합니다.

## 구두 방어와 재평가

리뷰어는 다음에서 5문제 이상을 선택하고 반례 조건을 추가합니다.

1. read_committed consumer가 멈췄지만 HW는 증가한다. LSO와 open transaction, lag 정의를 어떻게 확인하는가?
2. acks=all 요청이 성공했는데 장애 뒤 데이터를 잃을 수 있다고 주장한다면 어떤 장애·설정·failure domain을 먼저 명시해야 하는가?
3. partition 수를 늘린 뒤 같은 key 순서가 달라졌다. 기존 데이터와 새 partition mapping을 어떻게 추적하는가?
4. 동일 event ID가 로그에는 두 번 있지만 외부 DB에는 한 번 반영됐다. 어느 계층이 어떤 보장을 수행한 것인가?
5. consumer protocol을 바꾼 후 기존 heartbeat 설정을 줄여도 효과가 없다. 설정 주체와 코드 경로는?
6. compact topic에서 중복 key를 발견했다. 버그를 주장하기 전에 어떤 segment·cleanup 조건을 확인할 것인가?
7. Connect task가 RUNNING인데 source DB 삭제가 sink에 남아 있다. source event→converter→transform→sink를 어떻게 좁히는가?
8. metadata quorum을 복구했으나 사용자 데이터를 복원하지 못했다. 어떤 증거를 별도로 확보했어야 하는가?
9. Streams 처리 모드가 exactly_once_v2인데 외부 결제가 두 번 실행됐다. 불변식과 transaction 범위를 어디서 잘못 정의했는가?
10. 소스 unit test는 통과했는데 3-broker 환경에서 실패한다. mock 시간·network·disk·coordinator 경계 중 무엇이 빠졌는가?

틀린 답을 문구로 수정하는 대신 입력 분포·실패 시점·protocol 또는 기능 상태를 하나 바꿔 재실험합니다. 가설이 틀린 근거와 수정 전후 결과를 남기는 것이 재평가의 핵심입니다.
