# 선택 원리 부록: 인덱스·가시성·대기·복구 모형

이 부록은 필수 선행 과정이나 운영 완료 조건이 아니다. 주 실습은 [실제 엔진의 모니터링·트러블슈팅](../operations.md)이며, 아래 코드는 어려운 원리를 작은 입력으로 검산할 때만 선택한다.

[MySQL 트랙](../README.md) · [실습 안내](README.md) · [구현](offline_lab.py) · [테스트](test_offline_lab.py) · [소스 읽기](../source-reading.md)

이 실험은 MySQL 또는 InnoDB 호환 구현이 아니다. 실제 서버 없이 작은 입력의 정답과 반례를 계산하는 **서로 독립적인 네 모델**이다. 인덱스 조회 모델에 MVCC를 붙였다고 가정하거나, visibility 테스트 통과를 durability 증거로 사용하지 않는다.

Python 3.10 이상과 표준 라이브러리만 필요하다. 실행 코드는 파일 쓰기·네트워크·외부 프로세스·인증정보를 사용하지 않는다. `-B`는 bytecode cache 생성도 방지한다. 아래 명령은 저장소 루트 기준이다.

```bash
python -B databases/mysql/labs/offline_lab.py --lab all
python -B -m unittest discover -s databases/mysql/labs -p test_offline_lab.py -v
python -B -O -m unittest discover -s databases/mysql/labs -p test_offline_lab.py -v
```

모델의 핵심 정답 조건은 `assert`가 아닌 명시적인 `ValueError` 검사라서 `-O`에서도 유지된다. JSON의 `PASS`는 모델 계약만 뜻한다. 실제 MySQL 쿼리·페이지 I/O·동시성·crash recovery·replication은 여기서 **미검증**이다.

| 실행 이름 | 학습 질문 | 독립 정답/반례 |
| --- | --- | --- |
| `index-lookup` | secondary tuple만으로 어느 projection을 만들 수 있는가? | 동일 3개 후보, clustered logical fetch 0회와 3회 |
| `read-view` | 같은 version chain이 왜 RC와 RR에서 다르게 보이는가? | 경계 ID 표, own write, invisible/visible tombstone |
| `deadlock` | 기다리는 것과 순환 대기는 어떻게 다른가? | S/X compatibility, wait-for cycle, 64개 작은 그래프 대조 |
| `commit-recovery` | ACK와 durable evidence가 다른 질문인 이유는? | prepared + durable XID, unsynced loss, ACK 불확실성 |

## 1. Index lookup: tuple에서 얻는 값과 추가 조회를 구분한다

```bash
python -B databases/mysql/labs/offline_lab.py --lab index-lookup
```

### 모델 계약

입력은 immutable `Row(pk, tenant, score, payload)`이며 PK는 유일한 양의 정수다. `tenant`, `payload`는 문자열이고 `score`는 정수다. `(tenant, score, pk)` tuple을 Python 순서로 정렬한 목록을 secondary index라고 부르고, 별도의 PK→row mapping을 clustered lookup 대상으로 사용한다.

- 지원하는 조건은 `tenant = T AND low <= score <= high` 하나뿐이다. 두 경계는 포함한다.
- `(tenant, score)`가 같으면 PK 오름차순이다. 실제 SQL 결과 순서를 요구하려면 별도 `ORDER BY`가 필요하다.
- projection은 `pk`, `tenant`, `score`, `payload`의 중복 없는 목록이다.
- `payload`를 요청하지 않으면 tuple에 있는 값만 반환한다. 요청하면 일치한 tuple마다 PK mapping을 1회 조회한다.
- `secondary_entries`는 **조건을 만족하여 소비한 tuple 수**, `clustered_lookups`는 **반환 값을 얻기 위한 논리 record fetch 수**다. 입력 검증·정렬·인덱스 생성·범위 경계 탐색 비용은 집계하지 않는다.
- 정수 범위 `[-(2^63-1), 2^63-1]`와 PK 양수 조건은 이 교육 코드의 계약이다. MySQL 컬럼 타입이나 내부 transaction ID 형식을 재현하는 값이 아니다.

