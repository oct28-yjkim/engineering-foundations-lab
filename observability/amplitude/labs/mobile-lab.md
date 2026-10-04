# 모바일 SDK LAB — 앱 수명과 이벤트 수명을 나누기

[기본 LAB](README.md) · [환경 계약](../environment.md) · [SDK 전달 강의](../lessons/02-sdk-delivery.md) · [Identity 강의](../lessons/03-identity-sessions.md)

회사에서 쓰는 플랫폼부터 선택합니다. **완성 iOS/Android 앱·빌드/서명 환경은 제공하지 않습니다.** 소유한 시험 앱에 아래 작은 계측 화면과 로컬 원장을 준비하여 실제 SDK/OS에서 실행하는 수동 LAB입니다. 웹 앱이나 HTTP runner 통과를 네이티브 SDK의 검증으로 대체하지 않습니다.

## 1. 시험 앱의 정상 계약

실제 결제·로그인·광고/푸시·연락처 접근이 없는 화면 하나를 사용합니다. 허가된 테스트 key/region을 debug configuration으로 전달하고 소스/Git/빌드 로그에 남기지 않습니다. iOS는 package resolved/SDK·OS·device·app build, Android는 dependency lock/SDK·API level·device·build variant를 기록합니다. React Native/Flutter를 사용하면 wrapper와 실제 native SDK revision도 분리합니다.

