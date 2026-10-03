# 실험 방법: 속도와 정확성의 근거 만들기

실험의 단위는 “설정 변경”이 아니라 **반증 가능한 주장**입니다. 예를 들어 “정렬 키를 바꾸면 빠르다” 대신 “이 국가·기간 필터에서 primary index가 선택하는 marks와 읽은 바이트가 줄고, 동일 결과의 latency 분포가 개선된다”라고 적습니다.

## 실험 계약

| 항목 | 기록할 것 |
| --- | --- |
| 입력 | generator 버전, row count, key cardinality, skew, 시간 범위, NULL/중복 비율 |
| 환경 | DB 정확 버전·image digest·source commit, OS·CPU·RAM·디스크, 컨테이너 제한 |
| 설정 | 기본값 포함 실험 관련 settings, query cache, parallelism, background 작업 |
| 기준 | 기존 쿼리/모델, 정확성 oracle, 기대하는 불변식 |
| 변경 | 한 번에 바꿀 변수, 다른 변수를 유지한 방법 |
| 관측 | client 시간과 server 시간 구분, throughput, latency 분포, I/O·CPU·메모리 |
| 반례 | 개선되지 않거나 손해인 workload, 실패 상태 |
| 재현 | 실행 순서·원본 로그·결과 검증·정리·미검증 항목 |

버전이 바뀌면 이전 결과를 복사하지 않습니다. source 파일의 줄 번호보다 commit과 symbol을 기록하면 추적하기 쉽습니다.

## 정확성부터 검증

작은 입력은 손계산, 큰 입력은 단순하지만 독립적인 reference query로 검증합니다. 개선 쿼리와 같은 알고리즘을 복사한 검증기는 같은 오류를 공유할 수 있습니다.

- count뿐 아니라 고유 ID 집합, 금액 합, 날짜·상태별 집계, NULL/삭제 상태를 대조합니다.
- 전체 합이 같은 두 오류가 상쇄될 수 있으므로 차원별 차이와 mismatch row를 출력합니다.
- exact distinct와 approximate distinct는 같은 pass 조건을 사용하지 않습니다. exact oracle 대비 오차를 분포별로 측정하고 허용 기준을 먼저 정합니다.
- `ORDER BY`가 없을 때 반환 순서는 검증 계약에 포함하지 않습니다. 동률 선택은 명시적인 tie-breaker를 둡니다.
- 부동소수점의 결합 순서 차이와 Decimal의 반올림/scale 차이를 명시합니다.

## 성능 측정 순서

1. 기준/변경 양쪽의 결과를 비교합니다.
2. 설정과 background merge/vacuum 유무를 기록합니다.
3. warm-up과 측정을 나누고 A/B 실행 순서를 교차합니다.
4. 반복 결과 전체를 저장합니다. 평균 한 개만 남기지 않습니다.
5. plan의 row estimate·actual rows/loops, DB별 read work, CPU·memory·temp I/O를 해석합니다.
6. 입력 크기와 skew를 바꾸어 같은 설명이 유지되는지 확인합니다.
7. throughput·쓰기 비용·디스크·maintenance 비용을 함께 평가합니다.

실습에서는 20회 반복으로 시작하되 tail latency SLO 검증에는 충분한 요청 수와 지속 시간을 별도 설계합니다. bootstrap 등의 신뢰구간도 표본 대표성과 독립성이 없으면 의미가 약해집니다. “10배 빨라짐”은 특정 환경의 결과로 표기하며 일반적인 제품 성능 비율로 쓰지 않습니다.

## 캐시와 도구의 함정

PostgreSQL shared buffers, OS page cache, storage cache는 다른 계층입니다. 컨테이너 restart만으로 cold disk가 보장되지 않습니다. ClickHouse도 query result cache, filesystem/page cache, mark cache 등 서로 다른 효과가 있습니다. cache를 지웠다는 명령보다 어떤 계층이 통제됐는지 적습니다.

`EXPLAIN ANALYZE`는 쿼리를 실행하며 자체 계측 비용도 더합니다. plan 비용은 시간 단위가 아닙니다. 부모/자식 node의 누적 시간·buffers를 무작정 합하지 않습니다. 자세한 계측 해석은 [PostgreSQL 공식 EXPLAIN 설명](https://www.postgresql.org/docs/18/using-explain.html)을 따릅니다.

ClickHouse의 query log는 비동기 기록이므로 직후 조회에서 빠질 수 있습니다. 집계 단위와 분산 쿼리의 initiator/child 관계를 확인하고 query id로 묶습니다. [query_log 문서](https://clickhouse.com/docs/operations/system-tables/query_log)

## 장애 실험의 증거

장애 주입은 별도로 구성한 폐기 가능한 환경에서 수행합니다. 평상시 데이터, 예정된 주입 시점, 중단 조건, 복구 절차를 실험 전에 정의합니다. 단일 노드 입문 Compose에 분산 장애 검증이 포함됐다고 보고하지 않습니다.

client가 보낸 request ID, server 응답, 최종 저장 상태를 시간순 이력으로 남깁니다. 응답을 받지 못한 요청은 곧바로 실패로 분류하지 않고 저장 상태를 확인합니다. clock skew가 있으면 wall-clock만으로 인과관계를 확정하지 않습니다. 복구는 “프로세스 healthy”와 “업무 불변식 회복”을 따로 측정합니다.

## source trace의 최소 형식

```text
release / commit:
질문: 어떤 조건에서 이 경로를 타는가?
SQL / 입력 → 진입 함수 → 핵심 자료구조 → 상태 변경 → 관측 지표
잠금/소유권/수명:
가설을 지지하는 실험:
경로를 타지 않는 반례:
읽은 범위와 아직 확인하지 않은 범위:
```

파일을 많이 읽는 것보다 작은 현상 하나를 끝까지 추적합니다. 두 트랙의 `source-reading.md`를 출발점으로 사용하고, 코드는 실제 사용 버전으로 다시 확인합니다.

## 재제출 기준

아래 중 하나라도 해당하면 결론을 보류합니다: 결과 불일치, baseline 누락, 정확 버전 누락, 실행하지 않은 계획을 실측처럼 표기, source 추정을 확정 사실로 기재, 복구가 필요한 과제에서 restore 미수행. 미수행 항목을 솔직하게 남기는 것은 다음 실험의 출발점입니다.
