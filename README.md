# Engineering Foundations Lab — Zero to Hero

데이터·AI 시스템을 사용하는 단계에서 출발해 **동작을 예측하고, 내부 구현을 추적하며, 장애와 성능 문제를 증거로 설명하는 엔지니어**로 성장하기 위한 한국어 교육 과정입니다. 현재 PostgreSQL, ClickHouse, MySQL, Apache Kafka, NATS, Sentry, Supabase, Apache Spark, Databricks, Terraform, Terragrunt, OpenSearch, OpenBao, HashiCorp Vault, MCP(Model Context Protocol)와 LLM 논문 실험 트랙을 제공합니다.

SQL 작성, 저장 구조, 실행 엔진, 동시성, 복구, 복제, 이벤트 스트리밍, 관측, 인증·인가, 성능 측정, 소스 코드 분석을 연결합니다. 가장 높은 단계의 완료 기준은 낯선 현상을 최소 재현으로 줄이고, 원인을 코드와 측정값으로 설명하며, 수정안의 회귀를 검증하는 것입니다.

**제품·도구는 실제 실행과 관측·트러블슈팅 중심**, LLM 논문은 기존 CPU 기본·GPU/API 선택 경로로 학습합니다. 제품별 원리 모형은 선택 보조자료입니다. [개편된 학습 원칙과 제품별 운영 실습](operations/README.md)을 확인합니다.

## 시작할 곳

| 문서 | 역할 |
| --- | --- |
| [운영·모니터링·트러블슈팅](operations/README.md) | 15개 제품의 핵심 지표·진단 순서·회복 검증·보고서 |
| [데이터베이스 교육 과정](databases/README.md) | 수준 진단, PG+CH 72주 경로와 MySQL 선택 과정, 통과 기준 |
| [이벤트 스트리밍 교육 과정](streaming/README.md) | Kafka·NATS 선택 트랙과 PG/Kafka/CH 통합 100주 경로 |
| [공통 기초 8주](databases/shared/foundations.md) | SQL·자료구조·OS·확률·분산 시스템의 연결 |
| [PostgreSQL](databases/postgresql/README.md) | 14개 모듈, 저장·MVCC·planner·WAL·운영 |
| [ClickHouse](databases/clickhouse/README.md) | 14개 모듈, MergeTree·실행 pipeline·집계·분산 |
| [MySQL](databases/mysql/README.md) | 14개 모듈, InnoDB·MVCC·잠금·optimizer·redo/binlog·GTID·복구 |
| [Apache Kafka](streaming/kafka/README.md) | 14개 모듈, log·producer·consumer·KRaft·transaction·Streams·Connect |
| [NATS](streaming/nats/README.md) | 14개 모듈, Core·subject·JetStream·ACK/재전달·retention·Raft·보안·복구 |
| [Sentry](observability/sentry/README.md) | 14개 모듈, SDK·ingestion·grouping·tracing·sampling·개인정보·운영 |
| [Supabase](platforms/supabase/README.md) | 14개 모듈, PostgreSQL·Auth/JWT·RLS·Realtime·Storage·Functions·복구 |
| [Apache Spark](data-processing/spark/README.md) | 14개 모듈, 실행 엔진·Catalyst·shuffle·AQE·memory·Structured Streaming |
| [Databricks](platforms/databricks/README.md) | 14개 모듈, Delta·Unity Catalog·Lakeflow·Photon·배포·비용·복구 |
| [Terraform](infrastructure/terraform/README.md) | 14개 모듈, HCL·graph·provider·plan/apply·state·모듈·복구 |
| [Terragrunt](infrastructure/terragrunt/README.md) | 14개 모듈, include·dependency·unit/stack·실행 순서·CI·부분 실패 |
| [OpenSearch](search/opensearch/README.md) | 14개 모듈, Lucene·색인/refresh·BM25·분산 검색·복제·권한·벡터/하이브리드 |
| [OpenBao](security/openbao/README.md) | 14개 모듈, barrier·seal·identity·policy·KV·lease·transit·PKI·audit·Raft·복구 |
| [HashiCorp Vault](security/vault/README.md) | 14개 모듈, 비밀 수명·workload 인증·최소 권한·암호 서비스·HA·플러그인·edition 경계 |
| [비밀·신원 보안 경로](security/README.md) | 제품 비교, 격리 dev 환경과 상태·권한·lease·audit 진단 |
| [LLM 논문 실험](ai/llm-paper-lab/README.md) | 핵심 논문 20편·14모듈, CPU 실험 6개와 GPU/API 선택 확장 |
| [MCP](ai/mcp/README.md) | 14개 모듈, 명세·tools/resources/prompts·stdio/HTTP·인증·권한·cache·재시도·상호운용 |
| [실험 방법](databases/shared/experiment-method.md) | 재현성, 측정 오차, 정확성 oracle, 반증 |
| [통합 연구 8주](databases/shared/capstone.md) | PostgreSQL → Kafka → ClickHouse, CDC·복구·설계 검증 |
| [보안·관측 앱 연구 8주](capstones/secure-observable-app.md) | Supabase + Sentry, 테넌트 격리·privacy·장애·전체 상태 복구 |
| [Lakehouse 연구 8주](capstones/governed-lakehouse.md) | Spark + Databricks, version·권한·재처리·비용·복원 |
| [인프라 연구 8주](capstones/reproducible-infrastructure.md) | Terraform + Terragrunt, 변경 승인·state 소유권·부분 적용·복구 |
| [검색 품질·복구 연구 8주](capstones/search-quality-recovery.md) | OpenSearch, relevance·freshness·권한·재처리·복원 |
| [MySQL 트랜잭션·복구 연구 8주](capstones/mysql-transaction-recovery.md) | 불변식·재시도·동시 실행·복제 지연·독립 복원 |
| [비밀·신원·복구 연구 8주](capstones/secrets-identity-recovery.md) | OpenBao 또는 Vault, 권한·동적 계정 회수·키 수명·감사·독립 복원 |
| [MCP 도구 경계·장애 연구 8주](capstones/mcp-tool-boundary-recovery.md) | principal 격리·schema·cache·취소·업무 idempotency·호환성 |
| [NATS 전달·업무 복구 연구 8주](capstones/nats-delivery-recovery.md) | dedup·업무 원장·ACK 경계·tenant·quorum·독립 복원 |
| [환경과 실행 범위](databases/shared/environment.md) | 실행 명령, 버전 고정, 제공/미제공 환경 |

