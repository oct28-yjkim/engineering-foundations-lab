# Database Engineering — Zero to Hero

목표는 “무엇을 설정해야 하는가”와 함께 “왜 그 설정이 이 조건에서만 효과가 있는가”를 설명하는 것입니다. 한 쿼리의 요청부터 저장 장치와 복제본까지 추적하고, 지연·정확성·복구 가능성의 상충 관계를 실험으로 판단합니다.

## 제품별 선택 트랙

| 트랙 | 핵심 범위 | 실습 입구 |
| --- | --- | --- |
| [PostgreSQL](postgresql/README.md) | heap·MVCC·SSI·planner·WAL·vacuum·복구 | [공통 DB 환경](shared/environment.md) |
| [ClickHouse](clickhouse/README.md) | MergeTree·column/pipeline·집계·분산 | [공통 DB 환경](shared/environment.md) |
| [MySQL](mysql/README.md) | InnoDB·read view·next-key lock·optimizer·redo/binlog·GTID·복구 | [실제 MySQL·SQL 진단 환경](mysql/labs/README.md) |

각 제품은 **28주·14모듈·336시간** 선택 과정입니다. 아래 72주 표는 기존 PostgreSQL+ClickHouse 경로이며 MySQL을 자동 가산하지 않습니다. MySQL 중심이면 공통 8주 + MySQL 28주를 먼저 진행하고 [선택 연구 8주](../capstones/mysql-transaction-recovery.md)를 추가합니다. 세 DB를 모두 순차 이수할 때는 공통 8주 + 트랙 84주 + 선택 연구 8주 = **100주·약 1,200시간**입니다. 모든 DB 이수가 실무 적용의 전제는 아닙니다.

## 시작점 진단

아래 결과물을 먼저 만들어 통과한 범위만 건너뜁니다. 명령을 알고 있어도 예상 결과를 설명하지 못하면 해당 부분을 학습합니다.

| 진단 | 수행 과제 | 성공 증거 | 부족할 때 |
| --- | --- | --- | --- |
| SQL·데이터 모델 | 중복·NULL·취소 주문을 포함한 매출, 최신 상태 쿼리 | 손으로 계산한 작은 데이터와 SQL 결과 일치 | 공통 F01 |
| 자료구조·OS | 순차/임의 읽기, page/column, hash/sort 비용 추정 | 데이터 크기와 메모리 조건별 병목 가설 | 공통 F02 |
| 측정 | 동일 쿼리의 cold/warm 의미와 반복 편차 비교 | 실행 환경·원본 측정·오차 설명 | 공통 F03 |
| 분산·복구 | 응답 유실 후 재시도, replica 장애 구분 | 중복/유실을 검출하는 이벤트 이력 | 공통 F04 |
| 엔진 실무 | 실제 느린 쿼리 한 개와 lock/merge 현상 설명 | 전후 plan·측정·반례 | 각 트랙의 기초 모듈 |

## 전체 경로

| 순서 | 기간/시간 예시 | 내용 | 다음 단계 진입 조건 |
| --- | --- | --- | --- |
| 공통 기반 | 1–8주 / 96h | F01–F04, 모델·알고리즘·OS·측정·분산 | 작은 데이터의 정확성 검증과 반복 실험 |
| PostgreSQL | 9–36주 / 336h | PG 14개 모듈, 2주씩 | 트랙 평가의 필수 실험과 source trace |
| ClickHouse | 37–64주 / 336h | CH 14개 모듈, 2주씩 | 트랙 평가의 필수 실험과 source trace |
| 통합 연구 | 65–72주 / 96h | CDC, 운영 SLO, 장애·복구, 연구 보고 | 종합 프로젝트와 구술 방어 |

트랙 안의 주차는 1–28주로 표기합니다. 두 트랙의 순서는 업무 우선순위에 따라 바꿀 수 있습니다. 공통 과정·통합 과정은 각각 한 번만 이수합니다. 병렬 학습은 가능한 시간이 충분할 때 선택하며, 의존 관계와 증거 기준을 생략하지 않습니다.

이 표는 PostgreSQL+ClickHouse 전용 72주 경로입니다. [Kafka 28주 트랙](../streaming/kafka/README.md)을 더하면 공통 8주 + PostgreSQL 28주 + Kafka 28주 + ClickHouse 28주 + 통합 8주, **100주·약 1,200시간**의 확장 경로가 됩니다. 자세한 순서와 시스템별 보장 비교는 [이벤트 스트리밍 과정](../streaming/README.md)을 봅니다.

## 각 모듈을 공부하는 방식

2주 24시간을 예로 들면 원리와 공식 문서 6시간, SQL·시스템 실험 10시간, 코드 탐색 4시간, 보고서·구술·복습 4시간을 배분합니다. 초반에는 코드 읽기 시간을 자료구조 구현에, 후반에는 원리 시간을 논문과 회귀 테스트에 옮길 수 있습니다.

