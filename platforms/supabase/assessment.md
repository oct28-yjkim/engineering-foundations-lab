# Supabase 평가: 인증·권한·상태·복구를 연결한 증거

**운영 필수 gate:** [운영 runbook](operations.md)의 실제 baseline, 서로 다른 사건 2개, 사건마다 최소 두 경쟁 가설·지표/SQL/로그의 배제 증거·제한 변경/원복·회복 후 동일 권한/업무 상태를 제출합니다. oracle JSON/정적 SQL 검사·준비 완료는 운영 통과가 아닙니다. 환경/권한이 부족하면 미실행 상태를 명시하고 설계 평가와 분리합니다. 아래 기존 점수와 권한/복구 gate도 계속 적용합니다.

[커리큘럼](curriculum.md) · [소스 지도](source-reading.md) · [실습 범위](labs/local-lab.md)

평가 대상은 서비스 메뉴를 아는 것이 아니라 **누가 어떤 데이터에 어떤 경로로 접근하며 실패 후 무엇이 남는지 검증하는 능력**입니다. 14개 모듈/28주의 누적 포트폴리오와 SU14의 2주 mini-capstone을 구분합니다. 완성 앱·클라우드 프로젝트·self-hosted 배포가 이 저장소에 제공되거나 이미 실행됐다고 가정하지 않습니다.

## 1. 준비·구현·설계·검증의 구별

| 과제 범위 | 완료 증거 | 아직 완료가 아닌 것 |
| --- | --- | --- |
| LOCAL-PREP | 학습자가 준비한 CLI/local DB 지문, 격리 대상, synthetic SQL 결과 | CLI 설치나 SQL 파일 열기만으로 실제 Auth/API 검증 |
| BUILD | 직접 만든 앱/handler/client, 작은 입력, 실제 응답/상태 oracle | 의사코드·source reading을 실행 앱으로 표기 |
| HOSTED-DESIGN | 사용 권한·비용·리전·역할·backup/restore·실행 게이트의 설계 | hosted console를 보거나 문서를 읽은 것을 운영 검증으로 인정 |
| INTEGRATION-DESIGN | 시스템 경계·event 계약·replay/중복·보안·복구 oracle 설계 | 연결선 그림만으로 CDC·exactly-once·DR 완료 |

모든 실험은 별도로 미실행/실행/검증을 표시합니다. 실제 결과가 없는 경우 설계 평가를 받을 수 있지만 실행 필수 게이트를 대신하지 못합니다. managed 내부 image/commit이 비공개이면 unknown을 기록하고 설치 SDK/CLI·API 계약·시각을 근거로 삼습니다.

## 2. 공통 점수표: 25 × 4

총점 **80/100 이상**, **각 영역 15/25 이상**, 아래 **필수 게이트 전부 통과**가 선언한 범위의 검증 통과 조건입니다. 기능이 많아도 tenant 정보 노출을 점수로 상쇄할 수 없습니다.

| 영역 | 배점 | 15점: 최소 충족 | 20점: 독립 재현 가능 | 25점: 전문가 수준 증거 |
| --- | --- | --- | --- | --- |
| 정확성 | 25 | 인증·인가·DB role·tenant·commit/수신 경계 구분 | 허용/거절 matrix·ID별 결과·상태 불변식을 독립 oracle로 검사 | 우회 경로·경합·일부 실패·복구 후 상태까지 정확하게 판정 |
| 메커니즘·소스 | 25 | 실제 component 버전/commit과 상태 전이 설명 | API→service→DB/객체/worker 경계를 소스와 테스트로 연결 | 설정/버전별 분기·mock·권한 위임·실패 시 소유권을 반례와 함께 증명 |
| 실험·반증 | 25 | 작은 fixture·예상/실제 구분·한 변인 | 음성 요청·동시성·재시작/재접속·독립 원장으로 가설 시험 | 위조/만료/교차 tenant·실패 타이밍별 대조군·관찰 한계와 대안 설명 |
| 운영·재현성 | 25 | 명령·버전·대상·secret 처리·원복 경계 | bounded 실행·migration 전후 비교·복구 검산·runbook | 제3자 반복, 중단 조건, rollback 불가능성 처리, 데이터 종류별 복구 한계 |

