# 1강 — 클릭보다 먼저 정의할 event 계약

[커리큘럼](../curriculum.md) · AM01–AM02 · [기본 LAB](../operations.md)

## 정상 기능: 한 행동을 한 번 설명하기

웹 최소 SDK 앱에서 합성 사용자 A로 로그인하고 View→Checkout→Purchase의 **수동 업무 event 3개**를 한 번씩 만듭니다. 실제 이름·property·source/run 표시는 [실습 안내](../labs/README.md)를 그대로 사용합니다. HTTP 비교 fixture와 아래 강의용 확장 예제를 같은 run의 정답으로 섞지 않습니다.

버튼 클릭, 결제 시도, 결제 성공은 다른 행동입니다. Purchase를 어디서 발생시킬지 합의하지 않으면 데이터 전송이 완벽해도 매출 분석은 틀릴 수 있습니다. 이 LAB는 실제 결제하지 않고 이미 정한 합성 성공 조건만 사용합니다.

| 계약 필드 | 작성할 내용 | 잘못된 계약의 예 |
| --- | --- | --- |
| 업무 정의 | event가 성립하는 상태·정확한 호출 지점·owner | 성공과 실패 모두 `Purchase`로 이름만 통일 |
| 식별 | 업무 event ID·insert_id·합성 user/device·run/source | event_type에 사용자 ID·날짜를 붙여 이름을 무한 생성 |
| 속성 | event 시점 값·타입·단위·허용 enum·누락 의미 | 금액을 숫자/문자열로 혼용, 누락을 0으로 대체 |
| 시간 | event time·UTC 기준·session contract·client clock | 초와 millisecond를 섞고 수신 시간을 발생 시각으로 보고 |
| 개인정보 | 수집 허용 목록·금지 값·목적·보존/접근 담당자 | full URL·email·자유 입력을 일단 수집 |
| 소비 | totals/unique/funnel 등 차트·분모·하위 의존자 | dashboard 제목만 같으면 같은 metric으로 취급 |

이름의 대소문자·공백·형식을 고정하고 새 계약은 이전 소비 차트의 호환성을 검토합니다. Amplitude Data의 tracking plan은 계측 계약을 관리하는 도구이지 SDK 배포와 같은 transaction이 아닙니다. branch/version과 실제 배포 source를 따로 기록합니다. [계획 흐름](https://amplitude.com/docs/data/data-planning-workflow) · [taxonomy와 시험 환경](https://amplitude.com/docs/data/amplitude-data-get-started)

## 원리: event property와 user property의 시간 경계

구매 순간 상품/가격은 event에 귀속되고 현재 구독 상태 같은 user property는 변경될 수 있습니다. “지금 사용자의 plan”을 “구매 당시 plan”으로 곧바로 대체하지 않습니다. Identify와 뒤따르는 event, 차트에서 선택한 property 의미를 실측 자료로 대조합니다. SDK별 Identify 전송/묶음 처리도 version에 따라 확인합니다. [공식 Swift SDK의 Identify 설명](https://amplitude.com/docs/sdks/analytics/ios/ios-swift-sdk)

v1→v2의 단순 이름 변경은 과거 event를 취소하거나 과거 query 정의를 일괄 수정하는 작업이 아닙니다. 변경 종류를 추가 optional field, required 강화, 타입 변경, 의미 변경, event 폐기로 나누고 publisher/consumer 조합의 기대 결과를 작성합니다.

## 관측: 계획과 실제 payload를 대조한다

1. SDK 호출 전 업무 원장의 ID·행동 수를 확인합니다.
2. 개발자 도구/시험 로그에서 source·run·event_type·타입·필수 속성만 정제해 봅니다. key·cookie·전체 request dump는 저장하지 않습니다.
3. test project의 해당 event/속성과 비교합니다. HTTP 수락, Observe 표시, chart 조건을 별도 칸으로 둡니다.
4. Observe/Schema 기능이 없다면 기능을 구매하거나 권한을 우회하지 않고 허가된 event stream·작은 수동 검산을 사용합니다.

## 제한된 문제 2개

**이름 drift:** 별도 강의용 새 run에서 한 업무 event의 대소문자/버전만 바꾼 synthetic 변형을 검토합니다. 기존 차트가 이전 이름만 선택하면 수가 줄 수 있습니다. transport 실패, 잘못된 프로젝트, event 이름 분리를 가설로 나누고 실제 event 목록·원장으로 배제합니다. 기본 runner가 이 변형을 제공하지 않으면 수동 fixture 준비 과제입니다.

**속성 type drift:** 허가된 새 fixture의 숫자 property 하나를 잘못된 타입으로 만듭니다. HTTP payload validation과 project schema 처리가 같은 규칙이라고 가정하지 않습니다. 프로젝트 설정에 따라 event 수락·property 거절·경고가 다를 수 있으므로 실제 policy와 응답을 기록합니다. 운영 tracking plan을 바꿔 재현하지 않습니다. [Schema 설정](https://amplitude.com/docs/data/configure-schema)

## 조치·회복·확장

계측 이름/타입을 원래 계약으로 복구한 **새 run**에서 업무 event ID·속성·차트 분모를 재검산합니다. 이미 수집된 잘못된 run은 식별해 보존하고 분석에서 명시적으로 구분합니다. 숨김·삭제·재전송으로 count만 맞추지 않습니다.

기본 gate는 정상 3개 수동 행동의 계약과 실제 결과를 설명하는 것입니다. 심화에서는 v1/v2·web/iOS/Android source별 schema 행렬과 소비 chart 영향도를 만듭니다. 강의의 변형 fixture는 자동 제공/실행 완료가 아니며 [운영 상한](../operations.md)을 지킵니다.

구술 질문: 같은 클릭이 autocapture와 수동 business event로 각각 기록되면 항상 중복인가? 같은 목적의 두 publisher라면 어떻게 owner를 정하고, 서로 다른 의미라면 차트 분모를 어떻게 분리할 것인가?
