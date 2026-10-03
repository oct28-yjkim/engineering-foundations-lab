# AI 엔지니어링 연구와 실험

AI 시스템의 품질·비용·지연·안전성을 논문의 주장과 실제 실험으로 연결하는 영역입니다. 기존 데이터베이스·스트리밍·플랫폼·관측 과정을 대체하지 않고, 모델과 애플리케이션 계층을 추가합니다.

현재 제공하는 [LLM 논문 실험 트랙](llm-paper-lab/README.md)은 핵심 논문 20편, 28주·14모듈, 심화 강의 7개와 Python 표준 라이브러리 기반 CPU 실험 6개로 구성됩니다. GPU 학습·서빙과 외부 API는 선택 확장입니다. 기본 실행에서 모델·데이터를 내려받거나 외부 요청을 보내지 않습니다.

## 기존 기술과 연결할 질문

| 기술 | AI 시스템에서의 실험 질문 |
| --- | --- |
| [PostgreSQL](../databases/postgresql/README.md) | 문서·평가 데이터·정답의 버전과 권한을 어떻게 일관되게 관리하는가? |
| [Kafka](../streaming/kafka/README.md) | 비동기 평가·색인 갱신의 재시도와 중복을 어떤 업무 ID로 검산하는가? |
| [ClickHouse](../databases/clickhouse/README.md) | 모델·prompt·dataset별 품질/비용/latency 비교에서 분모와 누락을 보존하는가? |
| [Sentry](../observability/sentry/README.md) | 요청 실패와 모델 오답을 구별하며 prompt·사용자 데이터가 telemetry로 새지 않는가? |
| [Supabase](../platforms/supabase/README.md) | 검색 전에 tenant 권한을 적용하며 RLS·Storage·API의 경계가 일치하는가? |

이 연결은 학습자가 선택할 통합 과제입니다. CPU 논문 실험에 Docker·DB·모델 API·전체 플랫폼 구축을 필수로 요구하지 않습니다. 기존 GPT 구현이나 에이전트 런타임 학습에서 만든 코드를 가져오는 경우에도 입력·버전·평가 계약을 새로 기록합니다.
