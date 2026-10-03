# SU09–SU10. 객체 저장과 함수 실행의 commit 경계

[커리큘럼](../curriculum.md) · 이전: [Realtime](04-realtime.md) · 다음: [운영과 복구](06-operations-migrations.md)

<a id="su09"></a>
## SU09 Storage: metadata와 bytes는 같은 백업이 아니다 · LOCAL-PREP / BUILD

**선수 조건:** SU05 RLS, 객체 key와 filesystem path의 차이, checksum, HTTP cache. SU05의 membership/실제 Auth 사용자를 재사용합니다.

### 원리

Storage는 DB의 bucket/object metadata와 실제 객체 bytes 저장소를 연결합니다. 내부 `storage` schema를 직접 INSERT/DELETE하면 API의 객체 처리를 거치지 않아 불일치를 만들 수 있습니다. 읽기 관찰과 정책 관리는 가능하지만 객체 생성·변경·삭제는 Storage API를 사용합니다. [Storage schema](https://supabase.com/docs/guides/storage/schema/design)

private bucket의 RLS는 object path·bucket·인증 사용자에 따른 operation을 제한합니다. insert upload와 기존 key의 upsert에는 필요한 권한이 다릅니다. 파일 경로에 tenant 이름이 있다는 사실 자체가 인증은 아니며 client가 다른 tenant prefix를 제출할 수 있다고 가정해야 합니다. [Storage access control](https://supabase.com/docs/guides/storage/security/access-control)

public bucket과 signed URL의 접근 모델도 구별합니다. signed URL은 기간과 대상이 제한된 bearer capability이므로 링크를 가진 상대가 다운로드할 수 있는 기간을 고려합니다. 링크 발행 당시의 권한과 나중의 membership 변경, CDN cache, bytes overwrite는 서로 다른 시간축입니다. [파일 제공과 다운로드](https://supabase.com/docs/guides/storage/serving/downloads)

### 실험: tenant별 private object

로컬 관리 SDK/API로 새 private bucket `su-lab-private-exp1`을 만들고 크기·MIME 제한을 명시합니다. bucket이 이미 있으면 재사용하여 원본을 덮지 말고 suffix를 바꿉니다. 아래 SQL의 bucket명도 동일하게 바꿉니다. 기존 광범위 Storage policy가 없는 독립 실습 환경에서만 추가합니다.

```sql
CREATE POLICY su_lab_storage_read ON storage.objects
FOR SELECT TO authenticated USING (
  bucket_id='su-lab-private-exp1' AND EXISTS (
    SELECT 1 FROM public.su_lab_memberships m
    WHERE m.tenant_id=(storage.foldername(name))[1]
      AND m.user_id=(SELECT auth.uid()) AND m.active)
);
CREATE POLICY su_lab_storage_insert ON storage.objects
FOR INSERT TO authenticated WITH CHECK (
  bucket_id='su-lab-private-exp1'
  AND (storage.foldername(name))[2]=(SELECT auth.uid())::text
  AND EXISTS (SELECT 1 FROM public.su_lab_memberships m
    WHERE m.tenant_id=(storage.foldername(name))[1]
      AND m.user_id=(SELECT auth.uid()) AND m.active)
);
CREATE POLICY su_lab_storage_update ON storage.objects
FOR UPDATE TO authenticated USING (
  bucket_id='su-lab-private-exp1'
  AND (storage.foldername(name))[2]=(SELECT auth.uid())::text
  AND EXISTS (SELECT 1 FROM public.su_lab_memberships m
    WHERE m.tenant_id=(storage.foldername(name))[1]
      AND m.user_id=(SELECT auth.uid()) AND m.active)
) WITH CHECK (
  bucket_id='su-lab-private-exp1'
  AND (storage.foldername(name))[2]=(SELECT auth.uid())::text
  AND EXISTS (SELECT 1 FROM public.su_lab_memberships m
    WHERE m.tenant_id=(storage.foldername(name))[1]
      AND m.user_id=(SELECT auth.uid()) AND m.active)
);
```

이 실험의 계약은 같은 tenant는 읽기, 자신의 user folder에만 upload/upsert입니다. SU05의 문서 수정 정책과 **서로 다른 객체 계약**임을 명시합니다. tenant admin도 모든 파일을 쓸 권한을 자동으로 얻지 않습니다. 일반 사용자 DELETE를 허용하지 않았으므로 cleanup은 별도 로컬 관리 API로 대상 bucket/key를 확인한 뒤 수행합니다.

BUILD client는 알려진 UTF-8 text bytes를 가진 파일을 `tenant_a/<u_a 실제 UUID>/su09-note.txt`에 upload합니다. 업로드 전 SHA-256과 byte count를 원장에 계산합니다. 같은 key 두 번째 업로드는 `upsert:false/true`를 나누어 실행합니다. 결과코드뿐 아니라 다운로드 bytes의 hash가 입력과 같은지 검사합니다.

필수 negative case는 A가 B prefix에 upload, A가 A2 folder에 upload, B가 A object download, signed-out download, membership 제거 후 새 authenticated download입니다. 같은 tenant A2의 read는 허용되어야 합니다. 각 실패 후 객체의 존재 여부·최종 hash가 변하지 않았는지 **별도 관리 관찰**로 확인합니다. Storage API 에러 코드를 RLS row count와 동일하게 가정하지 않습니다.

### capability와 실패 경계

허용 사용자로 짧은 수명의 signed URL을 발행해 별도 비로그인 client에서 다운로드하고 만료 전/후를 비교합니다. URL 자체는 로그·저장소에 남기지 않습니다. URL 발행 뒤 membership을 제거했을 때 기존 URL의 실제 유효 범위를 관찰하고 “RLS 변경 즉시 기존 URL도 무효화”라고 가정하지 않습니다.

업로드 중 client 연결을 끊고 list/metadata/download hash를 확인합니다. 작은 standard upload 결과를 대용량 resumable upload의 보장으로 일반화하지 않습니다. 재시도시 같은 object key에 덮어쓰기, versioned key 생성, 업무 DB 참조 변경 중 어떤 계약인지 정합니다. Content-Type은 client 주장일 수 있으므로 파일 내용 검증·malware scanning·접근 격리가 필요한 제품의 설계를 별도 작성합니다. [업로드 방식](https://supabase.com/docs/guides/storage/uploads/standard-uploads)

**통과:** 허용/거부 최소8개, 독립 checksum 일치, forbidden overwrite0건, signed URL 수명/노출 위험 설명, metadata와 bytes의 불일치 탐지 계획. [소스 지도](../source-reading.md)에서 Storage authorization → metadata transaction → backend object 경계를 추적하고 SU12에 실제 bytes 복원 원장을 넘깁니다.

<a id="su10"></a>
## SU10 Edge Functions 인증과 재시도 안전성 · BUILD

**선수 조건:** SU03–06, SU09, idempotency key·transaction·timeout. 함수 앱과 테스트 runner는 학습자가 작성하며 저장소가 배포 가능한 앱을 제공하지 않습니다.

### 원리

Edge Function은 runtime의 request handler입니다. DB transaction도 durable job queue도 자동으로 제공하지 않습니다. process 재사용·종료, 제한시간, 네트워크 재시도, cold start를 전제로 설계합니다. 최신 runtime의 지원 API와 CPU/메모리/wall-clock 제한을 manifest에 기록하고 로컬 수치를 hosted 보장으로 사용하지 않습니다. [Edge limits](https://supabase.com/docs/guides/functions/limits)

인증에는 platform gateway의 검사와 handler의 credential 검증이 있습니다. 새 secret/publishable key는 JWT가 아니므로 이를 user JWT처럼 Authorization에 넣어 검증할 수 없습니다. 현재 공식 `@supabase/server`의 user/secret/publishable/none 모드를 확인하되 실제 SDK/runtime을 고정합니다. `verify_jwt=false`는 **인증 불필요 선언이 아닙니다**. 특히 비대칭 signing key 호환성 때문에 gateway 검사를 끄는 구성에서도 handler가 user JWT를 검증해야 합니다. [Function auth](https://supabase.com/docs/guides/functions/auth), [Authorization headers](https://supabase.com/docs/guides/functions/auth-headers)

user-scoped DB client와 admin client는 위임 범위가 다릅니다. 일반 사용자 요청을 받자마자 admin client로 body의 tenant ID를 신뢰하면 RLS를 건너뛰는 confused deputy가 됩니다. 외부 webhook은 provider signature·timestamp/replay 규칙을 **원본 body** 기준으로 검증하며 Supabase user JWT와 다른 신뢰 경로입니다.

### 구현 과제: 제목 변경 command

작은 user-authenticated 함수 `su-lab-command`와 DB RPC를 작성합니다. 입력은 `{command_id, task_id, new_title}`이며 tenant/owner는 client 주장으로 변경할 수 없습니다. SU06 invoker RPC의 권한 계약을 유지하고 같은 command의 재전송은 업무 변경을 한 번만 수행합니다. 학습자가 추가할 ledger table은 `public.su_lab_command_ledger`, mutation 증거용 audit table은 `public.su_lab_task_audit`로 이름을 정하고 각 table의 RLS·grant·보존 정책도 구현합니다. 두 table의 완성 구현은 이 예제에 포함되어 있지 않습니다.

다음은 설계 의사코드이며 실제 SQL 함수·권한·테스트를 추가해야 합니다.

```text
verify user credential; validate input; derive actor from verified identity
begin one database transaction
  try insert ledger(actor_id, command_id, request_hash), unique(actor_id, command_id)
  if inserted:
    perform authorized task update; fail atomically if not permitted
    record immutable result in the same ledger transaction
  otherwise:
    read committed ledger result; reject different request_hash
commit
return recorded result
```

동시 unique conflict 대기, 재시도에서 ledger SELECT 권한, RLS denied0행의 business error 처리까지 구현합니다. insert가 중복으로 생략된 뒤에도 update를 무조건 실행하는 구현은 실패입니다. hash에는 정규화된 요청 형식을 사용하고 actor/tenant 사이에 command key가 섞이지 않도록 scope를 정합니다. DB에 없는 payment provider 효과까지 한 transaction으로 묶었다고 주장하지 않습니다.

### 실패 주입과 oracle

1. 실제 A JWT로 `a1` 변경1건을 성공시킵니다. 같은 command를 순차10회, 동시10회 반복합니다.
2. 같은 command ID에 다른 제목을 보내고 충돌로 거부되는지 검사합니다.
3. DB commit 뒤 HTTP response를 전달하기 전에 테스트 harness가 연결을 끊습니다. client는 성공을 모르므로 같은 command로 재시도합니다.
4. A가 `a2/b1`을 변경하려는 요청, token 없음/변조/만료, publishable-only 요청을 user route에 보내 모두 거부되는지 확인합니다.
5. tenant admin도 body의 tenant/owner를 바꾸거나 B 문서를 변경할 수 없는지 검사합니다.

정답은 HTTP200 개수가 아니라 **ledger의 고유 command, 실제 business mutation 수, 최종 title, actor별 허용 범위**입니다. 변경 횟수를 title 최종값만으로 추론할 수 없으므로 동일 transaction의 append-only test audit 또는 version counter로 검증합니다. 재시도 횟수·오류·응답 unknown을 따로 기록합니다.

외부 이메일·결제 mock을 붙이는 확장에서는 DB outbox를 source transaction에 넣더라도 외부 receiver의 idempotency 또는 inbox가 없으면 중복 효과가 남는다는 반례를 만듭니다. “outbox를 만들었으니 외부 효과 exactly-once”는 통과 답이 아닙니다. real 결제·실제 이메일 발송은 범위 밖입니다.

**실패 모드:** `verify_jwt=false`만 설정한 공개 admin 함수, 무한 retry, 모듈 전역 user session, CORS를 인증으로 오인, timeout을 rollback 증거로 취급, background task를 durable queue처럼 사용.

**통과:** 동일 command의 업무 효과1회, body 충돌 거부, unauthorized 변화0건, commit-response gap 복구, token/secret 무로그. p95 개선은 정확성·실패율을 유지하고 최소20개 측정 구간에서만 결론을 냅니다. source 추적은 handler 인증 → DB request role → ledger transaction으로 연결합니다.
