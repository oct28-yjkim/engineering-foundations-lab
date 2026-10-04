# MCP 운영 실습: 요청이 어느 층에서 실패했는가

MCP는 모델 학습이 아니라 프로토콜·통합 경계입니다. 기본은 [실제 SDK stdio client/server](labs/README.md)를 실행하고 요청·오류·종료를 관측하는 경로입니다. GPU/모델 API 없이 가능합니다. 기준 **protocol 2026-07-28 / SDK 2.3.0**이며 다른 revision이나 SDK 지원을 자동 가정하지 않습니다.

<a id="basic-lab"></a>

## 기본 LAB: 정상 동작에서 장애 복구까지

**정상 기능 → 동작 원리 → 관측 → 제약 → 진단·복구** 순서의 입문 카드입니다. 실제 SDK의 목록·tool·resource 정상 요청부터 익히고 schema·오류 층·timeout·프로세스 수명을 관측합니다. [공통 LAB 계약](../../operations/lab-contract.md)에 따라 정상 결과를 먼저 검산한 뒤 아래 상세 절차로 진행합니다. 28주 심화는 선수 조건이 아니며, 이 카드 추가가 새 자동 실행기 제공이나 실제 장애 검증 완료를 뜻하지 않습니다.

| 단계 | 실행·관측·판정 |
| --- | --- |
| 정상 기능부터 | [실제 SDK 실습](labs/README.md)의 별도 venv에서 `--check` 후 `--run-local`을 실행합니다. 목록/schema→정상 tool A=7/B=0→resource→오류 뒤 정상 호출→child 종료를 기대표와 대조합니다. 모델/API 호출은 필요하지 않습니다. |
| 동작 원리 | client/server·transport·RPC envelope·tool 결과·업무 효과를 나눕니다. schema 거부와 handler 오류, 요청 완료와 process 종료가 다른 경계임을 설명한 뒤 정상 요청의 입력/출력 계약을 고정합니다. |
| 직접 볼 지표·방법 | 현재 runner의 기대값/오류 종류/종료 상태를 먼저 읽습니다. 요청별 monotonic latency·in-flight·timeout·retry/업무 key 원장은 아래 지침대로 별도 client wrapper/handler에 수동 계측합니다. stdout에는 protocol 외 로그를 쓰지 않습니다. |
| 먼저 확인할 제약 | 기본은 합성 child와 stdio이며 latency histogram/exporter·HTTP/auth server가 없습니다. logical metric 이름은 MCP 표준 지표가 아닙니다. 계측/지연 사건은 검토한 사본·최대 5요청·15초·외부 부작용 없음 범위를 지킵니다. |
| 자주 마주치는 사건 2개 | 기존 fixture의 잘못된 인자/schema 오류 뒤 정상 요청 회복을 먼저 봅니다. 아래 수동 timeout 카드에서는 bounded handler 지연과 client deadline을 비교해 단순 입력 오류와 지연/취소를 구분합니다. 지연 wrapper를 준비하지 않았다면 둘째 사건은 미실행입니다. |
| 조치와 회복 oracle | schema를 약화하지 않고 올바른 입력으로 복귀합니다. 지연 변경을 원복해 정상 A/B 결과·오류 입력 거부·child 정리와 timeout 후 잔존 작업/중복 효과를 검산합니다. timeout 증대나 무조건 retry가 복구는 아닙니다. |
| 제공물·추가 준비 | SDK stdio runner와 정확성 검사는 제공하고 계측·bounded delay는 수동 준비 과제입니다. HTTP 200/RPC/tool 오류 비교·OAuth·tenant/cache는 별도 transport/인가 환경 LAB입니다. LLM 논문 CPU 과정과 독립적입니다. |

두 사건의 결과가 예상과 다르면 관측한 상태를 기록하고 발생기/변경부터 멈춥니다. 정상 baseline·사건별 경쟁 가설·제한 조치·회복 oracle·미실행 범위를 [사건 보고서](../../operations/incident-report-template.md)에 남깁니다.

