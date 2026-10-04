# Amplitude 평가 — 정상 수치부터 복구 후 신뢰까지

[기본 LAB](operations.md) · [실습 제공 범위](labs/README.md) · [심화 커리큘럼](curriculum.md) · [소스 지도](source-reading.md)

기본 LAB와 28주 심화는 별도 평가입니다. 정상 기능을 사용하고 원리·관측·제약을 설명한 뒤 흔한 두 문제를 진단·회복하면 기본 LAB를 평가받을 수 있습니다. 전체 14모듈 이수나 CPU 모형 구현을 선수 조건으로 두지 않습니다.

## 1. 실행 증거 상태

| 상태 | 증거 | 아직 주장할 수 없는 것 |
| --- | --- | --- |
| 계약/준비 | synthetic fixture·oracle·manifest·허가 scope·설정 | 실제 Amplitude ingest/차트 성공 |
| 로컬 SDK 실행 | 고정 package·local transport/storage·원시 결과 | 서버의 identity/dedup/한도 동작 |
| 프로젝트 실행 | 허가된 test project의 요청/응답·event/차트 관측 | 결과 검산 없이 정확성·운영 안전성 |
| 검증 | 독립 oracle·실제 대조·음성 입력·회복·한계 | 다른 SDK·region·plan·대규모 부하로 일반화 |
| 자료 분석 | 승인된 정제 실제 사건·설정·원장·복구 기록 | 직접 장애 주입/수정 완료 |

각 상태는 실제 수행 범위에만 적용합니다. 정상 API fixture 성공과 Browser SDK/identity/funnel/retention 실습은 서로 대체하지 않습니다. 사용 가능한 기능이 없으면 `미지원/권한 없음/미실행`을 남기며 실제 값 0으로 채우지 않습니다.

## 2. 기본 LAB 필수 관문

### B1. 정상 기능과 업무 oracle

웹 기본 SDK 앱의 새 synthetic run에서 로그인 A→수동 View/Checkout/Purchase의 event ID·사용자·event_type·업무 값·event time을 전송 전에 기록합니다. 정상 수락과 가시성을 구분하여 UI에서 totals/unique와 해당 ID/속성을 검산합니다. HTTP 비교 fixture는 별도 source/run으로 판정합니다. 필요한 UI/API 권한이 없으면 가시성 검증 미완료입니다. 응답 수만 맞고 event/사용자 집합이 틀리면 실패입니다.

### B2. 원리와 관측 지점

업무 발생→SDK/API 요청→응답→최종 분석의 책임 경계를 설명합니다. offered, attempted, accepted, visible, unknown의 정의·단위·시간 창을 기록합니다. 원인 후보를 SDK/네트워크/validation·quota/identity/시간·차트 설정 중 적어도 두 계층으로 나누고 증거로 배제합니다. 비공개 내부 engine은 unknown으로 둡니다.

### B3. 정상 기능에 붙인 두 사건

[운영 카드](operations.md)에서 서로 다른 사건 두 개를 선택합니다. 권장 조합은 (a) 잘못된 event 계약 또는 계측 중복과 (b) totals/unique·시간·funnel 정의의 분석 불일치입니다. 제공 runner가 수행한 validation과 수동 UI 진단을 분리합니다. 실제 429·대량 traffic·개인정보 유출을 만들 필요는 없으며 로컬 오류 fixture는 그 범위로만 판정합니다.

각 사건에 정상 상태, 한 변인, 증상, 두 경쟁 가설, 관측 증거, 변경·중단 조건, 조치·원복, 정확한 회복 결과가 필요합니다. 웹 SDK는 navigation/offline·중복 계측·identity·consent의 실제 경계를 연결합니다. 모바일 수행을 주장하려면 iOS Swift/Android Kotlin 중 준비한 플랫폼에서 foreground/background·offline/reconnect·logout/reset의 별도 결과가 필요하며 웹/HTTP 결과로 대체하지 않습니다. 금지 이벤트가 거부되는 정상 기능을 서버 장애로 보고하지 않습니다.

### B4. 제약과 안전한 회복

허가된 test project·합성 ID·region·SDK/API 종류·최대 요청/event/시간/비용을 기록합니다. 회사 운영 project, 실제 사용자, 외부 cohort 동기화/메시지 알림, 관리/삭제 기능은 범위 밖입니다. 설정 원복은 새 수집 동작의 복구이며 이미 들어간 잘못된 데이터를 자동 취소하지 않습니다. 재전송은 accepted/unknown 원장을 확인한 뒤 제한적으로 판단합니다.

### B5. 개인정보·비밀·동의

