# Engineering Foundations Lab — Zero to Hero

데이터·AI 시스템을 사용하는 단계에서 출발해 **동작을 예측하고, 내부 구현을 추적하며, 장애와 성능 문제를 증거로 설명하는 엔지니어**로 성장하기 위한 한국어 교육 과정입니다. 현재 PostgreSQL, ClickHouse, Apache Kafka, Sentry, Supabase와 LLM 논문 실험 트랙을 제공합니다.

SQL 작성, 저장 구조, 실행 엔진, 동시성, 복구, 복제, 이벤트 스트리밍, 관측, 인증·인가, 성능 측정, 소스 코드 분석을 연결합니다. 가장 높은 단계의 완료 기준은 낯선 현상을 최소 재현으로 줄이고, 원인을 코드와 측정값으로 설명하며, 수정안의 회귀를 검증하는 것입니다.

## 시작할 곳

| 문서 | 역할 |
| --- | --- |
| [데이터베이스 교육 과정](databases/README.md) | 수준 진단, DB 전용 72주 경로, 통과 기준 |
| [이벤트 스트리밍 교육 과정](streaming/README.md) | Kafka 트랙과 세 기술 통합 100주 경로 |
| [공통 기초 8주](databases/shared/foundations.md) | SQL·자료구조·OS·확률·분산 시스템의 연결 |
| [PostgreSQL](databases/postgresql/README.md) | 14개 모듈, 저장·MVCC·planner·WAL·운영 |
| [ClickHouse](databases/clickhouse/README.md) | 14개 모듈, MergeTree·실행 pipeline·집계·분산 |
| [Apache Kafka](streaming/kafka/README.md) | 14개 모듈, log·producer·consumer·KRaft·transaction·Streams·Connect |
| [Sentry](observability/sentry/README.md) | 14개 모듈, SDK·ingestion·grouping·tracing·sampling·개인정보·운영 |
| [Supabase](platforms/supabase/README.md) | 14개 모듈, PostgreSQL·Auth/JWT·RLS·Realtime·Storage·Functions·복구 |
| [LLM 논문 실험](ai/llm-paper-lab/README.md) | 핵심 논문 20편·14모듈, CPU 실험 6개와 GPU/API 선택 확장 |
| [실험 방법](databases/shared/experiment-method.md) | 재현성, 측정 오차, 정확성 oracle, 반증 |
| [통합 연구 8주](databases/shared/capstone.md) | PostgreSQL → Kafka → ClickHouse, CDC·복구·설계 검증 |
| [보안·관측 앱 연구 8주](capstones/secure-observable-app.md) | Supabase + Sentry, 테넌트 격리·privacy·장애·전체 상태 복구 |
| [환경과 실행 범위](databases/shared/environment.md) | 실행 명령, 버전 고정, 제공/미제공 환경 |

## 시간 계획

데이터베이스 두 트랙은 공통 기반 8주 + PostgreSQL 28주 + ClickHouse 28주 + 통합 연구 8주, 총 **72주·약 864시간**입니다. Kafka까지 순차로 포함하면 공통 기반 8주 + PostgreSQL 28주 + Kafka 28주 + ClickHouse 28주 + 통합 연구 8주, 총 **100주·약 1,200시간**을 기준으로 합니다. 공통 기반과 통합 연구는 한 번만 이수합니다.

주 12시간 가정이며 기간은 보장치가 아닙니다. 이미 익힌 내용은 진단 과제를 통과하면 줄이고, 복구·분산 실험에 실패하면 해당 모듈을 반복합니다.

Sentry와 Supabase도 각각 **28주·14모듈·약 336시간**의 선택 트랙입니다. 백엔드·보안·관측이 우선이면 PostgreSQL → Supabase → Sentry → 보안·관측 앱 연구를 선택할 수 있습니다. 이 3트랙 경로도 공통 8주 + 트랙 84주 + 선택한 캡스톤 8주 = 100주입니다. 두 종류의 통합 연구를 모두 필수로 더하지 않습니다. 다섯 제품 트랙을 모두 순차 이수하는 경우에만 공통 8주 + 140주 + 선택 캡스톤 8주 = **156주·약 1,872시간**입니다. 모든 트랙을 끝내야 실무에 적용할 수 있다는 뜻은 아닙니다.

LLM 논문 실험은 별도의 **28주·336시간 선택 트랙**입니다. [논문 20편](ai/llm-paper-lab/papers.md)을 원리·구현·평가와 연결하며 CPU 오프라인부터 시작합니다. 기존 156주 경로에 자동으로 더하지 않으며 GPU/API는 필요할 때만 확장합니다. 행렬·미분·확률·Python은 별도 선수 지식입니다.

기술 한 개에 집중하는 경우 공통 기반 8주와 해당 트랙 28주를 먼저 진행합니다. 소스 빌드, 별도 복제 환경 구성, 실제 업무 경험을 더하면 기간이 늘어날 수 있습니다. 숙련도는 자료를 읽은 횟수보다 재현 가능한 결과물로 평가합니다.

## 첫 실습

