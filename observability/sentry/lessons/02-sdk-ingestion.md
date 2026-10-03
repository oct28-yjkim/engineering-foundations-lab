# S03–S04 — SDK 문맥, Envelope, 수집 제어

외부 서비스 없이도 검증할 수 있는 경계부터 시작합니다. 완성 SDK harness는 제공되지 않으며, 고정 버전 SDK와 메모리 transport 또는 loopback HTTP 수신기를 직접 구현하는 `SDK-LAB`입니다. [실습 준비](../labs/local-lab.md)의 외부 송신 방지 조건을 먼저 만족합니다.

## S03. 객체가 격리된 문맥에서 바이트가 되기까지

### 선수 조건과 원리

S02, UTF-8, Promise/비동기 callback, HTTP body를 이해해야 합니다. SDK capture 시점의 오류 객체는 곧바로 전송되는 JSON과 같지 않습니다. integration·event processor·scope 병합·필터·serialization이 개입합니다. 따라서 capture 함수만 mock하면 scope 누출이나 serializer 동작을 검증할 수 없습니다. SDK 처리 후 transport 경계의 payload를 관찰해야 합니다.

Node 환경에서 동시에 처리하는 요청 A/B는 process를 공유하지만 사용자·tag·breadcrumb가 섞이면 안 됩니다. 지원되는 framework integration은 요청 문맥을 분리하고, Node SDK는 AsyncLocalStorage를 이용하는 경로를 갖습니다. 다만 임의 background job, 사용자 정의 scheduler, 요청 종료 뒤 실행되는 작업의 경계는 직접 정의해야 합니다. global scope에 사용자 정보를 넣으면 동시 요청 모두에 영향을 줄 수 있습니다. 새 작업을 `withIsolationScope`로 감싸는 방식은 선택한 SDK 버전과 integration에서 검증합니다. “비동기면 무조건 자동 격리”도, “AsyncLocalStorage가 있으면 lifecycle 설계가 불필요”도 아닙니다. [Node 비동기 문맥](https://docs.sentry.io/platforms/javascript/guides/node/configuration/async-context/)

Envelope는 한 줄의 JSON header와 유형별 item header/payload의 열입니다. 명시적 `length`는 문자열 글자 수가 아닌 payload의 byte 수입니다. 한글·이모지와 binary attachment가 있는 경우 이 차이가 곧 parser correctness입니다. 명시 길이가 없을 때와 있을 때의 newline 처리도 다릅니다. Header의 project 식별 및 전송 metadata와 event 내부의 사용자 문맥을 혼동하지 않습니다. [Envelope 규약](https://develop.sentry.dev/sdk/foundations/envelopes/)

### 실험 A: 비동기 교차 오염 찾기 — `SDK-LAB`

입력은 100개의 동시 작업이며 각 작업에 `job_id`, 합성 `tenant_canary`, breadcrumb 3개와 서로 다른 지연 순서를 부여합니다. 사용자 canary는 `tenant-A-001` 같은 인공 문자열입니다. 외부 DSN 없이 SDK의 공식 custom transport 연결 지점을 사용하거나 송신 대상을 loopback으로 제한합니다. 네트워크 차단을 보조 장치로 둡니다.

1. 정상 구현은 작업별 isolation scope에 문맥을 넣고, Promise 병렬 분기와 지연 callback에서 오류를 한 번씩 capture합니다.
2. transport에 도달한 event를 `job_id`로 분류하고, 해당 작업의 canary만 포함하는지 독립 oracle로 비교합니다.
3. 비교용 결함 구현은 요청별 사용자 값을 global/shared mutable 상태에 넣습니다. 실행 순서를 barrier로 제어하여 A 설정→B 설정→A capture를 강제합니다. 우연한 timing에만 의존하지 않습니다.
4. 작업 종료 후 시작한 background task를 추가합니다. 이 작업이 원래 요청의 문맥을 이어받아야 하는지, 새로운 문맥이어야 하는지 계약을 먼저 정하고 검증합니다.

expected evidence는 capture 호출 수, 실제 transport item 수, 작업별 canary 집합, 잘못된 부모·사용자·breadcrumb의 차집합입니다. 동일 문자열을 모든 작업에 사용하는 test는 누출을 찾을 수 없습니다. 정상 구현에서 교차 오염 0, 결함 구현에서 의도한 반례 검출, 세 독립 실행에서 같은 oracle 판정이면 통과합니다. 이것은 SDK 격리 증거이며 tenant 권한 서버 검증을 대신하지 않습니다.

### 실험 B: Envelope 프레이밍 — `OFFLINE` / `SDK-LAB`

`ASCII`, `한글`, `😀`, 줄바꿈을 포함한 payload와 작은 binary fixture를 만듭니다. 아래 코드는 오프라인 길이 차이를 확인하는 예이며 파일이나 네트워크를 다루지 않습니다.

```javascript
const payload = JSON.stringify({message: "한글😀\nline"});
const bytes = Buffer.from(payload, "utf8");
console.log({jsCodeUnits: payload.length, utf8Bytes: bytes.length});
if (Buffer.byteLength(payload, "utf8") !== bytes.length) throw new Error("length oracle failed");
```

실제 Envelope fixture에서는 정확한 byte length, 1byte 짧은 값, 1byte 긴 값, 중간 EOF, 알 수 없는 item type, 명시 길이가 있는 newline payload를 만듭니다. 프로토콜에 정의된 skip/오류 정책과 선택 parser의 실제 동작을 비교합니다. 임의로 unknown type을 valid event로 세지 않습니다. binary를 JSON 문자열처럼 잘라 읽는 결함도 주입합니다.

통과 조건은 정상 fixture의 payload byte round trip 일치와 모든 음성 fixture의 명시적 판정입니다. parser가 입력을 거부했다는 사실과 서버가 같은 방식으로 거부한다는 주장은 구별합니다. [소스 지도](../source-reading.md)의 serializer/Envelope parser 경로를 연결합니다.

## S04. ACK·rate limit·재시도·종료를 분리하기

### 선수 조건과 원리

S03과 HTTP response header, monotonic clock, queue를 이해해야 합니다. capture 호출이 반환되더라도 asynchronous processing이나 transport queue에 데이터가 남을 수 있습니다. `flush`/`close`의 의미와 timeout 처리도 SDK마다 확인해야 합니다. 로컬 queue가 비었다는 사실은 서버 검색 완료나 알림 전달을 보장하지 않습니다.

Sentry rate limiting은 data category별 제한을 전달할 수 있습니다. `X-Sentry-Rate-Limits`의 category는 Envelope item type과 일대일 같지 않습니다. 제한 header는 429뿐 아니라 200 응답에도 올 수 있습니다. client는 아직 살아 있는 더 긴 제한을 짧게 덮어쓰지 않아야 하며, unknown category 처리와 전체 category 제한을 구별해야 합니다. 재시도 큐·offline persistence·종료 동작은 SDK 구현에 의존합니다. 제한 중인 데이터를 영구 보관한 뒤 모두 재전송한다고 가정하지 않습니다. [SDK rate-limit 규약](https://develop.sentry.dev/sdk/foundations/transport/rate-limiting/)

### 실험: 가짜 시계·응답 행렬 — `SDK-LAB`

실제 SaaS를 rate limit에 도달하도록 때리지 않습니다. loopback 수신기 또는 공식 transport test harness에서 fake clock을 사용하고, SDK 내부 limiter를 건너뛰는 mock은 피합니다. dependency injection이 어렵다면 해당 버전의 SDK 단위 테스트 형식을 활용합니다.

| 입력 응답/사건 | 사전 oracle에서 묻는 질문 |
| --- | --- |
| 200 + error category 10초 제한 | 첫 수락과 이후 error 차단, 다른 category의 독립성 |
| 429 + `Retry-After` | category 제한 header가 없을 때 적용 범위와 시간 |
| 429 + 관련 header 없음 | 규약의 fallback과 선택 SDK 구현이 일치하는가 |
| 기존 20초 제한 중 5초 제한 수신 | 기존 deadline이 잘못 단축되는가 |
| 5xx / 연결 실패 / 응답 timeout | 재시도·폐기·buffer 상태가 실제 구현에서 무엇인가 |
| 종료 직전 capture + 짧은 flush timeout | return value와 남은 항목, 관측 불가능 항목을 구별하는가 |

입력마다 event_id와 논리 입력 ID를 따로 붙입니다. 송신 시도, loopback 수신, SDK 폐기 사유, queue 상태를 기록하고 clock을 deadline 전·경계·후로 이동합니다. Rate limit spec에는 429 fallback 규칙이 있지만 SDK 버그·버전 차이가 있을 수 있으므로 예상값과 실제값을 별도 열로 둡니다. wall clock을 실제로 기다리는 test는 불필요하게 느리고 경계 재현이 어렵습니다.

서버가 받았지만 응답이 유실되는 시나리오는 “안 보냈음”과 구별되지 않을 수 있습니다. 논리 오류 ID에 대한 중복 처리 계약을 별도로 정합니다. arbitrary 재-capture가 같은 `event_id`나 업무 ID로 자동 dedup된다고 가정하지 않습니다. 반복 송신으로 시험 프로젝트 quota를 소모하지 않습니다.

### 산출물·실패·gate

응답 행렬, fake clock timeline, wire attempt 원장, 선택 SDK의 transport/limiter 호출 경로를 제출합니다. 모든 category/deadline 판정이 oracle과 맞아야 하며 실패한 항목은 regression fixture로 남깁니다. “captured”, “queued”, “HTTP accepted”, “indexed”를 서로 바꾸어 쓰면 미통과입니다.

queue 무제한 확장, 실패 때 매번 즉시 재시도하는 폭주, 비밀정보를 debug log에 출력하는 실패도 검토합니다. 운영 결정에는 메모리 상한, queue 폐기 정책, shutdown 예산과 SDK 바깥의 독립 health signal을 포함합니다. 본 실험은 서버 내부 영속성이나 실제 quota 정책을 검증하지 않습니다.