0점은 증거 없음 또는 조작, 1–14점은 중요한 계약 오류/재현 누락입니다. 16–19점과 21–24점은 인접 기준의 부분 충족입니다. 서비스 수·테이블 수·코드 줄 수가 높다고 자동 가산하지 않습니다.

## 3. 필수 게이트

### G1 — 대상 격리·권한·component 지문

local/linked/remote endpoint를 명시하고 프로젝트·DB·schema/table·bucket·channel·function 이름, 합성 데이터 수, 최대 요청률·대기 시간·비용 한도를 적습니다. CLI·PostgreSQL·SDK·Auth/API/Realtime/Storage/Edge/pooler를 독립 버전으로 취급합니다. source reading SHA를 실제 서비스 버전으로 채우지 않습니다. 운영/공유 프로젝트에 실험용 reset·migration repair·secret 교체·bucket 삭제를 수행하면 실패입니다.

### G2 — 두 tenant의 음성 권한 matrix

최소 두 tenant, 비인증 요청과 아래 oracle의 실제 synthetic 사용자/역할로 read/create/update/delete를 대조합니다. **자기 tenant 허용과 다른 tenant 거절**을 모두 증명해야 합니다. 거절의 API 표현이 빈 결과·403·기타 오류 중 무엇인지는 실제 계약으로 기록하고 단순 status code 하나로 정책을 판정하지 않습니다. 본인이 작성한 row의 tenant/owner key를 다른 값으로 바꾸는 update도 검사합니다.

SU05의 구체 통과 기준은 [authorization-oracle.json](labs/authorization-oracle.json)의 **18/18 케이스**입니다. 원장의 일반 회원·tenant admin·다른 owner·membership 없는 anonymous Auth 사용자·철회된 membership 사용자·signed-out을 실제 synthetic identity에 매핑합니다. tenant/owner는 tenant admin에게도 API상 불변이며, 오래된 유효 JWT가 있더라도 현재 membership 철회가 새 DB transaction의 read/write에 반영되어야 합니다. 허용된 새 값의 내용과 거부 후 원래 상태 보존도 검사합니다.

테이블 owner·superuser·BYPASSRLS·service 권한만으로 통과한 SQL은 일반 사용자 RLS 검증이 아닙니다. secret/service credential을 browser·공개 repo·보고서에 노출하거나 RLS를 끄고 결과를 맞추면 즉시 실패입니다. 뷰/RPC를 범위에 넣었다면 해당 invoker/definer와 search_path/권한 위임도 음성 검사합니다.

### G3 — SQL claims 모형과 실제 Auth/API를 분리

SU05의 `public.su_lab_tasks`, `public.su_lab_memberships` 및 synthetic request claims 시험은 PostgreSQL 정책 모형입니다. 직접 role/claim을 설정했다고 JWT signature·만료·issuer/audience 검증이 된 것이 아닙니다. BUILD 통과에는 학습자가 승인한 실험 Auth에서 발급받은 사용자 token으로 API 요청을 별도 실행하고 잘못된/만료된 token의 음성 사례도 제출합니다. token 본문·서명·refresh token은 증거에서 제거합니다.

SQL fixture만 준비한 제출은 LOCAL-PREP 검증으로 제한하며 실제 로그인/SSR 보안 통과를 주장하지 않습니다. hosted 환경을 새로 만들 필요는 없지만 실행 대상과 권한이 없으면 실제 Auth/API 게이트는 미통과로 남깁니다.

### G4 — session·credential의 생명주기

access JWT·refresh token·API key·service credential의 역할을 구분합니다. logout/revocation 뒤 이미 발급된 access JWT가 즉시 모든 경로에서 무효화된다고 가정하지 않고 실제 정책·만료·검증 방식을 기록합니다. SSR을 선택했다면 cookie 전파·refresh 경합·서버에서 검증한 identity와 단순 저장 session 값을 분리합니다. 모든 secret을 공유 로그에 출력하는 디버깅은 실패입니다.

### G5 — 실패 후의 상태와 복구 oracle

범위 내에서 실패 하나를 재현하고 side effect·metadata·client 표시·재시도 상태를 구분합니다. 예: 중복 HTTP 요청, 임시 API 실패 후 재시도, Realtime 재연결 뒤 snapshot 재조회, 제한된 migration 실패. 성공 응답이나 최종 count만 보지 말고 ID별 적용 횟수·tenant 귀속·내용 checksum 등 독립 oracle을 사용합니다. 실패 증거를 삭제하거나 offset/정책/원장을 조작해 통과 처리하면 실패입니다.

