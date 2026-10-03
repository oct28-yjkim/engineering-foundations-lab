# Supabase 소스 읽기: API 너머의 권한·상태·복구 경계

[커리큘럼](curriculum.md) · [평가 기준](assessment.md) · [실습 범위](labs/local-lab.md)

SU13은 Supabase를 하나의 backend 함수로 보지 않고 PostgreSQL, Auth, PostgREST, Realtime, Storage, Edge Runtime, CLI, pooler의 계약으로 분해하는 단계입니다. 이 문서는 실제 upstream 소스 지도입니다. 저장소에 완성된 multi-tenant 앱·managed project·self-hosted stack이 제공됐다는 의미는 아닙니다.

## 1. polyrepo의 읽기 기준과 실행 지문

2026-10-04 공식 저장소 HEAD와 해당 commit의 파일 목록을 확인했습니다. 다음 값은 **source-only snapshot**이며 설치 버전·안정 릴리스 추천·상호 호환 조합이 아닙니다. 실제 실행에서는 CLI version, SDK lockfile, 서비스별 image tag/digest, PostgreSQL major/extension, pooler mode, Auth/JWT 설정을 따로 기록합니다. hosted의 내부 SHA가 비공개이면 unknown으로 남깁니다.

| 구성요소 | 고정 읽기 commit | 추적할 실행 경계 |
| --- | --- | --- |
| Supabase monorepo / deployment | [4ab54b935919ba3f4bb92f436ae4e757108e4f8a](https://github.com/supabase/supabase/tree/4ab54b935919ba3f4bb92f436ae4e757108e4f8a) | docker 배포 tag와 실제 rendered config, Studio/docs와 server 구분 |
| Auth | [ce9a8eee0cc042be8c7a42981a7ddae631e41d91](https://github.com/supabase/auth/tree/ce9a8eee0cc042be8c7a42981a7ddae631e41d91) | Auth image, JWT signing scheme/JWKS, refresh/session 정책 |
| Realtime | [f86df8c33ef0d014d009e4ff55e3ba18a546cb07](https://github.com/supabase/realtime/tree/f86df8c33ef0d014d009e4ff55e3ba18a546cb07) | server image, Postgres Changes와 Broadcast/Presence의 구별 |
| Storage | [eccef5e70a67fb4030e0646e5e22602c94f568bc](https://github.com/supabase/storage/tree/eccef5e70a67fb4030e0646e5e22602c94f568bc) | API image, backend object store, bucket/metadata 권한 |
| Edge Runtime | [d4a4f606a90e8c66864219c9b1d31ef0e3e3f626](https://github.com/supabase/edge-runtime/tree/d4a4f606a90e8c66864219c9b1d31ef0e3e3f626) | runtime image, function revision, CPU/wall-clock/memory 제한 |
| CLI | [66ccc6f63a9a26b29c368698994a0843d23b80be](https://github.com/supabase/cli/tree/66ccc6f63a9a26b29c368698994a0843d23b80be) | 설치 CLI version, config, local/linked/remote 명령 대상 |
| PostgREST | [58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19](https://github.com/PostgREST/postgrest/tree/58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19) | API image, db roles, exposed schemas, schema cache |
| Supavisor | [e616317d74fbdd63324c3314aca6bb08cf764326](https://github.com/supabase/supavisor/tree/e616317d74fbdd63324c3314aca6bb08cf764326) | pooler image, transaction/session mode, client connection options |

**CLI vX는 Auth vX 또는 PostgREST vX라는 뜻이 아닙니다.** 아래 monorepo의 최신 image들을 위 각 저장소 HEAD 빌드로 일괄 바꾸지 않습니다. Supabase SDK/SSR package도 별도 package version·lockfile을 남기고, SDK 내부까지 연구할 때는 해당 저장소 commit을 표에 추가합니다.

PowerShell/Bash에서 ref를 조회하는 읽기 전용 예입니다. 현재 HEAD가 바뀌어도 문서 permalink는 같은 소스를 가리킵니다.

~~~text
git ls-remote https://github.com/supabase/auth.git HEAD
git ls-remote https://github.com/supabase/realtime.git HEAD
git ls-remote https://github.com/supabase/storage.git HEAD
git ls-remote https://github.com/supabase/edge-runtime.git HEAD
git ls-remote https://github.com/supabase/cli.git HEAD
git ls-remote https://github.com/PostgREST/postgrest.git HEAD
git ls-remote https://github.com/supabase/supavisor.git HEAD
git ls-remote https://github.com/supabase/supabase.git HEAD
~~~

확보한 별도 source checkout에서 `git rev-parse HEAD`, `git status --short`, `git describe --tags --always`를 기록합니다. runtime 조사 시 token·JWT·DSN·connection string·환경변수 전체를 보고서에 복사하지 않습니다. secret 값 대신 알고리즘·key ID·권한 범위·회전 시각과 비밀 제거된 설정만 남깁니다.

## 2. 구현 지도: 요청 하나의 identity와 state를 따라간다

각 경로는 고정 snapshot에 실재하는 구현 파일입니다. 이 snapshot에서는 CLI의 Go 코드가 **apps/cli-go/** 아래, PostgREST가 **src/library/PostgREST/** 아래 있습니다. 과거 글의 root internal/ 또는 src/PostgREST/를 그대로 복사하지 않습니다.

| 모듈·경계 | 실제 구현 경로 | 반드시 답할 질문 |
| --- | --- | --- |
| SU01 서비스 조합 | [docker-compose.yml](https://github.com/supabase/supabase/blob/4ab54b935919ba3f4bb92f436ae4e757108e4f8a/docker/docker-compose.yml) | 각 image·volume·healthcheck가 어떤 실패 영역인가? local CLI stack과 동일하다고 가정했는가? |
| SU01 gateway routing | [Envoy lds.template.yaml](https://github.com/supabase/supabase/blob/4ab54b935919ba3f4bb92f436ae4e757108e4f8a/docker/volumes/api/envoy/lds.template.yaml) | API key 처리·라우팅과 각 서비스의 최종 권한 검사는 어디서 갈리는가? |
| SU02/SU05 db role | [roles.sql](https://github.com/supabase/supabase/blob/4ab54b935919ba3f4bb92f436ae4e757108e4f8a/docker/volumes/db/roles.sql) | authenticator·anon·authenticated·service 역할의 privilege/BYPASSRLS 차이는 무엇인가? **읽기 대상이지 기존 DB 적용 지시가 아니다.** |
| SU03 token entry | [Auth token.go](https://github.com/supabase/auth/blob/ce9a8eee0cc042be8c7a42981a7ddae631e41d91/internal/api/token.go) | grant type·검증 실패·token 발급을 어떤 경로로 나누는가? |
| SU03 validation middleware | [Auth middleware.go](https://github.com/supabase/auth/blob/ce9a8eee0cc042be8c7a42981a7ddae631e41d91/internal/api/middleware.go) | signature·issuer/audience·만료·권한 판단 중 어디까지 담당하는가? |
| SU04 refresh rotation | [Auth token_refresh.go](https://github.com/supabase/auth/blob/ce9a8eee0cc042be8c7a42981a7ddae631e41d91/internal/api/token_refresh.go) | 동시 refresh·재사용·transaction 실패에서 session 상태가 어떻게 바뀌는가? |
| SU04 persisted session | [Auth sessions.go](https://github.com/supabase/auth/blob/ce9a8eee0cc042be8c7a42981a7ddae631e41d91/internal/models/sessions.go) | session revocation과 이미 발급한 access JWT의 가시성이 같은 시점인가? |
| SU03/SU06 API authentication | [PostgREST Auth.hs](https://github.com/PostgREST/postgrest/blob/58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19/src/library/PostgREST/Auth.hs) | JWT claim에서 DB role을 선택하는 경계와 Auth 서버의 로그인 검증을 구분하는가? |
| SU06 request parsing | [PostgREST ApiRequest.hs](https://github.com/PostgREST/postgrest/blob/58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19/src/library/PostgREST/ApiRequest.hs) | URL/filter/body가 query 의미로 변환될 때 허용/거절 조건은 무엇인가? |
| SU06 plan | [PostgREST Plan.hs](https://github.com/PostgREST/postgrest/blob/58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19/src/library/PostgREST/Plan.hs) | embedding·RPC·mutation의 plan과 PostgreSQL 실행계획을 혼동하지 않았는가? |
| SU05/SU06 execution | [PostgREST Query.hs](https://github.com/PostgREST/postgrest/blob/58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19/src/library/PostgREST/Query.hs) | request claims/role·transaction·query를 어느 경계에서 연결하며 최종 RLS는 누가 집행하는가? |
| SU06 schema lifecycle | [PostgREST SchemaCache.hs](https://github.com/PostgREST/postgrest/blob/58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19/src/library/PostgREST/SchemaCache.hs) | migration 성공과 API에서 새 schema가 보이는 시점을 분리할 수 있는가? |
| SU07 WAL/CDC polling | [Realtime replication_poller.ex](https://github.com/supabase/realtime/blob/f86df8c33ef0d014d009e4ff55e3ba18a546cb07/lib/extensions/postgres_cdc_rls/replication_poller.ex) | polling/checkpoint·replication slot·client 수신 경계가 어떻게 다른가? |
| SU07 subscription | [Realtime subscriptions.ex](https://github.com/supabase/realtime/blob/f86df8c33ef0d014d009e4ff55e3ba18a546cb07/lib/extensions/postgres_cdc_rls/subscriptions.ex) | 구독 filter/권한과 source transaction commit은 어떤 독립 상태인가? |
| SU07/SU08 channel | [realtime_channel.ex](https://github.com/supabase/realtime/blob/f86df8c33ef0d014d009e4ff55e3ba18a546cb07/lib/realtime_web/channels/realtime_channel.ex) | join·authorization·broadcast·presence·DB change가 같은 전달 보장을 갖는가? |
| SU08 private channels | [authorization.ex](https://github.com/supabase/realtime/blob/f86df8c33ef0d014d009e4ff55e3ba18a546cb07/lib/realtime/tenants/authorization.ex) | permission을 언제 계산/재검사하는가? JWT 교체·재가입 반례가 필요한가? |
| SU08 Presence | [presence_handler.ex](https://github.com/supabase/realtime/blob/f86df8c33ef0d014d009e4ff55e3ba18a546cb07/lib/realtime_web/channels/realtime_channel/presence_handler.ex) | presence 상태를 영속 업무 원장으로 사용하면 어떤 가정이 깨지는가? |
| SU09 upload | [Storage createObject.ts](https://github.com/supabase/storage/blob/eccef5e70a67fb4030e0646e5e22602c94f568bc/src/http/routes/object/createObject.ts) | object bytes와 PostgreSQL metadata의 실패·복구 경계는 어디인가? |
| SU09 signed access | [Storage getSignedURL.ts](https://github.com/supabase/storage/blob/eccef5e70a67fb4030e0646e5e22602c94f568bc/src/http/routes/object/getSignedURL.ts) | URL 생성 권한·유효기간·나중 접근 시 검증을 구분할 수 있는가? |
| SU09 request DB identity | [Storage plugins/db.ts](https://github.com/supabase/storage/blob/eccef5e70a67fb4030e0646e5e22602c94f568bc/src/http/plugins/db.ts) | request identity와 metadata RLS를 연결하는 단위는 무엇인가? |
| SU10 runtime entry | [Edge Runtime runtime/mod.rs](https://github.com/supabase/edge-runtime/blob/d4a4f606a90e8c66864219c9b1d31ef0e3e3f626/crates/base/src/runtime/mod.rs) | main/user runtime의 실행 능력·lifecycle은 어떻게 구별되는가? |
| SU10 isolation/lifecycle | [Edge Runtime worker/pool.rs](https://github.com/supabase/edge-runtime/blob/d4a4f606a90e8c66864219c9b1d31ef0e3e3f626/crates/base/src/worker/pool.rs) | isolate 재사용·종료·동시 요청 경계가 앱 전역 변수에 어떤 영향을 주는가? |
| SU11 migration apply | [CLI migration/apply.go](https://github.com/supabase/cli/blob/66ccc6f63a9a26b29c368698994a0843d23b80be/apps/cli-go/internal/migration/apply/apply.go) | migration history와 실제 schema를 어떻게 맞추며 어떤 DB가 대상인가? |
| SU11 schema diff | [CLI db/diff.go](https://github.com/supabase/cli/blob/66ccc6f63a9a26b29c368698994a0843d23b80be/apps/cli-go/internal/db/diff/diff.go) | shadow DB·diff 출력·적용은 서로 다른 단계인가? 생성 SQL을 검토 없이 실행해도 되는가? |
| SU02/SU11 pooling | [Supavisor client_handler.ex](https://github.com/supabase/supavisor/blob/e616317d74fbdd63324c3314aca6bb08cf764326/lib/supavisor/client_handler.ex) | client connection 수와 실제 PostgreSQL backend 수의 관계는 무엇인가? |
| SU02/SU11 backend protocol | [Supavisor db_handler.ex](https://github.com/supabase/supavisor/blob/e616317d74fbdd63324c3314aca6bb08cf764326/lib/supavisor/db_handler.ex) | transaction/session 경계에서 반환·재사용되는 state는 무엇인가? |

현재 self-host 문서는 Envoy 기본 경로를 설명하고 monorepo에 Kong 설정도 남아 있습니다. **과거와 현재·managed와 self-host·CLI local을 섞어 gateway를 하나로 단정하지 않습니다.** 실제 deployment의 route와 auth 설정을 확인합니다. [공식 self-host Docker 안내](https://supabase.com/docs/guides/self-hosting/docker)

SU05 RLS는 PostgreSQL executor가 최종 집행하는 정책입니다. Auth/PostgREST 코드를 읽은 것만으로 RLS의 owner·BYPASSRLS·view·security-definer 동작을 검증했다고 하지 않습니다. [공식 RLS 가이드](https://supabase.com/docs/guides/database/postgres/row-level-security), [SSR 가이드](https://supabase.com/docs/guides/auth/server-side)와 자신의 PostgreSQL major·함수·정책 정의를 함께 대조합니다.

Realtime도 “항상 replay 불가”라는 고정 문장으로 설명하지 않습니다. 현재 [Broadcast 문서](https://supabase.com/docs/guides/realtime/broadcast#broadcast-replay)는 지원 SDK에서 private channel의 DB-origin 메시지에 제한된 replay를 설명합니다. 자신의 버전에서 origin·보존 창·최대 반환 수·권한 재평가를 확인하고, 이를 무제한 history나 Kafka consumer-group offset 계약으로 일반화하지 않습니다.

## 3. 테스트에서 경계를 역추적한다

아래 최소 3개를 서로 다른 구성요소에서 선택합니다. SQL claims fixture만으로 JWT signature 검증까지 통과했다고 하지 않으며, mocked storage client의 성공을 실제 object 복원으로 해석하지 않습니다.

| 고정 테스트 경로 | 추적할 assertion |
| --- | --- |
| [Auth token_test.go](https://github.com/supabase/auth/blob/ce9a8eee0cc042be8c7a42981a7ddae631e41d91/internal/api/token_test.go) | token/grant 성공·실패와 session/DB fixture |
| [Auth sessions_test.go](https://github.com/supabase/auth/blob/ce9a8eee0cc042be8c7a42981a7ddae631e41d91/internal/models/sessions_test.go) | session persistence/revocation 상태와 이미 발급한 JWT의 차이 |
| [PostgREST AuthSpec.hs](https://github.com/PostgREST/postgrest/blob/58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19/test/spec/Feature/Auth/AuthSpec.hs) | role/claims별 API 응답, DB grants/RLS fixture의 전제 |
| [Realtime broadcast_handler_test.exs](https://github.com/supabase/realtime/blob/f86df8c33ef0d014d009e4ff55e3ba18a546cb07/test/realtime_web/channels/realtime_channel/broadcast_handler_test.exs) | channel 메시지·permission·mock된 외부 경계 |
| [Storage apikey.test.ts](https://github.com/supabase/storage/blob/eccef5e70a67fb4030e0646e5e22602c94f568bc/src/http/plugins/apikey.test.ts) | API key 처리와 사용자 권한을 같은 것으로 취급하지 않는가? |
| [CLI apply_test.go](https://github.com/supabase/cli/blob/66ccc6f63a9a26b29c368698994a0843d23b80be/apps/cli-go/internal/migration/apply/apply_test.go) | migration apply의 입력·실패·history와 실제 restore의 차이 |
| [Supavisor db_handler_test.exs](https://github.com/supabase/supavisor/blob/e616317d74fbdd63324c3314aca6bb08cf764326/test/supavisor/db_handler_test.exs) | backend lifecycle·protocol state, 실행 mode/config의 전제 |

## 4. 제한된 테스트 entry point와 부작용

다음 명령은 upstream manifest에서 이름/범위를 확인한 **실행 후보**이며 이 저장소에서 실행한 결과가 아닙니다. 별도 checkout·toolchain·dependency lockfile·폐기 가능한 test DB를 준비해야 합니다. 실제 로그 없이 통과 체크를 하지 않습니다.

| checkout/cwd | 후보 | 근거와 사전 검토 |
| --- | --- | --- |
| Storage root | `npm run test:unit -- src/http/plugins/apikey.test.ts` | [package.json](https://github.com/supabase/storage/blob/eccef5e70a67fb4030e0646e5e22602c94f568bc/package.json), [unit config](https://github.com/supabase/storage/blob/eccef5e70a67fb4030e0646e5e22602c94f568bc/vitest.unit.config.ts). 전체 npm test는 infra 재시작·dummy data 입력도 포함하므로 대체하지 않음 |
| Auth root | `make test CHECK_FILES=./internal/models` | [Makefile](https://github.com/supabase/auth/blob/ce9a8eee0cc042be8c7a42981a7ddae631e41d91/Makefile)의 범위 변수. DB fixtures/migrations·race toolchain 필요. 테스트 DB 대상 확인 후에만 실행 |
| Realtime root | `mix test test/realtime_web/channels/realtime_channel/broadcast_handler_test.exs` | [mix.exs](https://github.com/supabase/realtime/blob/f86df8c33ef0d014d009e4ff55e3ba18a546cb07/mix.exs)의 test alias가 epmd/distribution·ecto.create·ecto.migrate를 호출. **읽기 전용 명령이 아님** |
| CLI apps/cli-go | `go test ./internal/migration/apply` | [package.json](https://github.com/supabase/cli/blob/66ccc6f63a9a26b29c368698994a0843d23b80be/apps/cli-go/package.json)의 Go test entry point에서 범위 축소. package의 mock/외부 연결 fixture를 먼저 검토 |

PostgREST는 [고정 CONTRIBUTING](https://github.com/PostgREST/postgrest/blob/58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19/CONTRIBUTING.md)과 [Nix 개발 환경](https://github.com/PostgREST/postgrest/blob/58a8cb9d17ee7b31c6c15c06ebe402d2ffacce19/nix/README.md)을 읽고 플랫폼을 정합니다. 이 교재가 Windows 호스트에 Nix/Elixir/Rust/Go를 설치했다거나 전체 build가 된다고 주장하지 않습니다.

`db reset`, remote migration apply/repair, installer, 전체 infra test target은 source reading의 필수 실행 명령이 아닙니다. shared/hosted 프로젝트를 test endpoint로 쓰지 않습니다. 격리 프로젝트·DB 이름·포트·volume·credential 범위를 먼저 적고 기존 사용자 데이터에 닿지 않는다는 것을 확인합니다.

## 5. SU13 연구 노트와 SU14 연결

1. 요청 하나를 고릅니다. 예: tenant A 사용자가 tenant B task를 읽거나 signed URL을 만들려는 요청. 인증 identity와 업무 tenant membership을 분리합니다.
2. HTTP/JWT → gateway → service → DB role/claims → policy → 응답/side effect의 경계를 표시합니다. 거절이 401/403/빈 결과 중 무엇인지 실제 계약으로 기록합니다.
3. `public.su_lab_tasks`, `public.su_lab_memberships`의 synthetic claims 시험과 **실제 Auth에서 얻은 테스트 사용자 token의 API 시험**을 구별합니다. role을 직접 바꾼 SQL은 JWT 검증을 우회한 모델 실험입니다.
4. 위 구현 4개 이상과 서로 다른 구성요소 테스트 3개를 연결해 재현 가능한 실패 입력을 설계합니다. 부족한 SDK/SSR 또는 PostgreSQL 내부 경로는 실제 버전 기준으로 지도를 확장합니다.
5. authority 우회·refresh 경합·reconnect gap·object/metadata 불일치 중 하나만 바꾸고 expected/actual을 비교합니다. 전체 stack을 동시에 바꿔 원인을 흐리지 않습니다.

SU14의 2주 mini-capstone은 이전 모듈의 작은 API/권한·command·private object·재조회 경로를 재사용하고, 응답 유실/재시도와 disconnect 중 membership 철회의 두 실패에 집중합니다. full managed platform 재구축, 전체 CDC delivery 보장, 전체 object-store DR 인증은 별도 과제입니다. 실행하지 못한 조건은 LOCAL-PREP/BUILD/설계 단계로 남기고 [평가 게이트](assessment.md)로 검증 상태를 판정합니다.
