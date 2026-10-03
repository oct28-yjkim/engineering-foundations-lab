# 04. 최적화·통계·실행 — 빠른 계획보다 먼저 같은 결과를 확인한다

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

범위는 LOCAL-ENGINE / LOCAL-SESSIONS이며 계측기는 실제 MySQL입니다. CPU `index-lookup`의 비교 횟수는 서버 cost model이나 latency 예측값이 아닙니다. `EXPLAIN ANALYZE`는 실제 실행이므로 개인 fixture의 bounded SELECT에만 사용하고 반환 결과와 별도로 기록합니다.

<a id="my07"></a>
## MY07 · cardinality·cost·통계·분포 변화

### 원리

optimizer는 후보 경로의 비용을 비교하되 추정 row 수·통계·비용 계수와 지원되는 변환에 의존합니다. 계획이 바뀌었음을 관찰하는 것과 개선 원인을 입증하는 것은 다릅니다. persistent index statistics, column histogram, index dive, 실제 correlation을 분리합니다. 단일 컬럼 histogram만으로 모든 다중 컬럼 상관관계가 해결되지는 않습니다. [Optimizer statistics](https://dev.mysql.com/doc/refman/8.4/en/optimizer-statistics.html), [InnoDB 통계](https://dev.mysql.com/doc/refman/8.4/en/innodb-persistent-stats.html).

추정 cardinality 오차가 하위 iterator의 반복 횟수, join 순서, materialization·sort 비용으로 전파될 수 있습니다. `rows`·`filtered`·`cost`·실제 rows/loops의 의미를 포맷별로 구분하며 estimated cost를 밀리초로 읽지 않습니다. [EXPLAIN](https://dev.mysql.com/doc/refman/8.4/en/explain.html).

### 재현 fixture 설계

다음 스키마의 새 table에 **상한 10,000행**을 결정적으로 생성하는 별도 로컬 생성기를 만듭니다. `id=1..10000`, `tenant_id=1`이 9,000행이고 나머지는 2..11에 균등 분포하도록 합니다. `state`는 tenant와 강하게 상관된 버전과 독립적인 버전을 각각 만듭니다. 생성 seed/수식과 그룹별 실제 count를 저장합니다. 실행 성능 수치는 여기서 미리 정하지 않습니다.

```sql
CREATE TABLE my07_orders_run01 (
  id BIGINT PRIMARY KEY,
  tenant_id INT NOT NULL,
  state VARCHAR(16) NOT NULL,
  created_at DATETIME NOT NULL,
  total DECIMAL(12,2) NOT NULL,
  KEY ix_tenant (tenant_id),
  KEY ix_created (created_at)
) ENGINE=InnoDB;

SELECT tenant_id,state,COUNT(*) FROM my07_orders_run01
GROUP BY tenant_id,state ORDER BY tenant_id,state;
EXPLAIN FORMAT=TREE
SELECT id,total FROM my07_orders_run01
WHERE tenant_id=1 AND state='open' ORDER BY created_at,id LIMIT 20;
```

위 SQL은 스키마와 진단 예시이며 데이터 생성 완료를 대신하지 않습니다. 비어 있는 테이블의 계획을 skew 실험 결과로 제출하지 않습니다.

### 실험·반증

1. 빈도가 높은 tenant와 낮은 tenant 각각에서 결과 ID·값·순서를 검산합니다. `EXPLAIN FORMAT=TREE`와 bounded `EXPLAIN ANALYZE`의 추정/실측 rows·loops를 맞춥니다.
2. 자신이 만든 table에서 `ANALYZE TABLE my07_orders_run01;` 전후를 비교합니다. 통계 갱신은 부하와 계획 변화를 만들 수 있으므로 공유 table에서 수행하지 않습니다.
3. column histogram을 쓰는 별도 실험에서는 대상 컬럼, bucket 수, 전후 통계와 plan을 저장합니다. histogram이 실제 그 조건의 추정에 사용됐는지 optimizer trace와 대조합니다.
4. 같은 전체 row 수·단일 컬럼 빈도를 유지하면서 컬럼 간 correlation만 바꿉니다. 추정 오차의 원인이 단순 표본 부족인지 표현할 수 없는 상관관계인지 경쟁 가설을 세웁니다.
5. 데이터 분포를 바꾼 뒤 예전 계획/힌트가 유지되는 대조군을 비교합니다. 튜닝 데이터에만 유리한 hint를 일반 처방으로 배포하지 않습니다.

**통과:** 분포 원장, query별 exact oracle, 추정/실측 오차가 처음 커지는 지점, 두 개 이상의 경쟁 가설을 제출합니다. 계획 문자열 변화나 통계 갱신 성공만으로 성능 개선을 주장하면 미통과입니다.

<a id="my08"></a>
## MY08 · iterator·join·sort·복합 인덱스·쓰기 비용

### 원리

실행기는 iterator의 반복·조건 평가·join·sort·materialization·engine row 접근을 조합합니다. nested loop와 hash join의 선택 및 지원 조건은 실제 버전의 계획에서 확인합니다. `filesort`라는 이름만으로 디스크 사용을 확정하지 않고 임시 table·sort spill·메모리 경계를 실제 관측과 연결합니다. [Hash join](https://dev.mysql.com/doc/refman/8.4/en/hash-joins.html), [ORDER BY 최적화](https://dev.mysql.com/doc/refman/8.4/en/order-by-optimization.html).

복합 인덱스는 필터·정렬·covering 목적과 write amplification·공간·cache footprint·잠금 변화 사이의 trade-off입니다. index condition pushdown과 covering은 다른 개념이며, `Using index`·`Using index condition`을 같은 의미로 읽지 않습니다. [ICP](https://dev.mysql.com/doc/refman/8.4/en/index-condition-pushdown-optimization.html).

### 실험 설계

1. MY07의 동일 fixture를 복제한 새 실험 table에서 `(tenant_id,state,created_at,id)` 후보를 만듭니다. 기존 index와 비교하며 결과/순서가 같은지 먼저 검사합니다. 큰 PK와 중복 저장 비용도 고려합니다.
2. 정확한 PK tie-breaker를 가진 keyset pagination과 큰 OFFSET을 비교합니다. 동시 삽입/삭제가 있는 경우 페이지 간 누락·중복과 snapshot 계약을 따로 정의합니다. latency만으로 API 의미가 같은 것으로 간주하지 않습니다.
3. join 양쪽에 중복 키·NULL·매칭 없는 행을 넣고 inner/outer join의 exact 결과를 손으로 만듭니다. join 알고리즘을 바꿔도 결과 multiplicity가 유지되는지 확인합니다.
4. 동일 결과의 selective/unselective workload, warm/cold, concurrency 1/작은 고정값을 나눕니다. A/B 실행 순서를 섞고 query latency·rows examined·오류율·쓰기 지연을 함께 측정합니다.
5. 임시 공간/메모리 pressure 실험은 데이터·시간·메모리 상한과 중단 조건을 정합니다. global buffer를 무작정 키우거나 서버 전체 cache를 강제로 비우지 않습니다.
6. index를 invisible로 평가하는 경우에도 index maintenance 비용은 남을 수 있음을 확인합니다. read plan 평가와 write cost 제거를 혼동하지 않습니다. [Invisible indexes](https://dev.mysql.com/doc/refman/8.4/en/invisible-indexes.html).

### 구현 추적과 구술

한 query에 대해 optimizer의 access path 후보, 선택된 iterator, handler 호출, InnoDB index 접근을 연결합니다. [소스 지도](../source-reading.md)의 고정 revision에서 실행된 계획이 어느 경로에 대응하는지 찾고, 최신 development branch 코드를 읽었다면 런타임과의 차이를 표시합니다.

**통과:** 같은 결과 계약의 baseline/개선/악화 workload, 공간·쓰기 비용, 반복 측정과 불확실성, plan→실행 경로가 필요합니다. 10,000행 실험을 production p99나 대용량 처리량으로 외삽하면 미통과입니다.
