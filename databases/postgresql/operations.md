# PostgreSQL 운영 실습: 관측 → 가설 → 조치 → 회복

[트랙](README.md) · [공통 운영 방법](../../operations/README.md) · [장애 보고서](../../operations/incident-report-template.md)

기본 실습은 **실제 PostgreSQL 18의 상태를 읽고 장애를 구별하는 것**입니다. 원리·소스 읽기는 원인을 설명하는 수단이며, 모형 결과나 SQL 파일 존재는 운영 실습 통과가 아닙니다. 아래는 실행할 절차이며 이번 문서 작성 과정에서 서버 장애를 재현했다는 기록이 아닙니다.

## 1. 대상 확인과 정상 기준선

[환경 안내](../shared/environment.md)와 [트랙 시작 명령](README.md)을 먼저 따릅니다. `docker context show` 및 `docker context inspect`로 개인 로컬 daemon을 확인하고, 기존 볼륨은 보존합니다. 실제 minor/digest·자원 제한·행 수·설정·관측 권한을 기록합니다. 운영에서는 필요한 통계만 읽는 역할을 사용하고 실습의 `lab` 고권한 계정을 복제하지 않습니다. 쿼리 텍스트·client 주소는 민감할 수 있으므로 제출물에서 제거합니다.

```sql
SELECT version(), current_database(), current_user, pg_is_in_recovery();
SELECT clock_timestamp(), pg_postmaster_start_time();
SHOW track_io_timing;
SELECT extname, extversion FROM pg_extension WHERE extname='pg_stat_statements';
SELECT clock_timestamp(), pid, application_name, state, wait_event_type, wait_event,
       extract(epoch FROM clock_timestamp()-xact_start) AS xact_age_seconds,
       pg_blocking_pids(pid) AS blockers
FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid();
SELECT clock_timestamp(), datname, numbackends, xact_commit, xact_rollback,
       blks_read, blks_hit, temp_bytes, deadlocks, stats_reset
FROM pg_stat_database WHERE datname=current_database();
SELECT clock_timestamp(), relname, n_live_tup, n_dead_tup,
       last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10;
SELECT clock_timestamp(), wal_bytes, wal_records, wal_fpi, stats_reset FROM pg_stat_wal;
```

상시 고빈도 polling 대신 **10초 간격·5분** 기준선을 먼저 수집하고, 대기 재현 중에만 1초 간격·최대 20초로 좁힙니다. SQL은 autocommit에서 매번 새로 실행합니다. 긴 transaction의 통계 snapshot·지연된 누적 반영을 실제 정체로 오해하지 않습니다. 통계를 reset해서 정상처럼 만들지 않습니다.

| 지표 | 형식·단위·계산 | 진단할 때 같이 볼 것 |
| --- | --- | --- |
| `numbackends`, blocker 수 | gauge, 연결/세션 수; 현재 값 | pool 대기·max_connections·업무 오류율 |
| `xact_age_seconds` | gauge, 초; 열린 transaction의 나이 | idle-in-transaction, xmin, 소유 애플리케이션 |
| `xact_commit`, `deadlocks` | counter, 건; 동일 reset 구간의 Δ/Δ초 | 처리량과 오류율. rollback은 전부 장애가 아님 |
| `temp_bytes`, `wal_bytes` | counter, byte; 60초 Δ로 byte/s | 계획의 spill·WAL 발생 SQL·checkpoint·디스크 |
| `n_dead_tup` | 추정 gauge, tuple 수 | vacuum 진행·긴 snapshot·relation 크기; 정확한 bloat 아님 |
| `blks_hit/read` | counter, block 수; 같은 구간의 Δ | PostgreSQL buffer 통계이며 OS cache hit/물리 I/O와 다름 |

