# SU13–SU14. 최소 재현에서 설계 판단까지

[커리큘럼](../curriculum.md) · 이전: [운영·복구](06-operations-migrations.md) · [소스 읽기](../source-reading.md) · [평가](../assessment.md)

<a id="su13"></a>
## SU13 구현을 읽고 가설을 반증하기 · BUILD

**선수 조건:** SU01–12의 주요 실험. 완전한 서비스 코드를 먼저 이해하는 것이 아니라 자신이 관찰한 현상 하나를 최소 입력으로 설명하는 단계입니다.

### 원리

SDK의 한 호출이 여러 repository와 runtime을 지나므로 “Supabase 소스” 하나에서 모든 동작을 찾을 수 없습니다. Auth의 token/session 처리, PostgREST의 transaction/role 설정, PostgreSQL의 RLS, Realtime의 channel authorization, Storage backend 동작, CLI의 orchestration은 각기 다른 구현입니다. 호출 경계의 입력·출력·실패 의미를 연결하면 작은 증거로 넓은 주장을 막을 수 있습니다.

current documentation은 runtime fingerprint와 같은 증거가 아닙니다. 소스 HEAD에서 발견한 기능을 오래된 local image에도 존재한다고 가정하지 않습니다. 먼저 [소스 지도](../source-reading.md)의 repository·snapshot·경로를 참고하고, 실제 runtime과 일치하는 tag/commit을 찾아 별도 기록합니다. 매핑을 찾지 못하면 “구현 연구 baseline, runtime 동일성 미확인”으로 적습니다. upstream 전체 test suite 통과와 자신이 만든 앱의 안전성도 다른 명제입니다.

### 연구 과제: 하나의 현상을 작게 만들기

다음 중 하나를 골라 API/SQL/client 최소 재현을 작성합니다. 운영 계정·실데이터·실제 결제/메일을 사용하지 않습니다.

- **A. RLS는 맞는데 RPC 결과가 넓다:** invoker/definer·function owner·EXECUTE grant·exposed schema 중 한 변수만 바꾸어 원인을 찾습니다.
- **B. JWT는 유효하지만 membership은 폐기됐다:** old token claim과 DB lookup 정책의 반영 시점을 분리하고 열려 있는 channel의 재평가 경계를 찾습니다.
- **C. Realtime server ACK가 있는데 화면에서 누락됐다:** server receive, fan-out, client handler, app state 적용 중 어디까지 확인했는지 추적합니다.
- **D. upload metadata는 보이는데 다운로드가 실패한다:** 객체 bytes 부재, path/policy, credential, cache 상태를 차례로 반증합니다. 서비스 내부 metadata를 직접 바꾸는 재현은 별도 mock으로만 수행합니다.
- **E. commit된 함수 호출이 timeout 뒤 두 번 처리됐다:** idempotency ledger와 business mutation이 같은 transaction인지 확인합니다.

처음에는 synthetic row3개·사용자2명·단일 operation으로 줄이고, 정상/반례를 동일 harness에서 번갈아 실행합니다. 화면 스크린샷 대신 입력 request의 비밀 제거 형태, DB row oracle, SQLSTATE/HTTP error, version manifest, 시간선을 남깁니다. 재현을 단순화하는 과정에서 실제 원인인 concurrency/role을 제거하지 않습니다.

### 소스 추적 계약

소스 checkout은 별도 학습 디렉터리에 준비하고 `git rev-parse HEAD`, clean/dirty 상태, build tool 버전, dependency lock 상태를 남깁니다. 해당 repository의 CONTRIBUTING/test 문서를 읽고 환경에 맞는 **표적 테스트 하나**를 선택합니다. 이 저장소가 Go/Elixir/Haskell/Deno 전체 toolchain이나 디버그 환경을 제공한다고 가정하지 않습니다. 설치가 필요하면 별도 준비 단계로 분리합니다.

call chain에는 최소6개 지점이 있어야 합니다: client request 생성 → credential 처리 → 역할/권한 판단 → 상태 조회/변경 → commit/전달 → 오류/결과 변환. 관련 없는 서비스는 억지로 끼우지 말고 하나의 짧은 경로에서 함수·파일·line·commit을 연결합니다. DB policy와 service code를 연결할 때 request claims가 설정되는 지점을 확인합니다.

1. 정상 입력의 oracle를 먼저 고정합니다.
2. 테스트가 잡아야 하는 잘못된 구현을 한 문장으로 씁니다.
3. mock 또는 local test fixture 한 곳을 의도적으로 바꿔 테스트가 실패하는지 확인합니다.
4. 원래 구현/자신의 수정안에서 다시 통과하는지 확인하고 diff를 리뷰합니다.
5. concurrency·token expiration·API version 차이 등 이 테스트가 보장하지 않는 조건을 적습니다.

소스를 읽기만 했다면 실행 테스트 증거와 분리하고 BUILD gate를 완료 처리하지 않습니다. 외부 issue/PR 생성은 필수도 자동 승인도 아닙니다. 제출용 repro packet을 먼저 완성합니다.

**실패 모드:** 최신 main 코드를 runtime 버전이라고 표시, 같은 implementation으로 예상 결과를 생성, 네트워크 timeout을 DB rollback으로 추론, error message만 검색해 원인을 단정, regression test가 잘못된 구현에서도 통과.

**산출물·통과:** 최소 재현1개, call chain6지점, 독립 oracle, 의도적 실패→복구 테스트, 배포 적용/rollback 위험 분석. 동료는 초기 설명 없이10분 안에 재현 조건·정상과 비정상의 차이를 이해할 수 있어야 합니다. 실제 실행에 필요한 환경 준비시간은 이10분에 숨기지 않습니다.

