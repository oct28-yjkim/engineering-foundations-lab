# ClickHouse 운영 실습: query·part·merge·replica로 원인 좁히기

[트랙](README.md) · [공통 운영 방법](../../operations/README.md) · [장애 보고서](../../operations/incident-report-template.md)

실습의 기본은 실제 서버의 **정확성·읽기량·지연·메모리·적재 상태**를 함께 관찰하는 것입니다. CPU라는 하드웨어 자원은 관측 항목이며 Python 모형 실행을 뜻하는 과정명으로 사용하지 않습니다. 아래 절차는 학습자가 실행할 과제이며 문서 작성 시 장애를 검증했다는 의미가 아닙니다.

<a id="basic-lab"></a>

## 기본 LAB: 정상 동작에서 장애 복구까지

**정상 기능 → 동작 원리 → 관측 → 제약 → 진단·복구** 순서의 입문 카드입니다. MergeTree에 넣은 행을 조회·집계한 뒤 읽기량, part·merge, 비동기 mutation을 관측합니다. [공통 LAB 계약](../../operations/lab-contract.md)에 따라 정상 결과를 먼저 검산한 뒤 아래 상세 절차로 진행합니다. 28주 심화는 선수 조건이 아니며, 이 카드 추가가 새 자동 실행기 제공이나 실제 장애 검증 완료를 뜻하지 않습니다.

| 단계 | 실행·관측·판정 |
| --- | --- |
| 정상 기능부터 | 아래 §2의 새 MergeTree fixture에 합성 20,000행을 넣고 `count()`, 알려진 `id=42`의 customer/payload를 확인합니다. 정상 SELECT 한 건의 결과와 query_id를 기록한 뒤 두 번째 동일 요청과 비교합니다. |
| 동작 원리 | ORDER BY 키→granule 선택→읽기량, INSERT→part→background merge, mutation 수락→실제 part 변경의 순서를 먼저 설명합니다. ACK·완료·업무 가시성을 같은 사건으로 보지 않습니다. |
| 직접 볼 지표·방법 | §1의 `system.query_log`에서 query_id별 read_rows/read_bytes·duration·exception을 보고, `system.parts/merges/mutations`에서 part 수·진행·실패 이유를 함께 조회합니다. 로그는 비동기이며 query bytes는 물리 disk I/O와 다릅니다. |
| 먼저 확인할 제약 | 기본 단일 MergeTree는 Keeper/replica가 없습니다. 소유 DB·20,000행 시작 fixture·query 메모리/시간 상한을 지키고 missing metric을 0으로 채우지 않습니다. tiny fixture의 빠른 merge/mutation으로 증상이 보이지 않을 수 있습니다. |
| 자주 마주치는 사건 2개 | §3 B: 최대 10번의 1행 INSERT와 별도 테이블의 동일 10행 batch를 비교해 part 증가를 진단합니다. §3 C: 자기 100행 mutation의 수락·진행·결과를 구분합니다. Too many parts나 긴 mutation 장애를 강제로 만들지는 않습니다. |
| 조치와 회복 oracle | 발생기를 멈추고 batch 크기/유입 설계를 검토합니다. B 후 20,010행, C 후 `id<100`의 정확한 100행 변경과 나머지 ID/값 보존을 확인합니다. mutation은 ROLLBACK으로 되돌릴 수 없으므로 변경 원장과 원본 fixture를 보존합니다. |
| 제공물·추가 준비 | 독립 Compose·SQL 및 아래 수동 절차를 제공합니다. 정상 기능과 관측을 먼저 실행하고, Keeper·ReplicatedMergeTree·replica 복귀는 별도 구축이 필요한 확장 LAB으로 표시합니다. |

두 사건의 결과가 예상과 다르면 관측한 상태를 기록하고 발생기/변경부터 멈춥니다. 정상 baseline·사건별 경쟁 가설·제한 조치·회복 oracle·미실행 범위를 [사건 보고서](../../operations/incident-report-template.md)에 남깁니다.

## 1. 환경과 기준선

[시작 안내](README.md)의 개인 로컬 Compose를 사용하고 context·기존 데이터·권한을 먼저 확인합니다. 기준은 26.8 계열이며 실제 patch/digest·build commit·설정·part 상태를 저장합니다. ClickHouse 공식 사이트는 rolling 문서이므로 필드/설정은 `DESCRIBE TABLE` 및 실제 버전과 대조합니다. 없는 관측 항목을 0으로 채우지 않습니다.