버전별 초기화·queue·flush·opt-out·reset과 자동 수집 기본값은 [iOS Swift 공식 문서](https://amplitude.com/docs/sdks/analytics/ios/ios-swift-sdk), [Android Kotlin 공식 문서](https://amplitude.com/docs/sdks/analytics/android/android-kotlin-sdk)의 해당 version과 대조합니다. SDK가 바뀌면 같은 함수명도 동일한 수명/반환 보장을 가정하지 않습니다.

시험 화면은 다음 동작을 준비합니다.

| 화면 동작 | 계측 계약과 로컬 증거 |
| --- | --- |
| 초기화 | 동의·test project·region 확인 후 SDK instance 하나만 생성; 자동 계측/remote config/Replay/광고 ID 경로는 기본 비교에서 끄거나 확인 불가면 미준비 |
| 합성 로그인 A | 실제 회원 계정 대신 `efl-mobile-<run>-user-a`; SDK user/device/session 값을 별도 기록 |
| View / Checkout / Purchase | 세 고정 event type, `lab_run_id`, `source=efl-ios-sdk` 또는 `efl-android-sdk`, synthetic product/order ID; 원본 버튼 intent마다 고유 ID |
| Flush | 요청 시각, 반환/콜백의 실제 의미, request status/서버 가시 시각을 분리; 비동기 호출을 저장 완료로 취급하지 않음 |
| 로그아웃/Reset | 선택 SDK의 문서상 reset 계약과 실제 user/device 변경을 대조; 이전 queue에 담긴 event의 ID도 확인 |
| 동의 상태 | CMP 상태와 SDK 유효 설정, 수집/로컬 저장/전송 각각의 허용 조건 표시; 실제 동의를 우회하지 않음 |

로컬 원장은 wall-clock UTC + monotonic 경과시간, app lifecycle, intent/event ID, 합성 user/device, queue/transport 관측 가능 여부를 기록합니다. key·token·전체 요청·실제 사용자 내용은 제외합니다. 기본 budget은 **한 run 20개 수동 행동, 최대 5분, 네트워크 차단 30초 이내**입니다. SDK 자체의 자동 이벤트·retry도 별도 관측하고, 예상 밖 수집이 있으면 발생기를 멈추고 설정을 조사합니다. 요청 종료를 보장하는 전역 타이머는 아닙니다.

## 2. 정상 기능을 먼저 확인

foreground·online·동의된 상태에서 로그인 A → View → Checkout → Purchase를 각각 1회 수행합니다. 앱 호출 3건과 SDK 전송 원장을 비교하고, 허가된 프로젝트에서 같은 run/source의 정확한 3건과 ID·속성·시각을 검산합니다. 차트의 unique user=1, This order/30분 funnel `1→1→1`을 확인합니다. 앱의 별도 lifecycle/session 자동 이벤트가 있으면 비즈니스 세 이벤트와 섞지 않고 설정과 수량을 기록합니다.

SDK 로그만 있고 서버 가시성이 없으면 정상 gate는 미완료입니다. TLS interception이나 조직 망 우회는 필수 관측 방법으로 요구하지 않습니다. SDK의 정제 callback/plugin 로그와 프로젝트 UI로 필요한 경계를 확인하고 수집할 수 없는 항목은 unknown으로 남깁니다.

## 3. 기본 사건 카드

| 사건 | 한 변인과 경쟁 가설 | 관측·복구 oracle |
| --- | --- | --- |
| Background 직전 이벤트 누락 | 정상 event 하나 직후 홈 전환; 동일 사건을 foreground 유지와 비교. queue 미flush / OS suspend / 차트 시간/필터 가설 | lifecycle·flush/callback·원래 insert/event ID·서버 가시 시각. foreground 복귀 후 동일 원장이 전달됐는지 확인; 새로운 ID로 같은 행동을 무조건 재생성하지 않음 |
| Offline → reconnect | 정상 초기화 뒤 시험 기기만 30초 이내 offline, 고정 event 최대 2건, 복귀 | enqueue/저장 관측 가능 범위·retry·ID 보존·전송 시각·중복/누락 대조. 복귀 후 새 정상 event도 검산; 인터넷 단절과 HTTP429를 같은 오류로 보지 않음 |
| 화면 재생성 후 중복 | 시험 화면을 나갔다 들어오거나 Android 회전을 한 번 수행하고 View 한 번 | lifecycle의 handler 재등록/다중 SDK instance/자동+수동 계측을 구분. 하나의 intent에 두 callback이면 경로 수정, 새 run에서 1intent=1event. 과거 중복은 자동 삭제하지 않음 |
| Logout 뒤 다른 사람에게 귀속 | 합성 A 정상 event 후 시험 SDK의 user만 비운 경우와 문서상 reset을 별도 run에서 비교 | 현재 client ID, queued event ID, 서버 profile·기대 합성 사용자 집합. 정상 reset을 적용한 새 event 확인; reset으로 과거 merge가 해제됐다고 주장하지 않음 |
| 동의 해제 뒤 예상 밖 송신 | **기존 queue가 없는 정상 기준선부터** 시작, 허가된 시험 CMP/opt-out 변경 후 합성 행동 1개 | 수집/저장/신규 전송·remote config·autocapture를 각각 확인. 기존 queue/in-flight가 남을 가능성은 따로 조사; 재동의 후 새 정상 행동만 확인하고 비동의 기간을 backfill하지 않음 |

처음에는 강제 process kill·삭제/재설치·전체 기기 데이터 초기화를 하지 않습니다. 영속 queue의 kill/relaunch 내구성은 별도 폐기용 앱 데이터·복구 원장·보존 선택을 정한 후 확장합니다. iOS background task·Android process death/배터리 정책, simulator와 실기기 차이는 한 번의 실험으로 일반화하지 않습니다.

## 4. 웹과 모바일의 숫자를 맞출 때

동일한 업무 user ID를 사용한다는 계약, 플랫폼별 device ID, source 분리, 동일 event/property version, 시간·session 정의, 동의 포함 분모를 먼저 비교합니다. 정상 세 이벤트를 두 장치에서 수행했다면 total과 unique가 어떻게 달라져야 하는지 **예상 사용자 집합**을 먼저 적습니다. 실사용 이메일/전화번호를 analytics ID로 보내거나 계정을 강제로 merge해서 수치를 맞추지 않습니다.

## 5. 완료·종료

플랫폼 하나의 정상 gate, 서로 다른 사건 두 개, 원인을 가르는 자료, 제한된 코드/설정 변경과 원복, 회복 후 정확한 ID/값을 [보고서](../../../operations/incident-report-template.md)에 제출합니다. 미준비 플랫폼은 별도 미검증으로 표시합니다. 테스트 발생기와 debug build를 종료하고 미해결 queue·서버 보존을 기록합니다. `flush`/opt-out/reset/앱 종료/서버 삭제는 서로 다른 조치입니다.