<a id="su14"></a>
## SU14 두 주 안에 마무리하는 tenant 업무 슬라이스 · BUILD / INTEGRATION-DESIGN

**선수 조건:** SU05/06/09/10/12/13 gate. 전체 PostgreSQL·Kafka·ClickHouse·Sentry 과정을 먼저 끝낼 필요는 없습니다. 새로운 모든 기능을2주 안에 구현하는 과제가 아니라 앞서 검증한 실험을 작은 서비스 흐름으로 묶는 단계입니다.

### 제한된 제품 계약

synthetic “팀 문서 보드”를 만듭니다. 데이터는 oracle의 두 tenant·3개 문서로 시작합니다. UI는 CLI 또는 작은 웹 화면으로 충분합니다. 사용자 login → 허용 문서 읽기 → 자기 문서 title 변경 command → private 첨부파일1개 upload/download → Realtime 알림 이후 재조회 흐름만 포함합니다.

membership은 DB의 trusted 상태를 사용하고 tenant admin과 server maintenance를 분리합니다. idempotency command는 업무 변화와 같은 transaction의 ledger로 검증합니다. Realtime은 빠른 UI 갱신 신호로 사용하며 앱을 다시 열면 authoritative DB snapshot에서 상태를 복구합니다. external payment, production email, multi-region, 대규모 CDC는 구현 범위에서 제외합니다.

### 24시간 작업 예산

| 작업 | 시간 | 종료 조건 |
| --- | ---: | --- |
| 범위·원장·환경 고정 | 3 | feature 목록, exact component manifest, 사용자 가명 mapping |
| 이전 모듈 코드 통합 | 8 | login/API/command/object/reconcile 최소 흐름 |
| 보안·실패 주입 | 6 | oracle18개와 아래 두 장애의 raw evidence |
| 새 대상 복원·문서 | 4 | SU12 bounded restore 증거 재사용 또는 재실행 |
| 동료 리뷰·설명 | 3 | 반례 질의, 제한사항, 후속 설계 결정 |

범위를 넘기면 새 UI나 부가기능을 줄이고 보안/정확성 증거는 유지합니다. 큰 dataset·고급 HA·완전한 배포 자동화는 별도 과제입니다.

### 필수 두 장애와 독립 정답

**F1: commit 이후 응답 유실.** task title 변경 command의 DB commit 뒤 응답을 client가 받기 전에 연결을 끊습니다. client가 같은 command ID로 재시도한 후 고유 ledger1개·business mutation1회·정확한 title을 확인합니다. 동일 command ID에 다른 payload를 보낸 반례도 거부되어야 합니다. “최종값이 같으니1회”가 아니라 별도 transaction 내 audit/version 근거를 제출합니다.

**F2: 권한을 가진 client의 disconnect와 membership 철회.** A client가 끊긴 동안 title을 변경하고 A membership을 비활성화합니다. 이전 유효 JWT로 재접속/REST 조회를 시도합니다. DB API는 oracle R06 계약에 따라 허용 데이터를 반환하지 않아야 합니다. 열린/재가입 Realtime channel의 동작은 따로 관찰하고, 탈퇴 사용자의 화면 cache를 비우는 앱 정책을 구현합니다. 이미 전달된 데이터 자체를 서버가 원격으로 회수할 수 있다고 주장하지 않습니다.

각 장애는 시작 상태·주입 지점·요청 ID·관찰 로그·복구 동작·최종 oracle를 가집니다. 테스트 대상이 반환한 count를 별도 정답으로 삼지 않습니다. 객체는 입력 bytes hash와 비교하고, 앱 restore는 새 target에 data/RLS/객체와 **command ledger/audit까지 같은 복원 범위**로 검증한 SU12 확장 증거를 연결합니다. 복원된 기존 command의 재전송도 업무 효과가 늘지 않아야 합니다. 구버전 manifest를 사용한 증거를 현재 구현 성공으로 재활용하지 않습니다.

### 설계 심사와 다음 과정

아래 질문에 각각 선택·버린 대안·근거·남은 위험을 짧은 ADR로 답합니다.

- 언제 user-scoped Data API/RPC를 쓰고 언제 server privileged path가 정말 필요한가?
- JWT claim과 DB membership 중 어떤 권한을 어디에 두며, 철회 지연을 어떻게 제한하는가?
- DB row·객체 bytes·외부 효과·알림 각각의 commit/retry/복구 경계는 어디인가?
- 사용자에게 성공을 응답한 직후 서비스를 잃었을 때 무엇을 복원할 수 있는가?
- 무엇을 telemetry에 남길 수 있고 token·개인정보·signed URL은 어디에서 제거하는가?

Supabase·Sentry를 실제로 묶는 [보안·관측 앱 캡스톤](../../../capstones/secure-observable-app.md)은 **별도8주 과정**입니다. 여기서는 correlation ID와 privacy boundary의 연결 설계만 제출해도 됩니다. 완전한 Sentry SDK 수집/처리/보존 검증을 SU14의 완료 항목으로 과장하지 않습니다. 분석 파이프라인 확장은 선택적으로 [공통 DB 캡스톤](../../../databases/shared/capstone.md)과 연결합니다.

**최종 통과:** [평가표](../assessment.md)의 정확성25·원리/소스25·실험/반증25·운영/재현성25에서 총80 이상·각15 이상, 필수 gate 전부 통과. secret 노출, tenant 간 읽기/쓰기 누출, 없는 replay/복원 보장, 미실행을 실행으로 표현하면 재수행합니다. 결과물은 “이 workload와 실패 조건에서 증명한 능력”이며 모든 Supabase 운영 상황에 대한 자격 보증이 아닙니다.
