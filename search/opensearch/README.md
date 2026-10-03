# OpenSearch — 검색 원리부터 분산 검색 시스템 연구까지

문서를 넣고 검색하는 단계에서 출발해 **왜 이 문서가 일치했는지, 왜 이 순위인지, 언제 보이고 언제 복구되는지, 누가 볼 수 있는지**를 증명하는 28주·14모듈·약 336시간 과정입니다. Lucene 자료구조, OpenSearch 분산 실행, 운영 실패 모델, 검색 품질을 하나의 실험 원장으로 연결합니다.

OpenSearch는 검색·분석 엔진이며 업무 원장의 트랜잭션이나 LLM 답변의 사실성을 자동으로 보장하지 않습니다. 이 교재의 오픈소스 OpenSearch와 Amazon OpenSearch Service/Serverless도 동일한 배포·권한·복구 제품으로 취급하지 않습니다. 관리형 서비스는 별도 선택 확장입니다.

## 시작 순서

1. [공통 기초](../../databases/shared/foundations.md)의 OS·네트워크·트랜잭션·분산 실패 모델을 진단합니다. HTTP/JSON, Python, Java 클래스·iterator·동시성은 별도 보충합니다.
2. [실습 안내](labs/README.md)에서 OFFLINE, LOCAL-ENGINE, 별도 확장의 차이를 확인합니다.
3. [28주 커리큘럼](curriculum.md)의 7개 강의와 14개 실험 보고서를 작성합니다.
4. [소스·논문 지도](source-reading.md)에서 관찰한 현상의 구현과 논문 가정을 대조합니다.
5. [평가](assessment.md)에서 실행·설계·미검증 증거를 분리합니다.

저장소 루트에서 Python 표준 라이브러리만으로 시작합니다. 이 명령은 실제 OpenSearch나 Lucene이 아닌 교육용 모형을 실행합니다.

```text
python -B search/opensearch/labs/offline_lab.py --lab all
```

## 버전과 실험 범위

반복 가능한 기준은 **OpenSearch 3.9.0**, 해당 소스의 Lucene 의존성은 **10.5.1**입니다. 전체 제품의 영구적인 최신 버전이라는 뜻은 아닙니다. 문서 확인일은 2026-10-04이며, `latest` 공식 문서는 이후 변경될 수 있으므로 [고정 소스](source-reading.md)·플러그인·컨테이너 이미지 식별자와 실제 서버 응답을 함께 보존합니다. Lucene 버전은 OpenSearch 버전과 독립적으로 임의 선택하지 않습니다.

| 범위 | 제공 또는 수행할 것 | 이 범위로 증명하지 못하는 것 |
| --- | --- | --- |
| OFFLINE | BM25·refresh 가시성·분산 후보·hybrid/filter CPU 모형 4개 | 실제 Lucene 점수·fsync·내구성·HNSW·분산 장애·권한 |
| LOCAL-ENGINE | 별도 실행하는 단일 노드 합성 fixture: term/match/phrase·refresh·OCC·bulk 항목 오류 | 단계별 분석 API, replica 승격, quorum, TLS/DLS/FLS, 실제 ANN 품질·클러스터 성능 |
| CLUSTER-DESIGN / CLUSTER-LAB | 장애·격리·복구 설계 / 별도 다중 노드 실측 | 설계를 작성했다는 사실만으로 실제 장애 통과 |
| SECURITY-LAB / ANN-LAB | 보안 활성화 환경 / 고정 벡터와 실제 ANN 별도 과제 | 기본 단일 노드 코드나 CPU 정렬 모형의 자동 보장 |
| BUILD | 고정 소스의 회귀 테스트·작은 수정 | 관리형 서비스의 비공개 운영 계층 |

기본 CPU 과정에는 외부 계정·GPU·embedding API·클라우드 과금이 필요 없습니다. 제공하는 로컬 엔진 환경은 합성 데이터 전용이며 보안 검증 환경이 아닙니다. 강의의 다중 shard, PIT, snapshot, HNSW, 권한·장애 실험은 **학습자가 추가 구현하는 과제**입니다. 제공 스크립트가 모든 강의 과제를 자동으로 수행하지 않습니다. 실제 실행 여부와 제약은 [실습 안내](labs/README.md)를 기준으로 확인합니다.

## 다른 트랙과 연결하기

- [PostgreSQL](../../databases/postgresql/README.md): 업무 원장과 검색 projection을 분리하고 ID·업무 version·삭제·재색인 원장을 비교합니다. refresh나 replica가 DB transaction을 대신하지 않습니다.
- [Kafka](../../streaming/kafka/README.md): offset 성공과 bulk 개별 항목 성공의 간격, 재전송·out-of-order·tombstone 보존을 연결합니다.
- [ClickHouse](../../databases/clickhouse/README.md): 집계·컬럼 접근과 검색 postings/doc values를 비교합니다. 상위 `terms` bucket 결과를 완전한 SQL GROUP BY 결과라고 가정하지 않습니다.
- [LLM 논문 실험](../../ai/llm-paper-lab/README.md): BM25, dense retrieval, hybrid, reranker를 RAG retrieval 단계와 연결합니다. 검색 품질·권한·최신성·생성 답변 품질은 별도 gate입니다.
- [Spark](../../data-processing/spark/README.md): corpus 정제·분할·중복 제거의 fingerprint를 검색 index와 평가 judgment에 연결합니다.

OS14는 **2주 안에 끝낼 한 가지 작은 연구**입니다. DB·Kafka·검색·RAG·DR 전체를 새로 구축하는 과정이 아니며, 큰 통합은 선택 [8주 검색 품질·복구 캡스톤](../../capstones/search-quality-recovery.md)으로 분리합니다.
