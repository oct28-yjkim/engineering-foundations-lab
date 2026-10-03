# 05. DDL·유지보수·복구 — 성공 메시지 뒤의 업무 상태를 검산한다

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

MY09의 작은 DDL/MDL 실험은 LOCAL-SESSIONS, MY10의 독립 복원·PITR·crash 주입은 RESTORE-LAB입니다. 제공 단일 노드의 데이터 볼륨을 삭제하거나 서버를 강제 종료하는 자동 단계는 없습니다. 복원은 기존 source가 아닌 **별도 빈 target**에서 검증합니다.

<a id="my09"></a>
## MY09 · atomic DDL·online DDL·MDL·공간 회수

### 원리

atomic DDL, transactional DML, online DDL은 다른 계약입니다. 지원되는 DDL의 crash 원자성이 있다고 사용자 transaction의 ROLLBACK으로 DDL을 취소할 수 있다는 뜻은 아닙니다. 많은 DDL이 implicit commit을 일으킵니다. `CREATE TEMPORARY TABLE` 같은 예외도 “모두 rollback 가능”을 뜻하지 않으므로 statement별 조건을 확인합니다. [Atomic DDL](https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html), [implicit commit](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html).

INSTANT/INPLACE/COPY와 concurrent DML 허용 조건은 operation·버전·table 조건에 따라 다릅니다. “online”이어도 시작/종료의 MDL 대기와 자원 비용이 존재할 수 있습니다. 의도한 algorithm/lock 수준을 명시해 지원되지 않을 때 실패시키고 예상치 못한 비용 큰 fallback을 피합니다. [Online DDL operations](https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-operations.html).

### 수동 실험: 읽기 transaction이 DDL을 기다리게 할 때

```sql
CREATE TABLE my09_mdl_run01 (id INT PRIMARY KEY, n INT NOT NULL) ENGINE=InnoDB;
INSERT INTO my09_mdl_run01 VALUES (1,10);
```

1. A가 `START TRANSACTION; SELECT * FROM my09_mdl_run01;` 후 열린 상태를 유지합니다.
2. B는 transaction 밖에서 `SET SESSION lock_wait_timeout=3;`을 설정한 뒤 `ALTER TABLE my09_mdl_run01 ADD COLUMN note VARCHAR(20) NULL, ALGORITHM=INSTANT;`를 실행합니다.
3. B가 기다리는 동안 C에서 아래 metadata lock을 관측합니다. timeout이 먼저 나면 수집 시점을 조정해 다시 실행하되 대기 시간을 무한히 늘리지 않습니다.
4. A를 COMMIT한 뒤 B의 동일 ALTER를 실행합니다. 성공/실패와 `SHOW CREATE TABLE`을 확인합니다. 첫 실행이 이미 성공했다면 같은 컬럼을 재추가하지 않습니다.
5. `innodb_lock_wait_timeout`과 `lock_wait_timeout`이 다루는 대기 경계를 구분합니다. DDL 실패를 무조건 row deadlock으로 분류하지 않습니다.

```sql
SELECT OBJECT_TYPE, OBJECT_SCHEMA, OBJECT_NAME, LOCK_TYPE,
       LOCK_DURATION, LOCK_STATUS, OWNER_THREAD_ID
FROM performance_schema.metadata_locks
WHERE OBJECT_SCHEMA=DATABASE() AND OBJECT_NAME='my09_mdl_run01';
```

