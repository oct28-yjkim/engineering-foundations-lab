# SU05–SU06. 반례로 증명하는 tenant 격리와 Data API

[커리큘럼](../curriculum.md) · 이전: [인증](02-auth-jwt.md) · 다음: [Realtime](04-realtime.md)

<a id="su05"></a>
## SU05 role, grant, policy의 합성 · LOCAL-PREP / BUILD

**선수 조건:** SU02–04. 실제 Auth 테스트 계정과 [로컬 준비](../labs/local-lab.md)가 필요합니다. 이 절의 SQL은 독립 로컬 프로젝트의 관리자 psql에서 실행하며 운영 환경에 적용하지 않습니다.

### 원리

SQL 권한은 schema/table/column grant와 RLS를 함께 통과해야 합니다. `USING`은 기존 행을 볼/대상으로 삼을 수 있는지, `WITH CHECK`는 새 행 상태가 허용되는지를 판단합니다. SELECT의 비허용 행은 사라질 수 있으므로 HTTP 200과0행 UPDATE는 권한 검사가 없다는 증거가 아닙니다. 권한 없음과 자원 없음의 구별을 API에서 의도적으로 감출 수도 있습니다. [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

`auth.uid()`가 NULL이면 `NULL = owner_id`는 SQL의 UNKNOWN이며 policy에서 TRUE로 통과하지 못합니다. 일반 signed-out의 anon과 Auth의 anonymous sign-in 사용자(authenticated role을 가질 수 있음)는 다릅니다. 사용자 수정 가능 `user_metadata`를 admin 근거로 쓰지 않습니다. 서버 관리 `app_metadata`도 JWT에 들어간 순간 snapshot이므로 즉시 membership 철회를 요구하는 계약은 DB의 현재 membership을 조회해야 합니다. [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [Anonymous sign-ins](https://supabase.com/docs/guides/auth/auth-anonymous)

table owner/superuser/BYPASSRLS 테스트는 일반 사용자 격리를 검증하지 못합니다. `FORCE ROW LEVEL SECURITY`도 superuser/BYPASSRLS를 일반 사용자로 만들지 않습니다. 또 RLS는 old/new 값의 불변 비교를 자동으로 해주지 않습니다. 이 실험은 tenant/owner 변경을 **column privilege**로 막고 행 접근은 RLS로 막습니다.

### 독립 oracle와 사용자 준비

[authorization-oracle.json](../labs/authorization-oracle.json)은 구현에서 생성하지 않은 예상 결과입니다. `a1/a2/b1` 3개 문서, tenant A/B, 일반회원, tenant admin, signed-out, membership 없는 anonymous Auth 사용자, 폐기된 membership 사용자를 포함합니다. JSON 파싱 성공은 RLS 검증 성공이 아닙니다.

Auth API/SDK로 만든 테스트 계정 `u_a`, `u_a2`, `u_b`, `admin_a`, `revoked_a`의 **실제 UUID**를 아래 psql prompt에 입력합니다. anonymous Auth 계정은 별도로 login하되 membership row를 주지 않습니다. 기능이 비활성인 환경에서는 해당 검증을 미실행으로 남깁니다. 원장 가명을 서명 없는 가짜 JWT로 만들어 API에 보내지 않습니다.

```sql
\prompt 'u_a actual Auth UUID: ' u_a
\prompt 'u_a2 actual Auth UUID: ' u_a2
\prompt 'u_b actual Auth UUID: ' u_b
\prompt 'admin_a actual Auth UUID: ' admin_a
\prompt 'revoked_a actual Auth UUID: ' revoked_a

BEGIN;
CREATE TABLE public.su_lab_memberships (
  tenant_id text NOT NULL CHECK (tenant_id IN ('tenant_a','tenant_b')),
  user_id uuid NOT NULL,
  member_role text NOT NULL CHECK (member_role IN ('member','admin')),
  active boolean NOT NULL,
  PRIMARY KEY (tenant_id, user_id)
);
CREATE TABLE public.su_lab_tasks (
  id text PRIMARY KEY,
  tenant_id text NOT NULL CHECK (tenant_id IN ('tenant_a','tenant_b')),
  owner_id uuid NOT NULL,
  title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200)
);
ALTER TABLE public.su_lab_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.su_lab_tasks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.su_lab_memberships, public.su_lab_tasks
FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON public.su_lab_memberships, public.su_lab_tasks
TO anon, authenticated;
GRANT INSERT, DELETE ON public.su_lab_tasks TO authenticated;
GRANT UPDATE (title) ON public.su_lab_tasks TO authenticated;

CREATE POLICY su_lab_membership_self ON public.su_lab_memberships
FOR SELECT TO authenticated
USING (user_id = (SELECT auth.uid()) AND active);

CREATE POLICY su_lab_task_read ON public.su_lab_tasks
FOR SELECT TO authenticated USING (
  EXISTS (SELECT 1 FROM public.su_lab_memberships m
    WHERE m.tenant_id = su_lab_tasks.tenant_id
      AND m.user_id = (SELECT auth.uid()) AND m.active)
);
CREATE POLICY su_lab_task_insert ON public.su_lab_tasks
FOR INSERT TO authenticated WITH CHECK (
  owner_id = (SELECT auth.uid()) AND
  EXISTS (SELECT 1 FROM public.su_lab_memberships m
    WHERE m.tenant_id = su_lab_tasks.tenant_id
      AND m.user_id = (SELECT auth.uid()) AND m.active)
);
CREATE POLICY su_lab_task_update ON public.su_lab_tasks
FOR UPDATE TO authenticated USING (
  EXISTS (SELECT 1 FROM public.su_lab_memberships m
    WHERE m.tenant_id = su_lab_tasks.tenant_id
      AND m.user_id = (SELECT auth.uid()) AND m.active
      AND (su_lab_tasks.owner_id = (SELECT auth.uid()) OR m.member_role = 'admin'))
) WITH CHECK (
  EXISTS (SELECT 1 FROM public.su_lab_memberships m
    WHERE m.tenant_id = su_lab_tasks.tenant_id
      AND m.user_id = (SELECT auth.uid()) AND m.active
      AND (su_lab_tasks.owner_id = (SELECT auth.uid()) OR m.member_role = 'admin'))
);
CREATE POLICY su_lab_task_delete ON public.su_lab_tasks
FOR DELETE TO authenticated USING (
  EXISTS (SELECT 1 FROM public.su_lab_memberships m
    WHERE m.tenant_id = su_lab_tasks.tenant_id
      AND m.user_id = (SELECT auth.uid()) AND m.active AND m.member_role = 'admin')
);

INSERT INTO public.su_lab_memberships VALUES
('tenant_a', :'u_a'::uuid, 'member', true),
('tenant_a', :'u_a2'::uuid, 'member', true),
('tenant_b', :'u_b'::uuid, 'member', true),
('tenant_a', :'admin_a'::uuid, 'admin', true),
('tenant_a', :'revoked_a'::uuid, 'member', false);
INSERT INTO public.su_lab_tasks VALUES
('a1','tenant_a', :'u_a'::uuid, 'Synthetic A1'),
('a2','tenant_a', :'u_a2'::uuid, 'Synthetic A2'),
('b1','tenant_b', :'u_b'::uuid, 'Synthetic B1');
COMMIT;
```

최소 fixture이므로 user lifecycle/FK 삭제 정책까지 완성된 제품 모델은 아닙니다. 소유자 UUID와 Auth 계정의 일치도는 준비 원장에서 검증합니다. 재실행은 기존 데이터를 삭제하는 방식이 아니라 새 독립 프로젝트/접두사로 합니다.

### SQL 격리와 실제 API를 각각 검증하기

먼저 trusted 관리자 연결에서 role과 request claims를 **한 transaction 안에서만** 모사합니다. 이는 policy 단위 테스트이며 JWT 서명 검증 테스트가 아닙니다.

```sql
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', :'u_a', 'role', 'authenticated')::text, true);
SELECT current_user, auth.uid();
SELECT id, title FROM public.su_lab_tasks ORDER BY id;
UPDATE public.su_lab_tasks SET title='allowed probe' WHERE id='a1' RETURNING id;
UPDATE public.su_lab_tasks SET title='forbidden probe' WHERE id='a2' RETURNING id;
ROLLBACK;
```

예상 PK는 `a1,a2`, 첫 update1행, 두 번째0행입니다. 이는 기대값이지 이 저장소에서 측정한 실행 결과가 아닙니다. anon은 `SET LOCAL ROLE anon`과 claims `{}`로 별도 transaction을 만들고 `auth.uid() IS NULL`·반환0행을 확인합니다. column 변경(W07/W08)과 cross-tenant INSERT(W02)는 독립 transaction에서 실패를 관찰한 뒤 rollback합니다.

그다음 BUILD harness는 실제 publishable key와 각 사용자의 정상 Auth 세션으로 REST 요청을 보내 **oracle 18개**를 재검증합니다. write case마다 원래 fixture에서 시작합니다. 관리자 harness는 오직 `su_lab_tasks`의 테스트 행을 복구하고 전후 snapshot을 읽는 용도로 분리합니다. 테스트 대상 API의 반환값을 그대로 “정답”으로 저장하지 않습니다. 허용된 변경의 내용까지 맞는지, 거부된 요청 후 보호 대상 상태가 그대로인지 검사합니다.

`revoked_a`는 먼저 active로 허용되는 것을 확인한 뒤 관리 경로로 active=false를 바꾸고 **같은 아직 만료되지 않은 JWT**로 R06/W12를 실행합니다. 관리자가 membership을 바꾼 시간·새 DB transaction의 시간·token exp를 기록합니다. 기존 장기 transaction의 snapshot이나 다른 Realtime 채널까지 즉시 취소된다고 확장 해석하지 않습니다.

별도 privileged 관찰에서는 local 관리자 transaction에서 `GRANT SELECT ON public.su_lab_tasks TO service_role; SET LOCAL ROLE service_role;` 후 전체3행이 보이는지 확인하고 rollback합니다. `rolbypassrls`를 함께 기록합니다. 이것은 **tenant admin의 권한이 아니라 서버 유지보수 credential의 위험 범위**입니다.

**실패 모드:** broad `FOR ALL USING(true)` 정책이 다른 policy와 OR 결합, 자기참조 membership policy의 무한 재귀, UPDATE에 필요한 SELECT policy 누락, table-level UPDATE grant로 column 제한 무효화, metadata의 `admin:true` 신뢰, privileged client를 tenant admin으로 오인.

**통과:** 18/18 oracle 일치, actual API와 SQL 모사 결과 구분, negative 후 상태 불변, active 철회 반영, privileged 별도 위험 검증. 실패한 항목이 있으면 SU06의 view/RPC로 노출면을 늘리지 않습니다.

<a id="su06"></a>
## SU06 PostgREST transaction, view, RPC, policy 비용 · LOCAL-PREP / BUILD

**선수 조건:** SU05 전부, PostgreSQL 실행 계획·index. 아래 view는 실제 PostgreSQL15 이상에서 사용하며 더 오래된 버전에는 노출하지 않습니다.

### 원리

PostgREST 요청은 DB transaction 안에서 role·request context·query를 연결합니다. 여러 HTTP 호출을 묶는 client 함수가 자동으로 하나의 transaction을 만드는 것은 아닙니다. business invariant 여러 개를 원자적으로 변경하려면 DB 함수의 transaction 경계 등을 명시적으로 설계합니다. [PostgREST transactions](https://docs.postgrest.org/en/stable/references/transactions.html)

view의 기본 권한 문맥은 단순한 query alias와 다를 수 있습니다. `security_invoker=true`는 호출자 권한과 underlying RLS를 적용하도록 설계하는 수단입니다. 함수의 `SECURITY DEFINER`는 owner 권한으로 실행하므로 `search_path=''`, 완전 수식 이름, 최소 owner 권한, EXECUTE grant, 노출 schema를 함께 검토합니다. search_path만 고정했다고 부적절한 admin 작업이 안전해지는 것은 아닙니다. [CREATE VIEW](https://www.postgresql.org/docs/current/sql-createview.html), [Database functions](https://supabase.com/docs/guides/database/functions)

### SQL 실험: 안전한 조회와 최소 RPC

```sql
BEGIN;
CREATE VIEW public.su_lab_task_titles WITH (security_invoker=true) AS
SELECT id, tenant_id, title FROM public.su_lab_tasks;
REVOKE ALL ON public.su_lab_task_titles FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.su_lab_task_titles TO authenticated;

CREATE FUNCTION public.su_lab_rename_task(p_id text, p_title text)
RETURNS SETOF public.su_lab_tasks LANGUAGE sql SECURITY INVOKER
SET search_path = '' AS $$
  UPDATE public.su_lab_tasks SET title = p_title
  WHERE id = p_id RETURNING *;
$$;
REVOKE ALL ON FUNCTION public.su_lab_rename_task(text,text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.su_lab_rename_task(text,text) TO authenticated;
COMMIT;
```

SU05의 role/claims transaction에서 view 조회와 `SELECT * FROM public.su_lab_rename_task('a2','probe');`를 호출하고 rollback합니다. A 회원은 rename0행, A admin은1행, B는0행이어야 합니다. 같은 케이스를 실제 Data API view endpoint와 RPC endpoint로 반복합니다. client가 JSON에 `tenant_id`를 추가해도 함수 signature 밖 인수가 임의로 반영되지 않아야 합니다. schema cache 갱신 여부와 에러는 실제 PostgREST 버전에서 확인합니다.

**반증 과제:** 별도의 비노출 scratch schema에서 definer owner가 table owner인 경우를 재현하여 invoker와 결과를 비교합니다. 위험 함수를 public/exposed schema에 만들거나 anon EXECUTE를 열지 않습니다. owner의 BYPASSRLS 여부·table ownership·function grant를 하나씩 바꾼 원인표를 제출합니다.

### 성능 실험: 보안을 끄지 않고 비용 찾기

BUILD seed가 각 tenant별 결정적 ID를 가진10만행을 별도의 성능 fixture에 생성하게 합니다. SU05의3행 oracle는 보존합니다. tenant별 예상 PK 집합과 입력 개수를 seed 생성 시 따로 보관합니다. 동일한 authenticated role/claims, 동일 tenant 조건, page size로 `EXPLAIN (ANALYZE, BUFFERS, SETTINGS)`를 비교합니다. SELECT에만 사용하고 쓰기 EXPLAIN ANALYZE는 실제 변경임을 잊지 않습니다.

membership의 `(tenant_id,user_id)` PK, task의 `(tenant_id,id)` index, `(SELECT auth.uid())`의 statement-level 계산과 row 의존 subquery의 차이를 추적합니다. policy에 필터가 있다는 이유로 client query의 명시 tenant 필터·pagination이 불필요한 것은 아닙니다. index 전후20회 이상 측정하되 결과 PK와 negative RLS 회귀가 같아야 합니다. [RLS performance](https://supabase.com/docs/guides/database/postgres/row-level-security#rls-performance-recommendations)

**증거·통과:** view/RPC 접근 행렬, function owner·`prosecdef`·`proconfig`·ACL 조회, 계획과 raw timing, 선택도/rows 오차 해석. 최적화 후18개 authz oracle 중 하나라도 틀리면 성능 개선으로 인정하지 않습니다. [소스 지도](../source-reading.md)에서 request role 설정부터 SQL 실행/response까지 한 call chain을 제출합니다.
