# S05–S06 — 그룹화, 심볼리케이션, 릴리스와 회귀

이 강의는 화면의 issue를 실제 원인과 동일시하지 않습니다. 문제를 합치는 규칙과 배포 artifact를 검증한 후, 수정·회귀를 판단합니다. 실제 서버 검증에는 학습자가 준비한 별도 시험 프로젝트가 필요하며 이 저장소에서 외부 업로드를 자동 수행하지 않습니다.

## S05. stack trace를 원인 추정에 사용할 조건

### 선수 조건과 원리

S03, JavaScript 빌드·minification·source map의 기초가 필요합니다. 오류 grouping은 사건을 분석 가능한 묶음으로 줄이는 과정이지 인과 추론의 정답이 아닙니다. 기본 규칙은 stack frame·exception·message 등을 사용하며 프로젝트의 grouping 설정과 버전이 영향을 줍니다. SDK에서 fingerprint를 지정하면 기본 규칙의 결과를 바꿀 수 있습니다. 모든 오류를 고정 문자열로 묶으면 다른 원인의 false merge가 생기고, 사용자 ID나 timestamp를 fingerprint에 넣으면 동일 원인이 끝없이 분리됩니다. [공식 grouping 설명](https://docs.sentry.io/concepts/data-management/event-grouping/)

`event_id`는 개별 관측, fingerprint는 grouping 입력/식별 논리, issue ID는 제품의 그룹 객체입니다. 세 값이 같은 역할이 아닙니다. Grouping 설정 변경이 과거 모든 event를 새 규칙으로 다시 묶는다고 가정하지 않습니다. 현재 문서는 grouping 변경이 새 event에 적용됨을 설명합니다. SaaS의 추가 grouping 기능과 self-hosted에서 확인 가능한 동작도 별도 capability 표에 둡니다.

Minified stack을 원본 코드에 대응시키려면 실행된 bundle과 source map의 build identity가 일치해야 합니다. 현대 JavaScript 경로에서는 Debug ID가 bundle·event metadata·업로드 artifact를 연결하는 중요한 근거입니다. `release`, `dist`, URL/`abs_path`, artifact metadata는 선택 SDK/toolchain의 연결 규칙을 함께 확인합니다. 파일명이 같다는 사실만으로 같은 빌드를 뜻하지 않습니다. mapping이 틀리면 그럴듯하지만 잘못된 원본 줄을 가리킬 수 있습니다. [Source map 문제 해결](https://docs.sentry.io/platforms/javascript/sourcemaps/troubleshooting_js/)

### 실험 A: grouping 품질을 confusion table로 보기 — `OFFLINE` / `PROJECT-LAB`

6개의 합성 원인 계열을 만듭니다. 같은 함수에서 다른 업무 원인 2개, 다른 wrapper에서 같은 원인 2개, message의 동적 ID만 다른 계열, 공통 라이브러리 frame만 겹치는 계열을 포함합니다. 각 계열에서 5개씩, 총 30개 오류의 `ground_truth_cause`를 먼저 지정합니다. 이 값은 서버 issue에서 유도하지 않습니다.

1. OFFLINE에서는 default/fixed/dynamic fingerprint 정책의 예상 묶음을 모델로 만듭니다. 모델 결과를 실제 Sentry grouping 결과라고 부르지 않습니다.
2. PROJECT-LAB에서는 지정한 grouping 설정·SDK 버전·오류 입력으로 전송한 뒤 event-to-issue 관계를 수집합니다. 과거 데이터와 분리하기 위해 전용 합성 project/run tag를 사용합니다.
3. pairwise oracle을 사용합니다. 같은 ground-truth 원인인데 다른 issue면 split, 다른 원인인데 같은 issue면 merge 후보입니다. “모든 사건이 issue에 들어갔다”는 것만으로 정확하다고 평가하지 않습니다.
4. 임의 fingerprint 강제와 frame `in_app` 분류 변경을 한 가지씩 적용합니다. 다른 조건은 고정합니다. 정확한 grouping hash를 버전 불변의 예상값으로 쓰지 않습니다.

증거는 입력 cause map, grouping 설정 snapshot, event/issue 관계, false merge/split의 구체적 pair입니다. 정상/결함 정책에서 예상한 반례를 찾고, 운영 정책이 어떤 오류를 합치고 분리할지 설명하면 통과합니다. 무조건 그룹 수를 줄이는 것을 개선이라고 하지 않습니다.

### 실험 B: artifact identity 교환 — `OFFLINE` / `PROJECT-LAB`

작은 함수 두 개가 다른 줄에서 예외를 던지는 앱의 build A/B를 만듭니다. 의도적으로 같은 bundle 파일명을 사용하되 내용과 Debug ID는 다르게 둡니다. A event+A map, A event+B map, map 없음, 잘못된 path/metadata의 네 입력을 구성합니다. 소스 파일 안에는 canary 주석을 넣되 실제 비밀정보는 넣지 않습니다.

OFFLINE oracle은 고정 버전 source-map 도구 또는 bundler의 매핑 결과입니다. 생성된 위치가 예상 원본 함수·줄·열로 대응하는지 직접 확인합니다. PROJECT-LAB 확장에서는 승인된 합성 artifact만 먼저 업로드하고 같은 예외를 발생시켜 결과를 비교합니다. 현재 JS 문서에서 늦게 업로드한 map이 이미 수집된 사건에 자동 소급 적용되지 않는 경우를 설명하므로, “나중에 올리면 과거가 모두 고쳐진다”를 기대하지 않습니다.

정확한 build를 연결하는 정상 결과와 mismatch를 구별하고, 원시 minified frame·Debug ID·artifact manifest·원본 위치를 함께 제출해야 통과합니다. 업로드 성공 응답만 제출하면 미통과입니다. native debug information file의 Symbolicator 경로는 선택 심화 과제이며 JS source map과 동일한 파일 형식으로 취급하지 않습니다.

## S06. release는 문자열 이상의 배포 계약이다

### 선수 조건과 원리

S05, 배포 artifact identity와 environment를 설명할 수 있어야 합니다. release는 배포한 코드 버전을 묶는 식별자이며 여러 프로젝트에 연결될 수 있습니다. event의 release 값, 빌드 artifact, commit 집합, deploy 기록, 실제 실행 버전은 별도 증거입니다. release 객체가 존재한다고 해당 환경에 코드가 실제 배포되었음을 입증하지 않습니다. `dist`는 같은 release의 배포 변형을 구별할 수 있고, `environment`는 실행 환경을 나타냅니다. timestamp나 pod 이름을 release로 써서 매 실행마다 새 버전을 만들면 비교 단위가 무너집니다. [Releases](https://docs.sentry.io/product/releases/)

Regression 판단은 이전 해결 상태와 새 event의 grouping·release·프로젝트 동작에 의존합니다. issue가 reopened되었다는 사실은 새 코드가 원인이라는 완전한 증거가 아닙니다. 이전 버전 인스턴스가 남아 있거나 잘못된 release 값, delayed delivery, grouping 변경이 원인일 수 있습니다. commit association은 조사 방향을 제공하지만 인과 증명은 재현·통제 비교가 담당합니다.

Release Health의 session은 Replay session과 다른 개념입니다. session의 상태는 SDK·플랫폼에 따라 정의되며 unhandled exception, crashed session, process crash를 무조건 같은 숫자로 세지 않습니다. crash-free session은 오류가 없는 HTTP 요청의 비율이 아닙니다. 분모와 SDK 전송 정책을 확인해야 합니다. [Release Health](https://docs.sentry.io/product/releases/health/)

### 실험: vA/vB × staging/prod 행렬 — `OFFLINE` / `PROJECT-LAB`

입력은 두 release와 두 environment에 동일한 업무 시나리오를 적용한 4개 cohort입니다. cohort마다 요청 100개, 같은 cause ID의 실패 5개, session ID 20개를 준비합니다. vB에서는 알려진 오류 하나를 수정하고 별개의 오류 하나를 추가합니다. 요청→session 관계와 배포 시각, 뒤늦게 도착하는 vA 오류 1건을 원장에 명시합니다.

1. contract oracle은 실행 build가 manifest의 release/dist/environment와 일치하는지 검사합니다. “vB라고 적었지만 A bundle 실행” 결함을 한 cohort에 주입합니다.
2. 오류 발생 시각과 도착 시각을 따로 기록합니다. 배포 직후 들어온 오래된 vA 오류를 vB regression으로 잘못 판정하는 규칙을 반증합니다.
3. PROJECT-LAB에서는 시험 issue의 resolve/reappearance 동작을 프로젝트 설정과 함께 관찰합니다. UI 문구를 보편적 SDK 보장으로 서술하지 않습니다.
4. error event count, affected session 수, crashed session 수, 전체 session 수를 별도로 계산합니다. 입력에 process crash를 구현하지 않았다면 crashed-session 판정은 모델 결과이지 실제 crash 검증이 아닙니다.

산출물은 배포 행렬, artifact identity 비교, arrival/event time timeline, 분모가 있는 health 계산표입니다. 4개 cohort의 버전 연결이 맞고, 늦게 도착한 구버전 사건과 새 버전의 새 결함을 구별해야 통과합니다. 실제 SaaS 시험을 못 했으면 release 객체/resolve UI 동작은 실행 미검증으로 둡니다.

## 소스 방향과 구술 리뷰

[소스 지도](../source-reading.md)에서 grouping 입력 정규화→fingerprint 생성→issue 연결, artifact metadata→symbolication lookup, release ingestion의 경계를 추적합니다. 하나의 긴 호출 그래프를 외우기보다 각 경계의 입력·출력·실패 처리를 설명합니다.

구술 질문은 세 가지입니다. “서로 다른 root cause가 같은 stack을 쓰면 무엇을 기준으로 나눌까?”, “정확한 source map인데 잘못된 원본 줄이 나오는 조건은?”, “release의 crash-free가 개선됐는데 사용자 실패율이 나빠질 수 있는가?” 각각 fixture 또는 명시적 반례로 답해야 합니다.
