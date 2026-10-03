# M13–M14. 분산 경계, 장애, 독립 복구

[커리큘럼](../curriculum.md) · 이전: [MV와 수명 관리](06-materialization-and-lifecycle.md) · 다음: [종합 평가](../assessment.md)

현재 Compose는 단일 노드입니다. 이 강의는 **클러스터·백업·부하 격리 환경의 설계 및 추가 구현 과제**이며 해당 인프라를 이미 제공한다고 주장하지 않습니다. 단일 노드에서 조회 가능한 관찰은 따로 표시합니다. 문서만 읽은 경우 M13–M14 실행 검증은 미완료입니다.

## M13 분산 경계와 합의 CLUSTER-DESIGN

**선수 조건:** M09–M12, 메시지 지연·중복·분할, quorum과 Raft 기초.

### 원리

shard는 데이터 분배의 단위이고 replica는 같은 shard의 복제본입니다. sharding key는 부하 분산뿐 아니라 같은 엔티티의 버전·JOIN·집계를 어디서 결합할지 결정합니다. `Distributed`는 원격 읽기와 쓰기 라우팅을 제공하며 설정에 따라 비동기 전송 큐에 데이터가 머무를 수 있습니다. 라우터의 응답과 대상 shard 반영을 같은 시각으로 취급하지 않습니다. [Distributed 엔진](https://clickhouse.com/docs/engines/table-engines/special/distributed)

`ReplicatedMergeTree`는 replica 간 part와 작업을 조정합니다. Keeper는 데이터 part 전체를 저장하는 분석 노드가 아니라 coordination metadata를 관리하는 시스템입니다. Keeper의 Raft 다수결과 특정 INSERT의 replica 확인을 다루는 `insert_quorum`은 서로 다른 층입니다. replica quorum 설정이 여러 shard·여러 테이블·외부 시스템에 걸친 원자적 트랜잭션을 만드는 것은 아닙니다. [Replication](https://clickhouse.com/docs/engines/table-engines/mergetree-family/replication), [Keeper](https://clickhouse.com/docs/guides/sre/keeper/clickhouse-keeper), [트랜잭션 보장 범위](https://clickhouse.com/docs/guides/developer/transactional)

timeout은 실패 여부가 확정되지 않았다는 상태일 수 있습니다. 클라이언트는 요청 식별자·재시도 정책·독립 원장을 이용해 실제 반영 상태를 확인해야 합니다. 읽기의 최신성은 접속 replica·동기화 상태·설정·쿼리 경로와 연결되므로 단순히 “replicated이므로 read-after-write”라고 쓰지 않습니다.

### 추가 구축할 토폴로지

```text
client -> Distributed endpoint -> shard A: replica A1 / A2
                              -> shard B: replica B1 / B2
replicated tables -> Keeper K1 / K2 / K3 (coordination quorum)
independent backup destination + independent restore target
```

동일 물리 host의 컨테이너 7개는 protocol 실험에는 쓸 수 있지만 host 장애 내성을 증명하지 못합니다. 다른 failure domain, persistent volume, hostname/macros, Keeper 경로, 사용자/TLS, 포트, 자원 제한, 시작/중지 절차를 명시합니다. `ON CLUSTER` DDL queue 완료도 노드별로 확인합니다. 최소 자원량은 데이터·동시성에 의존하므로 실제 사용량을 측정해 정합니다.

### 실험 명세

10,000개 이상의 연속 event_id와 독립적인 producer ACK 원장을 사용합니다. fault마다 baseline → 주입 → 관찰 → 복구 → 모든 replica/집계 대조 순서로 수행합니다. 저장소는 fault injection 스크립트를 제공하지 않습니다.

| 장애 | 가설과 관찰 | 통과 증거 |
| --- | --- | --- |
| replica A2 중단 | A1의 쓰기·읽기가 어떤 설정에서 계속되는가? | 명시한 quorum/timeout, 성공·실패·불명 ACK 분류, 복구 후 event_id 대조 |
| Keeper 1개 중단 | 남은 2개가 다수결을 유지하는가? | leader/commit 상태, write 가용성, 재시작 catch-up |
| Keeper 2개 중단 | 다수결 없는 coordination write의 행동은? | 시간 제한 있는 오류/대기 증거, read 동작은 경로별 별도 기록 |
| Distributed 전송 중 shard B 단절 | 라우터 ack와 shard 도착의 차이는? | distribution queue·예외·disk 증가, 복구 후 누락·중복 대조 |

각 실험에 제한 시간과 원복 절차를 둡니다. 이미 대기 중인 write의 timeout 이후 다른 payload로 임의 재시도하지 않습니다. `insert_quorum=1/2`, 동기/비동기 분산 전송을 비교할 때 한 번에 하나의 변인만 바꿉니다.

**LOCAL 관찰:** 아래 조회의 빈 결과는 단일 노드 MergeTree에서 정상일 수 있습니다. 복제가 건강하다는 증거가 아닙니다.

```sql
SELECT cluster, shard_num, replica_num, host_name FROM system.clusters;
SELECT database, table, is_leader, is_readonly, queue_size, absolute_delay
FROM system.replicas;
SELECT database, table, type, create_time, num_tries, last_exception
FROM system.replication_queue;
SELECT * FROM system.distribution_queue LIMIT 10;
```

`absolute_delay` 하나로 모든 정확성·신선도를 증명하지 않습니다. 애플리케이션이 원하는 특정 event_id의 도착 시각과 함께 봅니다. 실패가 없더라도 shard key의 편향, GLOBAL JOIN/broadcast 네트워크 비용, initiator의 최종 aggregation 메모리 병목을 추가 측정합니다.

**SOURCE 과제:** `StorageReplicatedMergeTree`, `ReplicatedMergeTreeQueue`, `DistributedSink`, `KeeperStateMachine`에서 data plane과 metadata/consensus 경계를 연결합니다. Keeper log commit과 SQL transaction commit을 같은 이름 때문에 혼동하지 않습니다.

**실패 모드:** replica를 shard처럼 합산해 이중 집계, random shard 배정으로 같은 엔티티 버전 분산, 성공 응답 범위 오해, 큐 디스크 포화, Keeper 다수결 상실, 두 replica를 백업으로 오인.

**제출·통과:** 토폴로지·불변식·4개 장애 보고서·원복 상태. 실행 자료가 없으면 설계 통과만 기록하며 분산 운영 역량 완료 판정을 유보합니다.

## M14 복구와 워크로드 경계 OPS-DESIGN

**선수 조건:** M01–M13, RPO/RTO, percentile·capacity, 최소 권한.

### 원리

replication은 가용성을 높이지만 잘못된 DELETE나 논리 오류도 전파할 수 있습니다. 백업은 별도 시점으로 되돌릴 데이터·스키마·설정·접근 정보를 보존하고, 복구는 실제로 그것을 읽어 서비스를 검증하는 과정입니다. 백업 성공 로그는 restore 성공과 동의어가 아닙니다. [Backup/restore](https://clickhouse.com/docs/operations/backup)

워크로드의 품질은 단일 쿼리 최고 기록보다 서로 간섭할 때의 지연·신선도·오류율로 평가합니다. ingestion, 대시보드, ad-hoc JOIN, background merge/mutation을 함께 고려합니다. query 제한·동시성·대기열·resource/workload 스케줄러의 지원 범위와 적용 자원을 버전에서 확인합니다. 제한은 초과 시 거절·취소·spill·대기 중 무엇을 하는지 관찰해야 합니다. [Workload scheduling](https://clickhouse.com/docs/operations/workload-scheduling)

### 추가 구축 과제 A: 독립 복구

1. 백업 destination과 권한, 허용 disk/path 또는 object storage 설정을 구성합니다. 현재 Compose에는 이를 설정하지 않았으므로 바로 실행 가능한 BACKUP 경로를 가정하지 않습니다.
2. raw·MV target·DDL·계정/권한·설정의 백업 범위를 정의합니다. backup 객체가 비밀정보를 담는지도 구별합니다. source와 target의 시점이 엇갈릴 때 재계산할지 동시점으로 보호할지 정합니다.
3. `event_id`와 expected aggregate 원장을 별도로 보존하고 성공적으로 확인한 마지막 ingestion 위치를 표시합니다. 외부 replay log의 보관 기간도 RPO에 포함합니다.
4. 백업 실행 후 독립된 빈 복구 환경에 restore합니다. 원본 볼륨을 복구 환경에 재사용하지 않습니다. 인증, DDL, 행 수, distinct id, 시간 범위, group별 금액, 대표 query와 MV의 신규 insert 반응을 확인합니다.
5. 사고 선언부터 서비스 검증 완료까지 RTO, 확인된 마지막 데이터와 복구 가능한 마지막 데이터 차이로 RPO를 계산합니다. 차이를 설명하지 못하면 백업 성공 여부와 무관하게 실패입니다.

### 추가 구축 과제 B: 혼합 부하와 운영 경계

먼저 실험용 목표를 스스로 정합니다. 예: 데이터 1,000만 행, ingestion 5,000 rows/s, 대시보드 5 QPS, p95 1초, 신선도 10초, 오류율 0.1% 미만. **이는 학습용 목표 예시이며 제품 성능 보장이 아닙니다.** 현재 host에서 불가능하면 목표·근거를 사전에 수정합니다.

10분 baseline 뒤 20분 혼합 부하, 10분 회복을 관찰합니다. 최소 1,000개의 요청 표본을 확보하고 p95와 실패율을 계산합니다. load generator 자체의 병목·대기 포함 여부·open/closed loop·coordinated omission을 보고합니다. row 수·payload·skew·반복 패턴을 명시하고 생성 데이터만으로 실업무 용량을 단정하지 않습니다.

배경 작업과 ad-hoc query가 추가되면 dashboard 지연·ingestion 지연·메모리·디스크·part backlog가 어떻게 바뀌는지 봅니다. 제한 없는 OOM 대신 제한 계정의 query memory/time/concurrency 제약을 검증합니다. 분석 계정은 허용된 SELECT가 성공하고 INSERT/DROP/다른 데이터 읽기가 거부됨을 별도 시험합니다. 실습용 lab 관리자 자격증명을 운영 구성으로 복사하지 않습니다. [Access control](https://clickhouse.com/docs/operations/access-rights)

**기대 증거:** 실제 restore transcript와 검증 SQL, RPO/RTO timeline, 혼합 부하 raw latency/오류 표본, before/after 설정, 권한 positive/negative 결과. 미구성 기능은 미검증으로 표시합니다.

**실패 모드:** replicas=backup, 복구 시간이 준비 작업을 제외한 값, source만 복구하고 target stale을 정상 처리, p99를 몇 회의 실행으로 추정, disk가 가득 차기 직전에만 경보, 단일 host로 failure-domain 가용성을 증명.

**제출·통과:** 독립 restore에 성공하고 검증 SQL로 내용이 일치해야 합니다. 미리 정한 SLO를 달성하지 못하면 원인·용량 경계·수정안을 제출하고 다시 측정합니다. 최종 판정은 [종합 평가](../assessment.md)를 따릅니다.
