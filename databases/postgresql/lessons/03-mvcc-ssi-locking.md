# M05–06. MVCC, 격리 이상 현상, SSI와 잠금

## M05. 현재 값 대신 보이는 버전을 판단하기

**선수 지식:** M03 페이지/tuple, M04 commit. **범위:** S, psql 2개 이상.

MVCC는 각 행의 버전과 snapshot을 이용해 읽을 수 있는 데이터를 정합니다. xmin/xmax 숫자의 대소만으로 가시성을 판단하지 않습니다. 트랜잭션 상태, snapshot에 포함된 진행 중 XID, 자기 transaction/command, tuple flag도 필요합니다. xmax에는 삭제뿐 아니라 잠금과 MultiXact 의미가 담길 수 있습니다. [시스템 컬럼](https://www.postgresql.org/docs/18/ddl-system-columns.html), [가시성 구현](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/access/heap/heapam_visibility.c).

Read Committed(RC)는 문장마다 새 snapshot을 취합니다. Repeatable Read(RR)는 첫 비트랜잭션 제어 문장에서 정해진 snapshot을 유지합니다. `BEGIN`을 먼저 입력했다는 이유만으로 이미 snapshot이 고정됐다고 생각하면 실험 순서가 틀어집니다. PostgreSQL의 RR은 snapshot isolation으로 이해할 수 있지만 모든 업무 규칙을 직렬 실행처럼 보장하지는 않습니다. [격리 수준](https://www.postgresql.org/docs/18/transaction-iso.html).

### 실험: 같은 쿼리, 다른 시간표

한 세션에서 최초 준비:

```sql
CREATE SCHEMA IF NOT EXISTS deep_lab;
CREATE TABLE deep_lab.m05_snapshot (id integer PRIMARY KEY, value integer NOT NULL);
INSERT INTO deep_lab.m05_snapshot VALUES (1, 10), (2, 20);
```

명령을 아래 순서대로 **한 단계씩** 실행합니다.

| 순서 | A | B |
| --- | --- | --- |
| 1 | `BEGIN ISOLATION LEVEL READ COMMITTED;` | |
| 2 | `SELECT * FROM deep_lab.m05_snapshot ORDER BY id;` | |
| 3 | | `INSERT INTO deep_lab.m05_snapshot VALUES (3, 30);` (autocommit) |
| 4 | 같은 SELECT 재실행 | |
| 5 | `COMMIT;` | |

A의 두 번째 SELECT에 새 행이 보이는지 기록합니다. 두 세션 모두 transaction이 끝난 뒤 `DELETE FROM deep_lab.m05_snapshot WHERE id=3;`으로 이 실험의 추가 행만 원상 복구하고, A의 격리 수준을 `REPEATABLE READ`로 바꿔 같은 시간표를 반복합니다. A의 첫 SELECT를 B의 INSERT 이후로 옮긴 세 번째 시간표도 비교합니다.

별도 C 세션에서 A의 transaction이 열린 동안:

```sql
SELECT pid, state, backend_xid, backend_xmin, xact_start
FROM pg_stat_activity WHERE datname = current_database();
SELECT ctid, xmin, xmax, * FROM deep_lab.m05_snapshot ORDER BY id;
```

이 조회는 C가 보는 버전이므로 A의 snapshot을 직접 보여 주는 것이 아닙니다. A 안에서 같은 조회를 실행한 결과와 비교합니다. 다른 세션의 snapshot을 무심코 자기 SELECT의 snapshot으로 대체하지 않습니다.

**예상 증거:** RC/RR에서 달라지는 관측 행 집합, snapshot 확정 순서에 따른 RR 결과 차이, 긴 snapshot의 `backend_xmin` 관찰. XID/ctid의 숫자는 실행마다 달라집니다.

**실패 양상:** RC transaction 전체가 한 시점이라고 가정하기, UPDATE 충돌과 phantom을 섞기, xmax만으로 “삭제됨”을 판정하기, idle transaction이 항상 동일한 vacuum 방해를 한다고 단정하기. 실제 보유 snapshot/horizon을 확인합니다.

**산출물·통과:** RC/RR 실험 각각 2회와 순서 변경 1회, 최소 5행짜리 시간표, 각 단계의 가시성 설명을 제출합니다. `GetSnapshotData`와 `HeapTupleSatisfiesMVCC`가 각각 무엇을 책임지는지 [소스 지도](../source-reading.md)에서 확인합니다.

## M06. 직렬성, write skew, 대기 그래프

**선수 지식:** M05, 행 불변식과 다중 행 불변식의 차이. **범위:** S, psql 3개.

업무 규칙 “최소 한 명은 당직 중”은 각 행의 CHECK로 표현되지 않습니다. RR에서는 두 transaction이 같은 snapshot을 읽고 서로 다른 행을 변경하면 각각 타당해 보이지만 합친 결과가 규칙을 깨뜨릴 수 있습니다. SSI는 읽기-쓰기 의존 관계를 추적해 직렬성을 보장할 수 없는 경우 transaction을 실패시킵니다. SIReadLock은 보통의 쓰기 방지 잠금처럼 상대를 막기 위한 것이 아닙니다. [Serializable 격리](https://www.postgresql.org/docs/18/transaction-iso.html#XACT-SERIALIZABLE), [SSI 구현](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/storage/lmgr/predicate.c).

### 실험 1: RR에서 write skew, Serializable에서 재시도

처음 한 번:

```sql
CREATE TABLE deep_lab.m06_duty (doctor_id integer PRIMARY KEY, on_call boolean NOT NULL);
INSERT INTO deep_lab.m06_duty VALUES (1, true), (2, true);
```

| 순서 | A | B |
| --- | --- | --- |
| 1 | `BEGIN ISOLATION LEVEL REPEATABLE READ;` | `BEGIN ISOLATION LEVEL REPEATABLE READ;` |
| 2 | `SELECT count(*) FROM deep_lab.m06_duty WHERE on_call;` | |
| 3 | | 동일 COUNT (두 세션 모두 2를 읽은 뒤 진행) |
| 4 | `UPDATE deep_lab.m06_duty SET on_call=false WHERE doctor_id=1;` | |
| 5 | `COMMIT;` | |
| 6 | | `UPDATE deep_lab.m06_duty SET on_call=false WHERE doctor_id=2;` |
| 7 | | `COMMIT;` |

최종 COUNT를 확인합니다. 두 세션의 transaction이 끝났는지 확인한 뒤 `UPDATE deep_lab.m06_duty SET on_call=true;`로 초기화합니다. `REPEATABLE READ`를 `SERIALIZABLE`로 바꾸고 **같은 읽기 순서**를 반복합니다. 오류는 UPDATE 또는 COMMIT 시점에 드러날 수 있으므로 어느 명령에서 SQLSTATE `40001`이 발생했는지 `\errverbose`로 기록하고 실패 세션을 `ROLLBACK;`합니다. 성공 세션의 결과가 보존되고 불변식이 깨지지 않았는지 확인합니다.

C에서는 A/B가 읽기를 수행한 뒤 다음을 관찰합니다.

```sql
SELECT pid, locktype, mode, relation::regclass, page, tuple, granted
FROM pg_locks WHERE mode = 'SIReadLock';
```

읽기 계획과 메모리 조건에 따라 tuple/page/relation 수준이 달라질 수 있습니다. SIReadLock이 나타난 위치를 실제 실행 계획과 연결하되 한 관측으로 항상 같은 granularity라고 일반화하지 않습니다.

재시도는 실패한 UPDATE 한 줄이 아니라 **읽기·판단을 포함한 전체 transaction**입니다. 새 snapshot에서 당직이 한 명이면 두 번째 휴무를 거절해야 합니다. 이미 외부 메시지를 보냈다면 DB rollback이 메시지를 취소하지 않으므로 outbox·idempotency key의 책임을 따로 설계합니다. [직렬화 실패 처리](https://www.postgresql.org/docs/18/mvcc-serialization-failure-handling.html).

### 실험 2: 행 잠금 대기와 deadlock

```sql
CREATE TABLE deep_lab.m06_locks (id integer PRIMARY KEY, n integer NOT NULL);
INSERT INTO deep_lab.m06_locks VALUES (1, 0), (2, 0);
```

A: `BEGIN; UPDATE deep_lab.m06_locks SET n=n+1 WHERE id=1;`

B: `BEGIN; UPDATE deep_lab.m06_locks SET n=n+1 WHERE id=2;`

A: `UPDATE deep_lab.m06_locks SET n=n+1 WHERE id=2;` — 응답 대기 중에 C로 이동합니다.

C:

```sql
SELECT pid, state, wait_event_type, wait_event, pg_blocking_pids(pid) AS blockers
FROM pg_stat_activity WHERE datname = current_database();
SELECT pid, locktype, mode, transactionid, relation::regclass, granted
FROM pg_locks WHERE NOT granted;
```

B: `UPDATE deep_lab.m06_locks SET n=n+1 WHERE id=1;` — 순환 대기가 생깁니다. 어느 세션이 희생되는지는 고정하지 않습니다. 오류 SQLSTATE `40P01`과 대기 관계를 기록한 뒤 A/B 모두 `ROLLBACK;`합니다. timeout이 먼저 끊지 않도록 실험 세션 설정도 기록합니다. [명시적 잠금·deadlock](https://www.postgresql.org/docs/18/explicit-locking.html).

별도 반복에서는 deadlock 대신 B의 첫 대상도 id=1로 통일하고 A를 COMMIT/ROLLBACK하여 대기를 풀어 봅니다. 잠금 순서 통일은 이 두 행 경합을 줄이지만 모든 종류의 deadlock을 없애는 증명은 아닙니다. `lock_timeout='2s'` 실험을 추가할 때 `55P03`과 transaction 실패 상태를 구분하고 종료 후 세션 설정을 되돌립니다.

**예상 증거:** RR의 불변식 위반, SSI의 40001과 재판단, wait edge와 transactionid 대기, deadlock의 순환 및 40P01. row lock 전체가 pg_locks에 행마다 보이는 것은 아닙니다.

**실패 양상:** SERIALIZABLE을 직렬 실행으로 설명하기, SIReadLock이 writer를 막는다고 생각하기, SKIP LOCKED를 일관된 전체 데이터 조회로 사용하기, 애플리케이션 재시도가 무한 반복되게 하기, DDL 대기와 행 대기를 혼동하기.

**산출물·통과:** 두 이상 현상의 SQL/시간표/SQLSTATE 원본, wait-for graph, 최대 시도·deadline·jitter·멱등성 범위를 정의한 재시도 의사코드를 제출합니다. 40001/40P01/55P03마다 처리 근거와 실패 시 사용자에게 반환할 상태를 명시합니다. 소스 `CheckForSerializableConflictOut`, `LockAcquireExtended`, `DeadLockCheck` 중 두 경로를 추적합니다.
