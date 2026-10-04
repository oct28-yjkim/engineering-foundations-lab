# PostgreSQL: Zero to Hero → Internals & Production Engineering

SQL 입문부터 실행 계획, 페이지와 WAL, 동시성 제어, 복구·복제, 소스 코드까지 연결하는 **14모듈 심화 과정**입니다. 목표는 처음 보는 장애에서 가설을 세우고 관측·재현·소스 근거로 원인을 좁히며 복구의 안전성을 입증하는 것입니다. 완료는 읽은 분량이 아니라 [평가 기준](assessment.md)의 증거와 재현 결과로 판단합니다.

기준은 **PostgreSQL 18 계열**, 권장 페이스는 **28주 × 주 12시간 = 336시간**입니다. 처음 배우는 사람은 기초 모듈에 시간을 더 쓰고, 경험자는 진단 과제를 통과한 모듈만 압축합니다. 날짜보다 통과 기준을 우선하며, 특정 기간 이수가 전문성을 보장하지는 않습니다.

## 기본 LAB 입구

**정상 기능 → 동작 원리 → 관측 → 제약 → 진단·복구** 순서로 시작합니다. 계좌 두 행의 조회·짧은 트랜잭션부터 시작해 MVCC·잠금·실행 계획을 연결합니다. [제품별 기본 LAB 카드](operations.md#basic-lab)에서 정상 결과·직접 볼 지표·자주 만나는 사건 2개·회복 검산과 환경 제공 범위를 확인합니다.

[공통 LAB 계약](../../operations/lab-contract.md)을 적용하며 **28주 심화 과정을 먼저 마칠 필요는 없습니다.** 실행 환경이나 수동 준비가 필요한 단계는 준비/미실행으로 구분하고, 아래 심화 커리큘럼은 기본 LAB 이후 필요한 부분부터 확장합니다.

## 학습 경로

1. [전체 커리큘럼과 선수 지식](curriculum.md)을 읽고 진입 수준을 확인합니다.
2. [운영 실습](operations.md)에서 실제 서버 기준선·잠금·느린 쿼리·vacuum 진단을 먼저 수행하고, 강의의 원리로 원인을 설명합니다.
3. [소스 읽기 지도](source-reading.md)에서 해당 동작의 구현 경계를 추적합니다.
4. [평가·캡스톤](assessment.md)에 실행 증거를 모읍니다.

공통 기초가 부족하면 [공통 선수 지식](../shared/foundations.md)부터 시작합니다. 실험 기록은 [공통 실험 방법](../shared/experiment-method.md), 실행 제약은 [환경 안내](../shared/environment.md), 두 엔진의 통합 과제는 [공통 캡스톤](../shared/capstone.md)을 따릅니다.

| 모듈 | 강의 | 핵심 질문 |
| --- | --- | --- |
| M01–02 | [관계 모델·SQL·프로세스](lessons/01-foundations-and-architecture.md) | 정답인 SQL과 빠른 SQL을 어떻게 구분하며, 요청은 어떤 경로로 실행되는가? |
| M03–04 | [페이지·버퍼·WAL](lessons/02-storage-buffer-wal.md) | 행 변경이 언제 메모리에 있고 언제 내구성을 얻는가? |
| M05–06 | [MVCC·SSI·잠금](lessons/03-mvcc-ssi-locking.md) | 각 세션은 무엇을 볼 수 있고, 어떤 업무 불변식이 깨질 수 있는가? |
| M07–08 | [플래너·통계·인덱스](lessons/04-planner-and-indexes.md) | 추정 오차가 왜 잘못된 접근 경로로 이어지는가? |
| M09–10 | [실행기·I/O·HOT·Vacuum](lessons/05-executor-and-maintenance.md) | 병렬성과 메모리가 왜 오히려 느려지게 만들며, 버전은 언제 회수되는가? |
| M11–12 | [복구·복제·타임라인](lessons/06-recovery-and-replication.md) | 백업을 실제로 살릴 수 있고, 장애조치 후 무엇을 잃을 수 있는가? |
| M13–14 | [운영 판단·소스·캡스톤](lessons/07-production-and-capstone.md) | 관측에서 원인을 구별하고 근거 있는 변경을 제안할 수 있는가? |

## 실습 환경과 실행 범위

저장소 루트에서 [PostgreSQL 전용 Compose](compose.yaml)를 명시해 실행합니다. 프로젝트 `engineering-foundations-postgresql-lab`은 ClickHouse·다른 제품과 network·volume·수명 주기를 공유하지 않습니다. 초기 데이터는 사용자 1만 명, 상품 1천 개, 주문 10만 건, 주문 항목 30만 건입니다. 생성 SQL은 새 데이터 볼륨을 초기화할 때만 자동 실행됩니다. 재실행을 위해 기존 볼륨을 삭제하지 말고 각 강의의 별도 실험 테이블을 사용합니다.

이전에 루트 Compose를 사용했다면 **아래 기동 전에 [기존 환경 전환 안내](../shared/compose-migration.md)를 먼저 확인합니다.** 기본 구성은 새 프로젝트 volume을 사용하며 기존 데이터를 자동으로 옮기지 않습니다. 기존 컨테이너가 실행 중이면 같은 호스트 포트도 충돌할 수 있습니다.

```bash
docker compose -f databases/postgresql/compose.yaml up -d --wait postgres
docker compose -f databases/postgresql/compose.yaml exec postgres psql -X -U lab -d lab
```

접속한 `psql`에서:

```sql
\set ON_ERROR_STOP on
\timing on
SELECT version(), current_setting('server_version_num');
SELECT current_database(), current_user, pg_backend_pid();
SHOW block_size;
SHOW data_checksums;
SHOW io_method;
SELECT count(*) FROM commerce.orders;
```

실제 마이너 버전, 이미지 digest, OS/CPU/메모리 제한, 설정 변경, 데이터 크기를 기록합니다. `postgres:18`은 시간이 지나면 다른 마이너 빌드를 가리킬 수 있습니다. 재현 실험에서는 확인한 digest를 별도 실험 구성에 고정합니다. 소스는 같은 런타임 버전의 태그/커밋을 사용합니다.

| 표시 | 제공 범위 | 완료에 필요한 것 |
| --- | --- | --- |
| **S: 단일 노드** | 현재 Compose에서 실행 가능한 SQL·관찰·논리 백업/복원 | Docker 엔진, 필요한 경우 2–3개 psql 세션 |
| **E: 확장** | `pageinspect` 등 선택 확장 기반 페이지 관찰 | 해당 확장 설치 가능 여부·권한 확인 |
| **T: 별도 토폴로지** | PITR, 물리/논리 복제, 장애조치의 실험 설계와 판정 절차 | 격리된 별도 클러스터·보관소·네트워크 구성. 자동 배포는 제공하지 않음 |
| **B: 소스 빌드** | 디버깅·회귀/격리 테스트 과제 | 일치하는 소스, Linux/WSL2 개발 도구, 별도 debug 서버 |

**T/B 항목의 설계서 제출과 실행 완료는 다른 상태**입니다. 단일 노드 실행만으로 복제·PITR·소스 디버깅까지 검증했다고 기록하지 않습니다. 강의의 예상 증거는 관측할 항목이며, 미리 측정한 성능 결과가 아닙니다.

## SQL 자산 활용

- [00_setup.sql](sql/00_setup.sql): 주문 데이터와 기본 스키마. 데이터 모델의 전제부터 읽습니다.
- [01_exercises.sql](sql/01_exercises.sql): SQL·운영 기본 문제. 먼저 직접 풉니다.
- [02_solutions.sql](sql/02_solutions.sql): 답안 비교. 같은 결과·다른 계획이 가능한 이유를 설명합니다.
- [03_internals.sql](sql/03_internals.sql): 읽기 전용 내부 상태 진단. 시점별 원본 출력을 보관합니다.

각 강의 SQL은 명시한 순서와 세션에서 수동 실행합니다. `CREATE`가 있는 준비 블록은 최초 한 번 실행하며, 재실행은 새 이름/suffix를 정해 해당 실험 전체에 일관되게 적용합니다. 기존 객체를 덮어쓰거나 전체 스키마를 삭제하지 않습니다. `EXPLAIN ANALYZE`는 쿼리를 실제 실행하고, `ROLLBACK`도 이미 발생한 WAL·I/O·시퀀스 사용을 되돌리지는 않습니다. 쓰기 실험은 이름이 분명한 학습용 객체에서 수행합니다. 현재 `lab` 계정은 실습 편의를 위한 고권한 계정이며 운영 애플리케이션 역할의 예시가 아닙니다.

첫 주에는 환경 지문·정상 기준선을 저장하고 M01의 NULL/중복 반례와 주문 금액 검산을 실행합니다. 이후 M02에서 자신의 backend와 한 개의 대기 세션을 식별합니다. [운영 실습](operations.md)의 실제 사건 2개와 회복 후 검산은 단일 노드 운영의 필수 관문입니다. 환경이 없으면 설계·읽기까지만 진행하고 운영 완료로 표시하지 않습니다. 결과가 예상과 다르면 가설을 수정한 기록을 남깁니다.

공식 기준: [PostgreSQL 18 문서](https://www.postgresql.org/docs/18/), [18 릴리스 노트](https://www.postgresql.org/docs/18/release-18.html). 문서의 `/current/` 대신 `/18/` 링크를 사용하며, 릴리스 노트만으로 성능 향상을 단정하지 않습니다.
