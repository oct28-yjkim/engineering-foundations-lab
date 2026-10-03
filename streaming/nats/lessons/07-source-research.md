# 07. KV·Object Store·소스·Kafka 비교·2주 미니 연구

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="nt13"></a>
## NT13: 편의 API가 감춘 저장·전달 계약을 다시 드러낸다

선수 조건: NT01–12, CAS, checksum, source/test 탐색. KV와 Object Store는 JetStream을 이용하는 상위 추상화입니다. 별도의 관계형 transaction engine이나 모든 S3 동작을 제공하는 것으로 설명하지 않습니다. [KV 공식 자료](https://docs.nats.io/learn/key-value/), [Object Store 공식 자료](https://docs.nats.io/learn/object-store/)

### 원리와 내부동작

KV bucket/key/revision/history/watch/TTL과 실제 stream·subject·consumer의 대응을 조사합니다. 단일 key CAS와 다중 key transaction은 다르고, read consistency는 API·replica·direct read 경로의 가정에 영향을 받습니다. “가장 최신으로 읽었다”는 claim은 관측 경로와 실패 조건을 명시해야 합니다.

Object Store에서는 metadata와 chunk의 관계, digest 검증, 부분 upload, 교체, 삭제·purge·link의 차이를 분석합니다. 크기와 시간 상한이 있는 합성 byte fixture만 사용합니다. chunk가 존재하거나 upload 함수가 반환한 사실만으로 독립 download 결과를 대신하지 않습니다.

가설 H13: “KV update와 Object Store put을 제공하므로 다중 key 원자성과 영구 파일 보관도 자동 보장된다.”

### 실험

1. KV 합성 key 하나를 두 writer가 같은 revision에서 변경하게 합니다. 사전에 정한 CAS 성공/충돌 기대값과 실제 최종 revision/value를 비교합니다. unconditional put의 lost update 대조군을 만듭니다.
2. 두 key를 별도로 갱신하다 중간에 종료하는 실험으로 다중 key 원자성 가정을 반증합니다. TTL/history 상한과 delete/purge 후 watch 관측을 각각 기록합니다. 새 기능은 고정 SDK/server 지원을 먼저 확인합니다.
3. 작고 결정적인 byte 배열의 원본 SHA-256을 SDK 외부에서 계산합니다. 다중 chunk upload/download 후 digest·크기·metadata를 비교하고, 부분 업로드·교체·삭제 도중 종료는 별도 전용 bucket에서 수행합니다.
4. KV/Object Store source에서 client가 생성하는 stream config·subject·header·consumer와 서버의 실제 상태를 연결합니다. low-level stream을 직접 조작하는 잘못된 설계가 상위 invariant를 어떻게 깨는지 먼저 설계로 분석합니다.
5. [Kafka](../../kafka/README.md)와 같은 업무 workload를 비교합니다. subject/partition, queue/shared consumer, stream sequence/partition offset, ACK/commit, retention, replay, 복제, 업무 idempotency를 별개 축으로 다룹니다. 기본 설정과 완료 조건이 다른 benchmark로 우열을 정하지 않습니다.

독립 oracle: KV는 key→expected revision/value와 CAS 결과 원장, Object Store는 원본 byte count/digest입니다. SDK가 검증했다고 출력한 digest를 그대로 다시 기대값으로 사용하지 않습니다. 파일 완전성과 권한·내구성·업무 적합성도 다른 평가 축입니다.

실패 조건: stale revision, TTL 만료, watch 재연결, 불완전 chunk, metadata만 남은 상태, 잘못된 delete/purge, 다른 client version. 어떤 상태가 실제로 가능했는지는 fault timing·source·관측 증거를 제출하고 추측을 결과로 적지 않습니다.

소스 과제: [고정 소스 지도](../source-reading.md)에서 최소 5개 symbol, 2개 상태 자료구조, 1개 실제 시험을 제출합니다. 권장 경로는 SDK KV/Object Store→JetStream API→stream/consumer/store입니다. 문서 표현과 구현이 다르면 version·조건·최소 재현을 함께 기록합니다.

제출물·통과: CAS 원장, 독립 checksum, API→stream 매핑, source/test 설명, 업무 요구를 기준으로 한 Kafka/NATS 선택 ADR. key revision을 stream 전체 transaction ID로 해석하거나 Object Store를 무조건적인 장기 archive로 선택하면 미통과입니다.

<a id="nt14"></a>
## NT14: 2주 안에 한 주장만 재현하고 반증한다

선수 조건: NT13, 앞선 fixture와 evidence. 이 모듈은 새로운 제품 여러 개를 묶는 프로젝트가 아니라 기존 자산으로 **한 경로·한 개선·실패 조건 둘**을 연구하는 24시간입니다. 별도 [8주 캡스톤](../../../capstones/nats-delivery-recovery.md)과 시간을 합산하지 않습니다.

### 연구 질문과 1차 자료

다음 중 한 가지를 선택합니다. 논문/설계 문서를 읽고 그 보장에 필요한 가정을 먼저 적습니다. “논문에 안전하다고 쓰였다”는 이유로 특정 서버의 전체 구현을 증명했다고 하지 않습니다.

| 선택 경로 | 연구 질문 | 변인 하나 | 최소 반례 두 개 |
| --- | --- | --- | --- |
| consumer 업무 원장 | ACK와 업무 commit 사이의 crash에도 결과를 보존하는가? | transaction 안의 operation-key 검사 | commit 직후 crash, 재전달과 늦은 ACK |
| pull capacity | batch가 유용한 완료율과 tail을 어떻게 바꾸는가? | batch 크기 | 느린 worker, 연결 중단 |
| stream 보관 | 보관 정책이 재처리 요구를 만족하는가? | retention 또는 limit 하나 | 늦은 consumer, backlog 중 expiry |
| routing/권한 | namespace 변경이 필요한 접근만 유지하는가? | subject/filter 설계 | 과도한 wildcard, 권한 축소 |
| Raft 실패 분석 | 관측한 failover가 어떤 안전성 가정과 연결되는가? | 지정 그룹의 link 하나 | leader 격리, quorum 상실 |

합의 경로의 필수 1차 자료는 Ongaro·Ousterhout의 [Raft 원 논문](https://raft.github.io/raft.pdf)입니다. leader election·log replication·safety에서 주장 하나를 선택하여 membership·timing·stable storage 가정을 정리합니다. source의 해당 상태 전이와 시험으로 연결하되, 논문의 일반 안전성 증명과 NATS 특정 revision의 실험 결과를 분리합니다.

다른 경로는 [공식 client protocol](https://docs.nats.io/reference/protocols/client), [ACK/redelivery](https://docs.nats.io/learn/jetstream/acknowledgment), [고정 구현·회귀 시험](../source-reading.md)을 1차 자료로 사용합니다. 과거 버전의 버그 보고서를 쓰면 재현 버전·수정 여부·현재 버전 결과를 별도로 확인합니다. 이 과정에는 특정 과거 결함이 현재에도 존재한다는 주장이 없습니다.

### 2주 실험 계획

1. 1–4시간: 요구·가설·범위·독립 oracle·실패 모델·중단 조건을 먼저 고정합니다. 개선하지 않은 baseline에서 오류를 잡아내는 의도적인 음성 대조군을 만듭니다.
2. 5–12시간: baseline 반복과 두 실패 조건을 실행합니다. 모형·mock·실제 서버·cluster 중 사용한 층을 명시합니다. 필요한 환경이 없으면 가설 검증 미실행으로 남깁니다.
3. 13–18시간: 한 개선만 적용하고 동일 oracle로 반복합니다. 의미적 결과가 바뀌지 않았는지 먼저 확인한 뒤 latency·error·resource를 비교합니다.
4. 19–24시간: 소스 근거, 경쟁 가설, 최소 반례, 재현 명령, 실패/미검증 범위, 운영 적용 전 추가 검증을 작성하고 구술합니다.

독립 oracle은 개선 코드와 계산을 공유하지 않습니다. 원래 ID/digest fixture, 외부 업무 원장, 수작업 matching 표, quorum 계산 등 별도 증거를 사용합니다. ACK count·stream count·업무 count가 우연히 같은 결과를 통과로 삼지 않습니다.

### 실패·제출·통과

실패 조건은 가설 기각 자체가 아닙니다. 재현되지 않은 이득을 성공으로 꾸미기, 실패 표본 제거, source 미확인, 주입하지 않은 장애를 실행했다고 표기하기가 연구 실패입니다. 가설이 기각돼도 원인이 좁혀지고 재현 가능하면 유효한 결과입니다.

제출물은 2–4쪽 연구 보고서, 버전/config manifest, raw 합성 결과, 독립 oracle, source symbol/test 목록, 실행/설계/미검증 표입니다. 성능 수치에는 표본 수·반복·오류율·tail·자원·계측 한계를 포함합니다.

통과하려면 [평가표](../assessment.md)의 네 영역과 필수 gate를 충족해야 합니다. 구술에서는 임의 메시지의 publish→store→delivery→business→ACK→recovery 경로를 설명하고, 알 수 없는 지점과 그 지점을 검증할 다음 실험을 말할 수 있어야 합니다.
