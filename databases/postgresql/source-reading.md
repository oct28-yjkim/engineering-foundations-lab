# PostgreSQL 18 소스 읽기 지도

목표는 함수 이름 암기가 아니라 **SQL 관측 → 책임 경계 → 입력 상태 → 보호할 불변식 → 실패/해제 경로**를 연결하는 것입니다. 먼저 강의 실험으로 관측한 현상을 설명하고 그 설명이 코드와 맞는지 확인합니다.

## 버전과 빌드의 연결

아래 링크는 비교 가능한 출발점으로 **공식 `REL_18_0` 태그**를 사용합니다. 실제 `postgres:18` 컨테이너는 다른 18.x일 수 있습니다. 링크의 태그를 그대로 실험에 맞는 소스라고 주장하지 말고 `SELECT version()`의 버전과 이미지 digest를 기록한 뒤 해당 release tag/commit으로 바꿉니다. distribution patch가 있다면 그 차이도 남깁니다. `REL_18_STABLE` 같은 움직이는 브랜치를 사용했으면 최종 commit SHA를 반드시 고정합니다.

```sql
SELECT version(), current_setting('server_version_num');
```

소스 checkout에서 수행할 읽기 전용 확인:

```bash
git describe --tags --always
git rev-parse HEAD
git status --short
rg -n 'PG_VERSION|PG_MAJORVERSION' src/include/pg_config.h.in
```

`pg_config.h.in`은 템플릿이므로 실제 빌드 값은 생성된 `pg_config.h`, `pg_config --version`, 빌드 로그로 확인합니다. 운영 바이너리와 debug 바이너리의 compile option·extension·설정을 비교합니다. 결과 보고서에는 `runtime version / image digest / source tag / commit SHA / compiler / configure flags`를 포함합니다.

## 구현 경로별 지도

각 행에서 함수/구조체를 먼저 찾고 caller 1단계·callee 1단계를 따라갑니다. 행 전체를 읽는 것이 완료 조건은 아니며, 오른쪽 질문을 강의 증거와 연결해야 합니다. 일부 함수는 static이거나 버전별 signature가 달라질 수 있습니다. 실제 checkout에서 `rg -n`으로 위치를 다시 확인합니다.

