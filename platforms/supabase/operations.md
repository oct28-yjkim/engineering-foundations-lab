# Supabase 운영 실습: 연결·쿼리·권한·실시간 전달 진단

[시작](README.md) · [커리큘럼](curriculum.md) · [운영 공통 규약](../../operations/README.md) · [사고 보고서](../../operations/incident-report-template.md)

기본 경로는 실제 환경에서 **정상 baseline → 병목/권한 증상 → 경쟁 가설 → SQL·서비스 로그·업무 상태 대조 → 제한된 수정 → 회복 검증**입니다. 권한 oracle JSON은 기대값이지 제품 실행이나 운영 완료 증거가 아닙니다.

## 1. 읽기 전용 preflight

사용 권한을 가진 기존 local/self-hosted/hosted 학습 프로젝트 하나를 고릅니다. 새 클라우드 프로젝트 생성·plan 업그레이드·remote link·migration을 요구하지 않습니다. 프로젝트 별칭, PostgreSQL/CLI/SDK 버전, direct/session/transaction pool 연결 종류, 주요 서비스와 기존 로그 접근 범위를 기록합니다. hosted의 Metrics API·리포트·보존 기간은 실제 plan과 권한에 따라 확인하고 없는 기능은 `관측 불가`로 둡니다. local Studio와 hosted dashboard의 기능이 같다고 가정하지 않습니다. [Metrics API](https://supabase.com/docs/guides/observability/metrics), [서비스 로그](https://supabase.com/docs/guides/observability/logs)

기존 SQL Editor 또는 **이미 승인된 DB 연결**에서 아래 읽기 전용 블록을 실행합니다. 접속 문자열·service key·JWT·cookie는 입력 예시나 보고서에 넣지 않습니다. 관측자는 필요한 통계 조회 권한만 사용하고 권한 부족을 우회하려고 superuser/BYPASSRLS를 앱에 부여하지 않습니다. 통계 전체 가시성은 역할에 따라 다르므로 NULL·숨겨진 행은 정상 0으로 해석하지 않습니다.

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
SELECT current_database(), current_user, version();
SELECT rolname, rolsuper, rolbypassrls
FROM pg_roles WHERE rolname = current_user;
SHOW max_connections;
SELECT state, wait_event_type, wait_event, count(*) AS backends
FROM pg_stat_activity
WHERE datname = current_database() AND pid <> pg_backend_pid()
GROUP BY state, wait_event_type, wait_event
ORDER BY backends DESC;
SELECT pid, state, wait_event_type, wait_event,
       extract(epoch FROM clock_timestamp() - xact_start) AS xact_age_seconds,
       pg_blocking_pids(pid) AS blocked_by
FROM pg_stat_activity
WHERE datname = current_database() AND pid <> pg_backend_pid()
  AND (state LIKE 'idle in transaction%' OR cardinality(pg_blocking_pids(pid)) > 0)
ORDER BY xact_start NULLS LAST LIMIT 20;
COMMIT;
```

오류나 timeout이면 `ROLLBACK;`으로 해당 관측 트랜잭션을 종료합니다. 공유 세션을 방치하지 않습니다. 위 결과는 query text·IP·사용자 payload를 고의로 제외합니다. 보고서에서는 PID도 사건 내 별칭으로 바꿉니다. pool의 client 수와 PostgreSQL backend 수는 다릅니다. `max_connections`에는 내부 서비스·관리 여유도 포함되므로 전부 앱에 할당할 수 없습니다. [연결·blocking 진단](https://supabase.com/docs/guides/database/connection-management)

## 2. 느린 쿼리와 RLS를 실제 역할로 확인

먼저 설치 여부·schema를 읽습니다. extension이 없다면 이 단계에서 설치하지 않습니다.

```sql
SELECT e.extname, e.extversion, n.nspname AS extension_schema
FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace
WHERE e.extname = 'pg_stat_statements';
```

확인된 schema의 `pg_stat_statements` view를 조회합니다. 아래 `extensions`는 첫 조회가 그 schema를 반환한 경우에만 사용하며 다르면 검증한 identifier로 치환합니다. 이 블록도 `BEGIN READ ONLY;`와 `SET LOCAL statement_timeout='5s';`로 감싸고 성공 시 `COMMIT;`, 오류 시 `ROLLBACK;`으로 즉시 종료합니다.

```sql
SELECT queryid, calls, total_exec_time, mean_exec_time, rows
FROM extensions.pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY total_exec_time DESC LIMIT 10;
SELECT schemaname, tablename, policyname, permissive, roles, cmd
FROM pg_policies
WHERE schemaname = 'public' AND tablename LIKE 'su_lab_%';
SELECT n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname LIKE 'su_lab_%' AND c.relkind = 'r';
```

첫 결과의 누적 `calls`, `total_exec_time`을 5분 간격 두 snapshot으로 비교합니다. Δtotal_exec_time/Δcalls는 해당 창의 **평균 실행 ms**이지 p95나 API 왕복 시간은 아닙니다. reset/restart/entry eviction이면 같은 누적 구간으로 계산하지 않습니다. 통계 reset을 실습 준비로 실행하지 않습니다. 원문 SQL은 식별자·리터럴을 포함할 수 있어 별도 권한 아래 검토합니다. [pg_stat_statements](https://supabase.com/docs/guides/database/extensions/pg_stat_statements)

RLS 목록은 의도한 정책의 존재만 증명합니다. 실제 local Auth로 로그인한 사용자 A/B와 signed-out API 요청을 [18개 권한 기대값](labs/authorization-oracle.json)에 대조합니다. 동일 역할·claim으로 확인한 계획과 결과를 사용하며 관리자의 SQL 성공을 사용자 API 성공으로 바꾸어 보고하지 않습니다. 진단 단계에서 RLS를 끄거나 service key로 대체하지 않습니다. [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)

## 3. 첫 대시보드와 지표 해석

동일 UTC 15분 정상/증상 구간, 동일 project·service·route를 고정합니다. Dashboard의 Database 연결/성능 화면, Logs의 API/Auth/Postgres/Realtime/Storage, **Project Settings → Product Reports → Realtime**의 사용 가능한 차트를 함께 확인합니다. 기능 이름·보존·제공 plan은 실제 UI에서 기록합니다. [Realtime reports](https://supabase.com/docs/guides/realtime/reports)

| 지표 | 종류·단위·창 | 잘못된 해석을 막는 대조 |
| --- | --- | --- |
| API 오류율·지연 | 같은 5분 route의 실패/전체 요청 %, 요청 duration p95 ms·표본 수 | Auth 401/403, DB timeout, Storage 오류를 분리; retry attempt와 업무 요청 분모 구별 |
| DB backend·pool client | 순간 gauge, 연결 개수; 30초 간격·5분 | active/idle/idle-in-transaction·pool mode·관리 예약분 구분 |
| lock wait·transaction age | 대기 backend 수 gauge, age 초 | blocking PID chain과 앱 transaction 경계; 오래된 query만으로 lock 단정 금지 |
| statement 비용 | cumulative calls 건·total_exec_time ms의 5분 delta | 빈번한 짧은 쿼리와 드문 긴 쿼리를 구별; 평균을 p95로 바꾸지 않음 |
| Realtime | 연결 gauge, joins/s, 메시지 구간 count·lag ms(제공 시) | 클라이언트 reconnect와 DB commit→업무 화면 반영 지연을 별도 측정; 중앙 report median을 앱 p95로 부르지 않음 |
| Storage | 업/다운로드 status별 count·latency ms·전송 bytes | metadata 행 존재와 실제 object bytes/hash, signed URL 만료 구별 |

## 4. 증상에서 회복까지

| 증상 | 경쟁 가설과 확인 순서 | 제한된 완화·원복 | 회복 증거 |
| --- | --- | --- | --- |
| API timeout·연결 오류 | pool 고갈 / 긴 transaction·lock / 느린 SQL / network. pool chart→위 activity/blocking→query 통계→API trace | 시험 앱의 중복 pool·누수·transaction 하나를 수정하고 기존 client 설정으로 되돌릴 경로 확보. 즉시 max_connections 증설·전체 session kill 금지 | 같은 작은 workload에서 대기/오류 감소, backend 수 안정, 정상·권한 음성 요청 유지 |
| 로그인 성공 뒤 빈 결과·403 | token 만료·잘못된 audience / RLS·grant / membership·schema cache 차이. Auth/API log의 상태와 실제 사용자 role·정책 revision·18개 oracle 대조 | 문제 시험 정책/앱 credential 전달 변경만 검토 후 수정; 이전 migration revision으로 검토된 역변경. RLS disable 금지 | A 허용·B 교차 tenant 거부·signed-out 거부 모두 유지, 데이터 변조 없음 |
| Realtime 연결됐으나 화면이 뒤처짐 | 앱 중복/유실 subscription / 권한 거절 / replication lag / commit 후 client 단절. join·error log→report→source PK/업무 버전→snapshot 재조회 | 시험 client의 중복 channel 정리·재접속 backoff·DB 재동기화 적용; slot drop·WAL reset 금지 | DB authoritative PK/version 집합과 화면 일치, 누락 범위 설명; WebSocket open만으로 통과 불가 |
| Storage 다운로드 실패 | signed URL 만료 / bucket·RLS 정책 / bytes 부재 / network. 동일 합성 object의 메타데이터·API status·새 승인 요청·hash 비교 | 시험 경로의 권한/URL 생성 오류만 수정·원래 정책 diff 보관; public bucket 전환으로 우회 금지 | 허용 사용자 bytes hash 일치, 타 tenant 거부, 새 URL 정상·만료 계약 유지 |

## 5. 격리 환경의 수동 사건 2개

**자기 소유 disposable local 프로젝트**에서만 재현합니다. 실제 tenant·공유 DB·내부 auth/storage 테이블은 변경하지 않습니다. read-only baseline은 기존 승인 환경에서 가능하지만 아래 fault는 별도 허가 대상입니다. 총 5분·요청 최대 50·작업 세션 최대 2개+읽기 전용 관측 세션 1개, 예상 밖 프로젝트·사용자 영향이면 발생기부터 중단합니다.

1. **짧은 lock 대기**: 사전 준비된 자기 `su_lab_` 단일 행에만 수행합니다. 세션 A에서 `BEGIN;` 후 `SET LOCAL statement_timeout='5s';`와 `SET LOCAL idle_in_transaction_session_timeout='30s';`를 설정한 뒤 해당 행을 변경하고 아직 commit하지 않습니다. 세션 B도 **명시적으로 `BEGIN;`** 한 다음 `SET LOCAL lock_timeout='3s';`와 `SET LOCAL statement_timeout='5s';`를 실행하고 같은 행을 변경합니다. autocommit 상태의 `SET LOCAL`은 사용하지 않습니다. 세션 C는 위 read-only blocking 조회로 3초 대기 동안 A→B를 확인합니다. 놓쳤으면 실패로 기록하고 timeout을 늘리지 않습니다. B의 예상 lock timeout 직후 `ROLLBACK;`, A도 30초 이내 `ROLLBACK;`으로 끝냅니다. A가 idle timeout으로 종료됐다면 자동 rollback과 재접속 후 원본 행·대기 해소를 확인합니다. 자동 sleep·무한 lock·타 세션 terminate는 사용하지 않습니다. 테이블이 없으면 먼저 준비 과제로 돌아갑니다.
2. **client 단절과 재동기화**: 자기 합성 사용자의 Realtime client 하나를 15초 이내 끊고 동일 tenant의 합성 row 한 건만 별도 승인 앱으로 변경합니다. 다시 연결해 DB snapshot을 재조회하고 PK/version이 일치하는지 대조합니다. membership 철회 시나리오라면 재조회가 거부되는 것이 기대값일 수 있습니다. 원본 fixture로 되돌리는 작업은 해당 합성 행만 대상으로 사전 정의합니다.

gate는 baseline, 최소 두 사건, 사건당 두 개 이상 가설과 배제 증거, 변경·원복, 동일 지표·권한·업무 상태의 회복입니다. SQL/JSON 정적 검사는 대체하지 못합니다. SU01–02에 연결 baseline, SU03–06에 Auth/RLS·query triage, SU07–10에 Realtime/Storage 사건, SU11–14에 변경·복구·보고서를 매핑합니다. 기존 28주·14모듈과 내부 원리/소스 학습을 유지합니다.
