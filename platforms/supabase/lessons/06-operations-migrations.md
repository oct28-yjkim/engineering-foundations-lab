# SU11–SU12. 변경을 배포하고 상태를 복구하기

[커리큘럼](../curriculum.md) · 이전: [Storage/Functions](05-storage-functions.md) · 다음: [연구와 캡스톤](07-research-capstone.md)

<a id="su11"></a>
## SU11 migration, CI, branching과 connection budget · LOCAL-PREP / BUILD / HOSTED-DESIGN

**선수 조건:** SU02, SU06, SU10. 실험은 [독립 CLI 프로젝트](../labs/local-lab.md) 안에서 수행합니다. hosted link/push/deploy나 계정 변경은 이 교재를 읽었다는 이유로 자동 승인되지 않습니다.

### 원리

migration은 최종 CREATE TABLE 파일만이 아니라 순서가 있는 상태 전이입니다. schema가 같아 보여도 policy, grant, function owner/search_path, publication, extension, seed data가 다를 수 있습니다. 로컬에서 UI로 바꾼 결과와 migration history가 어긋나면 새 환경을 만들 때 재현되지 않습니다. [Local migrations](https://supabase.com/docs/guides/local-development/database-migrations), [배포 migrations](https://supabase.com/docs/guides/deployment/database-migrations)

앱과 DB가 한 순간에 동시에 교체되지 않는다면 expand → 호환 코드 → backfill/검증 → contract 순서가 필요합니다. “이전 앱으로 rollback”과 “데이터 손실 없이 schema downgrade”는 다른 작업입니다. 이미 새 형식으로 쓴 데이터를 버리는 down migration은 단순 rollback이 아닙니다.

Supabase preview branch는 별도 환경이며 credential과 데이터 포함 정책을 확인해야 합니다. Git branch를 만들었다고 hosted DB가 만들어지는 것은 아니고, hosted branching을 시작하면 비용·외부 상태 변화가 생깁니다. 기본 데이터 없는 preview도 seed에 production 개인정보를 넣으면 안전하지 않습니다. [Branching](https://supabase.com/docs/guides/deployment/branching)

### 실험: 두 경로로 같은 계약에 도달하기

SU05–06 SQL을 검토된 학습자 migration 파일로 옮기고 실제 Auth UUID fixture는 schema migration과 분리합니다. environment마다 달라지는 비밀/UUID를 source에 고정하지 않습니다. 다음 CLI는 **학습자가 준비한 로컬 작업 폴더**에서 migration 파일을 새로 생성하는 예이며 현재 저장소에서 실행한 명령이 아닙니다.

```text
supabase migration new su11_add_review_note
```

생성 파일에 아래 additive 변경을 넣습니다. 기존 `title` 계약은 유지하고 초기에는 application에서 `review_note`가 NULL이어도 동작하게 합니다.

```sql
BEGIN;
ALTER TABLE public.su_lab_tasks ADD COLUMN review_note text;
ALTER TABLE public.su_lab_tasks ADD CONSTRAINT su_lab_review_note_size
CHECK (review_note IS NULL OR length(review_note) <= 500);
-- title 수정 권한을 자동으로 전체 UPDATE 권한으로 넓히지 않는다.
COMMIT;
```

새 column을 사용자에게 쓰기 허용하려면 기존 row-level 정책과 필요한 **column grant**를 별도 변경·검증합니다. `SELECT *`를 사용한 API나 SETOF 반환형에 새 column이 드러나는지 확인합니다. 민감 정보를 추가할 때 column 접근 검토가 필요한 이유입니다.

BUILD CI harness는 다음 두 경로를 별도의 폐기 가능한 local 환경에서 실행합니다. 실제 전체 환경 구성과 pipeline 코드는 학습자 산출물입니다.

- **빈 환경 경로:** 고정 버전 서비스 준비 → migration 전체 적용 → synthetic Auth 생성/fixture → 18개 oracle → RPC/view/API 검증.
- **upgrade 경로:** 이전 migration+fixture → 구버전 앱의 계속된 요청 → 신규 migration → 구/신규 앱 호환성 → 같은 oracle.

두 경로의 `pg_policies`, `information_schema.column_privileges`, constraints, function 정의, 노출 schema·publication을 정규화해 비교합니다. migration 생성 diff를 그대로 신뢰하지 말고 불필요한 DROP/권한 확장/definer 변경이 없는지 검토합니다. `db reset` 같은 초기화는 **검증한 폐기 가능 로컬 대상만** 재생성하는 작업이며 기존 DB, 원격 project, 중요한 volume에는 적용하지 않습니다. 단계별 명령/flag는 설치 CLI `--help`와 [CLI reference](https://supabase.com/docs/reference/cli/supabase-migration-new)에서 확인합니다.

### 장애 주입과 pooling

별도 local 세션이 `su_lab_tasks`를 잡은 transaction을 열고 있는 동안 migration이 필요한 lock을 얻지 못하는 상황을 만듭니다. migration 세션에 짧은 `lock_timeout`·`statement_timeout`을 두고 실패 로그·history·실제 schema를 대조합니다. transaction 안의 변경과 밖의 concurrent index 작업을 같은 rollback 보장으로 설명하지 않습니다. 무조건 lock 보유 backend를 종료하지 말고 실험 세션만 정상 rollback합니다.

serverless instance 수 증가를 가정해 client pool·Supavisor·DB connection budget을 다시 계산합니다. transaction pooling에서는 session state와 prepared statement 지원을 해당 mode/driver별로 검증합니다. policy SQL의 request context가 다음 transaction으로 새어 나가지 않게 `SET LOCAL` 등 경계를 확인하며, 사용자 session client를 전역 공유하는 SSR 실수와 DB pool 재사용은 구별합니다. [연결 및 pool 제약](https://supabase.com/docs/guides/database/connecting-to-postgres)

**통과:** 빈/upgrade 경로 모두 oracle18개 성공, 동일 schema·권한 계약, 기존 앱 호환, lock timeout 후 상태 설명, rollback/forward-fix 결정표. 실제 hosted branch/remote deployment는 미실행이면 명시하고 local CI 성공으로 대체하지 않습니다.

<a id="su12"></a>
## SU12 backup, restore, 관측과 비밀 회전 · LOCAL-PREP / BUILD / HOSTED-DESIGN

**선수 조건:** SU09 객체 manifest, SU10 command ledger, SU11 migration. RPO는 허용 데이터 손실, RTO는 실제 서비스 검증까지 걸리는 복구시간으로 정의합니다.

### 원리

DB backup은 Storage 객체 bytes를 포함하지 않습니다. metadata가 돌아왔는데 object가 없거나, old DB가 최신 bytes를 가리키는 상태가 생길 수 있습니다. 프로젝트 설정·function code·환경 비밀·Auth identity/session·외부 provider 설정 역시 백업 범위를 각각 정해야 합니다. managed backup/PITR의 가용성·보존·중단시간은 실제 프로젝트/플랜 조건을 확인합니다. [Database backups](https://supabase.com/docs/guides/platform/backups)

restore 성공의 기준은 프로세스 healthy가 아니라 업무 oracle입니다. 관리자 조회가 성공하고 RLS가 빠져 모든 tenant가 보이는 복구는 실패입니다. PITR로 membership 변경 이전으로 돌아가면 탈퇴 사용자 권한이 되살아날 수도 있으므로 보안 변경의 재적용과 credential 폐기를 runbook에 포함합니다.

### 실제 실행 과제: 제한된 application data restore

첫 실험은 **SU05의 두 public table과 SU09의 테스트 객체**만 복원합니다. 전체 Auth/session/PITR 복구를 수행했다고 주장하지 않습니다. source/target은 서로 다른 폐기 가능 local Supabase 프로젝트이며 target에는 동명 application table이 없어야 합니다. 서비스 버전과 `auth.uid()` helper·roles가 준비된 target인지 확인합니다.

1. 쓰기를 잠시 멈추고 원본3행 및 membership, 객체 key·byte count·SHA-256, 사용한 migration revision을 원장으로 저장합니다. 실제 사용자/비밀정보는 포함하지 않습니다.
2. source의 로컬 DB 연결을 `PGHOST/PGPORT/PGDATABASE/PGUSER`와 안전한 password 전달 방식으로 지정합니다. dump를 `.gitignore`된 실습 증거 폴더에 저장하며 DB URL을 report에 남기지 않습니다.
3. 다음 명령은 두 table의 schema/data/policy/ACL 백업 범위를 확인하는 예입니다. dump 목록을 읽어 scope를 검증합니다. 큰 서비스 전체 backup의 대체가 아닙니다.

```text
pg_dump --format=custom --no-owner --file=su12-fixture.dump --table=public.su_lab_memberships --table=public.su_lab_tasks
pg_restore --list su12-fixture.dump
```

4. 별도 target의 실제 host/port·DB name·환경 표시를 읽기 전용 SELECT로 확인한 뒤 접속 설정을 target으로 바꿉니다. target에 같은 table이 있으면 중단합니다. `--clean`으로 기존 데이터를 지우지 않습니다.

```text
pg_restore --single-transaction --exit-on-error --no-owner --dbname=postgres su12-fixture.dump
```

5. source의 Auth 전체 데이터를 위 dump로 백업한 것은 아닙니다. target 테스트 Auth 사용자들을 정상 API로 다시 만들고 **가명→source UUID→target UUID mapping**에 따라 이 실습 table의 owner/membership만 관리 transaction으로 변환합니다. 필요한 view/RPC는 검토된 별도 migration으로 복구합니다. 이것은 명시적 **identity remapping 실험**이며 production Auth 복원 절차가 아닙니다.
6. 객체 bytes는 source Storage API로 별도 내보내고 hash manifest를 만든 뒤, target의 동일한 private bucket 설정·RLS를 구성하고 관리 Storage API로 재업로드합니다. user UUID가 path에 있다면 mapping에 따른 새 key를 정하고 manifest에 이전/새 key를 남깁니다. 내부 storage metadata를 직접 복사해 bytes가 복구됐다고 하지 않습니다.
7. target의 실제 사용자 세션으로 oracle18개, view/RPC, private object 접근, bytes checksum을 반복합니다. source에는 복구 실험을 이유로 데이터를 삭제하지 않습니다.

RPO 목표는 사전에 정한 허용 손실 범위입니다. 실제 복구에서는 백업의 일관성 기준시점과 복구된 command 집합을 확인하고, 장애 전 성공 응답한 command 원장과 대조해 **사라진 ID·개수·시간 범위**를 측정합니다. 쓰기 정지 시각과 마지막 command 시각의 차이는 단순 idle 시간일 수 있으므로 그것만으로 손실을 계산하지 않습니다. RTO는 복구 시작부터 authz·bytes 검증 완료까지 측정하며 migration/CLI command 수행시간만 적지 않습니다. 새 target이 독립 DB이지만 같은 컴퓨터에 있으면 zone 장애 내구성을 검증한 것은 아닙니다.

SU10/SU14의 command 앱을 복원할 때는 위 두 table만으로 부족합니다. 실제 구현한 `su_lab_command_ledger`와 `su_lab_task_audit`도 같은 일관된 dump에 명시적 `--table=public.su_lab_command_ledger --table=public.su_lab_task_audit` 옵션으로 포함하고, 해당 RPC/migration·actor UUID remapping도 복구합니다. ledger만 오래된 시점으로 되돌리면 이미 처리한 command를 새 요청으로 판단할 수 있습니다. 복원 뒤 기존 command를 재전송해 business mutation이 늘지 않는지 추가 검사합니다. 이 확장을 하지 않은 증거는 두-table 실험 통과이지 command 앱 전체 복원 통과가 아닙니다.

### 운영 복구와 관측 설계

HOSTED-DESIGN에서는 특정 오삭제 시점 전후의 sentinel command를 정하고, 실제 지원되는 PITR/restore 방법·권한·다운타임·target·비밀 회전·앱 재연결·Storage bytes 별도 복원·Auth 세션 정책을 작성합니다. 실제 승인된 테스트 프로젝트에서 restore하지 못했다면 “설계 완료, 실행 미검증”으로 남깁니다. SQL 데이터 복원만으로 API signing keys, 모든 사용자 세션, provider 설정까지 동일하다고 주장하지 않습니다.

관측은 request correlation ID로 gateway/API/Function/DB 시간을 연결하고, 인증 거부·RLS0행·권한 에러·pool 대기·DB lock·rate limit을 구별합니다. local에서는 서비스 로그와 `pg_stat_activity`를 확인할 수 있지만 hosted Logs/Metrics 기능과 retention이 같다는 보장은 없습니다. [Logs](https://supabase.com/docs/guides/observability/logs), [Metrics](https://supabase.com/docs/guides/observability/metrics)

```sql
SELECT application_name, state, wait_event_type, wait_event, count(*)
FROM pg_stat_activity WHERE datname=current_database()
GROUP BY application_name, state, wait_event_type, wait_event;
SELECT relname, n_live_tup, n_dead_tup, last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables WHERE relname LIKE 'su_lab_%';
```

관측 부하 실험은 제한된 연결 수와 timeout을 사용하고 차단 세션이 자신의 실험인지 확인합니다. 에러 유도 후 경보가 원인을 구분하는지 테스트하되 JWT/쿠키/업로드 내용/DB password는 telemetry에서 제거합니다. signing key와 server secret의 회전 대상·소비자·cache·rollback 가능 여부를 구분한 runbook도 제출합니다.

**통과:** 다른 target에서 실제18개 authz oracle·객체 hash 일치, 측정 RPO/RTO, backup scope 누락표, 탐지→복구→검증 시간선. bytes 복원 없이 “Supabase 백업 완료”, 미실행 PITR을 “복구 완료”로 쓰면 재수행합니다.
