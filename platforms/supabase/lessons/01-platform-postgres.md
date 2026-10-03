# SU01–SU02. 플랫폼의 경계와 PostgreSQL 기반

[커리큘럼](../curriculum.md) · 다음: [Auth와 JWT](02-auth-jwt.md)

<a id="su01"></a>
## SU01 요청이 통과하는 신뢰 경계 · LOCAL-PREP / BUILD

**선수 조건:** HTTP request/response, 프로세스·포트, SQL SELECT. 모르면 [공통 기반](../../../databases/shared/foundations.md)을 먼저 보충합니다.

### 원리

Supabase는 PostgreSQL을 중심으로 여러 독립 서비스가 연결된 플랫폼입니다. Auth는 사용자 세션을, PostgREST는 HTTP 요청을 DB 쿼리로 연결하는 경로를, Storage는 객체 접근을, Realtime은 채널과 변경 전달을 담당합니다. 관리 UI에서의 성공과 application role 요청의 성공은 다른 검증입니다. Admin DB 접속으로 보이는 행은 일반 사용자가 읽어도 되는 행이라는 증거가 아닙니다. [공식 아키텍처](https://supabase.com/docs/guides/getting-started/architecture)

API key, user JWT, DB password, management token은 서로 대체 가능한 “접속 키”가 아닙니다. 애플리케이션 식별과 최종 사용자 인증, SQL 권한, control plane 관리 권한을 분리해야 유출 범위를 계산할 수 있습니다. 반대로 모든 요청을 관리용 credential로 우회시키면 UI에서 tenant를 가려도 서버의 데이터 경계는 사라집니다.

호출 경로는 성능과 장애 모델도 바꿉니다. REST 한 번, RPC 한 번, 여러 REST 요청의 연속은 같은 atomic transaction이 아닙니다. DB commit 뒤 Realtime 연결이 끊길 수 있고, 객체 bytes가 저장된 뒤 별도 업무 row 생성이 실패할 수 있습니다. 서비스별 성공의 의미와 보상할 주체를 도식에 표시합니다.

### 실험: 플랫폼을 설치했다고 가정하지 않기

[환경 준비](../labs/local-lab.md)를 따라 학습자가 독립 로컬 프로젝트를 준비합니다. 준비가 끝나지 않았다면 아래 SQL/API 실험은 미실행입니다. 다음은 **관리 권한의 로컬 SQL 연결**에서 읽기 전용 조사입니다.

```sql
SELECT version(), current_database(), current_user, session_user;
SELECT extname, extversion FROM pg_extension ORDER BY extname;
SELECT nspname FROM pg_namespace
WHERE nspname IN ('public','auth','storage','realtime') ORDER BY nspname;
SELECT rolname, rolsuper, rolbypassrls
FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role','postgres');
SHOW max_connections;
```

CLI version, 실제 실행 image/digest, SDK lockfile, exposed schema, signing key 방식, 연결 주소의 종류를 **비밀값 없이** `environment.md` 증거에 남깁니다. 확인 불가능한 hosted 내부 image는 “미공개/미확인”으로 기록합니다. 추측한 upstream tag를 실제 배포 버전으로 쓰지 않습니다.

BUILD 과제는 Auth 로그인, REST 조회, RPC, Realtime 구독, Storage 다운로드, Function 호출의 6개 경로를 그리는 것입니다. 각 화살표에 transport·credential 종류·검증 주체·DB role·상태 저장 위치를 표시합니다. 각 경로에서 timeout 직전/직후 commit이 될 수 있는 곳을 1개 이상 찾습니다. gateway 제품 이름은 실제 topology에서 확인한 경우에만 적습니다.

**독립 oracle:** 성공 코드 대신 역할별 예상 데이터 집합과 실제 집합을 비교할 계획을 먼저 작성합니다. 예를 들어 tenant A 회원이 tenant B PK를 아는 상황을 포함합니다. 로그인 전/후 네트워크 기록에서 `apikey`와 Authorization의 **종류 변화**만 검사하고 원문은 저장하지 않습니다.

**실패 모드:** SQL editor의 admin 권한으로만 테스트, local 기능을 hosted SLA로 해석, 브라우저 bundle에 secret 포함, 내부 서비스 버전을 CLI 버전 하나로 대체, DB commit과 UI 수신을 같은 사건으로 취급.

**산출물·통과:** 6개 경로도, component manifest, secret 취급표, 6개 실패 경계. 동료가 “이 credential 하나가 유출되면 어디까지 읽고 쓸 수 있는가”를 물었을 때 권한·RLS·노출 schema를 근거로 답해야 합니다. 구현 추적은 [소스 지도](../source-reading.md)의 gateway → Auth/PostgREST → DB 경로를 선택합니다.

<a id="su02"></a>
## SU02 스키마, 불변조건, 연결 수명 · LOCAL-PREP / HOSTED-DESIGN

**선수 조건:** SU01, PK/FK/unique/check, transaction, PostgreSQL MVCC의 기본. SQL 엔진 내부는 [PostgreSQL 트랙](../../../databases/postgresql/README.md)으로 심화합니다.

### 원리

화면의 입력 검증은 경쟁 조건을 막지 못합니다. 두 요청이 같은 idempotency key를 동시에 보냈을 때 최종 중복을 막는 것은 DB unique constraint와 transaction입니다. NULL·타입·timezone·금액 단위도 저장 계약에 속합니다. RLS는 행 접근을 제한하지만 잘못된 업무 불변조건을 자동으로 만들어주지 않습니다.

브라우저에는 DB password를 배포하지 않습니다. Data API는 서버 측 role/transaction 경로를 거치며, direct SQL은 접속 role 자체가 신뢰 경계입니다. Supavisor의 session/transaction 모드는 backend connection을 유지하는 단위가 다릅니다. transaction pooler를 통과하는 세션에 오래 사는 state가 있다고 가정하면 role/context가 예상과 달라지거나 기능이 깨질 수 있습니다. 현재 shared transaction mode의 prepared statement 제약을 선택한 driver 설정과 함께 확인합니다. [연결 방식](https://supabase.com/docs/guides/database/connecting-to-postgres)

### SQL 실험: 제약은 최종 방어선인가

비운영 로컬 프로젝트에서 최초 한 번 생성합니다. `public`가 API 노출 schema일 수 있으므로 **같은 transaction에서 RLS와 grant를 닫은 뒤 commit**합니다.

```sql
BEGIN;
CREATE TABLE public.su_lab_commands (
  command_id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  idempotency_key text NOT NULL,
  amount_minor bigint NOT NULL CHECK (amount_minor >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);
ALTER TABLE public.su_lab_commands ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.su_lab_commands FROM PUBLIC, anon, authenticated;
COMMIT;
```

관리 세션 A에서 `BEGIN` 후 command UUID `00000000-0000-0000-0000-000000000101`, tenant `10000000-0000-0000-0000-000000000001`, key `su02-k1`, amount100을 INSERT하되 commit하지 않습니다. 관리 세션 B는 다른 command UUID와 **같은 tenant/key**로 INSERT합니다. B에 `SET lock_timeout='3s'`를 먼저 적용해 대기가 무한히 이어지지 않게 합니다. A rollback 후 B 재시도, A commit 후 B 재시도의 두 경우를 별도 key로 실험합니다. 성공/timeout/unique violation을 구별하고 어느 경우에도 최종 tenant/key row 수가1을 넘지 않는지 검사합니다.

추가로 음수 금액, NULL tenant, 같은 key의 다른 tenant를 입력해 예상 제약 행렬을 완성합니다. 실패 쿼리는 독립 transaction으로 실행하거나 savepoint를 사용합니다. 한 에러 뒤 aborted transaction에 후속 쿼리를 계속 보내지 않습니다.

연결 조사에서는 direct 세션에서 아래 값을 transaction 전/중/후 기록합니다. prepared statement, temporary table, session advisory lock을 **그대로 transaction pooler에 의존하는 설계**가 왜 위험한지 설명합니다. 로컬에 해당 pooler가 없다면 비교 실행 대신 HOSTED-DESIGN으로 표기합니다.

```sql
SELECT pg_backend_pid(), current_user, current_setting('application_name');
BEGIN;
SET LOCAL application_name = 'su02-exp1';
SELECT pg_backend_pid(), current_setting('application_name');
COMMIT;
SELECT current_setting('application_name');
```

`pg_backend_pid()`가 우연히 계속 같았다고 session 보장을 증명한 것은 아닙니다. 동시에 열리는 app instance 수 × instance별 pool 크기 + Auth/API/Realtime/운영 연결을 합산하여 예산을 세웁니다. 이 수치가 실제 backend 수와 왜 다를 수 있는지도 설명합니다. 원격 TLS는 암호화와 server identity 검증을 구분합니다.

**증거·통과:** 제약 위반5개 이상, 두 세션 시간선, 최종 unique oracle, endpoint별 기능 계약표, pool 예산. “REST 요청3개면 하나의 transaction”과 “RLS가 있으니 unique constraint 불필요”를 반례로 기각합니다. 권한이 필요한 business transaction은 SU06의 invoker RPC 설계로 연결합니다.
