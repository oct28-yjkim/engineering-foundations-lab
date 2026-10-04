# 03. Exact 정답, ANN 인덱스, 메모리 비용

[과정](../curriculum.md) · [기능 지도](../feature-map.md) · [소스·논문](../source-reading.md)

<a id="qd05"></a>
## QD05 — HNSW의 성능 이전에 비교할 정답을 만든다

목적은 제한된 시간에 가까운 후보를 찾는 것입니다. dense HNSW와 payload index는 역할이 다르며 필터 선택도·segment 크기에 따라 실행 전략이 달라집니다. `exact=true` 비교가 가능한 같은 corpus/distance/filter를 고정합니다. [공식 indexing](https://qdrant.tech/documentation/manage-data/indexing/)을 읽고 구성 값, 실제 인덱스 상태, 실행 결과를 나눕니다.

기본 LAB의 작은 fixture는 exact 정답·payload index 요청을 제공합니다. **HNSW 구축·탐색 경로 사용을 강제하거나 ANN 성능을 측정하는 fixture가 아닙니다.** 아래는 별도 bounded ANN 환경에서 수행합니다.

1. corpus/query/필터 정답을 고정하고 holdout query를 제외한 데이터로 설정을 선택합니다. zero vector·동률·중복을 별도 slice로 둡니다.
2. exact top-k와 ANN top-k의 ID 교집합으로 recall을 계산합니다. 동률 boundary는 허용 집합 또는 명시 tie 정책으로 평가합니다. 사람의 relevance judgment는 다른 파일로 둡니다.
3. `hnsw_ef` 하나만 바꾸고 같은 index에서 비교합니다. `m`/`ef_construct` 변경 실험은 build 비용·재구축 상태까지 별도 기록합니다.
4. 필터 선택도별로 index 유무·정답·latency를 비교합니다. 빈 결과를 candidate budget 문제로 판단하기 전에 정확한 filter truth set을 확인합니다.
5. 정답 1개가 후보에서 누락된 query를 재현해 후보 수 확대/필터 수정/모델 변경 중 무엇이 원인에 맞는지 분리합니다.

관측: index/segment 완료 증거, query별 recall, client p50/p95/p99와 표본 수, 오류/timeout, build 시간·RSS/I/O. p99 몇 개 값만으로 확신하지 않습니다. `exact`가 금지된 strict-mode 환경에서는 허가된 별도 evaluation collection에서 정답을 생성합니다.

제출: index가 실제 쓰였는지의 증거/추론 구분, 최소 세 선택도 slice, 한 성능·한 정확성 반례, exact 유지/ANN 채택 결정. ACORN 등 추가 탐색 옵션은 고정 API의 지원과 workload를 조사하는 확장으로 남깁니다.

<a id="qd06"></a>
## QD06 — 압축과 on-disk는 공짜 메모리가 아니다

목적은 품질과 응답시간 요구 안에서 저장·메모리 비용을 줄이는 것입니다. quantized 표현, 원본 datatype, 원본 재점수, oversampling, 메모리 배치는 서로 다른 선택입니다. [공식 quantization](https://qdrant.tech/documentation/manage-data/quantization/)과 [memory tiers](https://qdrant.tech/documentation/ops-configuration/memory-tiers/)를 확인합니다.

1.19.1 고정 API에는 scalar/product/binary/turbo quantization과 float32/float16/uint8/turbo4 datatype이 존재합니다. 이름이 비슷해도 같은 단계의 압축이 아닙니다. legacy `on_disk`는 deprecated이고 `memory`가 우선합니다. 지원하는 tier는 구성 요소별로 다르며 dense vector의 `pinned`는 지원되지 않습니다. 과거 버전 예제를 무조건 치환하지 말고 [고정 schema](../source-reading.md)를 먼저 읽습니다.

| 비교 축 | 기대 관측 | 반례·채택/비채택 판단 |
| --- | --- | --- |
| 원본 vs 압축 검색 | 같은 exact oracle 대비 recall·score/rank 차이 | 작은 평균 오차가 top-k boundary 순위를 바꿀 수 있음 |
| rescore off/on | 품질 회복과 원본 읽기 I/O/latency | 빠른 후보 단계만 측정해 전체 비용을 숨기지 않음 |
| 후보 oversampling | 누락 감소와 비용 증가 | prefetch에서 빠진 point를 후단 계산이 복구하지 못함 |
| cached/cold 등 배치 | cold/warm latency·RSS·page fault·I/O | on-disk는 RAM 0이 아니고 page cache가 결과를 바꿈 |
| index/원본/압축의 동시 보관 | peak memory·디스크·build 시간 | 원본 vector bytes만으로 노드 크기를 계산하지 않음 |

모든 비교는 추가 fixture·자원 상한이 필요한 **E/R 과제**입니다. 기본 runner의 짧은 응답을 압축의 효과로 주장하지 않습니다. 손계산 `N×dimension×bytes`는 원본 배열의 하한 참고일 뿐 payload/index/allocator/replica 비용을 포함하지 않습니다.

제출: 품질·지연·peak memory의 세 축 비교, cold/warm 순서와 반복 수, 실패한 설정 1개, 선택하지 않은 압축 방식의 이유. 원본 정밀도를 되찾을 수 없는 변경은 재생성 source와 rollback 계획부터 준비합니다.
