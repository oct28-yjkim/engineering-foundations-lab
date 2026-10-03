# MCP 명세·SDK·표준 읽기 지도

[커리큘럼](curriculum.md) · [호환성](compatibility.md) · [실습](labs/README.md)

확인일 **2026-10-04**. protocol은 **2026-07-28**, spec 저장소 snapshot은 **`75db1e987cbbba6d170315dc99d0dfc440754aef`**, Python SDK는 [`v2.3.0`](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)·commit **`2118f14f8a19bc158d8a1cf90af58d85d187f849`**입니다. spec snapshot은 이 날짜에 조회한 main commit이며 이름 붙은 release tag라고 주장하지 않습니다. 아래 경로는 고정 Git tree와 대조합니다.

## 1. 규범부터 구현으로

| 대상 | 고정 원문 | 확인할 질문 |
| --- | --- | --- |
| 메시지/자료형 | [schema.ts](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/schema/2026-07-28/schema.ts) | Request/Result·metadata·error·capabilities·extension의 shape와 MUST/SHOULD를 분리할 수 있는가? |
| 기본 계약 | [basic/index.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/basic/index.mdx) / [versioning.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/basic/versioning.mdx) | 같은 socket/process에서 이전 요청의 version·capability·conversation을 추정하면 왜 잘못되는가? |
| 도구 계약 | [tools.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/server/tools.mdx) | JSON Schema·structured content·실행 오류와 protocol error의 경계, annotations를 권한으로 믿으면 생기는 반례 |
| 전송 | [stdio.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/basic/transports/stdio.mdx) / [streamable-http.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/basic/transports/streamable-http.mdx) | frame·EOF·stderr·header/body 검증·POST/SSE·disconnect의 의미는 각각 무엇인가? |
| 추가 입력/취소 | [mrtr.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/basic/patterns/mrtr.mdx) / [cancellation.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/basic/patterns/cancellation.mdx) | 새 request ID·requestState·client input·승인·업무 idempotency의 관계, cancel 이후 이미 발생한 변경 |
| cache | [caching.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/server/utilities/caching.mdx) | `ttlMs`·`cacheScope`가 권한 폐기·principal 분리·catalog revision을 대신할 수 있는가? |
| 인증 | [authorization/index.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/basic/authorization/index.mdx) / [security-considerations.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/75db1e987cbbba6d170315dc99d0dfc440754aef/docs/specification/2026-07-28/basic/authorization/security-considerations.mdx) | resource metadata·issuer·audience·scope·redirect·token passthrough·metadata fetch의 신뢰 경계 |

규범의 요구, SDK의 구현, 앱의 정책을 다른 열로 정리합니다. 예를 들어 JSON-RPC가 허용하는 모든 형태를 MCP가 허용하는 것은 아니며 CPU의 작은 schema checker는 JSON Schema 2020-12 구현이 아닙니다.

## 2. Python SDK 요청 경로

| 층 | 고정 소스 | 추적 과제 |
| --- | --- | --- |
| client facade | [client.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/client/client.py) / [_probe.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/client/_probe.py) | `Client`·`call_tool`·version mode·discovery·fallback과 timeout의 실제 조건 |
| dispatcher | [jsonrpc_dispatcher.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/shared/jsonrpc_dispatcher.py) / [dispatcher.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/shared/dispatcher.py) | `JSONRPCDispatcher`의 pending/in-flight·ID 할당·응답 연결·cancel·EOF 전파 |
| stdio | [client/stdio.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/client/stdio.py) / [server/stdio.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/stdio.py) | subprocess 환경·pipe·프레이밍·stdout 보호·stderr·프로세스 종료, Windows 경로 |
| server facade | [mcpserver/server.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/mcpserver/server.py) / [tools/tool_manager.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/mcpserver/tools/tool_manager.py) | `MCPServer`·tool/resource/prompt 등록→validation→handler→content/error 변환 |
| server runner | [runner.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/runner.py) / [validation.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/validation.py) | 요청 metadata·modern/classic 경로·capability와 error 처리 |
| HTTP | [_streamable_http_modern.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/_streamable_http_modern.py) / [transport_security.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/transport_security.py) | Origin/Host·Mcp header·POST 응답·disconnect. stdio PASS로 검증됐다고 하지 않기 |
| 추가 입력/cache | [_input_required.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/client/_input_required.py) / [caching.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/client/caching.py) | MRTR retry budget·state·call options·cache invalidation의 누락 반례 |
| OAuth/관측 | [auth/oauth2.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/client/auth/oauth2.py) / [shared/_otel.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/shared/_otel.py) | issuer별 credential·callback lifetime, trace context·baggage·exporter와 비밀 노출 |

