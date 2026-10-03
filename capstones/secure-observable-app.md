# 보안·관측 가능한 앱: Supabase + Sentry 통합 연구 8주

이 과정은 [데이터 파이프라인 캡스톤](../databases/shared/capstone.md)과 **선택 관계인 별도 주제**입니다. 모두를 필수로 더하지 않습니다. Supabase와 Sentry 트랙에서 만든 작은 앱·권한 테스트·SDK harness를 재사용합니다. 기본 저장소에는 완성 앱·제품 스택·계정이 없으며 실제 구현·실행은 과제입니다. 트랙의 2주 미니 캡스톤만 완료하고 이 통합 연구까지 실행했다고 표시하지 않습니다.

## 업무 계약과 실패 모델

합성 tenant A/B의 문서 관리 앱을 만듭니다. 로그인·문서 생성/제목 수정·관리자 삭제·비공개 첨부·실시간 변경 알림을 제공합니다. 관측에는 오류·지연·안전한 request/run ID만 사용합니다. 실제 고객·토큰·사용자 본문은 실습에 넣지 않습니다.

| 불변식 | 독립 oracle |
| --- | --- |
| 다른 tenant의 행·객체·채널 데이터가 보이지 않는다 | 권한 fixture + API/Storage/Realtime 응답의 ID와 payload 비교 |
| 금지된 쓰기는 결과를 바꾸지 않는다 | 사용자 응답과 별도 관측자의 변경 전후 상태 대조 |
| 재시도는 문서·객체·함수 부작용을 잘못 중복 적용하지 않는다 | stable operation ID와 실제 부작용 횟수 |
| 관측 시스템에 금지 데이터가 남지 않는다 | 합성 canary가 실제 outgoing/수신·저장 경로에 없는지 검사 |
| 장애를 해결하면 업무 상태와 권한이 복원된다 | 별도 restore의 행·객체 hash·로그인/인가·앱 조회 |

권한 실패를 곧바로 HTTP 500으로 기록하거나 모든 403을 장애로 경보하지 않습니다. 업무상 거절·앱 결함·Auth 실패·관측 유실을 별도 분류합니다. source event/row ID, request ID, Sentry event/trace ID가 서로 다른 정체성임도 기록합니다.

## 1–2주: 모델·위협·관측 계약

[Supabase 18개 권한 기준](../platforms/supabase/labs/authorization-oracle.json)을 실제 Auth 사용자로 매핑합니다. member/admin과 서버 maintenance identity를 분리하고 tenant·owner 불변식을 정합니다. refresh·로그아웃·membership 해제·미만료 access token의 기대 권한을 문서화합니다. 모든 변경을 JWT 즉시 무효화가 자동 해결한다고 가정하지 않습니다.

각 데이터 필드에 `업무 저장 필요`, `관측에 허용`, `관측 금지`, `합성 대체`를 붙입니다. errors, spans, logs, replay, attachment 등 실제 활성 데이터 종류마다 다른 필터 경로를 정의합니다. SDK·서버 필터의 순서와 적용하지 못하는 경계를 구별합니다.

**제출:** schema·권한 matrix·위협 모델, 비밀 없는 component manifest, HTTP/DB/Auth/관측의 상태 전이, 아직 미구현된 테스트 목록. SLO는 입력 규모·지연·오류율·관측 지연·비용 예산과 함께 정하고 고정 숫자를 달성했다고 주장하지 않습니다.

## 3–4주: 허용·거절·실제 수집 구현

grants/RLS와 migration을 구현하고 SQL 테스트 및 실제 Auth 사용자 API 테스트를 나눕니다. 같은 사용자·tenant 계약을 view/RPC·Storage·Realtime·Function 경로에 적용해 우회가 없는지 검사합니다. membership 해제 후 기존 WebSocket의 권한 갱신과 reconnect를 실제 기능의 계약에 맞춰 검증합니다. replay 지원의 범위가 기능별로 다르면 별도 결과로 기록합니다.

앱에 Sentry SDK를 연결하되 먼저 무외부송신 transport로 동시성·context·privacy를 검증합니다. 별도 학습 프로젝트로 보내는 단계는 전송 허용 데이터·quota·알림 대상·보존을 먼저 정한 뒤 수행합니다. source map/Debug ID·release 연결을 검증하고 source artifact에 비밀이 없는지도 확인합니다. 실제 프로젝트가 없으면 서버 grouping·검색·알림은 미실행입니다.

