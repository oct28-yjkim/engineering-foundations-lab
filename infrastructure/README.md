# Infrastructure Engineering Lab

인프라를 선언하는 문법에서 시작해 **계획·실행·state·권한·실패 복구의 경계**를 설명하고 검증합니다. Terraform의 리소스 관리와 Terragrunt의 여러 unit 운영을 별도 계층으로 학습합니다.

| 경로 | 학습 범위 |
| --- | --- |
| [Terraform](terraform/README.md) | 28주·14모듈·7강: HCL/unknown, graph, provider, plan/apply, state, 모듈, 테스트·복구 |
| [Terragrunt](terragrunt/README.md) | 28주·14모듈·7강: include, unit/stack, dependency, 실행 순서, cache/backend, CI·부분 실패 |
| [CPU 원리 실험](shared/labs/README.md) | Python 표준 라이브러리로 graph·plan-policy·state-CAS·변경 영향 범위 검증 |
| [실제 CLI 환경](shared/environment.md) | Terraform 1.16.5·Terragrunt 1.1.6, built-in provider만 쓰는 로컬 실습 |
| [통합 연구 8주](../capstones/reproducible-infrastructure.md) | 변경 승인·부분 적용·state 소유권·복구·재현성 |

Terraform부터 시작하고 Terragrunt가 그 위에 추가하는 실행·설정 경계를 학습합니다. 두 과정은 각각 주 12시간 가정의 약 336시간이며, 순차 56주에 공통 기초와 선택 캡스톤이 자동 포함되지는 않습니다. 이전 제품 트랙의 전체 학습 기간에도 자동 가산하지 않습니다.

**CPU 모형 / 실제 로컬 CLI / 승인된 cloud / 설계만 수행**을 구분합니다. 로컬 state가 정확한 것과 실제 IAM, S3/GCS/Azure backend 잠금, provider API 재시도, 과금 자원 복구가 올바른 것은 별개입니다. 기본 경로는 cloud 계정·credential·GPU·외부 provider가 필요 없습니다.

Databricks workspace·Kafka·DB·LLM serving 인프라는 선택 확장입니다. 기존 [Spark/Databricks](../data-processing/README.md), [Kafka](../streaming/kafka/README.md), [LLM 논문](../ai/llm-paper-lab/README.md)의 서비스 정답·권한 검증을 인프라 `apply` 성공으로 대체하지 않습니다.
