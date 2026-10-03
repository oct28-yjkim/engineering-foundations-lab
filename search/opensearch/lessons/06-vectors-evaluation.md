# 06. Vector·hybrid — 후보 손실과 랭킹 품질을 분리한다

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

별도 ANN-LAB은 고정된 작은 합성 벡터부터 시작하며 embedding API나 GPU가 필수가 아닙니다. 제공 CPU `hybrid-filter`는 고정 순위 목록의 후보 절단·fusion/filter 교육용 모형으로, 벡터 거리 계산이나 HNSW를 구현하지 않습니다. LOCAL-ENGINE의 기본 fixture도 ANN 실행을 제공하지 않으므로 아래 ANN-LAB은 추가 구현 과제입니다.

<a id="os11"></a>
## OS11 · exact oracle·HNSW·엔진·필터

### 원리와 내부 동작

벡터 차원·전처리·normalization·거리 함수가 검색의 의미를 결정합니다. cosine, inner product, L2는 일반적으로 같은 순서가 아니며 단위 길이 같은 추가 조건에서 관계를 유도해야 합니다. zero vector·NaN/Infinity·차원 오류·동점 처리의 정책도 정합니다. OpenSearch가 반환하는 `_score`의 변환을 원래 거리값 자체와 혼동하지 않습니다.

