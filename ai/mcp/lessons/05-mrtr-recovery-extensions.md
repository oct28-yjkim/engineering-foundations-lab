# 05. MRTR·elicitation·취소·재시도·extensions

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="mc09"></a>
## MC09: 추가 입력을 요구하는 결과와 재시도

선수 조건: MC02, MC07–08. 현대 MCP는 server가 별도의 JSON-RPC request를 client로 보내는 대신 `input_required` 결과와 재시도를 사용합니다. `inputRequests`에 대응한 `inputResponses`, 필요 시 opaque `requestState`를 다음 요청에 넣으며 RPC ID는 새로 발급합니다. 대상은 `tools/call`, `resources/read`, `prompts/get`입니다. [공식 MRTR](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)

여기서 재시도는 네트워크 장애 때문에 같은 작업을 무작정 다시 실행하는 것과 다릅니다. 추가 입력을 받은 새로운 protocol attempt이고, 업무 operation의 부작용 시점은 별도로 설계해야 합니다. 승인 전 부분 실행을 허용하면 무엇을 되돌릴 수 있는지 명시해야 합니다.

### 실험

1. 합성 예약에서 배송 방법이 부족하면 입력을 요청하는 원장을 작성합니다. `accept`, `decline`, `cancel`, 응답 없음의 기대 업무 효과를 각각 정합니다.
2. capability가 없는 client에 지원하지 않는 입력 요청을 보내는 대조군을 만듭니다. client capability는 그 기능을 다룰 수 있다는 선언이지 모든 데이터를 공유한다는 동의가 아닙니다.
3. client는 `requestState`를 해석하거나 수정하지 않고 되돌립니다. server는 공격자가 변경할 수 있는 입력으로 보고 검증합니다. 서명/HMAC 또는 AEAD를 직접 구현하지 말고 검증된 라이브러리의 사용 설계를 검토합니다.
4. 다른 principal, 만료된 state, 다른 tool 인자, 한 번 사용한 state의 재사용을 각각 실패 모델로 만듭니다. 무결성 보호만으로 single-use가 보장되는 것은 아니므로 업무 원장을 별도로 확인합니다.
5. 동시 요청 둘의 input ID나 state가 섞이지 않는지 시험합니다. additional input이 오지 않아도 queue·메모리·유효 기간이 무한히 늘어나지 않게 상한을 둡니다.

elicitation의 form은 API key·암호·access token을 수집하는 입력 창이 아닙니다. 민감 상호작용은 URL mode의 별도 경로로 분리하고, 실제 target domain과 사용자 동의를 확인합니다. 기본 실습은 비밀이 없는 form 또는 고정 응답 fixture만 사용합니다. [공식 elicitation](https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation)

Roots·Sampling·Logging은 이 기준 revision에서 Deprecated입니다. 과거 sampling 요청과 현행 MRTR 관계를 읽되 새 기본 구현에 의존성을 추가하지 않습니다. 모델 API 선택 확장이 필요하면 비용·개인정보·승인·호출 상한을 별도 문서화하고 CPU 검증을 대체하지 않습니다. [기능 변경·deprecated 목록](https://modelcontextprotocol.io/specification/2026-07-28/changelog)

제출물: input/consent/state timeline, 재시도별 RPC ID와 업무 key, 거절 후 side effect 0건 검산, invalid-state negative case, 모델 없이 재현 가능한 최소 fixture.

<a id="mc10"></a>
## MC10: cancellation·deadline·idempotency·확장 계약

core의 취소 신호는 stdio의 notification과 HTTP response stream 종료로 구분됩니다. 취소를 수신해도 이미 완료한 외부 효과를 되돌렸다는 뜻은 아닙니다. protocol 응답 중단과 업무 보상 작업의 완료를 분리합니다. [공식 cancellation](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/cancellation)

### 실험

1. [CPU `request-ledger`](../labs/README.md)에서 성공 직전·업무 commit 직후·응답 전달 직후를 분리합니다. 모형의 ledger는 crash durability가 없는 제한된 추상화입니다.
2. 하나의 업무 key로 같은 payload와 다른 payload를 보내고 기대 결과를 기록합니다. RPC ID만 새로 바뀌어도 같은 업무가 중복될 수 있음을 보여 줍니다.
3. deadline 전에 시작했지만 뒤에 끝난 작업, client가 취소했으나 backend가 완료한 작업의 outcome을 `unknown` 또는 검산된 결과로 기록합니다. timeout을 곧바로 실패로 확정하지 않습니다.
4. 동시 retry 두 개가 모두 “처음 본 key”라고 판단하는 race를 설계합니다. durable unique constraint·transaction·outbox 등 실제 backing store의 원자성 없이 exactly-once를 주장하지 않습니다.
5. retry 횟수·전체 시간 budget·backoff·jitter·in-flight 상한을 정합니다. 인증 재시도, header mismatch 후 schema 갱신, 업무 retry는 원인이 다르므로 별도 counters로 냅니다.

Tasks는 core의 필수 기능이 아니라 `io.modelcontextprotocol/tasks` 선택 extension입니다. 지원을 선언한 양쪽에서만 task 결과를 사용하며 `tasks/get` polling과 `tasks/update` 입력, cooperative cancellation을 별도 검증합니다. 과거 core 실험 기능의 `tasks/result` 예제를 현재 extension에 그대로 적용하지 않습니다. [공식 Tasks](https://modelcontextprotocol.io/extensions/tasks/overview)

추가 과제는 Tasks·MCP Apps·인증 확장 중 **하나만** 선정합니다. extension 식별자, revision, SDK/host 지원, opt-in, fallback, 결과 형태를 표로 남깁니다. 공식 extension이라는 표기 자체가 모든 SDK나 client의 구현을 뜻하지 않습니다. [Extensions](https://modelcontextprotocol.io/extensions/overview)

제출물: wire attempt와 business operation의 이중 원장, uncertainty 분류, 보상 가능성, extension 미지원 시 fallback/거부, 소유한 테스트 프로세스의 종료 확인. 미실행 extension은 설계로만 제출합니다.

구술: server가 `requestState`에 만료를 넣으면 one-time 처리가 보장되는가? MCP stateless와 durable task는 모순인가? 취소 성공 응답과 원장의 예약 감소를 어떤 증거로 연결할 수 있는가?
