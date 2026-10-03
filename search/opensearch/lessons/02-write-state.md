# 02. Write·상태 — ACK, 가시성, 내구성은 다른 계약이다

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

이 강의는 refresh를 데이터 안전성의 동의어로 쓰지 않는 데서 시작합니다. 제공 OFFLINE `refresh`는 검색 가시성의 단순 모형일 뿐 fsync·translog·crash 복구를 구현하지 않습니다. 실제 LOCAL-ENGINE의 refresh·OCC·bulk 항목 검사는 시작점이며 강제 종료·복제·CDC는 추가 과제입니다.

<a id="os03"></a>
## OS03 · segment·refresh·flush·translog

### 원리와 내부 동작

Lucene은 segment와 이를 읽는 reader 관점으로 검색합니다. 새 write가 처리되어도 기존 searcher의 시야가 즉시 바뀌는 것은 아닙니다. refresh는 새 검색 시야를 열고, flush는 Lucene commit과 translog generation 관리에 연결됩니다. translog fsync 정책은 ACK와 crash 복구의 경계를 결정합니다. 이 세 이벤트를 한 개의 “디스크 저장” 화살표로 그리지 않습니다. [Index settings](https://docs.opensearch.org/latest/install-and-configure/configuring-opensearch/index-settings/)와 [index maintenance](https://docs.opensearch.org/latest/im-plugin/index-maintenance/)를 읽습니다.

`request`와 `async` durability는 서로 다른 위험 계약입니다. 전자는 해당 ACK 경로의 동기화 조건을 확인하고, 후자는 마지막 동기화 뒤 ACK된 write의 손실 가능성을 다룹니다. 어느 설정도 디스크·모든 복제본·원격 저장소가 동시에 유실되는 실패까지 마법처럼 해결하지 않습니다. real-time GET의 최신 문서 조회와 search의 reader 가시성도 분리합니다.

update/delete가 발생해도 segment의 모든 byte가 즉시 회수되지는 않습니다. 오래된 문서의 live 여부, 새 segment, merge·retention·열린 reader/PIT 때문에 유지되는 파일을 함께 추적합니다. force merge를 상시 write 부하의 일반적인 치료법으로 제안하지 않습니다.

### 추가 실험

1. 자신만의 새 index에서 자동 refresh를 통제합니다. 고정 ID write 뒤 ACK, GET, search의 결과를 순서대로 기록하고 명시적 refresh 뒤의 차이를 비교합니다.
2. write 1개마다 refresh하는 조건과 batch 뒤 refresh하는 조건을 작은 fixture로 비교합니다. 문서 수뿐 아니라 segment·refresh 횟수·가시성 지연을 관측합니다.
3. update/delete 뒤 `_source`의 최신 값과 search 결과, segment의 deleted-doc 관련 관측을 비교합니다. 논리적 삭제와 물리 공간 회수의 시점이 다른 것을 설명합니다.
4. 별도 격리 환경에서만 정상 종료/비정상 process 종료를 설계합니다. write ACK 원장과 재시작 후 ID·version·값을 비교합니다. OS page cache가 남는 process 종료를 전원 상실 시험이라고 부르지 않습니다.
5. `request`/`async` 비교는 검증된 scratch 환경의 선택 확장입니다. 손실이 한 번도 관찰되지 않았다는 사실은 `async`의 무손실 보장이 아닙니다.

### 제출·구술

한 write의 접수·primary 적용·replica 경로·translog 동기화·ACK·refresh·Lucene commit 시점을 미확정 구간까지 포함해 그립니다. 실행 환경에 replica가 없으면 해당 경로는 설계로 표시합니다. “refresh 후 검색되므로 crash에도 안전하다” 또는 “flush 전 ACK는 모두 사라진다” 중 하나라도 주장하면 미통과입니다.

<a id="os04"></a>
## OS04 · primary term·sequence number·bulk·재전송

### 원리와 내부 동작

`_seq_no`는 shard operation 순서를, primary term은 primary epoch를 추적하는 내부 경계입니다. 이를 업무 aggregate의 version·Kafka offset·전역 timestamp와 동일시하지 않습니다. 읽은 문서의 `_seq_no`와 `_primary_term`을 조건으로 보내는 OCC는 그 이후 변경 여부를 검사합니다. 409를 무한 반복해 덮어쓰는 것은 충돌 해결이 아닙니다. [Index Document API](https://docs.opensearch.org/latest/api-reference/document-apis/index-document/)의 조건을 확인합니다.

Bulk는 다중 문서 transaction이 아닙니다. HTTP 요청 성공과 각 item 성공은 다르며 실패 item마다 재시도 가능성·원인·업무 불변식이 다릅니다. client timeout은 서버 미적용의 증거가 아니므로 ID·업무 version·내용 digest와 성공/실패/미확정 원장이 필요합니다. [Bulk API](https://docs.opensearch.org/latest/api-reference/document-apis/bulk/)의 item 응답과 OCC를 읽습니다.

### 추가 실험

1. 두 client가 같은 seq/term을 읽게 합니다. 첫 변경은 성공하고 stale 조건을 가진 두 번째 변경은 409가 되는지 확인합니다. 실패한 쓰기가 최신 값을 바꾸지 않았는지 다시 조회합니다.
2. 성공, schema 오류, 중복 `create`, stale OCC가 섞인 bulk를 만듭니다. 모든 item의 action/ID/status/error를 원래 입력과 매핑합니다. 전체 응답 코드만 검사하는 잘못된 client가 테스트에서 실패해야 합니다.
3. 항목별 retry 정책을 설계합니다. 429/일시적 실패는 지수 backoff·jitter·횟수/시간 상한, 영구 mapping 오류는 격리, conflict는 업무 정책에 따른 재판정으로 구분합니다. 오류 메시지 문자열 하나로 분류하지 않습니다.
4. 업무 ID A에 v1→v3→v2, 같은 v3의 재전송, 같은 version의 다른 payload, v4 삭제 뒤 v2 지연 도착을 넣습니다. 최신 업무 상태와 삭제가 유지되는 별도 projection 계약을 구현합니다.
5. Kafka/CDC 확장에서는 마지막 성공 offset과 아직 미확정인 bulk item을 연결합니다. offset commit 전에 어떤 성공 ledger를 영속화하는지, 재시작 때 어떤 item을 재생하는지 증명합니다.

### 깊이 있는 반례

고정 `_id`만 사용하면 문서 개수 중복은 줄일 수 있지만 늦은 오래된 값의 overwrite를 막지는 못합니다. external version을 선택하더라도 같은 version의 서로 다른 내용, version reset/epoch, 삭제 version 보존 기간, reindex 중 version 이동을 별도로 설계해야 합니다. tombstone을 영구 보관하지 않는 물리 delete 후 매우 늦은 이벤트의 재생 위험도 포함합니다. `external_gte`를 내용 동일성 확인 없이 멱등성의 완전한 증명으로 사용하지 않습니다.

### 통과 기준

총 count뿐 아니라 ID별 최신 업무 version·값·삭제·미확정 항목을 독립 원장과 비교합니다. 한 번의 bulk 성공을 exactly-once 처리로 부르거나, seq_no를 다른 index/shard로 가져가 전역 업무 순서로 비교하면 미통과입니다. 소스에서 transport bulk 분배, primary operation, conflict 검사, item 응답 조립을 연결합니다.
