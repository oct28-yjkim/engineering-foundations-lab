# 3강 — 사용자 식별, 익명 로그인·로그아웃, 시간과 세션

[커리큘럼](../curriculum.md) · AM05–AM06 · [SDK 강의](02-sdk-delivery.md)

## 정상 기능: 합성 사용자의 원장을 먼저 만든다

웹 기본 앱의 A 로그인과 수동 정상 event를 검산한 뒤 확장합니다. 같은 시험 앱의 A/B·새 synthetic device ID를 사용하고 회사 계정·실제 로그인 token·실제 기기 광고 ID는 쓰지 않습니다. 서로 다른 run의 사용자 ID namespace를 분리하여 이전 merge 이력이 새 oracle을 오염시키지 않도록 합니다.

| 단계 | 앱에서 안다고 주장하는 것 | 실제 기록할 것 |
| --- | --- | --- |
| 익명 A-device | 아직 제품 로그인 없음 | device ID·user_id 부재·업무 marker |
| A 로그인 | 합성 제품 사용자 A | 안정적인 A user_id·해당 event의 device ID |
| A의 다른 장치 | 같은 제품 사용자, 다른 장치 | 같은 A user_id·다른 device ID·source |
| logout | 앱 인증 종료 | SDK user/device/reset 전후·queue 안의 이전 event |
| 익명 또는 B 로그인 | 의도한 새 주체 | 새 익명 경계 또는 B user_id·실제 User Lookup 귀속 |

Amplitude는 device ID·user ID·Amplitude ID를 조합해 분석 사용자를 식별합니다. device ID를 사람 수로 세거나 Amplitude ID를 제품 인증 권한으로 쓰지 않습니다. user_id만 비웠을 때 이전 알려진 사용자로 귀속될 수 있으므로 명시적 익명 분리가 필요하면 **선택 SDK의 logout/reset 계약**에 따라 device ID 경계도 확인합니다. [공식 identity 설명](https://amplitude.com/docs/data/sources/instrument-track-unique-users)

## 원리와 공개/비공개 경계

SDK source에서는 ID를 언제 읽고 queue event에 언제 붙이는지 추적할 수 있습니다. 서버가 최종 profile을 어떻게 합병했는지는 실제 test project 관측과 문서 계약으로 검산합니다. 서버 merge 알고리즘·저장 schema를 공개 SDK에서 추정하지 않습니다. logout/reset을 analytics 데이터 삭제나 법적 삭제 처리로 해석하지 않습니다.

웹·iOS Swift·Android Kotlin은 같은 함수 이름을 가진다고 수명/저장 효과가 완전히 같지 않습니다. 앱 version, SDK version, instance, storage, user/device 전후, 미전송 queue를 함께 기록합니다. 자동 광고 식별자를 켜거나 모든 device ID를 동일 상수로 바꿔 문제를 재현하지 않습니다. [Swift reset](https://amplitude.com/docs/sdks/analytics/ios/ios-swift-sdk) · [Kotlin identity](https://amplitude.com/docs/sdks/analytics/android/android-kotlin-sdk)

## 시간은 최소 세 종류다

1. **행동 시각/event time:** 실제 합성 행동이 언제 발생했는가? client clock·time 단위·명시 여부를 기록합니다.
2. **업로드 수락 시각:** 언제 서버가 요청을 받았는가? offline 기간과 queue 대기를 포함할 수 있습니다.
3. **분석 구간:** project/chart timezone·날짜 경계·세션 정의·retention window가 무엇인가?

Export API의 조회 범위는 server_upload_time 기준이며 chart와 같은 날짜 문자열을 넣어도 동일 event 집합이 아닐 수 있습니다. export row의 event time으로 다시 분석 구간을 맞춘 뒤 비교합니다. [공식 export/차트 차이](https://amplitude.com/docs/data/sources/export-api-differences)

session ID와 session chart 정의도 분리합니다. 프로젝트의 session 정의 변경은 여러 분석에 영향을 줄 수 있으므로 운영 프로젝트에서 바꾸지 않습니다. 웹 navigation과 모바일 background가 언제 세션 경계를 만드는지는 선택 SDK·project 설정을 함께 확인합니다. [Track sessions](https://amplitude.com/docs/data/sources/instrument-track-sessions)

## 문제 A — 로그인/로그아웃 뒤 unique가 이상하다

정상 A timeline→A logout→익명 행동→B login의 작은 합성 행렬을 미리 작성합니다. **새 run별 ID**로 잘못된 client 전이와 올바른 전이를 분리 비교합니다. 같은 identity 이력에 반복 실행해 원하는 count를 강제로 만들지 않습니다.

경쟁 가설: user_id 변경/공유, device 재생성/미재생성, 중복 SDK instance, 과거 합병 이력, query 기간/차트 unique 정의. 송신 payload의 ID와 User Lookup의 귀속을 함께 확인합니다. 회복은 새 올바른 run에서 예상 사용자별 marker와 금지 교차 귀속을 검산하는 것이며 과거 합병을 SDK reset으로 취소했다고 기록하지 않습니다.

## 문제 B — 오늘 보낸 event가 어제 차트에 있거나 세션이 다르다

client OS 시간을 바꾸지 않습니다. 별도 승인된 fixture에 명시적 event time을 써서 이미 끝난 UTC 날짜의 자정 전후 두 이벤트를 비교하고 실제 project timezone을 기록합니다. 모바일 offline/reconnect 자료에서는 발생·전송·가시성 시간을 분리합니다.

잘못된 단위, timezone, 늦은 수신, session_id 누락, chart 기간/필터를 경쟁 가설로 나눕니다. 원래 시간 계약의 새 run으로 복귀하고 **같은 사용자·event ID·업무 값·정확한 날짜 bucket**을 검산합니다. UI 시간대를 임의 변경해 수치만 맞추지 않습니다.

## 완료와 제한

기본은 웹 SDK의 정상 로그인/수동 event·identity 경계를 설명하는 것입니다. 모바일 앱이 없으면 [수동 준비](../labs/mobile-lab.md)와 기대 행렬만 제출하고 실측으로 표시하지 않습니다. identity merge·session duration·late event의 모든 규칙을 단 한 번의 테스트로 일반화하지 않습니다. “진짜 사람 수”나 cross-device 정확도가 자동 증명되는 것도 아닙니다.

제출물은 ID 별칭 지도, source별 SDK 지문, event/upload/관측 timeline, 두 경쟁 가설, 원복과 새 run oracle입니다. user_id를 email·전화번호 대신 비식별 합성 값으로 만들어도 실제 업무 데이터에서 자동 익명화되는 것은 아니므로 이번 실습에는 합성 데이터만 씁니다.
