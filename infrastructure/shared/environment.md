# IaC 실습 환경과 변경 범위

기본 [CPU 모형](labs/README.md)은 Python 3.10+ 표준 라이브러리만 사용합니다. 아래는 선택적인 **실제 CLI** 경로입니다. 합성 `terraform_data`와 로컬 state만 사용하며 AWS/GCP/Azure 계정·backend·원격 리소스는 만들지 않습니다. 다른 module/provider/hook을 추가하면 이 안전 범위는 더 이상 성립하지 않습니다.

## 고정 기준

- Terraform **1.16.5**: [공식 release](https://github.com/hashicorp/terraform/releases/tag/v1.16.5), [공식 설치](https://developer.hashicorp.com/terraform/install).
- Terragrunt **1.1.6**: [공식 release](https://github.com/gruntwork-io/terragrunt/releases/tag/v1.1.6), [공식 설치](https://docs.terragrunt.com/getting-started/install/).
- 실습에는 built-in `terraform_data`만 있습니다. 외부 provider/module registry에서 package를 가져오지 않습니다. [공식 리소스 계약](https://developer.hashicorp.com/terraform/language/resources/terraform-data).
- 최신이라는 표현 대신 실행한 정확한 CLI·OS·arch·source commit·checksum을 기록합니다. OpenTofu를 자동 대체하지 않습니다.

학습자가 CLI 설치를 선택할 때는 공식 배포 경로와 해당 OS/arch의 checksum·조직 서명 검증 정책을 따릅니다. 설치/다운로드는 Python 실험의 선행 조건이 아닙니다. 작성 시에는 공식 HTTPS 배포 파일과 SHA256SUMS를 대조한 portable Windows 실행 파일을 전용 ignored 폴더에서 사용했고 시스템 PATH는 바꾸지 않았습니다. [검증 기록](validation.md).

## 새 실습 사본 만들기 — PowerShell

**저장소 루트의 새 전용 터미널**에서 시작합니다. HEAD에 저장된 검토한 소스만 복사합니다. 아직 커밋하지 않은 편집 내용은 포함되지 않습니다. 기존 state/cache/secret을 재귀 복사하지 않도록 `git archive`를 사용합니다.

```powershell
$iacRepo = (Get-Location).Path
$iacAmbient = @(Get-ChildItem Env: | Where-Object { $_.Name -match '^(TF_|TG_|TERRAGRUNT_)' })
if ($iacAmbient.Count) { throw '기존 TF_/TG_/TERRAGRUNT_ 설정이 없는 전용 셸을 사용하세요.' }
$iacRun = Join-Path $iacRepo ('lab-workspaces/iac-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $iacRun -ErrorAction Stop | Out-Null
$iacArchive = Join-Path $iacRun 'source.zip'
git archive --format=zip ("--output=" + $iacArchive) HEAD infrastructure
if ($LASTEXITCODE -ne 0) { throw '소스 archive 실패: 다음 단계로 진행하지 마세요.' }
Expand-Archive -LiteralPath $iacArchive -DestinationPath $iacRun -ErrorAction Stop
$env:TF_CLI_CONFIG_FILE = Join-Path $iacRun 'infrastructure/shared/terraform.rc'
$env:CHECKPOINT_DISABLE = '1'
$env:TF_INPUT = '0'
$iacTerraform = (Get-Command terraform -CommandType Application -ErrorAction Stop).Source
& $iacTerraform version
```

출력이 Terraform 1.16.5가 아니면 멈춥니다. Terragrunt 실습 때만 `Get-Command terragrunt`로 1.1.6의 실제 경로를 추가로 선택합니다. PATH 없는 portable 실행 파일은 검증한 절대 경로를 `$iacTerraform`/`$iacTerragrunt`에 지정합니다. 환경 설정은 이 터미널에 한정하며 터미널을 닫으면 부모 프로세스에 반영되지 않습니다. 기존 셸 설정을 임의 삭제하지 않습니다.

POSIX 환경에서는 새 전용 경로에 `git archive HEAD infrastructure`의 내용을 풀고 `TF_CLI_CONFIG_FILE`을 그 사본의 `infrastructure/shared/terraform.rc`로 설정합니다. 경로·환경 격리를 확인한 후 아래 트랙별 CLI 순서를 수행합니다. Windows에서 검증한 결과를 다른 OS에서 이미 통과했다고 기록하지 않습니다.

## 어느 명령까지 무엇을 바꾸는가

| 작업 | 이 fixture의 변경 | 일반 구성에서의 추가 위험 |
| --- | --- | --- |
| Python 원리 모형 | 메모리의 합성 값만 계산 | 실제 backend/정책 엔진으로 사용하지 않음 |
| init/validate/plan | 사본의 metadata·cache·계획 파일; state 읽기·잠금 가능 | backend 초기화, provider 실행, data source, hook, 외부 API 가능 |
| Terraform test | 별도 test state로 built-in 자원 생성·정리 | 기본 apply 실행, 실제 cloud 자원 생성/삭제 가능 |
| 단위별 saved-plan apply | 지정된 사본의 로컬 state에 합성 자원 기록 | 확인창 없이 적용; 다른 provider에서는 실제 인프라 변경 |
| state/plan/output JSON 열람 | 합성 fixture 값 읽기 | sensitive 값이 포함될 수 있어 로그/공유에 부적절 |

`plan`이나 HCL 검증이라는 이름만으로 무부작용이라고 가정하지 않습니다. 제공 파일에는 provisioner, hook, `run_cmd`, external data, cloud provider가 없습니다. 검토하지 않은 설정에 본 안내의 명령을 재사용하지 않습니다.

## 상태·비밀·정리

`.tfstate`, backup, plan, `.terraform`, `.terragrunt-cache`, `.tfvars`는 Git에서 제외합니다. provider 선택을 기록하는 `.terraform.lock.hcl`은 제외하지 않습니다. 이 fixture는 built-in provider뿐이므로 외부 provider 잠금 항목이 없는 것이 정상입니다. `.gitignore`는 비밀 암호화나 이미 추적된 파일 제거 기능이 아닙니다.

이 실습은 자동 `destroy`, 강제 unlock, state push 또는 state migration을 수행하지 않습니다. 결과와 코드·CLI 지문을 보존한 뒤 **본인이 생성한 정확한 사본**만 정리합니다. state 삭제를 실제 cloud 자원 삭제와 혼동하지 않습니다. 테스트가 자신의 합성 자원을 teardown하는 것과 사용자의 기존 state 삭제는 다릅니다.

[Terraform 순서](../terraform/labs/README.md) · [Terragrunt 순서](../terragrunt/labs/README.md)
