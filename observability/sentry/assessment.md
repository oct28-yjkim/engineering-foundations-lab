# Sentry 평가: telemetry를 믿을 수 있는 범위까지 증명하기

[커리큘럼](curriculum.md) · [소스 지도](source-reading.md) · [실습 범위](labs/local-lab.md)

목표는 대시보드 화면을 만드는 것이 아니라 **무엇을 관찰했고 무엇을 놓칠 수 있는지 설명하는 엔지니어링 능력**입니다. 14개 모듈/28주 과정의 누적 실험 포트폴리오를 평가합니다. S14는 그중 한 경로를 묶는 **2주 mini-capstone**이며 전체 self-hosted 구축·모든 telemetry 종류·완전한 DR을 새로 구현하는 기간이 아닙니다.

## 1. 증거의 상태를 먼저 표시한다

**운영 필수 gate:** [운영 runbook](operations.md)의 실제 baseline 1개, 서로 다른 사건 2개, 사건별 최소 두 경쟁 가설과 지표·event·trace/원장 대조, 제한된 변경/원복, 회복 후 동일 관측을 제출합니다. SDK/CPU 모형 단위 검증은 원리 영역의 보조 증거이며 이 운영 gate를 충족하지 않습니다. 계정/환경/권한이 없으면 운영 미실행으로 남기고 설계·모형 완료와 분리합니다. 기존 점수/모듈 gate도 함께 적용합니다.

모든 제출물에 다음 상태 중 하나를 붙입니다. 문서를 읽고 예상 결과를 작성한 것은 실행 통과가 아닙니다. 저장소에는 학습 과제와 준비 안내가 있으며 완성 앱·운영 클러스터·테스트 성공 로그가 자동 제공되지 않습니다.

| 상태 | 필요한 증거 | 주장할 수 없는 것 |
| --- | --- | --- |
| 설계/읽기 | 계약, source permalink, 예상 oracle, 필요한 구성요소 | SDK 전송·server ingest·복구를 실제 검증했다는 주장 |
| 준비 | dependency/version/config, 격리 범위, 실행 전 검사 | 준비 완료만으로 기능·안전성 통과 |
| 실행 | command/시각/exit code, 원시 결과, 실패도 포함한 기록 | 종료 code나 화면 한 장만으로 정합성 통과 |
| 검증 | 독립 oracle, actual 대조, 반증 입력, 재현 절차와 한계 | 시험하지 않은 플랫폼·부하·실패 영역으로 일반화 |

실제 runtime 정보를 알 수 없는 hosted 서버에는 unknown을 허용합니다. 대신 SDK·API 계약·관측 시각·설정과 읽기 snapshot을 구별합니다. 권한·자원 부족으로 미실행인 실험은 정직하게 남기며 설계 평가를 받을 수 있지만 실행 필수 게이트를 대체하지 않습니다.

과제 범위는 `OFFLINE`(모형), `SDK-LAB`(학습자가 구현한 고정 SDK·메모리 transport/loopback 수신기), `PROJECT-LAB`(권한 있는 합성 시험 프로젝트), `SELF-HOST-DESIGN`(별도 운영 설계)으로 구분합니다. SDK-LAB의 200 응답은 Sentry server의 grouping/query 성공을 증명하지 않습니다. 아래 점수와 게이트는 **선언한 과제 범위**에 적용하고 다른 범위의 미실행 항목을 함께 공개합니다.

## 2. 공통 점수표: 25 × 4

총점 **80/100 이상**, **모든 영역 15/25 이상**, 아래 **필수 게이트 전부 통과**가 해당 범위의 검증 통과 조건입니다. 평균이 높아도 개인정보 유출이나 무근거 성공 판정을 상쇄하지 못합니다.

