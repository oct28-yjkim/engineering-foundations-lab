# 연구 읽기와 작은 엔진 구현

이 문서는 데이터베이스와 Kafka 트랙 중후반의 확장 경로입니다. 논문·설계 제안 내용을 현재 제품의 보장으로 그대로 옮기지 않습니다. 문제·가정·해법을 먼저 이해하고, 고정한 source revision과 실제 관측으로 현재 구현을 확인합니다. 아래 프로그램은 완성 코드가 아니라 **학습자가 구현할 과제**입니다.

## 읽기 순서와 재현 질문

| 원문 | 연결할 모듈 | 읽고 답할 질문 | 실험 결과물 |
| --- | --- | --- | --- |
| [Serializable Snapshot Isolation in PostgreSQL, 2012](https://arxiv.org/abs/1208.4179) | PG MVCC·SSI | 어떤 read/write dependency가 단순 write/write 충돌 검사로 잡히지 않는가? | write skew의 dependency graph와 RR/Serializable 재현 이력 |
| [MonetDB/X100: Hyper-Pipelining Query Execution, 2005](https://www.cidrdb.org/cidr2005/papers/P19.pdf) | PG executor / CH pipeline | tuple 단위 호출과 큰 중간 결과 materialization 사이에 어떤 비용 차이가 있는가? | 같은 연산의 row-at-a-time/block-at-a-time 구현과 입력 크기별 CPU 측정 |
| [HyperLogLog, 2007](https://algo.inria.fr/flajolet/Publications/FlFuGaMe07.pdf) | CH aggregate states | register 수와 추정 오차, state merge의 관계는 무엇인가? | exact oracle·여러 seed·cardinality별 오차 분포 |
| [ClickHouse — Lightning Fast Analytics for Everyone, 2024](https://www.vldb.org/pvldb/vol17/p3731-schulze.pdf) | CH storage·execution | 저장·pruning·실행 설계가 어느 workload에서 함께 유리해지는가? | paper의 설계 주장 하나를 26.8 source와 workload 실험에 대응 |
| [Raft 원 논문과 저자 자료](https://raft.github.io/) | CH Keeper / Kafka K09 / 공통 분산 | 선출·log 복제·commit·apply가 각각 어떤 안전 조건을 지키는가? | 3-node 이력표와 partition/leader 교체 사례; Keeper/KRaft metadata 구현과의 대응·차이 |
| [KIP-848: Consumer Rebalance Protocol](https://cwiki.apache.org/confluence/spaces/KAFKA/pages/217387038/KIP-848+The+Next+Generation+of+the+Consumer+Rebalance+Protocol) | Kafka K06 | 전역 동기화 지점을 제거할 때 assignment와 ownership 안전성을 어떻게 구분하는가? | classic/consumer의 회수·할당·처리 중단 이력, 실제 4.3.1 코드·feature와의 대조 |
| [KIP-890: Transactions Server-Side Defense](https://cwiki.apache.org/confluence/spaces/KAFKA/pages/235834631/KIP-890+Transactions+Server-Side+Defense) | Kafka K08 | 늦게 도착한 요청이 다음 transaction에 섞이는 문제를 어떤 식별자로 막는가? | transaction/epoch/sequence 이력과 실패 재현, protocol version별 적용 범위 |

X100의 과거 벤치마크 배수를 현재 PostgreSQL/ClickHouse의 성능 배수로 재사용하지 않습니다. HyperLogLog의 오차 공식을 모든 `uniq*` 함수의 공식으로 적용하지 않습니다. 논문 시점의 ClickHouse 기능을 현재 릴리스의 기능 목록으로 취급하지 않습니다.

KIP는 설계 논의를 포함하므로 accepted 표시만 보고 전체가 구현됐다고 판정하지 않습니다. KIP-848의 미구현·대체된 부분은 실제 [consumer protocol 문서](https://kafka.apache.org/43/operations/consumer-rebalance-protocol/) 및 [소스 지도](../../streaming/kafka/source-reading.md)와 대조합니다. Raft 논문을 읽었다고 Kafka 데이터 topic의 ISR 복제가 Raft와 동일하다고 설명하지 않습니다.

## 구현 A: page와 append log

선행: 공통 F02, PG 저장·WAL. 목표는 byte layout, 내구성 경계, 복구의 테스트 가능성을 이해하는 것입니다.

1. 고정 크기 page에 header, slot directory, variable-length payload를 직렬화합니다. slot은 논리 위치를, payload offset은 물리 위치를 나타내게 합니다.
2. append log record에 length, sequence, operation, payload, checksum을 둡니다. 정상 log 재생으로 reference map과 같은 결과를 만듭니다.
3. record의 각 byte 경계에서 잘린 파일을 입력으로 주고 partial tail을 어떻게 처리할지 명시합니다. 완전한 record 중 손상은 정상 EOF와 구별합니다.
4. commit marker 이전/이후 crash를 파일 fixture로 재현하고 acknowledged write가 복구에서 지켜야 하는 계약을 정의합니다.

**통과**: 정상·partial tail·checksum 불일치·중복 replay의 test, 원본 log와 복원 값 비교. 언어의 flush와 OS의 durability 보장을 구별합니다. 이 teaching engine은 PostgreSQL WAL format, 실제 page locking, filesystem crash consistency를 구현한 것이 아닙니다.

## 구현 B: sparse marks와 정렬 병합

선행: CH 저장·pruning. 동일 키를 포함한 정렬 run을 파일로 저장하고, K행마다 첫 키와 offset을 기록합니다. 범위 조회 시 모든 run을 스캔하는 reference와 sparse mark를 이용한 후보 구간 결과를 비교합니다.

K를 세 수준으로 바꾸고 index 크기, 실제 읽은 행, seek 횟수, latency를 기록합니다. 균등 분포와 hot key 분포를 비교하고, 경계에 걸친 duplicate가 누락되지 않는지 검증합니다. 두 run의 병합을 구현하고 version이 높은 값을 선택할 경우 version 동률의 계약을 정합니다.

**통과**: 임의 범위에 대한 property test, key 경계·마지막 불완전 granule·duplicate·역순 version의 반례. 디스크 상 run별 정렬과 전체 전역 정렬이 다름을 설명합니다. 실제 ClickHouse에는 adaptive granularity, codecs, part metadata, multi-stream 및 concurrency가 더 있음을 기록합니다.

## 구현 C: mergeable aggregate state

선행: CH 집계. `count`, `sum`, `avg`를 accumulate/merge/finalize 인터페이스로 구현합니다. `avg`의 state를 `(sum, count)`로 저장하고 서로 크기가 다른 batch의 평균을 단순 평균했을 때의 오류를 재현합니다.

exact distinct는 set union으로 구현한 후, 선택 과제로 원문에 따른 cardinality sketch를 구현합니다. 같은 입력을 여러 batch와 tree merge 순서로 나누고 결과·오차를 비교합니다. 같은 batch를 두 번 넣는 상황에서 count/sum과 set union이 같은 중복 특성을 갖지 않음을 증명합니다.

**통과**: 입력 분할 불변성, empty state, serialization round trip, duplicate replay test, Decimal/Float 선택 근거. “병합 가능”과 “재처리에 멱등”이 다르다는 반례를 반드시 포함합니다.

## 논문 리뷰 제출 형식

Kafka 확장 구현은 append log 과제에 producer identity/epoch/sequence 상태를 더하는 작은 state machine을 선택할 수 있습니다. 정상·중복 재요청·낡은 epoch·순서가 비는 요청에 대해 수락/거절/재응답 계약을 먼저 정의하고 model-based test를 만듭니다. 다른 logical event가 같은 payload를 갖는 경우도 포함합니다. 이 구현은 교육용 모델이며 Kafka의 실제 producer state 보존·복구·transaction 프로토콜을 대체하지 않습니다.

원문의 주장 한 가지, 그 가정, 실험 가능한 예측, 사용한 구현 revision, 지지/반박하는 데이터, 제품에서의 적용 한계를 2–4쪽으로 정리합니다. 구현을 제출하면 build/run/test 명령과 의도적으로 생략한 범위를 붙입니다. 공개 PR이나 이슈 전송은 과제 완료의 필수 조건이 아닙니다.