```sql
SELECT version(), hostName(), timezone();
DESCRIBE TABLE system.query_log;
SELECT event_time, query_id, type, query_duration_ms, read_rows, read_bytes,
       result_rows, memory_usage, exception_code
FROM system.query_log
WHERE event_time>=now()-INTERVAL 5 MINUTE AND is_initial_query=1
  AND type IN ('QueryFinish','ExceptionWhileProcessing','ExceptionBeforeStart')
ORDER BY event_time DESC LIMIT 30;
SELECT query_id, elapsed, read_rows, read_bytes, memory_usage FROM system.processes;
SELECT database,table,partition_id,count() AS active_parts,
       sum(rows) AS rows,sum(bytes_on_disk) AS disk_bytes
FROM system.parts WHERE active AND database IN ('lab','ch_course')
GROUP BY database,table,partition_id ORDER BY active_parts DESC LIMIT 20;
SELECT database,table,elapsed,progress,num_parts,total_size_bytes_compressed,memory_usage
FROM system.merges;
SELECT database,table,mutation_id,create_time,parts_to_do,is_done,latest_fail_reason
FROM system.mutations WHERE NOT is_done LIMIT 20;
```

동일 workload에서 10초 간격·5분을 기본 관측 창으로 사용합니다. `system.query_log`는 비동기이며 아직 안 보인다고 실패로 판정하지 않습니다. 대기 후 기록하거나 소유 실습에서만 `SYSTEM FLUSH LOGS`를 명시적 관리 작업으로 수행합니다. raw query·예외 내용에 비밀이 없는지 확인한 뒤 제출합니다.

| 지표 | 형식·단위·시간 창 | 함께 구별할 것 |
| --- | --- | --- |
| `query_duration_ms` | 완료 event의 duration, ms; 5분 표본 분포 | client 전체 latency와 다름; 표본 수·실패 요청 포함 |
| `read_rows/read_bytes` | query별 누적 작업량, row/byte; query_id 단위 | 결과 행 수, pruning, 압축/OS 실제 disk I/O와 구별 |
| query log `memory_usage` | query event의 메모리 사용 기록, byte | event type·버전의 집계 의미 확인; process RSS·전체 서버 peak와 다름 |
| active part 수·`parts_to_do` | gauge, 개; 10초 추세 | partition별 유입·merge/mutation 수행률·장애 |
| `system.events.value` | event별 누적 counter; 같은 uptime의 Δ/초 | 여러 세션 혼합; query ProfileEvents와 다른 범위 |
| replica queue·`absolute_delay` | gauge, 항목 수/초 | queue 원인·Keeper 상태·업무 marker의 실제 가시성 |