| 영역 | 배점 | 15점: 최소 충족 | 20점: 독립 재현 가능 | 25점: 전문가 수준 증거 |
| --- | --- | --- | --- | --- |
| 정확성 | 25 | event/issue/trace/span/release·capture/ingest/query의 경계를 구분 | ID·수량·시각·분모·단위를 oracle로 대조, unknown을 보존 | sampling·drop·중복·지연의 대안 설명을 분리하고 보장의 실패 조건까지 제시 |
| 메커니즘·소스 | 25 | 실제 버전/commit의 경로와 상태 변화 설명 | 2개 이상 구성요소의 protocol 경계와 관련 테스트 연결 | 버전/설정별 분기·mock 경계·반례를 추적하여 잘못된 인과 설명을 배제 |
| 실험·반증 | 25 | 작은 fixture·한 변인·예상/실제 결과 구별 | 독립 원장, 실패 주입, 반복 실행, 미확정 분류 | 음성 대조군·대안 가설·표본 편향/불확실성·관찰 제한 시간까지 설계 |
| 운영·재현성 | 25 | 명령·환경·실험 대상·원복/보존 범위를 기록 | bounded 실행·secret redaction·설정/데이터 지문·runbook 제공 | 실패 중 진단·중단 조건·안전한 재개와 복구 검산을 제3자가 반복 |

0점은 증거 없음 또는 조작된 결과, 1–14점은 중요한 경계 오류/재현 누락, 16–19점과 21–24점은 인접 기준의 부분 충족입니다. 코드량·스크린샷 수·모듈 이름 나열은 독립 점수가 아닙니다.

## 3. 점수와 별개인 필수 게이트

### G1 — 범위·권한·버전

실험 endpoint와 프로젝트, synthetic event 수, 최대 전송률·대기 시간·비용 한도, resource 소유자를 적습니다. hosted/self-hosted 실험은 학습자가 사용 권한을 가진 격리 대상에만 수행합니다. source SHA와 runtime SDK/image/config를 구분하고, 전체 stack을 설치하지 않았다면 그렇게 표시합니다. 운영 프로젝트의 alert·retention·quota·migration을 실험 목적으로 임의 변경하면 실패입니다.

### G2 — 독립 원장과 관찰 단계

SDK 호출 이전에 기대 event_id/fixture_id·업무 케이스·예상 drop 여부를 기록합니다. event_id를 SDK에서 생성한다면 입력 fixture ID와 연결합니다. capture 반환, transport 결과, Relay 수용, issue 생성, analytics 조회를 가능한 범위에서 따로 표기합니다. UI count 하나로 “전부 수집” 또는 “중복 없음”을 판정하면 실패입니다. 내부 단계가 보이지 않으면 unknown이며 관측한 단계의 합계를 전체 pipeline 합계로 부르지 않습니다.

### G3 — telemetry 의미와 sampling 분모

error event 수·issue 수·영향 사용자 수·trace/span 수는 서로 다른 지표입니다. sample rate·필터·quota·SDK drop·query time range를 기록하고 관측 비율의 분모를 명시합니다. 10% trace 표본의 관찰 건수를 무조건 10배하여 정확한 전체 장애 건수라고 주장하면 실패입니다. 고정 deterministic fixture의 exact oracle과 확률적 표본의 허용 범위/불확실성 검사를 구별합니다.

### G4 — 개인정보·비밀의 음성 검사

실제 고객 정보가 아닌 식별 가능한 가짜 canary 값으로 token/password/email/URL query/header/body의 전송·저장 경로를 시험합니다. SDK hook 한 곳에서 지웠다는 사실만으로 attachment/replay/log/span까지 안전하다고 하지 않습니다. 보고서에는 실제 auth token·session cookie·API secret·원본 개인정보를 넣지 않습니다. 노출이 확인되면 실험을 중단하고 해당 실습 credential 폐기/회전과 증거 접근 제한을 우선합니다.

### G5 — 실패 하나와 재현 가능한 재개

