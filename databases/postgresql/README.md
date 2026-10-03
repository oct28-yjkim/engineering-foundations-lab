# PostgreSQL Lab

주문 시스템의 데이터를 안전하게 저장하고, 쿼리와 운영 상태를 근거 있게 개선하는 업무를 가정합니다.

## 학습 목표

- 관계형 모델과 제약 조건으로 데이터 무결성을 표현한다.
- transaction, MVCC, isolation level, lock의 관계를 설명한다.
- B-tree를 중심으로 복합·부분·covering 인덱스를 설계한다.
- `EXPLAIN (ANALYZE, BUFFERS)`로 추측이 아닌 측정 기반 최적화를 한다.
- vacuum, analyze, 통계, connection, backup/restore의 운영 기준을 설명한다.

## 4주 학습 로드맵

| 주차 | 주제 | 산출물 |
| --- | --- | --- |
| 1주 | 관계형 모델, 제약 조건, 기본·분석 SQL | 주문 스키마와 KPI 쿼리 |
| 2주 | transaction, MVCC, isolation, lock | 동시성 재현 기록 |
| 3주 | index, planner, `EXPLAIN` | 측정 전후 비교표 |
| 4주 | vacuum, 모니터링, backup/restore, 미니 프로젝트 | 운영 runbook과 DB 설계서 |

## 0. 환경 확인

```bash
docker compose up -d postgres
docker compose exec postgres psql -U lab -d lab
```

접속 후:

```sql
SELECT version();
SELECT count(*) FROM commerce.orders;
\dt commerce.*
```

초기 데이터는 사용자 1만 명, 상품 1천 개, 주문 10만 건, 주문 항목 30만 건입니다.

편의를 위해 세션의 기본 schema를 지정할 수 있습니다.

```sql
SET search_path TO commerce, public;
```

## 1. 관계형 모델링과 무결성

### 스키마에서 표현할 것

- entity의 식별자는 `PRIMARY KEY`
- 참조 관계는 `FOREIGN KEY`
- 업무적으로 중복될 수 없는 값은 `UNIQUE`
- 허용 범위는 `CHECK`
- 값의 부재가 의미 있을 때만 nullable

제약 조건은 애플리케이션 검증을 대체하는 것이 아니라, 어떤 경로로 쓰기가 발생해도 지켜야 하는 마지막 경계입니다. 다만 foreign key와 index는 별개이므로 참조 방향의 조회·삭제 패턴에 필요한 index를 직접 검토합니다.

### 모델링 질문

- 주문 당시 상품명과 가격은 현재 상품 정보가 바뀌어도 보존되어야 하는가?
- 주문 상태 전이는 어떤 값과 순서만 허용하는가?
- 금액은 계산 결과인가, 감사 가능한 snapshot인가?
- 삭제는 물리 삭제, soft delete, 별도 이력 테이블 중 무엇이 적합한가?

## 2. 트랜잭션, MVCC, 잠금

PostgreSQL은 변경 시 행 버전을 생성하고 각 statement/transaction이 snapshot에 따라 볼 수 있는 버전을 결정합니다. 이 덕분에 일반적인 읽기와 쓰기가 서로 직접 차단하지 않지만, 같은 행을 변경하거나 DDL을 수행할 때는 lock 경합이 생길 수 있습니다.

### 두 터미널 실습

터미널 A:

```sql
BEGIN;
UPDATE commerce.accounts
SET balance = balance - 100
WHERE account_id = 1;
-- COMMIT하지 않고 대기
```

터미널 B:

```sql
SET lock_timeout = '3s';
UPDATE commerce.accounts
SET balance = balance + 100
WHERE account_id = 1;
```

별도 세션에서 대기 관계를 확인합니다.

```sql
SELECT pid, state, wait_event_type, wait_event,
       pg_blocking_pids(pid) AS blockers, query
FROM pg_stat_activity
WHERE datname = current_database() AND pid <> pg_backend_pid();
```

실습 후 A에서 `ROLLBACK;`을 실행합니다.

### 업무 규칙

- transaction은 짧게 유지하고 사용자 입력이나 외부 API 응답을 기다리지 않습니다.
- 여러 행을 갱신할 때 애플리케이션 전체에서 일관된 lock 순서를 사용합니다.
- “재시도하면 된다”면 어떤 오류 코드와 최대 재시도 횟수, idempotency 조건인지 정의합니다.
- isolation level을 높이기 전에 방지하려는 anomaly를 재현합니다.

## 3. 인덱스와 실행 계획

연습 문제는 [`sql/01_exercises.sql`](sql/01_exercises.sql), 비교용 답안은 [`sql/02_solutions.sql`](sql/02_solutions.sql)에 있습니다.

