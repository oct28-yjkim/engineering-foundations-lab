# Sentry 운영 실습: 애플리케이션 장애와 관측 누락을 분리하기

[시작](README.md) · [커리큘럼](curriculum.md) · [운영 공통 규약](../../operations/README.md) · [사고 보고서](../../operations/incident-report-template.md)

이 트랙의 기본 실습은 **실제 프로젝트의 읽기 전용 baseline → 증상 → 경쟁 가설 → 지표/이벤트/trace 대조 → 제한된 개선 → 회복 검증**입니다. 샘플링 oracle은 분모와 편향을 이해하는 선택 보조 자료입니다. UI 조작이나 모형 PASS만으로 운영 역량을 판정하지 않습니다. 이 문서는 실행 절차이며 실제 장애를 발생시키거나 계정·프로젝트를 생성한 기록이 아닙니다.

<a id="basic-lab"></a>

## 기본 LAB: 정상 동작에서 장애 복구까지

**정상 기능 → 동작 원리 → 관측 → 제약 → 진단·복구** 순서의 입문 카드입니다. 합성 요청·오류 하나가 SDK에서 화면까지 도착하는 정상 흐름을 먼저 확인하고 수집 누락과 실제 앱 결함을 나눕니다. [공통 LAB 계약](../../operations/lab-contract.md)에 따라 정상 결과를 먼저 검산한 뒤 아래 상세 절차로 진행합니다. 28주 심화는 선수 조건이 아니며, 이 카드 추가가 새 자동 실행기 제공이나 실제 장애 검증 완료를 뜻하지 않습니다.

| 단계 | 실행·관측·판정 |
| --- | --- |
| 정상 기능부터 | [준비 지침](labs/local-lab.md)에 따라 자기 시험 앱·허가된 프로젝트·합성 marker를 준비합니다. 정상 요청과 의도된 오류 요청의 독립 원장을 만들고 SDK capture→수집→Issues 가시성을 대조합니다. trace 계측이 준비됐다면 같은 요청의 parent/child 연결도 봅니다. |
| 동작 원리 | 요청 실패·error event·issue grouping·span을 구분하고 SDK sampling/filtering→ingestion outcome→조회 지연 순서를 설명합니다. issue 수가 줄었다고 업무 오류가 줄었다고 판단하지 않습니다. |
| 직접 볼 지표·방법 | §2의 Issues, Explore/Traces, Stats를 같은 project/environment/release·UTC 창으로 비교합니다. 업무 실패/전체 요청, span 종류가 같은 p50/p95·표본 수, accepted/filtered/rate-limited/invalid/client discard와 reason을 기록합니다. |
| 먼저 확인할 제약 | 완성 SDK 앱·전체 self-hosted stack은 미제공입니다. 외부 telemetry·비용·시험 알림 수신자를 먼저 확인하며 합성 요청 최대 100개·동시 1·1req/s 이하·5분을 지킵니다. 송신 허가가 없으면 tabletop/무외부송신 준비만 진행합니다. |
| 자주 마주치는 사건 2개 | §4 A: 시험 route의 특정 합성 입력에만 예외를 만듭니다. §4 B: `beforeSend`로 marker가 있는 error만 제외해 앱 오류는 있는데 관측은 줄어드는 상태를 봅니다. trace/Replay까지 같은 hook으로 제외된다고 가정하지 않습니다. |
| 조치와 회복 oracle | 문제 route와 hook revision을 각각 원복합니다. 독립 요청 원장의 업무 결과, 새 marker의 의도한 수집/제외, 중복 event 여부, 가시화 시간을 다시 검산합니다. quota 증액·PII 활성화·sampling 100%를 진단 대신 사용하지 않습니다. |
| 제공물·추가 준비 | 준비 자료·원리 보조 모형·아래 수동 카드만 제공하며 실제 SDK 앱/프로젝트가 필요합니다. 준비·관측·장애 실행 상태를 따로 기록합니다. self-hosted queue/storage 장애는 해당 stack이 있는 후속 LAB입니다. |

두 사건의 결과가 예상과 다르면 관측한 상태를 기록하고 발생기/변경부터 멈춥니다. 정상 baseline·사건별 경쟁 가설·제한 조치·회복 oracle·미실행 범위를 [사건 보고서](../../operations/incident-report-template.md)에 남깁니다.

## 1. 대상과 권한부터 확인

사용 권한을 가진 기존 학습 프로젝트 하나를 선택합니다. SaaS/self-hosted, organization/project의 별칭, SDK/runtime 버전, release/environment, 조회 가능한 기간, sampling/filter 설정, quota 범위와 확인 시각을 기록합니다. 처음에는 프로젝트 이벤트·Stats·trace 조회 권한만 사용합니다. 접근이 거절되면 필요한 권한을 운영자에게 확인하며 소유자 토큰 발급이나 개인정보 수집 활성화로 우회하지 않습니다.

