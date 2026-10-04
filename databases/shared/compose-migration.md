# 루트 Compose에서 제품별 Compose로 전환

루트의 PostgreSQL·ClickHouse 통합 Compose를 없애고 각 제품 디렉터리로 분리했습니다. 이 변경은 **파일·프로젝트 구성을 바꾼 것이며, 기존 컨테이너나 데이터를 이동·삭제하지 않습니다.** 기존 volume이 있으면 새 `up` 전에 이 문서를 읽습니다. 두 DB는 각각 전환하며 한 번에 합쳐 실행하지 않습니다.

| 구분 | 이전 기본값 | 새 기본값 |
| --- | --- | --- |
| Compose | 루트 `compose.yaml` | [PostgreSQL](../postgresql/compose.yaml), [ClickHouse](../clickhouse/compose.yaml) |
| 프로젝트 | `engineering-foundations-lab` | `engineering-foundations-postgresql-lab` / `engineering-foundations-clickhouse-lab` |
| 컨테이너 | 고정 `efl-postgres` / `efl-clickhouse` | Compose가 프로젝트·서비스별 이름 생성 |
| volume | 예: `engineering-foundations-lab_postgres-data` / `engineering-foundations-lab_clickhouse-data` | 제품별 프로젝트의 별도 신규 volume |