실행 중인 Docker Desktop의 Linux 컨테이너 엔진과 Docker Compose v2가 필요합니다. 저장소 루트에서 실행합니다. 아래 명령은 PowerShell과 Bash 모두에서 한 줄씩 사용할 수 있습니다.

```text
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose exec postgres psql -X -v ON_ERROR_STOP=1 -U lab -d lab
```

PostgreSQL 안에서 `SELECT version();`과 `SELECT count(*) FROM commerce.orders;`를 확인하고 `\q`로 나옵니다. ClickHouse는 다음 명령으로 접속합니다.

```text
docker compose exec clickhouse clickhouse-client --user lab --password lab_password --database lab
```

`SELECT version();`과 `SELECT count() FROM lab.events;`를 확인합니다. 상세 절차와 SQL 파일 실행은 [환경 안내](databases/shared/environment.md)를 따릅니다.

Kafka는 별도 Compose 프로젝트로 실행합니다. DB volume과 수명 주기를 분리하며, Kafka만 공부할 때는 위의 DB 시작 명령이 필요하지 않습니다.

```text
docker compose -f streaming/kafka/compose.yaml config --quiet
docker compose -f streaming/kafka/compose.yaml up -d --wait
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/00-inspect.sh
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/01-smoke.sh
```

Smoke 실습은 매번 새 학습용 topic을 만들고 기록·조회 결과를 검사합니다. 보존 데이터와 실행 범위는 [Kafka 로컬 실습](streaming/kafka/labs/local-lab.md)을 확인합니다. 컨테이너가 정상이라는 것과 복제·exactly-once가 검증됐다는 것은 다릅니다.

Sentry는 외부 계정 없이 [오프라인 sampling 실험](observability/sentry/labs/local-lab.md)부터 시작할 수 있습니다. 이것은 SDK나 서버 실행이 아닌 원리 검증입니다.

```text
node observability/sentry/labs/sampling-oracle.mjs
```

Supabase는 [CLI local 준비와 권한 oracle](platforms/supabase/labs/local-lab.md)을 먼저 봅니다. 루트 PostgreSQL 컨테이너가 Supabase Auth·API·RLS 앱 전체를 제공하는 것은 아닙니다. 두 과정의 SDK 앱·제품 스택은 별도 구성 과제이며 기존 Compose를 바꾸지 않았습니다.

LLM 논문 실험은 Python 3.10 이상으로 시작합니다. 별도 패키지·모델 다운로드·GPU·API 키·Docker가 필요하지 않습니다.

```text
python ai/llm-paper-lab/labs/lab.py --lab all
python -B -m unittest discover -s ai/llm-paper-lab/labs -p test_lab.py -v
```

이는 Attention·LoRA·DPO·KV cache·검색·평가의 **합성 CPU 모형**입니다. 실제 LLM 학습이나 논문 benchmark 재현과는 다릅니다. [실습 범위](ai/llm-paper-lab/labs/README.md)와 [환경 안내](ai/llm-paper-lab/environment.md)를 먼저 확인합니다.

## 저장소에 제공되는 것

- 단일 노드 PostgreSQL 18 및 ClickHouse 26.8 Compose 구성과 결정적으로 생성되는 합성 데이터
- Apache Kafka 4.3.1 단일 broker/controller KRaft Compose, 상태 관측 및 정확성 smoke 실습
- Sentry의 네트워크 없는 sampling 모델, Supabase의 18개 권한 기대 결과 fixture와 제품별 준비 지침
- LLM 핵심 논문 20편의 읽기·실험 지도, CPU 실험 6개와 단위 테스트, GPU/API 확장·재현 보고서 지침
- 기술별 커리큘럼, 원리·실험 강의, 소스 탐색 지도, 단계별 평가
- 기초 SQL 문제/답안, 읽기 전용 내부 상태 관찰 SQL
- 실험 기록 양식과 통합 연구 프로젝트 요구사항

복제 클러스터, Keeper, 다중 controller KRaft, CDC connector, Streams 애플리케이션, 부하 생성기, 디버그 빌드, 모니터링 스택은 심화 단계에서 학습자가 구성할 과제입니다. 현재 Compose를 실행하는 것만으로 이 구성들이 만들어지지는 않습니다. DB와 Kafka Compose 사이에도 네트워크·connector가 자동 연결되지는 않습니다. 문서에 기재한 기대 관찰값과 실행 계획은 실측 결과와 구분합니다.

Sentry/Supabase의 hosted와 self-hosted 기능·버전·운영 책임은 동일하지 않습니다. 소스 읽기 snapshot과 실제 실행 이미지·SDK·CLI 버전을 분리해 기록합니다. 클라우드 계정·프로젝트 생성, 외부 telemetry 전송, 원격 migration·배포는 자동 수행하지 않습니다. 합성 데이터만 사용하고 토큰·사용자 payload·실습용 secret은 커밋하지 않습니다.

기존 `sql/00_setup.sql`~`02_solutions.sql`은 입문 진단 및 워밍업 자료로 유지합니다. 기존 볼륨에는 바뀐 초기 데이터가 자동 반영되지 않습니다. 보존·재초기화 절차는 [환경 안내](databases/shared/environment.md)에 있습니다.