프로젝트가 없다면 [로컬 준비](labs/local-lab.md)로 환경 요구사항을 작성하고 상태를 `환경 미준비`로 둡니다. SaaS 구매나 self-hosted 전체 설치를 필수 시작 명령으로 만들지 않습니다. 기존 운영 프로젝트를 실습 대상으로 변경하지 않습니다. 데이터 열람 자체에도 개인정보 권한이 필요합니다. 원시 event·breadcrumb·request body·source map·Replay를 보고서에 복사하지 말고 합성 request ID, 집계값, 비밀 제거 stack frame만 사용합니다.

## 2. 첫 30분: 동일 구간을 세 화면으로 보기

다음은 로그인된 UI에서 수행하는 **읽기 전용 관찰**입니다. UI 명칭이 다른 배포는 같은 기능의 화면과 실제 query를 기록합니다. 시간은 UTC로 고정하고 정상 15분 구간과 증상 15분 구간의 project/environment/release를 일치시킵니다. 트래픽이 적으면 창을 늘리고 표본 수를 공개합니다.

1. **Issues**: project와 environment를 선택하고 해당 release를 필터링합니다. 오류 한 종류를 열어 first/last seen, event 수, 영향을 받은 사용자 범위, stack frame, release·Debug ID를 확인합니다. issue 개수와 error event 개수를 별도 칸에 둡니다.
2. **Explore → Traces**: 같은 범위에서 대상 서버 요청의 root/server span 종류를 먼저 고릅니다. 집계 필드 `count()`, `p50(span.duration)`, `p95(span.duration)`을 확인하고 route/operation별로 비교합니다. 하위 DB span 전체를 섞은 p95를 HTTP 요청 p95라고 부르지 않습니다. 한 느린 trace에서 parent-child 관계와 DB·외부 API·앱 처리 구간을 읽습니다. [공식 Explore 집계 필드](https://cli.sentry.dev/commands/explore/)
3. **Stats**: 동일 project/기간과 데이터 category를 선택하여 Accepted, Filtered, Rate Limited, Invalid, Client Discard 및 reason을 확인합니다. SDK가 보고하지 못한 유실도 있으므로 이 합계가 앱의 모든 요청과 같다고 가정하지 않습니다. [Stats 정의](https://docs.sentry.io/product/stats/)

API 조회의 rate-limit 헤더와 SDK ingestion의 제한/폐기를 혼동하지 않습니다. UI/API를 빠르게 반복 조회하지 않고 위 세 관측을 한 번 확보한 뒤 원인별로 범위를 좁힙니다. [조회 API의 rate limit](https://docs.sentry.io/api/ratelimits/)

| 관측값 | 종류·단위·창 | 해석과 대조 자료 |
| --- | --- | --- |
| 업무 요청 오류율 | 같은 5분 창의 실패 요청 수 / 전체 대상 요청 수 × 100, % | ingress/앱의 독립 request 원장 사용. 한 요청의 여러 error event나 issue 수를 분자로 쓰지 않음 |
| 오류 event·영향 사용자 | 구간 count, 건·관측 사용자 수 | release별 변화 탐지용. sampling·동의·PII 설정에 따라 사용자 집계가 달라짐 |
| 요청 지연 p50/p95 | 동일 route·span 집합의 구간 quantile, UI 단위 확인 후 ms로 통일 | 표본 수·sampling 조건과 함께 보고. 서로 다른 서버의 p95 평균 금지; 앱 독립 histogram과 비교 |
| ingestion outcomes | category/reason별 구간 count, 건; 비교 비율의 분모 명시 | accepted 감소만으로 앱 오류 감소를 결론 내리지 않음. 필터·할당량·client discard 확인 |
| freshness | 합성 event 발생→조회 가능 elapsed, 초 | 시계 차이와 polling 간격을 함께 기록. SDK capture 반환 시간과 구분 |
| self-hosted 플랫폼 | 서비스 상태, backlog/lag, 저장소 여유 bytes·I/O 지연 | 앱 오류율과 별도 대시보드. SaaS 내부 Kafka/ClickHouse 상태를 추측하지 않음 |

이 표의 5/15분은 학습 창이지 보편적인 경보 임계치가 아닙니다. 경보는 업무 SLO·평소 부하·최소 표본과 연결합니다. 비율 분모가 0이면 0%가 아니라 `표본 없음`입니다.

## 3. 증상별 진단·완화·회복

| 증상 | 경쟁 가설 | 먼저 확보할 증거 | 제한된 조치와 되돌림 | 회복 기준 |
| --- | --- | --- | --- | --- |
| 배포 뒤 오류율 급증 | 실제 결함 / SDK 중복 계측 / grouping·sampling 변화 | 업무 실패율과 event 수 차이, release별 stack, 동일 request ID 중복, 설정 diff | 시험 앱의 문제 release 또는 계측 변경 하나만 이전 revision으로 되돌림; 배포 rollback의 schema 호환성 확인 | 동일 요청 원장의 실패 감소, 중복 event 제거, 정상·음성 요청 모두 설명 |
| 앱은 실패하는데 issue가 줄거나 없음 | SDK 미활성·필터 / quota·client discard / 수집 또는 조회 지연 / 잘못된 environment | 합성 원장→SDK transport→Stats outcome→검색 시각, category와 기간 일치 | 원인 확인된 시험 앱 설정만 수정; quota 증액·PII 활성화·무조건 sampling 100%는 진단으로 사용하지 않음; 원래 설정 지문 복구 | 합성 ID가 의도대로 수집/제외되고 정한 관찰 시간 내 가시화; 미확인 유실은 남김 |
| p95 급증, error는 안정 | DB/외부 의존 지연 / async 문맥 단절 / 트래픽 구성 또는 sampling 편향 | route별 요청 수·p50/p95, 느린 trace와 독립 latency, 단절된 parent, release diff | 시험 의존성의 제한된 지연 설정 또는 계측 revision을 하나씩 원복; timeout 증가는 별도 설계 | 같은 workload·sampling에서 latency baseline 복귀, trace 연결 정상, 오류율 악화 없음 |
| self-hosted ingest는 응답하지만 조회가 늦음 | 소비 backlog / 저장소·쿼리 지연 / UI 시간·filter 오류 | 해당 revision의 ingest→consumer→Snuba/저장소→query 신호, 독립 event ID | 운영자의 승인된 구성 변경만 적용; offset reset·데이터 삭제·전체 재시작 금지 | backlog와 freshness 동시 회복, 입력 ID별 누락/중복 대조; health green 하나로 완료하지 않음 |

self-hosted를 이미 운영하는 학습 환경에 한해서 정확한 배포 폴더에서 `docker compose ps`와 `docker compose config --services`로 실제 서비스 이름을 확인합니다. 그 이름을 확인한 후에만 `docker compose logs --since 5m --tail 100 <확인한-service>`로 제한 조회합니다. 로그에는 개인정보가 있을 수 있으므로 원문을 제출하지 않습니다. `config` 전체 출력은 secret을 노출할 수 있어 사용하지 않습니다. 서비스·consumer 명칭은 버전별로 달라지며 본 저장소가 전체 Sentry stack을 제공하는 것은 아닙니다. [공식 self-hosted 구성](https://develop.sentry.dev/self-hosted/)

## 4. 안전한 재현과 운영 gate

실패 주입은 자기 소유의 격리 시험 앱에서만 수동 수행합니다. 합성 요청 최대 100개·동시성 1·1req/s 이하·총 5분 이하를 학습 상한으로 정하고, 메일/메신저/온콜 알림이 외부 수신자에게 가지 않도록 기존 시험 라우팅을 먼저 확인합니다. 비용/전송 허가가 없으면 네트워크 송신을 하지 않고 tabletop으로 표시합니다.

- **사건 A, 실제 앱 결함**: 시험 route 하나의 고정 합성 입력에만 예외를 발생시킵니다. 독립 요청 분모·event·issue·release를 대조하고 해당 변경을 원복합니다.
- **사건 B, 관측 누락**: 시험 SDK의 `beforeSend`에서 합성 marker가 있는 error만 제외합니다. 입력 원장과 accepted/의도적 제외를 대조합니다. 이것이 trace·Replay 등 모든 신호를 필터링한다는 뜻은 아닙니다. 원래 hook revision을 복구하고 새 marker가 보이는지 확인합니다. [Node SDK 필터링](https://docs.sentry.io/platforms/javascript/guides/node/configuration/filtering/)
- 예상 밖 실제 사용자 데이터·수신자 알림·429·서비스 영향이 생기면 즉시 **발생기부터 중단**합니다. 비용 한도나 개인정보 설정을 넓혀 계속하지 않습니다. 이미 송신한 데이터의 삭제·보존은 관리자의 별도 절차를 따릅니다.

통과 증거는 정상 baseline, 두 사건의 서로 다른 경쟁 가설, 지표·원장·trace/로그의 상관관계, 변경 diff·원복, 회복 후 동일 관측, 남은 불확실성입니다. 모형 테스트는 이 gate를 대체하지 않습니다. S01–02에서 분모/baseline, S03–08에서 사건 A/B와 trace, S09–12에서 platform health와 회복, S13–14에서 source 근거·보고서를 통합합니다. 28주·14모듈은 유지합니다.
