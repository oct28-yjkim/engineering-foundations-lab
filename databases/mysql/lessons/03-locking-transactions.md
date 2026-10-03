# 03. 잠금·deadlock·트랜잭션 — 행의 안전성과 업무 규칙은 다르다

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

범위는 OFFLINE / LOCAL-SESSIONS입니다. CPU `deadlock`은 wait-for graph의 순환을 다루며 InnoDB lock manager의 희생자 정책·MDL·latch를 재현하지 않습니다. 실제 실습은 개인 schema의 A/B 및 관측 C 세션에서 수행하고, 기다리는 문장은 다른 세션으로 이동해 해제합니다. 종료 시 모든 transaction을 끝냅니다.

<a id="my05"></a>
## MY05 · record·gap·next-key·insert intention·대기 그래프

### 원리

InnoDB의 row lock을 논리 행 하나에 붙은 자물쇠로만 이해하면 범위 쓰기를 설명할 수 없습니다. 실제 인덱스 record·gap과 접근 경로를 봅니다. next-key는 record와 앞 gap을 함께 다루고, gap lock은 삽입을 억제합니다. gap S/X 이름을 일반 record S/X 충돌표와 동일시하지 않습니다. insert intention도 “모든 INSERT끼리 배타적”이라는 뜻이 아닙니다. [InnoDB locking](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html).

RR의 존재하는 고유 키에 대한 완전한 고유 검색과 범위/부분 키 검색은 같은 footprint가 아닙니다. RC가 일반 검색의 gap locking을 줄여도 FK·duplicate-key 검사의 예외가 있습니다. index를 추가하거나 query를 rewrite하면 latency뿐 아니라 잠금 대상도 바뀔 수 있습니다. [격리별 잠금](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html).

### 실험 1: 같은 WHERE가 아니라 실제 index range

```sql
CREATE TABLE my05_gap_run01 (id INT PRIMARY KEY, n INT NOT NULL) ENGINE=InnoDB;
INSERT INTO my05_gap_run01 VALUES (10,1),(20,1),(30,1);
```

1. A는 RR transaction을 시작하고 `SELECT * FROM my05_gap_run01 WHERE id>10 AND id<20 FOR UPDATE;`를 실행합니다. 결과가 0행이라는 사실만으로 잠금이 없다고 결론 내리지 않습니다.
2. B는 열린 transaction 밖에서 `SET SESSION innodb_lock_wait_timeout=3;`을 설정하고 transaction을 시작한 뒤 ID 15를 INSERT합니다. A가 열린 동안의 대기/timeout과 오류를 기록하고 B를 명시적으로 ROLLBACK합니다.
3. A도 ROLLBACK한 뒤 새로운 transaction의 B에서 같은 INSERT가 성공하는지 확인하고 ROLLBACK합니다. **오류 대조군과 성공 대조군**이 모두 있어야 합니다.
4. 같은 데이터를 유지한 별도 실행에서 A를 RC로 바꿉니다. PK/FK/중복 키 검사가 섞이지 않은 이 삽입의 차이를 관측합니다. 이를 “RC에서는 gap lock이 절대 없다”로 일반화하지 않습니다.
5. A의 조건을 존재하는 `id=20` 고유 검색으로 바꾸고 대조합니다. 정확한 lock mode·index·range는 관측으로 기록하며 query predicate 경계와 물리 lock 경계가 항상 같다고 가정하지 않습니다.

권한 있는 관측 C에서 [Performance Schema lock tables](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-lock-tables.html)를 조회합니다. 다른 사용자의 SQL/값이 섞인 결과를 저장하지 않습니다.

```sql
SELECT ENGINE_TRANSACTION_ID, THREAD_ID, OBJECT_SCHEMA, OBJECT_NAME,
       INDEX_NAME, LOCK_TYPE, LOCK_MODE, LOCK_STATUS, LOCK_DATA
FROM performance_schema.data_locks
WHERE OBJECT_SCHEMA=DATABASE() AND OBJECT_NAME LIKE 'my05_%';
SELECT REQUESTING_ENGINE_TRANSACTION_ID, BLOCKING_ENGINE_TRANSACTION_ID,
       REQUESTING_ENGINE_LOCK_ID, BLOCKING_ENGINE_LOCK_ID
FROM performance_schema.data_lock_waits;
```

### 실험 2: 두 행의 반대 순서

```sql
CREATE TABLE my05_deadlock_run01 (id INT PRIMARY KEY, n INT NOT NULL) ENGINE=InnoDB;
INSERT INTO my05_deadlock_run01 VALUES (1,0),(2,0);
SELECT @@global.innodb_deadlock_detect, @@global.innodb_rollback_on_timeout;
```

A/B 모두 세션 `innodb_lock_wait_timeout=30`을 설정하고 transaction을 시작합니다. A는 ID 1, B는 ID 2를 `SET n=n+1`로 변경합니다. A가 ID 2를 UPDATE하여 대기하는 동안 C에서 A→B edge를 기록하고, 제한 시간 내 B가 ID 1을 UPDATE합니다. detector가 켜져 있으면 순환에 따른 1213을 관측할 수 있습니다. 어느 세션이 희생되는지는 고정하지 않습니다. detector가 꺼졌거나 1205가 먼저 발생하면 조건과 실패 순서를 기록하고 deadlock 검출 성공으로 세지 않습니다.

