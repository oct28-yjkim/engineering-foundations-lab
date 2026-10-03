# 05. 성능과 비용: 빨라진 이유를 분리하고 총비용을 검산한다

[커리큘럼](../curriculum.md) · [논문/소스](../source-reading.md)

<a id="d09"></a>
## D09 — Photon·AQE·파일 배치의 통제 실험

query latency는 planning, queue/startup, scan, shuffle, compute, spill, output transfer가 합쳐진 값입니다. Photon은 native vectorized 실행을 제공하지만 모든 operator를 Photon으로 실행한다고 보장하지 않습니다. query profile의 실제 operator/fallback 증거와 정답을 함께 봅니다. 공개 Photon 논문은 설계 근거이지 실행 binary의 소스 코드가 아니며, 로컬 Spark 성능을 Photon 성능이라고 부르지 않습니다. [Photon](https://docs.databricks.com/aws/en/compute/photon)

**CPU/LOCAL-SPARK 기본:** [Spark 실습](../../../data-processing/spark/labs/README.md)의 CPU hash-partition 모델로 key skew를 이해하고, 선택 Spark runner의6행 batch로 NULL·duplicate·aggregation 정답을 확인합니다. 제공 runner는 실제 task skew 성능 benchmark가 아닙니다. task partition·shuffle·skew의 실측 비교는 더 큰 synthetic fixture와 metrics 수집을 학습자가 추가 구현하는 과제입니다. 작은 CPU 모델의 처리량이나1회 wall time을 production node 수 산정에 사용하지 않습니다.

**MANAGED-OPTIONAL 실험 설계:** 동일한 synthetic 데이터와 정답, 지정한 compute budget 아래에서 아래 비교를 한 번에 하나씩 수행합니다. 환경에서 Photon off가 지원되지 않으면 조작했다고 쓰지 말고 해당 비교를 미실행으로 둡니다.

| 비교 | 고정할 조건 | 관측할 설명 변수 |
| --- | --- | --- |
| Photon on/off | 같은 지원 runtime·hardware·query·data·cache regime | native/fallback 구간, operator time, 전체 비용 |
| AQE 설정 | 같은 source·join·통계·parallelism | initial/final plan, partition size, join 전환 |
| small/large files | 같은 row set·schema·compression·query | 파일 수·scan bytes·scheduling overhead |
| layout A/B | 독립 복제 fixture, 동일 selectivity | pruning·file stats·write amplification·유지 비용 |
| cold/warm | cache 정책·반복 순서·client | I/O/cache hit, warmup 제외 범위 |

한 가지 레이아웃을 모든 table에 적용하지 않습니다. partitioning, Z-order, liquid clustering의 적용 조건·상호 제약·reader feature를 확인하고 선택합니다. 자동 최적화가 켜져 있다면 실험 사이에 layout이 바뀌는 교란 변수입니다. 관리형 background maintenance 비용과 history도 기록합니다. [liquid clustering](https://docs.databricks.com/aws/en/tables/clustering)

**측정 방법:** warmup 뒤 동일 workload 최소20개 측정 반복/구간, 가능하면 A/B 순서를 교차·무작위화합니다. median/p95와 분산, raw sample, 실패/timeout 수, source/result checksum을 제출합니다. p99는 충분한 표본 수가 별도로 필요합니다. 결과 cache로 query 실행 자체가 생략됐는지 확인합니다. 작은 결과를 client로 수집하는 시간과 query execution time을 분리합니다.

**반증:** Python UDF 추가, hot key 비율 변화, selectivity 변화 중 하나로 “항상 n배 빠르다” 가설을 깨뜨립니다. unsupported operator로 fallback이 예상되지만 profile에서 그렇지 않으면 실제 버전 지원을 다시 조사합니다. feature 문서의 marketing benchmark 숫자를 이 workload의 실측으로 옮기지 않습니다.

**gate:** 정답 일치가 속도보다 먼저입니다. bytes/plan/operator 변화와 latency 변화가 연결되지 않으면 원인을 미확정으로 남깁니다. 예산 초과 직전까지 반복하지 말고 사전 stop threshold를 둡니다.

<a id="d10"></a>
## D10 — DBU가 아니라 성공한 업무 단위당 비용

DBU 사용량, list-price 계산값, 계약 할인 반영 청구액, cloud VM/storage/network/egress, 실패·idle·retry 비용은 서로 다른 값입니다. serverless와 classic의 청구 구성도 cloud/상품에 따라 달라지므로 같은 항목을 두 번 더하거나 빠뜨리지 않도록 포함 범위를 씁니다. GPU/API는 선택 확장이고 기본 실습에 필요하지 않습니다.

**CPU 원장 과제:** 제공된 budget 모델은 driver/worker 시간과 attempt를 가상 unit price로 계산하는 작은 모델이며, 실행법은 [실습 안내](../labs/README.md)를 따릅니다. 아래 billing correction과 price 유효기간 join은 **별도 추가 구현 과제**이며 제공 runner가 구현·검증했다는 뜻이 아닙니다. 모두 실가격·요금 예측과 구분합니다.

- usage 기록의 ORIGINAL + RETRACTION + RESTATEMENT를 signed quantity로 합산해 수정 후 사용량을 계산합니다. ORIGINAL만 고르면 오차가 나는 fixture를 만듭니다.
- SKU/cloud/currency/usage unit과 유효기간이 맞는 price를 붙입니다. 가격 경계를 가로지르는 interval은 명시적 분할/정책으로 처리하며 무조건 시작 시점 하나만으로 곱하지 않습니다.
- 누락 price, 중복 join으로 증가한 usage, 음수 correction, 다른 currency를 오류 또는 별도 집계로 분류합니다.
- shared compute는 job별 직접 귀속 가능한 비용과 미할당 비용을 분리합니다. 모든 비용을 임의의 마지막 job에 붙이지 않습니다.

**MANAGED-OPTIONAL 읽기:** `system.billing.usage`와 `system.billing.list_prices`는 권한·제공 상태를 확인한 뒤 필요한 범위만 조회합니다. data freshness와 correction을 고려하고, usage가 아직 나타나지 않는다고 무료 실행이었다고 판단하지 않습니다. system table의 price로 계산한 수치는 계약 청구서와 다를 수 있습니다. [usage schema](https://docs.databricks.com/aws/en/admin/system-tables/billing), [price schema](https://docs.databricks.com/aws/en/admin/system-tables/pricing)

**의사결정 실험:** A는 더 빨리 끝나지만 높은 단가·startup 비용을, B는 더 느리지만 낮은 단가를 갖는 가상 실행을 비교합니다. `총비용 / 검증을 통과한 unique business record`와 deadline 만족 여부를 함께 보고합니다. 실패 결과를 denominator에 포함하지 않습니다. utilization만 높이고 backlog SLO를 위반한 설정을 최적이라고 선택하지 않습니다.

**예산 runbook:** owner, 최대 실행시간, 최대 동시 job, 허용 autoscale 상한, idle termination, 알림·중지 책임, storage/egress 상한을 명시합니다. 예산 alert가 hard spending cap이라고 가정하지 않습니다. 청구 지연 때문에 별도 실행시간/리소스 guard가 필요합니다.

**gate:** CPU model PASS와 실제 bill 검산을 분리하고, price의 기준일·통화·단위·포함 비용을 명시합니다. 1회 query 시간이 줄었다는 이유만으로 월비용 절감을 단정하지 않습니다.
