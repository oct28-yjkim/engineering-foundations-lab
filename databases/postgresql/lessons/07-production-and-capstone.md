# M13–14. 운영 판단, 소스 추적, 캡스톤

## M13. 증상을 원인과 연결하고 변경 비용을 계산하기

**선수 지식:** M01–12의 S 통과와 T 설계. **범위:** S, 실제 pool·외부 failover·다중 서비스 부하는 T.

운영에서 “느리다”는 말은 적어도 연결 대기, lock 대기, CPU 계산, buffer/I/O, WAL flush, 클라이언트 전송 중 무엇인지 나눠야 합니다. 하나의 누적 통계는 원인을 확정하지 않습니다. 같은 구간의 rate·wait event·plan·OS 자원·요청 지연 분포를 연결합니다. `pg_stat_statements`의 평균은 outlier와 parameter별 편차를 숨길 수 있으므로 대표 실행과 tail을 따로 수집합니다. [pg_stat_statements](https://www.postgresql.org/docs/18/pgstatstatements.html), [관측](https://www.postgresql.org/docs/18/monitoring-stats.html).

### S 실험 1: 읽기 전용 5분 조사

M06 잠금 대기, M09 sort spill, M10 긴 snapshot을 **각각 별도의 시간 구간**에 재현합니다. 친구나 다른 학습자가 어느 것을 주입했는지 숨긴 상태로 아래 조회와 [03_internals.sql](../sql/03_internals.sql)을 사용합니다.

```sql
SELECT clock_timestamp(), pid, application_name, state,
       clock_timestamp()-xact_start AS transaction_age,
       wait_event_type, wait_event, pg_blocking_pids(pid) AS blockers,
       left(query, 160) AS query
FROM pg_stat_activity WHERE datname=current_database()
ORDER BY xact_start NULLS LAST;

SELECT queryid, calls, total_exec_time, mean_exec_time, rows,
       shared_blks_hit, shared_blks_read, temp_blks_read, temp_blks_written,
       left(query, 120) AS query
FROM pg_stat_statements
WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database())
ORDER BY total_exec_time DESC LIMIT 10;

SELECT relname, n_live_tup, n_dead_tup, last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables ORDER BY n_dead_tup DESC;
```

조사자는 5분 안에 “원인 후보 2개·판별 쿼리·반증 결과”를 제시합니다. 주입자가 통제한 세션만 `ROLLBACK`하거나 실험을 종료해 회복을 확인합니다. 실제 서비스 runbook에는 `pg_cancel_backend`가 현재 문장을, `pg_terminate_backend`가 세션을 끝낸다는 차이와 transaction 롤백·connection retry 영향을 적습니다. 여기서는 임의 PID를 종료하지 않습니다. [서버 신호 함수](https://www.postgresql.org/docs/18/functions-admin.html#FUNCTIONS-ADMIN-SIGNAL).

### S 실험 2: 읽기 역할의 최소 권한을 실제 확인

다음은 전용 이름의 NOLOGIN 역할을 transaction 안에서 만들고 마지막에 원상복구하는 실험입니다. 기존에 같은 이름의 역할이 있으면 다른 이름을 선택합니다. 오류를 의도한 블록은 psql에서 **한 명령씩** 실행합니다.

```sql
BEGIN;
CREATE ROLE m13_lab_reader NOLOGIN;
GRANT USAGE ON SCHEMA commerce TO m13_lab_reader;
GRANT SELECT ON commerce.orders TO m13_lab_reader;
SET LOCAL ROLE m13_lab_reader;
SELECT current_user, count(*) FROM commerce.orders;
SAVEPOINT permission_probe;
SELECT count(*) FROM commerce.accounts;
-- permission denied를 확인한 뒤 다음 두 문장을 수동 실행한다.
ROLLBACK TO SAVEPOINT permission_probe;
RESET ROLE;
ROLLBACK;
```

상위/기존 PUBLIC grant가 있다면 거절되지 않을 수 있습니다. 그 경우 권한 경로를 조사한 결과가 이 실험의 핵심입니다. 기존 권한을 지워서 답을 맞추지 않습니다. 역할 membership, schema USAGE, object grant, owner/superuser 우회를 구분합니다. 실제 앱에서는 migration owner와 runtime role을 나누고, 다음에 생길 테이블에는 `ALTER DEFAULT PRIVILEGES`가 **객체 생성 역할별로** 적용된다는 점까지 설계합니다. [권한](https://www.postgresql.org/docs/18/ddl-priv.html), [default privileges](https://www.postgresql.org/docs/18/sql-alterdefaultprivileges.html).

### 변경 실험 설계: DDL도 부하와 잠금을 갖는다

복사한 주문 테이블에 nullable 새 열을 추가하고, 작은 batch backfill, 제약 검사, 앱 전환, 필요 시 정리까지 expand/contract 순서를 설계합니다. 각 단계의 lock mode·최대 대기·실패 후 재실행 여부를 공식 DDL 문서에서 확인합니다. `CREATE INDEX CONCURRENTLY`는 쓰기를 완전히 막지 않는 장점과 다중 단계·실패 시 invalid index·transaction block 제약을 함께 갖습니다. [인덱스 생성](https://www.postgresql.org/docs/18/sql-createindex.html), [ALTER TABLE](https://www.postgresql.org/docs/18/sql-altertable.html).

실행 과제는 복사본에 장기 읽기 transaction을 만들고 `lock_timeout`이 있는 DDL이 어떻게 대기/실패하는지 관찰하는 것입니다. 원본 commerce에 장기 lock을 걸지 않습니다. partitioning 후보를 검토할 때는 pruning, local index, uniqueness/partition key 제약, partition 수 증가의 planning 비용, retention용 detach/drop 절차를 포함합니다. partition을 추가하는 것만으로 전체 scan이 빨라지지 않는 반례도 제출합니다. [테이블 분할](https://www.postgresql.org/docs/18/ddl-partitioning.html).

**예상 증거:** 주입한 세 원인을 서로 구별하는 관측치, 읽기 권한의 성공/실패, DDL 대기와 실패 후 catalog 상태, 조사부터 회복까지 시간표.

**실패 양상:** blocker가 아닌 blocked query만 취소, 인덱스부터 추가, pool wait를 SQL time으로 해석, transaction pooling에서 session setting을 가정, migration role을 앱 계정으로 재사용, index 생성 실패 뒤 invalid index를 놓치기.

**산출물·통과:** 세 장애 모두 원인 후보를 반증으로 좁히고 적절한 조치를 제안합니다. SLO(예: 사용자 요청 p95·timeout 비율·오류율)의 측정 지점을 명시하고, pool admission/timeout budget·DB 자원 제한을 함께 제출합니다. 권한 시험과 복사본 migration의 전후 검산·rollback 기준을 기록합니다. 외부 pool 미구성 상태는 실제 부하 검증으로 표기하지 않습니다.

## M14. 소스와 실험을 연결하는 최종 과제

**선수 지식:** M01–13, C 구조체·포인터·함수 호출, Git diff, 디버거 기본. **범위:** S 캡스톤, B 소스 빌드, T 복구·복제. 모든 범위가 끝나야 고급 검증 통과입니다.

소스 코드는 함수 이름을 읽기 위한 사전이 아닙니다. 어떤 입력 상태에서 어떤 분기를 지나고, 그 분기가 어떤 불변식을 보호하며, 사용한 snapshot·lock·memory context를 누가 해제하는지 확인합니다. 문서의 계약, 코드의 구현, 자기 환경의 관측을 구분하면 구현 세부가 버전별로 바뀌어도 판단을 유지할 수 있습니다.

### B 실험: 최소 재현을 구현 경계까지 추적

1. [소스 읽기 지도](../source-reading.md)의 절차로 실제 서버 버전/이미지 digest와 소스 태그·SHA를 연결합니다. debug binary와 데이터 클러스터는 학습용으로 별도 생성합니다.
2. M05 snapshot, M07 selectivity, M10 vacuum 중 하나를 30줄 이하 SQL 또는 2세션 schedule로 축소합니다. 데이터가 작아도 현상의 의미가 유지되는지 먼저 확인합니다.
3. 일치하는 소스를 debug/assert 빌드하고 기본 테스트 결과를 저장합니다. production 프로세스에 debugger를 붙이지 않습니다.
4. 선택한 세션의 backend PID에 연결해 목표 함수 breakpoint, 호출 스택, 입력 구조체 값, 분기 조건을 저장합니다. 컴파일 최적화·inlining으로 보이지 않는 값은 빌드 설정과 함께 기록합니다.
5. 가설에 필요한 상태 한 가지를 바꾼 두 번째 실행을 추적합니다. 분기가 달라지는지 비교합니다. 발견한 차이가 정상 동작인지 버그 후보인지 판단합니다.
6. 결과 SQL은 `src/test/regress`, 동시성 schedule은 `src/test/isolation`의 형식을 조사해 최소 테스트를 작성합니다. 엔진 patch는 실제 결함 근거가 있을 때만 제안하고, 정상 동작이라면 설명·회귀 방지 테스트만으로 충분합니다.

**예상 증거:** 버전 일치 기록, build/test 로그, 두 입력의 stack·상태 차이, 재현 SQL과 expected 결과의 근거. debugger output을 꾸며 넣거나 코드에서 추측한 값을 실측으로 표시하지 않습니다.

### S/T 캡스톤: oversell·중복 주문·복구를 함께 다루기

기존 commerce는 읽기용 기준 데이터로 유지하고 별도 `capstone_pg` schema에 주문·재고·결제 시도·outbox 모델을 설계합니다. 문제는 재고 10개인 상품에 30개 동시 구매 요청과 동일 idempotency key의 재전송이 들어오는 경우입니다. 결제 서비스의 외부 성공은 DB transaction과 원자적이지 않으므로 그 경계를 명시합니다.

필수 구현·검증은 다음과 같습니다.

- 재고 음수 방지, 승인 수량 상한, 주문/항목 금액 일치, idempotency key 중복 거절을 데이터와 transaction으로 검증합니다. 락 순서·격리 수준·retry 정책을 선택하고 대안을 기각한 이유를 적습니다.
- 고객 주문 목록, 운영 pending queue, 재고 부족 감시의 query를 설계합니다. 동률 정렬과 pagination 의미를 고정하고 통계·인덱스·WAL/쓰기 비용을 포함해 측정합니다.
- 1/5/10/30 동시 요청 수준에서 throughput·p50/p95·timeout·serialization/deadlock 비율을 비교합니다. 부하 생성 방식, warmup, 요청 간격, 재시도 포함 여부를 명시합니다. DB 처리 시간과 요청 전체 시간을 분리합니다.
- M06 lock, M09 spill, M10 long snapshot 중 2개를 주입하고 관측·완화·되돌림을 실행합니다. 단일 설정 변경으로 두 장애가 모두 해결된다고 가정하지 않습니다.
- S에서는 별도 DB에 논리 복원하고 불변식·role/query를 검산합니다. T에서는 M11 PITR와 M12 replica/failover 후 외부 승인 원장을 대조합니다. 미실행 영역을 보고서 첫 페이지에 표시합니다.
- [소스 지도](../source-reading.md)의 query 실행, visibility, WAL/vacuum 중 3경로를 각 실험과 연결합니다. 각 경로에 “필수 조건·보호하는 불변식·실패/해제 경로”를 설명합니다.

**실패 양상:** 성공 요청 수만 세어 중복 부작용 누락, idempotency key가 같은데 payload가 다른 요청 미처리, 재시도 후 외부 결제를 두 번 수행, 벤치마크에서 오류 요청 제외, 백업을 생성하고 실제 restore를 생략.

**산출물·통과:** SQL/부하 도구/환경 지문/불변식 검사/실행 로그/plan/장애 타임라인/복구 runbook/소스 설명을 한 묶음으로 제출합니다. 다른 사람이 설명을 받지 않고 재현해 동일한 업무 불변식을 확인해야 합니다. 점수와 필수 게이트는 [평가 기준](../assessment.md)을 따르며 미실행 T/B는 총점과 별개로 고급 완료를 제한합니다.

이후 확장은 [공통 캡스톤](../../shared/capstone.md)의 PostgreSQL→ClickHouse 변경 전달과 재검산으로 연결합니다. PostgreSQL의 commit 보장과 분석 저장소의 갱신 지연·중복 처리 보장을 별도로 설명합니다.
