# 03. stdio·Streamable HTTP·프레이밍·라우팅

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="mc05"></a>
## MC05: 로컬 subprocess도 신뢰 경계다

선수 조건: MC02, pipe, UTF-8, async read/write, EOF. stdio는 client가 server subprocess를 실행하여 newline-delimited JSON-RPC를 교환하는 binding입니다. stdout은 protocol 전용이며 일반 로그는 stderr로 분리합니다. modern server는 독립 JSON-RPC request를 거꾸로 보내지 않습니다. [공식 stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)

학습 목표는 한 번의 `read()`와 한 개의 메시지를 같은 것으로 보는 버그를 제거하는 것입니다. OS pipe는 바이트를 운반하며 scheduler·buffering·프로세스 종료가 논리 메시지 경계와 일치하지 않을 수 있습니다. 실제 OS 경계 검증은 CPU 모형이 아닌 선택 LOCAL-SDK 및 별도 failure fixture에서 수행합니다.

### 실험

1. 합성 JSON 한 줄을 바이트 여러 조각으로 나눈 경우, 여러 줄을 한 번에 읽는 경우, UTF-8 문자 중간에서 분리한 경우의 parser 동작을 예측합니다.
2. server stdout에 일반 `print` 한 줄을 섞는 대조군을 설계합니다. stderr 메시지가 있다는 이유만으로 RPC 실패라고 판정하는 client도 비교합니다.
3. LOCAL-SDK의 실제 child process가 성공·검증 실패·client exception 뒤에 어떻게 종료되는지 확인합니다. parent 종료 후 소유한 process가 남는지 점검합니다.
4. queue 크기·메시지 바이트 수·동시 요청 수를 작게 제한하고 느린 reader에서 backpressure를 관측합니다. 무제한 producer 실험은 하지 않습니다.
5. 실행 파일 절대 경로, 고정 argv, 최소 environment, 좁은 작업 디렉터리를 기록합니다. tool/resource의 문자열을 shell command로 해석하지 않습니다.

프로세스가 사용자 권한으로 실행되면 로컬 파일이나 네트워크에 접근할 수 있습니다. stdio 자체가 sandbox는 아니며 roots는 경로 정보를 주는 기능이지 OS 파일 권한 장치가 아닙니다. credential 환경 변수를 전체 상속하지 말고 필요 항목을 명시합니다. 기본 fixture에는 실제 자격 증명이 없습니다.

제출물: framing 입력/출력 표, stdout/stderr 경계, 정상/비정상 종료 원장, queue 상한, child process 정리의 소유 범위. 소스에서는 receive loop와 pending-request map, cancellation/finally cleanup의 책임을 추적합니다.

<a id="mc06"></a>
## MC06: HTTP 경계·SSE·헤더와 body의 동일성

현재 HTTP binding은 단일 MCP endpoint로 POST를 보내며 응답은 JSON 또는 요청 범위 SSE입니다. `MCP-Protocol-Version`과 `Mcp-Method`, 해당 작업의 `Mcp-Name`은 body와 일치해야 합니다. 2026-07-28에는 기존 GET stream·protocol session·SSE resume 계약이 없습니다. [공식 Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)

추가 HTTP-LAB는 loopback 전용 합성 server/proxy에서만 수행합니다. 기본 stdio fixture의 통과를 HTTP 검증으로 바꾸지 않습니다. endpoint Origin 검사, 인증, 요청 크기, proxy routing의 책임을 별도로 도식화합니다.

### 실험

1. 같은 payload를 JSON 응답과 SSE 응답으로 받아 RPC 결과가 동일한지 검산합니다. SSE keep-alive comment를 업무 결과나 오류로 처리하지 않습니다.
2. method·tool 이름·revision을 header와 body에서 하나씩 다르게 보냅니다. proxy가 허용한 이름과 backend가 실행한 이름이 달라지지 않아야 합니다.
3. `x-mcp-header`를 쓰는 합성 region 파라미터에서 잘못된 schema·특수문자·encoding을 시험합니다. credential·PII는 routing header에 싣지 않습니다. 사용 가능한 형식의 정확한 제약은 [tool 정의](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)를 기준으로 합니다.
4. 허용 Origin·잘못된 Origin·Origin 없는 비브라우저 호출을 각각 기록합니다. Origin을 인증 대신 사용하지 않습니다. DNS rebinding 방어와 접근 권한 검사는 목적이 다릅니다.
5. proxy buffering·짧은 idle timeout·response stream 단절을 하나씩 바꿉니다. 단절 이후 처리 결과는 업무 원장으로 확인하고 무조건 재실행하지 않습니다.
6. change notification용 `subscriptions/listen`과 원래 요청의 progress stream을 분리합니다. 재연결 시 구독 복원과 업무 요청 재시도는 다른 절차입니다.

제출물: 실제 HTTP status·RPC error·handler 진입 여부·업무 결과의 네 열, routing 입력과 backend 입력 비교, 끊김 시점별 outcome. client가 문자열 이름을 바꾸거나 proxy가 header를 제거한 경우도 포함합니다.

구술: header/body 불일치가 권한 문제로 번지는 경로는 무엇인가? stateless protocol이면 연결 수·SSE queue·backend transaction 상태도 없어지는가? 오래된 `Mcp-Session-Id` 예제를 현대 서버에 그대로 붙이면 왜 문제가 되는가?