## 시간 계획

데이터베이스 두 트랙은 공통 기반 8주 + PostgreSQL 28주 + ClickHouse 28주 + 통합 연구 8주, 총 **72주·약 864시간**입니다. Kafka까지 순차로 포함하면 공통 기반 8주 + PostgreSQL 28주 + Kafka 28주 + ClickHouse 28주 + 통합 연구 8주, 총 **100주·약 1,200시간**을 기준으로 합니다. 공통 기반과 통합 연구는 한 번만 이수합니다.

주 12시간 가정이며 기간은 보장치가 아닙니다. 이미 익힌 내용은 진단 과제를 통과하면 줄이고, 복구·분산 실험에 실패하면 해당 모듈을 반복합니다.

Sentry와 Supabase도 각각 **28주·14모듈·약 336시간**의 선택 트랙입니다. 백엔드·보안·관측이 우선이면 PostgreSQL → Supabase → Sentry → 보안·관측 앱 연구를 선택할 수 있습니다. 이 3트랙 경로도 공통 8주 + 트랙 84주 + 선택한 캡스톤 8주 = 100주입니다. 통합 연구 주제를 모두 필수로 더하지 않습니다. 기존 다섯 제품(PostgreSQL·ClickHouse·Kafka·Sentry·Supabase)을 모두 순차 이수하는 경우에만 공통 8주 + 140주 + 선택 캡스톤 8주 = **156주·약 1,872시간**입니다. 모든 트랙을 끝내야 실무에 적용할 수 있다는 뜻은 아닙니다.

LLM 논문 실험은 별도의 **28주·336시간 선택 트랙**입니다. [논문 20편](ai/llm-paper-lab/papers.md)을 원리·구현·평가와 연결하며 CPU 오프라인부터 시작합니다. 기존 156주 경로에 자동으로 더하지 않으며 GPU/API는 필요할 때만 확장합니다. 행렬·미분·확률·Python은 별도 선수 지식입니다.

Spark와 Databricks도 각각 **28주·14모듈·336시간**의 선택 트랙입니다. [분산 처리 경로](data-processing/README.md)는 Spark 원리 → Databricks 플랫폼 순서를 권장하며, 두 트랙만 순차로 56주입니다. 공통 기초·선택 8주 통합 연구는 별도이고 기존 경로에 자동 가산하지 않습니다. Spark 4.0.4 로컬 실습과 Databricks Runtime의 관리형 기능을 동일 환경으로 취급하지 않습니다.

기술 한 개에 집중하는 경우 공통 기반 8주와 해당 트랙 28주를 먼저 진행합니다. 소스 빌드, 별도 복제 환경 구성, 실제 업무 경험을 더하면 기간이 늘어날 수 있습니다. 숙련도는 자료를 읽은 횟수보다 재현 가능한 결과물로 평가합니다.

Terraform과 Terragrunt는 각각 **28주·14모듈·336시간**의 선택 과정입니다. [인프라 경로](infrastructure/README.md)는 Terraform 실행·state 원리 → Terragrunt의 여러 unit 운영 순서이며 순차 56주입니다. 다른 제품 경로나 캡스톤 기간에 자동 합산하지 않습니다.

