# PostgreSQL·ClickHouse 실습 환경

각 DB는 **제품 디렉터리의 Compose로 독립 실행**합니다. 저장소 루트에는 Compose가 없으며, 예전의 루트 `docker compose up -d`는 더 이상 이 실습의 시작 방법이 아닙니다. 아래 명령은 저장소 루트에서 실행하고, 학습할 DB의 절만 선택합니다. 두 제품의 파일을 여러 `-f`로 합치지 않습니다.

이전 루트 Compose로 만든 데이터가 있다면 **새 `up` 전에 [기존 환경 전환 안내](compose-migration.md)를 읽습니다.** 기본 프로젝트명이 달라졌으므로 새 구성은 별도의 새 volume을 사용합니다. 파일 이동만으로 기존 데이터가 복사되거나 이전되지 않습니다.

## 제공 범위와 선택

| 제품 | 실행 파일 | 기본 프로젝트 | 로컬 접속 |
| --- | --- | --- | --- |
| PostgreSQL | [postgresql/compose.yaml](../postgresql/compose.yaml) | `engineering-foundations-postgresql-lab` | `127.0.0.1:5432` 또는 Compose exec |
| ClickHouse | [clickhouse/compose.yaml](../clickhouse/compose.yaml) | `engineering-foundations-clickhouse-lab` | HTTP `127.0.0.1:8123`, native `127.0.0.1:9000` 또는 Compose exec |

