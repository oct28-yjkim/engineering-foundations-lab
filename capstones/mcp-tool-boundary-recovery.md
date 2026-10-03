# MCP 도구 경계·권한·장애 연구 — 선택 8주

[MCP 트랙](../ai/mcp/README.md) · [호환성](../ai/mcp/compatibility.md) · [LLM 실험](../ai/llm-paper-lab/README.md) · [비밀·신원](../security/README.md)

기본 28주 과정의 2주 미니 연구 이후 선택하는 **추가 8주·96시간**입니다. LLM/API 없이 deterministic client로 protocol·업무 계약부터 검증합니다. 모델 도구 선택 실험은 별도 예산·데이터·승인을 갖춘 선택 확장입니다.

## 질문과 대상

“서로 다른 principal이 같은 MCP 연결/endpoint를 이용해도 권한·cache·요청 결과가 섞이지 않고, timeout·재시도·schema 변경 뒤에도 업무 불변식을 지킬 수 있는가?”

공개 합성 주문 A/B를 읽는 tool과 **전용 disposable ledger**의 상태를 바꾸는 tool 하나를 설계합니다. 기본 SDK fixture는 read-only이며 이 확장 서버·HTTP issuer·proxy·DB를 자동 제공하지 않습니다. 실제 주문·결제·운영 DB·현재 앱의 MCP 설정은 건드리지 않습니다.

## 8주 산출물

| 주 | 실험 | 독립 oracle |
| --- | --- | --- |
| 1 | 위협 모델·host/client/server/backend·신뢰된 principal·승인 UI 계약 | principal×tenant×tool×argument 권한표, prompt/annotation을 권한으로 사용하지 않음 |
| 2 | 명시 revision·도구 schema·결과/error·resource/prompt | 잘못된 version/metadata/args·unknown name·오염된 tool 결과를 각각 분류 |
| 3 | auth issuer/resource/audience·scope·egress와 metadata fetch | 잘못된 issuer/audience·타 tenant·redirect·metadata URL 거부, token passthrough 없음 |
| 4 | principal/authorization context/policy/catalog별 cache·opaque cursor·권한 회수 | A→B 및 같은 principal의 다른 token context 간 private cache 오염 없음, stale catalog 갱신 |
| 5 | 명시 업무 idempotency key·timeout·cancel·재시도 | timeout 직전 commit과 직후 commit의 원장 비교, RPC ID와 업무 key 분리 |
| 6 | modern HTTP proxy·header/body·SSE 종료·MRTR 선택 | 잘못된 header는 handler 실행 전 거부, 새 ID 재발행, 추가 입력의 승인/거부/예산 |
| 7 | 교차 SDK/host 및 classic-modern migration | protocol/SDK/extension별 matrix, 무조건 fallback 금지, 기능 축소/미지원 명시 |
| 8 | 관측·소스 trace·회귀·운영 계획 | 비밀 없는 trace, 최소 반례, budget·stop 조건·rollback 절차·미검증 범위 |

## 반드시 분리할 네 가지

1. **발견과 허가:** tool이 목록에 있거나 `readOnlyHint`가 true인 것과 그 사용자가 실행해도 되는 것은 다릅니다. 실제 backend 접근에서 재인가합니다.
2. **응답과 업무 결과:** JSON-RPC 성공, `isError`, SDK exception, 실제 ledger commit은 다른 상태입니다. 연결 종료만으로 변경 미발생을 확정하지 않습니다.
3. **연결과 신원:** process/socket/connection·`clientInfo`·요청 속 tenant 문자열은 인증된 principal이 아닙니다. 연결 재사용과 workload state는 explicit identifier/권한으로 관리합니다.
4. **프로토콜과 모델 판단:** 모든 MCP 요청이 유효해도 모델이 잘못된 도구/인자를 고를 수 있습니다. tool-selection accuracy·업무 성공·무권한 실행·불필요 호출·비용을 별도 측정합니다.

## 핵심 실패 시간표

- `검증된 A 요청 → private 결과 cache → 같은 arguments의 B 요청 → 같은 A의 token/authorization context 변경 → 권한 변경 → cache lookup`: 신뢰된 principal·authorization context·정책 revision과 TTL 각각을 제거한 대조군을 합성 값으로 비교합니다. raw token을 cache key/로그에 쓰지 않습니다.
- `업무 key K로 요청 ID 10 → backend commit → 응답 유실 → 새 요청 ID 11 + 같은 K → reconciliation`: exactly-once를 주장하지 말고 transaction·dedupe retention·payload mismatch·재조회 조건을 명시합니다.
- `catalog v1 발견 → schema v2 배포 → header/body 불일치 → 실패 → 목록 재조회 → 제한된 재시도`: 잘못된 routing 상태에서 업무 handler가 실행되지 않는지 카운터로 검산합니다.
- `input_required → user decline/cancel 또는 budget 초과 → 종료`: MRTR retry를 새 승인 없는 권한 확대나 무한 루프로 만들지 않습니다. `requestState`를 민감 데이터/권한 증거로 무조건 신뢰하지 않습니다.

## 안전·완료 gate

원리/명세 25 + 구현/소스 25 + 독립 oracle/반증 25 + 운영/재현성 25, 총 80점 이상·각 15점 이상을 요구합니다. 아래 gate는 점수로 상쇄하지 않습니다.

- 합성 A/B의 허용과 거부를 모두 시험하며 실제 issuer/audience 검증 없이 “auth 완료”로 표시하지 않는다.
- secret·refresh token·JWT·무인가 사용자 데이터는 Git/telemetry/LLM context에 넣지 않는다. 사용자 prompt·tool 결과는 선택 모델 실험에서 사용자가 허가한 최소화된 합성 입력만 전달하며, 원문을 Git/telemetry에 자동 기록하지 않는다. secret manager는 trusted execution에서만 사용한다.
- timeout 이후 unknown outcome을 기록하고 승인 범위 안에서 재조회/재조정한다. 취소를 rollback이나 RPC ID를 idempotency key로 가정하지 않는다.
- negative case의 다른 이유로 실패한 것을 성공 oracle로 세지 않는다. HTTP status·RPC error·tool error·SDK surface·업무 상태를 별도 기록한다.
- stdio·CPU·mock·같은 SDK 양끝 PASS를 HTTP 보안·교차 구현·공식 conformance PASS로 확대하지 않는다.
- cloud/API 호출·remote deploy·현재 앱 설정 변경은 이 캡스톤의 자동 동작이 아니다. 별도 사용자가 허가한 환경만 사용한다.

[공통 실험 방법](../databases/shared/experiment-method.md)에 따라 가설·독립 정답·정확한 revision·입력·시간선·실제 관측·경쟁 설명·회귀·남은 위험을 제출합니다. 운영 적용 권고는 통과한 범위까지만 작성합니다.