실제 email/token/URL query/고객 payload를 fixture·로그·차트에 넣지 않습니다. consent 전 수집/저장/송신을 따로 검사하고 autocapture/Replay/다른 plugin은 검증하지 않았다면 제외합니다. 인증 key·secret과 브라우저 전체 storage/네트워크 원문을 커밋하면 실패입니다. 이 기술 검사는 법률 준수 인증이 아닙니다.

### B6. 회복 oracle와 정직한 상태

같은 분석 정의로 새 정상 run을 다시 검산하고 누락/중복/identity 혼입/잘못된 속성 0을 확인합니다. 늦은 가시성·관측 한계·불확실한 요청은 명시적으로 남깁니다. 설계·local mock·단위 테스트 개수를 실제 SaaS 운영 성공으로 표시하지 않습니다.

## 3. 선택 심화 점수: 25 × 4

선택한 심화 범위는 총 **80/100 이상·각 영역 15/25 이상**, 해당 실행 범위의 필수 관문을 충족할 때 통과합니다. 점수는 전문가 인증이나 회사 운영 적합성 보증이 아닙니다.

| 영역 | 최소 충족 | 전문가 수준 증거 |
| --- | --- | --- |
| 정확성 25 | ID/속성/시간·사용자 집합·분모가 일치 | identity·dedup·late event·funnel/retention의 반례와 unknown 처리 |
| 원리·source 25 | 고정 SDK/API 계약과 공개/비공개 경계 | 실제 package 대응 SHA·구현/테스트 추적·문서와 관측의 차이 설명 |
| 실험·반증 25 | 한 변인·정상/음성·독립 oracle | 배포/계측/분석 정의의 대안 가설을 구분하는 최소 실험 |
| 운영·재현 25 | manifest·bounded 실행·회복/보존 원장 | 중단 후 안전한 재개·backfill 정합성·privacy·변경 영향까지 재검산 |

## 4. 모듈별 증거와 오답

| 모듈 | 제출물 | 통과할 수 없는 결론 |
| --- | --- | --- |
| AM01–02 | taxonomy·owner·버전 호환/소비 차트 행렬 | 이름 rename은 과거 event 의미도 자동 변경한다 |
| AM03–04 | queue/flush·응답 분류·attempt/event 원장 | track 반환/200이면 모든 차트 성공, 모든 오류를 같은 방식 retry |
| AM05–06 | 합성 identity 전이·UTC/project/session 시간표 | device=사람, logout 뒤 user_id만 지우면 항상 새 익명 사용자 |
| AM07–08 | 정확한 user 집합·funnel 분모·성숙 retention cohort | 일별 unique 합=전체 unique, 미성숙 Day N을 0%로 집계 |
| AM09–10 | 수집/품질/freshness·canary·권한 경계 | Observe 정상=upstream 누락 없음, 숨김=물리 삭제 |
| AM11–12 | backfill mapping/ID/partition ledger·한도/rollout | import는 rollback 가능, worker 증설이면 SaaS limit 해소 |
| AM13 | source permalink·테스트/반례·미공개 영역 | SDK source로 SaaS 저장/merge/query 구현 증명 |
| AM14 | 정상 run+두 사건+복구+인수인계 | 한 fixture 통과를 모든 기능·회사 환경으로 확대 |

## 5. 구술 리뷰

1. API 200인데 오늘 차트가 0이면 무엇부터 확인하는가? event time·timezone·project·event 이름·filter·가시성 시각을 어떤 순서와 증거로 구분하는가?
2. retry마다 새 insert_id를 만들면 무엇이 달라지는가? 응답이 유실된 요청의 결과가 unknown이면 어떻게 보존하는가?
3. 로그인 후 unique가 줄거나 logout 뒤 사용자가 섞여 보이면 어떤 ID 전이를 재현하는가?
4. purchase totals가 3인데 funnel 전환자가 1인 것이 언제 정상인가? user 집합과 chart 설정으로 설명할 수 있는가?
5. backfill 뒤 new-user/retention이 바뀌면 어느 변경이 데이터 수정이고 어느 변경이 정의/시간/identity 효과인가?
6. 관리 화면에서 event를 숨기는 것, 미래 수집을 막는 것, user privacy 삭제 요청은 왜 같은 원복이 아닌가?

판정 근거는 [identity 계약](https://amplitude.com/docs/data/sources/instrument-track-unique-users), [funnel 계산](https://amplitude.com/docs/analytics/charts/funnel-analysis/funnel-analysis-how-amplitude-computes), [backfill 주의](https://amplitude.com/docs/data/data-backfill), [governance 문제 구분](https://amplitude.com/docs/data/troubleshooting/instrumentation-issues)와 실행 manifest의 실제 설정입니다. 읽은 날짜와 적용 범위를 함께 제출합니다.
