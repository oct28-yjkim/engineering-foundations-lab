# 선택 원리 부록: 검색 결과가 달라지는 이유의 모형

이 부록은 필수 선행 과정이나 운영 완료 조건이 아니다. 주 실습은 [실제 엔진의 모니터링·트러블슈팅](../operations.md)이며, 수식·반례 이해가 필요할 때만 아래 코드를 선택한다.

[OpenSearch 트랙](../README.md) · [실습 실행 안내](README.md) · [구현](offline_lab.py) · [단위 테스트](test_offline_lab.py)

이 실험은 OpenSearch를 흉내 내는 호환 구현이 아니다. 작은 입력에 대해 정답을 손으로 계산하고, **가정이 바뀌면 어떤 보장이 사라지는지** 확인하는 네 가지 독립 모델이다. Python 3.10 이상과 표준 라이브러리만 사용한다. 실행 코드는 파일 쓰기·네트워크·외부 프로세스·클라우드 인증을 사용하지 않는다. 아래 명령의 `-B`는 Python bytecode 캐시 파일 생성도 방지한다.

```bash
# 저장소 루트
python -B search/opensearch/labs/offline_lab.py --lab all
python -B -m unittest discover -s search/opensearch/labs -p test_offline_lab.py -v
python -B -O -m unittest discover -s search/opensearch/labs -p test_offline_lab.py -v
```

각 실험의 정답 조건은 `assert`가 아니라 명시적인 `ValueError` 검사이므로 `-O`에서도 유지된다. `PASS`는 아래 모델의 계약이 성립했다는 뜻이며, 실제 클러스터·Lucene 점수·ANN recall·보안 정책·성능 검증 결과가 아니다.

| 실험 | 핵심 질문 | 실행 이름 | 정답/반례 |
| --- | --- | --- | --- |
| BM25 | 단어 빈도를 늘리면 점수가 선형 증가하는가? | `bm25` | 포화, 길이 정규화, 문서 빈도 손계산 |
| Refresh | GET에는 보이는데 검색에는 없는 이유는? | `refresh` | realtime 상태와 reader snapshot의 시점 차이 |
| Distributed top-k | 모든 shard의 상위 결과만 합쳐도 되는가? | `distributed-topk` | 문서 top-k 충분조건과 terms 집계 반례 분리 |
| Hybrid filter | 필터가 최종 결과만 바꾸는가? | `hybrid-filter` | 후보 절단 순서가 RRF 입력과 recall을 바꿈 |

## 1. BM25: 공식보다 먼저 통계의 모집단을 고정한다

```bash
python -B search/opensearch/labs/offline_lab.py --lab bm25
```

### 모델 계약

- 문자열을 소문자로 바꾼 뒤 `[a-z0-9]+`만 토큰으로 추출한다. 한국어 형태소 분석기, Unicode 단어 분리기, stemming, stopword, synonym 모델이 아니다. 예를 들어 `검색 café`는 `caf` 하나만 남는다.
- position은 추출한 토큰의 **0부터 시작하는 순서**다. `cat cat dog`의 `cat` position은 `(0, 1)`이다. character offset이나 synonym의 position increment가 아니다.
- `N`은 빈 문서까지 포함한 입력 문서 수, `df(t)`는 `t`가 한 번 이상 나타난 문서 수다. 평균 길이는 모든 문서의 토큰 수 합을 `N`으로 나눈다.
- query의 반복 단어는 한 번만 센다. 문서 score는 query의 서로 다른 단어 기여분의 합이다. score가 0인 문서는 결과에서 제외한다.
- 동점이면 문서 ID 문자열 오름차순을 사용한다. 실제 엔진의 tie-break를 재현하지 않는다.

이 모델이 사용하는 식은 다음과 같다. 로그는 자연로그다.

```text
idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
score(t,d) = idf(t) × tf(t,d) × (k1 + 1)
             / [tf(t,d) + k1 × (1 - b + b × dl(d)/avgdl)]
score(q,d) = 서로 다른 query term의 score(t,d) 합
```

