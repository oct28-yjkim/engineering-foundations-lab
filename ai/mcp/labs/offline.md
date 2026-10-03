# MCP CPU 실험: revision, 계약, 요청 수명, 권한별 캐시

[실습 시작점](README.md) · [트랙](../README.md) · [코드](offline_lab.py) · [테스트](test_offline_lab.py)

검토 기준일: **2026-10-04**. 이 실험은 MCP SDK나 실제 서버가 아니라, 실패하기 쉬운 경계를 분리한 작은 결정론적 모델이다. Python 3.10+ 표준 라이브러리만 사용하며 네트워크·파일·하위 프로세스·LLM 호출·실제 권한 변경을 수행하지 않는다. `-B`는 Python bytecode cache 생성도 막는다.

프로토콜 기준은 modern `2026-07-28`, 비교 대상은 classic `2025-11-25`다. 날짜는 제품/SDK 버전과 다른 축이다. 공식 현재 revision과 호환 모델은 [versioning](https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning), 변경 내용은 [2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)에서 확인한다.

## 실행과 예상 결과

저장소 루트에서 실행한다. 아래의 `python`은 실제 Python 3.10+ 실행 파일이어야 한다.

```powershell
python -B ai/mcp/labs/offline_lab.py --list
python -B ai/mcp/labs/offline_lab.py --lab all
python -B -m unittest discover -s ai/mcp/labs -p test_offline_lab.py -v
python -B -O -m unittest discover -s ai/mcp/labs -p test_offline_lab.py
```

기본 호출은 도움말만 출력한다. `--lab revision-gate`처럼 하나만 실행해도 된다. 실제 실행 시간은 성능 지표가 아니다. 출력의 핵심 oracle은 다음과 같다.

| 실험 | 관찰값 | 무엇을 의미하는가 |
| --- | --- | --- |
| `revision-gate` | modern `prior_session_required=false`, classic `phase=ready` | 두 era의 준비 조건을 섞지 않았다 |
| `tool-contract` | `valid=success`, `zero_divisor=tool-error`, `unknown_tool=protocol-error` | 성공과 두 오류 계층이 분리된다 |
| `request-ledger` | `first_request_state=unknown`, `retry_new_rpc_id=rpc-2`, `business_effects=1` | 첫 응답 소실과 업무 중복 방지는 서로 다른 문제다 |
| `principal-cache` | 동일 principal hit만 true; 다른 principal·권한 철회·만료 hit는 false | 캐시 적중은 권한 재검증을 대체하지 않는다 |

테스트는 독립적인 리터럴 예상값과 경계 조건을 확인한다. 런타임 검증에 `assert`를 사용하지 않으므로 `-O`에서도 동일한 결과가 나와야 한다. 통과한 테스트 수와 환경은 [검증 기록](validation.md)을 확인한다.

## 1. revision-gate: 준비 상태를 어느 요청에 귀속시킬 것인가

