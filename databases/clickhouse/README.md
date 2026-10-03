# ClickHouse: Zero to Hero, 내부 원리부터 운영 검증까지

목표는 SQL을 빠르게 작성하는 수준을 넘어, **결과의 정확성·처리 비용·실패 시 데이터 상태를 예측하고 코드와 실험으로 설명하는 엔지니어**가 되는 것입니다. 기존 4주 입문 과정을 14개 모듈, 명목상 28주 과정으로 확장했습니다. 주 12시간 기준 약 336시간이며, 일정이 아니라 모듈별 통과 증거로 다음 단계에 진입합니다. 수료가 전문성을 보장하지는 않습니다. 실제 장애 대응·복구·코드 리뷰까지 수행한 범위를 별도로 표시합니다.

## 학습 경로

공통 선수 과정은 [기초 원리](../shared/foundations.md), 실험 규칙은 [측정 방법](../shared/experiment-method.md), 환경 범위는 [환경 안내](../shared/environment.md)를 먼저 읽습니다. 두 DB를 연결하는 후속 과제는 [8주 통합 연구](../shared/capstone.md)입니다.

1. [전체 커리큘럼과 단계별 통과 기준](curriculum.md): 선수 지식, 14개 모듈, 주간 루틴.
2. [기초·자료형·열 지향 처리](lessons/01-foundations-and-types.md): M01–M02.
3. [MergeTree 저장 구조와 읽기 범위 선택](lessons/02-storage-and-pruning.md): M03–M04.
4. [Analyzer·계획·Processor 실행](lessons/03-query-engine.md): M05–M06.
5. [JOIN·집계·근사 알고리즘](lessons/04-joins-and-aggregation.md): M07–M08.
6. [적재·병합·갱신·Replacing 정확성](lessons/05-ingestion-and-correctness.md): M09–M10.
7. [집계 상태·MV·backfill·TTL](lessons/06-materialization-and-lifecycle.md): M11–M12.
8. [분산·Keeper·복구·워크로드 관리](lessons/07-distributed-and-recovery.md): M13–M14.
9. [버전을 고정한 소스 읽기](source-reading.md), [종합 프로젝트와 구술 평가](assessment.md).

## 실행 범위

| 표시 | 의미 | 현재 저장소에서 제공하는 것 |
| --- | --- | --- |
| `LOCAL` | 단일 ClickHouse에서 실행 | Compose, 50만 이벤트 seed, SQL 연습과 관찰 쿼리 |
| `SOURCE` | 소스 탐색; 빌드·디버거는 별도 환경 | 고정 릴리스의 코드 탐색 지도와 검증 절차 |
| `CLUSTER-DESIGN` | 다중 노드가 필요한 설계·실행 과제 | 토폴로지, 장애 주입 계획, 검증 기준; 클러스터 배포 파일은 미제공 |
| `OPS-DESIGN` | 백업 저장소·제한 계정·설정 파일 등이 필요한 과제 | 운영 실험 명세; 백업 디스크나 부하 발생기는 미구성 |

`CLUSTER-DESIGN` 문서를 읽은 것과 실험을 완료한 것은 다릅니다. M13–M14의 실행 증거가 없으면 수료 기록에 **단일 노드 과정 완료, 분산·운영 검증 미완료**라고 남깁니다.

## 시작

저장소 루트에서 실행합니다. PowerShell과 일반 셸에서 동일하게 사용할 수 있도록 명령을 한 줄로 적었습니다.

```text
docker compose up -d clickhouse
docker compose exec clickhouse clickhouse-client --user lab --password lab_password --database lab
```

접속 후:

```sql
SELECT version(), timezone();
SELECT name, value FROM system.build_options WHERE name ILIKE '%VERSION%' OR name ILIKE '%GIT%';
SHOW CREATE TABLE lab.events;
SELECT count(), uniqExact(event_id), min(event_time), max(event_time) FROM lab.events;
CREATE DATABASE IF NOT EXISTS ch_course;
```

`lab.events`는 기본 연습용, `ch_course`는 교재가 지시하는 별도 실험용입니다. 첫 초기화 시 seed는 500,000행입니다. 기존 Docker 볼륨이 있으면 초기화 SQL 변경이 자동 적용되지 않습니다. 현재 행 수가 다르면 원인을 기록한 후 실험 기준선을 정합니다. 기존 볼륨을 지우거나 seed를 중복 적재하는 방식으로 숫자를 맞추지 않습니다.

Compose의 이미지 `26.8`은 패치가 바뀔 수 있는 태그입니다. `SELECT version()`·이미지 digest·빌드 commit을 기록하고 [소스 버전 대응 절차](source-reading.md#실행-바이너리와-소스-맞추기)를 따릅니다. 문서는 26.8 계열을 기준으로 하며 최신 문서의 기능을 자동으로 이 환경에 적용하지 않습니다.

## 실습 파일과 반복 규칙

- [`sql/00_setup.sql`](sql/00_setup.sql): 최초 seed 생성용.
- [`sql/01_exercises.sql`](sql/01_exercises.sql): 먼저 직접 해결할 문제.
- [`sql/02_solutions.sql`](sql/02_solutions.sql): 자신의 결과와 대조할 답안. DDL·backfill 구간은 내용을 확인하고 필요한 구간만 실행합니다.
- [`sql/03_internals.sql`](sql/03_internals.sql): 내부 상태를 관찰하는 진단 쿼리.

Compose는 SQL 디렉터리를 `/lab/sql`로 읽기 전용 마운트합니다. 진단 파일은 저장소 루트에서 다음처럼 실행할 수 있습니다.

```text
docker compose exec -T clickhouse clickhouse-client --user lab --password lab_password --database lab --multiquery --queries-file /lab/sql/03_internals.sql
```

교재의 `CREATE TABLE`은 한 번만 실행하는 실험을 전제로 합니다. 같은 이름이 있으면 새 suffix로 실험을 분리하거나 자신이 만든 해당 테이블의 재사용 조건부터 검토합니다. `INSERT`와 backfill을 다시 실행하면 결과가 바뀝니다. 각 절은 **가설 → 예상 불변식 → 실행 → 실제 증거 → 반례 → 설계 결정** 순서로 기록합니다. 교재의 숫자는 입력 규모와 평가 기준이며, 실행했다고 주장하는 벤치마크 결과가 아닙니다.

## 반드시 끝까지 지킬 구분

- primary key는 유일성 제약이 아닙니다. 정렬 키, sparse index, 파티션의 역할을 분리합니다.
- 물리 merge가 끝나는 시각과 논리적으로 올바른 결과가 필요한 시각은 다릅니다.
- incremental MV는 삽입 블록에 반응합니다. 원본의 수정·삭제·중복 제거를 자동 재계산하지 않습니다.
- 근사 집계 오차, 이벤트 중복, 잘못된 JOIN으로 생긴 오차는 서로 다른 문제입니다.
- insert 응답, replica 반영, 사용자 읽기, 매체 내구성, 백업 복구는 각각 별도 보장입니다.

공식 문서의 보장과 실험 결과가 다르면 숨기지 말고 버전·설정·재현 조건부터 비교합니다. 각 강의 말미에 근거를 연결했습니다.