측정 기본형:

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT *
FROM commerce.orders
WHERE user_id = 42
ORDER BY ordered_at DESC
LIMIT 20;
```

확인 순서:

1. 추정 행 수와 실제 행 수가 크게 다른가?
2. 가장 많은 실제 시간과 loop를 사용한 node는 무엇인가?
3. filter로 버린 행이 많은가?
4. sequential scan이 문제인가, 전체의 큰 비율을 읽으니 합리적인가?
5. shared hit/read와 temp read/write는 어떠한가?
6. index가 WHERE와 ORDER BY를 함께 지원할 수 있는가?

### 인덱스 선택 기준

- B-tree 복합 인덱스는 일반적으로 선두 열 조건이 중요합니다.
- partial index는 일부 상태만 자주 조회할 때 크기와 쓰기 비용을 줄일 수 있습니다.
- `INCLUDE`를 이용한 covering index는 heap 접근을 줄일 수 있지만 index 크기와 쓰기 비용이 증가합니다.
- expression index의 쿼리 표현식은 index 정의와 맞아야 합니다.
- 중복·미사용 index는 쓰기, vacuum, 저장 공간 비용을 만들므로 관찰 후 제거합니다.

> `EXPLAIN ANALYZE`는 실제로 쿼리를 실행합니다. 쓰기 쿼리는 테스트 환경에서 실행하거나 `BEGIN`/`ROLLBACK`으로 보호하세요.

## 4. Vacuum과 통계

MVCC의 오래된 row version은 더 이상 보이지 않더라도 즉시 파일에서 제거되지 않습니다. 일반 `VACUUM`은 공간을 재사용 가능하게 하고 visibility map을 갱신하며, `ANALYZE`는 planner 통계를 갱신합니다. autovacuum을 무작정 끄지 않습니다.

```sql
SELECT
    relname,
    n_live_tup,
    n_dead_tup,
    last_autovacuum,
    last_autoanalyze,
    autovacuum_count,
    autoanalyze_count
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
```

`VACUUM FULL`은 테이블을 다시 쓰고 강한 lock을 요구하므로 routine maintenance 수단이 아닙니다. bloat의 원인과 재발 조건을 먼저 해결합니다.

## 5. 운영과 트러블슈팅

### 현재 활동과 장기 transaction

```sql
SELECT pid, usename, application_name, state,
       now() - xact_start AS transaction_age,
       wait_event_type, wait_event, left(query, 160) AS query
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY xact_start NULLS LAST;
```

### 누적 비용이 큰 쿼리

```sql
SELECT calls,
       round(total_exec_time::numeric, 2) AS total_ms,
       round(mean_exec_time::numeric, 2) AS mean_ms,
       rows,
       left(query, 160) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

### 운영 체크리스트

- 연결 수와 pool 크기에 근거가 있는가?
- `statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout`을 서비스 특성에 맞게 두었는가?
- backup 파일 생성이 아니라 실제 restore를 정기 검증하는가?
- RPO/RTO에 따라 base backup, WAL archive, PITR 전략이 정의됐는가?
- 장기 transaction, replication lag, dead tuples, 디스크 증가, 실패 query를 경보하는가?
- application role은 owner/superuser와 분리되고 최소 권한을 갖는가?

## 6. 미니 프로젝트

“재고를 초과 판매하지 않는 주문 생성 API”의 DB 부분을 설계합니다.

필수 결과물:

- 사용자·상품·재고·주문·주문 항목 모델과 제약 조건
- 주문 생성 transaction과 실패/재시도 정책
- 동시에 같은 상품을 주문하는 두 세션의 경합 재현
- 고객 주문 목록과 운영자 미처리 주문 목록을 위한 index
- `EXPLAIN (ANALYZE, BUFFERS)` 전후 비교
- deadlock, 장기 transaction, autovacuum 지연 대응 runbook
- backup/restore 검증 절차와 목표 RPO/RTO

## 학습 체크리스트

- [ ] 제약 조건이 잘못된 데이터를 차단하는 예를 만들었다.
- [ ] 두 세션으로 lock wait를 재현하고 blocker를 찾았다.
- [ ] index 전후 실행 계획과 buffer 사용량을 비교했다.
- [ ] window function과 `LATERAL`을 이용한 분석 쿼리를 작성했다.
- [ ] dead tuple과 autovacuum 상태를 조회했다.
- [ ] 미니 프로젝트의 동시성·운영 결정을 문서화했다.

## 공식 참고 자료

- [PostgreSQL 18 documentation](https://www.postgresql.org/docs/18/)
- [PostgreSQL tutorial](https://www.postgresql.org/docs/18/tutorial.html)
- [Indexes](https://www.postgresql.org/docs/18/indexes.html)
- [Using EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html)
- [Concurrency control](https://www.postgresql.org/docs/18/mvcc.html)
- [Routine vacuuming](https://www.postgresql.org/docs/18/routine-vacuuming.html)
- [Monitoring database activity](https://www.postgresql.org/docs/18/monitoring.html)
