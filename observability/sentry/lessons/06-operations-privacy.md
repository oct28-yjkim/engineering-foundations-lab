# S11–S12 — 개인정보, tenant 경계, 운영 SLO와 복구

관측 도구는 운영 데이터의 복사본을 여러 경로로 보유할 수 있습니다. 오류 분석을 쉽게 하는 것과 민감정보를 최소화하는 것은 함께 설계해야 합니다. 이 강의의 canary는 전부 인공 문자열이며 실제 비밀정보를 전송해 필터를 시험하지 않습니다.

## S11. `beforeSend` 하나로 모든 신호를 보호할 수 없는 이유

### 선수 조건과 원리

S03–S04, S07과 데이터 분류·최소 권한의 개념이 필요합니다. 에러 event의 hook, breadcrumb, span, structured log, application metric, Replay recording, attachment, profile은 payload 생성과 송신 경로가 다를 수 있습니다. `beforeSend`로 error JSON을 수정했다고 attachment binary나 Replay의 DOM/network 정보를 함께 제거했다고 결론 내리지 않습니다.

현재 JS 문서는 error/message의 `beforeSend`, breadcrumb의 `beforeBreadcrumb`, span의 `beforeSendSpan`/지원되는 제외 설정, transaction mode의 `beforeSendTransaction`을 구별합니다. logs와 metrics는 별도 hook을 제공합니다. API 이름만 복사하지 말고 선택 SDK의 지원 버전·호출 순서·drop 가능 여부를 확인해야 합니다. [필터링](https://docs.sentry.io/platforms/javascript/configuration/filtering/), [Logs](https://docs.sentry.io/platforms/javascript/logs/), [Metrics](https://docs.sentry.io/platforms/javascript/metrics/)

Replay의 기본 text/input masking과 media blocking은 유용하지만 모든 데이터 경로의 보편적 보증이 아닙니다. mask/block/ignore의 의미, DOM 속성·URL·network body·canvas·mobile 화면의 지원과 설정을 각각 확인합니다. UI에서 가려 보이는 것만 확인하지 말고 전송되는 serialized recording과 metadata도 검사합니다. [Replay privacy](https://docs.sentry.io/platforms/javascript/session-replay/privacy/)

DSN은 프로젝트 수집을 위한 routing/authentication 정보와 관련되지만 조직 관리용 API token과 같은 권한을 뜻하지 않습니다. browser에 노출되는 수집 식별자와 서버 측 관리 credential을 분리하고, DSN을 알고 있다는 이유만으로 프로젝트 데이터 조회 권한이 있다고 가정하지 않습니다. 반대로 비밀 관리 token을 client bundle에 넣으면 심각한 경계 위반입니다. 저장소에는 어느 종류든 실제 값 대신 placeholder와 secret 주입 계약을 둡니다.

애플리케이션의 `tenant_id` tag는 Sentry 서버의 authorization boundary가 아닙니다. 같은 Sentry project에 A/B 애플리케이션 tenant 데이터를 넣으면 그 project를 볼 권한이 있는 운영자가 양쪽을 볼 수 있습니다. UI tag filter를 접근 통제로 사용하지 않습니다. tenant별 분리 요구가 있다면 선택 배포에서 실제 지원하는 organization/project/team/role 및 token scope에 요구사항을 매핑하고, 허용/거부 접근 행렬을 따로 검증해야 합니다.

### 실험: 합성 canary의 전체 egress 검사 — `SDK-LAB` / 필요 시 `PROJECT-LAB`

금지 canary `TEST_SECRET_ALPHA`, 합성 이메일 `person@example.invalid`, tenant A/B 구별 문자열, 허용 correlation ID를 준비합니다. 실제 토큰·고객 데이터는 사용하지 않습니다. input은 URL query, error message, stack 주변 context, breadcrumb, user/tag/extra, span attribute, log body/attribute, metric attribute, Replay DOM/network, attachment text/binary, profile의 지원되는 metadata 위치에 각각 넣습니다. 지원하지 않는 신호는 “N/A + 버전 근거”로 표시합니다.

1. 데이터 분류표에서 허용/해시화/삭제/수집 금지를 먼저 결정합니다. hash가 자동으로 익명화를 보장한다고 쓰지 않습니다. 낮은 entropy 값은 사전 공격과 연결 가능성이 남습니다.
2. SDK transport의 모든 Envelope item을 추출하고, 압축·binary·recording format에 맞게 검사합니다. JSON 최상위 key만 검사하는 oracle은 부족합니다.
3. local capture 단계에서 금지 canary가 사라졌는지 판정합니다. client-side scrub이 필요한 정보는 server-side scrub만으로 egress 금지 조건을 충족하지 못합니다.
4. 허용된 별도 project로 확장하는 경우 서버 ingest 전/후와 조회 API·artifact·첨부 접근 경계를 검증합니다. 서버에 도달한 뒤 지워졌다는 사실과 송신 전 제거는 구별합니다.
5. organization/project/team/role 기반으로 허용·거부를 미리 정한 시험 계정의 접근 행렬을 허가된 환경에서 검증합니다. 예를 들어 A project만 허용된 계정이 B project를 조회할 수 없는지 확인하되 선택 배포의 실제 권한 모델을 먼저 확인합니다. 같은 project의 A/B tag는 별도 권한 경계로 가정하지 않습니다. 문맥 canary가 섞이지 않는 SDK test와 서버 authorization test는 다른 gate입니다.

oracle은 금지 값의 raw byte/정규화 표현이 모든 검사 대상 payload에서 0회이고, 허용 correlation ID가 필요한 위치에 남아 있는 것입니다. 문맥 손실 때문에 디버깅 가능성이 사라진 경우도 기록합니다. URL encoding·JSON escape·대소문자·한글 등 표현 변형 fixture를 추가해 허술한 문자열 검색기를 반증합니다.

### 실패와 통과 기준

에러만 scrub한 상태에서 attachment에 canary가 남는 반례, breadcrumb를 제거했지만 log body에 남는 반례, tenant가 shared scope로 섞이는 반례를 적어도 세 개 탐지해야 합니다. 설계로만 작성한 profile/Replay 검사는 실제 검사 완료로 체크하지 않습니다. 도구가 생성한 debug log와 raw evidence 파일 자체도 canary 외 실제 개인정보가 없는지 검토합니다.

산출물은 신호×필드×수집 단계 privacy matrix, egress 검사 코드/결과, 권한 테스트 범위, retention·삭제·artifact 접근 정책입니다. 선택한 모든 지원 신호의 금지 canary 0, tenant boundary 명시, credential 노출 0이어야 통과합니다. 법적 준수 인증을 이 실습만으로 주장하지 않습니다.

## S12. 관측 시스템의 SLO와 복구 증거

### 선수 조건과 원리

S09–S11과 RPO/RTO 개념이 필요합니다. self-hosted 공식 배포는 여러 서비스를 조합하지만 단일 host 설치가 자동 HA가 되는 것은 아닙니다. host·disk·network·controller·storage·credential의 장애 도메인과 운영 인력을 고려해야 합니다. SaaS에서 제공되는 기능이 self-hosted에 전부 동일하게 존재한다고 가정하지 않습니다. 공식 기능 차이, optional feature, reference architecture를 선택 revision과 함께 검토합니다. [Self-hosted 안내](https://develop.sentry.dev/self-hosted/)

수집 SLO에는 HTTP 성공률만이 아니라 “합성 입력이 지정 시간 내 지정 project/dataset에서 조회 가능한 비율”이 필요합니다. 원시 사건 발생 시각부터 검색까지의 freshness, 처리 backlog age, 영구/미확인 손실, query latency, tenant 접근 정확성도 나눕니다. Sentry 자체 장애를 Sentry만으로 경보하면 공통 실패에 취약하므로 독립된 probe와 기록 경로를 둡니다.

공식 partial JSON backup은 저용량 설정·사용자/조직 등 일부 정보를 다루며, historical event/issue와 외부 파일을 모두 백업하는 수단이 아닙니다. 따라서 “JSON export 성공”으로 전체 복구 가능성을 주장하지 않습니다. PostgreSQL·ClickHouse·blob/artifact·설정·암호화 관련 key material·queue/처리 checkpoint의 범위와 복구 순서를 조사해야 합니다. 모든 구성 요소를 같은 시점의 분산 snapshot으로 묶을 수 있는지도 별도 문제입니다. [Self-hosted backup](https://develop.sentry.dev/self-hosted/backup/)

### 실험 A: 학습용 SLO와 독립 probe — `OFFLINE` 설계 / 별도 배포 확장

합성 error 또는 지원되는 저비용 신호를 낮은 빈도로 생성하고, 별도 probe가 ID를 조회하는 계약을 설계합니다. 예시 학습 목표는 “100개 합성 입력 중 99개가 60초 안에 조회”이지만 이는 제품 보장이 아니라 직접 검증할 가정입니다. sampling·filter 때문에 probe 자체가 제외되지 않도록 그 정책을 명시하되 모든 실제 traffic을 같은 방식으로 취급하지 않습니다.

정상, ingress 실패, downstream 지연의 세 timeline을 입력으로 주고 SLO 분자/분모와 unknown 상태를 계산합니다. query 장애를 ingest loss로 잘못 분류하는 detector를 반증합니다. 알림은 최초 감지·전달·확인·복구 시각을 구별합니다. 실행 확장에서는 background probe가 무한 비용/데이터를 만들지 않도록 횟수와 종료 조건을 둡니다.

### 실험 B: 독립 namespace의 복구 리허설 — `SELF-HOST-DESIGN`

완료된 restore라고 보고하려면 실제 리허설이 필요합니다. 제공 자료에는 전체 배포·백업 자동화가 없으므로 우선 아래 조건을 갖춘 runbook을 작성합니다.

1. fixture: 두 synthetic app tenant의 데이터, 실제 Sentry organization/project/team/role에 매핑한 허용·거부 권한 행렬, 100개 오류 ID, artifact A/B, 작은 합성 attachment, grouping 관계, privacy 정책을 준비합니다. app tenant tag 자체가 접근 통제라는 가정은 하지 않습니다.
2. backup set: 각 저장소의 snapshot 시각·복제 상태·schema/버전·key/config 의존성·검증 checksum을 기록합니다. 실사용 비밀값을 보고서에 넣지 않습니다.
3. consistency: 쓰기를 중단할지, checkpoint를 기준으로 replay할지, 일부 시간 구간의 불일치를 허용할지 정합니다. “전부 복사”만으로 분산 일관성을 해결하지 않습니다.
4. restore: 원본을 덮어쓰지 않는 격리 namespace에서 복원하고, ingress를 합성 입력으로 제한합니다. 운영 endpoint나 알림 수신자로 연결되지 않도록 차단합니다.
5. oracle: ID 집합/내용, tenant 권한, grouping, source artifact 연결, attachment 무결성, 금지 canary 없음, 검색 freshness를 확인합니다. count 일치만으로 복구 성공을 판정하지 않습니다.
6. 측정: 마지막으로 보존된 입력 시각과 실제 중단/복구 시각으로 RPO/RTO를 계산합니다. 설계 목표와 관측값을 나란히 둡니다.

### 업그레이드·rollback과 gate

SDK 단독 변경과 backend/Relay/Snuba/schema 변경은 다른 실험입니다. upgrade 전후 동일 fixture를 흘려 event shape·grouping·symbolication·sampling·privacy·query 결과를 비교합니다. schema migration 후 image만 이전 것으로 바꾸는 rollback이 항상 가능한 것은 아닙니다. 지원되는 migration 순서와 복구 가능한 backup을 release별로 확인합니다. 공개 `main`의 호환성을 runtime release에 보장하지 않습니다.

산출물은 SLO 계약, 실패 도메인 표, 보존·backup coverage matrix, restore/upgrade runbook, 측정 또는 실행 미검증 표입니다. independent probe·부분 백업 한계·분산 복구 일관성·rollback 한계를 모두 설명하면 설계 gate를 통과합니다. 실제 복구 gate는 원시 실행 증거가 있어야 합니다. [소스 지도](../source-reading.md)와 [평가](../assessment.md)의 운영 영역을 함께 검토합니다.
