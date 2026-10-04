# Amplitude 운영 LAB — 이벤트 누락과 제품 변화를 구분하기

[시작](README.md) · [웹 기본 LAB](labs/README.md) · [모바일](labs/mobile-lab.md) · [보고서](../../operations/incident-report-template.md)

관측의 기준은 Amplitude 내부 서버 CPU가 아니라 **원본 행동·SDK 호출·전송·ingestion·사용자 식별·분석 계약**입니다. 배포 뒤 전환율이 내려갔을 때 실제 UX/기능 결함과 계측/분석 문제를 구분하는 것이 목표입니다. 아래는 수행할 지침이며 실제 회사 프로젝트의 사고를 조사하거나 변경한 결과가 아닙니다.

<a id="basic-lab"></a>

## 기본 LAB: 정상 동작에서 장애 복구까지

| 단계 | 실제로 수행할 것 |
| --- | --- |
| 정상 기능 | 웹 시험 앱에서 합성 A의 View→Checkout→Purchase 3건과 `1→1→1` 퍼널 확인; 모바일은 같은 작은 계약을 해당 SDK로 구현 |
| 동작 원리 | SDK queue/storage·flush/transport·수집 응답·user/device/Amplitude ID·event time·chart 계산 경계를 그림/원장으로 설명 |
| 모니터링 | 원본 intent 원장→정제 SDK callback/Network→Ingestion Debugger→User Activity/Event Stream→차트 정의 비교 |
| 제약 | 앱 memory queue·동의·OS lifecycle·실제 project/region·SDK version·기능 권한·시간/분모·서버 내부 관측 불가를 분리 |
| 대표 사건 | 기본: 중복 계측과 잘못된 임시 chart filter. 다음: offline/reconnect, user만 비운 logout, opt-out·수집 누락. 실제 OS/SDK별 재현 범위를 표시 |
| 회복 검산 | 원인을 가르는 증거 확보 후 자신의 시험 코드/설정/임시 chart만 수정; 신규 원장의 정확한 ID·속성·사용자 집합·분자/분모 검산 |

28주 심화는 선수 조건이 아닙니다. 웹 최소 앱·HTTP 보조 runner는 제공하지만 모바일 앱·지속 모니터링 exporter·회사 대시보드는 제공하지 않습니다. 준비 상태와 실제 결과는 [검증 기록](labs/validation.md)에 구분합니다.

## 1. 첫 30분: 읽기 전용 baseline

조회 권한이 있는 **테스트 프로젝트**의 비민감 별칭·region·시간대와 SDK/app revision을 기록합니다. 운영 데이터만 접근할 수 있다면 허가된 정제 자료로 분석하고 사건을 주입하지 않습니다.