권한 있는 격리 환경에서 transport 실패·잘못된 release artifact·filter/drop·처리 지연 중 선택한 실패 하나를 재현합니다. 발생 시각, unknown/누락 분류, 진단 근거, 수정 후 새 run의 oracle을 제출합니다. 원인 불명 데이터를 삭제하거나 UI 수치를 맞추기 위한 임의 replay는 실패입니다. 불완전 입력을 조용히 무시하는 것으로 문제를 해결하지 않습니다.

### G6 — 소스와 테스트를 교차 검증

고정 source permalink 4개 이상, 서로 다른 구성요소의 관련 테스트 3개 이상, 실제 경계 설명을 제출합니다. 테스트를 읽기만 했다면 그렇게 표시합니다. 실제 앱의 작은 검산과 upstream 대형 test suite의 실행 여부는 별개입니다. source-only HEAD를 현재 SaaS 내부 구현이라고 단정하거나 테스트 mock을 실서비스 보장으로 확대하면 실패입니다.

## 4. 모듈별 통과 증거

| 모듈 | 최소 제출물 | 자동 탈락하는 잘못된 결론 |
| --- | --- | --- |
| S01 계약·시스템 경계 | actor/data-flow·환경 지문, 1,000 합성 요청 원장의 단계별 상태 분류 | DSN·프로젝트가 있으면 전체 pipeline 사용 권한도 있다고 가정 |
| S02 telemetry 의미 | 12종 fixture의 단위·식별자·분모 비교표 | issue 수를 오류 발생 횟수와 동일시 |
| S03 SDK·context | 100개 교차 요청의 context 격리, UTF-8 envelope와 hook/processor 전후 payload | 전역 user/context의 요청 간 혼입을 무시 |
| S04 ingestion·Relay | envelope/item·수용/거절·transport/ingest의 단계별 상태 | capture 반환이나 HTTP 응답만으로 최종 조회 성공 단정 |
| S05 grouping·symbolication | 알려진 오류 6계열·동일/상이 stack/fingerprint의 grouping oracle, 선택 플랫폼의 artifact 매칭 | artifact upload만 확인하고 symbolication이 맞다고 주장 |
| S06 release·regression | release/env/dist 또는 선택 artifact identity, 재현한 regression 조건 | release tag 문자열만으로 root cause 확정 |
| S07 tracing·OTel | parent/child/span link·context 전파와 단절 반례 | trace ID 공유가 모든 작업의 시간/순서를 보장 |
| S08 sampling·편향 | 원모집단 fixture, sampling/drop 조건, 기대값/허용 범위/관찰 편향 | sampled latency·오류율을 모집단의 정확한 값으로 제시 |
| S09 Kafka·Snuba·ClickHouse | 선택 이벤트 종류의 실제 배포 경로, commit/insert/query 가시성 구분 | Kafka ACK 또는 consumer lag 0을 최종 분석 정합성과 동일시 |
| S10 backlog·replay | event ID 원장, backlog 크기·drain rate·replay 중복/누락 검산 | offset reset으로 숫자만 맞추거나 backlog 0을 처리 성공으로 간주 |
| S11 privacy·security | canary 음성 검사, 최소 권한·redaction·credential 처리 표 | DSN과 관리 API token을 같은 권한으로 취급 |
| S12 self-host 운영·복구 | 버전/volume/service dependency, 데이터 종류별 backup/restore 계획과 실행 상태 | 설정 파일·DB 하나만 복구하고 모든 event/artifact 복구라고 주장 |
| S13 소스 연구 | 구현 4개·테스트 3개·경계 하나의 반증 노트 | moving main 링크만으로 버전 고정 연구 완료 |
| S14 mini-capstone | 아래 2주 범위의 앱/fixture·실패·oracle·handoff | 전체 platform 운영 적합성 인증으로 확대 |

