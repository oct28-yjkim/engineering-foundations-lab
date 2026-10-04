# Terraform — 선언형 구성에서 변경 안전성·엔진 연구까지

HCL을 처음 읽는 단계에서 시작해 **어떤 주소의 객체가 왜 변경되는지, 실패 후 무엇이 남는지, 승인한 계획과 실행이 같은지**를 증명하는 28주·14모듈·약 336시간 과정입니다. 클라우드 리소스를 많이 생성하는 것이 아니라 값의 의미, 그래프, provider 계약, 상태의 권위와 복구 경계를 설명하는 능력을 기릅니다.

Terraform은 구성·관측 상태·provider를 연결하는 엔진입니다. [Terragrunt](../terragrunt/README.md)는 여러 root module의 실행·구성 재사용을 조정하는 별도 도구이며, Terraform의 resource graph와 Terragrunt의 unit graph는 같은 그래프가 아닙니다. OpenTofu도 별도 프로젝트이므로 한 도구의 통과 결과를 다른 도구로 자동 일반화하지 않습니다.

## 기본 LAB 입구

**정상 기능 → 동작 원리 → 관측 → 제약 → 진단·복구** 순서로 시작합니다. 실제 로컬 fixture의 plan→검토→apply→no-op를 먼저 익히고 입력·주소·state·오류를 연결합니다. [제품별 기본 LAB 카드](operations.md#basic-lab)에서 정상 결과·직접 볼 지표·자주 만나는 사건 2개·회복 검산과 환경 제공 범위를 확인합니다.

[공통 LAB 계약](../../operations/lab-contract.md)을 적용하며 **28주 심화 과정을 먼저 마칠 필요는 없습니다.** 실행 환경이나 수동 준비가 필요한 단계는 준비/미실행으로 구분하고, 아래 심화 커리큘럼은 기본 LAB 이후 필요한 부분부터 확장합니다.

## 시작 순서

1. Git diff·프로세스 환경 변수·JSON·파일 권한·HTTP 오류·DAG를 진단합니다. 처음이면 [공통 기초](../../databases/shared/foundations.md)의 OS·분산 실패 모델과 함께 보충합니다.
2. [Terraform 로컬 실습](labs/README.md)의 격리 조건을 확인하고 실제 CLI에서 정상 plan/state 기준선을 수집합니다.
3. [운영·트러블슈팅](operations.md)에서 계획 결과·lock·provider 지연·부분 실패를 진단하고 조치 전후를 비교합니다.
4. [28주 과정](curriculum.md), 7개 강의, [소스 지도](source-reading.md), [평가표](assessment.md)를 연결합니다.

[공통 원리 모형](../shared/labs/README.md)은 그래프·상태 원리를 보충하는 선택 부록입니다. 기본은 실제 CLI·실행 증거이며 CPU 모형이나 단위 테스트만으로 운영 실습을 완료하지 않습니다. CLI 준비가 안 됐다면 원리 학습/진단 설계로 기록하고 실측과 구분합니다.

## 고정 기준과 실습 경계

교재 기준은 **Terraform 1.16.5**, 태그 `v1.16.5`의 commit `ef47237fd0e03d6e93bdc510b526287f06e94c03`입니다. [공식 릴리스](https://github.com/hashicorp/terraform/releases/tag/v1.16.5)를 기준으로 하며, 이후 최신 버전이라는 주장은 하지 않습니다. Terraform 문서는 갱신될 수 있으므로 재현 보고서에는 실제 CLI·provider·module revision을 각각 기록합니다.

| 범위 | 증거 | 이 범위만으로 증명하지 못하는 것 |
| --- | --- | --- |
| OFFLINE | Python 표준 라이브러리의 작은 모형과 반례 | Terraform HCL 평가·실제 state lock·provider RPC |
| LOCAL-TERRAFORM | 제공 fixture의 실제 CLI 계획·로컬 상태·테스트 | AWS/GCP/Azure API 의미·원격 lock·IAM·비용 |
| SOURCE | 고정 Core 소스·단위 테스트·실패 경로 | 별도 provider 구현, HCP Terraform 관리 기능 |
| CLOUD-DESIGN / CLOUD-LAB | 격리 계정 설계 / 별도 승인한 실제 실측 | 설계만 제출하고 실제 권한·복구까지 통과했다는 주장 |

강의의 module migration, mock provider, CI, remote backend, fault injection은 **학습자가 추가 구현하는 과제**입니다. 제공 fixture가 28주 전체 실험을 자동 수행하지 않습니다. 기본 경로는 GPU·API key·클라우드 계정·유료 리소스를 요구하지 않습니다. CLI·provider를 자동 설치하거나 운영 상태를 수정하지 않습니다.

## 먼저 버려야 할 오해

- plan은 apply와 다르지만 보안 sandbox도, 무조건 무통신·무부작용인 순수 함수도 아닙니다. 초기화·provider·data source·외부 프로그램·ephemeral 동작을 먼저 검토합니다.
- `sensitive`는 표시 제어이며 state와 plan의 암호화가 아닙니다. 합성 비밀만 사용하고 산출물을 Git에 넣지 않습니다.
- `.terraform.lock.hcl`은 provider 선택·checksum 기록입니다. 동시 writer를 제어하는 backend state lock과 다릅니다.
- CLI workspace 이름은 인증·권한 경계가 아닙니다. 환경 분리는 backend와 실제 principal까지 검증합니다.
- apply는 여러 API 호출을 하나의 원자적 transaction으로 만들지 않습니다. state 복원 역시 데이터베이스·object·권한을 과거로 되돌리지 않습니다.

TF14는 작은 root module 한 개의 2주 연구입니다. 여러 환경·Terragrunt·배포 승인·장애 복구를 묶는 큰 과제는 별도 [8주 인프라 캡스톤](../../capstones/reproducible-infrastructure.md)으로 분리합니다.
