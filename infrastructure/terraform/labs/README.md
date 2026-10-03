# Terraform: CPU 모형에서 실제 로컬 plan/apply까지

[환경 준비](../../shared/environment.md) · [CPU 모형](../../shared/labs/README.md) · [실행 검증 기록](../../shared/validation.md)

실제 코드 [local/main.tf](local/main.tf)는 [공유 module](../../shared/modules/contract/main.tf)의 built-in `terraform_data` 3개만 사용합니다. `unit`과 `component["ingest"]`, `component["serve"]`의 주소·의존성을 관찰합니다. 외부 provider, cloud, provisioner는 없습니다.

## 1. init·검증·실제 테스트

공통 환경의 새 사본과 `$iacRun`, `$iacTerraform`을 준비한 PowerShell에서 **한 명령씩 실행하고 오류 때 중단**합니다.

```powershell
Set-Location -LiteralPath (Join-Path $iacRun 'infrastructure/terraform/labs/local')
& $iacTerraform init -input=false -no-color
& $iacTerraform validate -no-color
& $iacTerraform test -no-color
```

[테스트](local/tests/contract.tftest.hcl)는 ①apply 후 정확한 manifest·ID, ②변경 없는 plan의 ID 유지, ③잘못된 이름 거부의 3개 run입니다. 별도 test state를 사용하고 자기 합성 리소스를 teardown합니다. 실제 인프라가 있는 module의 `terraform test`를 안전한 정적 검사로 간주하지 않습니다. [공식 테스트](https://developer.hashicorp.com/terraform/language/tests).

## 2. 계획을 먼저 검토하고 적용

```powershell
& $iacTerraform plan -input=false -no-color -detailed-exitcode '-out=initial.tfplan'
$LASTEXITCODE
& $iacTerraform show -no-color initial.tfplan
```

`-detailed-exitcode`는 **0=변경 없음, 1=오류, 2=변경 있음**입니다. 최초 결과는 2이고 정확히 위 3개 `terraform_data`의 create만 있어야 합니다. backend는 이 사본의 local이어야 합니다. 다른 resource/provider, destroy, 예상 밖 입력이 있으면 적용하지 않습니다. PowerShell에서는 점이 포함된 `'-out=initial.tfplan'` 전체를 인용합니다.

검토가 끝났을 때만 아래를 실행합니다. saved plan 적용은 별도 확인창 없이 로컬 state를 변경합니다.

```powershell
& $iacTerraform apply -input=false -no-color initial.tfplan
& $iacTerraform output -json
& $iacTerraform plan -input=false -no-color -detailed-exitcode
$LASTEXITCODE
```

독립 정답: unit은 `{unit_name="terraform-lab", upstream_unit="none", revision=1}`이며 component는 ingest/capacity 1, serve/capacity 2이고 둘의 unit_name도 terraform-lab입니다. resource UUID는 가변이므로 literal로 고정하지 않습니다. 동일 configuration 재계획은 exit **0**이어야 합니다. 이 0이 cloud drift나 장애 복구까지 검증한 것은 아닙니다.

## 3. replacement와 unknown 전파 — 계획만

```powershell
& $iacTerraform plan -input=false -no-color -detailed-exitcode '-var=revision=2' '-out=replacement.tfplan'
& $iacTerraform show -no-color replacement.tfplan
```

예상: `unit`의 `triggers_replace` 때문에 replacement 하나, unit.output을 참조하는 두 component의 update가 계획됩니다. input의 unit_name이 unknown으로 바뀌는 이유를 graph로 설명합니다. `1 to add, 2 to change, 1 to destroy`는 리소스 4개의 교체가 아니라 replacement를 create/delete 각각에 포함한 표기입니다. 기본 실습은 이 계획을 적용하지 않습니다.

선택 추가 과제: 새 사본에서 component의 map key 변경과 capacity 변경을 비교하고 resource identity가 유지되는 조건을 입증합니다. `moved`, import, state migration, provider 오류·remote lock 경쟁은 별도 과제이며 제공 fixture가 자동 검증하지 않습니다.
