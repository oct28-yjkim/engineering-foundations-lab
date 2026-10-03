# 강의 4 — memory, spill, 파일 배치는 서로 다른 자원 문제다

LOCAL-SPARK 추가 구현 과제입니다. 기준 Spark 4.0.4. 부하 증가 전 CPU·RAM·disk 상한과 종료 조건을 정하고 OS가 불안정해질 정도의 OOM·disk-full 주입은 하지 않습니다.

<a id="sp07"></a>
## SP07 — executor memory를 늘리기 전에 실패 장소를 찾는다

### 원리와 가설

driver 결과 수집, JVM execution/storage memory, Python worker RSS, Arrow/native memory, direct/off-heap buffer, OS page cache를 구분합니다. executor heap 설정 하나로 전체 process tree의 memory가 제한되는 것은 아닙니다. [공식 memory·GC 튜닝](https://spark.apache.org/docs/4.0.4/tuning.html)을 읽고 실제 배포의 container/프로세스 한도와 대조합니다.

교육용 예산을 먼저 계산합니다.

```text
호스트 요구량 ≈ JVM heap + JVM 외 native + Python workers + OS 여유분
동시 task의 build/state 요구량 ≈ Σ 각 task의 peak working set
```

메모리 영역 공유와 peak 시점 때문에 항들을 독립 실측 없이 단순 합산해 정확한 RSS 예측이라 부르지 않습니다. 목적은 “입력 파일 1GB→RAM 1GB” 같은 잘못된 가설을 제거하는 것입니다.

### 추가 실험

1. 같은 행 수에 좁은 정수 row와 넓은 문자열 row를 만들고 입력 byte·결과 hash를 기록합니다.
2. cores를 고정한 채 partition 수를 바꾸고, 그 다음 partition 수를 고정한 채 동시 task 수를 바꿉니다. 한 번에 두 변수를 바꾸지 않습니다.
3. cache off/on에서 materialization·두 번째 action·unpersist 뒤를 따로 측정합니다. execution memory와 storage의 상호작용을 source와 대조합니다.
4. groupBy/sort/join별 memory spill·disk spill·GC time·peak RSS를 수집합니다. spill은 정상적인 완충 전략일 수 있으므로 0 spill만 목표로 삼지 않습니다.
5. driver에 작은 aggregate만 수집한 조건과 제한된 행을 수집한 조건을 비교합니다. 전체 데이터 `collect`를 해결책으로 쓰지 않습니다.

### 장애 분류 과제

실제 위험한 OOM 대신 합성 로그 또는 안전한 낮은 테스트 한도로 다음을 분류합니다: driver result 한도 초과, executor JVM heap 오류, container memory 종료, Python worker 종료, disk 공간 부족. 각 경우 어떤 metric이 증가해야 하는지, 증가하지 않으면 어떤 가설을 기각하는지 적습니다. exit code 하나로 GC 문제라고 결론 내리지 않습니다.

### 통과

적어도 세 경쟁 가설 중 두 개를 근거로 배제합니다. 안전한 한도 안에서 설정 변경 전후의 동일 결과를 확인하고, task concurrency·row width·cache 영향 중 하나를 인과적으로 설명합니다. [UnifiedMemoryManager·BlockManager](../source-reading.md)에서 ownership과 eviction 경계를 연결합니다.

<a id="sp08"></a>
## SP08 — 파일 수, row group, partition pruning

### 원리

파일 경로의 partition directory, Spark 실행 partition, Parquet row group, table format의 metadata는 별개입니다. directory partition pruning, column pruning, predicate pushdown, row-group 통계에 의한 skip은 동일한 최적화가 아닙니다. `PushedFilters`가 보인다는 이유로 반환 row만 디스크에서 읽었다고 주장하지 않습니다. [Parquet 문서](https://spark.apache.org/docs/4.0.4/sql-data-sources-parquet.html).

단순 비용 모형은 `T ≈ 파일 수×open/list 고정 비용 + 실제 scan bytes/유효 bandwidth + decode 비용`입니다. 병렬성과 cache가 빠진 설명용 식이며 실제 object store 성능을 로컬 SSD로 추정하지 않습니다.

### 동일 데이터·세 layout

학습용 새 출력 디렉터리를 run마다 만들고 overwrite/delete는 사용하지 않습니다. 날짜 4개·고객 key·정수 금액·넓은 payload를 가진 동일 fixture를 다음으로 저장합니다.

1. 비교적 적은 수의 파일, 날짜별 partition directory 없음.
2. 날짜별 partition directory, 각 날짜에 적정한 복수 파일.
3. 같은 날짜 partition이나 훨씬 많은 작은 파일.

전체 row multiset과 날짜별 합계를 별도 Python 원장으로 비교합니다. 행 정렬이 다를 수 있으므로 byte-identical 파일을 정답 조건으로 요구하지 않습니다.

### 추가 측정

- 날짜 필터 없음/있음, 넓은 payload 조회 없음/있음의 네 질의를 실행합니다.
- formatted plan의 read schema·partition filters·pushed filters와 선택 파일 수·읽은 bytes를 연결합니다.
- caching·OS cache 영향이 달라질 수 있으므로 cold/warm을 구분하고 모든 비교 순서를 섞습니다.
- 날짜를 문자열로 저장한 조건과 DATE로 저장한 조건의 parsing·predicate 차이를 검사합니다.
- schema가 충돌하는 파일을 별도 새 경로에 넣고 실패/허용 정책을 정의합니다. 조용한 NULL 발생을 schema evolution 성공으로 기록하지 않습니다.

### 반례와 통과

`coalesce(1)`로 파일 수를 최소화했더니 쓰기 critical path가 하나가 되는 반례를 설명합니다. partition key cardinality를 크게 늘려 directory 수가 폭증하는 경우도 비용 표에 포함합니다. 작은 파일 병합은 Parquet 데이터를 다시 쓰는 작업일 수 있고 transaction table의 안전한 compaction과 같지 않습니다.

세 layout에서 정답이 같고 적어도 하나의 pruning이 실제 읽기 지표로 확인되어야 합니다. 작은 fixture 때문에 통계적 성능 차이가 없으면 “차이 미확인”을 허용하되 최적화 성공 수치를 만들지 않습니다. [ParquetFileFormat](../source-reading.md)의 필터 전달·읽기 경로를 한 개 추적합니다.
