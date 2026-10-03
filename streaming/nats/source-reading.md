# NATS 고정 소스·논문 읽기 지도

목표는 “이 파일이 관련 있다”를 넘어 **입력 → 상태 변경 → 응답/오류 → 복구 → 회귀 시험**을 추적하는 것입니다. 기준은 서버 `v2.15.0`, Python `v2.16.0`입니다. 아래 경로는 기준 tag의 Git tree에서 확인했으며 파일 존재 확인과 upstream test 실행은 다릅니다. 코드 위치는 tag에 고정하고 함수명·line·실험 시 commit SHA를 보고서에 추가합니다.

## 서버 경로

모두 [nats-server v2.15.0](https://github.com/nats-io/nats-server/tree/v2.15.0)에 대한 링크입니다.

| 단계 | 구현 | 함께 읽는 시험 | 추적 질문 |
| --- | --- | --- | --- |
| subject/interest | [sublist.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/sublist.go) | [sublist_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/sublist_test.go) | literal·`*`·`>` 분기, cache invalidation, plain/queue 결과가 어떻게 달라지는가? |
| wire framing | [parser.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/parser.go) | [parser_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/parser_test.go), [fuzz](https://github.com/nats-io/nats-server/blob/v2.15.0/server/parser_fuzz_test.go) | TCP 조각 경계가 command/payload 경계와 다를 때 parser는 무엇을 보존하는가? |
| client lifecycle | [client.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/client.go) | [client_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/client_test.go) | PUB 처리·pending output·slow consumer·close와 PING/PONG 경계는 어디인가? |
| topology | [route.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/route.go), [gateway.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/gateway.go), [leafnode.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/leafnode.go) | [routes_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/routes_test.go) | interest 전파와 계정 경계가 어떻게 연결되는가? Core 경로를 Raft 투표로 오해하지 않는가? |
| stream admission | [stream.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/stream.go), [jetstream_api.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/jetstream_api.go) | [jetstream_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/jetstream_test.go) | dedup map·sequence·limit·expected sequence 검사는 어떤 순서이며 실패 전후 무엇이 바뀌는가? |
| persistence | [filestore.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/filestore.go), [memstore.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/memstore.go) | [filestore_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/filestore_test.go) | message block·index·삭제 흔적·flush/sync·복구 스캔의 역할은 무엇인가? |
| consumer | [consumer.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/consumer.go) | [jetstream_consumer_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/jetstream_consumer_test.go) | pending·redelivery timer·stream/delivery sequence·ack floor가 out-of-order ACK에서 어떻게 변하는가? |
| consensus | [raft.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/raft.go), [jetstream_cluster.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/jetstream_cluster.go) | [raft_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/raft_test.go), [cluster tests](https://github.com/nats-io/nats-server/blob/v2.15.0/server/jetstream_cluster_1_test.go) | metadata/stream/consumer group의 리더·commit·snapshot·catch-up 경계를 어디서 찾는가? |
| backup | [stream_backup.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/stream_backup.go) | [jetstream_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/jetstream_test.go) | snapshot 대상과 외부 계정·설정·업무 DB 상태 중 무엇이 포함되지 않는가? |
| security | [accounts.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/accounts.go), [auth.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/auth.go), [jwt.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/jwt.go) | [auth_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/auth_test.go), [jwt_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/jwt_test.go) | 인증·account mapping·publish/subscribe·reply 권한을 각각 어디서 거부하는가? |
| observability | [monitor.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/monitor.go), [events.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/events.go) | [monitor_test.go](https://github.com/nats-io/nats-server/blob/v2.15.0/server/monitor_test.go) | 지표가 누적 counter인지 순간 gauge인지, 메시지 body/신원 노출 가능성은 무엇인가? |

CPU의 `settled_prefix` 등 단순 모형 변수를 실제 consumer AckFloor 구현으로 해석하지 않습니다. stream sequence는 삭제·filter 때문에 연속 관측되지 않을 수 있고 consumer sequence는 재전달로 증가할 수 있습니다.

## Python client 경로

`v2.16.0`은 monorepo 구조입니다. **nats-py는 `nats/src/nats` 아래**이며 예전 `nats/aio/client.py` 링크는 이 tag에서 유효하지 않습니다. `nats-core`/`nats-jetstream`의 별도 API를 현재 fixture와 혼합하지 않습니다.

| 입력/상태 | 고정 소스 | 검증 질문 |
| --- | --- | --- |
| connect/flush/reconnect/drain | [aio/client.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/aio/client.py) | 서버 응답 전 client queue와 reconnect buffer가 보장하는 것과 못 하는 것은? |
| parser/subscription | [protocol/parser.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/protocol/parser.py), [aio/subscription.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/aio/subscription.py) | parser가 만든 메시지에서 callback/iterator까지 backpressure는 어디서 생기는가? |
| ACK/NAK/metadata | [aio/msg.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/aio/msg.py) | `ack`, `ack_sync`, `nak`, `in_progress`, `term`이 보내는 wire와 기다리는 응답은? |
| publish/fetch/config | [js/client.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/js/client.py), [js/api.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/js/api.py), [js/manager.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/js/manager.py) | Python 초 단위 timeout과 protocol 단위 변환, no-message와 API 오류를 구분하는가? |
| KV/Object Store | [js/kv.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/js/kv.py), [js/object_store.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/js/object_store.py) | revision/CAS·watch/delete/purge·chunk/metadata가 stream primitive에 어떻게 대응하는가? |
| regression | [test_js.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/tests/test_js.py), [test_client.py](https://github.com/nats-io/nats.py/blob/v2.16.0/nats/tests/test_client.py) | fixture와 다르게 여러 서버/네트워크 장애를 요구하는 test는 무엇인가? |

## 읽기·구현·반증 루프

1. 현상을 하나 선택하고 입력·시간·관측자·실패 모델을 적습니다. “유실”이면 publish 시도와 PubAck 완료를 별도 집합으로 둡니다.
2. pin된 코드에서 정상/오류 분기와 관련 시험을 찾습니다. test 이름은 직접 검색해 기록하고 추정한 이름으로 실행 성공을 주장하지 않습니다.
3. 작은 기대 상태 표를 먼저 계산합니다. 로그가 oracle의 유일한 근거가 되지 않도록 client 관측·server state·업무 원장을 대조합니다.
4. 해당 test만 재현하고 한 경계를 바꾼 음성 대조군을 추가합니다. source checkout·Go toolchain·플랫폼·build 옵션을 기록합니다.
5. 가설과 다르면 “서버 버그”로 단정하기 전에 지원 계약, client retry, retention, timeout, 측정 누락을 배제합니다. 최소 재현과 회귀 시험을 작성하고 upstream 공개/issue 제출은 별도 결정합니다.

## 원전 연구

- [Ongaro & Ousterhout, In Search of an Understandable Consensus Algorithm](https://raft.github.io/raft.pdf): election safety·log matching·leader completeness·state machine safety를 각각 assertion 후보로 바꿉니다. 논문의 가정과 JetStream의 실제 group/storage 설정을 매핑하고, 논문을 읽었다는 이유로 구현 correctness를 증명했다고 쓰지 않습니다.
- [공식 Core NATS 원리](https://docs.nats.io/learn/core-nats/), [subject 규칙](https://docs.nats.io/concepts/subjects), [JetStream 개념](https://docs.nats.io/concepts/jetstream): 용어의 시작점입니다. 최신 설명과 고정 source/실측의 차이를 별도 표에 남깁니다.
- [JetStream cluster](https://docs.nats.io/learn/topologies/jetstream-in-a-cluster), [보안 모델](https://docs.nats.io/concepts/security): Core topology와 persistence replication, 사용자 인증과 tenant namespace를 분리하는 설계 리뷰의 근거로 사용합니다.

필수 제출물은 호출 경로 2개, 정상/거부 분기 1쌍, upstream test와 추가 회귀 test의 차이, 측정값을 설명하는 최소 수정 또는 반례입니다. 소스 파일 수나 문서 읽기 시간으로 전문성을 평가하지 않습니다.