## 1. 실제 기준선

[별도 venv](environment.md)를 준비한 뒤 저장소 루트에서 다음을 실행합니다. 기존 앱에 등록된 MCP 서버나 조직 자산에는 연결하지 않습니다.

```text
./lab-workspaces/mcp-sdk-2.3.0/Scripts/python.exe -B ai/mcp/labs/sdk_lab.py --check
./lab-workspaces/mcp-sdk-2.3.0/Scripts/python.exe -B ai/mcp/labs/sdk_lab.py --run-local
```

POSIX는 같은 venv의 `bin/python`을 사용합니다. --check는 dependency 확인, --run-local은 소유한 합성 child와 실제 통신입니다. 정상 기대값·잘못된 인자·없는 resource·오류 후 정상 호출의 10개 검사를 [실습 표](labs/README.md)와 대조합니다. 이것은 시작 기준선이지 monitoring/HTTP/auth 전체 구현이 아닙니다.

기본 runner는 실패 예외 원문을 숨기며 **요청별 latency histogram/trace/exporter를 제공하지 않습니다**. 아래 계측은 검토한 전용 사본의 client wrapper/handler에 추가하는 과제입니다. child stdout에 print하여 protocol을 깨지 말고 stderr 또는 명시적으로 허가한 로컬 수집 경로를 사용합니다. [stdio 규칙](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)

## 2. 지표·로그의 최소 계약

아래 이름은 표준 MCP metric 이름이 아니라 **학습자가 정의할 논리 항목**입니다. exporter나 제품의 공식 metric처럼 인용하지 않습니다.

| 항목 | 수집 위치·정의 | 진단상의 주의 |
| --- | --- | --- |
| request count/rate | client 전송/응답, method·transport·revision·결과 분류; 구간 count/초 | RPC 요청 수와 business operation 수를 구분, request ID를 metric label로 쓰지 않음 |
| 오류 비율 | transport 오류, RPC error code, tool `isError`, schema 거부, 업무 실패 각각/명시한 요청 분모 | HTTP 200이나 RPC 응답 존재가 업무 성공은 아님 |
| 지연 | monotonic 전송→최종 결과, handler 시작→종료, queue wait; ms와 p50/p95/p99·표본 수 | 시간 초과·취소를 삭제하여 percentile을 좋게 만들지 않음 |
| in-flight/queue | client와 server의 현재 처리/대기 gauge | 같은 숫자라도 서로 다른 경계; 무한 queue 금지 |
| retry/중복 effect | attempt 수, 동일 업무 key의 commit/effect 수 | RPC ID 재사용만으로 exactly-once 보장 불가 |
| lifecycle | child exit code·기동 실패·정리 시간, timeout/cancel 이후 잔존 작업 | caller 취소가 handler rollback을 자동 의미하지 않음 |
| 권한·cache | 비민감 principal/tenant alias별 allow/deny, policy/catalog revision | token·prompt·tool 인자·resource URI 원문을 label/log에 넣지 않음 |