`k1 > 0`, `0 ≤ b ≤ 1`인 유한한 수만 받는다. 이는 이 코드의 입력 계약이다. 실제 Lucene의 parameter 허용 범위나 score 구현과 동일하다고 가정하지 않는다. 빈 corpus·전부 빈 문서·빈 query는 빈 결과다.

### 독립 손계산 정답

corpus는 `a="cat cat dog"`, `b="cat"`, `c="dog mouse"`, query는 `cat`, `k1=1`, `b=1`이다.

| 항목 | 값 |
| --- | --- |
| N / 평균 길이 | 3 / 2 |
| df(cat) / df(dog) / df(mouse) | 2 / 2 / 1 |
| idf(cat) | ln(1.6) |
| score(a) | ln(1.6) × 8/7 |
| score(b) | ln(1.6) × 4/3 |
| 결과 | `b`, `a` |

`b=0`으로 바꾸면 길이 패널티가 사라져 `a`, `b` 순서로 바뀐다. 길이를 4로 맞춘 별도 corpus에서 `tf=1,2,4`, `k1=1`, `b=0`의 기여분 배수는 각각 `1`, `4/3`, `8/5`다. 단어 수 두 배가 점수 두 배를 뜻하지 않는다.

### 실험 과제와 경계

1. `k1`과 `b`를 한 번에 하나씩 바꾸고, 순위 변화와 절대 점수 변화를 분리해 기록한다.
2. 빈 문서 하나를 추가해 모집단/평균 길이가 바뀌는 사례를 손계산한다.
3. 실제 `_analyze`, `_termvectors`, `_explain` 결과와 비교할 때 analyzer, field 통계, query rewrite, boost, norm encoding을 각각 확인한다. 모델 점수와 불일치를 즉시 엔진 오류로 판정하지 않는다.

