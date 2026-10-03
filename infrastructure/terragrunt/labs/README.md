# Terragrunt: 두 unit과 서로 다른 두 state

[환경 준비](../../shared/environment.md) · [CPU 모형](../../shared/labs/README.md) · [검증 기록](../../shared/validation.md)

[root.hcl](local/root.hcl)은 공통 입력·버전 제약이며 실행 unit이 아닙니다. [foundation](local/live/foundation/terragrunt.hcl) → [application](local/live/application/terragrunt.hcl)의 dependency를 사용합니다. 각 unit은 같은 built-in module로 합성 자원 3개를 만들지만 **state 파일과 lineage는 별개**입니다.

`remote_state`라는 block 이름에도 이 fixture의 backend는 **local**입니다. state 경로를 각 unit 디렉터리에 고정해 `.terragrunt-cache` 밖에 보존합니다. cache 삭제가 언제나 안전하다는 일반 보장은 아닙니다. backend가 cache 안을 가리키는 다른 설정이면 state까지 잃을 수 있습니다.

## 1. 초기 계획과 mock의 한계

공통 환경의 새 사본에서 실행합니다. Terraform 1.16.5·Terragrunt 1.1.6을 확인하고 기존 환경의 TG/TF override를 가져오지 않습니다.

```powershell
$iacTerragrunt = (Get-Command terragrunt -CommandType Application -ErrorAction Stop).Source
& $iacTerragrunt --version
$iacLive = Join-Path $iacRun 'infrastructure/terragrunt/labs/local/live'
Set-Location -LiteralPath $iacLive
& $iacTerragrunt hcl fmt --check
& $iacTerragrunt run --all --tf-path $iacTerraform --no-auto-provider-cache-dir -- plan -input=false -no-color -detailed-exitcode
$LASTEXITCODE
```

최초 aggregate exit는 **2**이고 각 unit에 3개 create가 계획됩니다. foundation은 아직 output이 없으므로 application의 upstream_unit은 **mock-foundation**입니다. 이것은 실제 foundation 계획의 미래 output이 아닙니다. 초기 mock 계획은 저장하거나 적용하지 않습니다. `--tf-path`로 Terraform을 명시하고 OpenTofu 자동 선택을 가정하지 않습니다.

`mock_outputs_allowed_terraform_commands`는 validate/plan에만 mock을 허용합니다. 별도 새 사본에서 foundation 없이 application을 apply하면 output 부재로 실패해야 합니다. 그러나 이 설정은 **과거 mock으로 생성한 saved plan의 내용까지 안전하게 바꾸는 장치가 아닙니다**. foundation 적용 후 반드시 application 계획을 새로 만듭니다.

## 2. foundation만 검토·적용

아래 각 단계의 오류 시 중단합니다. plan exit 2와 정확히 3개 built-in create, upstream_unit=none을 확인합니다.

```powershell
Set-Location -LiteralPath (Join-Path $iacLive 'foundation')
$iacPlan = Join-Path (Get-Location) 'reviewed.tfplan'
& $iacTerragrunt run --tf-path $iacTerraform --no-auto-provider-cache-dir -- plan -input=false -no-color -detailed-exitcode ("-out=" + $iacPlan)
& $iacTerraform show -no-color $iacPlan
```

검토한 뒤에만 saved plan을 적용합니다. 절대 plan 경로를 써서 Terragrunt의 cache 작업 디렉터리와 혼동하지 않습니다.

```powershell
& $iacTerragrunt run --tf-path $iacTerraform --no-auto-provider-cache-dir -- apply -input=false -no-color $iacPlan
& $iacTerragrunt run --tf-path $iacTerraform --no-auto-provider-cache-dir -- output -json
```

정답은 foundation, revision 1, upstream none, ingest 1, serve 2입니다. unit 디렉터리의 `terraform.tfstate`가 생기고 cache에만 보존된 상태가 아니어야 합니다.

## 3. application을 새로 계획·검토·적용

```powershell
Set-Location -LiteralPath (Join-Path $iacLive 'application')
$iacPlan = Join-Path (Get-Location) 'reviewed.tfplan'
& $iacTerragrunt run --tf-path $iacTerraform --no-auto-provider-cache-dir -- plan -input=false -no-color -detailed-exitcode ("-out=" + $iacPlan)
& $iacTerraform show -no-color $iacPlan
```

이번에는 정확히 3개 create, unit_name=application, **upstream_unit=foundation**이어야 합니다. mock-foundation이면 중단합니다. 앞 단계에서 만든 application 계획이 있다면 그것을 재사용하지 않습니다.

검토 후에만 다음을 실행합니다.

```powershell
& $iacTerragrunt run --tf-path $iacTerraform --no-auto-provider-cache-dir -- apply -input=false -no-color $iacPlan
& $iacTerragrunt run --tf-path $iacTerraform --no-auto-provider-cache-dir -- output -json
Set-Location -LiteralPath $iacLive
& $iacTerragrunt run --all --tf-path $iacTerraform --no-auto-provider-cache-dir -- plan -input=false -no-color -detailed-exitcode
$LASTEXITCODE
```

최종 두 unit의 변경 없음 aggregate exit는 0입니다. application의 capacity는 ingest 1/serve 2이고 upstream은 foundation입니다. 두 state lineage와 unit_id는 서로 달라야 합니다. state 분리는 접근 권한 분리나 여러 state 간 원자적 commit을 의미하지 않습니다.

## 실무로 일반화하면 안 되는 것

- 이 fixture는 `run --all apply/destroy`를 제공하지 않습니다. 해당 명령은 자동 `-auto-approve`와 실행 대상 확대에 주의해야 합니다. [공식 run 계약](https://docs.terragrunt.com/reference/cli/commands/run/).
- dependency는 현재 state output을 읽습니다. producer 계획만 바뀌었다고 consumer가 미래 output을 받아 계획하지 않습니다.
- 적용 중 downstream이 실패해도 앞 unit을 자동 rollback하지 않습니다. 재시도 전에 어느 state에 무엇이 반영됐는지 확인합니다.
- S3/GCS/Azure backend, 분산 lock, OIDC, cloud permission, remote module·provider cache 경쟁은 기본 실습의 미검증 확장입니다.
- 문법 검증·plan도 외부 설정의 hook/run_cmd/인증과 결합하면 명령·API 실행을 유발할 수 있습니다. 제공 fixture에는 그 기능을 넣지 않았습니다.
