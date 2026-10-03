# Engineering Foundations Lab

업무에서 자주 접하는 데이터베이스와 클라우드 기술을 **개념 → 실습 → 성능 분석 → 운영 판단** 순서로 익히는 저장소입니다.

## 현재 학습 트랙

| 트랙 | 핵심 목표 | 시작 문서 |
| --- | --- | --- |
| ClickHouse | 대규모 분석 워크로드의 모델링·집계·운영 | [`databases/clickhouse`](databases/clickhouse/README.md) |
| PostgreSQL | 관계형 모델링·트랜잭션·인덱스·운영 | [`databases/postgresql`](databases/postgresql/README.md) |

## 빠른 시작

준비물은 실행 중인 Docker Desktop과 Docker Compose입니다.

```bash
docker compose up -d
docker compose ps
```

ClickHouse 접속:

```bash
docker compose exec clickhouse clickhouse-client \
  --user lab --password lab_password --database lab
```

PostgreSQL 접속:

```bash
docker compose exec postgres psql -U lab -d lab
```

초기 SQL은 컨테이너의 데이터 볼륨이 처음 생성될 때 한 번 실행됩니다. 처음부터 다시 실습하려면 아래 명령으로 **이 저장소가 만든 볼륨만** 삭제한 뒤 재시작합니다.

```bash
docker compose down -v
docker compose up -d
```

> 비밀번호는 로컬 실습 전용입니다. 외부에 노출되는 환경에서는 반드시 별도 비밀 값으로 교체하세요.

## 권장 학습 방식

1. 기술별 `README.md`의 핵심 개념과 판단 기준을 읽습니다.
2. `sql/01_exercises.sql`을 정답 없이 실행합니다.
3. 실행 계획과 시스템 지표를 먼저 해석합니다.
4. `sql/02_solutions.sql`과 비교하고 차이를 기록합니다.
5. 각 트랙의 미니 프로젝트와 운영 장애 시나리오를 수행합니다.

정답 SQL 자체보다 다음 질문에 답할 수 있는지를 기준으로 학습합니다.

- 왜 이 데이터 모델과 인덱스/정렬 키를 선택했는가?
- 데이터가 10배가 되면 무엇이 먼저 병목이 되는가?
- 변경이 쓰기 성능, 저장 공간, 운영 복잡도에 주는 비용은 무엇인가?
- 운영 환경에 적용하기 전에 어떤 지표와 실패 조건을 확인해야 하는가?

## 저장소 구조

```text
.
├── compose.yaml
└── databases
    ├── clickhouse
    │   ├── README.md
    │   └── sql
    │       ├── 00_setup.sql
    │       ├── 01_exercises.sql
    │       └── 02_solutions.sql
    └── postgresql
        ├── README.md
        └── sql
            ├── 00_setup.sql
            ├── 01_exercises.sql
            └── 02_solutions.sql
```
