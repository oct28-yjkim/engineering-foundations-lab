# 4강 — totals, unique, funnel, retention, cohort를 집합으로 검산하기

[커리큘럼](../curriculum.md) · AM07–AM08 · [identity·시간](03-identity-sessions.md)

## 정상 기능과 독립 oracle

먼저 웹 기본 LAB의 **동일 source/run**에서 정상 수동 event 3개와 사용자 A를 검산합니다. 다음 표는 분석 의미를 배우기 위한 **별도 확장 fixture 명세**입니다. 기본 웹/HTTP runner가 아래 표를 자동 전송한다는 뜻이 아닙니다. 허가된 test project에 수동 준비하거나 자료 분석으로 진행합니다.

사용자 A/B/C/D는 서로 다른 안정적 synthetic user_id와 각각 독립 device ID를 가집니다. 표의 e1–e8은 서로 다른 업무 이벤트이며 독립 insert_id를 사용합니다. UTC의 이미 완료한 같은 날짜, 같은 10분 창 안의 정수 minute, 다른 사건·필터 없음으로 고정합니다. 실제 event 이름은 새 강의용 namespace로 분리합니다.

| event | 사용자 | minute | 행동 |
| --- | --- | --- | --- |
| e1 | A | 0 | View |
| e2 | A | 1 | Checkout |
| e3 | A | 2 | Purchase |
| e4 | A | 3 | Purchase |
| e5 | B | 0 | View |
| e6 | B | 2 | Checkout |
| e7 | C | 1 | Purchase |
| e8 | D | 0 | View |

**Event Totals:** View=3, Checkout=2, Purchase=3. **Uniques:** View={A,B,D}=3, Checkout={A,B}=2, Purchase={A,C}=2. 모든 행동의 사용자 합집합은 4명이지 `3+2+2=7명`이 아닙니다. 같은 사용자가 여러 날짜 bucket에 나타나면 일별 unique 합과 전체 기간 unique도 다릅니다. [Event Segmentation FAQ](https://amplitude.com/docs/analytics/charts/event-segmentation/faq)

## Funnel의 정상 기대값

View→Checkout→Purchase, **This order**, 10분 conversion window, 사용자 기준 unique conversion, hold properties constant 없음, source/run 필터와 기간 일치 조건에서 단계별 사용자 집합은 `{A,B,D}`→`{A,B}`→`{A}`입니다. 전체 전환은 **1/3**, Checkout→Purchase 조건부 전환은 **1/2**입니다. C는 Purchase를 했지만 첫 단계가 없으므로 이 funnel 전환자가 아닙니다. A의 Purchase 두 번도 이 사용자 기준 funnel의 전환자 두 명이 아닙니다.

기본 순서와 Exact order, Any order는 다른 계약입니다. Exact order에 영향을 주는 중간 event·제외 event·같은 timestamp·conversion window·반복 진입을 추가할 때는 공식 정의와 oracle을 다시 씁니다. [Funnel 계산](https://amplitude.com/docs/analytics/charts/funnel-analysis/funnel-analysis-how-amplitude-computes)

hold properties constant를 켜면 사용자만이 아닌 사용자/속성 조합이 계산 단위가 될 수 있습니다. item/session을 고정한 funnel 결과를 원래 사용자 unique와 직접 비교하지 않습니다. 하나의 속성이 모든 필요한 단계에 실제로 있는지도 확인합니다. [Hold properties constant](https://amplitude.com/docs/analytics/charts/funnel-analysis/funnel-analysis-hold-properties-constant)

## Retention의 정상 기대값

별도의 작은 명세: A/B/C가 모두 Day 0에 Start, A만 Day 1에 Return, B만 Day 2에 Return, C는 Return 없음입니다. project timezone을 고정한 **strict calendar days**, 같은 entry date, 다른 Start 없음, Day 3까지 관측이 끝난 성숙 cohort로 한정합니다.

| 질문 | 분자 / 분모 | 기대값 |
| --- | --- | --- |
| Day 1 Return On | {A} / {A,B,C} | 1/3 |
| Day 2 Return On | {B} / {A,B,C} | 1/3 |
| Day 1 Return On or After, 위 관측 범위 | {A,B} / {A,B,C} | 2/3 |

관측 완료일·시각을 함께 기록합니다. 아직 Day 2를 지나지 않은 신규 사용자는 동일한 Day 2 기회가 없으며 단순 실패자로 넣지 않습니다. 24시간 window와 달력 날짜는 경계가 다르므로 같은 `Day 1` 글자만 보고 같다고 가정하지 않습니다. [Retention FAQ](https://amplitude.com/docs/analytics/charts/retention-analysis/faq) · [Retention 시간](https://amplitude.com/docs/analytics/charts/retention-analysis/retention-analysis-time)

cohort는 정의·시간 범위·evaluation 시각·property 시점을 포함한 사용자 집합입니다. 현재 membership을 과거 기간에도 불변인 label로 덧붙이지 않습니다. 구매 event 횟수 조건과 user property 조건의 평가 지점을 명시합니다. [Behavioral cohort 정의](https://amplitude.com/docs/analytics/define-cohort)

## 모니터링과 자주 만나는 문제

**문제 A: 두 대시보드의 수가 다르다.** source/run·event 이름·시간 범위·timezone·totals/unique·group-by·cohort·exclude 조건을 표로 나란히 비교합니다. SDK 중복과 정의 차이를 분리하려면 위 원장의 event ID 집합과 사용자 집합을 각각 대조합니다. 차트를 복사해 학습용 설정만 수정하고 회사 공유 차트는 바꾸지 않습니다.

**문제 B: funnel/retention이 갑자기 좋아지거나 나빠진다.** 실제 행동 변화, identity 변화, 출발 분모 감소, conversion/retention window 변경, late event, 미성숙 cohort를 가설로 봅니다. 동일 계약의 정상/증상 run에서 numerator/denominator의 **멤버 ID**를 검산합니다. ratio만 같아도 집합이 틀릴 수 있습니다.

조치는 잘못된 학습 차트 정의를 원래대로 복원하거나 계측 계약을 고친 새 run을 검증하는 것입니다. 회복 oracle은 정확한 ID/값·사용자 집합·시간 bucket·분자/분모입니다. 입력을 삭제하거나 분모를 바꾸어 목표 비율에 맞추지 않습니다.

## 제한과 심화

tiny fixture의 정확한 검산은 실제 제품 성장·인과효과·대규모 query 성능을 증명하지 않습니다. 통계 유의성, Experiment, predictive cohort, group/account analytics는 별도 기능·설계 과제이며 기본 필수 항목이 아닙니다. 실제 chart가 해당 설정을 지원하지 않으면 문서/권한을 확인하고 분석 설계만 제출합니다.

심화 과제는 이벤트 도착 순서·중간 event·속성 변경·late event를 각각 한 개 추가하여 “어떤 oracle이 바뀌어야 정상인가”를 먼저 적는 것입니다. 자료구조를 Python으로 흉내 내는 대신 실제 분석 정의와 작은 집합의 대응을 검증합니다.