모든 세션을 ROLLBACK한 뒤 0/0인 fixture를 검산합니다. 다음 실행은 두 transaction 모두 ID 오름차순으로 획득하여 대기·진행을 비교합니다. 이 두 행 사례의 순서 통일이 모든 쿼리·DDL·FK의 deadlock을 제거하는 증명은 아닙니다.

**통과:** range/gap/고유 키 대조군, wait edge와 순환, 오류·희생자·최종 값을 제출합니다. MDL·row lock·latch를 같은 대기 원인으로 뭉뚱그리면 미통과입니다.

<a id="my06"></a>
## MY06 · write skew·전체 transaction 재시도·미확정 commit

### 반례: RR은 직렬성의 보장이 아니다

```sql
CREATE TABLE my06_duty_run01 (
  doctor_id INT PRIMARY KEY, on_call BOOLEAN NOT NULL
) ENGINE=InnoDB;
INSERT INTO my06_duty_run01 VALUES (1,TRUE),(2,TRUE);
```

업무 불변식은 `SUM(on_call)>=1`입니다. A/B 모두 RR transaction에서 **일반 SELECT**로 합계 2를 먼저 읽습니다. A가 ID 1을 FALSE로 UPDATE하고 COMMIT한 뒤, B가 이미 읽은 판단에 따라 ID 2를 FALSE로 UPDATE하고 COMMIT합니다. 최종 합계 0이 반례입니다. 고유 PK별 서로 다른 행을 갱신하므로 이 fixture에서 같은 행 쓰기 충돌이 불변식을 대신 지키지 않습니다.

별도 새 fixture의 개선안은 모든 해당 쓰기가 먼저 공통 guard row를 `FOR UPDATE`로 잠근 뒤 **잠금 이후의 유효한 읽기와 판단**을 수행하게 만드는 것입니다. 오래된 view에서 미리 읽은 COUNT를 재사용하지 않습니다. SERIALIZABLE을 택한 별도 실험은 단순히 RR 문자열만 바꾸고 성공이라고 쓰지 말고 잠금·대기·오류·retry의 전체 시간표를 기록합니다. 업무 규칙을 DB constraint로 표현 가능한지 먼저 검토하고 guard 병목 비용도 측정합니다.

### 오류와 재시도 계약

deadlock 1213은 전체 transaction rollback과 연결됩니다. lock wait timeout 1205는 기본 설정에서 실패한 statement만 되돌릴 수 있으며 `innodb_rollback_on_timeout`에 따라 범위가 달라집니다. 본 실습의 애플리케이션 정책은 오류 후 명시적 ROLLBACK으로 상태를 정리하고 **읽기·판단을 포함한 새 transaction**을 시작하는 것입니다. 중복 키 오류도 무조건 전체 transaction이 사라졌다는 뜻이 아닙니다. [InnoDB error handling](https://dev.mysql.com/doc/refman/8.4/en/innodb-error-handling.html).

```text
업무 idempotency key + 정규화한 요청 digest를 준비한다.
deadline과 최대 attempt 안에서 transaction을 시작한다.
잠금/현재 상태 읽기 → 업무 불변식 검사 → 변경+결과 원장 기록 → COMMIT한다.
확정 deadlock/정책상 retry 오류면 ROLLBACK, bounded backoff+jitter 후 전체를 다시 판단한다.
COMMIT 응답이 유실되면 성공/실패 미확정으로 분류한다.
새 연결에서 같은 업무 key의 결과를 확인하고, 다른 digest의 key 재사용은 거절한다.
결과 확인도 실패하면 미확정 상태를 유지하고 사용자/운영 계약에 따라 복구한다.
```

### 실험·제출

1. RR write skew 원본과 개선안의 정상·경합·거절 결과를 함께 냅니다. 실패를 잡는 테스트가 잘못된 원본 구현에서는 실제로 실패해야 합니다.
2. 같은 요청의 동시 재전송, 같은 key·다른 payload, commit 응답만 유실된 조건을 설계합니다. DB row count뿐 아니라 요청별 결과·총 금액/수량을 검산합니다.
3. 외부 메시지가 필요하면 같은 DB transaction의 outbox 기록과 외부 전달/소비자의 dedup 책임을 분리합니다. DB rollback은 이미 발송한 메시지를 되돌리지 못합니다.
4. `SKIP LOCKED`는 queue 소비 같은 특정 계약의 선택지로 평가하며 전체 일관 조회나 모든 업무의 중복 방지 수단으로 사용하지 않습니다. skip된 작업의 재방문·starvation·lease/장애 복구를 별도로 설계합니다.

**통과:** 불변식 반례, 수정 시간표, 오류별 rollback/retry 범위, 최대 시도·deadline·미확정 ledger가 필요합니다. 실패한 UPDATE 한 줄만 재실행하거나 “timeout이므로 미적용”이라고 단정하면 미통과입니다.
