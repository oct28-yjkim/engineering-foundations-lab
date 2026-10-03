# MySQL 실습 — CPU 원리와 실제 SQL을 구분하기

[트랙](../README.md) · [CPU 상세](offline.md) · [검증 기록](validation.md)

기본은 Python 3.10 이상 표준 라이브러리만 사용하는 CPU 실험입니다. MySQL 설치·Docker·계정·API·네트워크가 필요 없습니다. 실제 엔진은 별도 선택 경로이며 모든 명령은 저장소 루트에서 실행합니다.

## 1. CPU부터 시작

```text
python -B databases/mysql/labs/offline_lab.py --lab all
python -B -m unittest discover -s databases/mysql/labs -p "test_*.py" -v
```

| 실험 | 검산할 질문 | 증명하지 않는 것 |
| --- | --- | --- |
| `index-lookup` | secondary key에서 PK로 찾는 과정, covering/noncovering의 논리적 작업 차이 | B-tree page layout·실제 I/O·cache·MVCC·optimizer 비용 |
| `read-view` | creator·watermark·active ID, view 재사용/갱신과 version 가시성 | 전체 InnoDB·current read·잠금·직렬 가능성·purge 구현 |
| `deadlock` | record resource의 S/X 호환성·wait-for graph·cycle | gap/next-key/insert-intention·MDL·page latch·실제 victim 선택 |
| `commit-recovery` | durable prepare·완전한 durable binlog XID·commit 증거와 ACK 불확실성 | log 파일·fsync·실제 crash recovery·PITR·분산 commit |

covering 조건에서 lookup을 생략하는 CPU 결과는 정적 모형의 계약입니다. 실제 InnoDB secondary index의 consistent read는 가시성 때문에 clustered record를 확인할 수 있습니다. 네트워크와 SQL을 흉내 낸 테스트도 실제 MySQL을 실행한 증거가 아닙니다.

## 2. 선택: MySQL 8.4.11 단일 노드

[Compose](../compose.yaml)는 Docker Official Image `mysql:8.4.11`을 사용합니다. 별도 Docker 엔진·Compose v2·이미지 다운로드 네트워크와 디스크가 필요합니다. Python SQL connector나 호스트의 `mysql` client 설치는 필요하지 않고, Docker CLI가 PATH에서 실행 가능해야 합니다.

이 구성은 `engineering-foundations-mysql-lab` project의 단일 service `mysql`, hostname `efl-mysql-lab`, server_id `8411`입니다. 기존 PostgreSQL/ClickHouse/Kafka/OpenSearch와 network·volume을 공유하지 않습니다. **호스트 포트를 전혀 열지 않으며**, 로컬 Docker exec로 컨테이너 안의 Unix socket에 연결합니다. Docker daemon 접근 권한 자체는 강력한 관리자 권한이므로 격리된 개인 개발 환경에서만 사용합니다.

root 비밀번호 `local_mysql_root_not_for_production`은 공개된 학습용 dummy입니다. 실제 비밀이 아니며 운영·공유 호스트·개인정보에는 사용할 수 없습니다. root는 실습 편의를 위한 고권한 계정이고 앱 권한 설계가 아닙니다. 호스트 포트가 없다고 다른 컨테이너·Docker 관리자·로컬 사용자로부터 완전한 보안 격리가 생기지는 않습니다.

```text
docker version
docker compose -f databases/mysql/compose.yaml config --quiet
docker compose -f databases/mysql/compose.yaml up -d --wait
docker compose -f databases/mysql/compose.yaml ps
docker compose -f databases/mysql/compose.yaml logs --tail=60 mysql
python -B databases/mysql/labs/engine_lab.py --help
python -B databases/mysql/labs/engine_lab.py --run-local
```

`up`은 이미지·컨테이너·network·named volume을 생성합니다. Docker를 원격 context로 연결해 둔 환경에서 위 명령을 그대로 실행하지 말고 먼저 `docker context show`와 `docker context inspect`로 개인 로컬 대상을 확인합니다. 아래 runner의 guard가 수동 Docker 명령까지 대신 보호하지는 않습니다.

