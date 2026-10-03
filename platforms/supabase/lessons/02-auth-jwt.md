# SU03–SU04. 인증 정보의 수명과 SSR 경계

[커리큘럼](../curriculum.md) · 이전: [플랫폼](01-platform-postgres.md) · 다음: [RLS와 API](03-rls-api.md)

<a id="su03"></a>
## SU03 API key와 사용자 JWT는 무엇을 증명하는가 · BUILD

**선수 조건:** SU01, HTTP header, encoding과 encryption의 차이, 공개키 서명의 목적. [로컬 준비](../labs/local-lab.md) 후 테스트 사용자만 사용합니다.

### 원리

현재 publishable `sb_publishable_...`와 secret `sb_secret_...`는 애플리케이션 credential이며 JWT 자체가 아닙니다. legacy `anon`/`service_role`은 JWT 형식입니다. publishable 경로에서 사용자 JWT가 없으면 anon, 인증된 사용자 문맥이면 authenticated가 적용됩니다. server secret 경로의 service_role은 BYPASSRLS 권한을 가지므로 서버 전용입니다. grants까지 없어도 모든 객체를 읽는 만능 권한이라는 뜻은 아닙니다. 실제 Authorization 문맥과 SDK의 세션/헤더를 확인해야 하며, 키 이름만 보고 최종 role을 추측하지 않습니다. [API keys](https://supabase.com/docs/guides/getting-started/api-keys)

JWT payload를 Base64URL decode한 결과는 검증된 사용자 정보가 아닙니다. signature·허용 algorithm·issuer·expiry·서비스가 요구하는 audience 등을 검증하고 나서 claim을 사용합니다. Supabase Auth 토큰은 `getClaims()` 또는 적절한 검증 라이브러리로 확인합니다. JWKS에는 비대칭 signing key의 공개 부분만 나오므로 legacy shared-secret 방식에서 빈 JWKS가 관찰될 수 있습니다. `sub`는 사용자 식별, `role`은 DB 역할 문맥이며, 문자열 tenant ID가 들어 있다는 사실만으로 tenant 가입을 증명하지 않습니다. [JWT 문서](https://supabase.com/docs/guides/auth/jwts)

서명 키 회전, API key 폐기, 사용자 logout, tenant 탈퇴는 서로 다른 사건입니다. 캐시된 공개키, 이미 발행된 access token, refresh session, DB membership의 수명이 다르기 때문입니다. “관리 화면에서 제거 버튼을 눌렀으니 모든 요청이 즉시 거부된다”를 요구사항으로 삼으려면 각 검증 경로의 지연과 추가 검사를 설계해야 합니다. [Signing keys](https://supabase.com/docs/guides/auth/signing-keys)

### 실험: credential 행렬과 조작 토큰

완성 앱은 제공하지 않습니다. 학습자가 최소 Node/브라우저 harness를 작성하여 **공개 키를 쓰는 사용자 client와 관리 client를 분리**합니다. 로컬 Auth API/SDK로 테스트 사용자 A/B를 만들고 정상 login 결과를 얻습니다. 관리 credential로 사용자 세션을 생성하거나 로그인하는 일을 같은 client에서 섞지 않습니다. 실제 사용자 UUID는 이후 fixture의 가명 A/B에 매핑합니다.

다음 여섯 요청을 같은 test table에 보냅니다. 원문 token은 출력하지 않고 상태·에러 분류·반환된 PK 집합·credential 종류만 기록합니다.

| 요청 | 사전 예상할 검사 |
| --- | --- |
| credential 없음 | gateway/API가 어떤 인증 누락으로 거부하는가 |
| publishable만 있음 | anon context; 사용자용 데이터는0행 또는 grant 거부 |
| publishable + 유효한 A JWT | A 정책만 통과 |
| publishable + B JWT | B 정책만 통과, A PK 필터로 우회 불가 |
| 서명 부분이 잘못된 A JWT / 만료 token | RLS 전에 인증 거부; 단순 decode와 구별 |
| 서버 격리 client의 secret 또는 해당 환경 legacy service key | 명시된 privileged operation만 실행; RLS 우회 위험이 관찰됨 |

SU05 이전에는 접근을 닫은 SU02 table로 인증/권한 에러 분류만 수행하고, PK oracle은 SU05 이후 재실행합니다. 토큰 조작은 **학습용 본인 프로젝트의 테스트 토큰**에만 수행합니다. 임의 문자열을 정상 JWT처럼 표시하지 않습니다. SDK 버전/서명키 방식에 따라 검증이 로컬 공개키 확인인지 Auth 서버 호출인지 network trace로 구분합니다.

**반증:** A JWT의 `sub`를 B로 바꾼 뒤 signature는 그대로 둡니다. decode는 가능하지만 검증은 실패해야 합니다. `user_metadata`에 `admin:true`를 넣을 수 있다는 사실은 SU05에서 권한 근거로 쓰면 안 되는 이유가 됩니다. 사용자 통제 metadata와 서버 관리 claim을 별도 취급합니다.

**독립 oracle:** 기대 principal과 허용 PK는 token payload가 아니라 테스트 사용자 등록 원장·membership fixture에서 결정합니다. bundle·source map·로그에서 secret prefix, legacy privileged JWT, refresh token이 발견되지 않는지 검사합니다. 발견 시 값 자체를 보고서에 복사하지 말고 노출 위치만 기록하고 해당 테스트 credential을 폐기합니다.

**산출물·통과:** credential matrix6개, negative token2개 이상, 검증 호출 경로, 키 회전/캐시 설계표. claim decode를 인증으로 쓰거나 비밀키를 browser에 두면 점수와 관계없이 재수행합니다. [소스 지도](../source-reading.md)에서 SDK 요청 구성과 Auth token 검증 중 한 경로를 추적합니다.

<a id="su04"></a>
## SU04 refresh rotation, SSR, 권한 철회 · BUILD / HOSTED-DESIGN

**선수 조건:** SU03, cookies, CSRF/XSS, async 경쟁 조건. 실제 provider 이메일·OAuth 설정이 없으면 local 테스트 방식으로 제한하고 외부 login을 완료했다고 쓰지 않습니다.

### 원리

access token은 유효기간 동안 검증 가능한 증명이고 refresh token은 새 access token을 얻는 세션 credential입니다. refresh는 rotation과 재사용 탐지를 포함하며, 응답이 유실된 정상 client와 탈취된 token 재사용을 구별하기 위한 예외가 존재합니다. 현재 기본 reuse interval과 active token의 parent 처리 같은 구체 규칙은 설치된 Auth 버전과 [세션 문서](https://supabase.com/docs/guides/auth/sessions)를 대조합니다. 숫자를 보안 보장으로 하드코딩하지 않습니다.

SSR은 browser와 server가 같은 사용자의 최신 세션을 공유해야 합니다. PKCE code 교환, cookie 갱신, 요청별 client 생성, 응답 cache 정책이 함께 맞아야 합니다. 다른 사용자 요청에 session을 가진 client를 전역 재사용하거나 `Set-Cookie` 응답을 공용 cache에 넣으면 사용자 간 인증 정보가 뒤섞일 수 있습니다. DB connection pool 재사용과 **사용자 세션을 가진 Supabase client 재사용**은 별개의 판단입니다. [SSR advanced guide](https://supabase.com/docs/guides/auth/server-side/advanced-guide)

`getSession()`으로 local cookie/storage에서 읽은 session만으로 서버 권한을 확정하지 않습니다. 서명·만료 확인과 session의 현재 폐기 여부 확인도 구별합니다. 민감 작업에 현재 사용자 확인, membership 조회, 재인증/MFA 중 무엇이 필요한지 위협 모델에서 정합니다. [서버 client 구성](https://supabase.com/docs/guides/auth/server-side/creating-a-client)

### 실험 A: 두 browser의 세션 격리

BUILD로 최소 SSR 페이지 한 개와 API endpoint 한 개를 만듭니다. 화면은 실제 이메일 대신 테스트 가명·tenant ID만 표시합니다. 사용자 A/B를 독립 browser context에서 login하고, 요청별 server client를 만듭니다. framework용 공식 cookie adapter가 갱신 cookie와 필요한 cache header를 실제 response에 적용하는지 검사합니다. httpOnly cookie 사용 가능성은 server-only/BFF와 browser SDK refresh 구조에 따라 달라지므로 옵션 하나로 모든 보안 문제가 해결된다고 주장하지 않습니다.

1. A/B 요청을 교대로20회, 이어 동시에20회 보내고 각 응답 principal을 원장과 대조합니다.
2. refresh가 일어나는 시점에 같은 과정을 반복합니다. `Set-Cookie`가 다른 사용자의 응답에서 재사용되지 않는지 fingerprint만 비교합니다.
3. 수동으로 cookie payload를 변경한 요청은 인증 오류가 나야 합니다. `getSession()`만 믿는 잘못된 구현은 로컬 mock 단위 테스트로 비교하고 외부에 배포하지 않습니다.
4. CDN을 실제 사용하지 않으면 production CDN 검증은 HOSTED-DESIGN입니다. cache key·private/no-store·실제 cache policy 및 동적 route 구성을 점검하는 절차를 제출합니다.

### 실험 B: 권한 철회는 언제 반영되는가

A의 access token을 보관한 client와 별도 관리자 동작을 분리합니다. tenant membership 제거, refresh session 폐기, signing key 회전은 한 번에 하나씩만 바꿉니다. local에서 지원하지 않는 회전은 설계로 남깁니다. 변화 전후에 기존 JWT 검증, 새 access token 발급, membership 기반 RLS 조회를 각각 호출합니다. 시각·token `exp`·세션 ID의 비식별 fingerprint·DB membership 상태를 나란히 기록합니다.

JWT `app_metadata` 기반 정책에서는 기존 claim이 refresh 전까지 남을 수 있습니다. DB membership 기반 정책은 새 DB snapshot에서 제거가 반영될 수 있지만 열린 Realtime 채널의 권한 갱신은 별도 계약입니다. access token의 offline 서명 검증이 성공해도 “그 session은 현재 폐기되지 않았다”까지 증명한 것은 아닙니다. [세션 종료와 JWT](https://supabase.com/docs/guides/auth/sessions)

**실패 주입:** refresh 응답을 client가 저장하기 직전에 버리는 네트워크 mock을 넣습니다. 다음 시도에 어떤 token을 재사용하는지 기록하되 재사용 예외를 공격 방지 전체로 과대해석하지 않습니다. 외부 요청을 무제한 재시도하거나 실제 사용자 계정으로 실험하지 않습니다.

**통과:** A/B 교차 principal0건, 변조 token 승인0건, refresh 실패/재시도 경로1건, logout·membership·key rotation의 서로 다른 반영 시점 설명. 실제 실행한 시간선과 미실행 설계를 구별해야 합니다. 비밀값 없는 threat model과 회귀 테스트를 다음 SU05에 전달합니다.
