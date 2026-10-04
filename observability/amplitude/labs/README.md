# Amplitude 기본 LAB — SDK 이벤트를 숫자와 연결하기

[트랙](../README.md) · [환경](../environment.md) · [운영 runbook](../operations.md) · [모바일](mobile-lab.md) · [검증 기록](validation.md)

회사 사용방식에 맞춰 **웹·모바일 SDK가 기본**, HTTP는 진단 보조입니다. Amplitude SaaS를 Python 모형이나 로컬 서버로 대체하지 않습니다. 무송신 준비 단계도 학습이지만 실제 제품 검증과는 구분합니다.

## 1. 정상 기능: 합성 사용자 한 명의 구매 흐름

[환경 계약](../environment.md)을 확인하고 제공 [웹 앱](browser/index.html)을 loopback 서버로 엽니다. 시작 전 Network에서 외부 SDK/수집 요청이 없는지 확인합니다. 허가된 test 별칭과 key·region·동의를 명시하고 시작 버튼을 한 번 누릅니다. CDN 다운로드와 SDK 초기화가 발생하지만 아직 사용자가 누른 비즈니스 이벤트는 없습니다.

1. `합성 사용자 A 로그인`을 누르고 local 원장의 user/device/session/run ID를 기록합니다. 실제 로그인을 수행하는 앱이 아니라 SDK의 합성 identity를 설정하는 버튼입니다.
2. `Product Viewed` → `Checkout Started` → `Purchase Completed`를 한 번씩 누릅니다. 같은 순서로 UI와 시각을 기록하고 30분 안에 마칩니다.
3. `flush 요청`을 누르고 local `track_called` 3개와 `sdk_callback`·Network status/전송 시각을 비교합니다. callback/flush만으로 저장·차트 성공을 선언하지 않습니다.
4. 허가된 테스트 프로젝트에서 해당 합성 사용자의 **User Activity/Event Stream**, 사용할 수 있다면 **Event Explorer**를 읽습니다. 정확한 event type/시간/user/device와 `lab_run_id`, `source=efl-browser-sdk`, 합성 order/product 필드를 대조합니다.
5. Event Segmentation에서 각 이벤트 total=1, 각 이벤트 unique user=1을 확인합니다. 같은 run/source를 **각 이벤트 조건에** 적용합니다.
6. Funnel에서 세 이벤트, **This order·Unique Users·전환 창 30분**, 동일 시간 범위/UTC를 고정합니다. 이 단일 정상 경로의 기대값은 `1→1→1`, 100%입니다. 반복/추가 사건 이벤트와 섞지 않습니다.

