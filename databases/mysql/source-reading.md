# MySQL 소스·논문 읽기 지도

[커리큘럼](curriculum.md) · [실습](labs/README.md) · [평가](assessment.md)

목표는 한 SQL의 **server 계층 → handler → InnoDB 자료구조/동시성 → log → 응답** 경로를 관측값과 연결하는 것입니다. 파일 이름이나 함수 암기보다 해당 경로가 실행되는 조건과 반례를 설명합니다.

## 고정 기준과 검증 수준

확인일 2026-10-04. 기준은 **MySQL Community 8.4 LTS**, 소스 tag [`mysql-8.4.11`](https://github.com/mysql/mysql-server/tree/mysql-8.4.11), commit **`99960bf74fa919347e4f4e3ca47672f333d6e91f`**입니다. 아래 경로는 해당 commit의 GitHub tree에서 확인했고 read view·transaction 함수 일부 원문을 대조했습니다. C++ 빌드·MTR 실행은 수행하지 않았습니다.

선택 실행 이미지는 Docker Official Image [`mysql:8.4.11`](https://hub.docker.com/_/mysql)입니다. [8.4.11 릴리스 노트](https://dev.mysql.com/doc/relnotes/mysql/8.4/en/news-8-4-11.html)와 서버 응답을 함께 기록합니다. 이는 MySQL 전체의 영구적인 최신 버전이라는 뜻이 아닙니다. [8.4.12 노트](https://dev.mysql.com/doc/relnotes/mysql/8.4/en/news-8-4-12.html)는 MySQL Server Docker image만의 보안 갱신으로 설명되어 있으며, 확인 당시 `library/mysql:8.4.12`는 제공되지 않았습니다. Oracle 배포 이미지와 Docker Official Image의 tag를 자동으로 치환하지 않습니다. 실제 image digest·서버 버전·패키지 출처는 실행 환경에서 별도로 기록합니다.

MySQL Community·Enterprise 기능, InnoDB Cluster/Group Replication, NDB Cluster, MariaDB, Aurora MySQL은 동일 엔진/배포가 아닙니다. 이름이 비슷한 기능의 보장이나 소스를 그대로 가져오지 않습니다.

## 1. SQL 계층과 실행 엔진

| 모듈 | 고정 소스 | 확인할 질문 |
| --- | --- | --- |
| MY01 | [sql_parse.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/sql/sql_parse.cc) | command dispatch·parse·실행의 경계, SQL 오류와 transaction 종료가 항상 같은 사건인가? |
| MY01–02 | [handler.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/sql/handler.cc) / [ha_innodb.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/handler/ha_innodb.cc) | server와 storage engine 계약, row/index 접근·commit·오류 반환은 어떻게 이어지는가? |
| MY07 | [sql_optimizer.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/sql/sql_optimizer.cc) | predicate·cardinality·join order·access path 추정의 경쟁 대안은 무엇인가? |
| MY07–08 | [join_optimizer.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/sql/join_optimizer/join_optimizer.cc) | 대체 optimizer 구현의 진입 조건·feature gate를 확인하라. 파일이 있다고 모든 Community query가 이 경로를 쓴다고 주장하지 않는다. |
| MY08 | [composite_iterators.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/sql/iterators/composite_iterators.cc) | iterator 초기화/다음 행·materialization·집계 경계와 EXPLAIN ANALYZE의 rows/loops가 어떻게 연결되는가? |
| MY09 | [mdl.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/sql/mdl.cc) | metadata lock의 수명·대기 queue는 row lock과 어떻게 다른가? online DDL도 왜 기다릴 수 있는가? |

EXPLAIN은 관찰 수단이지 결과의 정답 oracle이 아닙니다. 작은 fixture의 합계·중복·NULL 의미를 먼저 검산하고 query shape·통계·설정을 기록합니다. EXPLAIN ANALYZE는 실제 실행이며 쓰기/side effect가 가능한 statement를 임의 대상으로 시험하지 않습니다.

## 2. InnoDB: 페이지·가시성·잠금

| 모듈 | 고정 소스 | 추적할 경계 |
| --- | --- | --- |
| MY02 | [btr0cur.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/btr/btr0cur.cc) | B-tree cursor·탐색·수정과 page latch. secondary→clustered 접근을 고정 2 I/O로 환산하지 않기 |
| MY03 | [buf0buf.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/buf/buf0buf.cc) / [mtr0mtr.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/mtr/mtr0mtr.cc) | buffer page 상태·pin/latch·mini-transaction 경계. mtr commit과 SQL transaction commit은 다르다. |
| MY03 | [log0write.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/log/log0write.cc) | log buffer·write·flush 완료와 LSN 관측의 의미. dirty data page flush와 혼동하지 않기 |
| MY04 | [read0types.h](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/include/read0types.h) / [read0read.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/read/read0read.cc) | `ReadView::changes_visible`, creator·상하 watermark·active transaction 집합과 view 생성/재사용 |
| MY04 | [row0sel.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/row/row0sel.cc) / [trx0purge.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/trx/trx0purge.cc) | consistent/current read 경로, 오래된 version 재구성, purge를 붙드는 view |
| MY05–06 | [lock0lock.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/lock/lock0lock.cc) / [lock0wait.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/lock/lock0wait.cc) | record/gap/next-key/insert-intention 호환성과 wait-for 탐색. CPU record S/X 표를 모든 lock type에 적용하지 않기 |

특히 read view의 `m_up_limit_id`는 **이 값보다 작은 transaction을 볼 수 있는 low watermark**, `m_low_limit_id`는 **이 값 이상을 볼 수 없는 high watermark**입니다. 변수 이름의 up/low를 직관으로 뒤집지 않습니다. 자기 transaction의 변경과 snapshot 당시에 active였던 transaction의 제외를 별도로 추적합니다. undo chain을 transaction ID 크기만으로 정렬하면 commit 순서·실제 변경 이력을 잃을 수 있습니다.

[InnoDB MVCC 문서](https://dev.mysql.com/doc/refman/8.4/en/innodb-multi-versioning.html)는 secondary index와 clustered record의 가시성 확인 관계도 설명합니다. covering index여도 실제 snapshot 검증에 clustered lookup이 필요할 수 있으므로 CPU `index-lookup`의 “covering=추가 lookup 0”은 명시한 정적 모형의 결과일 뿐입니다.

## 3. commit·복구·복제의 경계

| 모듈 | 고정 소스 | 반증 질문 |
| --- | --- | --- |
| MY03·06·10 | [trx0trx.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/trx/trx0trx.cc) | `trx_prepare_for_mysql`, `trx_commit_for_mysql`, `trx_commit_complete_for_mysql`, `trx_recover_for_mysql` 사이의 상태·flush 조건은? |
| MY10 | [log0recv.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/log/log0recv.cc) | redo 재생과 미완료 transaction 처리, page 상태와 log 경계는 무엇인가? |
| MY11 | [binlog.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/sql/binlog.cc) | binlog group commit의 flush/sync/commit과 InnoDB prepare·ACK의 관계. internal 2PC와 사용자 XA를 구별하라. |
| MY11–12 | [rpl_gtid_state.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/sql/rpl_gtid_state.cc) / [rpl_replica.cc](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/sql/rpl_replica.cc) | GTID 집합·receiver·applier·오류 상태. 받은 event, durable relay log, 적용된 업무 row는 같은 단계인가? |

[Redo](https://dev.mysql.com/doc/refman/8.4/en/innodb-redo-log.html), [binary log](https://dev.mysql.com/doc/refman/8.4/en/binary-log.html), [doublewrite](https://dev.mysql.com/doc/refman/8.4/en/innodb-doublewrite-buffer.html)를 구분합니다. doublewrite는 torn-page 보호 계층이지 redo·backup의 대체물이 아닙니다. fsync 성공의 실제 내구성은 OS·장치가 약속을 지킨다는 가정도 필요합니다. 로그를 찾았다는 사실만으로 media loss 복구나 replica 무손실 failover를 증명하지 않습니다.

## 4. 실제 테스트를 읽는 입구

- [consistent_snapshot.test](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/mysql-test/t/consistent_snapshot.test): view가 생기는 시점과 session 간 사건 순서를 표로 옮깁니다.
- [innodb-consistent.test](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/mysql-test/suite/innodb/t/innodb-consistent.test): consistent read의 expected result와 engine 설정을 연결합니다.
- [deadlock_detect.test](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/mysql-test/suite/innodb/t/deadlock_detect.test): 기다림과 cycle, rollback 범위의 검증 조건을 찾습니다.
- [deadlock_on_lock_upgrade.test](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/mysql-test/suite/innodb/t/deadlock_on_lock_upgrade.test): S→X upgrade가 단순 X 획득과 어떻게 다른지 반례를 만듭니다.

test file은 `mysql` client에 그대로 넣는 SQL이 아닙니다. MTR의 connection·send/reap·동기화·expected error 규칙이 포함됩니다. 고정 소스의 build/MTR 안내에 따라 별도 checkout을 준비하고 해당 테스트를 실행해야 합니다. 이 저장소의 Python mock PASS를 upstream MTR PASS로 기록하지 않습니다.

## 5. 논문 3편과 작은 실험

| 원문 | 읽기 목적 | 실험과 한계 |
| --- | --- | --- |
| Selinger 외, SIGMOD 1979, [Access Path Selection in a Relational Database Management System](https://research.ibm.com/publications/access-path-selection-in-a-relational-database-management-system) | cost 기반 access path·join order 선택의 가정 | skew·상관관계 fixture의 추정/실측 rows를 비교. System R 알고리즘을 MySQL optimizer의 동일 구현으로 부르지 않음 |
| Berenson 외, SIGMOD 1995, [A Critique of ANSI SQL Isolation Levels](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-95-51.pdf) | isolation 이름보다 현상·의존 관계·업무 불변식으로 판단 | RR/RC·write skew·locking read 시간표. 논문의 SI와 InnoDB RR을 무조건 동치로 놓지 않음 |
| Mohan 외, TODS 1992, [ARIES: A Transaction Recovery Method Supporting Fine-Granularity Locking and Partial Rollbacks Using Write-Ahead Logging](https://research.ibm.com/publications/aries-a-transaction-recovery-method-supporting-fine-granularity-locking-and-partial-rollbacks-using-write-ahead-logging) | WAL·redo/undo·failure model을 비교할 언어 | CPU `commit-recovery` 및 실제 복원 설계. InnoDB가 ARIES를 그대로 구현한다거나 CPU 모형이 ARIES 구현이라고 주장하지 않음 |

논문의 benchmark 숫자는 이 저장소의 실측 결과가 아닙니다. 단순 모형·실제 소규모 엔진·원 논문 환경 재현을 따로 기록합니다. 모든 논문 원문을 repository에 재배포하지 않고 출처 링크와 본인의 실험 기록을 남깁니다.

## 제출 계약

trace 한 개마다 입력 SQL·version/settings·독립 정답, symbol 5개·자료구조 2개, 상태 전이·동기화 경계, 실패 경로, 기존 test의 oracle, 본인 반례를 제출합니다. 정적 호출 경로와 실제로 관측한 실행 경로를 구분하고 아직 측정하지 않은 내용을 명시합니다. 소스 checkout·빌드 의존성·테스트 서버 설치는 자동 수행하지 않습니다.
