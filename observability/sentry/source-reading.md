# Sentry 소스 읽기: 구성요소별 계약과 증거

[커리큘럼](curriculum.md) · [평가 기준](assessment.md) · [실습 범위](labs/local-lab.md)

S13의 목표는 파일을 많이 읽는 것이 아니라 **관찰한 현상을 담당하는 코드·상태·테스트를 연결하고 반례를 만드는 것**입니다. Sentry 서버, SDK, Relay, Snuba, self-hosted 배포 저장소는 독립적으로 바뀝니다. 한 저장소의 버전으로 전체 제품의 구현을 설명하지 않습니다. 아래는 소스 읽기용 지도이며 완성 애플리케이션이나 self-hosted 설치 결과가 아닙니다.

## 1. 읽기 기준점과 실행 버전을 분리한다

2026-10-04 공식 저장소의 HEAD를 읽기 전용으로 조회하고 해당 commit의 실제 파일 목록을 확인했습니다. 아래 값은 **고정 source-only snapshot**입니다. 안정 릴리스 추천, 설치 버전, 서로 호환되는 배포 조합이라는 뜻이 아닙니다. 운영이나 실습 실행에는 각 구성요소의 실제 릴리스·이미지 digest·SDK lockfile을 별도로 기록합니다.

| 구성요소 | 고정 읽기 commit | 확인할 별도 실행 지문 |
| --- | --- | --- |
| Sentry application | [1db2b52455f11f0d86828c47d1c538e179695540](https://github.com/getsentry/sentry/tree/1db2b52455f11f0d86828c47d1c538e179695540) | 서버 image tag/digest, 기능 설정, grouping config |
| JavaScript SDK | [ec4931e61d7572ff08450944da84cd0a869cad14](https://github.com/getsentry/sentry-javascript/tree/ec4931e61d7572ff08450944da84cd0a869cad14) | 실제 사용 package·version·lockfile, framework integration |
| Relay | [c4e9930349068039dd6ecd06cf338c527ee90165](https://github.com/getsentry/relay/tree/c4e9930349068039dd6ecd06cf338c527ee90165) | image digest, relay mode, processing/PII/rate-limit 설정 |
| Snuba | [869ddcfb0e400e752bed798705faad9366750b22](https://github.com/getsentry/snuba/tree/869ddcfb0e400e752bed798705faad9366750b22) | image digest, consumer/storage/dataset 설정, migrations |
| self-hosted 배포 | [bcc168f5555f2a99dfc3f4b598887d24f67b7f3b](https://github.com/getsentry/self-hosted/tree/bcc168f5555f2a99dfc3f4b598887d24f67b7f3b) | 배포 tag/commit, rendered Compose의 image 목록, 외부 storage |

SaaS에서는 서버의 정확한 commit을 알 수 없을 수 있습니다. 그 경우 SDK·API 관측 시각·공개 계약을 기록하고 서버 구현은 **이 snapshot에서의 설명 가설**로 표시합니다. 모르는 runtime SHA를 읽기 SHA로 채우지 않습니다. self-hosted의 Compose가 참조하는 image들을 위 HEAD 다섯 개로 임의 교체하지 않습니다.

PowerShell/Bash에서 다음 명령은 원격 ref만 조회합니다. 오늘의 HEAD가 아래 지도와 달라도 자동 업그레이드하지 말고 차이를 기록합니다.

~~~text
git ls-remote https://github.com/getsentry/sentry.git HEAD
git ls-remote https://github.com/getsentry/sentry-javascript.git HEAD
git ls-remote https://github.com/getsentry/relay.git HEAD
git ls-remote https://github.com/getsentry/snuba.git HEAD
git ls-remote https://github.com/getsentry/self-hosted.git HEAD
~~~

이미 별도 디렉터리에 확보한 소스 checkout에서는 `git rev-parse HEAD`, `git status --short`, `git describe --tags --always`를 남깁니다. 태그가 붙어 있지 않은 개발 commit을 릴리스라고 부르지 않습니다. clone·dependency install·build는 자원·네트워크·스크립트 실행을 수반하는 별도 단계이며 이 교재 작성 중 실행하지 않았습니다.

## 2. 구현 지도: 하나의 이벤트를 경계별로 추적한다

아래 링크는 모두 위 commit에 고정되어 있습니다. 전체 코드를 암기하지 말고 각 행마다 **입력 타입 → 변경 상태 → 출력/실패 → 호출자**를 4칸으로 기록합니다. 저장소 사이 화살표는 protocol/config/queue로 연결되는 경계이지 한 프로세스의 함수 호출이 아닙니다.

| 모듈·경계 | 실제 구현 경로 | 읽으며 답할 질문 |
| --- | --- | --- |
| S03 SDK capture lifecycle | [core/client.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/src/client.ts) | capture 반환값, event 처리, transport 완료 중 무엇을 성공으로 보고 있는가? |
| S03 scope/context | [core/scope.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/src/scope.ts) | context가 언제 읽히고 복사·병합되는가? 동시 요청에 전역 scope를 쓰면 어떤 반례가 생기는가? |
| S03 processors·hooks | [prepareEvent.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/src/utils/prepareEvent.ts) | processor 순서와 null/drop, SDK별 beforeSend 경로를 어디서 구분하는가? |
| S04 envelope | [utils/envelope.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/src/utils/envelope.ts) | event와 envelope item의 단위가 다른 이유는 무엇인가? attachment도 같은 정책인가? |
| S04 transport·rate limit | [transports/base.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/src/transports/base.ts) | buffer 거절·network 오류·rate limit을 어떤 상태와 outcome으로 나누는가? |
| S03 browser integration | [browser/sdk.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/browser/src/sdk.ts) | core 공통 경로와 browser 전용 integration의 책임은 어디서 갈리는가? |
| S07 trace context | [dynamicSamplingContext.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/src/tracing/dynamicSamplingContext.ts) | trace identity와 sampling context가 언제 생성·전파되는가? |
| S08 SDK sampling | [tracing/sampling.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/src/tracing/sampling.ts) | parent decision·sampler·rate가 어떻게 결합되는가? 관찰된 trace의 모집단은 무엇인가? |
| S04 schema boundary | [Relay protocol/event.rs](https://github.com/getsentry/relay/blob/c4e9930349068039dd6ecd06cf338c527ee90165/relay-event-schema/src/protocol/event.rs) | SDK의 JSON과 Relay의 typed/annotated event 사이에 어떤 검증 경계가 있는가? |
| S04 error processing | [Relay errors/process.rs](https://github.com/getsentry/relay/blob/c4e9930349068039dd6ecd06cf338c527ee90165/relay-server/src/processing/errors/process.rs) | 정상화·필터·저장 경로에서 실패한 item의 운명은 무엇인가? |
| S08 processing filter | [Relay errors/filter.rs](https://github.com/getsentry/relay/blob/c4e9930349068039dd6ecd06cf338c527ee90165/relay-server/src/processing/errors/filter.rs) | filtering과 sampling을 같은 drop 이유로 합치면 어떤 지표가 틀리는가? |
| S08 sampling evaluation | [Relay sampling/evaluation.rs](https://github.com/getsentry/relay/blob/c4e9930349068039dd6ecd06cf338c527ee90165/relay-sampling/src/evaluation.rs) | rule matching과 sample decision을 재현하려면 어떤 설정·seed·context가 필요한가? |
| S04 admission limits | [Relay processing/limits.rs](https://github.com/getsentry/relay/blob/c4e9930349068039dd6ecd06cf338c527ee90165/relay-server/src/processing/limits.rs) | item category별 한도와 envelope 전체 거절을 어디서 구별하는가? |
| S05 grouping algorithm | [grouping/api.py](https://github.com/getsentry/sentry/blob/1db2b52455f11f0d86828c47d1c538e179695540/src/sentry/grouping/api.py) | event 입력·grouping config·variant가 hash 결과에 어떻게 관여하는가? |
| S05 grouping components | [grouping/component.py](https://github.com/getsentry/sentry/blob/1db2b52455f11f0d86828c47d1c538e179695540/src/sentry/grouping/component.py) | frame/message 일부가 grouping에 기여하는지 어떻게 표현하는가? |
| S05 fingerprint rules | [fingerprinting/rules.py](https://github.com/getsentry/sentry/blob/1db2b52455f11f0d86828c47d1c538e179695540/src/sentry/grouping/fingerprinting/rules.py) | 사용자 fingerprint와 기본 grouping을 섞는 계약은 무엇인가? |
| S05 ingest hash | [grouping/ingest/hashing.py](https://github.com/getsentry/sentry/blob/1db2b52455f11f0d86828c47d1c538e179695540/src/sentry/grouping/ingest/hashing.py) | hash 계산·캐시·group 선택을 한 함수의 보장으로 오해하지 않았는가? |
| S05/S06 event lifecycle | [event_manager.py](https://github.com/getsentry/sentry/blob/1db2b52455f11f0d86828c47d1c538e179695540/src/sentry/event_manager.py) | event 수용, issue의 발생 상태, release 관련 업데이트의 경계를 찾을 수 있는가? |
| S09 application ingest | [ingest/consumer/processors.py](https://github.com/getsentry/sentry/blob/1db2b52455f11f0d86828c47d1c538e179695540/src/sentry/ingest/consumer/processors.py) | consumer 입력·처리 결과·재시도 경로를 어떤 단위로 추적할 것인가? |
| S09/S10 queued store | [tasks/store.py](https://github.com/getsentry/sentry/blob/1db2b52455f11f0d86828c47d1c538e179695540/src/sentry/tasks/store.py) | queue 작업 완료와 UI query에서 보이는 완료는 같은 순간인가? |
| S09 analytics consumer | [Snuba consumers/consumer.py](https://github.com/getsentry/snuba/blob/869ddcfb0e400e752bed798705faad9366750b22/snuba/consumers/consumer.py) | 처리·commit·shutdown 경계는 어디이며 어떤 consumer 설정이 경로를 선택하는가? |
| S10 failed records | [Snuba consumers/dlq.py](https://github.com/getsentry/snuba/blob/869ddcfb0e400e752bed798705faad9366750b22/snuba/consumers/dlq.py) | DLQ는 누락을 없애는가, 격리하는가? replay 중 중복 기여는 누가 통제하는가? |
| S09 analytics query | [Snuba web/query.py](https://github.com/getsentry/snuba/blob/869ddcfb0e400e752bed798705faad9366750b22/snuba/web/query.py) | 논리 query와 실제 storage/query processor 선택을 어떻게 연결하는가? |
| S12 deployment graph | [self-hosted docker-compose.yml](https://github.com/getsentry/self-hosted/blob/bcc168f5555f2a99dfc3f4b598887d24f67b7f3b/docker-compose.yml) | 서비스별 image·volume·dependency·healthcheck·외부 endpoint를 분해할 수 있는가? |
| S12 schema lifecycle | [set-up-and-migrate-database.sh](https://github.com/getsentry/self-hosted/blob/bcc168f5555f2a99dfc3f4b598887d24f67b7f3b/install/set-up-and-migrate-database.sh) | 업그레이드 시 변경되는 상태와 rollback 전제는 무엇인가? **읽기 대상이며 실행 지시가 아니다.** |

S05 symbolication은 grouping과 별도 계약입니다. 이 지도만으로 모든 언어의 symbolicator·source-map uploader·debug artifact 서비스를 읽었다고 판정하지 않습니다. 선택한 언어/SDK에서 artifact ID·release/dist·debug ID의 실제 매칭 경로를 추가하고 해당 구성요소 commit을 새 행으로 기록해야 합니다. JavaScript SDK 경로를 Python/Java/native SDK 내부 구조로 일반화하지 않습니다.

## 3. 테스트를 명세 후보로 읽는다

각 테스트에서 arrange 입력, 설정, assertion, mock된 외부 경계를 분리합니다. 테스트 이름이 곧 SaaS 전체의 보장은 아닙니다. 아래 중 최소 3개를 서로 다른 구성요소에서 선택하고, assertion 하나를 깨는 입력을 설계합니다.

| 고정 테스트 경로 | 확인할 계약과 빠진 증거 |
| --- | --- |
| [SDK client.test.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/test/lib/client.test.ts) | event 처리·transport mock의 assertion. 실제 network 수용·UI 표시 검증과 구별 |
| [SDK scope.test.ts](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/test/lib/scope.test.ts) | scope 변경·병합·복제. framework 비동기 context 격리를 별도 검증 |
| [Relay localhost.rs의 inline tests](https://github.com/getsentry/relay/blob/c4e9930349068039dd6ecd06cf338c527ee90165/relay-filter/src/localhost.rs) | enabled filter, loopback/IP/domain/누락값의 분기. 모든 개인정보 필터의 증명은 아님 |
| [Sentry test_event_manager_grouping.py](https://github.com/getsentry/sentry/blob/1db2b52455f11f0d86828c47d1c538e179695540/tests/sentry/event_manager/test_event_manager_grouping.py) | issue/group 생성 조건과 설정 fixture. grouping version 변경 전후 비교 필요 |
| [Sentry test_fingerprinting.py](https://github.com/getsentry/sentry/blob/1db2b52455f11f0d86828c47d1c538e179695540/tests/sentry/grouping/test_fingerprinting.py) | fingerprint의 매칭/결합. 실제 배포의 프로젝트 설정은 따로 확인 |
| [Snuba test_dlq.py](https://github.com/getsentry/snuba/blob/869ddcfb0e400e752bed798705faad9366750b22/tests/consumers/test_dlq.py) | 실패 record 처리 경계. 전체 replay 결과의 exact oracle은 별도 |

## 4. 실행 후보와 자원·변경 범위

아래는 고정 manifest에서 확인한 테스트 entry point이며 **본 저장소에서 실행 검증한 결과가 아니다**. 별도 source checkout, 해당 lockfile/toolchain, 테스트 전용 환경을 먼저 준비합니다. Windows 호스트에서 그대로 실행된다고 보장하지 않으며 Linux/WSL/container 개발 환경은 학습자가 승인한 범위에서 별도로 준비합니다.

| 작업 디렉터리 | 제한된 실행 후보 | 근거·주의 |
| --- | --- | --- |
| sentry-javascript root | `yarn workspace @sentry/core test test/lib/scope.test.ts` | [core package.json](https://github.com/getsentry/sentry-javascript/blob/ec4931e61d7572ff08450944da84cd0a869cad14/packages/core/package.json)의 test=vitest run. workspace dependency/build 준비 필요 |
| Relay root | `cargo test -p relay-filter localhost` | [crate manifest](https://github.com/getsentry/relay/blob/c4e9930349068039dd6ecd06cf338c527ee90165/relay-filter/Cargo.toml), 위 inline tests. Rust/native dependency·빌드 자원 필요 |
| Snuba root | `SNUBA_SETTINGS=test pytest -vv tests/consumers/test_dlq.py` | **Bash 문법**. [Makefile](https://github.com/getsentry/snuba/blob/869ddcfb0e400e752bed798705faad9366750b22/Makefile)의 test 설정에서 범위 축소. fixtures와 ClickHouse/Kafka 등 필요 서비스 확인 전 실행 금지 |

전체 `make test`, install/upgrade 스크립트, integration orchestration을 무심코 실행하지 않습니다. repository의 target은 volume 제거·migration·서비스 재시작 같은 부작용을 포함할 수 있습니다. test DB·queue·topic·Compose project의 격리와 종료/보존 정책을 읽고 승인한 뒤 실행합니다. 실제 결과에는 command, cwd, SHA, exit code, assertion 수, duration, fixture 범위와 미실행 이유를 함께 기록합니다.

## 5. S13 제출: 한 경계에 집중한 연구 노트

1. S03/S04/S05/S08/S09/S10 중 하나의 주장과 반증 조건을 고릅니다. 예: “capture 반환값이 있으면 analytics query에도 반드시 즉시 한 번 보인다.”
2. 작은 합성 event 집합의 ID·expected outcome을 SDK 이전 원장에 고정합니다. 단계별 관측 여부와 drop/unknown을 구분합니다.
3. 서로 다른 두 구성요소의 최소 4개 구현 경로와 관련 테스트 3개를 읽고 실제 호출/메시지 경계를 그립니다. 앞 표의 25개 파일을 전부 실행했다는 주장은 필요하지 않습니다.
4. 한 변인만 바꾼 counterexample을 실행하거나 실행 불가 시 구체 fixture·예상 assertion·필요 서비스까지 설계합니다. 설계만 한 것은 BUILD/실행 통과가 아닙니다.
5. 관측 결과가 구현 설명과 어긋나면 source/runtime 버전 차이, 설정, 비동기 처리, sampling, query 지연 순으로 가설을 분리합니다. count를 맞추려고 ID를 제거하거나 재전송 증거를 지우지 않습니다.

완성물은 source permalink, protocol boundary, 테스트 assertion, 합성 원장, 실제/예상 결과 구분, 미검증 범위를 포함합니다. S14의 2주 mini-capstone에서는 이 중 하나의 얇은 경로만 사용하며 전체 self-hosted 운영 적합성 인증으로 확대하지 않습니다.
