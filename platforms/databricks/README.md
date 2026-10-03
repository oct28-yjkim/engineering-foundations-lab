# Databricks Engineering Lab

Databricks를 notebook 실행 화면이 아니라 **Spark 실행계층·Delta table protocol·권한·작업 배포·클라우드 운영이 만나는 플랫폼**으로 학습합니다. “결과가 나왔다”와 “올바른 사용자에게, 재시도해도 같은 업무 결과를, 복구 가능한 비용으로 제공한다”를 구분합니다. 14모듈 × 2주, 주12시간의 명목 **28주·336시간** 과정이며 전문가 인증이나 운영 안전성 보증은 아닙니다.

## 어디서 시작하는가

1. [커리큘럼](curriculum.md)에서 부족한 경계를 고릅니다. SQL·Python·트랜잭션·기본 분산 시스템이 선수 지식입니다.
2. [Spark 트랙](../../data-processing/spark/README.md)에서 execution plan, shuffle, partition, Structured Streaming의 원리를 보충합니다. 전체 과정을 먼저 마칠 필요는 없습니다.
3. [운영 관측·트러블슈팅](operations.md)에서 Query History/Profile·Jobs·compute metrics·pipeline freshness를 읽습니다. [실습 안내](labs/README.md)의 권한·비용 경계를 먼저 확인하며 로컬 Spark/모형으로 managed 검증을 대체하지 않습니다.
4. [소스와 논문](source-reading.md)을 따라 설명을 구현·측정 가능한 가설로 바꾸고 [평가](assessment.md)에서 반증합니다.

| 강의 | 모듈 | 끝나면 답해야 하는 질문 |
| --- | --- | --- |
| [Lakehouse와 실행 환경](lessons/01-lakehouse-runtime.md) | D01–02 | OSS Spark, DBR, SQL warehouse, Photon, control plane의 책임은 어떻게 다른가? |
| [Delta 트랜잭션](lessons/02-delta-transactions.md) | D03–04 | 파일이 이미 존재해도 언제 table에 보이지 않으며, 재시도·MERGE·보존기간은 어떤 오류를 만드는가? |
| [Unity Catalog와 저장소 경계](lessons/03-unity-catalog.md) | D05–06 | SQL 권한이 안전해도 직접 object access가 우회 경로가 될 수 있는가? |
| [수집·스트리밍](lessons/04-ingestion-streaming.md) | D07–08 | 파일 1회 발견, event 1회 적용, 외부 효과 1회가 왜 다른가? |
| [성능과 비용](lessons/05-performance-cost.md) | D09–10 | 더 빠른 쿼리가 더 싼가? 캐시·파일 배치·Photon을 어떻게 분리 측정하는가? |
| [배포·복구](lessons/06-delivery-recovery.md) | D11–12 | 배포자와 실행자는 누구이며, table history 외에 무엇을 복원해야 하는가? |
| [연구·미니 캡스톤](lessons/07-research-capstone.md) | D13–14 | 논문의 주장을 실제 환경의 작은 반례와 검증 가능한 변경으로 바꿀 수 있는가? |

## 실행 범위와 용어

- **CPU-MODEL, 선택 부록**: 필요할 때만 작은 입력과 독립 정답으로 원리를 보충합니다. 선수 과정·수료 조건이 아니며 실제 Delta protocol 또는 UC 집행의 검증이라고 하지 않습니다.
- **LOCAL-SPARK / LOCAL-DELTA**: 학습자가 고정한 Java/Python/Spark와 호환 Delta 의존성을 설치한 뒤 실행합니다. Delta 확장은 별도 준비가 필요하며 설치·다운로드를 자동 수행하지 않습니다.
- **MANAGED-OPTIONAL**: 승인된 비운영 workspace, synthetic data, 사용 상한·중지 책임을 정한 뒤에만 수행하는 실제 Databricks 과제입니다. 계정이 없으면 설계로 남기고 실행 gate는 미완료입니다.
- **DESIGN**: IAM·network·region outage·관리형 내부 구현처럼 로컬에서 입증할 수 없는 범위를 문서와 tabletop으로 분석합니다.

2026-10-04에 확인한 공식 문서는 Lakeflow pipelines / Spark Declarative Pipelines와 **Declarative Automation Bundles**라는 이름을 사용합니다. 이전 자료의 Delta Live Tables·Databricks Asset Bundles 명칭은 제품 이력을 설명할 때만 병기합니다. OSS Spark Declarative Pipelines와 Databricks의 관리형 확장도 같은 기능 집합으로 취급하지 않습니다. [공식 파이프라인 안내](https://docs.databricks.com/aws/en/getting-started/data-pipeline-get-started), [Bundles 안내](https://docs.databricks.com/aws/en/dev-tools/bundles/work-tasks)

공식 링크의 AWS 경로는 **AWS 문서 기준 예시**입니다. Azure/GCP에서는 identity·network·storage URI·기능 제공 region·제품 상태를 해당 cloud 문서와 실제 계정으로 재확인합니다. 특정 DBR이 이 저장소의 로컬 Spark와 같은 버전이라고 추정하지 않습니다. DBR release, compute type/access mode, serverless environment version, Spark/Python/Delta, Photon, UC, cloud/region, CLI·bundle engine을 실행 지문으로 남깁니다. managed 내부 SHA는 확인할 수 없으면 unknown입니다.

## 안전·완료 계약

실데이터·운영 bucket·공유 catalog·관리자 토큰을 사용하지 않습니다. notebook 출력, event log, query profile, query text에도 개인정보와 credential이 들어갈 수 있으므로 공유 전 정제합니다. cloud account 생성, workspace 배포, 외부 전송, 비용 발생 실행은 이 문서를 읽거나 로컬 테스트를 돌리는 것만으로 수행되지 않습니다.

`VACUUM` 보존기간 단축, retention safety 해제, table/bundle 파괴, 기존 checkpoint 삭제를 기본 실습으로 제공하지 않습니다. time travel·RESTORE·shallow clone은 독립 backup이 아닙니다. 성능은 정답 일치 후 같은 조건의 최소20개 반복/구간과 raw data로 비교합니다. 판정은 정확성25·원리/소스25·실험/반증25·운영/재현성25, 총80 이상·각15 이상 및 필수 gate 통과입니다. 실행하지 않은 관리형 기능은 CPU 실험 성공으로 대체하지 않습니다.
