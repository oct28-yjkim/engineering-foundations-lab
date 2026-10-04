# Supabase 실습 준비: 관리 계정의 성공과 사용자 격리를 구분하기

이 저장소는 Supabase 전체 스택, CLI, Auth 사용자, migration, SDK 앱을 미리 생성하지 않습니다. 제공되는 것은 [18개 권한 reference case](authorization-oracle.json)와 준비·검증 명세입니다. JSON은 **기대 결과**이며 RLS 실행기나 JWT 발급기가 아닙니다. 실제 정책·테스트·서비스는 학습자가 구현합니다.

## 1. 세 환경을 구분한다

기존 승인 환경이 있으면 설치부터 반복하지 말고 [운영 실습](../operations.md)의 read-only 연결/lock/query baseline으로 시작합니다. 실제 지표·로그·Auth/RLS·Realtime/Storage 증상과 회복 검증이 기본이며 JSON/모형 검사는 보조 자료입니다. 새 환경이 필요할 때만 아래 준비를 수동 수행합니다.

| 환경 | 준비 방법 | 확인할 범위 |
| --- | --- | --- |
| 기존 PostgreSQL lab | [PostgreSQL 전용 Compose](../../../databases/postgresql/compose.yaml)와 [환경 안내](../../../databases/shared/environment.md); 다른 제품과 독립 실행 | SQL·MVCC·WAL·일반 role/RLS 원리. Supabase Auth/API는 없음 |
| Supabase CLI local | 별도 초기화한 학습 폴더 + 고정 CLI + Docker | 해당 local stack의 Auth·API·RLS·Realtime·Storage·Functions |
| hosted / self-hosted | 별도 프로젝트 또는 공식 배포 구성 | 실제 배포의 pooling·network·backup·권한·운영 계약 |