| 연결 모듈 | 공식 소스 경로·출발 심볼 | 확인할 질문·연결할 증거 |
| --- | --- | --- |
| M02 | [`src/backend/tcop/postgres.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/tcop/postgres.c) · `exec_simple_query`, `PostgresMain` | protocol message 처리와 SQL 실행, transaction 시작/종료 경계는 어디인가? 세션 시간표 연결 |
| M01–02 | [`src/backend/parser/analyze.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/parser/analyze.c) · `parse_analyze_fixedparams` | raw syntax가 의미가 확인된 Query로 바뀔 때 타입·이름은 어떻게 해석되는가? 잘못된 타입 SQL 연결 |
| M07 | [`src/backend/optimizer/plan/planner.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/optimizer/plan/planner.c) · `standard_planner` | Query에서 PlannedStmt까지 어떤 planner state와 하위 계획을 거치는가? EXPLAIN 연결 |
| M02/M09 | [`src/backend/executor/execMain.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/executor/execMain.c) · `standard_ExecutorStart`, `standard_ExecutorRun` | executor state 초기화·실행·종료의 책임은 무엇인가? 계획 node와 실행 단계 연결 |
| M03 | [`src/include/storage/bufpage.h`](https://github.com/postgres/postgres/blob/REL_18_0/src/include/storage/bufpage.h) · `PageHeaderData` | lower/upper/special과 LSN이 pageinspect 출력의 어느 필드에 해당하는가? |
| M03/M05 | [`src/include/access/htup_details.h`](https://github.com/postgres/postgres/blob/REL_18_0/src/include/access/htup_details.h) · `HeapTupleHeaderData` | infomask·xmin/xmax·ctid가 각기 무슨 상태를 나타내는가? 한 숫자만 읽을 때 반례는? |
| M04 | [`src/backend/storage/buffer/bufmgr.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/storage/buffer/bufmgr.c) · `ReadBufferExtended`, `FlushBuffer` | pin/content lock/dirty를 누가 관리하는가? WAL-before-data가 어떤 분기에서 보장되는가? |
| M04 | [`src/backend/access/transam/xlog.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/access/transam/xlog.c) · `XLogFlush`, `CreateCheckPoint` | WAL flush 요청과 checkpoint의 책임이 어떻게 다른가? LSN 관측의 한계는? |
| M05 | [`src/backend/storage/ipc/procarray.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/storage/ipc/procarray.c) · `GetSnapshotData` | snapshot의 xmin/xmax/xip는 어느 진행 상태를 나타내는가? RC/RR 시간표 연결 |
| M05 | [`src/backend/access/heap/heapam_visibility.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/access/heap/heapam_visibility.c) · `HeapTupleSatisfiesMVCC`, `SetHintBits` | visible 판정의 분기 순서와 hint bit 변경 조건은 무엇인가? 읽기가 dirty page를 만들 수 있는가? |
| M06 | [`src/backend/storage/lmgr/predicate.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/storage/lmgr/predicate.c) · `CheckForSerializableConflictOut`, `PreCommit_CheckForSerializationFailure` | 읽기-쓰기 의존성의 기록과 abort 결정은 어떻게 나뉘는가? write skew 실험 연결 |
| M06 | [`src/backend/storage/lmgr/lock.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/storage/lmgr/lock.c) · `LockAcquireExtended` | 이미 보유한 lock·새 요청·대기의 분기를 구분할 수 있는가? pg_locks 연결 |
| M06 | [`src/backend/storage/lmgr/deadlock.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/storage/lmgr/deadlock.c) · `DeadLockCheck` | 대기 그래프의 cycle과 대기열 재배치 가능성을 어떻게 검사하는가? 40P01 연결 |
| M07 | [`src/backend/optimizer/path/costsize.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/optimizer/path/costsize.c) · `cost_seqscan`, `cost_index` | 행/페이지 추정과 CPU/I/O 가중치가 어떻게 비용으로 들어가는가? 단위가 ms가 아닌 이유는? |
| M07 | [`src/backend/utils/adt/selfuncs.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/utils/adt/selfuncs.c) · `eqsel` | equality selectivity가 상수·통계 유무에 따라 어떻게 달라지는가? correlated 조건 실험 연결 |
| M08 | [`src/backend/access/nbtree/nbtsearch.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/access/nbtree/nbtsearch.c) · `_bt_search`, `_bt_first` | root→leaf 탐색과 scan 시작, split 이후 오른쪽 이동 규칙은 무엇인가? skip scan 관련 호출도 탐색 |
| M08 | [`src/backend/access/nbtree/nbtinsert.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/access/nbtree/nbtinsert.c) · `_bt_doinsert` | uniqueness 검사·새 항목 삽입·split 비용을 어떻게 분리할 수 있는가? UPDATE/index 크기 연결 |
| M08 | [`src/backend/executor/nodeIndexonlyscan.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/executor/nodeIndexonlyscan.c) · `IndexOnlyNext` | VM 확인 뒤 heap으로 가는 조건은 무엇인가? Heap Fetches 반례 연결 |
| M09 | [`src/backend/executor/nodeHashjoin.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/executor/nodeHashjoin.c) · `ExecHashJoinImpl` | build/probe/batch/parallel 상태 전이는 어떤가? hash join EXPLAIN 연결 |
| M09 | [`src/backend/utils/sort/tuplesort.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/utils/sort/tuplesort.c) · `tuplesort_begin_heap`, `tuplesort_performsort` | 메모리 정렬에서 외부 정렬로 넘어가는 입력 상태는? Sort Method/temp I/O 연결 |
| M09 | [`src/backend/storage/aio/README.md`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/storage/aio/README.md) · AIO 설계 문서 | handle 소유·완료 처리와 sync/worker/io_uring 방법의 책임이 어떻게 나뉘는가? 환경별 실측 가능 범위 연결 |
| M10 | [`src/backend/access/heap/pruneheap.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/access/heap/pruneheap.c) · `heap_page_prune_and_freeze` | 어떤 버전·line pointer를 어떤 horizon 아래서 정리할 수 있는가? long snapshot 반례 연결 |
| M10 | [`src/backend/access/heap/vacuumlazy.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/access/heap/vacuumlazy.c) · `heap_vacuum_rel`, `lazy_scan_heap` | heap scan·index 정리·VM/freeze·통계 갱신은 어떻게 이어지는가? VACUUM VERBOSE 연결 |
| M11 | [`src/backend/access/transam/xlogrecovery.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/access/transam/xlogrecovery.c) · `PerformWalRecovery`, `ApplyWalRecord` | recovery target 판단, WAL record 적용, timeline 전환을 어떻게 구분하는가? PITR 로그 연결 |
| M12 | [`src/backend/replication/slot.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/replication/slot.c) · `ReplicationSlotAcquire` | slot 소유·지속 상태·retention 계산은 어디로 이어지는가? 중단 소비자 관측 연결 |
| M12 | [`src/backend/replication/logical/reorderbuffer.c`](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/replication/logical/reorderbuffer.c) · `ReorderBufferCommit` | transaction의 변경을 commit·stream·spill과 연결하는 경계는? logical 소비자 시험 연결 |

M14 테스트 경로는 [`src/test/regress`](https://github.com/postgres/postgres/tree/REL_18_0/src/test/regress), [`src/test/isolation`](https://github.com/postgres/postgres/tree/REL_18_0/src/test/isolation)입니다. 기능 SQL의 기대 결과와 동시성 schedule의 기대 순서를 서로 다른 방식으로 검사합니다.

## 읽기 실습의 최소 산출물

하나의 현상마다 다음 6항목을 1–2쪽으로 기록합니다.

1. 관측한 SQL·세션 순서·예상과 실제의 차이.
2. 정확한 source SHA와 경로/심볼. 이동하는 줄 번호만 적지 않습니다.
3. 함수의 입력 상태, 리턴값/오류, 수정하는 자료구조.
4. 호출자/피호출자와 소유권: snapshot, pin, lock, memory context의 생명주기.
5. 해당 분기가 보호하는 불변식, 분기를 제거했을 때 생길 반례.
6. 관측으로 확인한 부분과 코드에서 추론한 부분, 아직 확인하지 못한 부분.

처음에는 M05 가시성 경로가 적합합니다. 2세션 RR 실험을 축소하고 `GetSnapshotData`의 snapshot과 `HeapTupleSatisfiesMVCC`의 tuple 상태를 연결합니다. 그 다음 M07 추정, M10 정리 경로를 선택합니다. 호출 그래프에 모든 함수를 넣기보다 책임이 바뀌는 5–8개 경계를 설명합니다.

## B 환경: 빌드와 디버거

현재 Compose 이미지는 디버깅 환경을 제공한다고 보장하지 않습니다. Linux/WSL2의 전용 작업 디렉터리에 일치하는 소스를 준비하고, 운영 데이터와 분리된 debug cluster를 만듭니다. prerequisites는 해당 버전 [소스 설치 문서](https://www.postgresql.org/docs/18/installation.html), [configure 빌드](https://www.postgresql.org/docs/18/install-make.html), [회귀 테스트](https://www.postgresql.org/docs/18/regress.html)를 확인합니다.

소스 checkout의 올바른 태그가 확인된 뒤에만 실행할 **예시 빌드 명령**입니다. 의존 도구 설치와 새 클러스터 생성은 별도 환경 준비 과제입니다.

```bash
./configure --enable-debug --enable-cassert --prefix="$PWD/../pg18-debug"
make -j2
make check
```

설치/기동을 추가할 때는 전용 prefix/data directory/port를 명시하고, `initdb` 대상이 비어 있는지 먼저 확인합니다. 컨테이너와 같은 minor의 debug 서버에서 fixture를 재현한 다음 `SELECT pg_backend_pid()`로 **해당 실험 backend만** 선택합니다. 디버거로 멈춘 backend가 lock을 보유하고 다른 실험에 영향을 줄 수 있음을 기록합니다.

통과에는 기본 빌드·테스트 성공만으로 부족합니다. 최소 재현 1개에 대해 서로 다른 입력 2개가 어떤 분기 차이를 만드는지 stack·상태·SQL 결과를 제출하고, 회귀/격리 테스트 하나로 그 행동을 확인합니다. 결함이 없으면 엔진 코드를 억지로 수정하지 않습니다.
