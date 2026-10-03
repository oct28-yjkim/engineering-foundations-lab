# MySQL 운영 실습: Performance Schema로 진단하고 회복 검산하기

[트랙](README.md) · [실제 엔진 준비](labs/README.md) · [공통 운영 방법](../../operations/README.md) · [장애 보고서](../../operations/incident-report-template.md)

이 트랙의 주 실습은 **실제 InnoDB의 요청·잠금·실행 계획·복제 상태**입니다. Python 모형은 선택 원리 보조 자료이며 여기의 운영 관문을 대체하지 않습니다. 아래는 학습용 실행 절차이지 이번 변경에서 장애를 실제 실행한 기록이 아닙니다.

## 1. 사전 확인과 읽기 전용 기준선

[전용 Compose](compose.yaml)는 8.4.11 단일 노드이며 외부 포트를 열지 않습니다. 개인 로컬 Docker context·메모리/디스크 예산·기존 volume을 확인한 뒤 [접속 명령](labs/README.md)을 사용합니다. 실제 버전/digest와 Performance Schema 활성 여부를 기록합니다. 실습 root/dummy 비밀번호는 운영 계정 설계가 아닙니다. SQL 원문·사용자·오류 메시지에서 비밀을 제거합니다.

```sql
SELECT VERSION(), @@hostname, @@server_uuid, @@server_id,
       @@performance_schema, @@transaction_isolation, @@autocommit;
SHOW GLOBAL STATUS WHERE Variable_name IN
('Uptime','Threads_connected','Threads_running','Connections','Aborted_connects',
 'Innodb_buffer_pool_read_requests','Innodb_buffer_pool_reads',
 'Innodb_row_lock_waits','Innodb_row_lock_time','Innodb_log_waits');
SELECT ENGINE_TRANSACTION_ID,THREAD_ID,OBJECT_SCHEMA,OBJECT_NAME,
       INDEX_NAME,LOCK_TYPE,LOCK_MODE,LOCK_STATUS
FROM performance_schema.data_locks WHERE OBJECT_SCHEMA LIKE 'ops_my_%';
SELECT REQUESTING_THREAD_ID,BLOCKING_THREAD_ID,REQUESTING_ENGINE_TRANSACTION_ID,
       BLOCKING_ENGINE_TRANSACTION_ID FROM performance_schema.data_lock_waits;
SELECT OBJECT_TYPE,OBJECT_SCHEMA,OBJECT_NAME,LOCK_TYPE,LOCK_DURATION,
       LOCK_STATUS,OWNER_THREAD_ID
FROM performance_schema.metadata_locks WHERE OBJECT_SCHEMA LIKE 'ops_my_%';
SELECT SCHEMA_NAME,DIGEST,COUNT_STAR,SUM_TIMER_WAIT,SUM_ROWS_EXAMINED,
       SUM_ROWS_SENT,SUM_CREATED_TMP_DISK_TABLES,SUM_ERRORS
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME LIKE 'ops_my_%' ORDER BY SUM_TIMER_WAIT DESC LIMIT 10;
```

기준선은 같은 부하에서 10초 간격·5분, 대기 재현은 1초 간격·최대 20초입니다. consumer/instrument가 꺼져 있거나 권한이 없으면 **관측 불가**이며 정상 0이 아닙니다. summary를 TRUNCATE하거나 `FLUSH STATUS`로 사건 흔적을 지우지 않습니다.