### G6 — 소스·재현성·미검증 범위

고정 source 경로 4개 이상과 서로 다른 구성요소 테스트 3개 이상, 실제 요청의 trust boundary를 연결합니다. upstream test를 읽은 것과 실행한 것을 구별합니다. command·cwd·버전·fixture·expected/actual·실패 기록·종료/보존 범위를 제출합니다. Postgres backup만 복구하고 Storage object bytes까지 복구했다고 주장하거나 WebSocket 수신을 영속 업무 처리 완료로 부르면 실패입니다.

## 4. 모듈별 통과 증거

| 모듈 | 최소 증거 | 허용하지 않는 지름길 |
| --- | --- | --- |
| SU01 아키텍처 | gateway→Auth/API/Realtime/Storage/Edge→Postgres/object store의 identity·state 지도 | Supabase 전체를 한 서버·한 버전으로 가정 |
| SU02 PostgreSQL·connection | direct/session/transaction pool의 연결 지문, backend/transaction 경계 비교 | pooler 연결 수와 DB backend 수를 동일시 |
| SU03 Auth·JWT | 정상/위조/만료 token의 실제 검증 경로, 서명/claims/권한 구분 | decode한 JWT를 검증된 사용자로 취급 |
| SU04 sessions·SSR | refresh/동시 요청/cookie 전달 timeline과 secret 없는 관측 | getSession의 저장 값만으로 서버 권한 허용 |
| SU05 RLS | 두 tenant·두 사용자·anon matrix, INSERT/UPDATE의 새 값 및 교차 tenant 음성 검사 | owner/service role로만 SQL 실행, policy OR 결합 누락 |
| SU06 PostgREST·RPC·view | role/claim·schema cache·RPC/view 권한 경로와 음성 요청 | frontend filter를 권한 검사로 대체 |
| SU07 Postgres Changes·WAL | source commit·slot/backlog·subscription·client 수신 구분, 재접속 누락 범위 | client 수신만으로 durable consumer/영구 replay 보장 주장 |
| SU08 Broadcast·Presence | private channel 권한, join/leave/reconnect·state merge fixture | Presence를 authoritative membership DB로 사용 |
| SU09 Storage | metadata RLS와 object bytes, public/private·signed URL의 실제 접근 matrix | DB metadata count를 object 내용 복원으로 간주 |
| SU10 Edge Functions | identity/secret·idempotency·timeout·side effect 경계의 작은 handler | function timeout이면 외부 side effect도 없다고 단정 |
| SU11 migration·pooler·CI | 적용 대상 확인·schema/history diff·실패 전후 상태·CI 최소 권한 | 생성 diff 무검토 적용, 공유 DB reset, remote repair로 증거 은폐 |
| SU12 backup·DR·security | DB/objects/config/keys의 독립 복구 계획, 별도 대상 restore의 검사 또는 미실행 표시 | 플랫폼 backup 하나면 모든 객체·설정·외부 시스템 복구라는 주장 |
| SU13 소스 연구 | 4개 구현·3개 테스트·권한/상태 경계 하나의 반증 노트 | 현재 문서와 과거 runtime의 차이를 무시 |
| SU14 mini-capstone | 아래 제한된 앱/권한/실패/oracle/handoff | 전체 BaaS 또는 HA/DR 인증으로 확대 |

설계형 SU07/SU12/통합 확장을 실행하지 않았다면 해당 행의 실제 장애·복구 실험은 미완료입니다. 필수 gate 충족은 선언한 mini-capstone 범위의 통과이며 모든 hosted/self-host 운영 능력의 자동 인증이 아닙니다. 전체 과정 완료 보고서는 모듈별 실행/설계 상태를 함께 공개합니다.

## 5. SU14: 2주 mini-capstone의 고정 경계

주제는 **두 tenant의 작은 문서/task 앱**입니다. 이전 모듈의 membership/task·Auth/API·idempotent command·private object 하나·Realtime 알림 후 DB 재조회 코드를 재사용합니다. UI는 CLI 또는 작은 화면으로 제한하고, 전체 18개 oracle의 추가 identity/tenant admin·delete 권한 검증은 API harness로 수행합니다. 이 모든 서비스를 새로 작성하는 2주가 아니라 이미 검증한 작은 경로를 묶는 24시간 예산입니다. 외부 결제·메일·대규모 CDC·HA는 제외합니다.