셋은 같은 환경이 아닙니다. local stack의 동작으로 hosted의 plan·보존·지역·가용성을 증명하지 않습니다. 자체 호스팅은 [공식 안내](https://supabase.com/docs/guides/self-hosting)를 따르는 추가 운영 과제입니다. 이 커리큘럼 추가 과정에서는 설치·클라우드 생성·배포·migration을 실행하지 않았습니다.

## 2. 학습자가 준비할 CLI local

CLI는 [공식 설치 문서](https://supabase.com/docs/guides/local-development/cli/getting-started)에서 지원하는 방법을 선택하고 정확 버전을 기록합니다. 프로젝트 dependency 방식을 쓰면 lockfile에 고정하고 그 프로젝트의 runner로 실행합니다. 아래는 **전역 `supabase` 명령이 준비된 경우**의 예입니다. 이 저장소에서 `npx`로 임의 최신 버전을 자동 설치하는 절차는 제공하지 않습니다.

저장소 루트 아래 `lab-workspaces/supabase-local`이라는 **새로운 실습 폴더**를 만들고 그 폴더로 이동합니다. 이 경로는 실습용 비밀과 생성 파일을 실수로 커밋하지 않도록 `.gitignore`에 포함했습니다. 이미 사용 중인 프로젝트가 있다면 다른 새 폴더를 선택합니다. 다음 명령은 저장소 루트가 아니라 새 실습 폴더 안에서 실행합니다.

```text
supabase --version
docker version
supabase init
supabase start
supabase status
```

`init`은 최초 한 번만 수행하고, `start`의 성공 및 서비스 상태를 확인합니다. `status` 출력에는 로컬 개발용 key·DB 접속 정보 등이 포함될 수 있으므로 전체 출력을 저장소·스크린샷·보고서에 붙이지 않습니다. endpoint의 host/port, 제품 버전, 비밀이 아닌 설정만 골라 기록합니다. [공식 local workflow](https://supabase.com/docs/guides/local-development)

CLI가 생성한 config의 project ID·포트·노출 범위를 확인합니다. 루트 PostgreSQL의 포트/volume에 연결된 것으로 가정하지 않습니다. 여러 local 프로젝트는 포트가 겹칠 수 있고, Docker 엔진이 없으면 시작할 수 없습니다. SDK 앱은 `status`에서 확인한 **자기 local endpoint**만 사용하도록 검사합니다. local 개발키도 로그에 남기는 습관을 만들지 않습니다.

CLI local stack은 운영용 보안 구성이 아니므로 외부 트래픽에 공개하지 않습니다. 호스트 방화벽·Docker 포트 바인딩도 확인하고, 인터넷 공개가 필요한 경우에는 이 개발 구성을 그대로 노출하지 말고 별도 배포 설계를 수행합니다.

일반 종료는 같은 실습 폴더에서 다음을 사용합니다.

```text
supabase stop
```

여기에는 `db reset`, `stop --no-backup`, 원격 `link`, `db push`, `deploy`를 넣지 않습니다. reset은 데이터가 사라지는 재초기화이며 migration 검증에는 별도 disposable 프로젝트를 먼저 준비합니다. 원격 연결·배포는 명시적으로 대상과 권한을 결정한 다음 수행하는 별도 과제입니다.

## 3. 구성요소별 지문

CLI 버전 하나로 전체 runtime 버전을 대신하지 않습니다. 다음을 비밀 없이 기록합니다.

```text
run_id / local·hosted·self-hosted / CLI 버전·설치 방식
CLI config / 실제 서비스와 이미지 digest / PostgreSQL version·extension
Auth / PostgREST / Realtime / Storage / Edge Runtime / gateway / pooler
SDK 정확 버전·lockfile / 사용한 API key 종류 / 실제 user role
JWT 검증 방식·issuer/audience 정책·서명 key 식별자(비밀 값 제외)
migration revision / exposed schema·grants·RLS / source baseline SHA
복구 범위(DB, Auth 설정, Storage object bytes, Functions·secrets)
```

publishable/secret API key와 legacy anon/service_role, 사용자의 access token을 구별합니다. key 종류만 보고 실제 요청의 사용자·역할을 추측하지 말고 선택 SDK의 session과 Authorization 전달을 확인합니다. privileged client와 일반 user client를 별도 인스턴스로 분리합니다. [API key 계약](https://supabase.com/docs/guides/getting-started/api-keys)

## 4. 권한 oracle를 실제 테스트로 바꾸기

`authorization-oracle.json`의 symbolic user/tenant ID를 자신의 **합성 Auth 사용자 및 실제 ID**에 매핑합니다. 이 파일의 문자열로 JWT를 꾸며내지 않습니다. 비밀번호·refresh/access token은 source에 넣지 않습니다. 입력 DB는 `a1`, `a2`(tenant A), `b1`(tenant B) 문서 3개로 시작합니다.

업무 계약은 다음과 같습니다. 이것은 Supabase의 기본 권한이 아니라 **학습자가 구현할 정책**입니다.

- active member는 자기 tenant의 문서를 읽고, 자기 소유 문서를 추가하거나 제목을 수정합니다. 일반 member의 삭제는 허용하지 않습니다.
- tenant admin은 자기 tenant의 제목 변경·삭제가 가능하지만 다른 tenant에 접근하지 못합니다.
- `tenant_id`와 `owner_id`는 일반 앱 API에서 변경할 수 없습니다. admin도 예외가 아닙니다.
- membership은 신뢰된 서버 상태를 확인합니다. 이 fixture에서는 아직 만료되지 않은 토큰이어도 membership을 해제하면 즉시 접근이 막혀야 합니다.

마지막 조건은 claim-only 권한 모델의 반례를 만드는 업무 요구입니다. 서비스마다 즉시 해제와 token 만료 시 적용 중 무엇을 요구할지 결정해야 하며, claim이 오래됐는데 기대 결과만 바꾸어 통과시키지 않습니다. user-editable metadata나 요청의 tenant 값을 신뢰된 membership으로 사용하지 않습니다.

18개 case는 읽기 6개와 쓰기 12개입니다. **쓰기마다 원래 fixture에서 독립 실행**합니다. 실제 migration에 grants와 RLS를 함께 넣고, `USING`/`WITH CHECK`, column 권한, 제한된 RPC 또는 필요한 trigger 등으로 불변식을 구현합니다. row policy만으로 이전/이후 값의 모든 불변 조건이 자동 해결된다고 가정하지 않습니다. view·SECURITY DEFINER 함수·service role이 우회 경로가 되는지도 따로 조사합니다. [공식 RLS 안내](https://supabase.com/docs/guides/database/postgres/row-level-security)

허용 요청은 반환 행뿐 아니라 실제 새 값까지 검산합니다. 금지된 SELECT가 오류 대신 빈 결과를 줄 수 있고 UPDATE/DELETE가 오류 없이 0행에 적용될 수 있으므로 HTTP status만 검사하지 않습니다. **일반 사용자 응답에 다른 tenant의 payload가 없고 금지 쓰기 후 원본 상태가 변하지 않았음**을 독립 관측자 결과로 확인합니다. 관측용 관리자 계정으로 읽은 전체 행을 사용자 API의 반환으로 혼동하지 않습니다.

`signed_out`은 세션이 없고, `anonymous_auth_user`는 Auth의 anonymous sign-in을 한 별도 사용자입니다. 후자가 `authenticated` 역할을 사용하는 경우를 `anon` PostgreSQL role과 혼동하지 않습니다. 이 fixture에서는 둘 모두 membership이 없어서 접근을 허용하지 않습니다.

최소 두 층의 테스트가 필요합니다.

1. SQL/pgTAP: 실제 역할·claims를 명시하고 정책/권한의 허용·거절을 검사합니다. superuser·table owner·BYPASSRLS로만 테스트하면 사용자 격리 증거가 아닙니다.
2. SDK/HTTP: 실제 local Auth 세션으로 사용자 A/B/admin/세션 없음의 요청을 보내 JWT 검증·role 매핑·API·RLS 전체 경계를 검증합니다. SQL에서 claims를 설정한 모형은 JWT 검증을 증명하지 않습니다.

실제 test 파일을 작성한 뒤에만 local 프로젝트 폴더에서 `supabase test db`를 실행합니다. test 0개, skip, 잘못된 user session으로 실행한 성공을 통과로 세지 않습니다. 이 repo의 JSON 검사 성공은 위 두 실행의 대체가 아닙니다.

## 5. 다른 경계까지 확장

SU07–SU10에서 같은 A/B 권한 원장을 Realtime 채널, Storage path와 다운로드 URL, Edge Function 호출로 확장합니다. DB REST에서 거부됐다는 사실만으로 다른 경로의 격리가 증명되지 않습니다. reconnect 후 데이터 동기화와 인가 해제, signed URL 수명, retry한 함수의 외부 부작용을 각각 검증합니다.

복구는 DB schema/row와 Storage 객체 bytes, Auth 구성/서명 키 수명, 함수 배포·secret 참조를 나눕니다. **DB backup에는 Storage 객체 bytes가 포함되지 않는 범위**를 별도 보완해야 합니다. [백업 문서](https://supabase.com/docs/guides/platform/backups)와 선택 배포의 실제 backup/restore 지원을 대조합니다. 전체 dump가 존재한다는 사실만으로 제품 전체 복원이 완료되지 않습니다.

## 6. 검증 상태

2026-10-04 작성 환경에서 JSON 문법 및 18개 case ID의 유일성을 확인했습니다. 전역 Supabase CLI가 발견되지 않았고 Docker Linux 엔진도 실행되지 않아 **Supabase 기동·실제 JWT·RLS·API 테스트는 미실행**입니다. 결과표에는 기대값과 실제 관측을 별도 칸으로 남깁니다. 준비 후 [28주 과정](../curriculum.md)으로 이어집니다.
