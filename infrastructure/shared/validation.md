# Terraform·Terragrunt 실습 검증 기록

검증일: **2026-10-04**, Windows amd64, CPython 3.12.14, Terraform **1.16.5**, Terragrunt **1.1.6**. 아래는 실제 수행한 검사다. 학습자가 추가 수행할 cloud·분산 장애 과제와 구분한다.

## 도구와 실행 경계

공식 HTTPS release asset을 저장소의 ignored `lab-workspaces/iac-tools-20261004`에 다운로드하고 같은 공식 배포 경로의 SHA256SUMS와 대조했다. 시스템 설치나 PATH 변경은 하지 않았다. 이는 checksum 대조이며 별도의 서명 검증을 완료했다는 주장은 아니다.

| 배포 artifact | SHA-256 |
| --- | --- |
| `terraform_1.16.5_windows_amd64.zip` | `01700102b7291f95c0ab61394b55bfd5f57a12ac65632c2c1958691c8cf438ef` |
| `terragrunt_windows_amd64.exe` v1.1.6 | `609c60fbc334867cad90146cd0297ea80c19d711a81ae4690570082195f66afe` |

실제 CLI는 새 전용 `lab-workspaces/iac-native-20261004` 사본에서 실행했다. backend는 local, provider는 Terraform built-in뿐이다. 검증 파일과 실행 산출물은 분리했다. cloud account·원격 backend·과금 리소스·외부 provider·provisioner·hook을 생성하거나 실행하지 않았다.

## 결과

| 검사 | 결과 | 입증한 범위 |
| --- | --- | --- |
| CPU 모형 `--lab all` | 4개 PASS | graph·합성 plan-policy·메모리 CAS·영향 집합의 literal oracle |
| Python unittest | **82개 PASS** | 정상·오류·불변성·모형 경계 |
| 동일 suite의 `python -O` | **82개 PASS** | 핵심 검사가 최적화로 제거되지 않음 |
| Python 3.10 문법 AST 파싱 | 2파일 PASS | 실제 Python 3.10 runtime 검증은 아님 |
| Terraform fmt·init·validate | PASS | HCL 형식·local backend·built-in provider 구성 |
| Terraform native test | **3 runs PASS** | 실제 합성 apply와 exact manifest, ID 유지 plan, 잘못된 이름 거부 |
| Terraform 초기 saved plan | exit 2, 검토 PASS | terraform_data create 정확히 3개만 허용 |
| 그 plan의 실제 apply | PASS | 합성 manifest·capacity·unit binding 정합 |
| 변경 없는 후속 plan | exit **0** | 같은 코드/입력과 로컬 state의 no-op |
| revision=2 변경 plan | exit 2 | unit replacement 1개 + component update 2개; **적용하지 않음** |
| Terragrunt hcl fmt | PASS | 제공 HCL의 형식 검사 |
| 초기 `run --all ... plan` | aggregate exit **2** | 두 unit의 DAG 실행, 아직 없는 foundation output을 plan-only mock으로 대체 |
| foundation 전 application apply | 예상 실패·application state 없음 | output 부재, apply에서 mock 사용 불가 |
| foundation 단위별 saved plan 적용 | PASS | create 3개 검토 후 합성 local state 생성 |
| 실제 output으로 application 재계획·적용 | PASS | upstream_unit=foundation, create 3개, 정확한 component 값 |
| 두 unit 최종 `run --all ... plan` | aggregate exit **0** | 두 state의 변경 없음; lineage와 unit_id 서로 다름 |
| 기존 Spark·LLM 회귀 테스트 | 70개 + 50개 PASS | 기존 CPU/정적·mock 테스트의 회귀 확인; 실제 Spark 엔진 미실행 |
| 문서 링크·anchor·fence 검사 | 148문서·848내부 링크·오류 0 | 실제 CLI 실행이나 외부 URL 가용성 검증을 대신하지 않음 |

초기 PowerShell 호출에서 인용하지 않은 `-out=initial.tfplan` 인자가 잘못 전달되어 명령이 실패했다. 파일 이름을 포함한 인자 전체를 인용해 수정한 뒤 재실행했다. 문서의 PowerShell 예제에도 그 형식을 사용한다. 실패한 명령을 통과 개수에 포함하지 않았다.

## 아직 입증하지 않은 것

- 실제 AWS/GCP/Azure provider API, OIDC/IAM 격리, 원격 backend의 동시 lock·lease·복구.
- cloud drift, API timeout 뒤 부분 생성, rate limit·quota·비용 상한, 실제 remote object import/migration.
- Terraform Core/Terragrunt upstream Go 빌드·테스트. 고정 source 경로 확인은 실행 검증이 아니다.
- 여러 unit을 묶는 원자적 rollback, mock 기반 saved plan의 자동 안전성, 모든 command/filter/stack/cache 조합.
- 다른 OS·CLI 버전·외부 provider·실제 운영 데이터에서의 동등한 결과.

실행 방법은 [공통 환경](environment.md), [Terraform](../terraform/labs/README.md), [Terragrunt](../terragrunt/labs/README.md)에 있다. 생성된 로컬 state·계획·binary는 Git에 넣지 않고 보존했다. 재실행은 새 사본에서 시작하며 기존 결과를 자동 삭제하지 않는다.
