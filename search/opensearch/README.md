# OpenSearch — 검색 원리부터 분산 검색 시스템 연구까지

문서를 넣고 검색하는 단계에서 출발해 **왜 이 문서가 일치했는지, 왜 이 순위인지, 언제 보이고 언제 복구되는지, 누가 볼 수 있는지**를 증명하는 28주·14모듈·약 336시간 과정입니다. Lucene 자료구조, OpenSearch 분산 실행, 운영 실패 모델, 검색 품질을 하나의 실험 원장으로 연결합니다.

OpenSearch는 검색·분석 엔진이며 업무 원장의 트랜잭션이나 LLM 답변의 사실성을 자동으로 보장하지 않습니다. 이 교재의 오픈소스 OpenSearch와 Amazon OpenSearch Service/Serverless도 동일한 배포·권한·복구 제품으로 취급하지 않습니다. 관리형 서비스는 별도 선택 확장입니다.

## 시작 순서

1. [기본 LAB](labs/README.md)에서 단일 노드를 준비하고 합성 문서의 정상 색인·검색·정렬·집계 결과를 확인합니다. HTTP/JSON/Python이 낯설면 [공통 기초](../../databases/shared/foundations.md)에서 필요한 부분을 보충합니다.
2. mapping/analyzer·ACK·GET·refresh·검색 경계를 설명하고 [관측 LAB](labs/observation.md)으로 수집 API·지표 의미·query 비용·환경 제약을 익힙니다.
3. [단계형 사건 5개](labs/incidents.md)에서 검색 누락·bulk 부분 실패·write block·yellow·pagination 오류를 하나씩 진단·복구합니다. [운영 runbook](operations.md)을 함께 조사합니다.
4. 추가 자원을 선택했다면 [3→4노드 확장 LAB](labs/scaling-incidents.md)에서 replica 자리 부족·allocation 오류·한 노드 이탈·routing 편중을 확인합니다.
5. 필요해진 주제의 [28주 커리큘럼](curriculum.md)·[소스·논문 지도](source-reading.md)로 깊이를 확장하고 [평가](assessment.md)에서 기본 실측과 심화 완료를 구분합니다.

기본 순서는 **정상 기능 → 동작 원리 → 모니터링 → 제약 → 문제 진단·복구**입니다. 28주 전체 이수나 원리 모형 통과는 기본 LAB의 선수 조건이 아닙니다. 환경이 없으면 조사·설계/원리 학습으로 진행하고 실제 실측 관문은 미완료로 남깁니다. [신규 실습 검증 기록](labs/incident-validation.md)과 문서 끝의 선택 부록을 구분합니다.

## 버전과 실험 범위

반복 가능한 기준은 **OpenSearch 3.9.0**, 해당 소스의 Lucene 의존성은 **10.5.1**입니다. 전체 제품의 영구적인 최신 버전이라는 뜻은 아닙니다. 문서 확인일은 2026-10-04이며, `latest` 공식 문서는 이후 변경될 수 있으므로 [고정 소스](source-reading.md)·플러그인·컨테이너 이미지 식별자와 실제 서버 응답을 함께 보존합니다. Lucene 버전은 OpenSearch 버전과 독립적으로 임의 선택하지 않습니다.

| 범위 | 제공 또는 수행할 것 | 이 범위로 증명하지 못하는 것 |
| --- | --- | --- |
| LOCAL-ENGINE / OPERATIONS | 주 실습: 단일 노드 합성 fixture·node/cluster 기준선·사건 2개와 회복 | replica 승격, quorum, TLS/DLS/FLS, 실제 ANN 품질·클러스터 성능 |
| CLUSTER-DESIGN / CLUSTER-LAB | 제공된 별도 3→4노드 Compose·수동 배치/복귀/routing 카드 / 사용자 실측 | 작성·구성 검사만으로 실제 장애 통과, AZ 손실·partition·처리량 보장 |
| SECURITY-LAB / ANN-LAB | 보안 활성화 환경 / 고정 벡터와 실제 ANN 별도 과제 | 기본 단일 노드 코드나 CPU 정렬 모형의 자동 보장 |
| BUILD | 고정 소스의 회귀 테스트·작은 수정 | 관리형 서비스의 비공개 운영 계층 |
| OFFLINE (선택 보조) | BM25·refresh 가시성·분산 후보·hybrid/filter 원리 모형 4개 | 실제 Lucene 점수·fsync·내구성·HNSW·분산 장애·권한 |

기본 로컬 엔진 과정에는 GPU·embedding API·클라우드 과금이 필요 없지만 Docker 자원·설치·이미지 다운로드가 필요합니다. 합성 데이터 전용이며 보안 검증 환경이 아닙니다. 다중 shard/노드의 작은 배치·복귀 실습은 제공하지만 PIT, snapshot, HNSW, 권한·network partition·DR는 **추가 구현 과제**입니다. 제공 스크립트가 모든 강의 과제를 자동 수행하지 않습니다. 실제 실행 여부와 제약은 [실습 안내](labs/README.md)를 기준으로 확인합니다.

## 다른 트랙과 연결하기

- [PostgreSQL](../../databases/postgresql/README.md): 업무 원장과 검색 projection을 분리하고 ID·업무 version·삭제·재색인 원장을 비교합니다. refresh나 replica가 DB transaction을 대신하지 않습니다.
- [Kafka](../../streaming/kafka/README.md): offset 성공과 bulk 개별 항목 성공의 간격, 재전송·out-of-order·tombstone 보존을 연결합니다.
- [ClickHouse](../../databases/clickhouse/README.md): 집계·컬럼 접근과 검색 postings/doc values를 비교합니다. 상위 `terms` bucket 결과를 완전한 SQL GROUP BY 결과라고 가정하지 않습니다.
- [LLM 논문 실험](../../ai/llm-paper-lab/README.md): BM25, dense retrieval, hybrid, reranker를 RAG retrieval 단계와 연결합니다. 검색 품질·권한·최신성·생성 답변 품질은 별도 gate입니다.
- [Spark](../../data-processing/spark/README.md): corpus 정제·분할·중복 제거의 fingerprint를 검색 index와 평가 judgment에 연결합니다.

OS14는 **2주 안에 끝낼 한 가지 작은 연구**입니다. DB·Kafka·검색·RAG·DR 전체를 새로 구축하는 과정이 아니며, 큰 통합은 선택 [8주 검색 품질·복구 캡스톤](../../capstones/search-quality-recovery.md)으로 분리합니다.

## 선택 원리 부록

[오프라인 모형](labs/offline.md)은 수식·반례 이해가 필요할 때 선택합니다. 필수 선행 과정이나 운영 완료 조건이 아닙니다.

```text
python -B search/opensearch/labs/offline_lab.py --lab all
```