Compose에는 memory 1GB·CPU 2개·buffer pool 128MiB·최대 연결 30개를 작은 fixture의 출발 예산으로 둡니다. 이는 production sizing 권장값이나 최소 실행 보장이 아닙니다. 초기화/OOM 실패는 로그와 Docker VM 예산을 먼저 확인합니다. 엔진이 꺼져 있으면 중단하고 사용자가 환경을 준비합니다. runner는 Docker Desktop을 시작하거나 host 설정을 바꾸지 않습니다.

## 3. runner의 대상·쓰기 제한

`--help`와 인자 없는 실행은 subprocess를 시작하지 않습니다. `--run-local`에서만 다음을 수행합니다.

1. Docker/Compose/MySQL 연결 override 환경변수를 제거하고 기본 Docker 설정의 저장된 context를 읽습니다. 사용자가 환경변수로 지정한 다른 context/host/config를 따라가지 않습니다. Unix socket 또는 허용된 로컬 Windows named pipe만 받고 TCP/SSH endpoint를 거부합니다.
2. 이후 명령은 검사한 `--host`, 저장소 내 고정 Compose 파일·project·service를 명시합니다. 이는 로컬 전송/실수 방지이며 Docker 관리자나 위조된 서버에 대한 인증 경계는 아닙니다.
3. 컨테이너 안의 고정 shell 명령이 root password를 읽고 MySQL Unix socket client를 실행합니다. host argv에 비밀번호를 넣지 않고 SQL은 stdin으로 전달합니다. 임의 host/database/SQL 인자는 없습니다.
4. 서버 version/hostname/server_id/InnoDB 및 durability/binlog/GTID 설정을 읽기 전용으로 확인합니다. 일치하지 않으면 DB를 생성하지 않습니다.
5. 매번 `efl_mysql_<UUID>` 새 DB 하나만 만듭니다. 기존 DB를 재사용하거나 삭제하지 않고, 같은 이름이 이미 있으면 실패합니다. 모든 DDL/DML은 새 DB의 합성 fixture에만 수행합니다.