실제 InnoDB secondary record에는 clustered record를 찾기 위한 primary key 값이 포함된다. 이것이 이 모델의 출발점이다. [Clustered and Secondary Indexes](https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html)

### 손계산 fixture

| PK | tenant | score | payload |
| --- | --- | --- | --- |
| 40 | A | 20 | p40 |
| 10 | A | 10 | p10 |
| 30 | B | 15 | p30 |
| 20 | A | 20 | p20 |
| 50 | A | 30 | p50 |

`tenant=A`, `10 <= score <= 20`의 secondary 순서는 `(A,10,10)`, `(A,20,20)`, `(A,20,40)`이다.

| projection | 결과 | secondary tuple | clustered fetch |
| --- | --- | --- | --- |
| `(pk, score)` | `(10,10), (20,20), (40,20)` | 3 | 0 |
| `(pk, score, payload)` | `(10,10,p10), (20,20,p20), (40,20,p40)` | 3 | 3 |

**0회는 실제 InnoDB covering scan의 clustered 접근 0회를 보장하지 않는다.** 이 모델에는 transaction visibility가 없다. 실제 secondary record의 가시성을 secondary 정보만으로 판정할 수 없는 경우 clustered record와 undo를 확인할 수 있다. [InnoDB Multi-Versioning](https://dev.mysql.com/doc/refman/8.4/en/innodb-multi-versioning.html)

### 과제와 모델 밖의 조건

1. projection만 바꾸고 결과 PK와 논리 fetch 수가 어떻게 바뀌는지 먼저 손으로 계산한다.
2. tenant가 다른 같은 score, 동점 PK, 빈 범위, 중복 PK 입력을 각각 검증한다.
3. 실제 엔진 확장에서는 동일 SQL의 `EXPLAIN ANALYZE`, index 정의, 데이터 분포를 기록한다. CPU 모델의 3회 fetch를 3 physical I/O 또는 3 page read로 환산하지 않는다.
4. B+tree fanout/height, page split, buffer pool, adaptive hash, index condition pushdown, optimizer 선택, prefix index, NULL 및 collation은 구현하지 않았다. Python 문자열 비교는 MySQL collation이 아니다.

테스트는 별도의 full-scan filter/sort reference와 range 조회를 대조한다. 동일 구현을 한 번 더 호출하여 정답이라고 선언하지 않는다.

## 2. Read view: ID 크기는 commit 시각이 아니다

```bash
python -B databases/mysql/labs/offline_lab.py --lab read-view
```

일반 consistent `SELECT`의 version visibility만 다룬다. MySQL의 RC는 statement마다 새 snapshot을 얻고 RR은 transaction의 첫 consistent read에서 만든 snapshot을 재사용한다. 이전 statement의 own write는 보일 수 있다. `BEGIN`과 첫 consistent read를 같은 시점이라고 가정하지 않는다. [Consistent Nonlocking Reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html)

### 이름이 헷갈리는 두 경계

아래 규칙은 고정 소스의 `ReadView::changes_visible`을 읽어 단순화한 것이다. 소스의 `up_limit_id`는 작은 경계이고 `low_limit_id`는 큰 경계라는 점을 주의한다. `m_low_limit_no` 같은 purge 관련 값은 이 모델에 없다. [MySQL 8.4.11 read0types.h](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/include/read0types.h), [ReadView 초기화](https://github.com/mysql/mysql-server/blob/99960bf74fa919347e4f4e3ca47672f333d6e91f/storage/innobase/read/read0read.cc)

```text
creator_id = 조회하는 transaction의 ID; 0은 아직 ID가 없는 reader
active_ids = view 생성 시점의 active read-write IDs에서 creator를 뺀 집합
low_limit_id = 모델의 다음 미할당 transaction ID
up_limit_id = min(active_ids); 비어 있으면 low_limit_id

visible(id):
  id < up_limit_id 또는 id == creator_id -> True
  id >= low_limit_id                    -> False
  그 외                                -> id not in active_ids
```

실제 InnoDB의 ID/serialization number 할당과 모든 read-only 최적화를 복제하지 않는다. 여기서는 view를 만든 뒤 creator에 새 ID를 부여하지 않고, 입력 history에서 rolled-back version을 제거하는 작업도 구현하지 않는다. caller는 유효한 version chain을 제공해야 한다.

fixture는 `creator=20`, `next_id=30`, active 입력 `{12,20,25}`다. creator를 제외하여 `active={12,25}`, `up=12`, `low=30`이 된다.

| version 생성 trx ID | visible? | 이유 |
| --- | --- | --- |
| 8 | yes | 작은 경계보다 이전 |
| 12 | no | view 생성 당시 active |
| 15 | yes | 경계 사이이며 active에 없음 |
| 20 | yes | own write |
| 25 | no | view 생성 당시 active |
| 30 | no | view 이후 할당 경계 |

### 같은 history, 다른 view

history는 `(trx25, "new") -> (trx8, "old")`이며 **물리적으로 최신 version부터 과거 version 순서**다. transaction ID를 정렬해서 만들지 않는다. 먼저 시작한 transaction이 나중에 행을 수정할 수 있고 하나의 transaction이 같은 행을 여러 번 수정할 수도 있다.

1. 첫 view로 읽으면 trx25가 보이지 않으므로 `old`.
2. trx25가 commit한 뒤 `next=31`, active 입력 `{20}` 상태가 되어도, RR이 기존 view를 쓰면 `old`.
3. RC가 새 view를 만들면 `new`.
4. `(trx20, "own-write")` version을 head에 추가하면 이전 view에서도 `own-write`.
5. head가 `(trx25, deleted=True)`이면 이전 view에서는 `old`, 새 view에서는 행 없음. **보이는 tombstone을 만났다면 더 과거의 live row를 되살리지 않는다.**

`visible_version`은 첫 visible version 또는 `None`을 반환한다. visible tombstone과 visible version 자체가 없는 상태는 이 API에서 구분된다. `read_value`는 둘 다 SQL 조회의 행 없음에 대응하는 `None`으로 바꾼다. 모델에는 nullable live value를 두지 않았으므로 이 `None`은 SQL NULL 값이 아니다.

### 과제와 경계

- RR view에 own write를 추가했을 때 여러 행을 통합한 결과가 어느 한 시점의 global snapshot과 같다고 보장할 수 있는지 설명한다.
- 보이지 않는 delete 뒤에 보이는 update가 있는 chain, 같은 transaction의 두 version, 새 insert를 각각 만든다.
- 실제 엔진 확장은 두 세션의 명시적 transaction boundary와 barrier로 확인한다. 임의의 sleep으로 commit 순서를 추정하지 않는다.
- `SELECT ... FOR UPDATE/FOR SHARE`, DML의 current read, SERIALIZABLE, next-key locking, purge horizon, undo 공간 회수, write skew 및 전체 isolation anomaly 분류는 이 구현 밖이다.

## 3. Deadlock: wait edge와 cycle을 분리한다

```bash
python -B databases/mysql/labs/offline_lab.py --lab deadlock
```

자원은 `account:1`처럼 이름 붙인 **record 하나**다. 이미 부여된 lock 목록과 transaction당 최대 한 개의 pending request를 입력한다. 같은 자원의 서로 다른 transaction 사이에서 `S/S`만 호환되고 `S/X`, `X/S`, `X/X`는 호환되지 않는다. 같은 transaction의 자기 lock은 자기 대기를 만들지 않는다. 실제 shared/exclusive record locking 개념의 출발점은 공식 문서에서 확인한다. [InnoDB Locking](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html)

```text
holders:  T1 holds X(account:1), T2 holds X(account:2)
requests: T1 wants X(account:2), T2 wants X(account:1)
edges:    T1 -> T2, T2 -> T1
cycle:    T1 -> T2 -> T1
```

화살표 방향은 **waiter → blocker**다. request 하나만 남기면 edge는 있어도 cycle이 없으므로 이 정적인 모델에서 deadlock은 아니다. 두 transaction이 같은 record의 S를 가진 채 둘 다 X로 upgrade하려는 사례에도 cycle이 생긴다.

이미 서로 충돌하는 lock을 동시에 granted라고 입력하면 잘못된 fixture이므로 거부한다. `find_cycle`은 deterministic iterative DFS를 사용하여 닫힌 cycle을 반환하며, 재귀 호출 깊이를 늘려서 큰 graph를 처리하지 않는다.

### 독립 검증

- S/X 2×2 compatibility 표를 literal 정답과 대조한다.
- 3개 정점, self-edge 없는 방향 edge 6개의 모든 선택인 **64개 graph**에서 DFS 결과를 별도로 작성한 transitive closure 정답과 대조한다.
- 반환 cycle의 첫·마지막 정점이 같고 모든 edge가 입력 graph에 실제 존재하는지 검사한다.
- 길이 1,500의 acyclic chain에서도 recursion error 없이 cycle 없음이 나와야 한다.

이 graph는 실제 InnoDB lock manager의 복제본이 아니다. wait queue의 선후 관계, table/intention lock, gap/next-key/insert-intention lock, metadata lock, latches, lock timeout, scheduler, victim 선정 및 rollback은 모델링하지 않는다. 실제 detector에는 관측 가능한 lock 범위와 탐색 한계가 있으므로 CPU cycle 결과를 실제 서버의 victim 예측으로 쓰지 않는다. [Deadlock Detection](https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlock-detection.html)

과제: cycle edge마다 실제 engine 실험에서 대응되는 transaction ID·lock resource·request/grant 상태를 증거로 붙인다. “항상 T2가 victim” 같은 oracle을 만들지 않고, 어느 transaction이 rollback되어도 업무 불변식과 제한된 retry가 성립하도록 설계한다.

## 4. Commit recovery: durable decision과 client 관측을 구분한다

```bash
python -B databases/mysql/labs/offline_lab.py --lab commit-recovery
```

이 모델은 **binlog를 사용하는 한 InnoDB transaction의 internal two-phase commit에 관한 evidence 표**다. external XA coordinator, distributed consensus, replication ACK, GTID 집합, DDL, 여러 engine, torn page, log parser, checksum, WAL bytes 또는 fsync를 구현하지 않는다.

공식 문서는 binlog와 InnoDB의 commit 일관성을 위해 두 로그의 동기화가 필요하고, 재시작 시 binlog에 기록된 transaction XID를 사용하여 prepared transaction을 완료하는 절차를 설명한다. 하드웨어/파일시스템이 sync 요청을 정직하게 수행한다는 조건도 확인해야 한다. [The Binary Log](https://dev.mysql.com/doc/refman/8.4/en/binary-log.html)

### 입력 상태와 손실 가정

`CommitEvidence(redo, binlog, ack_received)`는 실제 log가 아니라 immutable 설명용 값이다.

- `redo=absent/prepared/committed`: crash 이후에도 살아남는 engine 측 증거만 표현한다. `absent`는 volatile 작업까지 전혀 없었다는 뜻이 아니다.
- `binlog=absent/written/durable`: `durable`은 **완전하고 유효한 transaction 및 XID까지** 살아남는다고 가정한다. 부분 레코드나 XID 없는 로그를 durable commit 결정으로 인정하지 않는다.
- `written`은 write는 했지만 필요한 persistence를 확보하지 않은 상태다. 이번 반례는 **모든 비영속 증거가 유실되는 power-failure 시나리오 하나**를 선택한다. 현실에서 unsynced write가 언제나 유실된다는 주장은 아니다. process crash와 OS/power loss도 같지 않다.
- `ack_received`는 client가 성공 응답을 관측했는지다. recovery의 입력 log를 바꾸는 근거가 아니다.

### 독립 truth table

| durable redo | durable complete binlog XID 없음 | durable complete binlog XID 있음 |
| --- | --- | --- |
| absent | `ABSENT` | `INCONSISTENT` |
| prepared | `ROLLBACK` | `COMMIT` |
| committed | `INCONSISTENT` | `COMMIT` |

`ABSENT`는 이 crash projection에 복구 가능한 transaction 증거가 없다는 뜻이며, client가 이전에 ACK를 받지 않았다는 뜻은 아니다. `INCONSISTENT`는 가정 위반/불일치 표시다. 특히 **이미 durable commit한 transaction에서 binlog가 빠졌다고 자동 rollback한 것으로 처리하지 않는다.** 이 코드는 실제 MySQL의 오류 처리나 수복 명령을 구현하지 않는다.

### Strict trace의 crash cut

`commit_trace()`는 안전 조건을 설명하기 위해 다음 순서를 택한다. 실제 MySQL group-commit의 모든 세부 단계 또는 각 transaction마다 별도 fsync가 실행된다는 뜻은 아니다. durable engine commit까지 ACK 전에 있다고 두는 것은 이 trace의 명시적인 충분조건이다.

| crash cut | durable redo | binlog 상태 | client ACK | 모델 복구 |
| --- | --- | --- | --- | --- |
| initial | absent | absent | no | ABSENT |
| prepare 뒤 | prepared | absent | no | ROLLBACK |
| binlog write 뒤 | prepared | written | no | ROLLBACK |
| binlog sync 뒤 | prepared | durable | no | COMMIT |
| engine commit 뒤 | committed | durable | no | COMMIT |
| ACK 수신 뒤 | committed | durable | yes | COMMIT |

두 번째 핵심은 **응답이 없다고 commit이 없었던 것은 아니라는 점**이다. engine commit 뒤의 네트워크 단절은 client에 unknown outcome을 남길 수 있다. 재시도 설계는 idempotency key와 결과 조회 등 별도의 업무 프로토콜을 필요로 한다. 이 모델은 exactly-once를 제공하지 않는다.

### Persistence를 약화한 반례

`commit_trace(durable_redo=False, sync_binlog=False)`는 필요한 persistence를 둘 다 생략한 가상 정책이다. volatile 실행 후 ACK를 받았어도 선택한 power-failure 시나리오에서는 `ABSENT`가 된다. `durable_redo=True, sync_binlog=False`라면 durable engine commit만 남아 `INCONSISTENT`가 된다. 반대 조합에서는 durable binlog만 남아 역시 불일치다.

이 Python boolean은 실제 `innodb_flush_log_at_trx_commit` 또는 `sync_binlog` 변수값을 그대로 시뮬레이션하는 스위치가 아니다. 실제 설정은 버전, group commit, flush 시점, 장애 유형과 함께 분석한다. CPU 결과로 RPO=0, power-loss 안전성, replica failover 보장을 선언하지 않는다.

과제: binlog commit 결정은 있지만 ACK가 없는 경우의 안전한 재시도 절차를 작성한다. 실제 crash test 확장은 폐기 가능한 별도 환경에서 장애 범위·지속성 설정·storage 보장·실패 시 정리 정책을 먼저 정하고 수행한다. 이 실습 코드는 서버를 중단하거나 호스트 설정을 변경하지 않는다.

## 검증 기록과 제출물

2026-10-04 기준 CPython 3.12.14에서 CLI 4개를 일반/`-O` 모드로 실행했고 **79개 단위 테스트를 두 모드 모두 통과**했다. 테스트 내부의 64개 graph 대조를 별도의 64개 테스트로 부풀리지 않는다. 모델 입력 검증, 독립 정답, immutable state, CLI 선택 및 help 경로를 포함한다. 실제 MySQL 8.4.11 binary를 실행한 결과는 아니다.

보고서는 다음 여섯 항목을 남긴다.

1. 변경할 가정 하나와 변경 전 손계산 예상값.
2. 입력 tuple/version chain/lock graph/durable evidence의 정확한 내용.
3. 실제 출력과 정답 oracle의 독립성.
4. 반례가 깨뜨리는 주장 및 여전히 유지되는 보장.
5. MySQL 소스/문서와 대응하는 부분 및 생략한 부분.
6. 실제 엔진·성능·복구를 실행하지 않았다면 해당 항목을 `미검증`으로 표시.

공식 문서는 MySQL 8.4 계열을 기준으로 2026-10-04 확인했다. source 링크는 비교 기준 MySQL 8.4.11의 commit `99960bf74fa919347e4f4e3ca47672f333d6e91f`에 고정했다. CPU 모델은 해당 소스를 빌드하거나 링크하지 않는다.