1. **앱 원장:** 정상 3개 행동의 시각/intent와 SDK 호출 수를 비교합니다. 중복 handler, SPA 재마운트, native 화면 재생성, 다중 instance가 없는지 확인합니다.
2. **SDK/Network:** 이벤트를 실제로 생성했는지, identity/consent 상태, batch/flush 시각, 요청 status/실패 구간을 확인합니다. 원본 key/payload/HAR는 공유하지 않습니다. 실패가 어느 층인지 아직 모르면 retry부터 추가하지 않습니다.
3. **수집 상태:** 해당 source/endpoint의 Ingestion Debugger에서 성공/오류 요청·event 수와 throttled 대상 여부를 봅니다. 요청 건수와 이벤트 건수는 다른 분모입니다. 실제 권한·UI 경로를 manifest에 기록합니다. [공식 debugger 안내](https://amplitude.com/docs/migration/migrate-from-adobe)
4. **사용자 이벤트:** User Activity/Event Stream에서 합성 user/device·run/source·시간·속성을 대조합니다. Event Explorer는 실제 이용 가능 범위에 맞춰 사용합니다. [이벤트 QA](https://amplitude.com/docs/analytics/charts/event-explorer)
5. **차트:** event 이름·source/run·날짜/timezone·totals/unique·cohort·funnel 순서/창을 나란히 적습니다. ingestion에 보인 이벤트가 현재 chart의 대상이라는 보장은 없습니다.
6. **품질:** Observe가 제공되는 환경이면 schema 변화·위반/예상 밖 속성을 원래 tracking plan과 대조합니다. 관측 경고와 실제 수집 거부를 동일시하지 않습니다. [Observe/validation](https://amplitude.com/docs/data/validate-events)

계측 build/환경·관측 기간·분모가 다른 화면의 숫자를 먼저 맞추지 않습니다. normal 5분 → 증상 5분 → 복구 관측은 학습용 시간 창이며 실제 quota·가시성·SLO 보장이 아닙니다. 보이지 않는다고 무한 polling하지 않고 5분 뒤에도 미확인이면 unknown으로 남겨 대상/문서를 조사합니다.

## 2. 지표와 분모

아래는 **실습 원장의 논리적 지표**입니다. Amplitude가 같은 이름의 metric API/exporter를 제공한다는 뜻이 아닙니다. 실제로 수집 가능한 필드와 어디서 계산했는지를 별도 기록합니다.

| 신호 | 관측/계산·단위 | 해석 제한 |
| --- | --- | --- |
| eligible business intents | 동의/정책상 분석 대상인 고유 업무 행동, 건/동일 구간 | SDK 로그 자체를 원본 행동 분모로 쓰지 않음; 결제 DB건수와 View건수도 다름 |
| track calls / intent | 앱 계측 wrapper의 호출 수/고유 intent | 중복 handler 진단; 자동 이벤트는 별도 source로 분리 |
| SDK pending / oldest age | 지원되는 SDK 저장/queue 계측, 건·초 | 직접 볼 수 없으면 unknown; flush 호출 횟수로 queue=0 추정 금지 |
| send attempts / failures | Network·SDK 전송 기록의 건·status별 구간 비율 | batch 요청과 event 수 분리; timeout은 수신 상태 불확정일 수 있음 |
| accepted / visible | 수집 응답·debugger와 사용자 event 조회를 각각 기록 | 수락 수가 최종 고유 수/차트 반영 수라는 보장 없음 |
| freshness | 합성 발생 시각→처음 관측한 가시 시각, 초 | 클라이언트 clock skew·관측 간격·event/upload time 차이 포함 |
| completeness / duplicates | 고정 원장의 기대 ID 대 관측 ID 집합·차이 | API/UI에 ID가 안 보이면 완전 대사 미검증; 같아 보이는 비율만으로 통과 금지 |
| funnel/retention | 정의를 고정한 분자 사용자 집합/분모 사용자 집합 | 미성숙 cohort·기간·identity 변경·필터 차이를 먼저 통제 |
| schema/source drift | event/property type·version·platform/build별 위반·누락 | 권한/기능/실제 enforcement 범위 확인; 경고 0이 개인정보 안전 보장 아님 |

대상 분모 0은 0%가 아니라 표본 없음입니다. UI 구간 집계는 프로세스 누적 counter가 아닙니다. client counter를 재시작 전후 비교할 때는 reset을 처리합니다. 합성 ID·run 기반 필터는 테스트에서만 사용하고 회사 전체 사용자 raw ID를 high-cardinality metric label로 복제하지 않습니다.

## 3. 증상별 진단·조치·회복

| 증상 | 경쟁 가설과 첫 증거 | 제한된 조치 | 회복 oracle |
| --- | --- | --- | --- |
| 화면 행동은 있었는데 이벤트 없음 | 동의/opt-out, handler 미실행, queue/종료, 망/CSP, 잘못된 key/region, chart filter; 원장→SDK→Network→프로필 순서 | 확인한 시험 경로 하나만 수정. 보안/동의 우회·전량 replay 금지 | 허용된 신규 합성 event의 정확 ID/값 가시성, 금지 동의 상태의 새 event는 수집되지 않음 |
| event total이 두 배 | 수동+자동 중복, handler 이중 등록, 새 insert ID 재시도, genuine 두 행동; intent와 event ID 비교 | 정상 한 intent/한 호출로 변경한 새 run, 기존 분석 오염 범위 기록 | 신규 intent별 event 1개; 단순 unique user 수 동일만으로 해결 판정 금지 |
| logout 이후 귀속·DAU 이상 | user만 비움, device 재사용, 불안정 user ID, 공유 기기, queue의 과거 identity; client와 서버 profile 비교 | SDK별 logout/reset 계약과 원래 업무 identity 설계 적용 | 새 anonymous/device·다음 login의 기대 사용자 집합, 과거 merge/이미 전송된 event는 자동 수정됐다고 하지 않음 |
| HTTP 200인데 funnel 다름 | totals/unique·순서/창·timezone·source/run·schema drift·late event | 임시 chart의 한 조건만 원복하고 원장 대사 | 웹 `1→1→1` 또는 별도 HTTP `4→3→2`와 정확한 전환자; 분모 바꿔 수치만 맞추지 않음 |
| 400/403/413 | payload/ID/time·WAF/대상/권한·크기 문제; endpoint 계약·status 분류 | 고정 입력/schema/배치 크기를 검토한 별도 시험; blind retry 금지 | 유효한 신규 입력의 수락·조회 확인, 거부/불확정 항목은 원장 보존 |
| 429·timeout·지연 | ID 편중·project/endpoint 제한·네트워크·retry 폭주·다른 팀 유입 | 실제 경계별 제한 조사, 발생기 중단, 승인된 sender 제한/backoff·재처리 설계 | 정상 범위 재전송/신규 흐름·oldest backlog·누락/중복 대사. 기본 LAB에서 부하로429를 만들지 않음 |
| 배포 뒤 schema/지표 회귀 | 앱/SDK/CMP/remote config·tracking plan·차트 revision 차이 | canary/new run에서 원인 revision 하나 복구, 테스트 완료 후 별도 배포 승인 | 같은 분석 계약의 정상 ID/필드·동의 경계·새 발생률 회복; 과거 데이터 정정은 별도 작업 |

HTTP status의 자세한 의미·부분 실패/재시도 규칙은 사용한 endpoint의 [HTTP V2 문서](https://amplitude.com/docs/apis/analytics/http-v2)로 확인합니다. SDK version별 queue/retry/flush 계약을 함께 읽으며 직접 HTTP의 거부를 네이티브 SDK lifecycle 원인으로 단정하지 않습니다.

## 4. 확장·예방 학습

Amplitude의 확장 문제는 사용자가 임의로 SaaS node를 추가하는 LAB이 아닙니다. event volume/속성 cardinality·sender batching·사용자/장치 편중·quota·consent·tracking plan 배포·warehouse/backfill·서로 다른 분석 정의를 관리하는 과제로 다룹니다. [심화 운영 강의](lessons/06-backfill-operations.md)에서 비용/권한/요청 상한·checkpoint·대사·중단 조건을 정합니다.

실제 한도를 초과시키거나 raw 회사 데이터를 export/import하는 것은 기본 과제에 포함하지 않습니다. 권한이 없으면 공식 계약+정제된 실제 장애 기록으로 조사 보고서를 작성하며 직접 복구와 구분합니다. 장애 빈도의 정량 순위를 주장하지 않고 대표 사례를 예방하는 학습으로 사용합니다.

## 5. 기본 완료와 종료

정상 기능·원리 설명·수집 방법·제약을 먼저 제출하고, 서로 다른 사건 두 개의 정상/실패/조치 후 원장·가설·회복 ID·남는 영향/미검증을 기록합니다. 새 데이터의 회복과 과거 분석 오염의 정정은 별도입니다. opt-out/reset/flush/프로세스 종료/서버 삭제를 같은 복구로 취급하지 않습니다. 특히 제공 웹 앱의 중지는 **이미 queue에 있거나 전송 중인 이벤트를 취소하지 않습니다.**