S09/S10/S12의 실제 multi-service 실험을 수행하지 않았다면 해당 행은 설계 단계입니다. 다른 모듈 점수가 높다고 실행 완료로 바꾸지 않습니다. 다중 서비스 통합이 필요한 과제는 누적 포트폴리오나 별도 확장으로 수행하며 S14의 2주 범위에 몰아넣지 않습니다.

## 5. S14: 2주 bounded mini-capstone

범위는 **작은 합성 서비스 단면 하나·1,000개 합성 요청·두 실패 조건**입니다. 두 실패는 비동기 context 혼입과 category별 rate limit이며, 고정 SDK와 학습자가 구현한 메모리 transport/loopback 수신기에서 시험할 수 있습니다. 이는 실제 Sentry server의 grouping·조회·운영을 대체하지 않습니다. PROJECT-LAB을 추가하면 학습자가 승인한 격리 대상을 사용하고 외부 전송량·비용 한도를 별도로 정합니다.

| 기간 | 산출물·종료 조건 |
| --- | --- |
| 1–2일 | 대상·권한·정확 버전·이벤트 계약·개인정보 canary, 1,000개 synthetic 요청의 독립 원장 |
| 3–5일 | SDK/context와 baseline, 입력→transport 경계의 ID별 관측·unknown 기록 |
| 6–8일 | 비동기 context 혼입과 category rate limit의 두 반례, 수정/설정 대조 후 새 run |
| 9–10일 | source/테스트 교차 읽기, oracle 재실행, runbook·한계·미완료 목록 |

1,000개는 로컬 합성 요청 원장의 크기이지 외부 서비스에 모두 전송하라는 지시가 아닙니다. 실제 수집/필터/제한/unknown으로 분류하며, 전송 event 수와 요청 수를 구별합니다. sampling의 작은 fixture 관찰을 모집단 정확 추정으로 확대하지 않습니다. trace·logs·replay·profiling·모든 native symbolication을 동시에 넣지 않습니다.

필수 결과는 정상 run, 두 실패 조건의 run, 수정/설정 대조 후 run, privacy canary 결과, source boundary와 운영 handoff입니다. 전체 self-hosted 설치, multi-node HA, 대용량 부하, 모든 storage 복구는 제외 범위를 ADR에 적습니다. 전체 앱 통합은 별도의 [8주 보안·관측 앱 캡스톤](../../capstones/secure-observable-app.md)으로 이어지며, 기존 데이터 통합 캡스톤에 추가되는 필수 과정이 아니라 선택 경로입니다.

## 6. 재현 패키지와 구술 방어

패키지에는 run ID, fixture 생성 규칙과 checksum, SDK/runtime 지문, secret 제거 설정, source permalink, command/시각/exit code, expected/actual, 불일치 목록, 종료/원복 범위가 있어야 합니다. 실패한 run도 보존합니다. Sentry에서 export한 일부 결과만으로 원래 입력 원장을 대신하지 않습니다.

구술 평가에서는 다음 다섯 질문 중 세 개 이상에 증거를 가리키며 답합니다.

1. SDK가 event ID를 반환했는데 UI에 없다면 어떤 단계부터 어떤 관측으로 좁힐 것인가?
2. grouping이 바뀌었을 때 버그 증가와 grouping config 변경을 어떻게 구별할 것인가?
3. sampling/drop이 latency나 오류율 판단에 만드는 편향은 무엇이며 분모를 어디서 얻는가?
4. Kafka/Snuba backlog를 replay할 때 누락과 중복을 무엇으로 검산하는가?
5. backup 복원이 성공했다는 주장에 DB 외 artifact/object data와 설정·키의 어떤 증거가 추가로 필요한가?

최종 판정은 “28주를 읽었다”가 아니라 **선언한 범위에서 80점·영역별15점·필수 게이트를 충족했는가**입니다. 검증 범위와 아직 수행하지 않은 운영 실험을 나란히 적어 다음 단계의 학습 계획으로 남깁니다.
