# OpenSearch 소스·논문 읽기 지도

[커리큘럼](curriculum.md) · [강의 입구](README.md) · [실습](labs/README.md)

파일 이름을 아는 것이 아니라 **요청의 입력 조건 → 실행 경계 → 상태 변화 → 관측값 → 반례를 검사하는 테스트**를 연결합니다. 정적 소스 읽기, 로컬 source build, 실제 제품 실험은 서로 다른 증거입니다.

## 버전과 증거 수준

2026-10-04에 공식 release/tag·GitHub tree·아래 일부 원문을 확인했습니다. 현재 `latest` 문서는 실행 이미지와 다른 기능을 포함할 수 있으므로 API와 설정은 해당 버전에서 다시 검증합니다. 소스 빌드·Java 테스트 실행은 이 저장소에서 수행하지 않았습니다.

| 계층 | 고정 기준 | 읽기 범위 |
| --- | --- | --- |
| OpenSearch | [3.9.0 release](https://github.com/opensearch-project/OpenSearch/releases/tag/3.9.0), commit `4ee42a94e87f66fbf1e62a9871b1b87f91e02472` | core server·coordination·query·snapshot |
| Apache Lucene | tag `releases/lucene/10.5.1`, commit `64ce863a2bea79c69c19c4d56268c26710ff0ff9` | reader/writer·BM25·collector·Lucene HNSW |
| k-NN plugin | [3.9.0.0 release](https://github.com/opensearch-project/k-NN/releases/tag/3.9.0.0), commit `e654c346d04f3599491f6e307384e651b28c6135` | query builder·engine/filter별 query 생성 |

Lucene 10.5.1은 임의로 붙인 최신 버전이 아니라 OpenSearch 고정 commit의 [gradle/libs.versions.toml](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/gradle/libs.versions.toml)에 선언된 의존성입니다. 플러그인 소스 tag와 실제 image 안의 plugin 목록은 별도 증거이므로 선택 벡터 실험에서 후자를 기록합니다. tag 기반 이미지의 digest·CPU 아키텍처도 별도로 관측합니다.

## 1. Lucene: 디스크와 검색기의 경계

| 모듈 | 고정 소스 | 추적·반증 질문 |
| --- | --- | --- |
| OS01–02 | [IndexWriter](https://github.com/apache/lucene/blob/64ce863a2bea79c69c19c4d56268c26710ff0ff9/lucene/core/src/java/org/apache/lucene/index/IndexWriter.java) | document 입력부터 token/flush/segment/merge 경로를 찾아라. OpenSearch refresh와 Lucene commit을 왜 같은 사건으로 설명하면 안 되는가? |
| OS03–04 | [DirectoryReader](https://github.com/apache/lucene/blob/64ce863a2bea79c69c19c4d56268c26710ff0ff9/lucene/core/src/java/org/apache/lucene/index/DirectoryReader.java) | 어떤 writer/commit으로부터 reader가 열리는가? reader 세대가 바뀌어야 보이는 변경과 realtime GET을 구별하라. |
| OS05–06 | [BM25Similarity](https://github.com/apache/lucene/blob/64ce863a2bea79c69c19c4d56268c26710ff0ff9/lucene/core/src/java/org/apache/lucene/search/similarities/BM25Similarity.java) | collection/term statistics, IDF, tf, length norm, boost가 합쳐지는 위치를 찾아라. 논문 공식·CPU 공식·구현의 상수/정밀도 차이가 순위/절댓값에 미치는 영향을 설명하라. |
| OS05–08 | [TopScoreDocCollector](https://github.com/apache/lucene/blob/64ce863a2bea79c69c19c4d56268c26710ff0ff9/lucene/core/src/java/org/apache/lucene/search/TopScoreDocCollector.java) | collector의 competitive threshold, tie와 total-hits 정확도 계약은 무엇인가? 모든 hit를 세는 것과 top-k만 얻는 비용을 분리하라. |
| OS11–12 | [HnswGraphSearcher](https://github.com/apache/lucene/blob/64ce863a2bea79c69c19c4d56268c26710ff0ff9/lucene/core/src/java/org/apache/lucene/util/hnsw/HnswGraphSearcher.java) | 후보 방문·종료 조건·accept filter는 어디에서 적용되는가? 이것이 모든 k-NN engine의 구현이라고 가정하지 마라. |

검증 출발점은 [TestBM25Similarity](https://github.com/apache/lucene/blob/64ce863a2bea79c69c19c4d56268c26710ff0ff9/lucene/core/src/test/org/apache/lucene/search/similarities/TestBM25Similarity.java)입니다. 기존 테스트의 입력/불변식/실패 조건을 설명한 뒤 작은 counterexample 하나를 제안합니다. 테스트 파일을 읽은 사실과 실행 성공을 구분합니다.

## 2. OpenSearch: 요청부터 상태와 결과까지

| 모듈 | 고정 소스 | 반드시 남길 추적 결과 |
| --- | --- | --- |
| OS03–04 | [TransportBulkAction](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/action/bulk/TransportBulkAction.java) | batch의 routing·item별 실패·응답 조립, HTTP 성공과 전체 쓰기 성공의 차이 |
| OS03–04 | [IndexShard](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/index/shard/IndexShard.java) | primary term, local checkpoint, shard lifecycle, 쓰기/refresh 호출 경계 |
| OS03–04 | [InternalEngine](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/index/engine/InternalEngine.java) | `refresh`, `flush`, `maybeRefresh`, reader와 checkpoint의 연결; 내구성은 translog 설정까지 별도 추적 |
| OS04 | [TransportUpdateAction](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/action/update/TransportUpdateAction.java) | OCC token·충돌·재시도 계약, 원자적 문서 수정과 여러 문서 transaction의 차이 |
| OS05–06 | [SimilarityService](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/index/similarity/SimilarityService.java) / [SimilarityProviders](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/index/similarity/SimilarityProviders.java) | 이 snapshot의 default `BM25`와 별도 `LegacyBM25` 생성 경로를 비교. 오래된 버전의 기본 점수 공식을 그대로 가져오지 않기 |
| OS05–06 | [SearchService](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/search/SearchService.java) / [QueryPhase](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/search/query/QueryPhase.java) | search context, query execution, collector, partial response가 생기는 조건 |
| OS07–08 | [SearchPhaseController](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/action/search/SearchPhaseController.java) | `mergeTopDocs`·`reducedQueryPhase`, from/size·tie·fetch 대상; terms bucket reduction과 문서 top-k의 차이 |
| OS07–08 | [TransportReplicationAction](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/action/support/replication/TransportReplicationAction.java) | primary/replica 실행과 실패 응답. 문서/segment replication 설정, ACK, 가시성·내구성 조건을 별도로 명시 |
| OS07–08 | [Coordinator](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/cluster/coordination/Coordinator.java) | cluster-manager 선출·cluster state publication과 데이터 shard primary 역할의 구분 |
| OS09–10 | [SnapshotsService](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/main/java/org/opensearch/snapshots/SnapshotsService.java) | snapshot state transition·shard 완료·repository 경계, partial 실패와 restore oracle |

대응 테스트: [InternalEngineTests](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/test/java/org/opensearch/index/engine/InternalEngineTests.java), [IndexShardTests](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/test/java/org/opensearch/index/shard/IndexShardTests.java), [SearchPhaseControllerTests](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/server/src/test/java/org/opensearch/action/search/SearchPhaseControllerTests.java).

실제 함수 경로는 요청·설정에 따라 달라집니다. 위 표를 “모든 요청이 이 순서로 한 번씩 통과한다”는 call graph로 사용하지 않습니다. 실행을 추적하지 않았다면 관찰한 정적 호출 관계와 가정한 runtime 경로를 다른 색/주석으로 표시합니다.

## 3. k-NN: 논문과 plugin의 연결

[KNNQueryBuilder](https://github.com/opensearch-project/k-NN/blob/e654c346d04f3599491f6e307384e651b28c6135/src/main/java/org/opensearch/knn/index/query/KNNQueryBuilder.java)에서 요청 필드의 검증과 query 변환을, [KNNQueryFactory](https://github.com/opensearch-project/k-NN/blob/e654c346d04f3599491f6e307384e651b28c6135/src/main/java/org/opensearch/knn/index/query/KNNQueryFactory.java)에서 engine·filter·nested 여부에 따른 분기를 읽습니다. Lucene 경로와 다른 engine의 native 경로를 구별합니다. HNSW 논문의 알고리즘을 읽었다는 이유로 특정 plugin engine의 filter·parameter·메모리 형식을 안다고 주장하지 않습니다.

대응 테스트는 [KNNQueryBuilderTests](https://github.com/opensearch-project/k-NN/blob/e654c346d04f3599491f6e307384e651b28c6135/src/test/java/org/opensearch/knn/index/query/KNNQueryBuilderTests.java), [KNNQueryFactoryTests](https://github.com/opensearch-project/k-NN/blob/e654c346d04f3599491f6e307384e651b28c6135/src/test/java/org/opensearch/knn/index/query/KNNQueryFactoryTests.java)입니다. 하나의 허용된 mapping/engine 조합과 거부되는 조합을 골라 validation 경계를 설명합니다.

## 4. 핵심 논문 3편과 실험

| 원문 | 읽기 질문 | 제공 실험 / 추가 구현 |
| --- | --- | --- |
| Robertson·Zaragoza, 2009, [The Probabilistic Relevance Framework: BM25 and Beyond](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf) | relevance 가정·IDF·tf 포화·length normalization은 어떤 실패를 줄이고 어떤 편향을 만드는가? | `bm25` 손계산과 k1/b 변화. 실제 `_explain`과 차이를 분석하되 점수의 완전 일치를 약속하지 않음 |
| Cormack·Clarke·Buettcher, SIGIR 2009, [Reciprocal rank fusion outperforms condorcet and individual rank learning methods](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) | 순위를 합치면 score scale 문제는 어떻게 바뀌며, 원래 후보에 없던 문서는 복원할 수 있는가? | `hybrid-filter`의 1-based RRF·후보 절단 반례. 실제 고정 qrels에서 lexical/vector/fusion 각각 평가 |
| Malkov·Yashunin, [Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs](https://arxiv.org/abs/1603.09320v4), 2016 preprint/2018 revision | 계층·neighbor 선택·탐색 budget의 recall/latency/memory tradeoff는 무엇인가? | 제공 CPU 코드는 HNSW 구현이 아님. 별도 실제 engine에서 exact filtered ground truth 대비 ANN recall·지연·메모리 측정 |

논문 보고값을 재현 결과로 복사하지 않습니다. 합성 CPU 실험, 소규모 실제 제품 실험, 논문의 데이터·모델·환경까지 맞춘 재현을 세 수준으로 구분합니다. 최신 embedding 모델과 외부 API는 필수가 아닙니다. 연결 과정은 [LLM 논문 실험](../../ai/llm-paper-lab/README.md)의 retrieval·평가 모듈이며, 해당 트랙도 자동 실행되지 않습니다.

## 제출 양식과 구현 확장

한 장 trace마다 다음을 남깁니다.

1. commit/image fingerprint, 요청·설정·입력과 정확한 질문 하나.
2. 진입점·분기 조건·핵심 자료구조·상태 변경·동기화 경계.
3. 기대 응답과 독립 oracle, 기존 Java 테스트의 대응 assertion.
4. 최소 반례·실측/미실측 구분·설명이 틀렸을 때 나타날 신호.
5. 작은 회귀 테스트 제안과 범위 밖 가정. 실행하지 않은 테스트는 미실행 표시.

소스 빌드는 고정 tag의 공식 build 안내·JDK·Gradle wrapper·plugin 호환성을 먼저 확인한 뒤 별도 checkout에서 수행합니다. 다운로드·의존성 설치·긴 테스트·host 설정 변경은 이 문서나 CPU runner가 자동 수행하지 않습니다. 작은 단위 테스트 → 관련 module 회귀 → 실제 REST fixture 순서로 확장하고, source patch만으로 운영 성능 개선이 입증됐다고 기록하지 않습니다.
