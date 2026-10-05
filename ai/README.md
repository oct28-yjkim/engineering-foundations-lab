# AI 엔지니어링 연구와 실험

AI 시스템의 품질·비용·지연·안전성을 논문의 주장과 실제 실험으로 연결하는 영역입니다. 기존 데이터베이스·스트리밍·플랫폼·관측 과정을 대체하지 않고, 모델과 애플리케이션 계층을 추가합니다.

처음부터 배우는 경로는 **[ML → DL → LLM 로드맵](ml-dl-llm-roadmap.md)**입니다. 데이터 분할·일반화·선형/트리 모델에서 시작해 역전파·표현 학습·시퀀스와 attention을 거쳐 기존 LLM 과정으로 이어집니다. 수학이 부족하면 [선택 기초 4주](foundations.md)를 먼저 사용합니다.

| 단계 | 논문과 과정 | 제공 CPU 실험 |
| --- | --- | --- |
| [ML](ml-paper-lab/README.md) | 핵심 11편·16주·8모듈·강의 4개 | ridge·logistic 학습, stump bagging, PCA/k-means 4개 |
| [DL](dl-paper-lab/README.md) | 핵심 12편·20주·10모듈·강의 4개 | autodiff/MLP·optimizer·공유 필터·Elman RNN 4개 |
| [LLM](llm-paper-lab/README.md) | 핵심 20편·28주·14모듈·강의 7개 | attention·LoRA·DPO·KV·retrieval·evaluation 모형 6개 |

ML/DL에는 작은 모델의 실제 fitting/학습을 포함하며, LLM의 기존 수학 모형을 실제 Transformer 학습으로 부르지 않습니다. Transformer는 DL과 LLM에 같은 원전으로 다시 등장합니다. GPU 학습·서빙과 외부 API는 선택 확장이며 기본 실행에서 모델·데이터를 내려받거나 외부 요청을 보내지 않습니다. [실행 환경](paper-labs-environment.md)·[평가](paper-labs-assessment.md)·[새 ML/DL 검증 기록](paper-labs-validation.md)을 확인합니다.

세 단계를 순차 이수하는 명목 예산은 **64주·768시간**, 선택 기초까지 포함하면 68주·816시간입니다. 원논문 전체 재현과 실제 업무 숙련은 별도 검증이 필요합니다. 기존 LLM을 이미 학습했다면 ML의 누출/평가 또는 DL의 gradient/sequence 진단으로 필요한 부분만 보충할 수 있습니다.

[MCP 심화 트랙](mcp/README.md)은 별도의 **28주·14모듈·7강·336시간**입니다. Model Context Protocol의 명세·wire·SDK·앱 정책을 분리하고 tool/resource/prompt, stdio/HTTP, 인증·권한, cache·취소·재시도, 호환성·운영을 연결합니다. 기본은 실제 공식 SDK stdio와 [요청·오류·지연 진단](mcp/operations.md)이며 원리 모형 4개는 선택 보조자료입니다. 모델/API 없이 실행하며 ML→DL→LLM 64주에 자동 합산하지 않습니다.

MCP의 기준은 protocol 2026-07-28, SDK 2.3.0입니다. 2025-11-25 handshake는 비교 과정이며 현재 stateless core와 섞지 않습니다. [버전 계약](mcp/compatibility.md)과 [실험 검증 범위](mcp/labs/validation.md)를 확인합니다.

## 기존 기술과 연결할 질문

| 기술 | AI 시스템에서의 실험 질문 |
| --- | --- |
| [PostgreSQL](../databases/postgresql/README.md) | 문서·평가 데이터·정답의 버전과 권한을 어떻게 일관되게 관리하는가? |
| [Kafka](../streaming/kafka/README.md) | 비동기 평가·색인 갱신의 재시도와 중복을 어떤 업무 ID로 검산하는가? |
| [ClickHouse](../databases/clickhouse/README.md) | 모델·prompt·dataset별 품질/비용/latency 비교에서 분모와 누락을 보존하는가? |
| [Sentry](../observability/sentry/README.md) | 요청 실패와 모델 오답을 구별하며 prompt·사용자 데이터가 telemetry로 새지 않는가? |
| [Supabase](../platforms/supabase/README.md) | 검색 전에 tenant 권한을 적용하며 RLS·Storage·API의 경계가 일치하는가? |
| [MCP](mcp/README.md) | protocol 성공·모델의 도구 선택·업무 허가·실제 실행 결과를 분리하는가? |
| [Qdrant/OpenSearch](../search/README.md) | representation의 의미 품질과 검색 엔진의 필터·근사 탐색·운영 상태를 분리하는가? |
| [OpenBao/Vault](../security/README.md) | 모델에 비밀을 노출하지 않고 trusted tool 실행 경계에만 credential을 전달하는가? |

이 연결은 학습자가 선택할 통합 과제입니다. ML/DL/LLM CPU 논문 실험에 Docker·DB·모델 API·전체 플랫폼 구축을 필수로 요구하지 않습니다. 기존 GPT 구현이나 에이전트 런타임 학습에서 만든 코드를 가져오는 경우에도 입력·버전·평가 계약을 새로 기록합니다.
