# 2강 — 웹·모바일 SDK의 queue, flush, lifecycle, 재전송

[커리큘럼](../curriculum.md) · AM03–AM04 · [웹 실습](../labs/README.md) · [모바일 수동 LAB](../labs/mobile-lab.md)

## 정상 기능과 책임 경계

기본 입구는 실제 **Browser SDK 2**의 정상 View→Checkout→Purchase입니다. 호출·queue·transport·수락·chart 가시성 시각을 구분합니다. 직접 HTTP runner는 SDK와 동일 payload가 비교 가능한지 확인하는 보조이며 웹 lifecycle·storage·consent를 검증하지 않습니다.

Mobile은 선택한 회사 플랫폼부터 수행합니다. iOS Swift 또는 Android Kotlin의 **별도 합성 시험 앱**에서 정상 foreground track→flush→User Lookup/차트 가시성을 확인합니다. Xcode/Android Studio·simulator/device·앱 준비가 필요하고 이 저장소가 native 앱이나 회사 앱 변경을 제공하지 않습니다. [Swift SDK](https://amplitude.com/docs/sdks/analytics/ios/ios-swift-sdk) · [Android Kotlin SDK](https://amplitude.com/docs/sdks/analytics/android/android-kotlin-sdk)

## 원리: queue와 OS 수명은 같은 것이 아니다

SDK는 event를 묶고 일정 조건에서 전송할 수 있습니다. `track` 호출 반환·flush 요청·transport 응답·최종 분석은 서로 다른 완료점입니다. 영속 queue 지원, 크기/보존 정책, callback 의미, background 처리, 자동 retry의 유한성은 **각 SDK의 고정 버전**에서 확인합니다. 웹 설정을 Android/iOS 기본값으로 복사하지 않습니다.

| 경계 | 웹에서 관측 | 모바일에서 관측 |
| --- | --- | --- |
| init·instance | 중복 script/tag/SPA mount·instance·유효 config | 앱 lifecycle 초기화·singleton/instanceName·native bridge |
| 화면 변화 | navigation·SPA route·visibility/page lifecycle | screen 변화·foreground/background·OS suspend |
| queue·storage | cookie identity와 unsent event storage를 분리 | app-private SDK storage·process 살아 있음/종료를 구분 |
| network | offline/reconnect·차단된 요청·proxy·CSP | 연결 인식 권한/설정·offline plugin·reconnect·전송 오류 |
| flush | 호출 시각·완료 관측점·남은 원장 | 비동기 업로드·background 기회·OS 실행 제한 |

background로 갔다가 돌아온 결과를 OS 강제 종료·배터리 절약·앱 데이터 삭제의 내구성 보장으로 확대하지 않습니다. 설치 제거·storage clear·기기 reset은 기본 재현 방법이 아닙니다. SDK 문서의 “재전송”도 앱이 영원히 실행된다는 뜻은 아닙니다.

## 관측 계약

합성 event마다 business ID, insert_id, SDK package, app/source revision, 생성/track/attempt/응답/가시성 시각, 결과(accepted/rejected/unknown)를 기록합니다. 개인정보가 아닌 event 수·queue 상태·비민감 오류 종류만 남깁니다. SDK가 queue depth를 공개하지 않으면 계측 불가로 표시하고 원장의 차이를 queue 내부 숫자로 위장하지 않습니다.

한 업무 event를 재시도할 때 ID가 바뀌는지 확인합니다. HTTP API의 dedup은 documented 식별 조합·기간 조건을 가지며 영구 exactly-once가 아닙니다. server-side 계산이나 주문 원장의 멱등성을 대체하지 않습니다. [HTTP V2 계약](https://amplitude.com/docs/apis/analytics/http-v2)

## 문제 A — 이동/백그라운드 후 마지막 이벤트가 안 보인다

시험 앱에서 정상 기준선 후 **짧은 offline 또는 navigation/background 한 가지**만 선택합니다. 허가된 합성 행동만 제한 수집하고 바로 정상 foreground/network로 복귀합니다. queue 준비·동의·보존 정책을 모르거나 payload가 실제 사용자 값이면 진행하지 않습니다.

경쟁 가설은 호출 자체 없음, init/instance 오류, queue flush 미완료, storage 불가, transport 실패, 조회 시간/필터입니다. 웹 network/SDK 상태와 모바일 sanitized SDK 로그를 해당 run 원장에 연결합니다. 같은 source/revision에서 정상 foreground 비교군을 둡니다. retry 횟수가 무한인 SDK 구성이면 학습 앱 자체의 시간·event 예산과 중지 절차를 먼저 둡니다.

회복은 정상 연결·원래 lifecycle에서 **동일 업무 event 집합의 ID/속성**을 검산하는 것입니다. 알 수 없는 요청을 전부 새 ID로 보내지 않고 unknown을 남깁니다. 정상 복귀 후에도 미확인이라면 다음 반복 전에 중지합니다.

## 문제 B — autocapture와 수동 계측 때문에 event가 늘어난다

기본 LAB는 자동 수집을 꺼 둡니다. 추가 과제는 별도 시험 앱에서 같은 합성 행동에 대해 manual only와 허가된 autocapture 옵션 **한 종류만** 비교합니다. remote config·plugin·tag manager와 앱 설정 중 실제 유효 설정을 기록하고 source/수동 event 의미를 대조합니다. [Autocapture 설명](https://amplitude.com/docs/get-started/autocapture) · [Web schema](https://amplitude.com/docs/data/web-autocapture-schema)

모든 자동 event가 업무 event의 중복인 것은 아닙니다. 같은 의미의 event가 두 publisher에서 나왔다면 한 계측 owner를 정하고 시험 설정을 원복합니다. 정상 행동 횟수·목적별 event 수·새 run의 차트가 회복되어야 합니다. 기존 데이터 삭제로 “고치지” 않습니다. Replay·network body 수집은 기본 확장에 포함하지 않습니다.

## HTTP 오류를 SDK 운영에 연결하기

| 관측 | 첫 판단 | 안전한 학습 방법 |
| --- | --- | --- |
| validation 400 | 입력/ID/time/필수 필드와 상세 분류 | 로컬 오류 fixture 또는 승인된 작은 음성 입력; 같은 오류 무한 retry 금지 |
| 413 | 직렬화 byte·batch 계약·endpoint 확인 | 실제 한도 소진 대신 local transport 응답으로 분할 정책 검사 |
| 429 | endpoint·project/ID 범위·응답 retry 정보 확인 | 의도적으로 quota를 넘기지 않고 기존 정제 응답/로컬 응답으로 backoff 검토 |
| timeout·5xx | 수락 여부 unknown 가능 | attempt/event 원장과 stable ID를 보존하고 승인된 bounded 재시도 결정 |

SDK가 실제로 수행하는 자동 분할·backoff·drop는 [공개 소스 지도](../source-reading.md)에서 선택 버전으로 확인합니다. mock PASS는 SaaS 제한을 재현했다는 뜻이 아닙니다.

마지막으로 consent는 opt-out 한 플래그와 같지 않습니다. 기본 앱은 동의 전 SDK를 초기화하거나 event를 모으지 않습니다. storage·plugin·network가 모두 계약을 지키는지 별도로 확인합니다. [Browser consent](https://amplitude.com/docs/sdks/analytics/browser/cookies-and-consent-management)
