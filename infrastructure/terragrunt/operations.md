# Terragrunt 운영 실습: 실패한 unit과 실행되지 않은 unit을 구분하기

[실제 두-unit 실습](labs/README.md)과 [격리 환경](../shared/environment.md)을 먼저 준비합니다. 기준 **Terragrunt 1.1.6 / Terraform 1.16.5**, local backend·built-in module입니다. CLI orchestration은 broker처럼 상시 CPU dashboard를 보는 대신 **선택·시작·완료 집합, unit별 시간, dependency 실패, state 소유권**을 관측합니다.

<a id="basic-lab"></a>

## 기본 LAB: 정상 동작에서 장애 복구까지

**정상 기능 → 동작 원리 → 관측 → 제약 → 진단·복구** 순서의 입문 카드입니다. foundation/application 두 unit의 정상 의존성과 no-op부터 익힌 뒤 mock·입력·실행/미실행을 구분합니다. [공통 LAB 계약](../../operations/lab-contract.md)에 따라 정상 결과를 먼저 검산한 뒤 아래 상세 절차로 진행합니다. 28주 심화는 선수 조건이 아니며, 이 카드 추가가 새 자동 실행기 제공이나 실제 장애 검증 완료를 뜻하지 않습니다.

| 단계 | 실행·관측·판정 |
| --- | --- |
| 정상 기능부터 | [실제 두-unit 실습](labs/README.md)의 새 ignored 사본에서 각 unit의 계획을 검토하고 순서대로 적용합니다. foundation의 실제 output을 application이 참조하는지 확인하고 두 state/ID·전체 no-op=0를 기록합니다. |
| 동작 원리 | include/inputs 평가→dependency outputs→실행 큐→unit별 state를 연결합니다. mock 기반 plan은 실제 upstream 배포 성공이 아니며 여러 state는 하나의 전역 transaction이 아닙니다. |
| 직접 볼 지표·방법 | 아래 `run --all ... plan`의 summary·unit 로그에서 intended/selected/started/success/failure를 이름까지 대조합니다. 지원되는 버전에서만 Run Report를 사용하고 duration·Reason/Cause·upstream 값·state identity를 확인합니다. |
| 먼저 확인할 제약 | local backend/built-in 두 unit만 제공됩니다. HCL hook/run_cmd/source/backend에는 추가 효과가 있을 수 있습니다. `run --all apply/destroy`는 입문 명령이 아니며 plan 2·제외·upstream 때문에 미실행을 모두 실패로 합치지 않습니다. |
| 자주 마주치는 사건 2개 | 아래 기본 사건 1: 미적용 새 사본의 `mock-foundation` plan과 foundation 적용 후 실제 output plan을 비교합니다. 사건 2: 정상 완료한 별도 새 사본에서 application 입력만 validation 위반으로 바꾸고 foundation 결과·application 오류·aggregate를 구분합니다. |
| 조치와 회복 oracle | 오래된 mock plan은 적용하지 않고 실제 output을 읽은 새 plan을 검토합니다. 잘못된 input을 원복하여 두 unit no-op=0·기존 ID/값 유지·실행 대상 일치를 확인합니다. 이 plan 오류를 부분 apply 장애로 보고하지 않습니다. |
| 제공물·추가 준비 | fixture·CLI 준비·아래 수동 절차를 제공하며 report/로그 수집은 버전 지원을 먼저 확인합니다. backend 경쟁·hook 부작용·원격 provider/부분 apply는 추가 LAB이고 28주 심화는 기본 LAB의 선수 조건이 아닙니다. |

두 사건의 결과가 예상과 다르면 관측한 상태를 기록하고 발생기/변경부터 멈춥니다. 정상 baseline·사건별 경쟁 가설·제한 조치·회복 oracle·미실행 범위를 [사건 보고서](../../operations/incident-report-template.md)에 남깁니다.

## 기준선·관측

이미 검토한 새 fixture에서 `$iacTerragrunt`, `$iacTerraform`, `$iacLive`를 준비하고 두 unit을 정상 완료한 후 실행합니다. 일반 HCL의 hook/run_cmd/source/backend에는 추가 효과가 있으므로 다른 저장소에 복사해 실행하지 않습니다.

```powershell
Set-Location -LiteralPath $iacLive
& $iacTerragrunt --version
& $iacTerragrunt run --help
& $iacTerragrunt run --all --tf-path $iacTerraform --no-auto-provider-cache-dir -- plan -input=false -no-color -detailed-exitcode
$iacAggregateExit = $LASTEXITCODE
```

예상 정상은 foundation/application 두 unit 모두 no-op, aggregate 0입니다. 초기 미배포 상태의 plan 2와 오류를 구분합니다. run summary와 각 unit 로그를 함께 기록하며 전체 exit 하나로 어떤 unit이 실패했는지 추정하지 않습니다.

