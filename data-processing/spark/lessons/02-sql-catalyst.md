# 강의 2 — SQL 의미를 보존하면서 계획을 바꾸기

기준 Spark 4.0.4. 제공 batch 코드 위에 NULL·ANSI·UDF 변형을 추가 구현합니다. 성능보다 결과 동등성부터 검증합니다.

<a id="sp03"></a>
## SP03 — 분석·최적화·물리 계획의 경계

### 원리

사용자가 만든 unresolved plan, attribute/type이 해석된 analyzed plan, 규칙으로 변환된 optimized plan, 물리 연산자와 distribution이 결정된 plan을 구분합니다. “Catalyst가 최적화했다”는 문장 대신 어느 rule의 전제조건과 어떤 의미 보존을 사용하는지 적습니다. 선언적 질의와 extensible optimizer라는 역사적 동기는 [Spark SQL 논문](https://people.csail.mit.edu/matei/papers/2015/sigmod_spark_sql.pdf)에서 읽고, 실제 4.0.4 구현은 [QueryExecution·Analyzer·Optimizer](../source-reading.md)에서 확인합니다.

### 명시적 정답 fixture

```text
left:  (l1, key=1), (l2, key=1), (l3, key=NULL), (l4, key=2)
right: (r1, key=1), (r2, key=1), (r3, key=NULL)
```

일반 동등 조건의 inner join 결과는 `l1-r1`, `l1-r2`, `l2-r1`, `l2-r2`의 **4개 pair**입니다. NULL-safe 동등 조건을 쓰면 `l3-r3`까지 5개가 됩니다. 이 oracle은 `distinct`로 중복을 지우면 틀립니다. 일반 left join은 두 NULL/미매칭 left row가 더해져 6개 pair입니다. NULL-safe left join도 이 fixture에서는 6개지만 NULL row의 매칭 여부가 다르므로 개수만으로 비교하지 않습니다. [공식 NULL 의미](https://spark.apache.org/docs/4.0.4/sql-ref-null-semantics.html).

### 추가 실험

1. 명시적 schema를 사용해 위 fixture를 만들고 SQL과 DataFrame으로 각각 질의합니다. 행을 안정적으로 정렬하거나 multiset으로 비교합니다.
2. 오른쪽 컬럼을 제한하는 predicate를 left join의 ON 내부와 WHERE에 각각 둡니다. NULL을 거부하는 WHERE가 결과를 바꾸는 반례를 손으로 계산합니다.
3. `explain("extended")`와 `explain("cost")`를 수집하고 column pruning·predicate 이동의 전제조건을 찾습니다. 추정치와 실측 row 수를 혼동하지 않습니다.
4. `CAST('bad' AS INT)`와 `try_cast`를 비교합니다. ANSI true/false에서 오류·NULL·성공을 구별하고 각 실행에 설정을 명시합니다. 4.0.4의 ANSI 기본값에 의존하는 코드를 만들지 않습니다. [ANSI 문서](https://spark.apache.org/docs/4.0.4/sql-ref-ansi-compliance.html).
5. NULL·빈 입력·정수 overflow·소수 precision·UTC 이외 timezone을 별도 test case로 추가합니다. 예외를 모두 NULL로 바꾸어 pass시키는 처리는 금지합니다.

### 최소 통과

4/5/6개 pair의 내용까지 맞고 SQL·DataFrame 간 결과가 같습니다. semantic 변화를 plan 개선으로 포장하지 않아야 합니다. 분석 오류·runtime 오류·빈 결과를 서로 다른 실패로 기록하고 실제 source에서 관련 rule 하나를 찾아 전제조건을 적습니다.

<a id="sp04"></a>
## SP04 — codegen, JVM/Python, Arrow는 서로 다른 경계다

### 원리

whole-stage code generation은 연결 가능한 물리 연산자들을 코드 경로로 묶는 최적화입니다. 모든 연산자·모든 Python 코드가 한 generated function으로 들어간다고 가정하지 않습니다. Python scalar UDF, Arrow-optimized scalar UDF, pandas UDF는 전송·batch·타입 변환·실행 계약이 다릅니다. Arrow 사용만으로 사용자 함수가 자동 벡터화되지는 않습니다. 공식 진입점은 [PySpark Arrow 안내](https://spark.apache.org/docs/4.0.4/sql-pyspark-pandas-with-arrow.html)이며 버전별 연결된 Python 문서의 지원 타입을 확인합니다.

설명용 비용식을 세웁니다.

```text
T ≈ 데이터 읽기 + 직렬화/변환 + 언어 경계 횟수×고정 비용 + 실제 계산 + 대기
```

항목들은 실제로 겹쳐 실행될 수 있습니다. 따라서 이 합은 profiling 없이 실측 기여도를 더한 값이 아니라 경쟁 가설을 만들기 위한 모형입니다.

### 추가 실험

1. `amount_cents * 2`를 built-in expression, 명시적 return type의 scalar UDF, 설치 가능한 경우 pandas UDF로 만듭니다. 결과를 전부 소비하는 aggregate를 사용합니다. 단순 `count`가 projection 계산을 제거할 가능성을 먼저 확인합니다.
2. 정상·NULL·상한 근처 정수·빈 partition fixture에서 결과 또는 의도된 오류가 동일한지 비교합니다. Python의 큰 정수와 Spark Long의 범위가 같다고 가정하지 않습니다.
3. `explain("codegen")` 또는 formatted plan에서 Python evaluation과 codegen 경계를 찾습니다. UDF가 있는데 관측되지 않는다면 optimizer가 결과를 사용하지 않아 제거했는지 조사합니다.
4. record batch 크기를 한 번에 하나씩 바꾸며 처리량과 peak RSS/heap을 기록합니다. 가장 큰 batch가 항상 빠르거나 안전하다는 가설을 반박합니다.
5. driver `toPandas`로 모든 데이터를 모으는 것과 executor에서 pandas UDF를 처리하는 것을 구분합니다. 작은 합성 입력만으로 driver conversion 의미를 확인하고 실제 OOM을 유발하도록 데이터를 무한 증가시키지 않습니다.

### 소스와 통과

[WholeStageCodegenExec·ArrowEvalPythonExec](../source-reading.md)의 입력 형식·batch 생성·결과 형식 경계를 읽습니다. 설치되지 않은 Arrow/pandas 확장은 건너뛴 사실을 명시하고 실행 통과로 세지 않습니다. 최소 통과는 built-in과 UDF의 정상/NULL/오류 동등성, 실행 계획의 경계, 조건별 비용 가설, 추가 의존성 version manifest입니다.