| 지표 | 형식·단위·계산 | 주의점 |
| --- | --- | --- |
| Threads_connected / Threads_running | gauge, 연결/스레드 수 | pool 대기·DB 대기·CPU 포화는 다름 |
| Connections / Aborted_connects | counter, 건; 같은 uptime의 60초 Δ/초 | 분모·실패 원인 없이 비율만 비교하지 않음 |
| Innodb_row_lock_waits / time | counter, 건/ms; Δtime/Δwaits는 구간 평균 ms | 평균은 p95/p99가 아니며 MDL 대기는 별도 |
| buffer_pool_reads / read_requests | counter, page 접근/읽기 수; 구간 Δ비율 | logical miss 비율은 storage latency·전체 건강과 다름 |
| digest SUM_TIMER_WAIT | counter, picosecond; Δ/1e12는 seconds | ΔCOUNT_STAR로 평균 계산; 누적 순위는 최근 악화와 다름 |
| SUM_ROWS_EXAMINED / SUM_ROWS_SENT | counter, row; digest·60초 Δ | 0행 결과/집계에서는 비율만으로 나쁜 SQL 판단 금지 |
| Innodb_log_waits | counter, wait 건; Δ/60초 | redo buffer 기다림 지표이며 모든 fsync 지연을 대표하지 않음 |

근거: [8.4 상태 변수](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html), [data_lock_waits](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-data-lock-waits-table.html), [statement digest](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-statement-summary-tables.html).

## 2. 명시적으로 선택한 로컬 fixture

이하 DDL/DML은 개인 실습 환경에서만 실행합니다. `ops_my_01`이 있으면 새 suffix로 바꾸고 기존 객체를 보존합니다. 세션 최대 3개·fixture 2,000행·각 사건 60초·SELECT 5초·대기 10초가 상한입니다. 서버 전체 설정/다른 세션은 변경하지 않습니다.

```sql
CREATE DATABASE ops_my_01;
USE ops_my_01;
CREATE TABLE accounts(id INT PRIMARY KEY,balance INT NOT NULL) ENGINE=InnoDB;
INSERT INTO accounts VALUES(1,100),(2,100);
CREATE TABLE events(id INT PRIMARY KEY, customer INT NOT NULL, payload VARCHAR(120)) ENGINE=InnoDB;
INSERT INTO events
WITH RECURSIVE n AS (SELECT 1 AS x UNION ALL SELECT x+1 FROM n WHERE x<1000)
SELECT x,MOD(x,100),REPEAT('x',100) FROM n;
```

## 3. 사건별 진단

### A. UPDATE timeout: row lock인가, deadlock인가?

세션 A: `USE ops_my_01; START TRANSACTION; UPDATE accounts SET balance=balance+1 WHERE id=1;` 후 최대 20초 유지합니다. 세션 B: `USE ops_my_01; SET SESSION innodb_lock_wait_timeout=10; START TRANSACTION; UPDATE accounts SET balance=balance-1 WHERE id=1;`. 관측 세션에서 위 `data_lock_waits`와 `data_locks`로 thread→transaction→index/record를 연결합니다.

**경쟁 가설:** CPU/I/O 지연, row lock wait, deadlock. 대기 edge 한 개만으로 cycle을 선언하지 않습니다. **조치/롤백:** A와 B 모두 명시적 `ROLLBACK`을 실행합니다. lock wait timeout의 transaction rollback 범위는 설정에 따라 다르므로 에러만 받고 세션을 방치하지 않습니다. **회복:** wait edge 0, 두 잔액 100, 새 transaction 정상. 앱에서는 transaction 전체의 deadline·멱등성·bounded retry를 검토하고 임의 `KILL`을 하지 않습니다.

### B. ALTER가 멈춘다: MDL과 InnoDB lock은 다른가?

세션 A: `START TRANSACTION; SELECT * FROM ops_my_01.accounts WHERE id=1;` 후 transaction을 유지합니다. 세션 B: `SET SESSION lock_wait_timeout=10; ALTER TABLE ops_my_01.accounts ADD COLUMN ops_note INT NULL;`. A는 최소 B timeout 확인 시까지 유지하되 사건 상한 30초 후 반드시 `ROLLBACK`합니다. 관측 세션에서 `metadata_locks`의 GRANTED/PENDING과 thread 소유자를 기록합니다.