**제출:** 18개 기준의 실제 결과, 정상/권한 거절/의도된 결함 3종의 앱·DB·SDK 이력, 금지 canary 검사, 입력 대비 수집/제외/미확정 원장. 이벤트가 보이지 않는 현상을 “오류 없음”으로 기록하지 않습니다.

## 5–6주: 장애·재시도·관측 손실

최소 다섯 종류를 독립 run으로 실행합니다. 실제 운영·계정의 장애를 유발하지 않습니다. 각 run에는 시간 제한, 자원 한도, 중단 조건, 원복 절차가 있어야 합니다.

| 실험 | 실패 주입 | 확인할 계약 |
| --- | --- | --- |
| 세션/권한 경계 | membership 해제 뒤 기존 token·connection 재사용 | 선언한 즉시/지연 적용 정책, stale 권한 검출 |
| SSR/context 격리 | 동시 A/B 요청·refresh·공유 cache 조건 | 응답·cookie·SDK scope에 tenant/사용자 혼입 없음 |
| 객체/함수 경계 | 업로드 또는 부작용 성공 뒤 앱 응답 유실 | orphan·중복·부분 성공을 검출하고 안전하게 수렴 |
| 관측 종료 경계 | capture 직후 종료·flush timeout | 앱 오류와 수집 손실을 원장으로 구분 |
| 관측 전송 경계 | 격리 proxy/transport에서 응답 지연·rate limit·실패 | bounded retry·backpressure·drop/unknown 집계 |
| schema 경계 | 구 앱/신 앱·RLS migration 전후 혼합 | 접근 확대 없이 기능 유지 또는 명시적 거절 |

proxy나 fake transport를 썼다면 실제 Sentry 서버의 장애를 주입한 것으로 말하지 않습니다. 공개 서비스에 부하를 가하거나 rate limit을 유발하는 대신 격리된 도구·합성 응답을 먼저 사용합니다. observability가 고장 난 동안에도 업무 정합성을 판단할 독립 원장을 유지합니다.

**제출:** 장애별 ID·시점·상태·실제 결과, 개선 전후 반례, 원복 및 데이터 대조. 성능 비교는 [공통 실험 방법](../databases/shared/experiment-method.md)을 따르며 샘플링·누락된 요청을 분모에서 숨기지 않습니다.

## 7–8주: 복구·source trace·설계 방어

별도 대상에 DB와 객체 bytes를 복원합니다. Auth·권한·config·함수 버전·secret 참조를 복구 범위에 포함하고, 실제 secret을 결과물에 넣지 않습니다. 객체 파일이 없는데 Storage metadata가 남아 있는 경우를 검출합니다. 관측 저장소 복구를 선택했다면 업무 DB 복구와 별개로 범위를 선언합니다.

복구 목표 RTO/RPO는 실험 전에 선언합니다. 실제 복구 시간은 프로세스 기동이 아닌 업무 oracle와 권한 음성 테스트 통과 시점까지 측정합니다. 실제 데이터 손실은 독립 입력 원장의 성공 응답 ID와 복원 상태를 비교해 누락된 ID·시각 및 일관된 복원 시점을 기록하고, 사전 RPO 목표와 대조합니다. 마지막 쓰기 이후의 유휴 시간을 곧바로 데이터 손실이라고 계산하지 않습니다. 복원 후 tenant B가 tenant A의 데이터를 볼 수 있으면 데이터 내용이 맞아도 실패입니다.

문제 한 개를 작은 입력으로 줄여 각 제품의 [Supabase source](../platforms/supabase/source-reading.md) 또는 [Sentry source](../observability/sentry/source-reading.md)에 연결합니다. 제품 간 요청 경계를 network/event 전달로 표시하고, 서로 다른 저장소의 함수가 직접 연속 호출되는 것처럼 그리지 않습니다. SDK-only 실험으로 서버 내부 분기를 실행했다고 주장하지 않습니다.

**최종 필수:** 허용·거절·privacy oracle, 실제 최소 재현, 다섯 장애, 독립 restore 후 업무/권한 검증, component fingerprint와 동료 재현. 미구축인 hosted/self-hosted 기능은 완료가 아닙니다. 공통 기준은 정확성·원리/소스·실험/반증·운영/재현성 각 25점, 총 80점 이상·각 영역 15점 이상입니다.

마지막 90분은 보장/위협 20분, 실패 시나리오 30분, source trace 20분, 미검증 범위와 대안 20분으로 방어합니다. 전체 결과물에는 실제 실행과 설계-only 부분을 구분한 [실험 보고서](../databases/shared/templates/experiment-report.md), [설계 기록](../databases/shared/templates/design-review.md), [장애 기록](../databases/shared/templates/incident-review.md)을 포함합니다.