HNSW는 계층적 graph 탐색을 이용해 계산량과 recall을 교환합니다. graph 연결 수·construction effort·search effort가 각각 build 시간·메모리·탐색 품질에 주는 영향을 분리합니다. Lucene, Faiss 등 engine마다 지원 method·parameter·filter·메모리 경로가 다르므로 다른 엔진의 knob를 그대로 복사하지 않습니다. 실제 선택한 3.9.0 배포·plugin·mapping과 [methods/engines](https://docs.opensearch.org/latest/mappings/supported-field-types/knn-methods-engines/)를 대조합니다.

post-filter는 ANN이 뽑은 후보를 나중에 버리므로 충분한 허용 문서가 있어도 k보다 적게 반환할 수 있습니다. efficient filter는 engine/method별 탐색·exact fallback 전략을 사용하므로 모든 설정에서 동일한 성능·보장을 선언하지 않습니다. exhaustive scoring은 비교 대상이 작으면 좋은 oracle이지만 large-scale latency 해법이라는 뜻은 아닙니다. [Filtering](https://docs.opensearch.org/latest/vector-search/filter-search-knn/index/)과 [exact scoring](https://docs.opensearch.org/latest/vector-search/vector-search-techniques/knn-score-script/)을 확인합니다.

### 별도 ANN-LAB

1. 고정 seed로 작은 corpus를 만들고 원본 vector와 query를 저장합니다. CPU exhaustive 거리 계산의 손계산 fixture를 먼저 통과시킵니다. 모델로 vector를 생성하는 경우 모델 revision·tokenizer·pooling·normalization을 추가로 고정합니다.
2. 같은 corpus·거리·filter에서 exact top-k를 정의합니다. 허용 문서가 k보다 적으면 분모는 허용 가능한 `min(k, N_allowed)`로 정하고 0개인 query는 별도 처리합니다. 경계 동점의 정답 집합 규칙을 명시합니다.
3. 한 engine/method의 지원 parameter만 바꾸며 recall@k, returned count, query latency, build 시간, index 크기, memory를 기록합니다. 작은 corpus에서 exact fallback이 실행되면 이를 HNSW 품질 검증으로 부르지 않습니다.
4. tenant/category/time filter의 선택도를 바꾸어 pre/exact, supported efficient filtering, post-filter를 비교합니다. 각 query의 정답도 필터 후 corpus에서 다시 구합니다.
5. delete/update, segment 수·merge, cold/warm 조건을 분리합니다. ANN graph가 바뀐 뒤 품질이 달라진 것을 embedding 모델 변화로 오인하지 않습니다.
6. quantization을 추가할 경우 원본 full-precision exact와 quantized 공간의 exact를 구별합니다. “압축된 공간에서 exact”가 원본 공간 top-k와 항상 같다는 뜻은 아닙니다. candidate oversampling과 rescoring을 각각 검증합니다.

### 통과 기준

relevance judgment와 ANN exact-neighbor recall을 같은 지표로 쓰지 않습니다. 전체 query 평균뿐 아니라 restrictive-filter slice와 최악 query를 제출합니다. filter를 검색 정확성 조건으로 시험한 결과를 DLS/FLS 인가 시험으로 대체하면 미통과입니다.

<a id="os12"></a>
## OS12 · hybrid·normalization·RRF·reranker·RAG

### 원리

BM25 score와 vector score를 의미가 같은 숫자처럼 더하지 않습니다. score normalization은 결과 분포·후보 크기·이상치에 영향을 받고 RRF는 score 크기를 버리고 rank를 사용합니다. 둘 다 이미 잘린 candidate 밖의 문서를 만들어내지 못합니다.

```text
RRF(d) = sum(1 / (rank_constant + rank_i(d)) for lists containing d)
```

rank는 1부터 시작하며 미등장 list의 기여는 0입니다. rank constant와 후보 깊이는 별도 parameter입니다. 같은 문서가 list 안에서 중복 등장하면 단일 문서로 처리할 계약을 정하고 source document와 chunk ID의 중복도 구별합니다. [공식 RRF](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/rrf/)와 [score ranker](https://docs.opensearch.org/latest/search-plugins/search-pipelines/score-ranker-processor/)를 실제 plugin 버전과 대조합니다.

### 추가 실험

1. OS06의 frozen judgment를 재사용합니다. BM25 단독, dense 단독, 정규화 결합, RRF 네 baseline을 같은 corpus·권한·query split으로 비교합니다.
2. lexical/vector 후보 깊이를 따로 바꿉니다. candidate union에 정답이 없는 miss와 fusion/reranker가 낮게 둔 ranking miss를 분리합니다. 후보 recall을 고정한 실험도 추가합니다.
3. RRF constant 또는 fusion weight를 tuning split에서만 선택합니다. score 크기가 하나만 매우 큰 문서, 한 list에만 있는 문서, 서로 상충하는 순위, 모든 score가 같은 list를 음성 fixture로 넣습니다.
4. query slice별 nDCG·MRR·중복 원문 수·권한 위반·최신성·end-to-end latency를 보고합니다. RRF가 언제나 정규화 결합보다 우월하다는 결론을 사전에 정하지 않습니다.
5. reranker는 candidate가 고정된 선택 확장입니다. 실제 모델·GPU/API가 필요하면 별도 동의·비용 상한·비밀 처리·모델 revision을 먼저 정합니다. 기본 CPU 합성 점수 실험을 실제 모델 검증으로 보고하지 않습니다.

### LLM engineer의 추가 계약

chunking은 문서 ID·version·원문 위치·인용 위치·ACL과 함께 정의합니다. 원문 삭제나 권한 회수가 검색 index뿐 아니라 cached result·retrieval cache·reranker 입력·응답 로그에도 어떻게 반영되는지 설계합니다. 검색 후 filter만으로 민감한 문서를 외부 reranker/API에 보내는 것을 정당화하지 않습니다.

RAG 평가에서는 retrieval relevance, 근거의 최신성·허용성, 답변의 사실성·인용 충실성, 답변 유보, prompt injection 저항성을 분리합니다. 검색 문서 안의 지시문은 신뢰할 수 없는 데이터이며 tool 실행 권한을 부여하지 않습니다. [LLM 논문 실험](../../../ai/llm-paper-lab/README.md)으로 확장하되 실제 생성 모델을 실행하지 않았다면 RAG end-to-end 결과도 미검증입니다.

### 제출

query별 lexical/vector 후보→fusion→reranker→최종 문서의 ID 원장, 실험별 품질·latency·권한 gate, tuning/holdout fingerprint를 제출합니다. 상위 평균 지표가 좋아져도 권한·삭제·최신성 필수 gate를 깨면 변경을 채택하지 않습니다.
