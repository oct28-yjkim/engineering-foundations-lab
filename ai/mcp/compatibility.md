# MCP 버전·기능·호환성 계약

[트랙](README.md) · [소스 지도](source-reading.md) · [환경](environment.md) · [검증](labs/validation.md)

확인일 **2026-10-04**. 주 학습 명세는 **2026-07-28**, 비교 대상은 **2025-11-25**, 선택 구현은 **공식 Python SDK 2.3.0**입니다. protocol revision, SDK release, server implementation version, host 지원 기능, extension revision은 서로 다른 축입니다. 하나의 숫자로 호환성을 판정하지 않습니다.

## 두 프로토콜 세대를 섞지 않기

| 계약 | Classic: 2025-11-25 | Modern: 2026-07-28 |
| --- | --- | --- |
| 시작/버전 | `initialize` → 응답 → `notifications/initialized` | 초기화 handshake 없음; 요청별 `params._meta`의 version·capabilities |
| 서버 발견 | initialize 응답의 서버 정보 | 서버는 `server/discover` 구현; client의 사전 호출은 선택 |
| 연결 의미 | 협상된 연결/세션 context를 고려 | 연결·stdio process를 conversation/tenant identity로 사용하지 않음 |
| 일반 결과 | `resultType` 필드 없음 | `resultType:"complete"`; 추가 입력 필요 시 `"input_required"` |
| 서버의 추가 입력 | server→client 요청 | MRTR: `inputRequests` → 원 요청 재시도의 `inputResponses` |
| HTTP 세션/구독 | 선택 `Mcp-Session-Id`, GET stream 등 | protocol session header·GET stream 제거, POST `subscriptions/listen` |
| HTTP 스트림 복구 | 명세 조건에 따른 event ID/replay 지원 가능 | `Last-Event-ID` 재개 없음; 끊긴 요청은 새 RPC ID로 재발행 |
| cache metadata | 해당 revision의 계약 | 대상 결과의 `ttlMs`·`cacheScope`, 권한별 cache 분리 필요 |
| 고급 기능 | 당시 core/experimental 분류 | Tasks 등은 별도 extension; Roots/Sampling/Logging은 Deprecated |

이 표는 이 저장소가 선택한 두 revision의 비교입니다. 모든 2025판이 같은 기능을 제공한 것은 아닙니다. modern client가 이전 결과의 누락 `resultType`을 `complete`로 해석하는 호환 규칙과, modern 결과에서 필드를 요구하는 규칙을 구분합니다. 상세 기준은 [변경 내역](https://modelcontextprotocol.io/specification/2026-07-28/changelog), [base](https://modelcontextprotocol.io/specification/2026-07-28/basic), [고정 versioning 원문](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/basic/versioning.mdx)입니다.

## HTTP는 이름만 같다고 같은 wire가 아니다

2026-07-28 [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)는 POST의 `MCP-Protocol-Version`, `Mcp-Method`, 해당 연산의 `Mcp-Name`, 선택 `Mcp-Param-*`와 body 값의 일치를 검증합니다. proxy가 header를 제거·변경하거나 도구 schema가 오래되어도 문제가 생길 수 있습니다. 단순히 HTTP 200이거나 SSE frame이 보인다는 사실은 상호운용성 증거가 아닙니다.

구버전 HTTP+SSE, classic Streamable HTTP, modern Streamable HTTP를 별도 행으로 시험합니다. fallback은 명세가 허용한 응답/조건에서만 수행하고, OAuth 실패·잘못된 audience·임의 5xx를 버전 fallback의 근거로 사용하지 않습니다. modern에서 HTTP SSE stream 종료는 취소 신호이지만 업무 변경의 rollback을 보장하지 않습니다. stdio 취소 notification과 HTTP 취소 경로도 구분합니다.

## 확장·deprecated·SDK 구현

[Deprecated 목록](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)의 기능은 즉시 사라졌다는 뜻이 아닙니다. 이 과정은 Roots/Sampling/Logging을 호환성·마이그레이션 관점에서 읽고 신규 기본 lab의 의존성으로 삼지 않습니다. DCR도 최신 명세의 deprecated 상태와 대체 registration 방식을 확인합니다. Tasks·Apps·기타 extension은 core 지원만으로 자동 활성화되지 않습니다.

[Python SDK 2.3.0 릴리스](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)는 현재 실습 API의 기준입니다. v1의 `FastMCP`·`ClientSession.initialize()` 예제를 v2의 `MCPServer`·`Client`와 섞지 않습니다. `mode="2026-07-28"`처럼 명시한 실습 결과와 자동 협상 결과를 분리합니다. Python SDK의 지원을 다른 SDK·특정 앱·host의 지원으로 추정하지 않습니다.

**명세 기대값 → 고정 SDK 실제 응답 → client가 노출한 객체/예외**를 각각 기록합니다. SDK helper가 wire 오류를 `is_error` 또는 예외로 변환할 수 있습니다. 선택 fixture PASS는 해당 SDK 조합의 작은 동작 검증이며 공식 conformance 인증이 아닙니다. 구현별 오류 경계는 [실습](labs/README.md)에서 별도로 검산합니다.

## 제출할 호환성 matrix

각 행에 `client SDK/version + mode`, `server SDK/version`, `protocol revision`, `transport`, `advertised capabilities/extensions`, `auth identity`, `request metadata`, `wire result/error`, `SDK surface`, `검증/미검증`을 넣습니다.

필수 대조군은 지원하지 않는 revision, 누락 metadata, stale catalog, 잘못된 schema, 취소/timeout, 권한 변경, 다른 principal cache입니다. 실행한 두 조합으로 모든 앱·extension·배포가 호환된다고 보고하지 않습니다.
