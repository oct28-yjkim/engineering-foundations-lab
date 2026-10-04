# Qdrant 벡터 검색 기능과 운영 학습

벡터를 넣고 nearest neighbor를 조회하는 데서 시작해 **어떤 후보가 왜 반환됐는지, 필터·색인·저장 방식이 무엇을 바꾸는지, 복제와 복구가 어디까지 보장하는지** 직접 검산하는 과정입니다. 기본 LAB과 28주·14모듈·7강 심화를 제공합니다. 고급 기능도 채택 여부와 별개로 목적·동작·관측·제약·반례·대안을 배웁니다.

Qdrant는 원본 업무 DB, embedding 모델, LLM 답변 평가기를 대신하지 않습니다. 기본 실습은 실제 Qdrant REST API와 작은 고정 벡터를 사용합니다. CPU 수학 모형이나 Python client의 local mode로 서버 검증을 대신하지 않으며 GPU·모델 다운로드·유료 embedding API가 필요 없습니다.

## 시작 순서

1. [환경](environment.md)에서 단일 노드 전용 Compose·포트·volume·합성 데이터 경계를 확인합니다.
2. [기본 LAB](labs/README.md)에서 생성→기록→조회→필터→업데이트→삭제/복구의 독립 정답을 확인합니다.
3. named dense/sparse·payload index·RRF를 비교하고 차원/이름/타입 오류를 하나씩 진단합니다. [운영 지침](operations.md)의 신호를 함께 관찰합니다.
4. [기능별 수동 LAB](labs/advanced.md)에서 nested filter·multivector·strict mode·alias 전환·snapshot 복원을 실행합니다.
5. [별도 3노드 LAB](labs/cluster.md)에서 shard/replica 배치·일관성·한 노드 이탈과 복귀를 확인합니다.
6. [기능 지도](feature-map.md)로 빠진 영역을 확인하고 [커리큘럼](curriculum.md)·[소스](source-reading.md)·[평가](assessment.md)로 확장합니다.

## 제공 범위와 완료 상태

| 경로 | 제공물 | 이 경로만으로 주장할 수 없는 것 |
| --- | --- | --- |
| 단일 서버 | 버전 고정 Compose, 6-point fixture, 실제 REST runner와 단위 테스트 | 실제 실행 전 성공, tiny data에서 HNSW 성능·운영 처리량 |
| 기능 탐구 | 구체적인 요청·기대 ID/점수·거부와 복구가 있는 수동 절차 | 설명만 읽고 실행 완료, 모든 검색 방식의 업무 적합성 |
| 분산 | 독립 3노드 Compose, replica/read/write 비교와 stop/start 카드 | AZ 손실·partition·운영 HA·무손실 자동 재조정 |
| 심화 | 14모듈·7강, 기능/제약 지도, 고정 소스·논문과 독립 평가 | 모든 provider/edition/규모의 기능 실행 완료 |

현재 작성·검사·실측 상태는 [검증 기록](labs/validation.md)에 구분합니다. 단위 테스트 PASS는 서버의 API·저장·복제 검증이 아닙니다. 기능 지도에서 **제공 runner / 수동 절차 / 추가 환경 / 조사 과제**를 구별하며 이름만 있는 기능을 완료로 표시하지 않습니다.

## 버전과 제품 경계

기준은 **Qdrant 1.19.1**, peeled source commit `6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de`, 확인일 2026-10-04입니다. [공식 release](https://github.com/qdrant/qdrant/releases/tag/v1.19.1)와 실제 `/` 응답·image digest를 함께 기록합니다. `latest`를 자동으로 따라가지 않습니다. client SDK local mode, OSS 서버, Qdrant Cloud/Hybrid/Private/Edge는 동일 환경이 아닙니다. rolling 문서의 신규 설정은 고정 버전 명세와 대조합니다.

학습용 포트는 loopback REST만 공개하고 API 인증/TLS는 꺼져 있습니다. 로컬 다른 process·사용자도 접근 가능하므로 개인 컴퓨터의 합성 데이터에만 사용합니다. tenant filter는 인증·인가가 아니며 이 구성은 보안 학습 완료 환경이 아닙니다.

## 다른 트랙과 연결

- [OpenSearch](../opensearch/README.md): BM25·dense·hybrid의 후보 생성과 ranking을 비교합니다. API 이름이나 같은 RRF 사용이 동일한 점수·결과를 보장하지 않습니다.
- [PostgreSQL](../../databases/postgresql/README.md) / [Kafka](../../streaming/kafka/README.md): 업무 원장→검색 projection의 version·삭제·중복·재처리를 대조합니다.
- [LLM 논문](../../ai/llm-paper-lab/README.md): retrieval Recall@k와 생성 답변의 근거 충실도·권한·최신성을 별도로 평가합니다. embedding 생성부터 시작할 필요는 없습니다.
- [Sentry](../../observability/sentry/README.md): client timeout과 서버 응답·실제 반영 여부를 연결하되 원문 벡터·사용자 payload를 오류 로그에 싣지 않습니다.