기준선의 workload·오류 허용치·회복 허용 범위를 먼저 정합니다. 예를 들어 동일 100개 요청에서 결과 오류 0건, 대기 세션 0개, 지연이 기준선 범위로 복귀하는 조건을 사용합니다. 보편적인 p99/캐시 비율 임계값을 암기하지 않습니다. 근거: [PG18 통계](https://www.postgresql.org/docs/18/monitoring-stats.html).

## 2. 격리 재현의 공통 준비

아래 쓰기는 **개인 로컬 실습에서 명시적으로 선택한 경우만** 실행합니다. `ops_pg_01`이 이미 있으면 중단하고 새 suffix를 모든 문장에 일관되게 적용합니다. 기존 객체를 DROP/TRUNCATE하지 않습니다. 관측 포함 최대 세션 3개, 테이블 20,000행, 쿼리 10초, 각 사건 60초가 상한입니다.

```sql
CREATE SCHEMA ops_pg_01;
CREATE TABLE ops_pg_01.accounts(id integer PRIMARY KEY, balance integer NOT NULL);
INSERT INTO ops_pg_01.accounts VALUES (1,100),(2,100);
CREATE TABLE ops_pg_01.events AS
SELECT g AS id, g%100 AS customer, repeat(md5(g::text),4) AS payload
FROM generate_series(1,20000) AS g;
ANALYZE ops_pg_01.events;
```

## 3. 세 가지 단일 노드 사건

### A. UPDATE가 느리다: CPU 부족인가, 잠금 대기인가?

가설은 행 잠금, I/O, 잘못된 접근 경로입니다. 먼저 `wait_event_type`과 `pg_blocking_pids`로 구분하고 PID→트랜잭션→업무 요청을 연결합니다.

```sql
-- 세션 A: 자기 실습 객체만, 관측 후 즉시 아래 ROLLBACK 실행
SET application_name='ops_pg_01_a';
BEGIN;
SET LOCAL idle_in_transaction_session_timeout='30s';
UPDATE ops_pg_01.accounts SET balance=balance+1 WHERE id=1;
-- 세션 B: 별도 터미널
SET application_name='ops_pg_01_b';
BEGIN;
SET LOCAL lock_timeout='8s';
SET LOCAL statement_timeout='10s';
UPDATE ops_pg_01.accounts SET balance=balance-1 WHERE id=1;
-- 대기 중 세션 C에서 위 pg_stat_activity 조회
-- B의 timeout 뒤 B에서 ROLLBACK; A에서도 ROLLBACK;
```

**조치:** 소유 세션 A의 `ROLLBACK`으로 원인을 제거합니다. 실제 장애에서는 요청 소유자 확인 없이 전체 세션을 종료하지 않습니다. 쿼리 취소가 idle transaction의 lock 해제를 보장하지 않는 점을 설명합니다. **회복:** 두 transaction 종료, blocker 0, balance가 100/100, 새 읽기/쓰기 정상. timeout은 실험 상한이며 자동 재시도 허가는 아닙니다.

### B. SELECT가 느리다: 추정 오차인가, scan인가, spill인가?

```sql
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL work_mem='64kB';
EXPLAIN (ANALYZE, BUFFERS, SETTINGS)
SELECT id,payload FROM ops_pg_01.events ORDER BY payload;
ROLLBACK;
```

`actual rows × loops`, 추정 행, sort method·disk, temp I/O를 기록합니다. 같은 SELECT를 `work_mem='4MB'`로 한 번 더 실행하고 결과 동등성 및 plan을 비교합니다. 20,000행/현재 환경에서 spill이 관측되지 않으면 미재현으로 남기고 데이터를 무한 확대하지 않습니다. **조치:** 쿼리·인덱스·통계 문제인지 확인한 뒤 해당 session 한정 변경을 평가합니다. **롤백:** `ROLLBACK`으로 LOCAL 설정 복원. **회복:** 계획·temp 변화와 같은 결과를 확인하며, 한 번의 실행 시간 차이를 p99 개선으로 부르지 않습니다. `EXPLAIN ANALYZE`는 실제 실행입니다. 근거: [PG18 EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html).

### C. 테이블이 커지고 vacuum이 효과 없어 보인다

가설은 긴 snapshot 때문에 회수 지연, autovacuum 미실행, 파일 크기에 대한 기대 오류입니다. 세션 A에서 `BEGIN ISOLATION LEVEL REPEATABLE READ; SELECT count(*) FROM ops_pg_01.events;`로 snapshot을 확보하고 30초 안에 종료합니다. 세션 B에서 `SET statement_timeout='10s'; UPDATE ops_pg_01.events SET customer=customer+1 WHERE id<=1000; VACUUM (VERBOSE) ops_pg_01.events;`를 **autocommit 개별 문장**으로 실행합니다. verbose 결과와 A의 `backend_xmin`, `pg_stat_user_tables`를 비교합니다.

**조치/롤백:** A를 `ROLLBACK`한 뒤 자기 테이블에만 VACUUM을 다시 실행합니다. B의 update는 이미 commit됐으므로 rollback됐다고 기록하지 말고, 1,000행의 변경을 기대 원장에 반영합니다. **회복:** snapshot 종료·회수 제한 변화·정확한 20,000행 확인. 통계는 비동기 추정이며 VACUUM 성공이나 파일 크기 불변만으로 bloat를 결론 내리지 않습니다. `VACUUM FULL`·글로벌 autovacuum 중지는 기본 대응이 아닙니다.

## 4. replica 지연·WAL 증가: 별도 토폴로지 사건

단일 Compose에는 replica가 없습니다. 아래는 구성한 전용 복제 실습에서만 실행하며 해당 환경이 없으면 **설계 완료/실행 미완료**입니다.

```sql
-- primary에서 읽기 전용
SELECT application_name,state,sync_state,sent_lsn,write_lsn,flush_lsn,replay_lsn,
       pg_wal_lsn_diff(pg_current_wal_lsn(),replay_lsn) AS replay_gap_bytes
FROM pg_stat_replication;
SELECT slot_name,active,restart_lsn,confirmed_flush_lsn,wal_status
FROM pg_replication_slots;
```

gap은 gauge byte이며 초 지연이 아닙니다. 수신·flush·replay 중 어디서 벌어지는지, slot 유지량·네트워크·standby I/O·긴 읽기를 경쟁 가설로 봅니다. 격리 standby에서만 소유자가 replay를 최대 20초 pause하고, 전용 fixture에 최대 100행을 넣은 뒤 반드시 resume하는 별도 실행 계획을 승인받습니다. **조치:** 발생 계층의 병목 해소, 유입 제한 또는 읽기 정책 조정. slot 삭제·무조건 승격은 기본 조치가 아닙니다. **회복:** resume 확인, LSN gap 감소, 알려진 업무 marker가 replica에서 실제 조회됨, 보존 WAL 용량 정상화. 함수의 권한·primary/standby 제약은 [관리 함수](https://www.postgresql.org/docs/18/functions-admin.html)를 확인합니다.

## 5. 제출과 통과

정상 기준선 1개 + 실제 사건 최소 2개 + 각 사건의 경쟁 가설 2개·원시 관측·한정 조치·회복 후 업무 검산을 제출합니다. 세션/설정은 원상 복귀시키고 실습 객체는 결과와 함께 보존합니다. replica/PITR/실제 storage 장애 미실행은 별도 표기하며 단일 노드 진단 통과와 구분합니다. 모델·단위 테스트 성공으로 이 관문을 대체하지 않습니다.
