# MySQL 28주 심화 커리큘럼

14모듈 × 2주 × 주 12시간 = 약 336시간입니다. 모듈당 원리·공식 자료 6시간, 실험 10시간, 소스 추적 4시간, 분석·구술 4시간을 기준으로 합니다. SQL 입문자는 [공통 기초](../shared/foundations.md)를 보충하고 C++·Linux debug 환경과 별도 복구/복제 토폴로지 구축 시간은 따로 확보합니다.

## 모듈 지도

| 모듈 / 주 | 선수 조건 | 핵심 질문 | 제출·최소 통과 |
| --- | --- | --- | --- |
| MY01 / 1–2 | 집합·명제·기초 SQL | [SQL 의미·서버/엔진 경계](lessons/01-foundations-storage.md#my01) | NULL·중복·collation·정렬 계약, parser→executor→handler 경로 |
| MY02 / 3–4 | MY01, 트리·페이지 | [clustered/secondary index](lessons/01-foundations-storage.md#my02) | secondary key→PK→행 경로, covering 반례·PK 폭 비교 |
| MY03 / 5–6 | MY02, OS I/O | [buffer·redo·checkpoint·commit](lessons/02-buffer-redo-mvcc.md#my03) | dirty page/redo flush/ACK 시간선, process crash와 전원 상실 구분 |
| MY04 / 7–8 | MY03, 트랜잭션 | [undo·read view·purge](lessons/02-buffer-redo-mvcc.md#my04) | RC/RR 시간표, 첫 consistent read·current read·장기 snapshot 반례 |
| MY05 / 9–10 | MY04, 그래프 | [record/gap/next-key·deadlock](lessons/03-locking-transactions.md#my05) | 접근 경로별 lock footprint·wait graph·희생자 비고정 검산 |
| MY06 / 11–12 | MY05, 업무 불변식 | [write skew·재시도·멱등성](lessons/03-locking-transactions.md#my06) | RR 반례, 읽기/판단 전체 재실행·미확정 commit 계약 |
| MY07 / 13–14 | MY02, 통계 | [cardinality·cost·통계](lessons/04-optimizer-execution.md#my07) | skew/correlation fixture·추정 대 실제·경쟁 가설 |
| MY08 / 15–16 | MY07 | [iterator·join·sort·인덱스](lessons/04-optimizer-execution.md#my08) | 결과 동등성·실행 계획·반복 측정·쓰기 비용과 trade-off |
| MY09 / 17–18 | MY03–MY05 | [atomic/online DDL·MDL·purge](lessons/05-maintenance-recovery.md#my09) | DDL 대기/실패/공간 예산·기존 transaction 경계 확인 |
| MY10 / 19–20 | MY03, MY09 | [backup·crash recovery·PITR](lessons/05-maintenance-recovery.md#my10) | 독립 target 복원·binlog 경계·원장 검산·RPO/RTO |
| MY11 / 21–22 | MY03, MY06, MY10 | [binlog·내부 commit 협조·GTID](lessons/06-binlog-replication.md#my11) | redo/undo/binlog 역할, GTID received/executed·CDC 재생 계약 |
| MY12 / 23–24 | MY11, 분산 실패 모델 | [복제·세미동기·승격·HA](lessons/06-binlog-replication.md#my12) | 적용 지연·fencing·split-brain·read-after-write 반례 |
| MY13 / 25–26 | MY01–MY12, C++ 기초 | [운영·권한·소스 근거](lessons/07-production-research.md#my13) | 5symbol·2자료구조·1test·권한 양성/음성 대조군 |
| MY14 / 27–28 | MY13 | [2주 최소 연구](lessons/07-production-research.md#my14) | 한 경로·한 개선·두 실패 조건·독립 oracle·한계 보고서 |

## 시간보다 증거를 우선한다

모든 모듈은 업무 질문 → 불변식 → 실패 모델 → 입력·기대값 → 실행 범위 → 관찰 → 경쟁 가설 → 소스 근거 → 한계 순으로 제출합니다. [공통 실험 방법](../shared/experiment-method.md)의 원시 기록에 다음 항목을 추가합니다.

```text
run_id / fixture fingerprint / image digest / server version+edition / source revision
schema+indexes / engine / sql_mode / charset+collation / timezone / isolation+autocommit
session+connection ID / transaction boundaries / statement order / result IDs+values
error number+SQLSTATE / affected rows / retry attempt+deadline / uncertain commit ledger
plan / estimated+actual rows / loops / latency samples / cache state / concurrency
redo/binlog durability settings / checkpoint+purge indicators / lock+MDL wait evidence
server UUID+server ID / source-replica channel / GTID sets / received-applied-visible times
backup manifest / replay boundaries / restored business ledger / measured RPO+RTO
```

모든 칸을 항상 관측할 수 있는 것은 아닙니다. 모형에서 만든 값, 서버에서 직접 관측한 값, 간접 추론한 값을 표시합니다. client timeout은 commit 실패로 확정하지 않고, connection ID·InnoDB transaction ID·GTID·업무 idempotency key는 서로 대체하지 않습니다.

성능 측정에서는 같은 행·정렬·트랜잭션 계약을 유지합니다. 동시성, 연결 재사용, warm/cold 상태, 데이터 크기, buffer pool, background flushing, 실패율을 고정·기록합니다. A/B 순서를 섞고 충분한 반복·표본 수를 제시합니다. 한 번의 `EXPLAIN ANALYZE` 시간이나 CPU 모형의 연산 수를 운영 QPS/p99로 환산하지 않습니다.

## 네 개의 gate

- G1, MY01–MY04: SQL 의미·접근 경로·commit 경계·가시성. RR의 `BEGIN`만으로 snapshot이 고정된다고 설명하거나 redo/undo/binlog를 하나로 취급하면 미통과입니다.
- G2, MY05–MY08: 잠금·불변식·재시도·최적화. lock wait와 deadlock을 구별하고, 인덱스의 결과 의미·쓰기 비용·잠금 범위를 함께 검토합니다.
- G3, MY09–MY12: DDL·복구·복제. replica를 backup으로, source의 GTID를 replica 적용 증명으로, 세미동기 ACK를 replica query 가시성으로 부르면 미통과입니다.
- G4, MY13–MY14: 관측·권한·소스·연구. 실행하지 않은 복원·장애조치·보안·빌드를 PASS로 표시하지 않습니다.

[평가표](assessment.md)는 정확성 25, 원리·소스 25, 실험·반증 25, 운영·재현성 25점입니다. **총 80점 이상·모든 영역 15점 이상·필수 gate 전부 충족**이 선언한 범위의 완료 기준입니다. OFFLINE과 LOCAL-ENGINE만 했다면 그 범위로 표기하고 RESTORE-LAB·REPLICA-LAB·SECURITY-LAB·BUILD는 각각 별도 상태를 남깁니다.

MY14 안에서 새 다중 클러스터·CDC 플랫폼·클라우드를 모두 구축하지 않습니다. 큰 통합은 선택 [8주 캡스톤](../../capstones/mysql-transaction-recovery.md)으로 진행합니다.
