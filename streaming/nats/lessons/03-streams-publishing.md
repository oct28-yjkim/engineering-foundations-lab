# 03. stream·retention·저장 내부·PubAck·유한 중복 제거

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="nt05"></a>
## NT05: 저장됐다는 사실과 언제까지 남는지를 구별한다

선수 조건: NT04, 파일·인덱스·시간 제한. stream은 subject 선택과 저장·제한·retention을 관리합니다. consumer의 읽기 진행과 stream의 보관 집합은 같은 상태가 아닙니다. [첫 stream](https://docs.nats.io/learn/jetstream/your-first-stream), [Retention policies](https://docs.nats.io/learn/jetstream/retention-policies)

### 원리와 내부동작

Limits는 보관 한계 중심, Interest는 관련 consumer의 관심/ACK 중심, WorkQueue는 작업을 ACK한 뒤 제거하는 정책입니다. Interest에서 관심 있는 consumer가 없는 메시지, WorkQueue에서 겹치는 consumer filter, ACK된 Limits 메시지의 차이를 직접 확인합니다. stream의 나이·개수·byte 제한은 retention과 별개이며, discard-old와 discard-new의 결과를 구분합니다.

memory store와 file store의 자료구조, stream sequence, 삭제된 sequence의 빈 구간, subject별 인덱스, block/cache, 만료 검사, flush/sync와 snapshot 경로를 조사합니다. 파일이 존재한다는 것, process restart 후 읽힌다는 것, 전원 장애에 견딘다는 것은 서로 다른 증거입니다.

가설 H5: “ACK가 있으면 모든 정책에서 메시지가 없어지고, ACK가 없으면 영원히 남는다.”

### 실험

1. 합성 ID A–F를 만들고 policy·필터·ACK·시간·크기 한계가 결정하는 expected retained ID 집합을 손으로 계산합니다. [CPU `retention-gates`](../labs/offline.md)는 제공된 추상화 범위에서만 비교합니다.
2. 실제 서버의 별도 stream들에 동일 payload를 넣습니다. Limits에서 ACK 후 replay, Interest에서 관심 없음/한 consumer 미ACK, WorkQueue에서 정상 ACK 전후의 메시지 존재를 검사합니다.
3. MaxMsgs를 작게 고정하고 discard-old/new를 각각 시험합니다. “새 publish가 거부됐다”와 “이전 message가 축출됐다”를 PubAck/error와 retained IDs에서 독립 구별합니다.
4. WorkQueue consumer filter가 겹치는 설정의 거부 여부를 확인합니다. 한 consumer를 여러 worker가 공유하는 것과 겹치는 여러 consumer를 생성하는 것을 혼동하지 않습니다.
5. file store의 프로세스 재시작을 별도 확장으로 수행합니다. 시험 전 manifest를 보관하고 재시작 후 ID/digest를 비교합니다. store 파일을 손으로 삭제·편집하지 않습니다.

독립 oracle: input IDs−명시적으로 예상한 expiry/eviction/retention 삭제입니다. stream count만 보지 말고 ID와 digest, 첫/마지막 sequence, gap을 확인합니다. 비동기 만료가 관측되는 실제 시간은 bounded polling과 timeout으로 기록합니다.

실패 조건: 늦은 consumer 생성, 수신되지 않은 메시지의 age expiry, discard-new 수락 거부, filter 겹침, 저장 공간 압박. 기본 실습에서는 호스트 디스크를 실제로 채우지 않고 작은 전용 quota 또는 설계 과제로 대체합니다.

소스 과제: `server/stream.go`, `server/store.go`, `server/filestore.go`, `server/memstore.go`에서 append→limit 검사→삭제/index 갱신→복구의 경로를 찾습니다. 삭제와 물리 공간 회수가 반드시 같은 순간인지 시험/소스로 답합니다.

제출물·통과: 세 정책의 retained-ID 원장, discard 선택 ADR, 저장 경계 그림, 제한 한 개의 실제 거부 증거. WorkQueue를 “업무 부작용이 한 번만 생긴다”는 보장으로 설명하면 미통과입니다.

<a id="nt06"></a>
## NT06: publish 응답 유실과 중복 제거의 유효 범위를 검산한다

선수 조건: NT05, retry, 업무 operation key. JetStream PubAck는 stream이 처리한 publish에 대한 응답이며 subscriber의 업무 완료 응답이 아닙니다. `Nats-Msg-Id` 기반 dedup은 유한 window와 특정 stream의 상태에 의존합니다. [Publishing](https://docs.nats.io/learn/jetstream/publishing), [Advanced publishing](https://docs.nats.io/learn/jetstream/advanced-publishing)

### 원리와 내부동작

서버 수락과 client의 확인을 분리하면 `성공/실패` 외에 `결과 불명`이 필요합니다. ACK 응답이 유실된 publish를 같은 ID로 retry하는 이유와, window가 끝난 뒤 동일 retry가 새 메시지가 될 수 있는 이유를 설명합니다. dedup이 payload의 의미적 동일성이나 DB의 operation key 충돌을 자동 검사한다고 가정하지 않습니다.

stream sequence는 수락된 메시지의 순서를 설명하지만 여러 publisher의 업무 인과관계·consumer 완료 순서를 자동 정의하지 않습니다. expected-stream/expected-sequence 계열 조건부 publish는 사용하는 header와 서버/SDK 지원을 확인하고 적용 범위를 한 stream 또는 subject로 정확히 한정합니다.

가설 H6: “message ID만 부여하면 어느 시점·어느 stream·어느 DB에서도 중복이 사라진다.”

### 실험

1. [CPU `publish-dedup`](../labs/offline.md)에서 최초 publish, window 내부 재시도, window 이후 재시도를 검산합니다. 모형의 가상 시각과 실제 서버 timer 정밀도를 동일시하지 않습니다.
2. 실제 서버에서 같은 ID/같은 body, 같은 ID/다른 body, 다른 ID/같은 body를 따로 발행합니다. PubAck duplicate/sequence와 읽어 온 payload digest를 동시에 비교합니다.
3. finite window를 명시한 전용 stream에서 충분한 여유를 둔 window 전/후 실험을 반복합니다. 정확한 경계 시각에 대한 claim은 scheduler 오차와 측정 한계를 함께 제출합니다.
4. 고의 응답 유실 장치를 별도 구축했다면 저장 직후 응답만 차단합니다. 그런 장치 없이 publish timeout만 관측했다면 “응답 유실 주입 성공”이라고 쓰지 않습니다.
5. expected sequence를 사용하는 경쟁 publisher 둘을 비교합니다. 성공/거부 수와 최종 저장 값을 검산하고 이 조건부 수락을 여러 stream 또는 DB에 걸친 transaction으로 확대하지 않습니다.

독립 oracle: `business key→expected payload digest`와 별도로 `publish attempt→PubAck/unknown` 및 `stream seq→stored digest`를 작성합니다. 메시지 수가 적어졌다고 중복 제거가 정확했다고 결론 내리지 않습니다. 잘못 재사용한 ID로 정상 변경이 사라진 경우도 오류입니다.

실패 조건: ID 생성 충돌, payload 변경 후 ID 재사용, window 밖 retry, stream 재생성, 응답 timeout, 비동기 publish의 미확인 future. restart 이후 dedup 상태의 실제 보존 범위는 고정 버전에서 추가 검증하고 영구 원장으로 가정하지 않습니다.

소스 과제: `server/stream.go`의 message ID 추출·dedup 조회/만료·sequence 조건 검사·PubAck 반환 경로와 관련 시험을 찾습니다. client의 async publish pending future 정리, 제한 초과, timeout cleanup을 함께 추적합니다.

제출물·통과: ID/본문/window 조합의 truth table, 응답 불명 처리 정책, source 기반 가설 하나, 잘못된 대조군. publisher dedup과 consumer의 확인 ACK를 합쳐 외부 결제/DB 작업의 end-to-end exactly-once라고 부르면 미통과입니다.
