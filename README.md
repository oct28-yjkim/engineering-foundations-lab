# Engineering Foundations Lab — Zero to Hero

데이터베이스를 사용하는 단계에서 출발해 **동작을 예측하고, 내부 구현을 추적하며, 장애와 성능 문제를 증거로 설명하는 엔지니어**로 성장하기 위한 한국어 교육 과정입니다. 현재 PostgreSQL과 ClickHouse 트랙을 제공합니다.

SQL 작성, 저장 구조, 실행 엔진, 동시성, 복구, 복제, 성능 측정, 소스 코드 분석을 하나의 경로로 연결합니다. 가장 높은 단계의 완료 기준은 낯선 현상을 최소 재현으로 줄이고, 원인을 코드와 측정값으로 설명하며, 수정안의 회귀를 검증하는 것입니다.

## 시작할 곳

| 문서 | 역할 |
| --- | --- |
| [전체 교육 과정](databases/README.md) | 수준 진단, 72주 경로, 통과 기준 |
| [공통 기초 8주](databases/shared/foundations.md) | SQL·자료구조·OS·확률·분산 시스템의 연결 |
| [PostgreSQL](databases/postgresql/README.md) | 14개 모듈, 저장·MVCC·planner·WAL·운영 |
| [ClickHouse](databases/clickhouse/README.md) | 14개 모듈, MergeTree·실행 pipeline·집계·분산 |
| [실험 방법](databases/shared/experiment-method.md) | 재현성, 측정 오차, 정확성 oracle, 반증 |
| [통합 연구 8주](databases/shared/capstone.md) | PostgreSQL → 분석 저장소, CDC·복구·설계 검증 |
| [환경과 실행 범위](databases/shared/environment.md) | 실행 명령, 버전 고정, 제공/미제공 환경 |

## 시간 계획

처음부터 두 트랙을 순차로 공부한다면 공통 기반 8주 + PostgreSQL 28주 + ClickHouse 28주 + 통합 연구 8주, 총 **72주·약 864시간**을 기준으로 합니다. 주 12시간 가정이며 기간은 보장치가 아닙니다. 이미 익힌 내용은 진단 과제를 통과하면 줄이고, 복구·분산 실험에 실패하면 해당 모듈을 반복합니다.

기술 한 개에 집중하는 경우 공통 기반 8주와 해당 트랙 28주를 먼저 진행합니다. 소스 빌드, 별도 복제 환경 구성, 실제 업무 경험을 더하면 기간이 늘어날 수 있습니다. 숙련도는 자료를 읽은 횟수보다 재현 가능한 결과물로 평가합니다.

## 첫 실습

실행 중인 Docker Desktop의 Linux 컨테이너 엔진과 Docker Compose v2가 필요합니다. 저장소 루트에서 실행합니다. 아래 명령은 PowerShell과 Bash 모두에서 한 줄씩 사용할 수 있습니다.

```text
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose exec postgres psql -X -v ON_ERROR_STOP=1 -U lab -d lab
```

PostgreSQL 안에서 `SELECT version();`과 `SELECT count(*) FROM commerce.orders;`를 확인하고 `\q`로 나옵니다. ClickHouse는 다음 명령으로 접속합니다.

```text
docker compose exec clickhouse clickhouse-client --user lab --password lab_password --database lab
```

`SELECT version();`과 `SELECT count() FROM lab.events;`를 확인합니다. 상세 절차와 SQL 파일 실행은 [환경 안내](databases/shared/environment.md)를 따릅니다.

## 저장소에 제공되는 것

- 단일 노드 PostgreSQL 18 및 ClickHouse 26.8 Compose 구성과 결정적으로 생성되는 합성 데이터
- 기술별 커리큘럼, 원리·실험 강의, 소스 탐색 지도, 단계별 평가
- 기초 SQL 문제/답안, 읽기 전용 내부 상태 관찰 SQL
- 실험 기록 양식과 통합 연구 프로젝트 요구사항

복제 클러스터, Keeper, CDC connector, 부하 생성기, 디버그 빌드, 모니터링 스택은 심화 단계에서 학습자가 구성할 과제입니다. 현재 Compose를 실행하는 것만으로 이 구성들이 만들어지지는 않습니다. 문서에 기재한 기대 관찰값과 실행 계획은 실측 결과와 구분합니다.

기존 `sql/00_setup.sql`~`02_solutions.sql`은 입문 진단 및 워밍업 자료로 유지합니다. 기존 볼륨에는 바뀐 초기 데이터가 자동 반영되지 않습니다. 보존·재초기화 절차는 [환경 안내](databases/shared/environment.md)에 있습니다.