OpenSearch도 **28주·14모듈·7강·336시간**의 선택 트랙입니다. [검색 경로](search/README.md)는 Lucene 색인/reader → relevance → 분산 실행/복구 → 벡터·하이브리드 평가를 연결합니다. 기본 트랙 마지막 2주 미니 캡스톤과 별도 선택 연구 8주는 다른 과정이며 기존 전체 기간에 자동 가산하지 않습니다.

MySQL도 **28주·14모듈·7강·336시간**의 선택 트랙입니다. InnoDB의 저장·동시성·실행·복구를 깊이 있게 다루며 MySQL 8.4 LTS를 기준으로 합니다. 기존 72주 경로에 자동 추가하지 않고, PostgreSQL과 같은 isolation 이름도 실제 보장과 내부 구현을 따로 비교합니다.

OpenBao와 HashiCorp Vault도 각각 **28주·14모듈·7강·336시간**의 선택 트랙입니다. 두 제품을 순차 이수하면 56주이며 [공통 원리·제품 차이](security/shared/comparison.md)를 함께 학습합니다. 기본 모형은 공유하지만 제품별 구현과 검증은 분리합니다. 마지막 2주 미니 연구와 별도 선택 캡스톤 8주는 다르며 기존 경로에 자동 합산하지 않습니다.

MCP도 **28주·14모듈·7강·336시간**의 선택 트랙입니다. protocol 2026-07-28의 stateless core와 2025-11-25 classic 방식을 비교하고, SDK 구현과 앱의 권한/승인을 분리합니다. LLM 논문 경로에 자동 가산하지 않으며 기본 실습에 모델·유료 API가 필요하지 않습니다.

NATS도 **28주·14모듈·7강·336시간**의 선택 트랙입니다. Core NATS와 JetStream의 전달·보존·복구 경계를 구분하고 Kafka와 비교합니다. 기존 100주 PG/Kafka/CH 경로에 자동 가산하지 않으며, 마지막 2주 미니 연구와 별도 8주 캡스톤은 구분합니다.

## 첫 실습: 제품 관측과 트러블슈팅

제품별로 **실제 실행 → 정상 기준선 → 증상·지표·로그 → 원인/내부 구현 → 조치·복구**를 기본 경로로 사용합니다. [공통 운영 학습 안내](operations/README.md)와 [장애 보고서 양식](operations/incident-report-template.md)을 먼저 봅니다. 원리 모형은 선택 보조자료이며 실제 실습의 선수 조건이나 완료 증거가 아닙니다.

| 트랙 | 환경·실행 시작점 | 기본 운영 실습 |
| --- | --- | --- |
| PostgreSQL / ClickHouse | [별도 DB 환경과 SQL](databases/shared/environment.md) | [PG 세션·잠금·plan](databases/postgresql/operations.md), [CH query log·merge·복제](databases/clickhouse/operations.md) |
| MySQL | [단일 엔진·SQL](databases/mysql/labs/README.md) | [Performance Schema·InnoDB·복제 진단](databases/mysql/operations.md) |
| Kafka | [KRaft Compose·로컬 실습](streaming/kafka/labs/local-lab.md) | [lag·ISR·request latency·장애 대응](streaming/kafka/operations.md) |
| NATS | [격리 서버·SDK](streaming/nats/labs/README.md) | [consumer·ACK·slow consumer·stream 상태](streaming/nats/operations.md) |
| OpenSearch | [단일 엔진·REST](search/opensearch/labs/README.md) | [shard·heap·rejection·검색/색인 지연](search/opensearch/operations.md) |
| Spark / Databricks | [실제 Spark](data-processing/spark/labs/README.md), [관리형 환경 준비](platforms/databricks/labs/README.md) | [Spark UI·skew·spill](data-processing/spark/operations.md), [query/job·권한·비용](platforms/databricks/operations.md) |
| Sentry / Supabase | [Sentry 준비](observability/sentry/labs/local-lab.md), [Supabase 준비](platforms/supabase/labs/local-lab.md) | [오류·trace·ingestion](observability/sentry/operations.md), [DB/pool·Auth/RLS·서비스별 오류](platforms/supabase/operations.md) |
| Terraform / Terragrunt | [격리 local CLI 환경](infrastructure/shared/environment.md) | [plan/state·lock·부분 적용](infrastructure/terraform/operations.md), [unit·dependency·실행 원장](infrastructure/terragrunt/operations.md) |
| OpenBao / Vault | [격리 dev 환경](security/shared/environment.md) | [OpenBao 상태·lease·audit](security/openbao/operations.md), [Vault health·권한·Raft](security/vault/operations.md) |
| MCP | [실제 SDK stdio](ai/mcp/labs/README.md) | [요청 지연·오류 층·timeout·권한 경계](ai/mcp/operations.md) |