Lucene의 공식 BM25 문서는 `docCount`, term statistics, length normalization, overlap 처리라는 실제 구현 경계를 확인하는 출발점이다. 여기서는 빈 입력 문서를 모두 `N`에 포함하므로 sparse field의 실제 통계와 다를 수 있다. [Lucene 10.5.1 BM25Similarity API](https://lucene.apache.org/core/10_5_1/core/org/apache/lucene/search/similarities/BM25Similarity.html)

## 2. Refresh: 가시성만 모델링하고 내구성은 추론하지 않는다

```bash
python -B search/opensearch/labs/offline_lab.py --lab refresh
```

`VisibilityState`는 immutable tuple 두 개를 가진다. `realtime`은 최신 write가 반영된 상태, `searchable`은 마지막 명시적 refresh가 복사한 reader snapshot이다. `put`, `delete`, `refresh`는 새 상태를 반환하며 이전 상태를 수정하지 않는다.

| 순서 | 연산 | realtime GET(a) | 검색 snapshot |
| --- | --- | --- | --- |
| 1 | `put(a, "old cat")` | `old cat` | 비어 있음 |
| 2 | refresh | `old cat` | `cat` query에 a |
| 3 | `put(a, "new dog")` | `new dog` | 여전히 `cat`에 a, `dog`에는 없음 |
| 4 | refresh | `new dog` | `dog`에 a |
| 5 | delete(a) | 없음 | 여전히 `dog`에 a |
| 6 | refresh | 없음 | 비어 있음 |

검색은 **서로 다른 query token의 AND**이며 실제 `match` query의 기본 동작이 아니다. 모델의 write/search sequence는 설명용 정수 카운터이지 OpenSearch `_seq_no`, primary term, global checkpoint, 실제 시각이 아니다. 존재하지 않는 ID의 delete도 이 모델에서는 write counter를 증가시킨다.

OpenSearch의 realtime GET과 refresh 후 검색 가시성의 차이가 학습 대상이다. 실제 GET API는 realtime 여부를 선택할 수 있으며, Refresh API는 변경 사항의 검색 가시성을 다룬다. [Get Document API](https://docs.opensearch.org/latest/api-reference/document-apis/get-documents/), [Refresh Index API](https://docs.opensearch.org/latest/api-reference/index-apis/refresh/)

**이 모델에는 ack, translog, fsync, flush, segment merge, replica, process crash, power loss가 없다.** 따라서 “refresh 했으므로 장애 복구 가능”, “검색되었으므로 모든 replica에 durable”, “GET 성공이 전체 트랜잭션 commit” 같은 결론을 낼 수 없다. 자동 refresh 주기나 idle shard도 재현하지 않는다.

과제: 실제 disposable index에서 자동 refresh를 제어한 뒤 단계별 GET/search 결과를 기록한다. 별도 durability 실험을 설계한다면 acknowledgement, 복제 설정, translog durability, 장애 종류와 복구 관측값을 추가하고, 현재 CPU 결과와 다른 증거로 제출한다.

## 3. Distributed top-k: 문서 순위와 bucket 집계는 다른 문제다

```bash
python -B search/opensearch/labs/offline_lab.py --lab distributed-topk
```

### 문서 top-k의 충분조건

모든 문서에 **이미 전역 비교 가능한 고정 점수**가 주어져 있고, 모든 shard와 coordinator가 `(-score, doc_id)`라는 같은 total order를 사용한다고 가정한다. 문서 ID는 shard 사이에서도 유일해야 한다.

각 shard에서 최소 `k`개를 전달하면 전역 top-k는 그 후보들의 합집합 안에 있다. 증명: 어떤 문서가 자기 shard의 top-k 밖이면 같은 shard에 그것보다 앞서는 문서가 최소 k개 존재한다. 따라서 전역 top-k 안일 수 없다. 이 증명은 local BM25 통계와 global BM25 통계가 같다는 주장이 아니다.

- shard 1: `a=100, b=99, c=98`
- shard 2: `d=97, e=96`
- 전역 top-3: `a,b,c`
- 각 shard 후보 3개: `a,b,c`로 정확
- 각 shard 후보 1개: `a,d`만 남아 `b,c`를 복구할 수 없음

여기에는 approximate ANN, timeout/partial failure, `terminate_after`, score rewrite, shard별 IDF, rescore window, PIT, pagination, 중복 ID 합치기가 없다. 이러한 조건을 넣으면 해당 보장을 따로 증명해야 한다.

### Terms aggregation 반례

다음은 문서 순위가 아니라 **shard별 bucket count의 합**이다.

| shard | shared | a | b |
| --- | --- | --- | --- |
| 1 | 9 | 10 | 0 |
| 2 | 9 | 0 | 10 |
| 전역 합 | 18 | 10 | 10 |

각 shard의 상위 bucket 1개만 보내면 `shared`가 양쪽에서 탈락하여 잘못된 top-1 `a=10`이 나온다. 전체 집계 정답은 `shared=18`이다. 최종 winner가 맞아도 특정 shard의 기여분이 잘리면 count 자체가 작아질 수 있으며 테스트에 별도 반례를 포함했다.

실제 `terms` API의 `size`, `shard_size`, count error 추정치를 연결해서 읽는다. CPU 코드는 단순 local truncation 모델이며 실제 기본값, segment slice, error-bound 계산을 구현하지 않는다. [Terms aggregation](https://docs.opensearch.org/latest/aggregations/bucket/terms/)

과제: 후보 예산을 늘리는 것이 문서 top-k와 terms의 정확성에 각각 어떤 영향을 주는지 설명하고, 네트워크/메모리 비용은 실제 엔진 측정 결과가 있을 때만 수치로 제시한다.

## 4. Hybrid filter: 후보에서 잃은 문서는 fusion이 살리지 못한다

```bash
python -B search/opensearch/labs/offline_lab.py --lab hybrid-filter
```

lexical/vector 검색기는 실행하지 않는다. 같은 4개 문서 corpus에 대한 다음 두 **미리 주어진 순위 목록**만 사용한다.

```text
tenant A: a1, a2       tenant B: b1, b2
lexical list: b1, b2, a1, a2
vector list:  b2, b1, a2, a1
각 목록의 후보 예산: 2
```

`tenant=A` 조건을 각 목록에 먼저 적용하고 2개를 고르면 `[a1,a2]`, `[a2,a1]`이다. 먼저 전체 목록 상위 2개를 자른 다음 조건을 적용하면 두 목록 모두 비어 있다. 이는 exhaustive 고정 순위 목록에 대한 비교다. 실제 HNSW/Faiss/Lucene의 filtering 전략이나 ANN recall 보장이 아니다.

RRF 모델은 rank를 1부터 세며, 문서별로 `1/(60+rank)`를 합한다. 어떤 목록에 없는 문서는 그 목록의 기여분이 0이다. 가중치는 없고 동점은 ID 오름차순이다.

- 먼저 필터: `a1`과 `a2` 모두 `1/61 + 1/62 = 123/3782`, 순서는 `a1,a2`.
- 절단 후 필터: 후보도 RRF 결과도 없음.
- 정답 relevant set `{a1,a2}`에 대한 recall@2: 각각 `1.0`, `0.0`.

`recall_at_k`는 relevant set이 비어 있으면 정의하지 않고 오류를 낸다. duplicate ID를 허용하지 않으므로 같은 문서 반복으로 recall을 부풀릴 수 없다. 이 fixture에서만 둘 다 relevant라고 선언한 것이며 tenant 소속이 현실의 relevance label을 대신하지 않는다.

**tenant 후보 필터는 인증·인가 경계가 아니다.** 호출자가 tenant 문자열을 위조할 수 있는지, 다른 API/직접 index 접근으로 우회할 수 있는지, 정책이 모든 검색 경로에 적용되는지는 여기서 시험하지 않는다. 실제 보안 검증에서는 서로 다른 principal과 positive/negative control을 사용하고 DLS/FLS 등 정책 경계를 별도 확인해야 한다.

OpenSearch의 score ranker processor는 RRF를 적용하는 실제 search pipeline 구성 요소다. 이 모델의 `rank_constant`는 수학 실험용으로 유한한 `c ≥ 0`을 허용하므로 **실제 API parameter validator와 동일하지 않다**. 특정 버전의 유효 범위, weights, 실행 위치는 공식 문서와 실제 응답으로 확인한다. [Score ranker processor](https://docs.opensearch.org/latest/search-plugins/search-pipelines/score-ranker-processor/)

과제: 두 검색 목록을 만드는 방법, prefilter의 정의, 후보 예산, label 출처를 고정한 뒤 relevance와 latency를 함께 측정한다. 목록 결합 실험만으로 embedding 모델 또는 ANN 검색기의 우열을 주장하지 않는다.

## 제출 및 검증 기록

2026-10-04 기준 CPython 3.12.14에서 4개 CLI 실험과 `test_offline_lab.py`의 **96개 테스트를 일반/`-O` 모드에서 검증**했다. 테스트는 손계산 score, ID tie, 빈 입력, finite parameter, mutation 금지, visibility 시점, 다중 shard 분할 충분조건, bucket count 누락, 중복 ranking 거부, RRF/recall 정답을 확인한다. 실제 OpenSearch/Lucene/ANN runtime 시험은 포함되지 않는다.

실험 보고서에는 다음을 남긴다.

1. 변경한 단 하나의 가정과 변경 전 손계산 예상값.
2. 입력 corpus/순위 목록과 정확한 정답 ID·count·score.
3. 실제 출력, 예상과 다른 결과 및 원인 설명.
4. 모델에서 성립한 보장과 실제 엔진에서 추가 확인할 경계.
5. 성능·내구성·인가를 측정하지 않았다면 해당 항목을 `미검증`으로 표시.

공식 문서 링크는 2026-10-04 확인했으며 `latest`는 변경될 수 있다. 이 트랙의 비교 기준은 OpenSearch 3.9.0 / Lucene 10.5.1이지만 CPU 모델이 해당 binary를 실행하는 것은 아니다. 실제 엔진 실험에 사용하는 release/plugin 버전과 조회한 문서 버전은 [트랙 안내](../README.md) 및 실행 보고서에 함께 기록한다.