**경쟁 가설:** MDL, table rebuild/I/O, row lock. ALTER의 session 상태와 MDL 없이 원인을 단정하지 않습니다. **조치:** 열린 transaction 종료를 먼저 협의합니다. **롤백:** DDL은 implicit commit이므로 ROLLBACK으로 schema가 돌아간다고 생각하지 않습니다. B가 예상과 달리 성공하면 column을 무조건 삭제하지 말고 `SHOW CREATE TABLE`로 실제 상태를 보존합니다. **회복:** pending MDL 0, transaction 종료, schema diff와 잔액 검산. DDL 재시도는 상태를 확인한 후 별도 판단합니다. 근거: [metadata_locks](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-metadata-locks-table.html).

### C. 읽기가 느리다: scan·추정 오차·buffer miss 구별

```sql
USE ops_my_01;
SET SESSION max_execution_time=5000;
EXPLAIN ANALYZE SELECT id,payload FROM events WHERE customer=42;
CREATE INDEX events_customer ON events(customer);
EXPLAIN ANALYZE SELECT id,payload FROM events WHERE customer=42;
```

**확인:** 동일 결과 10행, plan·추정/실제 rows·loops와 digest rows examined·실행 시간·buffer counter를 같은 구간에서 비교합니다. 작은 fixture에서는 scan을 골라도 정상입니다. **조치:** 결과 계약을 유지한 인덱스/통계/쿼리 개선을 선택하고 쓰기 비용도 측정합니다. **롤백:** index는 자기 fixture에만 생성하며 필요 시 소유 index의 제거 계획을 별도 검토합니다. 세션 종료로 session 설정을 해제합니다. **회복:** 정확한 ID 집합과 오류율 유지, plan의 인과관계 설명. 수 밀리초의 단발 차이를 운영 성능 개선으로 확정하지 않습니다. 근거: [EXPLAIN ANALYZE](https://dev.mysql.com/doc/refman/8.4/en/explain.html).

### D. replica가 stale하다: 수신·적용·가시성 분리

기본 Compose는 GTID/binlog가 있어도 replica가 아닙니다. 아래는 별도 소유 source/replica 환경에서만 수행합니다.

```sql
SHOW REPLICA STATUS\G
SELECT CHANNEL_NAME,SERVICE_STATE,LAST_ERROR_NUMBER,LAST_ERROR_MESSAGE
FROM performance_schema.replication_connection_status;
SELECT CHANNEL_NAME,WORKER_ID,SERVICE_STATE,LAST_ERROR_NUMBER,LAST_ERROR_MESSAGE
FROM performance_schema.replication_applier_status_by_worker;
```

**가설:** receiver/network, applier 오류/경합, replica read transaction의 오래된 snapshot. Seconds_Behind_Source는 초 단위 gauge이나 0/NULL만으로 최신성이나 건강을 판정하지 않습니다. channel·received/executed GTID·worker 오류와 알려진 업무 marker를 같이 봅니다. 전용 channel에서만 SQL thread를 최대 20초 중단→합성 INSERT 최대 100행→SQL thread 재개하는 승인된 재현 계획을 사용합니다. 실제 명령과 channel 이름은 [8.4 복제 상태](https://dev.mysql.com/doc/refman/8.4/en/show-replica-status.html) 및 토폴로지와 대조합니다.

**조치:** 오류/병목 계층 복구 및 읽기 일관성 정책 수정; 트랜잭션 skip·GTID 초기화·무조건 승격 금지. **롤백/회복:** thread 재개, 신규 applier 오류 없음, GTID 격차 감소, 새 read transaction에서 업무 marker 확인. 해당 환경이 없으면 미실행으로 남깁니다.

## 4. 운영 완료 기준

실제 baseline + 사건 최소 2개 + 각 사건의 경쟁 가설·관측·제한된 조치·변경 상태·회복 후 업무 검산이 필요합니다. [기존 runner](labs/README.md)의 정상 기능 검사만으로 이 관문은 통과하지 않습니다. CPU/mock 테스트는 보조 코드 검증이며 실제 replica·PITR·권한 실습은 각각 별도 증거를 요구합니다.