각 트랙은 **제공된 실행 코드 / 직접 구성할 관측·장애 과제 / 실제 검증 이력**을 구분합니다. 이 표가 모든 제품의 exporter·dashboard·다중 노드·cloud 환경을 자동 제공한다는 뜻은 아닙니다. 실제 계정·비용·권한이 필요한 단계는 사용자가 선택한 허가된 환경에서만 진행하며, 기본 재편 작업이 환경을 자동 실행하거나 자원을 만들지 않습니다.

LLM 논문 트랙은 기존의 **CPU 기본 + GPU/API 선택 확장**을 유지합니다. 수학·알고리즘의 작은 재현과 실제 모델 학습/benchmark 재현을 구분합니다.

```text
python ai/llm-paper-lab/labs/lab.py --lab all
python -B -m unittest discover -s ai/llm-paper-lab/labs -p test_lab.py -v
```

제품별 기존 `offline_lab.py`와 테스트는 삭제하지 않습니다. [원리 모형의 역할](operations/README.md)에 따라 필요한 개념의 보조 자료로 사용하고, 테스트 PASS나 모형의 속도를 제품 운영 숙련도·실제 처리량으로 보고하지 않습니다.

## 저장소에 제공되는 것

- 단일 노드 PostgreSQL 18 및 ClickHouse 26.8 Compose 구성과 결정적으로 생성되는 합성 데이터
- Apache Kafka 4.3.1 단일 broker/controller KRaft Compose, 상태 관측 및 정확성 smoke 실습
- NATS 심화 과정, 고정 서버/SDK fixture와 운영 진단 지침, Core/JetStream 소스·Raft 원전·선택 원리 모형
- Sentry의 네트워크 없는 sampling 모델, Supabase의 18개 권한 기대 결과 fixture와 제품별 준비 지침
- LLM 핵심 논문 20편의 읽기·실험 지도, CPU 실험 6개와 단위 테스트, GPU/API 확장·재현 보고서 지침
- Spark/Databricks 실제 Spark 배치·스트리밍/Delta SQL fixture, UI·실행 계획·지연·비용 진단 지침과 선택 원리 모형
- Terraform/Terragrunt built-in 실제 테스트·로컬 2-unit 실습, plan/state·실행 로그·부분 실패 진단과 선택 원리 모형
- OpenSearch 단일 노드 Compose·REST fixture, shard/heap/검색 진단과 BM25/RRF/HNSW 논문·소스·선택 원리 모형
- MySQL 단일 노드 Compose·SQL fixture, Performance Schema/InnoDB 진단·소스·복구 연구와 선택 원리 모형
- OpenBao/Vault 격리 dev Compose·KV/ACL fixture, 제품별 health·lease·audit·Raft 진단·소스·선택 원리 모형
- MCP 공식 SDK stdio fixture, 요청·오류·timeout 진단·명세/SDK 소스·호환성·선택 원리 모형
- 기술별 커리큘럼, 원리·실험 강의, 소스 탐색 지도, 단계별 평가
- 기초 SQL 문제/답안, 읽기 전용 내부 상태 관찰 SQL
- 실험 기록 양식과 통합 연구 프로젝트 요구사항

복제 클러스터, Keeper, 다중 controller KRaft, CDC connector, Streams 애플리케이션, 부하 생성기, 디버그 빌드, 모니터링 스택은 심화 단계에서 학습자가 구성할 과제입니다. 현재 Compose를 실행하는 것만으로 이 구성들이 만들어지지는 않습니다. DB와 Kafka Compose 사이에도 네트워크·connector가 자동 연결되지는 않습니다. 문서에 기재한 기대 관찰값과 실행 계획은 실측 결과와 구분합니다.

Sentry/Supabase의 hosted와 self-hosted 기능·버전·운영 책임은 동일하지 않습니다. 소스 읽기 snapshot과 실제 실행 이미지·SDK·CLI 버전을 분리해 기록합니다. 클라우드 계정·프로젝트 생성, 외부 telemetry 전송, 원격 migration·배포는 자동 수행하지 않습니다. 합성 데이터만 사용하고 실제 토큰·사용자 payload·실습에서 생성한 secret은 커밋하지 않습니다. Compose의 공개 dummy 자격 증명은 폐기 가능한 로컬 fixture용이며 실제 인증 정보로 재사용하지 않습니다.

기존 `sql/00_setup.sql`~`02_solutions.sql`은 입문 진단 및 워밍업 자료로 유지합니다. 기존 볼륨에는 바뀐 초기 데이터가 자동 반영되지 않습니다. 보존·재초기화 절차는 [환경 안내](databases/shared/environment.md)에 있습니다.
