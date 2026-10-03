# 06. SDK 내부·conformance·관측·배포·회복

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="mc11"></a>
## MC11: 편리한 decorator 뒤의 실제 실행 경로

선수 조건: MC01–10, Python async/context manager, 예외, type hint. 기준은 Python SDK **2.3.0**입니다. `MCPServer`와 `Client`의 v2 API를 사용하며 과거 v1 FastMCP 예제를 그대로 현재 API 설명으로 제시하지 않습니다. 외부 동명 라이브러리와 공식 SDK도 구분합니다. [고정 SDK README](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/README.md)

### 소스 읽기 계약

1. [고정 소스 지도](../source-reading.md)에서 schema/model, client request 경로, transport, server dispatcher, 결과 변환의 **5symbol**을 선택합니다.
2. pending request 또는 context, tool schema registry처럼 상태를 운반하는 **2자료구조**를 선택합니다. 수명·소유자·동시 접근·취소 시 정리 동작을 설명합니다.
3. 해당 경로를 다루는 **실제 test 1개**를 읽고 실패 입력 하나를 추가하거나 최소 재현으로 분리합니다. test 실행 전후를 기록하고 파일을 읽었다는 이유로 성공 표시하지 않습니다.
4. 규격 요구·SDK 구현 선택·우리 application 정책을 각각 열로 둡니다. 객체 생성이 완료됐다는 사실과 실제 subprocess wire 왕복을 구별합니다.

### 실험

- LOCAL-SDK에서 도구 검색·정상 호출·잘못된 인자·알 수 없는 이름·resource/prompt·종료 결과를 검산합니다. 정확한 fixture 범위는 [실습 문서](../labs/README.md)를 따릅니다.
- 같은 logical 실패가 JSON-RPC error 또는 `CallToolResult(is_error=True)` 중 어디에 나타나는지 기록합니다. 특히 SDK의 unknown-tool 처리와 [tools 규격](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)의 오류 분류가 다르면 차이를 숨기지 않습니다.
- output에 명시적 null이 있을 때와 필드가 누락됐을 때를 비교합니다. Python 객체의 attribute와 wire JSON의 필드명을 섞지 않습니다.
- callback exception·handler exception·transport EOF의 정리 경로를 구분합니다. 하나의 smoke test가 통과했다고 전체 conformance를 선언하지 않습니다.

버전 2.3.0에는 header annotation 등록 검증·header mismatch 후 tool 재조회/재시도·명시적 null structured result 검증 등의 변경이 있습니다. 특정 버전의 자동 retry가 업무 handler의 중복 실행으로 이어지는지 별도 관측해야 합니다. [릴리스 노트](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)

제출물: 5symbol/2자료구조/1test, 규격 대 구현 차이 표, 최소 wire trace, 미실행 protocol/extension. SDK 편의 동작이 가려 버린 실패를 독립 oracle로 찾아내는 것이 목표입니다.

<a id="mc12"></a>
## MC12: 관측 가능성과 자원 상한이 있는 배포

단일 응답 시간은 다음 구간으로 나눠 봅니다: queue 대기, client encode, transport, server validation/auth, handler, downstream, serialize, consumer 처리. 모델을 추가했다면 모델 지연은 별도 구간입니다. trace가 연결되어도 token·전체 인자·민감 resource 내용이 수집되어서는 안 됩니다.

### 실험

1. synthetic run ID와 낮은 cardinality의 method/result class로 성공·거부·unknown outcome을 상관시킵니다. raw token·사용자 입력·URI 전체를 metric label로 쓰지 않습니다.
2. 같은 합성 호출 수에서 느린 handler, 작은 worker pool, proxy buffering, 느린 consumer를 하나씩 바꿉니다. p50/p95/p99와 오류율·queue 길이·메모리 상한을 함께 냅니다.
3. body 크기·SSE event 크기·입력 recursion·response 크기·동시 실행 수를 제한합니다. 허용 범위를 넘으면 handler 진입 전에 거부되는지 확인합니다.
4. 시작 중, 처리 중, 정상 응답 후의 종료를 나눕니다. graceful drain, deadline, cancellation, 잔여 child process, 재시작 뒤 작업 원장 복구를 기록합니다.
5. 설정 reload 또는 배포로 tool schema가 바뀐 경우 client cache가 오래된 계약을 사용하는 시간을 측정합니다. schema와 handler를 서로 다른 시점에 갱신한 합성 실패를 검산합니다.
6. canary에서 현대/이전 client와 권한 context를 섞지 않고 probe합니다. rollback 시 protocol schema·업무 schema·지속 상태의 호환 조건을 따로 검사합니다.

### 운영 인수 기준

| 항목 | 최소 증거 | 부적절한 대체 |
| --- | --- | --- |
| readiness | 실제 의존성·권한 검증과 구분된 준비 상태 | process PID 존재 |
| 부하 | 제한된 입력·고정 결과·오류율 포함 지연 | 성공 요청만의 평균 |
| 취소·종료 | 원장/소유 process/자원 정리 | client가 연결을 끊었다는 로그 |
| 비밀 제거 | 필드별 redaction negative test | “로그에 token은 안 넣었음” 선언 |
| 회복 | 별도 시작/재시도 후 업무 검산 | 200 status 또는 server/discover 성공 |

로그와 trace를 공개하기 전에 합성 데이터 여부를 재검사합니다. endpoint URI나 tool 이름 자체도 조직 정보를 포함할 수 있습니다. 실제 서비스 credential 없이 CPU와 로컬 fixture로 실험할 수 있는 구간부터 완료합니다.

구술: 짧은 request timeout이 OAuth 사용자 상호작용을 자동으로 제한하는가? latency를 낮춘 결과가 권한 검사를 생략했기 때문이라면 개선인가? stateless routing을 하면서 업무 key 저장소가 장애 나면 어떤 정책으로 쓰기를 거부할 것인가?