Python SDK v2는 별도 `mcp-types` 패키지를 같은 버전으로 배포합니다. wire의 camelCase 이름과 SDK 객체의 snake_case attribute를 확인하고 임의 변환 규칙을 가정하지 않습니다. `src/mcp-types/mcp_types/`의 버전별 타입과 serializer도 trace에 포함합니다.

## 3. upstream test를 반례로 읽기

- [test_jsonrpc_dispatcher.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/tests/shared/test_jsonrpc_dispatcher.py): out-of-order·ID·pending·error를 찾아 요청 원장과 비교합니다.
- [test_stdio.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/tests/client/test_stdio.py): 환경 상속·pipe·EOF·cleanup의 가정을 씁니다.
- [test_streamable_http_modern.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/tests/server/test_streamable_http_modern.py), [test_streamable_http_security.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/tests/server/test_streamable_http_security.py): header/body·Origin과 transport별 오류를 분리합니다.
- [test_output_schema_validation.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/tests/client/test_output_schema_validation.py), [test_client_caching.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/tests/client/test_client_caching.py): server schema를 신뢰하는 범위와 cache identity를 반증합니다.
- [test_cancel_handling.py](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/tests/server/test_cancel_handling.py): 취소가 어느 task에 전파되고 어떤 변경이 남는지 확인합니다.

upstream test suite·공식 conformance harness는 별도 checkout과 의존성/실행 범위 검토가 필요합니다. 이 저장소의 단위 테스트·실제 stdio smoke와 같은 시험이 아닙니다. 공식 test 이름만 읽고 실행했다고 기록하지 않습니다.

## 4. 표준·설계 문서·논문

| 원문 종류 | 자료 | 실험 연결 |
| --- | --- | --- |
| 프로토콜 표준 | [JSON-RPC 2.0](https://www.jsonrpc.org/specification) | notification과 request ID·error/result, MCP에서 좁혀진 계약 찾기 |
| 인증 표준 | [RFC 9728](https://www.rfc-editor.org/rfc/rfc9728.html), [RFC 8707](https://www.rfc-editor.org/rfc/rfc8707.html), [RFC 9207](https://www.rfc-editor.org/rfc/rfc9207.html) | resource metadata·audience·issuer를 서로 바꾼 거부 대조군; 실제 OAuth 검증은 별도 |
| 명세 변경 근거 | [2026-07-28 changelog와 연결된 SEP](https://modelcontextprotocol.io/specification/2026-07-28/changelog) | stateless·MRTR·header routing·extension·cache의 설계 trade-off와 이전 방식 반례 |
| 보안 원리 논문 | [Saltzer·Schroeder, 1975](https://web.mit.edu/Saltzer/www/publications/protection/) | 최소 권한·완전 매개·default deny를 host→MCP→backend 경계에서 시험 |
| 에이전트 연구 | [기존 논문 지도](../llm-paper-lab/papers.md)에서 ReAct·Toolformer·평가 논문 | 도구 선택 품질과 protocol correctness·업무 권한을 분리한 평가 |

RFC/SEP는 학술 논문과 같은 유형의 자료가 아닙니다. 논문 benchmark 성능을 MCP 프로토콜이 보장한다고 주장하지 않습니다. 최종 trace는 명세 요구 1개·symbol 5개·자료구조 2개·정상/실패 oracle·최소 반례·미검증 경계를 포함합니다.
