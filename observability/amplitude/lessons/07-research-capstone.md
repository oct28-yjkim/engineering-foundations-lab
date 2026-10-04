# 7강 — 공개 SDK 연구와 2주 미니 캡스톤

[커리큘럼](../curriculum.md) · AM13–AM14 · [소스 지도](../source-reading.md) · [평가](../assessment.md)

## 목표와 범위

한 웹 또는 모바일 SDK 경로를 골라 **정상 기능→원리→관측→제약→두 문제→회복**을 독립 재현 가능한 evidence로 묶습니다. 기본 LAB의 선수 과정이 아니며 전체 mobile 앱·회사 tracking plan·모든 chart·backfill/개인정보 삭제를 2주 안에 구현하는 과제가 아닙니다.

웹 기본 앱의 Browser SDK 고정 버전으로 시작할 수 있습니다. 모바일은 [수동 LAB](../labs/mobile-lab.md)의 준비가 끝난 플랫폼 하나를 고릅니다. Swift/Kotlin SDK·OS·앱 source·lockfile·실기기/simulator 여부를 따로 기록합니다. HTTP API fixture만 실행했다면 SDK lifecycle 연구가 아닌 HTTP 전달 계약 연구로 범위를 낮춰 명시합니다.

## 1주차 — 반증 가능한 가설과 정상 단면

1. **경계 하나 선택:** queue에 identity가 결합되는 시점, flush/종료 의미, offline/reconnect, consent/storage, duplicate instrumentation 중 하나를 고릅니다.
2. **공개 계약 읽기:** [소스 지도](../source-reading.md)의 고정 package·SHA와 공식 문서 확인일을 기록합니다. 공개 source/test와 서버 black-box 계약을 나눕니다.
3. **정상 fixture:** 기본 수동 event 또는 소수 합성 업무 event의 ID·속성·user/device·시각·기대 chart를 전송 전에 작성합니다.
4. **실제 source 추적:** API entry→config/identity→queue/transport→결과 분기 중 필요한 구현 두 군데 이상, 관련 테스트 두 개 이상을 permalink로 연결합니다.
5. **관측 준비:** SDK 호출/attempt, sanitized 오류, User Lookup/품질/차트 상태, 독립 업무 원장을 같은 source/run으로 묶습니다. 원시 비밀/개인정보는 수집하지 않습니다.

가설 예: “이 선택 버전/설정에서 background 후 flush 요청을 했으므로 모든 chart가 즉시 같아질 것이다.” 이 주장은 과도하므로 SDK가 관측하는 완료점과 SaaS 가시성·분석의 완료점을 나누어 반증합니다. 항상 실패하도록 결론을 정해두지 말고 실제 조건과 반례를 기록합니다.

## 2주차 — 문제 두 개와 회복

| 선택 사건 | 정상 대조군 | 확인할 경쟁 가설 | 회복 oracle |
| --- | --- | --- | --- |
| SDK lifecycle/네트워크 문제 | 같은 행동의 foreground/online run | 호출 누락·queue·transport·UI 필터 | 원장 event ID·업무 값·unknown 처리·정상 새 run |
| login/logout identity 혼입 | 사용자별 분리한 새 synthetic ID | user/device 전이·instance·과거 merge·query 범위 | 사용자별 marker 집합·교차 귀속 없음 |
| manual/autocapture 중복 | manual only·동일 합성 행동 수 | publisher 중복·서로 다른 event 의미·retry | 목적별 기대 event 수·SDK/config 원복 |
| chart 정의 차이 | 고정 totals/unique/funnel/시간 조건 | 계측 변화·분모/창·cohort·timezone | 정확한 event/user 집합·분자/분모 |

기본 권장은 SDK/계측 문제 하나와 분석 정의 문제 하나입니다. 과금·429·실제 개인정보 유출·운영 데이터 삭제는 재현 목표가 아닙니다. 외부 송신 권한이 없으면 local SDK/문서 분석 범위로 완료하고 SaaS gate는 미실행으로 남깁니다.

각 사건을 시작하기 전에 event/request/시간·금액 상한과 중단 버튼/담당자를 확인합니다. 예상과 다른 project·payload·목적지·사용자 영향이 보이면 발생기를 중단합니다. 조치 이후 새 run의 정확한 결과를 비교하고 기존 잘못된 데이터를 “원복되었다”고 숨기지 않습니다.

## 제출 디렉터리의 논리 구성

- `manifest`: 실제 package/lockfile·app/OS·source SHA·project 별칭/region·권한·설정·chart revision·확인일.
- `contract`: taxonomy·event/user/time 의미·정확 oracle·허용/금지 정보.
- `baseline`: 정상 원장·정제 관측·expected/actual 차이.
- `incident-a`, `incident-b`: 재현·가설·증거·조치·원복·회복·unknown.
- `source-note`: 구현/테스트 permalink, 실행 여부, mock과 SaaS 경계.
- `handoff`: 다른 학습자가 시작·중지·검산하는 방법, 미구현/미실행·추가 권한.

이는 제출 구조이며 실제 key·token·raw 고객 export를 저장하라는 뜻이 아닙니다. 실행 산출물은 저장소의 무시 경로와 조직의 보존 규칙을 따릅니다. 기존 evidence를 덮어쓰지 않습니다.

## 연구 깊이와 완료 판정

전문가는 내부를 그럴듯하게 추정하는 대신 **공개된 SDK의 정확한 상태 전이, API/분석 계약의 반례, 미관측 경계**를 분리합니다. 한 줄짜리 count 비교보다 ID/속성/시간·사용자 집합·SDK/서버 단계의 근거가 중요합니다.

통과는 [기본 관문과 선택 심화 평가](../assessment.md)에 따릅니다. source를 읽기만 했는지 실제 SDK로 재현했는지, local mock인지 허가 test project인지, 웹인지 모바일인지 모두 표시합니다. 평균 latency가 줄었다고 정확성·privacy 저하를 상쇄하지 못합니다.

공식 출발점: [TypeScript SDK](https://github.com/amplitude/Amplitude-TypeScript), [Swift SDK](https://github.com/amplitude/Amplitude-Swift), [Kotlin SDK](https://github.com/amplitude/Amplitude-Kotlin), [Amplitude 문서](https://amplitude.com/docs). 외부 issue/지원 요청·회사 배포·프로젝트 관리 변경은 이 캡스톤의 자동 수행 범위가 아닙니다.