Modern 모델의 `modern_gate()`는 요청 하나만 받아 판단한다. `params._meta`의 `io.modelcontextprotocol/protocolVersion`과 `io.modelcontextprotocol/clientCapabilities`가 각각 문자열·객체인지 검사한다. 이전 호출에서 선언한 capability를 기억하지 않는다. 빠진 필드는 `-32602`, 미지원 revision은 `-32022`, 필요한 capability가 없으면 `-32021`로 구분한다. 이는 [base protocol의 요청별 metadata](https://modelcontextprotocol.io/specification/2026-07-28/basic/index)와 [version error의 data 구조](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)를 좁게 모델링한다.

```json
{
  "jsonrpc": "2.0",
  "id": "r-1",
  "method": "tools/list",
  "params": {
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {}
    }
  }
}
```

Classic 모델은 `new → await-initialized → ready`만 다룬다. 성공한 `initialize` 교환을 한 단계로 추상화하고, ID 없는 `notifications/initialized`를 받아 준비를 마친다. 실제 classic 협상에는 서버가 다른 지원 버전을 제안하는 경로도 있지만 여기서는 고정된 `2025-11-25` 성공 경로만 허용한다. 초기화 이전 ping/logging 예외도 제외한다. [Classic lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)

### 반례를 만들어 볼 것

1. 첫 modern 요청에 `elicitation: {}`를 선언하고 다음 요청에서 제거한다. 두 번째 호출까지 capability가 전파되면 실패다.
2. ID를 `1`, `"1"`, `true`, `null`, `1.0`으로 바꾼다. 정수와 문자열은 구분되고 bool/null/float는 거부되어야 한다. 빈 문자열·음수 정수 ID를 프로토콜이 금지한다고 가정하지 않는다.
3. classic `initialize`에 modern metadata를 덧붙여 단일 handshake처럼 쓰지 않는다. 모델은 두 profile을 명시적으로 구분하며 자동 fallback을 구현하지 않는다.
4. `clientInfo.name`을 유명 제품명으로 바꾼다. 이 값이 인증·권한으로 승격되는 코드가 없어야 한다.

한계: metadata 전체 schema, HTTP header 일치, stdio framing, batching 지원 판단, 서버 discovery 결과, extension negotiation, transport별 fallback, MRTR을 구현하지 않는다. allowlist 밖의 method 거부는 교육용 profile 제한이지 전체 MCP의 지원 목록이 아니다.

## 2. tool-contract: 문법 오류와 실행 실패를 분리한다

`ratio`는 두 유한 수의 나눗셈만 수행한다. 이름을 찾을 수 없거나 call 인자가 객체가 아니면 JSON-RPC error다. 도구 입력 계약 불일치, 0 나눗셈, 출력 overflow는 `result.isError=true`인 도구 오류다. 정상 결과는 `resultType=complete`, text content, `structuredContent.quotient`를 돌려준다. 결과 schema를 다시 확인한 뒤에만 성공으로 분류한다. [Tools의 오류 구분과 structured content](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

이것은 작은 schema 구현이지 JSON Schema 2020-12 validator가 아니다.

| 지원하는 부분집합 | 의도적인 제한 |
| --- | --- |
| 단일 `type`: object/array/string/number/integer/boolean/null | union type, boolean schema 거부 |
| object `properties`, `required`, boolean `additionalProperties` | required는 이 실험에서 정의된 property만 참조; schema-valued additionalProperties 거부 |
| array `items` | items를 생략한 schema·tuple validation 거부 |
| number/integer `minimum`, `maximum` | bool·NaN·Infinity·명시적 null bound 거부 |
| 선택적 2020-12 `$schema`, 문자열 `description` | 다른 dialect, `$ref`, `oneOf`, `format`, `enum` 등 나머지 keyword 거부 |

JSON 값은 깊이 16, 방문 노드 4096 이하로 제한한다. schema는 깊이 16, object당 property 64 이하를 허용한다. 숫자는 Python 표현을 사용한다. JSON Schema의 정수 의미에 맞춰 `3.0`은 integer지만 `true`는 integer가 아니다. 객체/배열/원시 값의 검증을 연습하되 실제 도구의 출력 형태가 항상 객체라고 일반화하지 않는다.

### 반례를 만들어 볼 것

1. 성공 응답의 `quotient`를 `"0.5"`로 바꾼다. text가 그럴듯해도 structured 결과를 거부해야 한다.
2. 응답에 `result`와 `error`를 동시에 넣거나 요청 ID `1`에 응답 ID `"1"`을 붙인다.
3. `isError`를 문자열 `"false"`로 넣어 truthiness 오류를 유도한다.
4. 입력 schema에 `$ref` 또는 `format`을 더한다. 조용히 무시하여 검증했다고 주장하면 실패다.
5. `resultType=input_required`를 넣는다. 이 구현의 complete-only profile은 거부해야 한다. MRTR이 프로토콜상 잘못이라는 뜻은 아니다.

Classic 응답의 누락된 `resultType`을 `complete`로 해석하는 호환 처리는 이 classifier에 넣지 않았다. classifier 자체를 **modern 전용**으로 표시했기 때문이다. 실제 dual-era client에서는 revision별 adapter를 분리한다.

## 3. request-ledger: 취소·재시도·업무 결과를 따로 기록한다

`Ledger`는 명시적인 정수 clock과 immutable request tuple을 가진다. `now >= deadline`이면 응답이 오지 않은 요청은 `unknown`이 된다. `cancel-requested`나 `broken-stream`도 외부 업무가 취소됐다는 증거가 아니라 기다림을 중단한 이유다. 늦은 응답은 `late-result`로 보관하지만 정상 대기자에게 다시 전달하지 않는다. 결과 payload는 JSON 문자열로 snapshot하여 호출자가 원본 dict를 바꿔도 기록이 변하지 않는다.

Modern 연결 소실 뒤 재발행은 새 RPC ID를 사용한다. 이 실험은 관찰 trace 전체에서 ID를 재사용하지 않는 더 강한 로컬 규칙을 쓴다. 프로토콜의 일반 ID 고유성 조건은 아직 응답받지 않은 요청에 대한 조건이므로 이를 전체 수명 영구 고유성 요구로 일반화하면 안 된다. [기본 요청 ID 규칙](https://modelcontextprotocol.io/specification/2026-07-28/basic/index), [stream resumability 제거](https://modelcontextprotocol.io/specification/2026-07-28/changelog)

`BusinessStore`는 별도의 합성 counter다. `(principal, tenant, business key)`와 업무 인자 fingerprint를 원자적으로 저장한다고 **가정**한다. 같은 key·같은 의도는 같은 receipt, 같은 key·다른 의도는 오류다. RPC ID는 이 저장소의 key가 아니다.

```text
rpc-1 전송 → 업무 counter 증가 → 응답 stream 소실 → 결과 unknown
rpc-2 전송 → 동일 business key 확인 → 기존 receipt 반환 → counter는 1
```

### 반례를 만들어 볼 것

1. business key를 빼면 두 번 호출한 counter가 2가 되는가?
2. 취소 이벤트 이후에도 이미 증가한 counter가 1로 남는가?
3. 마감시각 직전과 정확히 마감시각에 응답을 주었을 때 delivery가 달라지는가?
4. timeout 이후 같은 RPC ID를 재사용하면 늦은 응답이 새 요청에 잘못 대응하는 상황을 설명할 수 있는가?
5. 같은 business key에 다른 tenant/principal을 붙였을 때 독립적인 업무로 처리되는가?

한계: 취소 notification을 송신하지 않고 로컬 이벤트만 모델링한다. 실제 서버가 취소를 수용하는지, DB commit이 일어났는지, 외부 API의 idempotency 보존 기간·분산 경쟁·장애 원자성은 검사하지 않는다. counter 저장과 외부 효과 사이 crash가 있는 시스템에 이 결과를 대입하여 exactly-once를 주장할 수 없다. caller는 재시도 전에 권한과 업무 위험도를 다시 평가해야 한다.

## 4. principal-cache: 연결 ID가 아니라 결과의 권한 문맥을 분리한다

교육용 private cache key는 다음을 모두 포함한다.

```text
server + protocol revision + principal + tenant + authorization context
       + method + result-affecting params + policy revision + catalog revision
```

`authorization_context`는 인증 계층이 확인한 문맥의 불투명한 식별자다. 같은 principal이라도 token/scope 문맥이 달라지면 같은 cache entry를 쓰지 않는다. 이 모델은 `clientInfo`, 도구 인자에 쓰인 사용자 이름, 세션/연결 ID를 신뢰 주체로 바꾸지 않는다. 실제 token을 테스트·키 출력에 넣지 않는다.

`cache_get()`은 매번 별도로 계산된 `authorized`를 요구한다. TTL이 남아 있어도 권한이 없으면 반환하지 않는다. `now < created_at + ttlMs`에서만 hit이며 TTL 0은 즉시 stale이다. policy/catalog revision 변경은 새 key로 구분한다. 원본 payload와 반환값 모두 snapshot/copy하여 mutation을 통한 오염을 막는다.

이 모델은 `tools/list`, `resources/read`의 ordinary params만 허용하고 `inputResponses`/`requestState`가 있는 MRTR retry를 거부한다. `cacheScope=public`은 지원하지 않는다. 실제 MCP의 private scope는 authorization context 간 공유를 금지하고, TTL은 변경되지 않을 것이라는 보장이 아닌 신선도 힌트다. [Caching specification](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching)

### 반례를 만들어 볼 것

1. principal·tenant·authorization context·policy revision을 하나씩 바꾸어 전부 miss인지 확인한다.
2. 동일 URI라도 다른 서버·다른 protocol revision에서 결과가 재사용되는지 확인한다.
3. 인자 key 순서를 바꾸면 동일 key가 되지만 `cursor`나 `uri` 값이 바뀌면 다른 key가 되는지 확인한다.
4. cache TTL이 남아 있는 동안 권한을 철회하여 `authorized=false`로 읽는다.
5. cache 반환값을 수정한 뒤 다시 읽어 저장된 값이 변하지 않았음을 확인한다.

한계: 인증·token 검증·scope 해석·policy revision 전파는 외부에서 이미 올바르게 이루어졌다고 가정한다. JSON serialization은 이 교육 데이터용으로 key를 안정화할 뿐 RFC 8785 canonicalization이 아니다. TTL·cacheScope만으로 접근 통제를 구현할 수 없고, stale policy 정보·잘못된 principal 매핑·입력 누락은 여전히 정보 유출을 일으킨다. 여러 페이지의 snapshot consistency나 실제 gateway의 Vary/헤더 처리는 검증하지 않는다.

## 제출물과 통과 조건

각 실험마다 예측한 결과, 실제 출력, 하나 이상의 의도적 실패, 제외된 운영 가정을 한 장에 기록한다. 테스트 통과만 보고서에 붙이지 않는다.

- revision: modern 요청과 classic 준비 절차를 wire 예시 두 개로 구분한다.
- 계약: protocol error·tool error·성공·output 계약 위반을 혼동하지 않는다.
- 요청 수명: caller state와 외부 업무 state를 독립적으로 그린다.
- 캐시: 주체/인가 문맥 분리와 매 요청 권한 재검증의 실패 사례를 설명한다.
- 모든 결과에 “교육용 부분집합; MCP 전체 conformance·OAuth 보안·분산 exactly-once 검증 아님”을 명시한다.