근거: [query_log](https://clickhouse.com/docs/operations/system-tables/query_log), [merges](https://clickhouse.com/docs/operations/system-tables/merges), [replicas](https://clickhouse.com/docs/operations/system-tables/replicas). 서버 평균 지연만으로 특정 query 악화를 숨기지 않습니다.

## 2. 한정된 개인 fixture

쓰기·DDL은 **로컬 합성 데이터 실습을 선택한 경우만** 실행합니다. `ops_ch_01`이 있으면 새 이름을 사용하며 덮어쓰지 않습니다. 최대 20,000행·동시 query 2개·각 SELECT 10초·전체 사건 2분, 메모리는 query별 256MiB로 제한합니다. 기본 Compose의 자원 제한 유무도 별도로 확인합니다.

```sql
CREATE DATABASE ops_ch_01;
CREATE TABLE ops_ch_01.events(id UInt64, customer UInt64, payload String)
ENGINE=MergeTree ORDER BY id;
INSERT INTO ops_ch_01.events
SELECT number, number%100, repeat(toString(number),8) FROM numbers(20000);
```

## 3. 사건별 조사와 회복

### A. 동일한 결과인데 SELECT 비용이 커졌다

가설은 key pruning 실패, plan 변화, 동시 merge/I/O 경쟁입니다. 동일 fixture에서 `EXPLAIN indexes=1 SELECT count() FROM ops_ch_01.events WHERE id=42`와 `WHERE customer=42`를 비교합니다. 이는 서로 다른 필터이므로 서로 같은 결과인 A/B 성능 주장으로 쓰지 않고 **선택된 granule의 차이를 진단하는 대조군**으로 사용합니다. 각 SELECT에 `SETTINGS max_execution_time=10,max_memory_usage=268435456,max_threads=2`를 붙이고 query_id·read_rows·예외를 기록합니다.

**조치:** 문제가 되는 실제 workload의 같은 predicate를 유지한 채 정렬 키/투영/index 대안을 새 실습 테이블에서 비교합니다. global max_threads나 memory를 우선 올리지 않습니다. **롤백:** 기존 테이블 유지, query별 설정 종료. **회복:** 같은 결과 계약과 query별 읽기량·지연 분포를 검산합니다. 해당 counter는 physical disk read byte와 같지 않습니다.

### B. 작은 INSERT가 많고 part가 늘어난다

가설은 작은 batch, partition fan-out, merge 처리량 부족입니다. fixture의 `id>=20000` 범위에 **최대 10회, 매번 1행**을 넣고 각 회의 ACK 지연과 `system.parts`를 기록합니다. 그 뒤 다른 새 테이블에 같은 10행을 한 batch로 넣어 비교합니다. merge 속도에 따라 active part 차이가 곧 사라질 수 있으므로 재현 실패도 유효한 결과입니다.

**확인:** 유입 행/초·INSERT 수/초와 partition별 part 수, `system.merges` 진행 및 서버 오류를 대조합니다. part 수만으로 `Too many parts`를 재현했다고 쓰지 않습니다. **조치:** batch 합치기/유입 제한을 평가하고 async insert는 ACK·재시도 계약을 별도 검토합니다. **롤백:** 부하 발생 즉시 중지; merge를 강제로 멈추거나 `OPTIMIZE FINAL`을 기본 조치로 실행하지 않습니다. **회복:** insert 오류 0, fixture 행 수 20,010, part 추세가 안정되며 미처리 작업이 감소합니다.

### C. ALTER UPDATE가 끝난 줄 알았는데 결과가 다르다

가설은 mutation 비동기 실행, 실패 part, 잘못된 결과 기대입니다. 자기 fixture에만 `ALTER TABLE ops_ch_01.events UPDATE payload='changed' WHERE id<100 SETTINGS mutations_sync=0;`을 한 번 실행합니다. `system.mutations`를 1초 간격·최대 30초 관측하고 `SELECT countIf(payload='changed') FROM ops_ch_01.events WHERE id<100;`를 확인합니다. 작은 데이터에서 즉시 완료되면 지연 장애는 미재현으로 기록합니다.

**조치:** `latest_fail_reason`·`parts_to_do`·disk 여유·진행 상태로 원인을 나누고 재발행 전 mutation ID를 확인합니다. **롤백:** mutation은 transaction ROLLBACK 대상이 아닙니다. 취소도 이미 바뀐 part를 되돌리지 않으므로 기존 데이터에 적용하지 않습니다. 실험 후 변경 100행을 기대 원장으로 보존하고, 복원이 필요하면 별도 원본 fixture에서 새 테이블을 만듭니다. **회복:** 작업 완료·실패 이유 없음·정확한 100행 변경·전체 수 일치. 근거: [system.mutations](https://clickhouse.com/docs/operations/system-tables/mutations).

### D. replica가 뒤처진다: Keeper인가, fetch/merge인가?

```sql
SELECT database,table,is_readonly,is_session_expired,queue_size,inserts_in_queue,
       merges_in_queue,absolute_delay,total_replicas,active_replicas
FROM system.replicas;
SELECT database,table,type,create_time,num_tries,last_exception
FROM system.replication_queue LIMIT 30;
```

기본 MergeTree 단일 노드에서는 0행이 정상이며 복제 건강을 뜻하지 않습니다. 별도 소유 ReplicatedMergeTree 토폴로지에서만 한 replica의 서비스 중단 최대 20초·전용 table INSERT 최대 100행·재시작을 사전 승인된 계획으로 수행합니다. Keeper quorum은 건드리지 않고 disk 여유/쓰기 오류가 한도를 넘으면 즉시 중단합니다.

**경쟁 가설:** Keeper session, 네트워크/fetch, 디스크/merge 병목. **조치:** 해당 계층 복구 및 유입 제한; queue 삭제·Keeper metadata 편집을 하지 않습니다. **롤백/회복:** 중단한 replica 재기동, session/read-only 회복, queue 감소, 모든 replica의 업무 ID/version 검산. `absolute_delay=0` 하나로 일관성·백업 복구를 통과시키지 않습니다. 별도 환경이 없으면 설계 과제로 남깁니다.

## 4. 운영 관문

기준선 + 실제 사건 2개 이상 + 경쟁 가설·원시 query/metric 증거·한정 조치·회복 검산을 제출합니다. 소스 설명은 이를 뒷받침하며 대체하지 않습니다. 단일 노드 통과와 replica/독립 restore/권한 검증은 별도 상태입니다. 종료 시 열린 부하/변경 설정이 없고 fixture 이름·누적 용량을 기록합니다.
