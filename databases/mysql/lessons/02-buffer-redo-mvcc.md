# 02. Buffer·redo·undo·read view — 내구성과 가시성을 분리한다

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

범위는 OFFLINE / LOCAL-SESSIONS이며 crash 주입은 별도 RESTORE-LAB입니다. CPU `read-view`와 `commit-recovery`는 선택한 규칙의 모형입니다. 실제 undo page, redo byte stream, page latch, fsync 또는 MySQL recovery를 실행하지 않습니다.

<a id="my03"></a>
## MY03 · dirty page·WAL·checkpoint·commit ACK

### 원리

buffer pool의 dirty page와 redo의 durable progress는 서로 다른 상태입니다. redo는 crash 뒤 변경을 재구성하는 경로, undo는 rollback과 이전 버전 구성 경로, binlog는 서버의 변경 기록·복제/PITR 경로와 연결됩니다. checkpoint는 모든 SQL이 끝났다는 표식이 아닙니다. WAL 순서와 checkpoint/redo 재사용 제약을 분리합니다. [Redo log](https://dev.mysql.com/doc/refman/8.4/en/innodb-redo-log.html), [checkpoint](https://dev.mysql.com/doc/refman/8.4/en/innodb-checkpoints.html).

`innodb_flush_log_at_trx_commit=1`과 binary logging 사용 시 `sync_binlog=1`은 commit 내구성을 검토하는 핵심 조건이지만, storage가 flush 약속을 지킨다는 가정과 고장 범위를 함께 명시해야 합니다. 0/2의 주기적 flush는 정확히 1초 안의 손실만 허용한다는 보장이 아닙니다. 이 트랙에서는 값을 낮춰 성능을 높이는 변경을 자동 실행하지 않습니다. [내구성 설정](https://dev.mysql.com/doc/refman/8.4/en/innodb-parameters.html#sysvar_innodb_flush_log_at_trx_commit).

group commit은 여러 transaction의 동기화 비용을 묶는 기법이지 여러 업무 transaction을 하나로 바꾸는 기능이 아닙니다. InnoDB와 binlog의 내부 commit 협조는 MY11에서 다루며 사용자 `XA` transaction과 구별합니다. doublewrite의 page 손상 보호 역할도 redo·backup의 대체물로 설명하지 않습니다.

```sql
SELECT @@global.innodb_flush_log_at_trx_commit, @@global.sync_binlog,
       @@global.log_bin, @@global.innodb_redo_log_capacity,
       @@global.innodb_buffer_pool_size;
SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool%';
SHOW GLOBAL STATUS LIKE 'Innodb_redo_log%';
```

### 실험·관측

1. 전용 작은 write fixture의 단건 commit과 bounded batch commit을 비교합니다. 업무 transaction 크기가 바뀐 실험이면 “같은 계약의 단순 성능 개선”으로 분류하지 않습니다.
2. 실행 전후 redo 관련 status, dirty page, write/flush 관측값과 ACK 시각을 기록합니다. global counter에는 background 작업이 섞이므로 모든 증가량을 내 query에 귀속하지 않습니다.
3. 모형에서 durable prepare·binlog decision·engine commit 여부를 바꾸고 recovery 결정을 예측합니다. 도달 불가능한 조합과 전제 밖 조합을 모형이 어떻게 다루는지 확인합니다.
4. 별도 disposable 서버에서만 정상 종료와 process 강제 종료를 비교하도록 설계합니다. client ACK ledger와 재시작 후 PK/값을 검산합니다. OS cache가 남는 process crash는 전원 상실 시험이 아닙니다.
5. 페이지 flush 완료를 기다리지 않아도 commit이 가능할 수 있는 이유, redo 공간이 부족할 때 write 지연이 생길 수 있는 이유를 각각 설명합니다.

**통과:** 한 transaction의 수정→redo 기록/동기화→내부 commit 경계→client ACK와 별도 page flush 시간선을 그립니다. 관측한 사실과 설정으로 추론한 보장을 구별합니다. 복구 모형 통과를 전원 상실 내구성 검증으로 쓰면 미통과입니다.

<a id="my04"></a>
## MY04 · undo·read view·consistent/current read·purge

### 원리

InnoDB는 undo를 이용해 과거 버전을 구성합니다. read view는 transaction ID 숫자 하나가 아니라 생성 시점의 진행 중 transaction과 경계 등을 사용합니다. 자기 transaction의 변경도 고려해야 합니다. 오래된 view를 유지하면 필요한 이전 버전의 회수가 지연될 수 있습니다. [Multi-versioning](https://dev.mysql.com/doc/refman/8.4/en/innodb-multi-versioning.html).

RR의 일반적인 consistent read는 **첫 consistent read에서 만든 view**를 재사용합니다. `START TRANSACTION`만 실행한 시각과 동일하지 않으며 `WITH CONSISTENT SNAPSHOT`은 별도로 다룹니다. RC에서는 consistent read마다 view를 새로 얻습니다. locking read/UPDATE/DELETE를 같은 과거 snapshot의 단순 조회로 간주하지 않습니다. [Consistent reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html), [격리 수준](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html).

### 실행 시간표: BEGIN, 첫 read, current read

개인 schema에서 한 번 준비하고 A/B는 같은 schema에 접속합니다. B의 각 UPDATE는 `autocommit=1`인 별도 transaction입니다.

```sql
CREATE TABLE my04_view_run01 (id INT PRIMARY KEY, n INT NOT NULL) ENGINE=InnoDB;
INSERT INTO my04_view_run01 VALUES (1,10);
```

| 순서 | A: RR | B: autocommit |
| --- | --- | --- |
| 1 | `SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;` | `SET autocommit=1;` |
| 2 | `START TRANSACTION;` | |
| 3 | | `UPDATE my04_view_run01 SET n=20 WHERE id=1;` |
| 4 | `SELECT n FROM my04_view_run01 WHERE id=1;` → 20 | |
| 5 | | `UPDATE my04_view_run01 SET n=30 WHERE id=1;` |
| 6 | 같은 일반 SELECT → 20 | |
| 7 | `SELECT n FROM my04_view_run01 WHERE id=1 FOR UPDATE;` → 30 | |
| 8 | `UPDATE my04_view_run01 SET n=40 WHERE id=1;` | |
| 9 | 같은 일반 SELECT → 자기 변경 40 | |
| 10 | `COMMIT;` | |

위 숫자는 단 하나의 행만 있고 표 외 writer가 없다는 fixture의 기대값입니다. step 7 이후에는 A가 row lock을 가지므로 추가 B write를 끼워 넣지 않습니다. 문장을 통째로 동시에 실행하지 말고 한 단계씩 진행합니다.

### 반증·확장

1. 새 suffix의 같은 초기 데이터에서 A의 첫 SELECT를 B의 첫 UPDATE **이전**으로 옮깁니다. A의 RR 결과가 왜 10을 유지하는지 설명합니다.
2. 또 다른 새 fixture에서 RC로 바꾸면 일반 SELECT step 6은 30입니다. `SET SESSION`은 열린 transaction 밖에서 실행하며 종료 후 실습 세션 설정을 기록합니다.
3. 읽기와 자기 write가 섞이면 “과거의 한 시점 전체”라는 단순 모델로 모든 결과를 설명할 수 없는 반례를 만듭니다. 이를 RR의 모든 읽기가 최신이라는 주장으로 바꾸지 않습니다.
4. 작은 write 수를 상한으로 장기 view를 유지한 조건과 종료한 조건의 purge/history 지표를 비교합니다. transaction을 열기만 한 상태와 실제 consistent read 후 상태를 구분하고 모든 세션을 COMMIT/ROLLBACK합니다.
5. 소스에서 read-view 생성/가시성 판정/undo 추적/회수 가능 경계를 찾습니다. CPU `read-view`가 구현한 own write·삭제와, 생략한 실제 undo page·record format·purge·DDL 경계를 대조해 적습니다.

**통과:** RR/RC/첫 read 이동의 세 시간표, 일반/locking read 기대값, purge 관측과 생략 조건을 제출합니다. RR을 serializable 또는 모든 SELECT/DML에 적용되는 고정 snapshot으로 설명하면 미통과입니다.