공식 [Run Report](https://docs.terragrunt.com/features/stacks/run-report/)의 summary/per-unit duration·JSON report 기능은 설치한 고정 버전 `run --help`에서 지원 여부를 확인한 후 사용합니다. 지원된다면 같은 허가된 fixture에서 아래처럼 **저장소가 아닌 해당 ignored 사본**에 새 report를 저장합니다. report 이름은 매번 새로 만들고 다른 실행 결과를 덮어쓰지 않습니다.

```powershell
$iacReport = Join-Path $iacLive ('run-' + [guid]::NewGuid().ToString('N') + '.json')
& $iacTerragrunt run --all --tf-path $iacTerraform --no-auto-provider-cache-dir --report-file $iacReport --report-format json -- plan -input=false -no-color -detailed-exitcode
```

| 관측 | 단위·계산·대조 | 잘못된 해석 |
| --- | --- | --- |
| intended/selected/started | unit 경로 집합; config/source/command별 명시 | count 같으면 올바른 대상이라는 판단 |
| succeeded/failed/early exit/excluded | run의 unit 결과와 cause·dependency 원장 | 미실행 downstream을 독립 실패로 중복 집계 |
| unit/전체 duration | Started/Ended 차이 초, critical path와 순차/병렬 관계 | 병렬 unit 시간 합=wall time이라는 가정 |
| 실행 failure ratio | 동일 종류 run/선택 정책의 실제 실행 unit 중 오류 비율 | 제외·대기·plan diff를 모두 실패로 합산 |
| output/state identity | backend path·lineage·upstream output hash/alias | working directory/cache 위치만으로 state ownership 판정 |
| retry/hook 영향 | attempt·실행 단계·부작용 발생 집합 | retry가 앞선 성공 unit을 rollback한다는 가정 |

report schema는 버전별로 다를 수 있습니다. `Result`/`Reason`/`Cause` 부재를 임의 성공 값으로 채우지 않습니다. 원문 inputs/state/credentials는 공유하지 않고 unit 이름도 민감하면 alias로 바꿉니다.

## 네 가지 진단 시나리오

| 증상 | 점검 순서·경쟁 설명 | 조치와 회복 판정 |
| --- | --- | --- |
| application 실패, foundation 성공 | dependency 현재 outputs → mock 허용 명령 → 실제 source/ref → 입력 계약 오류와 provider 오류 분리 | 성공한 foundation을 무조건 재적용하지 않음. 실제 output 기반 application 새 plan 검토. 두 state·upstream 값 일치와 전체 no-op 확인 |
| downstream 실행이 안 됨 | selected 포함 여부 → excluded 설정 → ancestor 실패 → cycle/queue 구성 → 로그 시작 여부 | 선택 누락과 upstream failure를 서로 다르게 조치. 대상 집합 수정 또는 원인 unit 복구 후 새 plan; intended/started 결과 대조 |
| 특정 unit만 느림 | unit duration → init/source download/cache → engine lock/provider → 반복 retry | cache를 먼저 삭제하지 말고 state 위치 확인. root cause에 맞는 다운로드/동시 실행 조정 후 같은 두 unit workload 비교 |
| 환경과 다른 값/교체 계획 | include/inputs origin → dependency 현재 state → CLI engine/cwd/source → backend identity | 잘못된 input/ref를 전용 사본에서 복구하고 계획 재생성. debug artifact와 오래된 saved plan을 재사용하지 않음 |

필요한 단일 run에만 `--log-level debug`를 사용하고 engine 로그와 Terragrunt 로그를 구분합니다. `--inputs-debug`가 만든 변수 파일은 비밀을 포함할 수 있으므로 합성 사본에서만 사용합니다. 전체 환경에 DEBUG를 영구 설정하지 않습니다. [공식 debugging](https://docs.terragrunt.com/troubleshooting/debugging/)

## 기본 두-unit fixture에서 재현

1. **아직 foundation을 적용하지 않은 새 사본**에서 [로컬 절차](labs/README.md)의 plan을 실행합니다. application의 `mock-foundation` 관측과 실제 foundation output 부재를 기록합니다. 이 plan을 적용하지 않습니다. foundation을 개별 검토·적용한 후 application을 새로 plan하여 실제 값 `foundation`으로 바뀌는 것이 첫 회복 증거입니다.
2. 또 다른 **새 사본**에서 먼저 [로컬 절차](labs/README.md)대로 두 unit을 각각 검토·적용하고, 두 state/ID와 전체 no-op=0 기준선을 확보합니다. 이후 application의 `inputs` 중 unit_name을 module의 validation을 위반하는 값으로 바꿉니다. 변경은 application의 합성 설정에만 제한합니다. 두-unit plan에서 foundation의 결과와 application 오류·aggregate status를 대조합니다. input을 원래 값으로 복구한 뒤 재계획하여 no-op=0과 기존 state/ID 유지를 확인합니다. 이 오류는 plan 단계이며 부분 apply 실험으로 기록하지 않습니다.

원격 lock·provider throttling·hook 부작용·apply 도중 장애는 별도 실습이 필요합니다. `run --all apply/destroy`, 강제 unlock, state push, 재귀 cache 삭제를 기본 진단 명령으로 제공하지 않습니다. 여러 state는 전역 transaction이 아니며 [run의 자동 승인 경계](https://docs.terragrunt.com/reference/cli/commands/run/)를 확인합니다.

## 모듈·완료 기준

TG01–02 engine/cwd/input 출처, TG03–04 dependency·실행/미실행 원장, TG05–06 cache/backend identity·lock, TG07–08 selected/intended 변화, TG09–10 retry·신원/공급망, TG11–12 승인별 plan·state별 회복, TG13–14 원인 source·재현 보고서를 기본 산출물에 추가합니다.

실제 기준선과 두 문제의 가설/조치/회복을 [운영 보고서](../../operations/incident-report-template.md)에 남깁니다. Python DAG/CAS 결과만으로 scheduler/backend 운영을 통과하지 않습니다. 새 report 명령/사건은 이 개편에서 실행하지 않았으며 기존 native 실행 이력은 [검증 기록](../shared/validation.md)을 따릅니다.
