# Search Engineering Lab

검색 엔진을 단순 API 저장소가 아니라 **색인·순위·분산 실행·권한·복구를 함께 검증하는 시스템**으로 학습합니다. SQL 결과의 정확성과 검색 순위의 유용성을 같은 지표로 평가하지 않습니다.

| 경로 | 학습 범위 |
| --- | --- |
| [OpenSearch](opensearch/README.md) | 28주·14모듈·7강: Lucene, 쓰기/refresh, BM25, 분산 검색, 운영·보안, 벡터/하이브리드 |
| [실습 시작](opensearch/labs/README.md) | 실제 OpenSearch 3.9.0 단일 노드·REST 기준선, 원리 모형은 선택 부록 |
| [소스·논문 지도](opensearch/source-reading.md) | OpenSearch/Lucene/k-NN commit 고정, BM25·RRF·HNSW 논문과 반례 |
| [검색 품질·복구 연구 8주](../capstones/search-quality-recovery.md) | relevance·freshness·인가·재처리·복원 검증 |

트랙은 주 12시간 기준 약 336시간입니다. 공통 기반과 선택 8주 연구는 별도이며 기존 DB·Kafka·LLM 경로에 자동 합산하지 않습니다. 선행 과정은 [공통 기초](../databases/shared/foundations.md)이고, Python·확률·자료구조·HTTP를 함께 익힙니다.

실제 엔진의 기준선과 [운영·트러블슈팅](opensearch/operations.md)이 기본 경로입니다. 별도 Docker Compose의 단일 노드는 보안 플러그인이 꺼진 **개인 로컬 합성 데이터 전용**입니다. 분산 복제·권한·HNSW 성능·재해 복구가 검증된 환경으로 취급하지 않습니다. 원리 모형은 필요한 개념만 보충하는 선택 자료입니다.

연계 선택: [Kafka](../streaming/kafka/README.md)로 변경 이벤트를 전달하고, [PostgreSQL](../databases/postgresql/README.md)을 원본으로 유지하며, [LLM 논문 실험](../ai/llm-paper-lab/README.md)의 retrieval 평가로 확장합니다. connector·embedding 모델·RAG 앱은 자동 연결되지 않습니다.