로그에는 run_id·비민감 request correlation·method·revision·오류 층·시각·bounded duration을 남깁니다. 민감 값은 단순 hash만 해도 재식별될 수 있으므로 합성 값 또는 alias를 사용합니다. transport/RPC/tool 오류 구분은 [기본 메시지 계약](https://modelcontextprotocol.io/specification/2026-07-28/basic)과 [tools 명세](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)를 확인합니다.

## 3. 증상별 진단

| 증상 | 경쟁 원인·확인 순서 | 조치·회복 기준 |
| --- | --- | --- |
| 서버 연결이 안 됨/즉시 종료 | interpreter/dependency → child argv/cwd → process 권한 → stderr의 비민감 오류 종류 → revision/transport | 같은 검토된 fixture로 환경 하나만 바로잡기. OS 보호 해제 금지. tools/list·정상 호출·종료까지 성공해야 회복 |
| tool call만 실패 | 목록/schema revision → 필수 인자/enum → RPC error vs tool result → handler 업무 조건 | 잘못된 입력 또는 stale catalog 수정; 잘못된 입력은 계속 거부되어야 함. 정상 A=7/B=0과 양쪽 대조 |
| HTTP 200인데 업무 실패 | 응답 JSON/SSE 형식 → RPC error envelope → `isError` → output schema → 업무 원장 | 성공률 분류기 수정, 재시도 전 부작용 상태 확인. HTTP 성공률만으로 경보 해제 금지 |
| timeout·중복 실행 | client deadline → queue/handler/downstream 지연 → retry attempt → business key/commit 경계 | 무조건 timeout 확대 대신 병목/중복 제어. 정상 지연과 effect 수·cancel 후 잔존 작업 함께 비교 |
| 401/403 또는 tenant 결과 혼입 | issuer/audience/scope·승인 → principal binding → cache key/context → 실제 정책 결정 | 토큰 우회나 권한 전체 허용 금지. A/B 허용·거부 matrix와 cache 교체 후 재검증 |

HTTP/SSE·proxy·OAuth 문제는 별도 격리 HTTP server와 issuer가 있어야 재현됩니다. stdio 성공을 HTTP 검증으로 기록하지 않습니다. [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)의 요구와 [호환성 지도](compatibility.md)를 함께 읽습니다. SDK가 unknown tool을 tool error로 표현한 기존 관측도 명세 일반 규칙과 구분합니다.

## 4. 실제 재현·회복 과제

1. **제공된 실제 SDK 호출:** 올바른 `widget-a`와 필수 인자 누락/enum 밖 값을 비교합니다. 실패한 계층·정상 structured content 부재·오류 후 정상 호출 결과를 적습니다. “어떤 예외라도 났다”를 통과 조건으로 삼지 않습니다. 기본 runner의 10검사 중 해당 비교는 이미 제공됩니다.
2. **추가 계측 과제:** 검토한 전용 사본에서 고정 합성 handler 하나에만 bounded delay를 넣고 client deadline을 더 짧게 설정합니다. 요청 5개 이하·총 15초 이하·외부 부작용 없음으로 제한합니다. 전송/handler/timeout/종료 시각과 in-flight를 기록한 후 delay를 제거해 동일 입력으로 회복을 확인합니다. 실제 control flow·deadline 변경 코드는 학습자가 작성하며 기본 runner가 자동 제공하지 않습니다.
3. 선택 신뢰 경계 과제는 A/B 합성 주체와 cache를 두고 정책 revision 변경 전후를 검증합니다. 현재 fixture는 OAuth/tenant cache를 구현하지 않으므로 별도 구현 없이 CPU predicate 결과를 운영 인증 증거로 제출하지 않습니다.

첫 과제는 schema 진단, 두 번째는 latency/lifecycle 진단입니다. 기존 모형 테스트와 합쳐 “2개 실제 운영 장애를 이미 검증했다”고 기록하지 않습니다. 원문 token/payload를 보존하는 debug exporter는 추가하지 않습니다.

## 5. 14모듈 관측 증거

MC01–02 process/revision/메시지 경계, MC03–04 schema/error·catalog/cache 변경, MC05–06 framing/latency/proxy, MC07–08 인증/인가 allow/deny, MC09–10 timeout/cancel/retry/effect, MC11–12 SDK trace·queue·lifecycle, MC13–14 호환성별 정상/실패/회복 표를 기본 산출물로 둡니다. 원리·명세·소스 추적은 각 관측의 원인을 설명하는 데 사용합니다.

[공통 운영 기준](../../operations/README.md)에 따라 실제 기준선·두 증상의 진단·회복 비교를 [보고서](../../operations/incident-report-template.md)에 제출합니다. 원리 모형만으로 운영 과정을 완료할 수 없습니다. 기존 [검증 기록](labs/validation.md)은 과거 CPU/mock/SDK 수행 범위이며 이 개편의 새 계측·지연 주입·HTTP 실험을 수행했다는 증거가 아닙니다.
