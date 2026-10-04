# Amplitude 커리큘럼 — 기본 LAB에서 제품 분석 운영 심화까지

[시작](README.md) · [기본 운영 LAB](operations.md) · [실습](labs/README.md) · [평가](assessment.md) · [소스 지도](source-reading.md)

Amplitude는 **제품·행동 분석 SaaS**로 다룹니다. 목표는 event를 보내고 차트를 만드는 데서 출발하여, 그 수치를 믿을 조건과 어긋난 원인을 설명하고 안전하게 복구하는 것입니다. 비공개 ingestion·identity·query 서버의 자료구조나 배포 구성을 공개 SDK 구현에서 추정하지 않습니다.

## 기본 LAB와 심화의 관계

기본 경로는 **정상 기능 → 동작 원리 → 모니터링 → 제약 → 빈번한 문제 재현·진단·복구**입니다. 회사의 웹·모바일 SDK 사용에 맞춰 [웹 최소 SDK 앱](labs/README.md)의 합성 정상 행동과 [모바일 수동 LAB](labs/mobile-lab.md), [운영 카드](operations.md)를 연결합니다. 직접 HTTP fixture는 진단 비교 보조입니다. 아래 **14모듈·28주·주 12시간·명목 336시간**을 먼저 마칠 필요는 없습니다. CPU 알고리즘 모형을 새 입문 과정으로 만들지 않습니다.

한 모듈 2주·24시간은 기능/계약 확인 4시간, 문서·공개 SDK 탐색 4시간, 정상·음성·장애 실습 12시간, evidence/구술 리뷰 4시간의 출발점입니다. 속도보다 정확성·원장·원복이 우선이고 모든 제품 기능을 구매하거나 모든 모듈을 이수할 필요는 없습니다.

자료 확인일은 **2026-10-04**입니다. SaaS build를 알 수 없으면 unknown으로 적습니다. 실제 SDK package/lockfile·source SHA·project/region·chart timezone·계측/consent·tracking plan/차트 revision·권한과 plan별 기능 가용성을 manifest에 따로 기록합니다. 문서의 최신 기본값·상한·가격을 모든 회사 프로젝트에 적용하지 않습니다.

## 14모듈 지도

| 모듈 / 주차 | 정상 기능과 원리 | 관측·자주 만나는 문제 | 실험·통과 증거 |
| --- | --- | --- | --- |
| AM01 / 1–2 | 업무 행동→event taxonomy·event/user property·owner | 이름 대소문자/버전 분리·자동/수동 계측 중복 | 작은 행동 원장→payload→차트 계약; 이름/타입/분모를 먼저 정의하고 정상 결과 검산 |
| AM02 / 3–4 | schema·tracking plan 변경·source/branch/version | required 누락·타입 drift·소스별 배포 차이 | v1/v2 호환 행렬·소비 차트 영향·롤백 계획; 경고와 실제 rejection 구분 |
| AM03 / 5–6 | Browser SDK 2·iOS Swift·Android Kotlin의 init/instance·queue·storage·flush·consent | navigation/background 후 미전송·중복 등록·opt-out 오해 | 회사 플랫폼부터 소유 시험 앱의 호출→저장→전송 원장; SDK별 동의 전 수집/저장/송신 검사 |
| AM04 / 7–8 | offline/reconnect·SDK retry·HTTP 수락/오류·insert_id | 400·413·429·timeout unknown·OS lifecycle 제약 | SDK별 재시도/보존·background/정상 복귀 행렬; HTTP/local mock을 SDK/SaaS 검증과 분리 |
| AM05 / 9–10 | user/device/Amplitude ID·익명→로그인→logout·SDK별 reset | DAU/unique 과대·과소·공유 장치의 잘못된 귀속 | 웹/모바일 합성 두 사용자·두 장치 행렬; queue 전후 ID와 실제 profile·기대 집합 비교 |
| AM06 / 11–12 | event/upload time·timezone·session 정의·late event | 자정 경계·잘못된 time 단위·session 누락·늦은 이벤트 | UTC 원장과 프로젝트 시간 경계 대조; 차트와 export의 시간 기준 차이 설명 |
| AM07 / 13–14 | Event Totals/Uniques·segmentation·funnel 순서/창 | 총수와 unique 혼용·전환 분모/hold-constant 변경 | [강의 4](lessons/04-analysis-semantics.md)의 작은 사용자 집합을 손으로 검산하고 동일 차트 설정 비교 |
| AM08 / 15–16 | retention Return On/On or After·성숙 cohort·membership | 관찰 기간 미완료·평균의 평균·동적 cohort 오해 | 완결된 시간 창의 분자/분모 집합·cohort 정의와 계산 시점·미성숙 표본 표시 |
| AM09 / 17–18 | 수집 health·품질·freshness·Observe | upstream drop·schema drift·프로젝트/필터 불일치 | offered/attempted/accepted/visible/unknown 원장; 정상+증상 구간의 두 경쟁 가설 배제 |
| AM10 / 19–20 | governance·consent·PII 최소화·권한·downstream | 웹/mobile autocapture+manual 중복·remote config·예상 외 수집 | SDK별 가짜 canary 음성 검사·유효 설정·수신 목적지·숨김/차단/삭제와 승인 경계 |
| AM11 / 21–22 | Batch backfill·ID/time mapping·reconciliation | 중복 replay·현재 user property 오염·new-user 시점 이동 | 작은 별도 fixture의 partition ledger·checkpoint·누락/중복 분리; 원복 불가능한 import 경계 명시 |
| AM12 / 23–24 | SaaS 한도·sender capacity·rollout·변경 통제 | 한 ID 편중·retry 폭주·원래 차트 정의 변경 | endpoint/plan/범위별 상한 확인표·bounded retry·동일 분석 계약 canary·원복 검산 |
| AM13 / 25–26 | 공개 SDK 호출 경로·문서 계약·source/test 연구 | moving main·버전 혼합·SDK mock을 서버 보장으로 확대 | 실제 package와 대응 SHA, 구현/테스트 permalink, 한 반례 및 공개되지 않은 경계 |
| AM14 / 27–28 | 작은 end-to-end 제품 분석 단면 | 계측 오류 1개+분석 정의 오류 1개 | 정상 fixture·두 사건·회복 oracle·privacy·handoff; 모든 managed 기능/DR를 완성했다는 주장 금지 |