프로젝트 timezone은 전역 변경하지 않고 현재 설정을 기록합니다. chart에서 UTC를 선택할 수 없다면 이벤트가 속한 실제 날짜 범위를 계산해 비교합니다. 시간 경계·filter·관측 지연이 불명확하면 틀린 숫자를 SDK 유실로 단정하지 않습니다. [Event Explorer](https://amplitude.com/docs/analytics/charts/event-explorer), [퍼널 순서](https://amplitude.com/docs/analytics/charts/funnel-analysis/funnel-analysis-how-amplitude-computes)

## 2. 동작 원리와 관측 위치

원본 버튼 행동은 앱 원장, `track` 호출은 SDK 입력, batch/flush는 전송 경계, HTTP 수락은 ingestion 응답, 사용자 프로필/차트는 별도의 조회 결과입니다. 한 단계의 성공을 다음 단계의 보장으로 확대하지 않습니다.

| 확인할 질문 | 직접 볼 곳 | 반드시 기록할 제약 |
| --- | --- | --- |
| 클릭 한 번을 몇 번 계측했나? | UI 행동 원장 vs `track_called`·`lab_intent_id` | SDK 로그는 원본 업무 분모 자체가 아님 |
| 어느 identity로 보냈나? | 앱 `현재 identity`와 event의 user/device/session | SDK 현재 상태와 서버의 historical merge 결과는 다를 수 있음 |
| queue가 전송됐나? | DevTools Network의 시간/요청·callback, flush 원장 | queue 길이를 직접 계측하지 않았으면 0으로 가정하지 않음 |
| ingestion 오류인가? | HTTP status + 테스트 프로젝트 Ingestion Debugger | 실제 project/endpoint/관측 창 확인; SDK의 raw message/HAR 공유 금지 |
| 보이지만 숫자가 다른가? | User Activity의 event와 chart 정의 | totals/unique·기간·timezone·filter·순서·전환 창을 고정 |

메모리 queue, retry/flush 호출, ID 변경의 구현은 [고정 SDK 소스](../source-reading.md)에서 조사합니다. 공식 설명과 관측이 다르면 SDK version·설정·재현 절차를 남겨 반증합니다. [SDK 진단](https://amplitude.com/docs/sdks/sdk-debugging)

## 3. 정상 이후에 고를 사건

각 사건은 가능하면 **새 페이지/run ID**로 시작하여 정상 3개를 먼저 관측합니다. 종료 후 새 run은 새 합성 ID를 쓰며 과거 이벤트는 남습니다. 다음은 자동 합격 버튼이 아니라 사용자가 가설·증거·정답을 비교하는 실습입니다.

| 사건 | 재현·관측 | 조치와 회복 검산 |
| --- | --- | --- |
| 중복 계측 | `한 번의 View를 두 번 계측`: 같은 intent에 다른 insert_id 두 개, total +2/unique 변화 비교 | 정상 View 버튼으로 하나의 intent당 track 1회 확인; 실제 앱에서는 중복 handler/수동+autocapture 경로를 고침. 기존 중복 데이터는 자동 정정되지 않음 |
| 전송 중복 vs 업무 중복 | 마지막 정상 이벤트의 identity 유지 상태에서 `같은 insert_id로 재전송` 1회 | Network의 추가 시도와 UI의 unique event를 비교; dedup 결과는 직접 관측. 새 insert_id로 계속 재전송하지 않음 |
| 로그아웃 뒤 잘못된 귀속 | 로그인 A·정상 이벤트 후 `user ID만 비우기`, View 1회; client device가 그대로인지와 서버 귀속 비교 | `reset + 새 세션` 후 View 1회. 새 device/익명 상태·허가된 서버 관측으로 차이를 설명. reset이 이미 합쳐진 과거 데이터를 분리한다는 뜻 아님 |
| SDK 호출은 있는데 전송이 없음 | pending 없는 정상 상태에서 opt-out 켜기 → View 1회, local 호출과 Network/프로필 비교 | 허가된 시험 동의 조건으로 opt-out 끄기 → **새** View. opt-out 중 누락은 자동 backfill하지 않음 |
| offline·재연결 | 초기화와 정상 확인 이후 DevTools로 해당 테스트 탭을 offline → View 최대 2회 → online | 원래 identity·insert_id·callback과 서버 가시성 대조, 필요 시 flush. queue가 메모리뿐이라 reload/종료 내구성은 없음 |
| 차트만 비어 있음 | 정상 수집이 보인 뒤 자신의 임시 chart에 잘못된 run filter/기간을 적용 | SDK를 건드리지 않고 임시 chart 조건만 원복하여 정확한 ID/값과 1→1→1 회복 |

dedup는 유한 조건의 ingestion 동작이며 모든 업무 중복이나 영구 exactly-once를 제거하지 않습니다. 사용자 merge도 client 변수 하나로 완전 재현하지 않습니다. [HTTP V2 dedup 계약](https://amplitude.com/docs/apis/analytics/http-v2), [사용자 식별](https://amplitude.com/docs/data/sources/instrument-track-unique-users)

## 4. 중요한 제한

- **SDK 실제 코드**를 사용하지만 회사 앱의 SPA/router/CMP·native lifecycle·disk queue까지 제공한 앱은 아닙니다. 모바일은 [별도 절차](mobile-lab.md)로 검증합니다.
- 한 페이지 20회 track·5분 이후 신규 작업을 중지합니다. auto retry=0은 재시도 폭주를 피하는 학습 설정이지 운영 권장치가 아닙니다. 중지/opt-out 뒤에도 이미 queue에 있던 이벤트가 전송될 수 있습니다. 요청 전역 hard deadline·queue 폐기·전송 중인 요청 취소를 보장하지 않습니다.
- 기본 앱은 서버 차트/identity/dedup를 조회하는 API를 호출하지 않습니다. HTTP 수락이나 SDK callback을 `VERIFIED`라고 표시하지 않습니다.
- 초기화/수집 실패 뒤 버튼을 반복 누르지 않습니다. key/region·CSP·망·권한·입력과 원본 원장을 먼저 조사합니다. ad blocker·조직 보안 정책·동의를 우회하지 않습니다.
- 감시 exporter나 SaaS 내부 CPU/queue 접근은 제공하지 않습니다. 실제 관측 가능한 수집·데이터 품질·사용자 결과와 지표 분모가 중심입니다.

## 5. 다른 분석의 독립 정답

4명/10건의 totals·unique 차이와 `4→3→2=50%` 퍼널은 [HTTP 보조 fixture](http-lab.md)로 확인합니다. 웹의 1명/3건과 source/run을 섞지 않습니다. retention/cohort는 [분석 의미 강의](../lessons/04-analysis-semantics.md)의 별도 입력/관측 기간을 사용합니다. 오늘 보낸 3건으로 D1 retention 완료를 주장하지 않습니다.

기본 완료에는 정상 결과·원리·직접 관측·제약과 서로 다른 사건 두 개의 진단/복구 보고서가 필요합니다. [공통 기록 양식](../../../operations/incident-report-template.md)을 재사용하고 실제 실행 여부는 [검증 기록](validation.md)과 별도 실측 원장에 남깁니다.
