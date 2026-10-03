# M05–M06. 텍스트에서 Processor 실행까지

[커리큘럼](../curriculum.md) · 이전: [저장 구조](02-storage-and-pruning.md) · 다음: [JOIN과 집계](04-joins-and-aggregation.md)

## M05 텍스트에서 실행 계획까지 LOCAL SOURCE

**선수 조건:** M04, 트리·방향 그래프, C++ 클래스와 참조.

### 원리

parser는 텍스트 구조를 AST로 표현합니다. analyzer는 식별자·타입·함수·테이블을 해석하고 query tree에 의미를 부여합니다. planner는 실행 단계를 구성하며 최적화가 적용될 수 있습니다. query pipeline은 그 단계를 실제 데이터 흐름으로 구체화합니다. 단계마다 해결하는 질문이 다르므로 AST 모양만 보고 실제 읽기량이나 병렬성을 결론내리지 않습니다. [Analyzer 설명](https://clickhouse.com/docs/guides/developer/understanding-query-execution-with-the-analyzer)

필터 pushdown은 더 적은 데이터를 후속 단계로 보내려는 변환입니다. 그러나 JOIN 종류·NULL 의미·집계 전후의 식에 따라 결과를 바꿀 수 있습니다. 상수 전파, 불필요한 열 제거, 집계 최적화도 성능 수치보다 먼저 동등성의 전제가 있습니다. 최적화 이름을 외우는 대신 입력·출력과 적용 조건을 소스에서 찾습니다.

### 실험

아래 SELECT에 네 EXPLAIN을 적용합니다. 각 EXPLAIN 문장 아래의 SELECT는 동일해야 합니다.

```sql
EXPLAIN AST
SELECT country, sum(revenue) AS total
FROM lab.events
WHERE event_type = 'purchase' AND event_date >= '2026-02-01'
GROUP BY country ORDER BY total DESC;

EXPLAIN QUERY TREE
SELECT country, sum(revenue) AS total
FROM lab.events
WHERE event_type = 'purchase' AND event_date >= '2026-02-01'
GROUP BY country ORDER BY total DESC;

EXPLAIN indexes = 1, actions = 1
SELECT country, sum(revenue) AS total
FROM lab.events
WHERE event_type = 'purchase' AND event_date >= '2026-02-01'
GROUP BY country ORDER BY total DESC;

EXPLAIN PIPELINE
SELECT country, sum(revenue) AS total
FROM lab.events
WHERE event_type = 'purchase' AND event_date >= '2026-02-01'
GROUP BY country ORDER BY total DESC;
```

AST의 country 식별자가 어느 테이블·타입으로 해석되는지, 합계의 입력/결과 타입, filter와 aggregate의 상대적 위치, 읽기 source와 최종 sort를 연결합니다. 사용 버전에서 옵션이 지원되지 않으면 오류와 `SELECT version()`을 보존하고 동일 목적의 지원 옵션으로 수정합니다.

다음 두 변형을 비교합니다. 먼저 결과 동등성을 자신의 입력에서 확인하고, 동등성 범위를 설명합니다.

- `event_date >= date`를 raw `event_time` 범위로 변경: 타임존·일 경계와 쿼리 범위를 고정해야 합니다.
- 합계 전 `WHERE revenue > 0`와 합계 후 `HAVING sum(revenue) > 0`: 음수 조정 이벤트를 넣으면 일반적으로 동등하지 않습니다. 이 반례를 사용해 단순 pushdown의 한계를 설명합니다.

**SOURCE 과제:** [코드 지도](../source-reading.md)의 `QueryAnalyzer`, `Planner`, `QueryPlan`을 따라 3개 경계를 고릅니다. 각 경계에서 입력 자료구조·출력 자료구조·소유권·오류를 기록하고 실제 함수명과 commit permalink를 남깁니다. 최신 master에서 본 함수를 26.8 호출 경로로 간주하지 않습니다.

**기대 증거:** 네 EXPLAIN 원문과 노드 대응표, 동등한 변형 1개와 동등하지 않은 반례 1개. EXPLAIN은 실행 결과나 실측 시간 증거가 아니므로 별도 실행 통계를 붙입니다.

**실패 모드:** 계획상의 행 흐름과 CPU 실행 순서를 동일시, 타입 cast로 필터 의미 변경, plan의 추정이나 표시를 실제 read bytes라고 보고, 다른 쿼리의 로그를 연결.

**제출·통과:** 10분 동안 텍스트→타입 해석→읽기 범위→집계→정렬→결과 경로를 설명하고, 코드와 계획의 각 경계를 3곳 이상 연결합니다.

## M06 Processor 병렬성 메모리와 관측 LOCAL SOURCE

**선수 조건:** M05, 스레드·동기화·캐시·backpressure.

### 원리

Processor는 입력/출력 포트를 가진 처리 단위입니다. `prepare()`가 데이터·포트 상태에 따라 다음 작업 가능성을 판단하고 `work()`가 계산을 수행하는 계약을 [고정 버전 IProcessor](https://github.com/ClickHouse/ClickHouse/blob/v26.8.1.2041-lts/src/Processors/IProcessor.h)에서 읽습니다. 모든 Processor가 자신의 전용 OS thread를 가진다는 뜻이 아닙니다. 입출력 기다림과 작업 가능 상태, downstream이 막힌 상태를 구분해야 pipeline의 정체를 이해할 수 있습니다.

읽기·부분 집계는 병렬화할 수 있어도 최종 병합·정렬·전송에 병목이 남습니다. 동시 query가 증가하면 단일 query의 최대 병렬성보다 전체 시스템의 메모리·CPU·I/O 예산이 중요해집니다. 부분 집계마다 상태를 가지면 thread 증가와 peak memory가 함께 증가할 가능성도 있습니다. `max_threads`는 실행 환경에서 사용 가능한 실제 코어 수나 항상 점유하는 thread 수를 보장하지 않습니다.

### 실험

```sql
EXPLAIN PIPELINE
SELECT user_id, sum(duration_ms) AS s
FROM lab.events GROUP BY user_id ORDER BY s DESC LIMIT 100
SETTINGS max_threads = 1;

EXPLAIN PIPELINE
SELECT user_id, sum(duration_ms) AS s
FROM lab.events GROUP BY user_id ORDER BY s DESC LIMIT 100
SETTINGS max_threads = 4;

SELECT /* m06_threads1_r1 */ user_id, sum(duration_ms) AS s
FROM lab.events GROUP BY user_id ORDER BY s DESC, user_id LIMIT 100
SETTINGS max_threads = 1, max_memory_usage = 268435456;

SELECT /* m06_threads4_r1 */ user_id, sum(duration_ms) AS s
FROM lab.events GROUP BY user_id ORDER BY s DESC, user_id LIMIT 100
SETTINGS max_threads = 4, max_memory_usage = 268435456;
```

`max_threads=1,2,4`로 각 5회 측정합니다. host가 2코어면 4thread 조건은 oversubscription 가설을 검증하는 조건이라고 명시합니다. 정렬 동률을 위해 user_id를 tie-breaker로 사용하고 같은 결과 집합을 확인합니다. 예산 부족 오류는 그대로 보존합니다. 시스템 전체 OOM을 유도하는 것이 목적이 아닙니다.

query log의 해당 query_id에서 `ProfileEvents`를 조회하고 다음 항목의 의미를 runtime에서 확인합니다.

```sql
SELECT event, description
FROM system.events
WHERE event ILIKE '%CPU%' OR event ILIKE '%Read%' OR event ILIKE '%External%'
ORDER BY event;

SELECT query_id, query_duration_ms, read_rows, read_bytes, memory_usage, ProfileEvents
FROM system.query_log
WHERE type = 'QueryFinish' AND query LIKE '%/* m06_%'
  AND query NOT LIKE '%system.query_log%'
ORDER BY event_time_microseconds DESC LIMIT 15;
```

CPU 시간 총합은 여러 thread 때문에 wall time보다 클 수 있습니다. query log의 `memory_usage`를 host RSS와 동일시하지 않습니다. `system.processors_profile_log`, `system.trace_log`는 설정·권한·sampling을 확인해야 쓰며 기본 Compose에서 항상 활성화되어 있다고 가정하지 않습니다. 필요하면 설정 변경안을 별도 작성하고 수집 비용까지 평가합니다.

**SOURCE/별도 빌드 과제:** `PipelineExecutor`에서 runnable processor가 작업으로 이어지는 지점을 추적합니다. 소스와 symbol이 일치하는 Linux 개발 환경에서 단일 query의 stack sample을 수집하고 추정 병목과 대조합니다. 빌드·debugger 환경은 저장소가 제공하지 않습니다. 프로파일 미수집을 실제 프로파일링 완료로 채점하지 않습니다.

**기대 증거:** pipeline의 변화, query별 CPU·wall·read·memory 비교, 1개 병목 가설의 반증 또는 지지. 50만 행에서 thread를 늘려도 개선되지 않을 수 있으며 이것도 정상적인 결과입니다.

**실패 모드:** thread 수를 무조건 증가, CPU 합계를 지연으로 보고, 캐시 warm-up 없이 비교, spill을 설정했다는 이유만으로 spill 발생을 주장, 병렬성이 정확성을 자동 보장한다고 가정.

**제출·통과:** 3개 thread 조건의 15회 측정, 병목 근거 2종 이상, Processor 상태 전이 그림, wall time을 설명하는 가설. 별도 빌드를 하지 않았으면 소스 추적과 동적 추적 완료 여부를 분리합니다.