| 기간 | 산출물·종료 조건 |
| --- | --- |
| 1–2일 | 실험 대상·버전·threat model·두 tenant fixture·허용/거절 oracle 고정 |
| 3–5일 | 이전 모듈의 얇은 앱/API·command·private object·reconcile 통합, 실제 사용자 token과 18개 oracle |
| 6–8일 | 아래 두 실패, 재시도/재조회 후 원장·상태 검산, 현재 버전의 SU12 bounded restore 증거 연결 |
| 9–10일 | source/테스트 노트, 새 run 재현, secret 검사, 동료 리뷰·runbook·미완료 목록 |

기본 fixture는 원장의 두 tenant·문서3개로 시작합니다. **F1**은 command commit 뒤 응답 유실과 같은 ID 재시도입니다. ledger 1개·business mutation 1회·정확한 title을 검산하고 같은 ID/다른 payload는 거절합니다. **F2**는 client disconnect 중 membership 철회입니다. 이전 유효 JWT의 새 API 요청은 R06 계약을 지키고 앱 cache를 정리해야 하며, Realtime 재가입/기존 channel의 실제 경계는 따로 관찰합니다. 객체 bytes는 입력 hash와 비교합니다.

race 시험은 시도 횟수·동시성·기대 가능한 상태 집합을 고정하며 몇 번의 성공으로 모든 부하를 보장하지 않습니다. 비용·권한·환경 제약으로 앱 실행이 불가능하면 코드를 포함한 BUILD 준비와 설계를 제출하되 verified mini-capstone으로 표기하지 않습니다.

필수 결과는 정상 요청 run, 18개 권한 case, 두 실패와 회복 run, 현재 schema/policy의 bounded data/object restore 증거, migration/설정 지문, source boundary 노트와 handoff입니다. 전 서비스 자체 호스팅, global HA, 전체 Auth/session/PITR DR, PostgreSQL→Kafka→ClickHouse 통합은 2주 필수 범위에서 제외합니다. 전체 앱 통합은 별도의 [8주 보안·관측 앱 캡스톤](../../capstones/secure-observable-app.md)으로 이어지며 기존 데이터 통합 캡스톤과 선택 관계입니다.

command 앱의 복원 증거에는 `su_lab_command_ledger`와 `su_lab_task_audit`를 업무 데이터와 같은 일관성 기준으로 포함합니다. 새 target의 actor UUID·요청 identity mapping·RPC/권한을 복구하고 **기존 command 재전송이 추가 business mutation을 만들지 않는지** 검산합니다. SU12의 두-table 기본 실험만으로 command 앱 전체 복원 통과를 대신하지 않습니다.

## 6. 제출 패키지·구술 방어

제출물에는 run ID, 합성 fixture와 checksum, schema/policy/view/RPC 정의, 사용자/역할의 익명화 식별자, 버전·endpoint 범위, 요청/응답의 비밀 제거본, expected/actual matrix, 변경/종료/원복 절차가 필요합니다. JWT·cookie·connection secret·실제 고객 데이터는 포함하지 않습니다. API 응답만으로 원래 입력 원장을 대신하지 않습니다.

다음 질문 중 세 개 이상에 소스나 실제 결과를 연결해 답합니다.

1. 올바르게 서명된 사용자 JWT가 있어도 다른 tenant row가 안 보여야 하는 이유와 집행 위치는 어디인가?
2. SQL에서 직접 설정한 claims 시험과 실제 Auth→PostgREST 요청 사이에 어떤 검증이 추가되는가?
3. transaction pooling에서 session state·prepared statement·migration client의 동작을 어떤 version/mode 기준으로 확인하는가?
4. WebSocket 재접속 뒤 “화면이 다시 연결됨”과 “데이터가 빠짐없이 최신임”은 어떻게 다른가?
5. PostgreSQL restore가 성공한 뒤에도 Storage object·Auth 설정·키·Edge 외부 부작용 중 무엇을 추가 검산해야 하는가?

최종 판정은 점수뿐 아니라 **신뢰 경계·음성 검사·실행 범위의 정직한 표시**를 포함합니다. 통과 범위와 남은 운영/통합 실험을 함께 기록해야 다음 단계로 진행할 수 있습니다.
