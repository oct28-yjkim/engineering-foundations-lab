# 06. Binlog·GTID·복제·HA — ACK와 적용과 읽기는 다른 시점이다

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

binlog/설정 읽기는 권한 범위 안의 LOCAL-ENGINE 과제이고 replica·승격·partition·Group Replication은 **별도 REPLICA-LAB**입니다. 제공 단일 노드 구성은 복제 토폴로지를 배포하지 않습니다. CPU `commit-recovery`의 성공을 실제 replication crash safety 검증으로 표시하지 않습니다.

<a id="my11"></a>
## MY11 · redo/undo/binlog·내부 commit 협조·GTID·CDC

### 원리

InnoDB redo와 server binlog가 서로 다른 commit 결과를 남기면 복구·복제 계약이 깨집니다. binary logging을 사용하는 transactional commit 경로에서 engine prepare, binlog 기록/동기화, engine commit과 recovery의 협조를 추적합니다. 이것은 클라이언트가 수행하는 `XA START/PREPARE/COMMIT`의 사용자 분산 transaction과 구별해야 합니다. group commit의 batch와 개별 transaction 경계도 다릅니다. [Binary log](https://dev.mysql.com/doc/refman/8.4/en/binary-log.html), [XA 개요](https://dev.mysql.com/doc/refman/8.4/en/xa.html).

GTID는 변경 묶음을 추적하는 식별 체계이지 서버 전체의 wall-clock이나 업무 요청 번호가 아닙니다. source 계보·interval·8.4의 tag를 포함한 집합 의미를 읽고, `gtid_executed`와 수신/소유 중 상태를 구별합니다. source에서 GTID를 확인했다고 replica가 이미 적용·조회 가능하다는 뜻은 아닙니다. [GTID format/storage](https://dev.mysql.com/doc/refman/8.4/en/replication-gtids-concepts.html).

```sql
SELECT @@global.server_uuid, @@global.server_id, @@global.log_bin,
       @@global.binlog_format, @@global.gtid_mode,
       @@global.enforce_gtid_consistency;
SELECT @@global.gtid_executed, @@global.gtid_purged;
```

권한이 없으면 오류와 필요한 관측 권한을 기록합니다. `mysql.gtid_executed`를 직접 수정하거나 GTID 상태를 reset하여 시험을 쉽게 만드는 절차는 사용하지 않습니다.

### 실험·소스 추적

1. 세 transaction의 request ID·변경 행·commit 응답과 binlog의 transaction 경계를 매핑합니다. binlog 설정이 꺼졌거나 GTID mode가 OFF라면 미설정 사실부터 기록하고 임의 global 변경 대신 별도 토폴로지를 설계합니다.
2. row-based event의 table map, before/after image와 schema를 읽습니다. row image 정책 때문에 이벤트 한 개만으로 전체 행을 재구성할 수 있다고 가정하지 않습니다. [Row-based logging](https://dev.mysql.com/doc/refman/8.4/en/replication-rbr-usage.html).
3. [소스 지도](../source-reading.md)의 binlog group commit→handler prepare/commit→InnoDB 경로에서 정상 순서와 recovery 분기 조건을 찾습니다. 모형의 marker와 실제 구현 상태를 1:1이라고 단정하지 않고 대응/생략 표를 만듭니다.
4. CPU 모형에서 engine durable prepare가 있고 binlog durable decision이 없는 경우, decision은 있으나 engine 최종 marker가 없는 경우 등을 대조합니다. 실제 엔진의 실패 주입은 BUILD/RESTORE-LAB로 별도 수행해야 합니다.
5. CDC 소비자는 transaction boundary, source epoch/GTID 또는 log position, schema version, 업무 key/version, sink 성공 원장을 연결합니다. 같은 이벤트 재생·부분 sink 성공·삭제 뒤 오래된 이벤트·schema 변경을 음성 대조군으로 넣습니다.

**통과:** redo/undo/binlog 역할표, 실제 또는 설계로 표시한 commit/crash 시간선, GTID 집합 연산과 source/replica 차이, CDC의 중복/미확정 계약이 필요합니다. GTID를 전역 업무 순서나 임의 sink의 exactly-once 보장으로 부르면 미통과입니다.

<a id="my12"></a>
## MY12 · 비동기·세미동기·Group Replication·fencing·read-after-write

### 세 가지 질문을 따로 묻는다

1. source가 client에게 무엇을 ACK했는가?
2. 어떤 replica가 무엇을 수신·내구성 있게 보관·적용했는가?
3. **이 client의 이 transaction/snapshot**이 그 변경을 볼 수 있는가?

비동기 복제에서 source commit과 replica 적용 사이에 지연/실패가 있을 수 있습니다. 세미동기 ACK는 설정된 replica의 relay-log 수신·flush 경계와 연결되며 SQL 적용 완료의 동의어가 아닙니다. timeout에 따른 비동기 fallback과 wait point·대기 replica 수 등 설정을 기록해야 합니다. [Semisynchronous replication](https://dev.mysql.com/doc/refman/8.4/en/replication-semisync.html).

Group Replication은 멤버십·합의/순서·certification·적용과 연결된 별도 시스템입니다. 선택한 consistency 수준에 따라 대기·읽기 계약이 달라지며, “group에 속하면 모든 읽기는 즉시 최신”으로 설명하지 않습니다. Router·Shell·InnoDB Cluster의 운영 기능과 Group Replication protocol도 분리합니다. [Consistency guarantees](https://dev.mysql.com/doc/refman/8.4/en/group-replication-consistency-guarantees.html).

### 별도 토폴로지 실험 matrix

| 조건 | 기록할 증거 | 불충분한 판정 |
| --- | --- | --- |
| replica apply만 지연 | source ACK, relay 수신, 적용 GTID, 정확한 조회 값 | connection 정상 또는 lag 숫자 하나 |
| client write 후 replica read | 필요한 GTID/업무 version, bounded wait, 새 read 경계 | source GTID 보유만 확인 |
| source process 중단 | ACK/미확정 ledger, 후보별 적용 집합, 승격 후 업무 검산 | 가장 큰 GTID 문자열 선택 |
| source/replica network 단절 | membership·fallback·write 허용·fencing 시점 | ping 또는 재접속 성공 |
| 옛 primary 재등장 | 외부/서버 쓰기 차단, 계보·divergence·재합류 절차 | 단순 read_only 설정 하나 |
| 잘못된 정상 DELETE 전파 | replica도 함께 오염되는 반례, 별도 backup 복원 | replica가 있으므로 backup 불필요 |

### 실행 설계

1. 독립 server UUID/server ID·volume·계정·channel을 가진 전용 다중 서버를 준비합니다. source와 target을 정확히 식별한 뒤에만 복제 관리 명령을 실행하고 기존 서버의 GTID/로그를 reset하지 않습니다.
2. source의 업무 request ID·ACK와 replica의 received/executed set 및 행 값을 시간선에 놓습니다. `SHOW REPLICA STATUS`와 Performance Schema를 함께 읽고 실패 worker·channel·오류를 숨기지 않습니다.
3. read-after-write 구현은 필요한 GTID의 적용을 **선택한 replica**에서 제한 시간 내 기다리고, 실패·timeout 시 반환 정책을 정의합니다. 이미 오래된 RR view를 가진 transaction이라면 wait 성공만으로 그 view가 새로워지지 않는 반례도 검증합니다.
4. 승격은 후보 선택뿐 아니라 옛 writer fencing, 라우팅 전환, 기존 connection·pool 처리, 미확정 요청 재판정, 재합류의 전체 절차로 검증합니다. source에 연결이 안 된다는 사실은 source가 쓰기를 멈췄다는 증거가 아닙니다.
5. `gtid_executed`의 포함 관계를 검토하되 filtering·skip·errant transaction·업무 데이터 오염 가능성 때문에 GTID 일치만으로 데이터 동등성을 단정하지 않습니다. exact ledger·값·제약을 추가 검사합니다.
6. semi-sync fallback을 포함한 실패 조건에서 ACK된 요청 손실 가능성을 실패 모델별로 설명합니다. 한 번의 무손실 승격 관측을 모든 network/storage 고장의 RPO=0 보장으로 쓰지 않습니다.

**통과:** 실제 다중 서버의 받은/적용한/보이는 상태, 정상·지연·승격·재합류 원장, fencing 증거와 독립 복원 경계가 필요합니다. 설계서만 제출했다면 REPLICA-LAB은 설계 완료·실행 미검증으로 남깁니다.