1. 입력·출력·불변식을 적고 실행 결과를 먼저 예측합니다.
2. 두 경쟁 가설을 세웁니다. 예: “disk I/O가 줄었다”와 “cache가 따뜻해졌다”.
3. 한 변수를 바꿔 실험하고, 가설을 구별할 수 있는 지표를 수집합니다.
4. 내부 구조 또는 소스 경로가 관측값을 어떻게 만들었는지 설명합니다.
5. 선택이 나빠지는 데이터 분포·동시성·실패 조건을 하나 이상 재현합니다.
6. 다른 사람이 재현할 수 있는 결과물을 제출합니다.

기록은 [실험 방법](shared/experiment-method.md)과 [실험 보고서 양식](shared/templates/experiment-report.md)을 사용합니다.

낯선 용어는 [용어집](shared/glossary.md)에서 시작합니다. 내부 구조를 익힌 뒤에는 [연구 논문과 작은 엔진 구현](shared/research-reading.md)을 소스 분석과 함께 진행합니다.

## 숙련도와 평가

다음은 이 저장소의 교육 평가 기준입니다. 직무 자격이나 실제 숙련도에 대한 보증이 아닙니다.

| 단계 | 할 수 있어야 하는 일 | 요구 증거 |
| --- | --- | --- |
| L0 기초 | 작은 입력의 결과·NULL·중복·정확 금액 설명 | 정답 oracle와 반례 |
| L1 실무 | 실행 계획·운영 지표로 병목 조사 | 재현 스크립트, baseline, 개선 비용 |
| L2 내부 구조 | page/part/상태 전이·메모리·잠금의 인과 설명 | 코드 경로·구조체·관측값 연결 |
| L3 운영 설계 | 장애·재시도·복구·용량의 보장 범위 설계 | 복구 실측, 실패 이력, SLO와 runbook |
| L4 연구·기여 | 모르는 문제 최소 재현, 구현 또는 회귀 테스트 | 검증된 패치/실험 구현, 리뷰 대응 |

공통 평가를 정확성 25점, 원리·코드 연결 25점, 실험·반증 25점, 운영·재현성 25점으로 나눕니다. **총 80점 이상과 각 영역 15점 이상**을 통과 기준으로 삼습니다. 트랙 평가의 필수 gate도 모두 충족해야 합니다. 빠른 쿼리라도 금액·중복·복구 검증에 실패하면 재제출합니다.

L4 결과물은 upstream PR 채택 여부와 분리해서 평가합니다. 공개 보고·기여는 사용자가 결정할 일이며, 로컬 패치·테스트·설계 리뷰까지로도 학습 증거를 만들 수 있습니다.

## 두 시스템을 함께 배우는 이유

| 같은 질문 | PostgreSQL에서 추적할 것 | ClickHouse에서 추적할 것 |
| --- | --- | --- |
| 한 행이 어디에 있는가? | relation fork, heap page, TID, tuple header | data part, mark, granule, compressed column |
| 무엇을 안 읽는가? | index, bitmap, visibility map, partition pruning | sparse index, skip index, PREWHERE, projection |
| 변경은 언제 보이는가? | snapshot, transaction ID, WAL/commit | inserted blocks, replica 지연, merge-time semantics |
| 같은 키가 두 번 오면? | unique constraint와 transaction conflict | engine·버전·dedup token·조회 semantics |
| 삭제 후 용량이 왜 남는가? | MVCC horizon, vacuum, free space 재사용 | part 교체, mutation/TTL, merge·retention |
| 재시도해도 맞는가? | transaction retry, idempotency key | 적재 dedup 범위, materialized view, late events |
| 장애 후 맞게 복구됐는가? | base backup, WAL, LSN, timeline, 업무 불변식 | backup metadata/data, 복제 상태, 원본 재처리·집계 대조 |

각 트랙은 특정 강점을 중심으로 다루지만 “PostgreSQL은 분석 불가”, “ClickHouse는 어떤 UPDATE도 불가” 같은 이분법을 사용하지 않습니다. 지원 기능의 이름과 해당 버전에서 제공하는 보장을 구별합니다.

MySQL과 PostgreSQL을 비교할 때는 clustered row/secondary lookup과 heap/TID, read view+undo와 tuple visibility+vacuum, next-key lock과 SSI predicate conflict를 같은 용어로 합치지 않습니다. InnoDB의 RR consistent read와 current read, PostgreSQL의 isolation 동작은 같은 세션 사건표·업무 불변식으로 대조합니다. [MySQL 소스 지도](mysql/source-reading.md)는 server/handler/InnoDB 경계를 따로 추적합니다.

## 최종 포트폴리오

- 트랙별 핵심 실험과 source trace를 연결한 결과 목록
- 정상 조건 외에 skew, 높은 동시성, 데이터 증가, 장애 주입 결과
- 각 엔진의 실제 restore 검증 보고서와 데이터 정확성 증거
- [통합 캡스톤](shared/capstone.md)의 아키텍처·CDC 계약·운영 비용·구술 리뷰
- [설계 결정 기록](shared/templates/design-review.md)과 [장애 분석 기록](shared/templates/incident-review.md)
