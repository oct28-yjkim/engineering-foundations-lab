# M11–12. 복구의 증명, WAL 계보, 복제와 장애조치

## M11. 백업 생성에서 서비스 복원까지

**선수 지식:** M04 WAL/LSN, M10 vacuum/horizon. **범위:** 논리 복원은 S, 물리 복원·PITR·crash 주입은 T. 이 문서는 T의 실험 설계와 판정 절차를 제공하며 별도 클러스터 자동 설치는 제공하지 않습니다.

논리 백업은 스키마와 데이터를 다시 구성하는 입력이고 물리 백업은 클러스터 파일 상태와 필요한 WAL을 이용합니다. 복제는 실수한 DELETE도 전파할 수 있으므로 백업을 대체하지 않습니다. 일관된 base backup과 끊기지 않은 WAL 구간이 있어야 원하는 시점까지 복구할 수 있습니다. 백업 파일 존재·manifest 검증·서버 기동·업무 검증은 각각 다른 확인 단계입니다. [백업 방법](https://www.postgresql.org/docs/18/backup.html), [PITR](https://www.postgresql.org/docs/18/continuous-archiving.html).

RPO는 잃어도 되는 데이터 범위, RTO는 서비스를 되살려야 하는 시간입니다. SQL상 마지막 LSN과 업무상 승인된 주문 원장을 연결해야 실제 손실을 계산할 수 있습니다. LSN은 byte 위치이며 failover/recovery로 timeline이 갈라지면 timeline history와 함께 읽어야 합니다. timestamp만으로 어떤 WAL 계보를 복구했는지 알 수는 없습니다.

### S 실험: 별도 데이터베이스로 논리 복원

저장소 루트의 터미널에서 실행합니다. 원본 데이터를 수정하는 작업을 멈춘 짧은 실습 구간을 잡아, dump 시점과 검산 시점의 차이를 통제합니다. 이미 `lab_m11_restore`가 있으면 삭제하지 말고 새 이름을 정해 모든 명령에 일관되게 사용합니다.

```bash
docker compose -f databases/postgresql/compose.yaml exec postgres pg_dump -U lab -d lab --schema=commerce --format=custom --file=/tmp/m11-commerce.dump
docker compose -f databases/postgresql/compose.yaml exec postgres pg_restore --list /tmp/m11-commerce.dump
docker compose -f databases/postgresql/compose.yaml exec postgres createdb -U lab lab_m11_restore
docker compose -f databases/postgresql/compose.yaml exec postgres pg_restore -U lab -d lab_m11_restore --exit-on-error --no-owner /tmp/m11-commerce.dump
docker compose -f databases/postgresql/compose.yaml exec postgres psql -X -U lab -d lab_m11_restore
```

`--schema=commerce`는 여기서 학습 데이터만 복원하기 위한 선택입니다. 모든 extension·role·권한·외부 의존성을 포괄하는 전체 운영 백업이라고 주장하지 않습니다. `/tmp` 파일은 장기 보관소가 아니므로 이 연습은 off-host 백업 검증도 아닙니다. [pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).

원본 `lab`과 복원한 `lab_m11_restore` 양쪽에서 다음 쿼리의 결과를 저장해 비교합니다.

```sql
SELECT 'users' AS entity, count(*) FROM commerce.users
UNION ALL SELECT 'products', count(*) FROM commerce.products
UNION ALL SELECT 'orders', count(*) FROM commerce.orders
UNION ALL SELECT 'order_items', count(*) FROM commerce.order_items
UNION ALL SELECT 'accounts', count(*) FROM commerce.accounts
ORDER BY entity;

SELECT count(*) AS orders, sum(total_amount) AS total_amount,
       min(ordered_at), max(ordered_at) FROM commerce.orders;

SELECT order_id / 1000 AS bucket,
       md5(string_agg(order_id::text || ':' || total_amount::text, ',' ORDER BY order_id)) AS signature
FROM commerce.orders GROUP BY order_id / 1000 ORDER BY bucket;

SELECT count(*) AS missing_parent
FROM commerce.order_items i LEFT JOIN commerce.orders o USING (order_id)
WHERE o.order_id IS NULL;
SELECT conname, contype, convalidated FROM pg_constraint
WHERE connamespace='commerce'::regnamespace ORDER BY conname;
```

선택한 signature는 order_id/금액만 검사하므로 모든 컬럼의 동일성 증명이 아닙니다. 필요 컬럼별 canonical 형식을 정하고 NULL·시간대·정렬·문자열 경계까지 고려해 검사 범위를 확장합니다. 데이터 검산 후 대표 쿼리와 잘못된 참조를 거절하는 제약 테스트를 수행합니다. 복원 종료 시각뿐 아니라 **검증 끝나고 서비스 가능해진 시각**까지 측정합니다.

### T 실험: 이름 있는 restore point로 PITR 검증

다음은 별도 환경에서 구현해야 하는 실험 사양입니다. 현재 Compose의 데이터 디렉터리·볼륨에 직접 복원하지 않습니다.

| 구성 요소 | 필요한 조건 |
| --- | --- |
| 원본 primary P | 일치하는 PG18 빌드, `wal_level`·`archive_mode` 확인, 성공을 정확히 반환하는 archive command/library |
| base backup B | 빈 전용 목적지, `pg_basebackup`과 backup manifest, 시작/끝 LSN 기록 |
| archive A | 원본 장애에도 남는 별도 보관소, 같은 파일 이름의 잘못된 덮어쓰기 방지, 성공/실패 지표 |
| restore R | 별도 data directory·포트·볼륨·역할, P와 다른 서버 식별, 같은 system identifier 계보 |
| 검증 원장 | DB 밖에 기록한 승인 ID·commit 응답 시간·restore point·목표 RPO/RTO |

실행 순서는 다음과 같습니다.

1. archive 설정과 파일 실제 도착을 검증합니다. `pg_stat_archiver`의 실패/성공과 저장소 파일을 대조합니다. 설정만 해 두고 base backup부터 만들지 않습니다.
2. P에서 물리 base backup을 별도 B에 받습니다. 해당 버전 `pg_basebackup`의 streaming WAL 포함 방식·권한을 선택하고 `pg_verifybackup`을 수행합니다. manifest 검증은 실제 restore를 대신하지 않습니다. [base backup](https://www.postgresql.org/docs/18/app-pgbasebackup.html), [백업 검증의 범위](https://www.postgresql.org/docs/18/app-pgverifybackup.html).
3. 실험 전용 ledger에 승인 주문 A/B를 넣고 COMMIT한 뒤 외부 원장에 응답을 기록합니다. `SELECT pg_create_restore_point('m11_before_bad_change');`의 LSN과 UTC 시각을 저장합니다. restore point는 잘못된 변경보다 먼저, 필요한 정상 commit보다 나중이어야 합니다.
4. 원본의 실험 ledger에서만 잘못된 UPDATE/DELETE를 COMMIT합니다. 이후 sentinel C를 COMMIT하여 복구 목표 뒤의 데이터도 구별할 수 있게 합니다. WAL을 switch하고 목표까지 필요한 archive 파일의 도착을 확인합니다.
5. R이 정지한 상태에서 **빈 전용 디렉터리**에 B를 복원합니다. 소유권·tablespace·설정 파일·네트워크 주소를 검토합니다. `restore_command`, `recovery_target_name='m11_before_bad_change'`, 목표 계보의 `recovery_target_timeline`, `recovery_target_action='pause'`, `recovery.signal`을 구성합니다. 구체 경로는 환경 설계서에 기록합니다. [복구 목표 설정](https://www.postgresql.org/docs/18/runtime-config-wal.html#RUNTIME-CONFIG-WAL-RECOVERY-TARGET).
6. R을 기동하고 시작점, 복구 목표 도달, pause를 로그에서 확인합니다. read-only 연결로 A/B는 존재하고 잘못된 변경·sentinel C는 반영되지 않았는지 검증합니다. 목표를 못 찾았는데 임의로 승격하지 않습니다.
7. 검증 후 계획한 방식으로 recovery를 종료하고 새 timeline 및 history를 기록합니다. 서비스 연결을 R로 바꾼 시험에서 읽기·쓰기·제약·권한·업무 검산을 수행합니다.
8. 원본과 독립된 두 번째 restore R2에 같은 입력으로 재복원합니다. archive 한 구간이 없는 부정 시험은 **복사된 시험 archive**에서 수행하고 원본 archive를 훼손하지 않습니다. 누락을 성공으로 오판하지 않는지 확인합니다.

**예상 증거:** S는 원본/복원 결과 비교와 소요 시간. T는 base/WAL manifest, archive 연속성, 목표 LSN·timeline, recovery 로그, A/B/C 검산, 실제 RPO/RTO와 실패 시험 결과입니다.

**실패 양상:** 살아 있는 데이터 디렉터리를 파일 복사해 일관된 백업이라고 부르기, WAL 일부 유실, 역할/extension/비밀정보 의존성 누락, archive command가 실패해도 성공을 반환, 목표 이후 데이터가 있는데 기동만으로 성공 판단.

**산출물·통과:** S는 별도 DB restore와 업무 검산이 실제로 성공해야 합니다. T는 동일 입력으로 2회 복원, A/B/C 판정, archive 누락의 탐지, 선언한 RPO/RTO 측정을 통과해야 합니다. 설계서만 있으면 T는 `설계 완료/실행 미완료`입니다.

## M12. 복제의 진행 위치와 장애조치의 책임

**선수 지식:** M06 동시성, M11 LSN/timeline/복구. **범위:** 현재 단일 노드의 준비 상태 관찰은 S, 복제·장애조치 실험은 T.

물리 복제는 같은 클러스터 계보의 WAL을 전달하고 replay하여 데이터 상태를 따라갑니다. 송신, 수신, 디스크 flush, replay는 서로 다른 지점입니다. 비동기 복제에서 primary가 응답한 commit이 standby에 아직 없을 수 있습니다. 동기 복제도 선택한 acknowledgment 단계와 standby 구성에 따라 내구성·가용성·읽기 가시성 보장이 달라집니다. [streaming/synchronous replication](https://www.postgresql.org/docs/18/warm-standby.html).

논리 복제는 publication/subscription과 replica identity를 사용해 변경을 행 수준으로 적용합니다. DDL, sequence 상태 등 모든 객체가 자동으로 동기화되는 것은 아닙니다. slot은 소비자가 필요로 하는 WAL 또는 catalog horizon을 보존하게 하므로 멈춘 소비자가 디스크와 vacuum에 영향을 줄 수 있습니다. restart_lsn과 confirmed_flush_lsn은 같은 의미가 아닙니다. [논리 복제 제한](https://www.postgresql.org/docs/18/logical-replication-restrictions.html), [논리 decoding](https://www.postgresql.org/docs/18/logicaldecoding-explanation.html), [slot 컬럼](https://www.postgresql.org/docs/18/view-pg-replication-slots.html).

### S 관찰: 구성되었다고 가정하지 않기

```sql
SHOW wal_level;
SHOW max_wal_senders;
SHOW max_replication_slots;
SELECT pg_is_in_recovery();
SELECT application_name, state, sync_state, sent_lsn, write_lsn, flush_lsn, replay_lsn
FROM pg_stat_replication;
SELECT slot_name, slot_type, active, restart_lsn, confirmed_flush_lsn,
       xmin, catalog_xmin, wal_status, safe_wal_size
FROM pg_replication_slots;
```

현재 Compose에는 replica가 없습니다. 결과가 0행이면 “지연 0”이 아니라 “해당 연결/slot 없음”으로 해석합니다. 관찰을 위해 필요 없는 slot을 만들지 않습니다.

### T 실험 사양: physical P→S와 logical P→L

서로 다른 두 실험 토폴로지를 구성합니다. 물리 standby S는 P의 base backup에서 시작하고, logical subscriber L은 독립 클러스터와 미리 맞춘 스키마를 사용합니다. logical 시험에는 `wal_level=logical` 및 적절한 slot/sender/worker 한도가 필요하며 재시작 여부를 확인합니다. 실제 host·port·역할·credential 보관 방법을 기록합니다. [논리 복제 설정](https://www.postgresql.org/docs/18/logical-replication-config.html).

| 시험 | 주입·관찰 | 통과 증거 |
| --- | --- | --- |
| physical 전송/재생 | 학습용 S의 replay를 일시 정지하고 P에 sentinel을 commit. send/write/flush/replay 위치와 S 조회 결과 기록 후 replay 재개 | flush되어도 replay 전에는 조회 불가할 수 있음을 확인. 재개 뒤 sentinel 도달 |
| 비동기 장애 | 원장에 ACK된 ID를 남긴 뒤 P를 실험 환경에서 중단, S의 수신/재생 상태 확인 | 승인 ID와 실제 복원 ID의 차이로 손실 계산. 손실 0을 가정하지 않음 |
| 동기 구성 | 선택한 sync standby가 일시 불가할 때 commit 대기와 timeout을 기록 | 사용한 sync 모드의 보장·가용성 비용과 장애 해제 절차 설명 |
| logical apply | insert/update/delete를 P에서 실행하고 L의 PK·금액 결과 비교 | replica identity, 적용 오류, 초기 동기화 완료를 확인 |
| 멈춘 소비자 | L의 소비를 제한 시간 중단하고 P의 WAL 생성량·slot retention 증가 관찰 | restart/confirmed LSN 차이, 저장 공간 예산·경보·중단 조건 확인 후 재개 |
| 중복/재연결 | 사용한 CDC 소비자가 재시작 시 마지막 처리 지점을 복원하도록 구현 | 엔진·드라이버 보장을 확인하고 event key/offset으로 중복 부작용 방지 |
| logical schema 변경 | L/P에 호환되지 않는 시험 변경을 계획된 순서로 적용·수정 | DDL 자동 전파를 가정하지 않는 migration 순서와 회복 로그 |

slot retained byte의 한 관측은 다음처럼 계산할 수 있지만, 해당 값 전체가 지금 삭제 가능한 WAL의 정확한 양이라는 뜻은 아닙니다.

```sql
SELECT slot_name, active, restart_lsn,
       pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS distance_bytes
FROM pg_replication_slots WHERE restart_lsn IS NOT NULL;
```

허용 공간과 최대 시험 시간을 먼저 정합니다. 중단된 slot을 무조건 삭제하는 것은 소비 연속성을 잃을 수 있으므로 소유자·재동기화 비용·중단 이유를 확인한 결정이 필요합니다. PG18 `idle_replication_slot_timeout` 같은 설정도 실제 버전의 무효화 시점·조건을 확인합니다. [복제 설정](https://www.postgresql.org/docs/18/runtime-config-replication.html).

### 장애조치 설계의 필수 조건

S 승격만으로 서비스 장애조치가 끝나지 않습니다. P의 재접속/쓰기를 차단하는 fencing, 클라이언트 endpoint 전환, 새 timeline 기록, 오래된 P를 새 primary에 다시 합류시키는 절차, logical slot/consumer 상태와 read-after-write 정책을 포함합니다. 복제는 consensus 기반 leader 선출 기능을 자동 제공하지 않습니다. 네트워크 단절과 진짜 primary 사망을 구별하지 못한 상태에서 양쪽을 writable로 만들지 않는 설계를 제출합니다. [failover](https://www.postgresql.org/docs/18/warm-standby-failover.html), [pg_rewind](https://www.postgresql.org/docs/18/app-pgrewind.html).

**실패 양상:** lag가 NULL/0이면 건강하다고 판정, flush와 replay 혼동, 논리 복제를 전체 DB 백업으로 사용, 장기 slot 방치, 승격 뒤 old primary 재등장으로 이중 쓰기 발생, CDC의 exactly-once를 offset만으로 주장.

**산출물·통과:** topology/ACK 경계/복구 순서도와 위 시험 중 physical 지연, logical slot, 장애조치 3종의 실제 로그가 필요합니다. 양쪽 sentinel 검산과 외부 원장의 승인 ID 대조를 통과하고 불가능한 보장은 명시합니다. T 환경이 없으면 설계 및 S 관측까지만 완료로 표시합니다.