client는 option/login 파일·재접속·local infile·대화형 system command를 제한합니다. 선택한 8.4.11의 지원 옵션은 [공식 mysql client 옵션](https://dev.mysql.com/doc/refman/8.4/en/mysql-command-options.html)을 기준으로 하며, 다른 버전의 client에 임의 적용하지 않습니다.

고정 명령 수 16회와 각 subprocess timeout 30초를 제한합니다. 출력 크기 1MiB 검사는 **캡처 후 검증**이며 streaming 메모리 상한은 아닙니다. 각 SQL session의 lock wait와 일부 SELECT 실행 시간도 제한하지만 전체 서버 statement의 강제 취소 보장은 아닙니다. timeout으로 Docker client가 끝나도 서버 실행이 끝났거나 rollback됐다고 단정하지 않습니다.

실패하면 stage·신규 DB·생성 시도/확인 여부만 남기고 원시 stderr·SQL·비밀번호를 출력하지 않습니다. 실패/성공 DB 모두 보존하며 자동 cleanup은 없습니다. 재실행은 또 다른 DB를 생성하므로 namespace·용량·결과를 원장에 기록합니다. DDL은 implicit commit이 생길 수 있으므로 실패한 schema 초기화 전체가 transaction rollback된다고 가정하지 않습니다.

## 4. 합성 fixture와 SQL oracle

두 계정의 초기 잔액은 최소 단위 정수로 alpha=10000, beta=5000입니다. 주문은 다음과 같습니다.

| order_id | account_id | amount_cents | currency | tag |
| --- | --- | --- | --- | --- |
| 101 | 1 | 1200 | USD | x |
| 102 | 1 | 300 | NULL | x |
| 103 | 2 | 700 | USD | NULL |
| 104 | 2 | 900 | EUR | y |

아래는 **기대값**입니다. 실제 수행 여부는 [검증 기록](validation.md)에 따릅니다.

| 검사 | 통과 조건 |
| --- | --- |
| 행/NULL/중복/합계 | 주문 COUNT(*)=4, COUNT(currency)=3, DISTINCT currency=2, 금액 합계=3100 |
| `currency NOT IN ('USD', NULL)` | 결과 0건. NULL을 일반 값처럼 비교하면 틀림 |
| `NOT EXISTS` 반조인 | order_id=102,104. NULL currency를 포함하는 것이 명시한 equality 계약 |
| tag 그룹 | NULL=1,x=2,y=1 |
| 계정별 주문 합계 | alpha=1500,beta=1600 |
| 복합 index와 조회 | owner_code/balance_cents 선언·조회 결과 1/10000; JSON EXPLAIN 구조 확인 |
| 1250 이체 COMMIT | ID1=8750,ID2=6250, 총액=15000 |
| 추가 500 이체 후 ROLLBACK | transaction 안 8250/6750, rollback 후 8750/6250 |
| 중복 PK / 없는 FK / 음수 balance | 각각 오류 1062 / 1452 / 3819 및 기대 SQLSTATE |
| 최종 전체 상태 | 계정 2개·주문 4개와 모든 field 일치, InnoDB 확인 |

작은 fixture는 optimizer가 scan 또는 다른 index를 고를 수 있으므로 특정 plan·estimated cost·latency를 성공 조건으로 고정하지 않습니다. EXPLAIN JSON이 파싱된다는 사실도 성능 개선 증거가 아닙니다. 두 session이 아닌 단일 session transaction 검산만으로 MVCC·deadlock·실제 동시성 검증을 주장하지 않습니다.

## 5. 수동 다중 세션·관측으로 확장

```text
docker compose -f databases/mysql/compose.yaml exec mysql mysql --no-defaults --no-login-paths --protocol=socket --socket=/var/run/mysqld/mysqld.sock -uroot -p
```

위 명령은 비밀번호를 프롬프트에 입력합니다. 로컬 학습용 dummy만 사용하며 실제 secret을 shell history·스크립트에 넣지 않습니다. runner 출력의 DB를 확인하고 `USE`하되, 자동 검증 fixture는 결과 보존용으로 남겨 두고 강의의 새 실험 객체/DB를 따로 만듭니다.

두 터미널의 connection ID·isolation·autocommit·사건 순서를 기록합니다. [28주 커리큘럼](../curriculum.md)의 LOCAL-SESSIONS는 학습자가 직접 수행하는 과제입니다. 기다림은 sleep 시간 추측만으로 판정하지 않고 Performance Schema의 data_locks/data_lock_waits·metadata_locks와 session 상태를 대조합니다. 다른 세션을 임의 KILL하거나 공유 설정을 바꾸지 않습니다.

## 6. 보존과 재현

```text
docker compose -f databases/mysql/compose.yaml images
docker image inspect mysql:8.4.11 --format '{{json .RepoDigests}}'
docker compose -f databases/mysql/compose.yaml stop
docker compose -f databases/mysql/compose.yaml start
```

stop/start는 named volume을 보존합니다. 기존 volume에는 환경변수 변경이 초기 계정/데이터를 다시 적용하지 않습니다. 비밀번호가 안 맞는다고 volume을 지우지 말고 실제 대상·초기화 이력·보존 여부를 먼저 확인합니다. 삭제 명령은 자동 제공하지 않으며 필요한 결과를 별도 보존하고 정확한 대상의 소유권을 확인한 뒤 결정합니다.

엄밀한 재현에는 git commit·image digest·서버/OS/아키텍처·SQL mode·charset/collation·isolation·durability/binlog·데이터 fingerprint를 기록합니다. `sync_binlog=1`과 `innodb_flush_log_at_trx_commit=1` 설정 확인은 장치의 실제 fsync 내구성이나 backup 존재를 증명하지 않습니다. GTID가 켜져 있어도 replica는 생성되지 않습니다.

기본 환경에는 다중 노드, replication channel, Group Replication/Router, CDC, backup 보관소, 실제 PITR, TLS/역할 기반 앱이 없습니다. [8주 연구](../../../capstones/mysql-transaction-recovery.md)에서 별도 구성하고 미검증 경계를 줄입니다. MariaDB·Aurora·관리형 MySQL에 그대로 적용하지 않습니다.
