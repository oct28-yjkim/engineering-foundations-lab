# OpenSearch 관측 LAB — 정상 쿼리에서 비용 원인까지

[실습 순서](README.md) · [단계형 사건](incidents.md) · [운영 지표 사전](../operations.md) · [코드](observe_lab.py)

정상 검색이 무엇인지 먼저 확인한 뒤 **같은 정답을 만드는 두 query 경로의 비용과 관측 방법**을 익힙니다. CPU 알고리즘 모형이 아니라 실제 OpenSearch REST 호출입니다. 느려지는 이유를 조사하는 입문 관측 실습이며, 포화·OOM·429·서비스 장애를 반드시 발생시키는 부하 시험은 아닙니다.

## 1. 정상 기능·원리·예측

[단일 노드 준비](README.md)를 마치고 `engine_lab.py --run-local`의 문서 정답과 검색 의미를 먼저 확인합니다. 관측 runner는 별도 신규 `efl-os-observe-<UUID>` index를 사용합니다. 문서 `n=0..N-1`의 정답은 `doc_id=d000000` 형식, `group_no=n%10`, `value=3n`입니다.

두 query 모두 `group_no=3`인 문서만 반환합니다. `script`는 Painless 조건을 평가하고, `indexed`는 integer 필드의 term 조건을 이용합니다. 같은 결과가 필수이며 단순히 빠른 응답만 통과시키지 않습니다. 스크립트가 더 비쌀 것이라는 **가설**을 먼저 쓰되 작은 데이터에서 유의한 차이가 안 날 수도 있습니다. 실제 수치를 미리 적어 놓지 않습니다. [공식 Script query](https://docs.opensearch.org/latest/query-dsl/specialized/script/)

## 2. 계획 확인 → 선택 실행

저장소 루트에서 Python 3.10 이상 표준 라이브러리로 실행합니다. 기본/`--plan`/`--help`는 서버에 연결하지 않습니다.

```text
python -B search/opensearch/labs/observe_lab.py --plan
python -B search/opensearch/labs/observe_lab.py --run-local --documents 2000 --samples 20
```

실행은 고정 loopback `127.0.0.1:19200`과 기존 3.9.0/cluster/node 식별을 확인한 뒤 신규 index 하나만 만듭니다. 기존 index 선택·삭제·원격 URL·global 설정 변경은 지원하지 않습니다. proxy/redirect도 사용하지 않습니다. 결과는 JSON stdout이며 자동 파일 저장은 없습니다. 필요한 경우 정제 후 자신의 실행 원장에 보관합니다.

상한은 문서 **100~10,000**, variant별 표본 **10~100**, 동시성 **1**, 전체 요청 **300회**, 요청 body **1MiB**, 응답 **5MiB**입니다. 기본값은 2,000문서/variant별 20회입니다. 120초 경과 시 **다음 요청을 시작하지 않는 예산 검사**, socket 작업 timeout 10초, search timeout 5초를 사용합니다. 실행 중 요청을 강제로 끊는 전역 wall-clock deadline 보장은 아닙니다. 요청 오류/partial/timed-out/정답 불일치에서는 첫 실패로 중단하며 남은 index를 자동 삭제하지 않습니다.

## 3. 어떻게 모니터링하는가

runner는 bulk item 성공 → explicit refresh → 두 query의 정확한 ID·값 → 각 2회 warmup → 시작 stats → 순서를 고정 seed로 섞은 직렬 요청 → 종료 stats → 별도 Profile/정답 재검산 순서로 실행합니다. 측정 중에는 `size=0`으로 count와 실패 여부를 검증하고, 측정 전후에는 모든 일치 문서의 ID/값을 검산합니다. Profile 호출은 timed sample에 포함하지 않습니다.

| 출력/수집 위치 | 읽는 방법 | 해석 제한 |
| --- | --- | --- |
| `samples`, `summary` | client ms와 서버 `took` ms; variant별 p50/p95·count | nearest-rank 표본 요약; 기본 20개 p95는 설명용이지 p99/SLO/통계적 개선 증명이 아님 |
| `before/after.gauges` / Nodes Stats | heap %, process CPU %, fs 가용 byte, search active/queue, write queue | 두 시점의 값뿐; 0이어도 중간 peak가 없었다고 결론 내리지 않음 |
| `counter_changes` / Nodes Stats | young/old GC count·ms, search/write rejected, merge count·ms | node ID/uptime 변화·counter 감소 시 reset 표기; 누락은 null, 0으로 대체하지 않음 |
| `owned_index.*` / Index Stats | 해당 신규 index search/indexing/merge/refresh 누적 count·ms 차이 | node 전체 counter와 다른 범위; 총 query time을 client latency로 사용하지 않음 |
| `profile` | query type·`time_in_nanos`로 비용 경로 확인 | profiler overhead가 있고 network·queue 등 전체 지연을 포함하지 않음 |
| `status`, `stage`, `http_status` | `MEASURED`는 완료된 비교, `ERROR`는 중단 지점 | 성공 출력의 `observed_errors=0`은 이 직렬 비교에서의 값; 부하 중 오류율 시험이 아님 |

수집 API: [Nodes Stats](https://docs.opensearch.org/latest/api-reference/nodes-apis/nodes-stats/), [Index Stats](https://docs.opensearch.org/latest/api-reference/index-apis/stats/), [Profile](https://docs.opensearch.org/latest/api-reference/search-apis/profile/). 노드 counter에는 다른 활동이 섞일 수 있습니다. 상세 API 응답·지속 시계열은 [운영 runbook](../operations.md)의 별도 수집을 병행하고 학습 index 외의 민감 이름/내용을 공유하지 않습니다.

두 번의 node ID/uptime 비교는 탐지 가능한 reset을 거르는 장치일 뿐 모든 재시작을 확정 배제하지 못합니다. index counter도 index 수명·수집 범위와 함께 해석하며 재시작/재생성 로그가 있으면 그 관측 구간을 별도로 표시합니다.

## 4. 진단 연습과 제약

1. **정답은 같은가?** 기대 match 수는 `len(range(3,N,10))`입니다. 기본 N=2000이면 200개입니다. 두 query의 ID·group_no·value가 같아야 합니다.
2. **쿼리 비용인가, 환경인가?** script/indexed의 client·took·Profile을 비교하고 heap/GC·queue·merge 관측을 연결합니다. 지연 차이 하나만으로 CPU 병목을 확정하지 않습니다.
3. **cache가 설명하는가?** request cache는 끄지만 query cache/OS page cache는 남습니다. warmup 이후의 비교이며 cold-start 결과로 부르지 않습니다. 새 run은 새 index를 만들어 저장량이 늘어납니다.
4. **오류가 났다면?** 연결/identity/입력/partial/timeout을 먼저 분류합니다. script query가 expensive-query 정책으로 거부되면 실제 설정과 공식 문서를 조사하고 중단합니다. runner는 정책을 임의로 켜거나 retry로 숨기지 않습니다.
5. **조치 후보를 검증했는가?** 같은 조건을 indexed query로 표현할 수 있는 경우에만 결과 동등성과 관측 차이를 비교합니다. 모든 script를 term으로 바꿀 수 있다는 뜻은 아닙니다.

결과에 `slowdown_conclusion=unconfirmed_repeat_with_controlled_workload`, `pressure_incident=not_reproduced_by_design`을 남깁니다. 음수/작은 지연 차이나 rejection 증가 없음도 정상적인 관측 결과입니다. 지연 회복을 확정하려면 동일 workload·관측 창의 반복과 경쟁 설명 배제가 더 필요합니다. 같은 호스트의 3→4노드도 capacity/SLO 보장이 아니라 [배치·복제 실습](scaling-incidents.md)입니다.

## 5. 제출물과 실제 검증 상태

예측한 query 경로, 실제 정답, 수집한 지표의 의미/단위, 측정 원장, 채택/기각/불명인 경쟁 가설, 제약, 다음 조사 항목을 남깁니다. 이 LAB의 완료는 **관측·해석 학습 완료**이며 장애 복구 완료를 대신하지 않습니다. 실제 단계형 오류·복구는 [사건 LAB](incidents.md)에서 진행합니다.

2026-10-04 작성 시 실제 Docker 엔진이 준비되지 않아 실제 쿼리 실행·성능 수치를 검증하지 않았습니다. mock 테스트는 요청/정답/예산/보고 계약만 확인합니다. [검증 기록](incident-validation.md)을 함께 읽습니다.