각 구성은 단일 노드 E0입니다. 프로젝트·network·volume·수명 주기가 분리되며, 같은 저장소에 있다는 이유로 상호 연결되지 않습니다. `-p`나 `COMPOSE_PROJECT_NAME`을 설정하면 프로젝트명이 바뀝니다. 같은 프로젝트를 다른 실습에 재사용하지 말고 `config` 결과의 이름을 확인합니다. [Docker 프로젝트 이름 규칙](https://docs.docker.com/compose/how-tos/project-name/)

| 수준 | 제공 범위 | 별도 준비가 필요한 내용 |
| --- | --- | --- |
| E0 단일 노드 | 제품별 Compose, 초기 SQL, 읽기 전용 `/lab/sql` | 실제 실행 후 SQL·plan·관측 기준선 기록 |
| E1 추가 관측/부하 | 구현 과제 | 추가 extension, profiler, 부하 생성기·예산 |
| E2 복제/분산/복구 | 구현 과제 | PG primary/standby, CH shard/replica/Keeper, 별도 restore 대상 |
| E3 엔진 개발 | 구현 과제 | 버전 고정 source, debug/release build, regression test |

PostgreSQL의 S/E/T/B는 각각 E0/E1/E2/E3에, ClickHouse의 LOCAL은 E0, CLUSTER-DESIGN은 E2에 대응합니다. OPS-DESIGN은 과제에 따라 E1/E2가 필요합니다. SOURCE 정적 읽기와 실제 빌드·디버깅 결과는 구분합니다.

기본 학습은 실제 실행 → 정상 기준선 → 지표·로그·plan → 원인 분석 → 회복 검증입니다. [PostgreSQL 운영 진단](../postgresql/operations.md), [ClickHouse 운영 진단](../clickhouse/operations.md), [공통 운영 학습](../../operations/README.md)을 연결합니다. 원리 모형은 보조자료이며 실제 진단 증거를 대체하지 않습니다.

## 공통 준비

```text
docker version
docker compose version
docker context show
```

Linux 컨테이너 엔진과 선택한 Docker context를 확인합니다. `dockerDesktopLinuxEngine` pipe 오류라면 엔진 상태/context부터 확인하고 SQL 오류로 판단하지 않습니다. 기존 컨테이너가 같은 포트를 사용하는지도 확인합니다. 기존 환경을 자동 종료하거나 교체하지 않습니다.

DB명·학습 계정·암호는 `lab` / `lab` / `lab_password`입니다. 공개된 로컬 합성 데이터용 값이며 운영 자격 증명이 아닙니다. PostgreSQL의 `lab`은 초기 관리자이므로 운영 application role 설계와 다릅니다. loopback 포트가 있다고 인증·권한·TLS 검증이 완료되는 것도 아닙니다.

## PostgreSQL만 실행

```text
docker compose -f databases/postgresql/compose.yaml config --quiet
docker compose -f databases/postgresql/compose.yaml up -d --wait
docker compose -f databases/postgresql/compose.yaml ps
docker compose -f databases/postgresql/compose.yaml logs --tail=60 postgres
docker compose -f databases/postgresql/compose.yaml exec postgres psql -X -v ON_ERROR_STOP=1 -U lab -d lab -f /lab/sql/03_internals.sql
docker compose -f databases/postgresql/compose.yaml exec postgres psql -X -v ON_ERROR_STOP=1 -U lab -d lab
```

대화형 psql에서는 `\i /lab/sql/02_solutions.sql`로 답안을 실행할 수 있습니다. DDL·데이터 변경이 포함되므로 파일 머리말과 범위를 먼저 읽습니다. 다중 세션 과제는 같은 접속 명령을 별도 터미널에서 실행하고 A/B/관측자를 표시합니다.

버전과 이미지 확인:

```text
docker compose -f databases/postgresql/compose.yaml images
docker compose -f databases/postgresql/compose.yaml exec postgres psql -X -U lab -d lab -c "SELECT version();"
```

데이터를 보존하는 종료·재시작:

```text
docker compose -f databases/postgresql/compose.yaml stop
docker compose -f databases/postgresql/compose.yaml start
```

## ClickHouse만 실행

```text
docker compose -f databases/clickhouse/compose.yaml config --quiet
docker compose -f databases/clickhouse/compose.yaml up -d --wait
docker compose -f databases/clickhouse/compose.yaml ps
docker compose -f databases/clickhouse/compose.yaml logs --tail=60 clickhouse
docker compose -f databases/clickhouse/compose.yaml exec clickhouse clickhouse-client --user lab --password lab_password --database lab --multiquery --queries-file /lab/sql/03_internals.sql
docker compose -f databases/clickhouse/compose.yaml exec clickhouse clickhouse-client --user lab --password lab_password --database lab
```

답안은 `--queries-file` 경로를 `/lab/sql/02_solutions.sql`로 바꿔 실행합니다. DDL·데이터 변경 범위를 먼저 검토합니다. healthcheck 성공만으로 seed 생성 완료나 원하는 스키마 상태를 단정하지 말고 로그와 SQL 결과를 확인합니다.

버전과 이미지 확인:

```text
docker compose -f databases/clickhouse/compose.yaml images
docker compose -f databases/clickhouse/compose.yaml exec clickhouse clickhouse-client --user lab --password lab_password --query "SELECT version();"
```

데이터를 보존하는 종료·재시작:

```text
docker compose -f databases/clickhouse/compose.yaml stop
docker compose -f databases/clickhouse/compose.yaml start
```

## 초기 데이터·버전·보존

| DB | 최초 초기 데이터 | 기본 이미지 계열 | 기본 신규 volume |
| --- | --- | --- | --- |
| PostgreSQL | users 10,000 / products 1,000 / orders 100,000 / order_items 300,000 | `postgres:18` | `engineering-foundations-postgresql-lab_postgres-data` |
| ClickHouse | events 500,000 | `clickhouse/clickhouse-server:26.8` | `engineering-foundations-clickhouse-lab_clickhouse-data` |

위 volume 이름은 프로젝트명을 변경하지 않았을 때의 값입니다. 실제 mount를 기준으로 확인합니다. 각 `./sql`은 해당 제품 Compose 디렉터리를 기준으로 해석되며 `/lab/sql`에 읽기 전용 mount됩니다. [Compose 경로와 병합 규칙](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)

seed는 작은 합성 실험의 출발점입니다. 운영의 skew·late event·중복·hot key·지속 적재를 대표하지 않으며, 각 모듈에서 분포와 크기를 별도로 설계합니다. DB별 memory/disk/실험 시간 예산을 정하고 실제 사용량을 확인한 뒤 부하를 늘립니다. 두 DB나 복제 노드를 동시에 켜야 하는 기본 요구사항은 없습니다.

이미지 tag는 패치 업데이트에 따라 바뀔 수 있습니다. 실제 엔진 버전과 실행한 이미지 ID/digest를 보고서에 기록합니다. 재현·기존 volume 재사용 시에는 관측한 digest로 image를 고정하고, 별도 override를 쓰면 **모든 명령에서 같은 `-f` 목록**을 명시합니다. 임의 digest나 태그 이름만으로 binary 동일성을 주장하지 않습니다.

`00_setup.sql`은 최초 초기화용이지 schema migration 도구가 아닙니다. PostgreSQL init script는 비어 있는 데이터 디렉터리에서 실행되며 ClickHouse 초기화도 이미지·데이터 상태의 영향을 받습니다. 기존 volume에 새 seed를 강제 적용하지 않습니다. [PostgreSQL 이미지 안내](https://hub.docker.com/_/postgres), [ClickHouse 이미지 안내](https://hub.docker.com/r/clickhouse/clickhouse-server)

데이터 초기화가 필요하면 우선 필요한 결과를 백업하고 별도 대상으로 복원 검증합니다. 그 후 선택한 DB의 **실제 context·프로젝트·컨테이너 mount·volume 이름**을 확인하고, 해당 volume을 쓰는 컨테이너가 없는지 검토한 뒤 그 대상만 정리하는 별도 절차를 작성합니다. 이 안내는 일괄 `down -v`나 volume prune을 제공하지 않습니다. 일반 학습 종료는 위의 `stop`, 재개는 `start`를 사용합니다. 기존 volume을 보존했다면 seed 예상값과 현재 데이터의 차이도 기록합니다.

## 다른 트랙과의 경계

| 트랙 | 독립적인 준비 경로 |
| --- | --- |
| MySQL | [전용 Compose·SQL 실습](../mysql/labs/README.md); PG·CH 선행 실행 불필요 |
| Kafka | [전용 Compose](../../streaming/kafka/compose.yaml), [로컬 실습](../../streaming/kafka/labs/local-lab.md) |
| NATS | [고정 서버·SDK fixture](../../streaming/nats/labs/README.md), [운영 관측](../../streaming/nats/operations.md); DB Compose와 연결되지 않음 |
| OpenSearch | [전용 엔진·REST 실습](../../search/opensearch/labs/README.md); loopback·보안 off 합성 데이터용 |
| Sentry / Supabase | [Sentry 준비](../../observability/sentry/labs/local-lab.md), [Supabase 준비](../../platforms/supabase/labs/local-lab.md); 전체 스택·SDK 앱·실제 Auth/RLS는 별도 준비 |
| Spark / Databricks | [Spark 로컬 실행](../../data-processing/spark/labs/README.md), [허가된 Databricks 대상](../../platforms/databricks/labs/README.md); 이 Compose가 cluster·Unity Catalog를 제공하지 않음 |
| OpenBao / Vault | [제품별 dev 환경](../../security/shared/labs/README.md); DB와 연결되지 않으며 dev 인메모리 상태는 영속 DB volume과 다름 |
| MCP / IaC | [MCP SDK 환경](../../ai/mcp/labs/README.md), [Terraform·Terragrunt CLI 환경](../../infrastructure/shared/environment.md); DB·cloud 연결은 자동 구성하지 않음 |
| LLM 논문 | [CPU 기본 환경](../../ai/llm-paper-lab/environment.md); GPU·모델 다운로드·외부 API는 선택 확장 |

PostgreSQL → Kafka → ClickHouse 파이프라인도 자동 생성되지 않습니다. connector·권한·네트워크·복구 설계는 [통합 연구](capstone.md)의 별도 구현 과제입니다.

## 검증 결과의 해석

문서의 명령과 통과 기준은 독자가 수행할 지침입니다. Compose `config` 검사는 엔진 기동·이미지 다운로드·SQL 실행·장애 복구 성공을 대신하지 않습니다. 파일 위치 변경은 데이터 이동을 의미하지 않으며, 보고서에 실제 수행 범위와 미수행 범위를 구분합니다. 이번 위치 변경의 실제 점검 결과는 [구성 검증 기록](compose-validation.md)에 남깁니다.
