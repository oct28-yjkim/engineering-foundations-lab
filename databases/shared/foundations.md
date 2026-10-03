# 공통 기반: 원리를 읽고 실험하는 8주

PostgreSQL/ClickHouse를 처음 배우는 사람은 F01부터 진행합니다. 각 모듈은 2주·24시간을 기준으로 하고, 모르는 프로그래밍 언어 구문은 필요한 만큼 보충합니다. 시작 환경은 [환경 안내](environment.md)를 사용합니다.

## F01 · 1–2주: 데이터, SQL, 정확성

선행 지식: 파일·디렉터리·터미널 사용. 학습 목표는 작은 데이터의 SQL 결과를 직접 계산하고 업무 정의와 쿼리의 차이를 발견하는 것입니다.

관계형 대수는 선택·투영·조인의 관계를 설명하지만 실제 SQL에는 중복을 허용하는 bag semantics와 NULL의 3값 논리가 있습니다. `COUNT(*)`, `COUNT(column)`, `COUNT(DISTINCT column)`은 같은 질문이 아닙니다. 하나의 주문을 여러 항목과 JOIN하면 주문 합계가 항목 수만큼 증폭될 수 있습니다. 먼저 결과의 grain, 즉 한 행이 무엇을 뜻하는지 정해야 합니다.

다음 PostgreSQL 실험은 기존 테이블을 바꾸지 않습니다.

```sql
WITH sample(v) AS (VALUES (1), (1), (NULL::integer))
SELECT count(*) AS rows, count(v) AS known_values,
       count(DISTINCT v) AS distinct_known, sum(v) AS total
FROM sample;
```

실행 전에 결과 `(3, 2, 1, 2)`를 설명하고, `WHERE v <> 1`을 넣었을 때 NULL이 선택되지 않는 이유를 적습니다. `IS DISTINCT FROM 1`과 비교합니다. 이어 주문 2건과 주문 항목 3개로 손계산 가능한 CTE를 만들고 JOIN 전후의 주문 금액 합계를 대조합니다.

ClickHouse에서는 `SELECT`로 같은 입력을 만들되 해당 자료형의 `Nullable` 여부와 집계의 NULL 처리를 확인합니다. SQL 문법이 닮았다고 결과 semantics까지 같다고 가정하지 않습니다.

**과제**: 주문 상태·취소·환불·환율·시간대·중복 이벤트를 포함한 매출 지표 정의서를 작성합니다. 돈은 최소 통화 단위 정수 또는 정확 십진수로 계산하고, 반올림 시점을 명시합니다. “구매 사용자/방문 사용자” 비율과 “방문 후 구매한 사용자” 퍼널을 별도 정의합니다.

**통과**: 5개 이상 작은 반례(중복·NULL·1:N JOIN·경계 시각·취소)를 준비하고 수기 결과와 두 엔진의 결과 차이를 설명합니다. 단순 행 수만 맞는 것은 정확성 검증으로 부족합니다.

