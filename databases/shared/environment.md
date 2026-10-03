# 실습 환경과 실행 범위

모든 shell 명령은 저장소 루트에서 한 줄씩 실행합니다. PowerShell과 Bash에서 서로 다른 multiline 문법을 피하기 위해 한 줄 명령을 사용합니다.

## 제공 환경

| 수준 | 제공 여부 | 용도 |
| --- | --- | --- |
| E0 단일 노드 | `compose.yaml` 제공 | SQL·plan·저장 구조·같은 서버의 여러 세션 |
| E1 추가 관측/부하 | 학습자가 구성 | pageinspect 등 extension, profiler, 부하 생성기 |
| E2 복제/분산/복구 | 학습자가 구성 | PG primary/standby, CH shard/replica/Keeper, 별도 restore 대상 |
| E3 엔진 개발 | 학습자가 구성 | 버전 고정 source, debug/release build, regression test |

각 강의의 “다중 노드”, “별도 환경”, “구현 과제” 표시는 E0만으로 완료되지 않습니다. 상위 환경의 IaC·Compose·설정·운영 명령 작성 자체가 평가 결과물입니다.

Kafka는 [별도 Compose](../../streaming/kafka/compose.yaml)와 [로컬 실습 안내](../../streaming/kafka/labs/local-lab.md)를 제공합니다. 이 문서의 `docker compose` 명령은 루트의 두 DB에만 적용됩니다. Kafka는 `docker compose -f streaming/kafka/compose.yaml ...`로 관리하며 프로젝트·네트워크·volume을 분리합니다. 기본 상태에서는 PostgreSQL → Kafka → ClickHouse 파이프라인이 만들어지지 않습니다. connector와 네트워크 연결은 [통합 연구](capstone.md)의 구현 과제입니다.

MySQL은 [전용 환경](../mysql/labs/README.md)과 `databases/mysql/compose.yaml`을 사용합니다. 기존 root Compose에 세 번째 DB를 추가하지 않으며 MySQL만 학습할 때 두 DB를 먼저 시작할 필요가 없습니다. 호스트 포트 없이 로컬 Docker exec·container socket으로 접속하고 project/network/volume을 분리합니다. CPU 모형과 실제 SQL fixture, 별도 다중 세션·복제·PITR 실험을 구분합니다.

[Sentry 준비 실습](../../observability/sentry/labs/local-lab.md)과 [Supabase CLI local 준비](../../platforms/supabase/labs/local-lab.md)는 별도 과정입니다. Sentry의 offline 계산과 Supabase 권한 reference fixture는 제공하지만, 두 제품의 전체 스택·SDK 앱·클라우드 프로젝트·실제 Auth/RLS 검증은 제공된 DB Compose에 포함되지 않습니다. 기존 PostgreSQL·Kafka·ClickHouse를 제품 내부 dependency로 자동 연결하지 않습니다.

[LLM 논문 실험](../../ai/llm-paper-lab/environment.md)의 CPU 기본 경로는 Python 표준 라이브러리만 사용하며 이 DB Compose와 독립적입니다. GPU·모델 다운로드·외부 API 호출은 별도 선택 확장이고 기본 실험에서 자동 수행하지 않습니다.

[Spark 실습](../../data-processing/spark/labs/README.md)은 CPU 모형과 별도 Java/PySpark 4.0.4 기반 로컬 runner를 구분합니다. [Databricks 실습](../../platforms/databricks/labs/README.md)은 허가된 관리형 대상과 비용 계약이 필요한 별도 단계입니다. 이 DB Compose가 Spark cluster·Delta·Unity Catalog·Databricks를 제공하지 않습니다.

[OpenSearch 실습](../../search/opensearch/labs/README.md)은 독립 CPU 모형과 별도 `search/opensearch/compose.yaml`을 사용합니다. 단일 노드·합성 데이터·보안 플러그인 off·loopback HTTP 전용이며 운영·권한·HA 검증용이 아닙니다. DB/Kafka와 network·volume·수명 주기를 공유하지 않고 connector·CDC·embedding 모델을 자동 구성하지 않습니다. [검증 기록](../../search/opensearch/labs/validation.md)의 CPU/mock/실제 엔진 구분을 확인합니다.

트랙별 표기는 PostgreSQL의 S가 E0, E가 선택 확장을 포함한 E1, T가 E2, B가 E3에 대응합니다. ClickHouse의 LOCAL은 E0, CLUSTER-DESIGN은 E2에 해당하며 OPS-DESIGN은 과제에 따라 E1/E2가 필요합니다. SOURCE의 정적 읽기는 파일 탐색으로 가능하지만 직접 빌드·디버깅은 E3 준비가 필요합니다.

Docker에 사용할 메모리는 입문 두 서비스를 합쳐 6–8GiB 정도를 출발점으로 삼되, 이는 보장된 최소 요구사항이 아닙니다. 실제 소비량을 `docker stats --no-stream`으로 확인합니다. 규모 확대는 1배→2배→10배로 진행하고 disk/memory 예산을 먼저 정합니다. Keeper 다수 노드와 replica를 구성하는 경우 E0 예산을 그대로 적용하지 않습니다.

## 시작과 상태 확인

```text
docker version
docker compose version
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose logs --tail=60 postgres clickhouse
```

`dockerDesktopLinuxEngine` pipe가 없다는 오류는 보통 Linux 엔진이 시작되지 않았거나 context가 다른 상태입니다. Docker Desktop 상태와 `docker context show`를 확인한 뒤 진행합니다. SQL 초기화 실패는 해당 서비스 로그에서 첫 오류를 확인합니다. 단순 healthcheck 성공만으로 seed 데이터가 완성됐다고 판단하지 않습니다.