## 7강과 학습 전환

1. [Event 계약](lessons/01-event-contracts.md), AM01–02: 질문·행동·전송 객체·분석 분모를 연결합니다. 정상 사용자 집합을 설명하지 못하면 차트 튜닝부터 하지 않습니다.
2. [SDK·전달](lessons/02-sdk-delivery.md), AM03–04: SDK 호출 반환, transport 결과, 수락, 최종 가시성을 분리합니다. timeout은 실패 확정도 성공 확정도 아닙니다.
3. [Identity·시간·세션](lessons/03-identity-sessions.md), AM05–06: 실제 사람·제품 로그인·분석 identity가 같다는 가정을 제거합니다. identity 변화와 시간 범위를 고정한 뒤 count를 비교합니다.
4. [분석 의미](lessons/04-analysis-semantics.md), AM07–08: 정상 작은 집합의 정확한 oracle로 차트를 검산합니다. event 총수, user 집합, 전환 기회, 성숙 cohort를 섞지 않습니다.
5. [품질·거버넌스](lessons/05-quality-governance.md), AM09–10: 수집 감소를 제품 개선으로 오판하지 않고 관측 사각과 금지 데이터 경로를 진단합니다.
6. [Backfill·확장 운영](lessons/06-backfill-operations.md), AM11–12: 서버 노드 증설이 아니라 sender·quota·identity 편중·분석 계약·변경 통제를 운영합니다.
7. [소스·미니 연구](lessons/07-research-capstone.md), AM13–14: 알려진 SDK 경계 하나를 깊게 추적하고 원인·수정·한계를 다른 사람이 재검산하게 만듭니다.

## 실행 범위

| 범위 | 가능한 증거 | 대체할 수 없는 것 |
| --- | --- | --- |
| `PREP/CONTRACT` | fixture·기대 사용자 집합·payload·manifest 정적 검산 | 실제 수집·identity merge·차트·운영 복구 |
| `SDK-LOCAL` | 별도 시험 앱/로컬 transport에서 queue·flush·consent·오류 분류 | Amplitude SaaS 수락·차트 engine·quota 동작 |
| `TEST-PROJECT` | 허가된 비운영 프로젝트에서 작은 합성 event와 실제 UI/API 관측 | 회사 운영 데이터·다른 region/plan·대규모 처리량 |
| `EVIDENCE-REVIEW` | 승인된 정제 실제 사건의 원장·설정·복구 결과 분석 | 직접 장애 재현/수정했다는 주장 |

기본 웹 앱과 제공 runner가 모든 SDK/화면 자동화/backfill 도구를 제공한다는 뜻이 아닙니다. 현재 정확한 범위는 [실습 안내](labs/README.md)를 확인합니다. native mobile 앱은 미제공이며 [수동 준비](labs/mobile-lab.md)가 필요합니다. 추가 과제에서 권한이 없으면 설계/자료 분석 상태로 남깁니다. 어떤 수치도 승인된 실습 event/요청/시간/비용 상한을 늘리는 근거가 아닙니다.

## 읽기 근거와 제출

공식 [계획·계측 흐름](https://amplitude.com/docs/data/data-planning-workflow), [Browser SDK 2](https://amplitude.com/docs/sdks/analytics/browser/browser-sdk-2), [분석 chart 지도](https://amplitude.com/docs/analytics/charts), [Observe](https://amplitude.com/docs/data/validate-events)를 함께 읽고 버전·권한별 지원을 확인합니다. 공개 SDK와 비공개 서비스의 선은 [소스 지도](source-reading.md)를 따릅니다.

각 모듈은 manifest, 가설, fixture/oracle, 실행·관측 시각, 실제 결과, 경쟁 원인, 제한된 조치/원복, 미검증 범위를 제출합니다. 실제 token·key·원본 고객 데이터·브라우저 전체 storage/네트워크 dump를 커밋하지 않습니다. 기본 LAB 통과와 28주 심화 평가는 [별도 기준](assessment.md)으로 판정합니다.
