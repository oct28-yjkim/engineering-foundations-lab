# SU07–SU08. 실시간 알림과 복구 가능한 업무 상태

[커리큘럼](../curriculum.md) · 이전: [RLS/API](03-rls-api.md) · 다음: [Storage/Functions](05-storage-functions.md)

<a id="su07"></a>
## SU07 WAL에서 WebSocket까지 · LOCAL-PREP / BUILD

**선수 조건:** SU05–06, transaction commit/WAL/logical replication slot. [PostgreSQL 트랙](../../../databases/postgresql/README.md)의 복제 개념을 보충하되 실제 Supabase PostgreSQL 버전을 확인합니다.

### 원리

Postgres Changes는 publication/logical decoding 경로의 변경을 구독자에게 전달합니다. 원본 DB의 commit, slot의 처리 위치, Realtime의 처리, WebSocket 전송, client handler 반영은 각각 다른 사건입니다. WAL에 남았다는 사실은 끊긴 browser가 원하는 위치부터 모든 이벤트를 다시 받을 수 있다는 보장이 아닙니다. [Realtime architecture](https://supabase.com/docs/guides/realtime/architecture), [Realtime concepts](https://supabase.com/docs/guides/realtime/concepts)

Postgres Changes는 변경과 구독자별 권한 검사를 연결하므로 쓰기량뿐 아니라 fan-out·policy 비용·구독 수가 병목을 만듭니다. publication에 table이 있고 client가 subscribe했다는 사실만으로 접근 정책이 검증된 것은 아닙니다. DELETE event의 권한/old row 처리에는 일반 SELECT와 다른 제약이 있으므로 “SQL DELETE에 RLS가 작동하지 않는다”와 혼동하지 않습니다. `REPLICA IDENTITY FULL`도 무조건 전체 old payload를 안전하게 전달하는 보장은 아닙니다. [Postgres Changes](https://supabase.com/docs/guides/realtime/postgres-changes)

알림은 화면의 cache를 무효화하는 신호로 사용할 수 있습니다. 업무의 authoritative state는 RLS를 거친 DB 조회로 재조정합니다. 정확한 event history가 필요하면 별도의 append-only event/outbox, cursor, retention, replay 계약을 설계합니다. 이를 마련하지 않은 Realtime 채널을 [Kafka](../../../streaming/kafka/README.md)의 durable consumer offset 모델과 같은 것으로 설명하지 않습니다.

### 실험: 빠진 알림과 남아 있는 데이터

SU05의 non-sensitive fixture를 재사용하되 oracle 18개 테스트와 동시에 실행하지 않습니다. 관리 로컬 SQL에서 다음 읽기 전용 조사를 먼저 수행합니다.

```sql
SELECT pubname, puballtables FROM pg_publication;
SELECT pubname, schemaname, tablename FROM pg_publication_tables
WHERE tablename = 'su_lab_tasks';
SELECT slot_name, plugin, slot_type, active, restart_lsn, confirmed_flush_lsn
FROM pg_replication_slots;
SELECT relreplident FROM pg_class WHERE oid='public.su_lab_tasks'::regclass;
```

확인된 local `supabase_realtime` publication에 아직 포함되지 않은 경우에만 `ALTER PUBLICATION supabase_realtime ADD TABLE public.su_lab_tasks;`를 실행합니다. publication이 없으면 배포 버전의 문서/설정을 확인하고 다른 publication을 덮어쓰지 않습니다. slot을 삭제하거나 직접 LSN을 진행시키는 실험은 이 범위가 아닙니다.

BUILD harness에서 A/B 사용자 client가 자신의 실제 JWT로 table의 INSERT/UPDATE를 구독합니다. 다음은 이미 로그인된 `clientA`가 존재한다는 전제의 핵심 부분이며 완성 앱이 아닙니다.

```javascript
const seen = [];
const channel = clientA.channel('su07-a-exp1')
  .on('postgres_changes', {
    event: 'UPDATE', schema: 'public', table: 'su_lab_tasks'
  }, change => seen.push({ id: change.new.id, title: change.new.title }))
  .subscribe(status => recordStatus(status));
// SUBSCRIBED 확인 뒤 writer를 시작한다. 종료 시 removeChannel(channel).
```

1. writer가 A의 `a1` title을 `v01`~`v10`으로 순차 commit합니다. 별도 입력 원장에 요청 ID·예상 최종값·성공/unknown을 저장합니다.
2. `v04` 뒤 A client를 의도적으로 disconnect하고 `v05`~`v08`을 commit합니다. reconnect 후 `v09`~`v10`을 보냅니다.
3. client가 받은 event 목록과, 쓰기를 멈춘 뒤 RLS REST로 읽은 `a1`의 최종 `v10`을 구분해 비교합니다. B client에 A title이 노출되지 않았는지 검사합니다.
4. 전체 tenant 행을 pagination으로 다시 읽어 client cache를 교체합니다. 누락 event가 있어도 최종 PK/title 집합이 DB oracle와 일치하는지 확인합니다.

다른 동시 쓰기가 없는 마지막 full refresh는 작은 실험의 복구 방법입니다. 이를 “동시 쓰기 중 race 없는 snapshot+stream 알고리즘”이라고 주장하지 않습니다. 확장 과제로 source version, tombstone, snapshot boundary, overlap/dedup를 포함한 reconciliation protocol을 설계합니다. `updated_at > 마지막시각`만으로 삭제·동일 timestamp·commit 순서 문제를 모두 해결할 수 없습니다.

### 삭제와 부하의 반례

별도 fixture에서 `REPLICA IDENTITY DEFAULT/FULL`을 한 변수로 비교하여 UPDATE/DELETE의 실제 `old/new` 필드, filter 동작, 타 tenant 구독의 payload를 확인합니다. delete event에서 record 존재 자체가 민감한 요구사항이면 전용 private Broadcast 또는 다시 조회하는 방식 등 대안을 선택합니다. 제품 버전별 관찰과 공식 제한을 기록하고 과거 예제의 “항상 필터 불가/항상 전체 old”를 단정하지 않습니다.

구독자1/10/50과 같은 제한된 local 부하를 쓰기율 고정으로 비교합니다. 실제 요청 수·RLS query 비용·지연·slot lag·오류·DB 연결 수를20개 구간 이상 측정합니다. client를 느리게 만들었다고 slot이 반드시 해당 client를 위해 WAL을 영구 보관하는 것은 아닙니다. 각 단계의 queue와 acknowledgement를 소스로 확인합니다.

**증거·통과:** publication/slot 관찰, 입력 commit 원장, 수신 목록, offline 누락 또는 제한 관찰, 최종 tenant 상태의 정확한 일치, 타 tenant payload 누출0건. `received_count == writes`만으로 정확성을 판단하지 않으며 없는 누락을 만들어 기록하지 않습니다. [소스 지도](../source-reading.md)의 replication → authorization → channel 경로를 추적합니다.

<a id="su08"></a>
## SU08 Broadcast, Presence, 권한 캐시와 backpressure · LOCAL-PREP / BUILD

**선수 조건:** SU04, SU07, async queue와 bounded memory. private channel 정책 변경은 독립 로컬 프로젝트에만 적용합니다.

### 원리

Broadcast는 메시지를 전달하고 Presence는 연결된 client의 상태를 병합합니다. Broadcast의 server ACK는 모든 client가 업무 결과를 반영했다는 ACK가 아닙니다. 현재 일부 버전에는 **private 채널의 DB-origin 메시지에 제한된 Broadcast Replay**가 있습니다. SDK·보관기간·최대 반환 개수·origin 제약을 확인해야 하며 무제한 history나 durable consumer group 재생으로 일반화할 수 없습니다. [Broadcast와 Replay](https://supabase.com/docs/guides/realtime/broadcast)

Presence의 join/leave는 상태 재조정 과정에서도 발생할 수 있습니다. 연결 상태를 결제 완료나 출근 원장으로 사용하지 않고, 고빈도 cursor 이동을 무조건 Presence track으로 보내지 않습니다. client가 쓴 presence payload의 `user_id`도 그 자체로 서버 검증된 신원이 아닙니다. [Presence](https://supabase.com/docs/guides/realtime/presence)

private channel 권한은 `realtime.messages`의 정책과 JWT/topic 등을 이용해 가입 시 평가됩니다. channel 이름을 tenant ID로 짓거나 client에서 `private:true`를 선택하는 것만으로 정책이 만들어지지 않습니다. 장기 connection의 membership 철회와 JWT 갱신 시 권한 재평가 시점은 별도로 검증합니다. [Realtime authorization](https://supabase.com/docs/guides/realtime/authorization)

### 실험: room 이름을 바꿔도 tenant를 건널 수 없는가

현재 공식 환경에서는 `realtime.messages` RLS가 이미 켜져 있으므로 아래에서 `ALTER TABLE ... ENABLE RLS`를 추가하지 않습니다. 소유권/관리 정책과 실제 배포 기능을 먼저 확인합니다. 정책은 기존 permissive policy와 OR 결합되므로 광범위 허용 policy가 있는 프로젝트에서는 먼저 그것을 조사합니다. 이 실험 때문에 다른 정책을 삭제하지 말고 독립 프로젝트로 옮깁니다.

```sql
SELECT policyname, cmd, roles, qual, with_check
FROM pg_policies WHERE schemaname='realtime' AND tablename='messages';

CREATE POLICY su_lab_channel_read ON realtime.messages
FOR SELECT TO authenticated USING (
  extension IN ('broadcast','presence') AND EXISTS (
    SELECT 1 FROM public.su_lab_memberships m
    WHERE m.user_id=(SELECT auth.uid()) AND m.active
      AND (SELECT realtime.topic()) = 'su_lab:' || m.tenant_id)
);
CREATE POLICY su_lab_channel_write ON realtime.messages
FOR INSERT TO authenticated WITH CHECK (
  extension IN ('broadcast','presence') AND EXISTS (
    SELECT 1 FROM public.su_lab_memberships m
    WHERE m.user_id=(SELECT auth.uid()) AND m.active
      AND (SELECT realtime.topic()) = 'su_lab:' || m.tenant_id)
);
```

실제 SDK가 인증 상태를 Realtime에 반영하도록 설정한 뒤 `channel('su_lab:tenant_a', {config:{private:true,broadcast:{ack:true}}})`에 A와 B가 각각 가입합니다. A는 성공하고 B·signed-out·membership 없는 사용자에게 A payload가 보이면 안 됩니다. A에서 `event_id`1~100, `source_version`을 보내고 서버 ACK 목록과 A의 다른 browser 수신 목록을 분리합니다. payload에는 비밀·실제 PII를 넣지 않습니다.

Presence에는 client instance별 key를 사용해 A browser 두 개를 연결하고 하나를 갑자기 종료합니다. 즉시 leave를 받는다고 가정하지 말고 실제 상태 수렴 시간을 측정합니다. user 수와 connection 수는 다를 수 있습니다. membership 제거 뒤 기존 채널·재가입·token 갱신 각각의 허용 시점을 표로 남깁니다. “매 메시지마다 live membership 확인”이 관찰되지 않았다면 그 보장을 주장하지 않습니다.

### 작은 backpressure와 Replay 과제

수신 handler에 의도적 지연을 넣고 메모리 queue 상한100개, 초과 시 `needsResync=true`와 snapshot 재조회 규칙을 구현합니다. 오래된 cursor update는 최신 version으로 coalesce할 수 있지만 결제 이벤트를 같은 방식으로 버리면 안 됩니다. 쓰기100/초를 목표로 해도 실제 달성량과 drop/resync 횟수를 함께 보고하고 local 자원 한도를 넘기지 않습니다.

Replay 지원을 확인한 경우에만 별도 private topic에 DB-origin 이벤트30개를 남기고 제한된 replay 응답과 원장을 대조합니다. client-origin Broadcast와 같은 보장을 받는지, 요청 limit보다 큰 gap을 앱이 어떻게 탐지하는지 검증합니다. 지원되지 않으면 기능 없음으로 기록하고 DB snapshot 복구를 검증합니다. [프로토콜](https://supabase.com/docs/guides/realtime/protocol)에서 join, heartbeat, access token 갱신, reply와 app ACK를 구분합니다.

**통과:** 금지 채널 payload0건, ACK 범위 설명, queue 상한 준수, reconnect 후 oracle 수렴, Presence 비업무원장 선언. 증거는 join matrix·권한 철회 시간선·메모리/queue 곡선·replay 조건표이며, Realtime을 전체 이벤트 저장소로 가정한 설계는 재수행합니다.
