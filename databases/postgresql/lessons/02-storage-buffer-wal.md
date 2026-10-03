# M03–04. 저장 페이지, 버퍼, WAL과 내구성

## M03. 행을 바이트와 페이지로 내려가기

**선수 지식:** M01–02, byte·offset·파일. **범위:** S, 페이지 원시 관측은 E(`pageinspect`).

heap은 고정 크기 페이지의 집합입니다. 페이지에는 header, line pointer 배열, 빈 공간, tuple이 있고 ctid는 블록 번호와 item 위치를 가리킵니다. UPDATE는 새 버전을 만들 수 있으므로 ctid는 업무 기본키가 아닙니다. tuple header, NULL bitmap, 정렬 padding 때문에 컬럼 크기의 단순 합은 행/테이블 크기와 다릅니다. 큰 값의 압축·외부 저장은 TOAST가 맡습니다. VM은 가시성/동결 정보를, FSM은 빈 공간 탐색 정보를 제공합니다. [페이지 레이아웃](https://www.postgresql.org/docs/18/storage-page-layout.html), [TOAST](https://www.postgresql.org/docs/18/storage-toast.html), [VM](https://www.postgresql.org/docs/18/storage-vm.html), [FSM](https://www.postgresql.org/docs/18/storage-fsm.html).

### 실험: 논리 행, 물리 크기, 첫 페이지 연결

강의 전용 객체를 처음 한 번 만듭니다. 재실험할 때는 기존 결과를 먼저 저장한 뒤 다른 이름을 사용하거나 해당 테이블만 초기화합니다.

```sql
CREATE SCHEMA IF NOT EXISTS deep_lab;
CREATE TABLE deep_lab.m03_pages (
  id integer PRIMARY KEY, tag text NOT NULL, payload text
) WITH (fillfactor = 70);
INSERT INTO deep_lab.m03_pages
SELECT g, 'tag-' || g,
       (SELECT string_agg(md5((g * 1000 + s)::text), '') FROM generate_series(1, 100) s)
FROM generate_series(1, 1000) g;

SHOW block_size;
SELECT ctid, xmin, xmax, id, pg_column_size(payload), octet_length(payload)
FROM deep_lab.m03_pages ORDER BY id LIMIT 5;
SELECT pg_relation_filepath('deep_lab.m03_pages'),
       pg_relation_size('deep_lab.m03_pages') AS heap_main,
       pg_table_size('deep_lab.m03_pages') AS table_with_aux,
       pg_indexes_size('deep_lab.m03_pages') AS indexes,
       pg_total_relation_size('deep_lab.m03_pages') AS total;
SELECT reltoastrelid::regclass FROM pg_class
WHERE oid = 'deep_lab.m03_pages'::regclass;
```

`pg_table_size`는 TOAST·보조 fork를 포함하고 별도 인덱스 크기는 다른 함수로 봅니다. 저장된 압축률을 예단하지 말고 위 결과를 사용합니다. [객체 크기 함수](https://www.postgresql.org/docs/18/functions-admin.html#FUNCTIONS-ADMIN-DBSIZE).

E 실험은 고권한 학습 계정으로 확장이 사용 가능한 경우만 실행합니다.

```sql
SELECT name, installed_version FROM pg_available_extensions WHERE name = 'pageinspect';
CREATE EXTENSION IF NOT EXISTS pageinspect;
SELECT * FROM page_header(get_raw_page('deep_lab.m03_pages', 0));
SELECT lp, lp_flags, lp_len, t_xmin, t_xmax, t_ctid, t_infomask, t_infomask2
FROM heap_page_items(get_raw_page('deep_lab.m03_pages', 0));
```

page header의 lower/upper와 free space, SQL ctid와 `t_ctid`의 관계를 그립니다. `t_xmax`가 0이 아니라는 이유만으로 삭제된 행이라고 단정하지 않습니다. lock/MultiXact와 infomask를 함께 해석해야 하며 M05–06에서 다시 다룹니다. `pageinspect`는 MVCC로 필터링한 SQL 결과와 다른 물리 정보를 보여 줍니다. [pageinspect](https://www.postgresql.org/docs/18/pageinspect.html).

**반증 실험:** payload를 압축되기 쉬운 `repeat('x', 3200)`로 바꾼 별도 테이블과 크기를 비교합니다. 컬럼 순서를 바꾸거나 NULL 비율을 바꾼 1,000행 테이블로 “행 수가 같으면 크기도 같다”는 가설을 반증합니다.

**예상 증거:** 서로 다른 계층의 크기 값, 실제 block_size, TOAST relation 유무/크기, 가능한 경우 page header와 item 목록. raw page 한 번 읽기로 전체 테이블의 bloat를 계산하지 않습니다.

**실패 양상:** ctid를 영구 식별자로 저장하기, TOAST를 무조건 큰 파일이라고 가정하기, `pg_relation_size`만으로 전체 용량을 산정하기, 페이지 관측 중 동시 writer의 영향을 무시하기.

**산출물·통과:** 자기 테이블 페이지의 바이트 구조 그림, 크기 함수 4개 차이, 압축성 비교 결과를 제출합니다. E 환경이 없으면 페이지 부분은 문서 분석으로 표시하고 E 실측 관문은 미완료로 남깁니다. 소스의 `PageHeaderData`와 `HeapTupleHeaderData`를 그림에 연결합니다.

## M04. 버퍼 변경과 COMMIT 사이의 경계

**선수 지식:** M03, BEGIN/COMMIT/ROLLBACK. **범위:** S. OS crash/power-loss 시험은 T의 격리 복구 실험으로 미룹니다.

buffer pin은 사용 중인 버퍼의 교체를 막는 참조이며 content lock은 페이지 내용 접근을 조율합니다. dirty는 메모리 내용이 디스크와 다름을 나타냅니다. 같은 잠금이라고 해도 SQL row lock과 buffer content lock은 범위와 수명이 다릅니다. buffer hit는 디스크 요청을 안 했다는 관측일 뿐 CPU 비용이 없다는 뜻이 아닙니다. [buffer manager 구현](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/storage/buffer/bufmgr.c).

WAL-before-data 규칙은 영구 데이터 페이지를 내보내기 전에 해당 변경을 복구할 WAL이 안전하게 기록되도록 합니다. COMMIT 응답에 필요한 flush 경계는 `synchronous_commit`과 복제 설정에 달립니다. 보통의 로컬 동기 커밋은 모든 heap 페이지를 즉시 flush하지 않습니다. checkpoint는 이후 복구의 시작 범위를 제한하는 작업이며 모든 transaction의 COMMIT마다 수행되지 않습니다. [WAL 소개](https://www.postgresql.org/docs/18/wal-intro.html), [WAL 내부](https://www.postgresql.org/docs/18/wal-internals.html), [WAL 설정](https://www.postgresql.org/docs/18/runtime-config-wal.html).

LSN은 WAL 내 위치이고 시계 시간이 아닙니다. insert, write, flush 위치는 같은 개념이 아니며 timeline을 건너뛰어 숫자만 비교하면 계보를 잃습니다. `full_page_writes`는 checkpoint 이후 페이지의 첫 관련 변경 등에서 full-page image를 기록해 torn page 복구를 돕습니다. 정확한 byte 수는 페이지 상태·동시 작업·설정에 따라 달라집니다.

### 실험: ROLLBACK은 WAL과 I/O를 되감지 않는다

```sql
CREATE TABLE deep_lab.m04_wal (id integer PRIMARY KEY, value integer NOT NULL);
INSERT INTO deep_lab.m04_wal SELECT g, 0 FROM generate_series(1, 10000) g;
SELECT pg_current_wal_insert_lsn() AS before_lsn \gset

BEGIN;
EXPLAIN (ANALYZE, BUFFERS, WAL, TIMING OFF)
UPDATE deep_lab.m04_wal SET value = value + 1 WHERE id <= 1000;
ROLLBACK;

SELECT count(*) FILTER (WHERE value <> 0) AS changed_visible_rows
FROM deep_lab.m04_wal;
SELECT pg_wal_lsn_diff(pg_current_wal_insert_lsn(), :'before_lsn') AS cluster_wal_bytes;
SELECT pg_current_wal_insert_lsn(), pg_current_wal_lsn(), pg_current_wal_flush_lsn();
SELECT wal_records, wal_fpi, wal_bytes, stats_reset FROM pg_stat_wal;
SELECT * FROM pg_stat_checkpointer;
```

행의 논리 변경이 돌아가도 WAL byte 차분이 양수일 수 있음을 확인합니다. 차분은 클러스터 전체 값이므로 그 UPDATE만의 비용으로 단정하지 않습니다. 문장 단위 `EXPLAIN ... WAL` 관측과 같은 기간의 다른 backend 활동을 비교합니다. 롤백한 UPDATE도 나중에 회수해야 할 버전을 남길 수 있습니다.

같은 테이블에서 같은 READ를 3회 실행하고 `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)`의 shared read/hit를 기록합니다. shared read는 OS page cache hit에서도 생길 수 있어 물리 디스크 읽기 횟수와 같지 않습니다. `DISCARD ALL`은 OS/공유 버퍼의 cold cache를 만들지 않습니다. [EXPLAIN의 해석](https://www.postgresql.org/docs/18/using-explain.html).

**설계 과제:** default durability, `synchronous_commit=off`, synchronous standby의 3조건에서 “응답 직후 primary를 잃은 경우”의 보장을 표로 만듭니다. `fsync=off`로 속도를 만드는 실험 대신 보장이 어떻게 달라지는지 문서에서 설명합니다.

**실패 양상:** rollback했으니 부작용 없는 벤치마크라고 생각하기, LSN 차분을 해당 쿼리 전용 WAL 양으로 단정하기, checkpoint를 backup으로 취급하기, 평균 commit 시간만으로 tail latency를 무시하기.

**산출물·통과:** WAL/LSN/buffer 원본 출력, page write·WAL flush·COMMIT 응답의 순서도, 두 durability 설정의 장애 보장표를 제출합니다. 소스의 `XLogFlush`, `CreateCheckPoint`, `FlushBuffer`를 [소스 지도](../source-reading.md)에서 추적하고 SQL 관측만으로 검증할 수 없는 실제 장치 flush 경계도 설명합니다.
