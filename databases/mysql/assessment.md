# MySQL 심화 과정 평가 기준

[커리큘럼](curriculum.md) · [실습 범위](labs/README.md) · [소스 지도](source-reading.md)

평가의 대상은 **SQL 의미·물리 구조·동시성·내구성·복구 경계를 증거로 설명하는 능력**입니다. OFFLINE, LOCAL-ENGINE, LOCAL-SESSIONS, RESTORE-LAB, REPLICA-LAB, SECURITY-LAB, BUILD를 구분합니다. 작은 모형의 성공은 실제 fsync나 다중 서버 보장의 증거가 아닙니다.

## 점수와 필수 gate

각 25점, 총 **80/100 이상·모든 영역 15/25 이상**과 필수 gate 전부 통과가 선언한 범위의 완료 기준입니다.

| 영역 | 최소 증거 | 높은 수준의 증거 |
| --- | --- | --- |
| 정확성 25 | 행 ID·값·순서·업무 불변식·오류의 독립 oracle | 경합·timeout·중복 요청·복원/승격 뒤 원장 검산 |
| 원리/소스 25 | server/engine·page/index·read view·로그 역할과 고정 revision | 실제 symbol·자료구조·test를 잇고 반례로 가정 범위 확인 |
| 실험/반증 25 | baseline·한 변인·음성 대조군·세션 시간표 | 경쟁 가설·반복·불확실성·failure injection과 수정 검증 |
| 운영/재현성 25 | 환경·자원 상한·권한·비밀 제거·scope 기록 | 미확정 commit/GTID/backup ledger와 독립 복구 재현 |

1. **버전·의미:** MySQL/InnoDB와 MariaDB/Aurora/NDB를 구별하고, collation·sql_mode·시간대·격리 수준·autocommit을 기록합니다. count만 맞는 결과를 정답으로 인정하지 않습니다.
2. **가시성:** RR consistent read의 첫 snapshot, RC의 문장별 view, own write, current/locking read를 구별합니다. transaction ID 숫자 비교만으로 visibility를 판정하거나 RR을 serializable이라고 부르면 미통과입니다.
3. **잠금·재시도:** 실제 접근 경로·record/gap/next-key·MDL을 구별하고 wait graph를 제시합니다. deadlock과 lock timeout의 rollback 범위를 확인하며, 불확실한 commit을 무조건 실패로 재전송하지 않습니다.
4. **내구성:** buffer page·redo write/flush·undo·binlog·commit ACK의 경계를 설명합니다. process 종료와 전원 상실·storage 유실을 구별하고, 모형의 durable marker를 fsync 검증으로 쓰지 않습니다.
5. **최적화:** 결과 동등성, 추정/실측 rows와 loops, cache·반복·오류율을 함께 냅니다. 작은 fixture에서 optimizer가 index를 고르지 않았다는 이유로 잘못된 결과라고 판정하지 않습니다.
6. **복구·복제:** backup 파일 존재가 아닌 독립 복원, source ACK가 아닌 replica 적용·조회, GTID 집합만이 아닌 업무 데이터 검산이 필요합니다. replica·HA·backup·PITR은 서로 다른 gate입니다.
7. **안전·정직성:** 공유 서버·기존 volume을 삭제하지 않습니다. 실제 비밀·개인정보를 기록하지 않고, mock/정적 검사와 실제 서버 실행을 구분합니다. 운영 계정 권한을 실습 편의 계정으로 대체하지 않습니다.

## 범위별 최소 결과물

| 범위 | 제출물 | 별도 미검증 경계 |
| --- | --- | --- |
| OFFLINE | 4개 CPU 모형·수작업 기대값·의도적으로 틀린 대조군·단순화 목록 | 실제 InnoDB B-tree, MVCC, lock manager, WAL/복구 |
| LOCAL-ENGINE | 고정 단일 서버·합성 fixture·정확한 값/오류 검산 | 경합·replica·PITR·전원 상실·운영 권한 |
| LOCAL-SESSIONS | 2–3세션 시간표·connection ID·대기/오류·최종 ledger | 다른 계획/격리 설정/대규모 workload |
| RESTORE-LAB | 독립 target·backup+log manifest·복원 경계·행/값/권한·RPO/RTO | 실행하지 않은 region/account/storage 실패 |
| REPLICA-LAB | 다중 서버·received/applied/visible 원장·fencing·승격/재합류 검산 | 시험하지 않은 network partition·AZ·managed service |
| SECURITY-LAB | 별도 주체의 허용/거부·TLS 검증·최소 권한·감사 경계 | 단순 localhost bind·비밀번호 존재만으로 보안 완료 불가 |
| BUILD | 일치하는 소스·도구·빌드 옵션·재현 테스트·실패 전후 출력 | 코드 읽기·grep 결과만으로 빌드 성공 불가 |

“설계 완료 / 실행 완료 / 결과 검증 / 미검증 / 실패”를 구별합니다. 상위 환경을 실행하지 않았더라도 학습 기록은 제출할 수 있지만 전체 운영 역량 완료로 표기하지 않습니다.

## MY14: 2주 미니 연구

앞선 fixture와 코드를 재사용하여 한 경로, 개선 하나, 실패 조건 두 개를 고릅니다. 예: 재고 차감의 중복 요청+commit 응답 유실, RR 업무 규칙의 write skew+retry, skewed query의 통계 변경+데이터 분포 변화입니다. 비교군·독립 oracle·수정 후 정상/실패 재실행을 함께 냅니다.

동료가 임의 요청 최대 10개를 골라 읽기·판단·commit·retry·최종 값을 추적할 수 있어야 합니다. 성능 개선을 제시하면 정확성·불변식이 같은지 먼저 입증하고 악화된 workload도 보고합니다. 실패 주입을 실행하지 않았다면 설계서로만 표시합니다.

별도 [8주 트랜잭션·복구 캡스톤](../../capstones/mysql-transaction-recovery.md)은 백업/PITR·복제/승격·업무 ledger까지 범위를 넓힙니다. [실험 보고서](../shared/templates/experiment-report.md)와 [장애 기록](../shared/templates/incident-review.md)에 세션 시간표, uncertain commit, GTID와 restore 검산을 추가합니다.