서비스는 로컬 실습 계정 `lab` / `lab_password`를 사용합니다. PostgreSQL의 이 계정은 초기 관리자이며 운영 application role 설계와 다릅니다. endpoint와 volume은 [Compose](../../compose.yaml)에 정의돼 있습니다.

## SQL 실행

양쪽 `sql` 디렉터리는 컨테이너의 `/lab/sql`에 읽기 전용으로 연결됩니다. 문제 파일은 주로 문제 설명이며, 답안 파일에는 DDL/학습용 변경이 포함될 수 있으므로 머리말을 읽고 실행합니다.

```text
docker compose exec postgres psql -X -v ON_ERROR_STOP=1 -U lab -d lab -f /lab/sql/03_internals.sql
docker compose exec clickhouse clickhouse-client --user lab --password lab_password --database lab --multiquery --queries-file /lab/sql/03_internals.sql
```

대화형 접속:

```text
docker compose exec postgres psql -X -v ON_ERROR_STOP=1 -U lab -d lab
docker compose exec clickhouse clickhouse-client --user lab --password lab_password --database lab
```

PostgreSQL에서는 `\i /lab/sql/02_solutions.sql`로 답안을 실행할 수 있습니다. ClickHouse 답안은 위 `--queries-file` 경로를 `02_solutions.sql`로 바꿉니다. 여러 세션 실습은 서로 다른 터미널에서 접속하고 세션 A/B/관측자를 표시합니다.

## 초기 데이터와 버전

| DB | 초기 데이터 | 기본 이미지 계열 |
| --- | --- | --- |
| PostgreSQL | users 10,000 / products 1,000 / orders 100,000 / order_items 300,000 | `postgres:18` |
| ClickHouse | events 500,000 | `clickhouse/clickhouse-server:26.8` |

이 데이터는 문법·정확성·작은 실험의 출발점입니다. 운영의 skew·late event·중복·hot key·지속 적재를 대표하지 않습니다. 각 심화 모듈에서 분포와 크기를 바꾼 실험을 별도로 수행합니다. “실제로 180일 동안 운영했다”는 데이터가 아니라 고정 시각 범위의 합성 데이터입니다.

이미지 tag는 패치 업데이트에 따라 달라질 수 있습니다. 실험마다 아래 정보를 기록하고, 엄밀한 재현이 필요하면 `compose.override.yaml`의 `image`를 관측한 `repository@sha256:...` 값으로 고정합니다. 여기 문서에 임의 digest를 제공하지 않습니다.

```text
docker compose images
docker image inspect postgres:18 --format '{{json .RepoDigests}}'
docker image inspect clickhouse/clickhouse-server:26.8 --format '{{json .RepoDigests}}'
docker compose exec postgres psql -X -U lab -d lab -c "SELECT version();"
docker compose exec clickhouse clickhouse-client --user lab --password lab_password --query "SELECT version();"
```

`00_setup.sql`은 최초 초기화용입니다. PostgreSQL의 init scripts는 데이터 디렉터리가 비어 있을 때 실행됩니다. ClickHouse 이미지의 초기화 동작도 버전 및 데이터 상태에 영향을 받으므로 시작을 schema migration으로 취급하지 않습니다. 새 curriculum의 seed를 기존 볼륨에 강제로 덮어쓰지 않습니다. [PostgreSQL 이미지 안내](https://hub.docker.com/_/postgres), [ClickHouse 이미지 안내](https://hub.docker.com/r/clickhouse/clickhouse-server)

## 보존과 재시작

일반 종료·재시작은 volume을 보존합니다.

```text
docker compose stop
docker compose start
```

초기 데이터부터 다시 시작할 때는 로컬 학습 결과를 먼저 별도 보존합니다. 다음 명령은 **`engineering-foundations-lab` 프로젝트의 두 DB volume을 삭제**합니다. 필요한 데이터가 있을 때는 실행하지 않습니다.

```text
docker compose down -v
docker compose up -d
```

답안과 강의마다 별도 실습 테이블 이름을 사용하며, 정리 명령은 그 테이블만 대상으로 합니다. 기존 volume을 유지한 경우 `03_internals.sql`의 검증 결과가 새 seed의 기대값과 다른지 먼저 확인합니다.

## OpenBao / Vault 별도 환경

[비밀·신원 보안 실습](../../security/shared/labs/README.md)은 CPU 모형 4개와 제품별 선택 dev Compose를 사용합니다. 기존 DB Compose와 독립이며, 컨테이너 외부 네트워크·host port·영속 volume을 제공하지 않습니다. dev는 자동 unseal·공개 dummy root·인메모리 구성이므로 stop/start 시 실습 상태가 사라집니다. 실제 DB 동적 자격 증명·TLS·Raft·snapshot 복원은 별도 격리 환경을 준비하는 [선택 연구](../../capstones/secrets-identity-recovery.md)입니다. DB나 cloud 계정을 자동 생성·연결하지 않습니다.

## 검증 상태의 해석

Terraform·Terragrunt의 선택 실습은 [IaC 전용 환경](../../infrastructure/shared/environment.md)에서 진행합니다. DB/Kafka Compose와 state/cache의 수명 주기를 공유하지 않습니다. CPU 모형과 실제 로컬 CLI 검증, 미검증 cloud backend를 구분합니다.

문서의 “예상”과 “통과 기준”은 독자가 수행할 실험 조건입니다. 해당 컴퓨터의 실행 결과를 미리 제공한 것이 아닙니다. Compose 구문 검사는 엔진 실행·이미지 다운로드·SQL 문법 실행·복구 성공을 대신하지 않습니다. 실험 보고서에 수행한 범위와 미수행 범위를 따로 남깁니다.
