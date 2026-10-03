# M01–02. 관계 모델에서 backend까지

## M01. SQL의 의미를 먼저 고정하기

**선수 지식:** 터미널에서 psql 접속, 집합·정렬·정수 계산. **범위:** S, 현재 단일 노드.

관계 모델은 값의 관계와 제약을 기술합니다. SQL 결과는 기본적으로 중복을 허용하므로 집합 대수와 그대로 같지 않습니다. NULL은 빈 문자열도 0도 아니며 비교 결과가 UNKNOWN일 수 있습니다. `WHERE`는 TRUE인 행만 남깁니다. 따라서 조인을 빠르게 만드는 일보다 무엇을 한 건으로 집계하는지 먼저 결정해야 합니다. [공식 SQL 표현식](https://www.postgresql.org/docs/18/sql-expressions.html), [비교·NULL](https://www.postgresql.org/docs/18/functions-comparison.html).

기본키는 식별을, 외래키는 참조 유효성을, CHECK는 행의 허용 상태를 표현합니다. `CHECK (price >= 0)`만으로 NULL을 금지하지 못합니다. 여러 행의 합계나 상태 전이 같은 불변식은 행 CHECK 하나로 해결되지 않습니다. 함수 종속 `order_id → user_id, ordered_at`와 상품 가격의 시간적 의미를 써 보고, 주문 당시 가격을 별도로 저장하는 이유를 설명합니다. [제약 조건](https://www.postgresql.org/docs/18/ddl-constraints.html).

### 실험 1: 5행으로 SQL 반례 만들기

다음 코드를 같은 psql 세션에서 실행하기 전 각 결과를 종이에 계산합니다. 임시 테이블은 세션이 종료되면 사라집니다.

```sql
CREATE TEMP TABLE m01_values (id integer, amount numeric, label text);
INSERT INTO m01_values VALUES
  (1, 10, 'a'), (1, 10, 'a'), (2, NULL, 'b'), (3, 0, NULL), (4, 20, 'c');
SELECT count(*), count(amount), sum(amount), avg(amount) FROM m01_values;
SELECT id FROM m01_values WHERE amount <> 10 ORDER BY id;
SELECT id FROM m01_values WHERE id NOT IN (SELECT NULL::integer);
SELECT DISTINCT id, amount FROM m01_values ORDER BY id;
SELECT id, amount,
       sum(amount) OVER (ORDER BY id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running
FROM m01_values ORDER BY id;
```

마지막 쿼리는 `id=1` 동률 행의 순서를 결정하지 않습니다. 금액을 다르게 바꾸어 순서 의존성을 확인하고 업무 식별자를 추가해 정렬을 완전하게 만듭니다. `ROWS`와 기본 window frame의 차이는 peer group이 있는 데이터로 검증합니다. [윈도 함수](https://www.postgresql.org/docs/18/functions-window.html).

### 실험 2: 주문 grain과 가격의 의미

```sql
SELECT count(*) AS joined_rows, count(DISTINCT o.order_id) AS orders
FROM commerce.orders o JOIN commerce.order_items i USING (order_id);

SELECT o.order_id, o.total_amount,
       sum(i.quantity * i.unit_price) AS lines_amount,
       o.total_amount - sum(i.quantity * i.unit_price) AS difference
FROM commerce.orders o JOIN commerce.order_items i USING (order_id)
GROUP BY o.order_id, o.total_amount
ORDER BY o.order_id LIMIT 10;
```

현재 v2 생성 데이터는 주문 금액을 항목 합계와 일치시킵니다. 위 결과에서 차이가 0인지 검산하고 전체 주문에 대한 불일치 건수 검사로 확장합니다. 기존 볼륨에는 이전 생성 데이터가 남을 수 있으므로 결과가 다르면 실제 초기화 버전과 수정 이력을 먼저 확인합니다. 배송비·할인 차이로 설명하려면 해당 항목을 모델에 먼저 정의해야 합니다. 조인 후 주문 금액을 SUM하면 같은 주문이 항목 수만큼 중복되는 문제를 작은 예로 증명합니다.

추가 과제는 월별 순매출/주문 수/구매자 수를 각각 정의하고 `[월 시작, 다음 월 시작)` 범위와 시간대를 명시하는 것입니다. `timestamptz`는 입출력 시간대와 저장 의미를 나누어 이해합니다. [날짜·시간 타입](https://www.postgresql.org/docs/18/datatype-datetime.html).

**예상 증거:** NULL 포함/미포함 집계 차이, join fan-out, 주문/항목 금액 차이의 원본 결과. 특정 성능 수치는 요구하지 않습니다.

**실패 양상:** DISTINCT로 중복 원인을 덮기, CHECK가 NULL까지 막는다고 믿기, float로 금액 계산, 날짜 종료 조건에 `23:59:59` 사용, 구매자별 집계를 주문별 집계로 혼동하기.

**산출물·통과:** 5행 손계산 표와 SQL 출력 일치, 잘못된 SQL 3개와 수정 근거, 주문/재고 모델의 후보키·함수 종속·불변식 5개를 제출합니다. 주어진 쿼리가 빠르더라도 금액 의미가 틀리면 통과하지 않습니다.

## M02. 요청·세션·프로세스·프로토콜

**선수 지식:** M01, 프로세스와 파일 구분. **범위:** S. packet capture와 pool 서버 설치는 선택 설계 과제입니다.

연결이 만들어지면 backend가 프로토콜 메시지를 받아 SQL을 parse/analyze하고 rewrite와 planning을 거쳐 executor를 동작시킵니다. prepared statement의 parse 단계와 execute 시점의 계획 선택을 같은 것으로 보지 않습니다. simple protocol의 SQL 문자열 요청과 extended protocol의 Parse/Bind/Execute를 구분해야 pool의 prepared statement·세션 상태 문제를 설명할 수 있습니다. [처리 경로](https://www.postgresql.org/docs/18/overview.html), [메시지 흐름](https://www.postgresql.org/docs/18/protocol-flow.html).

Backend 외에 checkpointer, background writer, WAL writer, autovacuum 등이 다른 책임을 갖습니다. CPU가 바쁜 backend, 클라이언트를 기다리는 idle backend, 열린 transaction을 가진 idle backend는 운영 영향이 다릅니다. 연결 수는 처리량과 동의어가 아닙니다. pool의 대기 시간과 DB 실행 시간을 나눠야 포화 지점을 찾습니다. [서버 구조](https://www.postgresql.org/docs/18/tutorial-arch.html), [활동 관측](https://www.postgresql.org/docs/18/monitoring-stats.html).

### 실험: 세 세션의 생명주기

터미널 A/B/C에서 각각 README의 psql 명령으로 접속합니다. A:

```sql
SET application_name = 'm02-A';
BEGIN;
SELECT pg_backend_pid(), pg_current_xact_id_if_assigned();
SELECT count(*) FROM commerce.orders;
-- 열린 트랜잭션을 유지하고 다음 명령을 입력하지 않는다.
```

B:

```sql
SET application_name = 'm02-B';
SELECT pg_backend_pid(), pg_sleep(15);
```

C에서 B가 실행 중일 때:

```sql
SELECT pid, backend_type, application_name, state,
       wait_event_type, wait_event, xact_start, query_start,
       backend_xid, backend_xmin
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY pid;
```

B가 끝난 뒤 같은 조회를 다시 실행합니다. A에서 `ROLLBACK;`한 뒤 다시 비교합니다. 일반 읽기 트랜잭션에 실제 XID가 아직 배정되지 않을 수 있다는 점과 snapshot/horizon 보유는 별개임을 기록합니다. `state='active'`가 CPU를 사용한다는 뜻은 아니며 `pg_sleep`도 active일 수 있습니다.

### 계획·세션 상태 실험

```sql
PREPARE m02_orders(bigint) AS
SELECT order_id FROM commerce.orders WHERE user_id = $1;
EXPLAIN EXECUTE m02_orders(42);
SELECT name, parameter_types, generic_plans, custom_plans
FROM pg_prepared_statements WHERE name = 'm02_orders';
DEALLOCATE m02_orders;
```

다른 세션에서 위 prepared statement가 보이는지 확인하고, transaction pooling에서 세션 SET, 임시 테이블, prepared statement가 어떤 조건에서 유효한지 제품별 확인 항목을 만듭니다. 이 저장소에는 pool이 설치되어 있지 않으므로 실제 pool 호환성을 검증했다고 쓰지 않습니다. [PREPARE](https://www.postgresql.org/docs/18/sql-prepare.html).

**예상 증거:** A의 열린 transaction, B의 active→idle 전이, wait event와 상태가 다른 정보를 주는 사례, 준비된 문장의 세션 범위.

**실패 양상:** `pg_stat_activity.query`를 항상 현재 실행 중인 SQL로 해석하기, 모든 idle을 장애로 판단하기, 풀 대기를 DB 실행 시간으로 합치기, 긴 transaction을 외부 API 호출 사이에 유지하기.

**산출물·통과:** 프로토콜→backend→계획→executor→buffer/WAL 경로를 그립니다. 상태 3종을 실제 PID와 연결하고, 풀 크기를 늘렸을 때 생길 병목 3개와 필요한 지표를 제시합니다. [소스 지도](../source-reading.md)의 `postgres.c`, `analyze.c`, `execMain.c`에서 경계 함수 3개를 찾으면 완료입니다.