이전에도 `-p`, `COMPOSE_PROJECT_NAME`, override를 사용했다면 실제 이름이 다를 수 있습니다. 위 예시 이름으로 데이터를 추정하지 않습니다. 새 기본 환경에서 빈 데이터나 seed만 보인다고 기존 volume이 삭제된 것은 아닙니다. 기본 `up`은 이전 volume을 찾아서 이어 붙이지 않습니다. [Docker 프로젝트 이름](https://docs.docker.com/compose/how-tos/project-name/)

## 1. 먼저 기존 대상을 읽기 전용으로 식별

저장소 루트에서 실행합니다. 선택한 DB의 줄만 확인해도 됩니다. Docker context가 이전 실습의 대상과 같은지 먼저 확인합니다.

```text
docker context show
docker ps -a --filter name=efl-postgres --format '{{.ID}} {{.Names}} {{.Status}}'
docker ps -a --filter name=efl-clickhouse --format '{{.ID}} {{.Names}} {{.Status}}'
docker inspect efl-postgres --format '{{.Name}} project={{index .Config.Labels "com.docker.compose.project"}} service={{index .Config.Labels "com.docker.compose.service"}} imageID={{.Image}} mounts={{json .Mounts}}'
docker inspect efl-clickhouse --format '{{.Name}} project={{index .Config.Labels "com.docker.compose.project"}} service={{index .Config.Labels "com.docker.compose.service"}} imageID={{.Image}} mounts={{json .Mounts}}'
```

`name` 필터는 부분 일치 후보를 보여 주므로 정확한 `/efl-postgres`, `/efl-clickhouse`와 Compose labels를 대조합니다. 전체 `docker inspect` 결과에는 환경변수·비밀이 포함될 수 있어 위처럼 필요한 필드만 읽습니다. mount의 `Type=volume`, `Name`, `Destination`이 각각 PostgreSQL `/var/lib/postgresql`, ClickHouse `/var/lib/clickhouse`에 연결되는지 확인합니다. 예상과 다른 bind mount나 데이터 경로면 이 재사용 절차를 중단하고 해당 구성을 먼저 검토합니다.

컨테이너가 없으면 volume만 남아 있을 수 있습니다. Docker volume 목록·Compose labels와 이전 실습 기록을 대조해 소유권과 DB 종류를 확인합니다. 확신할 수 없는 volume을 연결하지 않습니다. 식별한 이름으로 `docker volume inspect VERIFIED_VOLUME_NAME`을 실행해 존재와 labels를 검토하되, `VERIFIED_VOLUME_NAME`은 **실제로 확인한 이름으로 바꿔야 하는 자리표시자**입니다.

## 2. 새로 시작할지, 기존 데이터를 사용할지 선택

- **새 실습:** 기존 데이터·컨테이너를 보존하고 [제품별 기본 시작](environment.md)으로 진행합니다. 이전 컨테이너가 실행 중이면 같은 호스트 포트를 점유할 수 있습니다. 필요할 때 아래의 정확한 대상 확인 후 종료 절차를 따르며, 기존 환경을 제거하지 않습니다.
- **기존 데이터 유지:** 아래 백업·이미지 고정·단일 writer 조건을 모두 충족한 후에만 external-volume override로 연결합니다. 다른 major 버전으로 올리는 upgrade 절차가 아닙니다.

기존 데이터 재사용 전에는 DB에 맞는 일관된 백업을 만들고 **별도의 복원 대상에서 복구 가능성을 확인**합니다. 실행 중 DB의 volume 디렉터리 단순 복사는 이 조건을 충족하지 않습니다. 접근 권한, 기존 계정/암호, 확장·설정·데이터 형식 호환성을 확인합니다. 새 Compose의 환경변수는 기존 DB 계정 암호나 schema를 자동 변경하지 않습니다.

동일한 `postgres:18` 또는 `clickhouse/clickhouse-server:26.8` 태그라도 이전과 같은 바이너리라고 가정하지 않습니다. 1단계의 실행 이미지 ID로 `docker image inspect VERIFIED_IMAGE_ID --format '{{json .RepoDigests}}'`를 확인하고 실제 엔진 버전과 기록을 대조합니다. 기존 image가 식별되지 않거나 호환성을 증명하지 못하면 원본 volume 재사용을 진행하지 말고 별도 환경으로 백업 복원을 선택합니다.

## 3. 기존 이미지 고정과 volume 선택

기존 이미지와 동일한 것으로 확인한 repository digest를 사용해 아래 **선택한 제품의 로컬 파일만** 작성합니다. `lab-workspaces/`는 Git 제외 경로입니다. 아래 digest 자리표시자는 실행 가능한 값이 아니므로 실제 관측값으로 바꿉니다. 공식 upgrade·호환성 검토 없이 더 새로운 image를 원본 volume에 연결하지 않습니다.

`lab-workspaces/postgresql-image-pin.yaml`:

```yaml
services:
  postgres:
    image: postgres@sha256:REPLACE_WITH_VERIFIED_EXISTING_DIGEST
```

`lab-workspaces/clickhouse-image-pin.yaml`:

```yaml
services:
  clickhouse:
    image: clickhouse/clickhouse-server@sha256:REPLACE_WITH_VERIFIED_EXISTING_DIGEST
```

volume 환경변수도 실제 확인한 이름으로 설정합니다. PostgreSQL과 ClickHouse 중 전환할 제품만 설정합니다.

PowerShell:

```powershell
$env:EFL_POSTGRES_LEGACY_VOLUME = 'REPLACE_WITH_VERIFIED_POSTGRES_VOLUME'
$env:EFL_CLICKHOUSE_LEGACY_VOLUME = 'REPLACE_WITH_VERIFIED_CLICKHOUSE_VOLUME'
```

Bash:

```bash
export EFL_POSTGRES_LEGACY_VOLUME='REPLACE_WITH_VERIFIED_POSTGRES_VOLUME'
export EFL_CLICKHOUSE_LEGACY_VOLUME='REPLACE_WITH_VERIFIED_CLICKHOUSE_VOLUME'
```

[PostgreSQL override](../postgresql/compose.legacy-volume.yaml)와 [ClickHouse override](../clickhouse/compose.legacy-volume.yaml)는 이름 누락 시 config 단계에서 실패합니다. `external: true`이므로 그 이름의 volume이 없으면 기동이 실패하며 새 빈 volume으로 대체하지 않습니다. 이것이 **잘못된 기존 volume 선택까지 막아 주지는 않으므로** mount·labels 확인은 필수입니다. [Docker external volume](https://docs.docker.com/reference/compose-file/volumes/)

## 4. 정확한 기존 컨테이너만 종료하고 전환

백업·복원 검증과 이미지 고정을 마친 뒤, 1단계에서 확인한 컨테이너만 사용자가 직접 종료합니다. 두 명령을 일괄 실행하지 말고 전환할 제품 한 개만 선택합니다.

```text
docker stop efl-postgres
docker stop efl-clickhouse
```

정지한 컨테이너와 원본 volume은 그대로 둡니다. `docker ps --filter volume=VERIFIED_VOLUME_NAME --format '{{.ID}} {{.Names}} {{.Status}}'`로 **실제로 확인한 volume**을 쓰는 실행 중 컨테이너가 없는지 확인합니다. 다른 writer가 있으면 진행하지 않습니다. `docker ps -a`에서도 mount 대상을 대조하고 이후 기존 컨테이너가 다시 시작되지 않도록 합니다. 두 DB 프로세스가 같은 데이터 volume을 동시에 쓰면 안 됩니다.

선택한 제품에서 아래 `config`의 프로젝트 이름·image digest·external volume·mount 경로를 확인한 다음에만 `up`을 실행합니다. 새 프로젝트 이름이 1단계의 이전 프로젝트나 다른 실습 프로젝트와 달라야 합니다. 사용자 맞춤 비밀이 포함된 config/log 출력은 공유 전에 제거합니다. `-f` 순서는 기본 → legacy-volume → image-pin입니다. 경로는 첫 Compose 파일을 기준으로 해석됩니다. [Docker Compose 병합 규칙](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)

PostgreSQL:

```text
docker compose -f databases/postgresql/compose.yaml -f databases/postgresql/compose.legacy-volume.yaml -f lab-workspaces/postgresql-image-pin.yaml config
docker compose -f databases/postgresql/compose.yaml -f databases/postgresql/compose.legacy-volume.yaml -f lab-workspaces/postgresql-image-pin.yaml up -d --wait --pull never
docker compose -f databases/postgresql/compose.yaml -f databases/postgresql/compose.legacy-volume.yaml -f lab-workspaces/postgresql-image-pin.yaml ps
docker compose -f databases/postgresql/compose.yaml -f databases/postgresql/compose.legacy-volume.yaml -f lab-workspaces/postgresql-image-pin.yaml logs --tail=60 postgres
docker compose -f databases/postgresql/compose.yaml -f databases/postgresql/compose.legacy-volume.yaml -f lab-workspaces/postgresql-image-pin.yaml exec postgres psql -X -U lab -d lab -c "SELECT version();"
```

ClickHouse:

```text
docker compose -f databases/clickhouse/compose.yaml -f databases/clickhouse/compose.legacy-volume.yaml -f lab-workspaces/clickhouse-image-pin.yaml config
docker compose -f databases/clickhouse/compose.yaml -f databases/clickhouse/compose.legacy-volume.yaml -f lab-workspaces/clickhouse-image-pin.yaml up -d --wait --pull never
docker compose -f databases/clickhouse/compose.yaml -f databases/clickhouse/compose.legacy-volume.yaml -f lab-workspaces/clickhouse-image-pin.yaml ps
docker compose -f databases/clickhouse/compose.yaml -f databases/clickhouse/compose.legacy-volume.yaml -f lab-workspaces/clickhouse-image-pin.yaml logs --tail=60 clickhouse
docker compose -f databases/clickhouse/compose.yaml -f databases/clickhouse/compose.legacy-volume.yaml -f lab-workspaces/clickhouse-image-pin.yaml exec clickhouse clickhouse-client --user lab --password lab_password --query "SELECT version();"
```

`--pull never`는 확인한 기존 이미지가 로컬에 없을 때 다운로드로 넘어가지 않고 중단하도록 합니다. 이 경우 이미지 보존·복구 계획을 먼저 확인합니다. healthcheck 통과만으로 데이터 전환 성공을 판정하지 않습니다.

기존 인증을 바꿨다면 위 공개 실습용 접속 정보를 그대로 쓰지 말고 기존 인증 방식에 맞춥니다. 기존 테이블·건수·대표 쿼리 결과를 전환 전 기록과 대조합니다. 새 seed가 생성된 것을 전환 성공으로 판단하거나, `00_setup.sql`·답안 SQL을 검증 대신 재실행하지 않습니다. 새 컨테이너의 실제 mount도 확인한 원본 volume과 일치하는지 재검증합니다.

## 5. 이후 실행과 롤백

기존 volume 경로를 선택한 뒤에는 기본 Compose만 사용하지 않습니다. **제품 README·강의·운영 진단의 기본 명령도 SQL 실행·로그·중지·시작을 포함해 항상 위의 세 `-f`와 같은 프로젝트명/환경변수를 유지하도록 바꿔 실행합니다.** 기본 파일만 사용하면 원본 volume 대신 새 기본 volume으로 컨테이너가 재구성될 수 있습니다. 예:

```text
docker compose -f databases/postgresql/compose.yaml -f databases/postgresql/compose.legacy-volume.yaml -f lab-workspaces/postgresql-image-pin.yaml stop
docker compose -f databases/postgresql/compose.yaml -f databases/postgresql/compose.legacy-volume.yaml -f lab-workspaces/postgresql-image-pin.yaml start
docker compose -f databases/clickhouse/compose.yaml -f databases/clickhouse/compose.legacy-volume.yaml -f lab-workspaces/clickhouse-image-pin.yaml stop
docker compose -f databases/clickhouse/compose.yaml -f databases/clickhouse/compose.legacy-volume.yaml -f lab-workspaces/clickhouse-image-pin.yaml start
```

롤백이 필요하면 새 DB를 먼저 중지하고 volume에 writer가 없는지 다시 확인합니다. 새 image가 이미 데이터 형식을 바꿨을 수 있으므로 **기존 컨테이너를 무조건 다시 시작하지 않습니다.** 이전 image와 데이터의 호환성이 검증된 경우에만 원래 환경을 재개하고, 그렇지 않으면 검증한 백업을 별도 대상으로 복원합니다. 기존 컨테이너·volume·백업을 정리하는 작업은 이 전환 절차에 포함하지 않습니다.

이 문서는 사용자 수행 지침입니다. Compose 파일 검사만으로 데이터 전환·복원·엔진 기동이 검증되었다고 기록하지 않습니다. 실제 변경 검증 범위는 [구성 검증 기록](compose-validation.md)을 확인합니다.