읽기: [PostgreSQL SQL tutorial](https://www.postgresql.org/docs/18/tutorial-sql.html), [SELECT의 처리와 DISTINCT](https://www.postgresql.org/docs/18/sql-select.html). 다음 단계에서 만드는 데이터 생성기도 이 정확성 계약을 지켜야 합니다.

## F02 · 3–4주: 자료구조, CPU, 메모리, 저장 장치

선행: F01. 목표는 알고리즘 복잡도와 하드웨어 비용을 함께 설명하는 것입니다.

정렬된 N개 키의 이진 탐색은 비교 횟수를 줄이지만, 데이터가 어디에 놓였는지에 따라 cache miss와 random I/O가 지배할 수 있습니다. B-tree는 큰 fan-out으로 탐색의 page 접근 단계를 줄입니다. hash join은 예상 O(N+M)이어도 hash table·문자열·pointer·부하율의 메모리가 충분해야 합니다. 자료형 폭과 key 분포가 달라지면 동일 행 수에서 전혀 다른 결과가 나올 수 있습니다.

row storage는 소수 행의 여러 필드를 한 번에 읽는 경우, column storage는 많은 행의 소수 열을 집계하는 경우에 유리한 비용 구조를 가집니다. 압축은 저장·I/O 비용을 줄이지만 해제 CPU를 필요로 합니다. 따라서 “더 작은 파일”과 “더 짧은 응답”은 별도 측정 항목입니다.

**손계산**: 1억 행, 행당 200바이트에서 전체 논리 데이터 크기를 계산합니다. 쿼리가 8바이트 필드 2개만 읽는다고 할 때 투영만으로 줄어드는 논리 바이트 비율을 구합니다. 압축·헤더·index·복제본·실제 I/O는 이 계산에서 제외했음을 명시합니다. `T ≳ max(bytes / bandwidth, CPU work / CPU capacity)`를 이상화한 하한으로 사용하고, 직렬 실행·동기화·network가 더해지면 왜 달라지는지 설명합니다.

**구현 실험**: 익숙한 언어로 입력 배열을 만드는 프로그램을 작성합니다. 동일 key·payload 데이터에 대해 선형 탐색, 정렬 후 이진 탐색, hash lookup을 비교합니다. 입력 생성·정렬 준비 시간과 lookup 시간을 분리하고, 모든 결과가 같음을 먼저 확인합니다. 균등 key와 특정 key에 80%가 몰리는 입력을 각각 사용합니다. 라이브러리가 최적화된 정도를 DB 엔진 전체 성능으로 일반화하지 않습니다.

**관측 실험**: PostgreSQL의 `pg_relation_size`, `pg_indexes_size`, `pg_total_relation_size`를 비교하고 ClickHouse의 `system.parts`에서 compressed/uncompressed bytes와 active parts를 확인합니다. 논리 데이터와 파일 크기가 일치하지 않는 이유를 네 가지 이상 적습니다.

**통과**: 알고리즘 O 표기만으로 실행 시간을 단정하지 않으며, 행 수·바이트·메모리·I/O 접근 패턴을 포함한 비용 모델을 제출합니다. CPU cache, OS page cache, DB buffer cache의 경계를 구분합니다.

읽기: [PostgreSQL physical storage](https://www.postgresql.org/docs/18/storage.html), [ClickHouse MergeTree](https://clickhouse.com/docs/engines/table-engines/mergetree-family/mergetree). PG page와 CH granule은 서로 대응하는 동일 단위가 아닙니다.

## F03 · 5–6주: 통계, 실험 설계, tail latency

선행: F02. 평균이 좋아도 일부 요청이 느려지는 이유와 관측된 개선이 재현 가능한지를 다룹니다.

관측 시간에는 서버 실행 외에 connection acquisition, 전송, 결과 decoding, client processing이 포함될 수 있습니다. 둘 중 어느 시간을 재는지 먼저 정합니다. 실행 계획의 cost는 벽시계 밀리초가 아니고, 내부 node의 시간과 buffer 값은 부모·자식에 중복 포함될 수 있습니다. 모든 값을 더해 전체 시간을 만들지 않습니다. [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html)

**분포 실험**: 가상의 100개 요청 중 95개가 10ms, 5개가 1000ms일 때 평균과 중앙값을 손으로 계산합니다. p95/p99는 사용한 quantile 정의에 따라 경계값이 달라질 수 있으므로 계산 함수를 함께 적습니다. 5번 실행한 결과로 p99를 주장하지 않습니다.

**DB 실험**: 기준 쿼리와 변경 쿼리를 번갈아 실행합니다. warm-up 3회와 측정 20회 이상을 구분하고 작은 실습에서의 임시 기준임을 적습니다. 결과 집합의 동일성을 먼저 확인한 후 latency 중앙값·분산·최솟값/최댓값, read rows/bytes 또는 buffers를 기록합니다. throughput 실험은 동시성 1→4→16을 단계적으로 올려 saturation 이전/이후를 비교합니다. 부하 도구는 심화 과제로 별도 준비합니다.

**대기열 사고 실험**: 안정된 조건에서 `L = λW`를 적용합니다. 초당 완료 요청 수가 일정한데 평균 응답 시간이 늘면 평균 진행/대기 요청 수가 어떻게 변하는지 계산합니다. 자원이 포화된 불안정 구간의 유입률을 완료율과 혼동하지 않습니다. 원인 후보를 CPU·I/O·lock·merge·client 제한으로 나누고 하나씩 반증합니다.

**통과**: [실험 보고서](templates/experiment-report.md)에 정확성 oracle, 독립 변수, 통제 변수, 원본 결과, 개선이 재현되지 않는 조건을 기록합니다. 캐시 상태를 입증하지 못하면 “cold” 대신 “첫 실행, cache 상태 미확인”이라고 표기합니다.

## F04 · 7–8주: 실패, 복제, 분산 보장

선행: F03. 응답 성공·디스크 영속성·다른 노드의 가시성을 서로 다른 사건으로 이해합니다.

쓰기에는 요청 전송, 수신, 처리, 영속화, 복제, 응답 전송 같은 단계가 있습니다. client timeout은 서버가 쓰지 않았다는 증거가 아닙니다. 처리 후 응답만 유실됐다면 재시도가 중복을 만들 수 있습니다. idempotency는 요청 식별자만 붙이면 완성되는 기능이 아니라 식별자 저장의 원자성, 보관 범위, 충돌 처리까지 포함한 계약입니다.

**이력 실험**: 10개의 가상 주문 이벤트에 `event_id`, `source_version`, `occurred_at`, `received_at`을 기록합니다. 중복 전송 2개, 순서 역전 2개, 삭제 뒤 늦게 도착한 update 1개를 추가합니다. append-only event log, 최신 상태 테이블, 매출 집계가 각각 무엇을 저장해야 하는지 수기로 검증합니다. 같은 이벤트 목록을 서로 다른 batch로 분할해도 최종 결과가 같아야 하는지 명시합니다.

**합의 사고 실험**: 3개 투표 노드에서 한 노드가 분리됐을 때 다수 쪽과 소수 쪽에 허용할 동작을 정합니다. log entry가 복제됨, commit됨, state machine에 apply됨을 구별합니다. [Raft 원 논문과 설명](https://raft.github.io/)의 safety 조건을 자신의 이벤트 이력에 대응시킵니다. Keeper의 합의와 ClickHouse 사용자 데이터의 모든 연산이 동일한 transaction을 제공한다는 주장은 하지 않습니다.

**복구 설계**: RPO(허용 가능한 데이터 손실)와 RTO(서비스 회복 시간)를 숫자로 정합니다. 복제본에 논리 삭제가 전파됐을 때 어디서 복구할지 답합니다. 백업 파일 존재가 아니라 별도 인스턴스 restore 후 업무 데이터의 일치 여부를 통과 기준으로 정합니다. PostgreSQL 구현 실습은 [PITR](https://www.postgresql.org/docs/18/continuous-archiving.html)과 트랙 복구 모듈로 이어집니다.

**통과**: “replication=backup”, “timeout=실패 확정”, “exactly once=어떤 범위에서도 중복 없음”이라는 오해를 각각 반례 하나로 설명하고, 관찰할 수 없는 상태는 unknown으로 남기는 이력표를 제출합니다.

## 공통 과정 종료 구술

30분 동안 다음 질문을 설명하고, 답이 틀릴 수 있는 조건도 말합니다.

1. 행 수가 같은 두 테이블의 hash aggregation 메모리가 10배 차이 나는 이유는?
2. index가 추가됐지만 더 느려지는 입력은 어떻게 만들 것인가?
3. 매출 합계가 맞아도 CDC 파이프라인이 틀릴 수 있는 이유는?
4. p99가 악화됐을 때 connection pool을 늘리면 무엇이 나아지고 무엇이 악화될 수 있는가?
5. 데이터베이스 두 개의 commit timestamp만으로 전역 순서를 확정할 수 있는가?

답변이 설정 이름 나열에 머물면 관련 실험을 보완한 뒤 [PostgreSQL](../postgresql/README.md) 또는 [ClickHouse](../clickhouse/README.md)로 진입합니다.