[Metadata locking](https://dev.mysql.com/doc/refman/8.4/en/metadata-locking.html)의 transaction 수명과 위 시간표를 맞춥니다. 권한 없는 계정이 관측에 실패하면 이를 기록하고 전역 관리 권한을 애플리케이션에 부여하는 해결책을 쓰지 않습니다.

### 심화 과제

- 별도 table에서 index 추가를 `ALGORITHM=INPLACE, LOCK=NONE` 조건으로 평가합니다. MDL·중간 공간·write rate·실패 시 남는 상태를 기록하며 “LOCK=NONE이므로 잠금이 전혀 없다”고 쓰지 않습니다.
- 오래된 read view와 undo/purge, delete-marked record와 실제 공간 재사용, 파일 크기 감소를 구별합니다. DELETE 직후 파일이 줄지 않는 현상을 즉시 공간 누수로 판정하지 않습니다.
- schema migration의 expand→호환 write/read→backfill 검산→cutover→contract 단계를 설계합니다. backfill의 중복·늦은 write·rollback 가능 경계를 포함하고 대규모 변경은 자동 수행하지 않습니다.
- DDL을 포함한 실험은 transaction 경계를 별도로 기록합니다. DML 전후의 implicit commit을 빠뜨린 테스트가 왜 잘못된 rollback 검산을 만드는지 반례를 제출합니다.

**통과:** MDL 양성/음성 대조군, DDL algorithm/지원 조건, 공간/시간 예산·중단 조건, migration의 역호환성과 검산 원장이 필요합니다.

<a id="my10"></a>
## MY10 · crash recovery·backup·PITR·복원 판정

### 원리

crash recovery는 기존 데이터와 로그로 crash 일관성을 복구하는 과정이고 backup restore/PITR는 저장된 별도 사본과 보관 로그에서 목표 상태를 재구성하는 과정입니다. undo/redo가 있어도 잘못된 정상 transaction이나 모든 storage 유실을 자동으로 되돌려 주지 않습니다. [InnoDB recovery](https://dev.mysql.com/doc/refman/8.4/en/innodb-recovery.html), [PITR](https://dev.mysql.com/doc/refman/8.4/en/point-in-time-recovery.html).

논리 dump의 `--single-transaction`은 InnoDB 데이터 snapshot의 조건을 다루며 동시 DDL·비트랜잭션 table·계정/권한·서버 설정 전체를 자동으로 해결하지 않습니다. dump와 binlog/GTID 좌표의 정합성, 도구 버전, 권한, 보존 정책을 확인합니다. [mysqldump](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html). 물리 백업 도구는 지원 버전·복구 준비 단계·암호 키·라이선스를 별도로 검토하며 특정 도구 설치를 필수로 하지 않습니다.

### 별도 환경의 최소 복원 원장

가상 업무는 두 계좌 A/B와 요청 원장입니다. 순서마다 금액과 request ID를 독립 기록하고 dump/binlog 파일의 checksum·크기·시작/끝 좌표를 manifest로 관리합니다.

| 시점 | 업무 사건 | 기대 A/B | 검산 |
| --- | --- | --- | --- |
| T0 | A=100, B=100 초기화 후 일관된 backup | 100 / 100 | 총 200, 요청 0 |
| T1 | 요청 r1: A→B 10 이체 | 90 / 110 | 총 200, r1 1회 |
| T2 | 요청 r2: A에 외부 입금 5 | 95 / 110 | 총 205, r1/r2 각각 1회 |
| Tbad | 별도 실험에서 의도한 잘못된 transaction | 오염된 상태 | 잘못된 transaction 경계를 별도 기록 |
| Restore | 새 target에 T0 복원 후 T2까지 replay | 95 / 110 | 행·원장·제약·r1/r2 정확히 검산 |

Tbad는 **disposable source에만** 설계하는 선택 실패 주입입니다. 기존 데이터나 기본 제공 볼륨에 손상 명령을 실행하지 않습니다. binlog를 운영 연결에 pipe하지 않습니다.

### 실행·판정 순서

1. backup 범위·버전·일관성 조건·계정/권한·암호 키·binlog retention을 manifest로 정의합니다. 보관 로그의 연속성이 없으면 가능한 복원 경계와 불가능 구간을 먼저 표시합니다.
2. 새 target에 T0만 복원해 기대 100/100을 확인합니다. `mysqlbinlog` 등 지원 도구로 사건/transaction 경계를 읽고 T1/T2/Tbad와 연결합니다.
3. 완결된 transaction 경계까지 replay합니다. wall-clock timestamp만 보고 중간 event를 자르지 않으며 time zone·동시 transaction·commit 순서 때문에 시각만으로 모호한 경계는 좌표/GTID/업무 ledger로 해소합니다.
4. 기대 95/110·총 205·요청 두 개·중복 없는 원장을 검사합니다. row count 또는 GTID만 맞는 것으로 통과하지 않습니다. 저장 routine·trigger·권한·시간대 등 애플리케이션 실행 조건도 범위에 맞춰 확인합니다.
5. 잘못된 경계와 누락된 log segment의 음성 대조군이 검산에서 실패하는지 확인합니다. 실패 후 무작정 재생을 반복하지 말고 새 target 또는 명확한 복원 checkpoint에서 재시작합니다.
6. 실제 탐지→복원→검산→접속 전환 시간으로 RTO를, 복구한 마지막 확인 업무와 원장의 차이로 RPO를 계산합니다. 예상치와 측정치를 구분합니다.

`innodb_force_recovery`는 일상적 정상 복구/일관성 보장의 스위치가 아닙니다. 손상 대응 과제는 복사본·버전별 위험·전문 절차를 전제로 설계만 수행할 수 있으며 원본에 임의 적용하지 않습니다.

**통과:** 독립 target 복원, 정확한 transaction 경계, 정상/오염/복원 원장, 음성 대조군, 실제 RPO/RTO가 필요합니다. 백업 파일이 만들어졌거나 서버가 시작됐다는 이유만으로 복구 완료라고 선언하면 미통과입니다.
