# Terraform 운영 실습: 계획·실행·상태 문제를 증거로 좁히기

[실제 CLI 실습](labs/README.md) → 이 문서 → [커리큘럼](curriculum.md) 순서로 학습합니다. Terraform **1.16.5**를 기준으로 하며 실습 대상은 [격리 환경](../shared/environment.md)의 built-in `terraform_data`와 local state입니다. 상시 서비스 지표보다 **실행별 결과·단계별 시간·변경 대상·lock/상태·provider 오류**가 중심입니다. Python 모형은 선택 보조자료입니다.

<a id="basic-lab"></a>

## 기본 LAB: 정상 동작에서 장애 복구까지

**정상 기능 → 동작 원리 → 관측 → 제약 → 진단·복구** 순서의 입문 카드입니다. 실제 로컬 fixture의 plan→검토→apply→no-op를 먼저 익히고 입력·주소·state·오류를 연결합니다. [공통 LAB 계약](../../operations/lab-contract.md)에 따라 정상 결과를 먼저 검산한 뒤 아래 상세 절차로 진행합니다. 28주 심화는 선수 조건이 아니며, 이 카드 추가가 새 자동 실행기 제공이나 실제 장애 검증 완료를 뜻하지 않습니다.

| 단계 | 실행·관측·판정 |
| --- | --- |
| 정상 기능부터 | [실제 CLI 실습](labs/README.md)의 새 ignored 사본에서 built-in `terraform_data` 계획을 검토한 후 해당 로컬 fixture만 적용합니다. 기대 output·state ID를 기록하고 같은 입력의 재계획 exit 0/no-op를 정상 기준선으로 확보합니다. |
| 동작 원리 | HCL 입력/validation→graph→plan actions→apply→state binding을 연결합니다. config·state·실제 객체는 같은 것이 아니며 plan의 변경 제안과 오류를 구별합니다. provider lock file과 state lock도 다릅니다. |
| 직접 볼 지표·방법 | 아래 version/providers/workspace/validate/plan 명령으로 실제 대상·exit 0/1/2·diagnostic·planned actions를 기록합니다. 실행별 시간, replacement 주소, state ID를 비교하며 상시 CPU dashboard가 필수는 아닙니다. |
| 먼저 확인할 제약 | 제공 fixture는 local backend/built-in만 사용하며 cloud API·IAM·remote lock·throttling을 재현하지 않습니다. 일반 plan은 외부 효과가 있을 수 있고 state/plan/debug에는 민감 값이 들어갈 수 있습니다. 다른 저장소에 명령을 그대로 적용하지 않습니다. |
| 자주 마주치는 사건 2개 | 아래 기본 사건 1: revision 변경 계획의 exit 2를 실패로 오분류하는 wrapper와 정상 diff를 구별합니다. 사건 2: 별도 새 사본에 validation 위반 입력을 plan으로만 전달해 실제 exit 1·diagnostic을 확인합니다. replacement 계획을 실행하지 않습니다. |
| 조치와 회복 oracle | 원래 revision으로 plan을 되돌려 no-op=0·기존 ID 유지, 잘못된 입력을 정상으로 돌려 validation/plan 통과를 확인합니다. state/객체를 강제로 되돌리지 않고 plan 분류기의 0/1/2 세 경우를 검산합니다. |
| 제공물·추가 준비 | 고정 CLI 준비 안내·실제 module/fixture·아래 수동 사건을 제공합니다. CLI는 별도 준비이며 새 사건 자동실행기는 아닙니다. remote lock·부분 apply·provider 오류·cloud 확장은 별도 격리 환경 LAB입니다. |

두 사건의 결과가 예상과 다르면 관측한 상태를 기록하고 발생기/변경부터 멈춥니다. 정상 baseline·사건별 경쟁 가설·제한 조치·회복 oracle·미실행 범위를 [사건 보고서](../../operations/incident-report-template.md)에 남깁니다.

## 먼저 수집할 증거

실습 안내의 새 사본·`$iacTerraform`·init을 준비한 뒤 해당 root module에서 실행합니다. 아래 plan은 제공된 무클라우드 fixture에 한정합니다. 일반 plan은 provider/data source/외부 프로그램·backend lock 등을 사용할 수 있으며 읽기 전용 보안 경계가 아닙니다.

```powershell
& $iacTerraform version -json
& $iacTerraform providers
& $iacTerraform workspace show
& $iacTerraform validate -no-color
& $iacTerraform plan -input=false -no-color -detailed-exitcode
$iacPlanExit = $LASTEXITCODE
```

exit **0=성공·변경 없음, 1=오류, 2=성공·변경 있음**을 구분합니다. exit 2를 CI 장애율에 포함하지 않습니다. 저장된 plan은 승인 artifact의 hash·구성 revision·실제 대상과 함께 비교하며 plan 원문에는 민감 값이 포함될 수 있습니다. [공식 plan 계약](https://developer.hashicorp.com/terraform/cli/commands/plan)

| 관측 항목 | 정의·수집 | 진단에 쓸 때의 한계 |
| --- | --- | --- |
| 실행 성공/오류/변경 유무 | run별 exit와 diagnostic severity·stage; 분모는 완료된 동일 종류 실행 | plan 2와 apply 실패는 다른 사건; 취소/timeout을 별도 표기 |
| plan/apply duration | 단조 시각 start/end의 초, 같은 root·동일 데이터 baseline과 비교 | init 다운로드·lock 대기·provider 호출을 전체 시간 하나로 뭉개지 않음 |
| planned actions | 저장 plan의 resource_changes/address/action 조합별 건수 | replacement는 delete/create 둘을 가지며 단순 create 건수로 위험 판정 불가 |
| lock wait | 대기 시작/획득/실패 시간과 lock owner·backend identity | `.terraform.lock.hcl`과 state lock은 다름; backend별 지원을 확인 |
| provider 오류/재시도 | 정제된 diagnostics의 provider/resource·상태 분류·반복 횟수 | built-in fixture에는 cloud API·throttling 측정이 없음 |
| drift/부분 적용 | config·관측 객체·state binding의 차이, 변경 전후 ID/속성 | state serial만으로 원격 업무 결과를 확정하지 않음 |

집계는 최근 N개의 동일 pipeline 또는 명시한 시간 구간을 사용합니다. 보편적인 CPU/지연 임계값을 만들지 않습니다. `-json` 실행 출력은 event stream이고 `show -json` saved-plan 문서와 다른 형식입니다. 지원 버전과 event type을 확인합니다. [machine-readable UI](https://developer.hashicorp.com/terraform/internals/machine-readable-ui)

## 증상별 점검 순서

| 증상 | 경쟁 원인과 점검 순서 | 조치·되돌리기·회복 기준 |
| --- | --- | --- |
| CI가 plan을 실패라고 표시 | 원래 exit 1/2 → wrapper 전달값 → 실제 error diagnostic → 변경 actions | 2를 정상 diff로 분류하도록 pipeline 수정. 권한/실행 오류를 무시하지 않음. 동일 입력 no-op=0, 변경=2, invalid=1 세 경우를 모두 확인 |
| 예상하지 못한 replacement | 실제 var/주소/key → triggers_replace/lifecycle → provider schema/force replacement → 이전 state binding | 적용 보류, 의도한 입력/주소로 복귀 후 재계획. `-target`으로 숨기거나 plan 내용을 수동 변조하지 않음. 불필요한 delete/replacement 0과 ID 유지 확인 |
| state lock에서 오래 대기 | backend/workspace/owner 확인 → 진행 중 CI/프로세스 → 이전 실행 완료 여부 → backend 접근 오류 | 실제 writer가 있으면 기다리거나 승인된 소유자가 종료. `-lock=false`/강제 unlock을 첫 조치로 쓰지 않음. [lock 규칙](https://developer.hashicorp.com/terraform/language/state/locking)에 따라 잔존 lock 판정 후 별도 승인; 다음 plan과 state/객체 일치 확인 |
| apply 일부 성공 뒤 실패 | 성공 resource 집합 → 실패 단계/diagnostic → 실제 객체·state ID → 원래 승인 artifact와 현재 차이 | 전체 재실행/과거 state push 전에 성공분 보존과 새 plan 검토. 같은 backend라도 다중 API는 원자적 rollback 아님. 회복 후 전체 no-op와 기대 ID/값 검산 |
| plan 지연·API throttling | init/cache vs lock 대기 → slow resource/provider → API quota·오류·동시 실행 → 네트워크 | 원인에 맞춰 변경 하나만 제한. 병렬도 무조건 증가 금지. 동일 workload에서 duration·error·retry·정확성을 비교; cloud 확장은 별도 환경 필요 |

추가 debug는 전용 합성 사본에서 필요한 한 실행에만 활성화합니다. `TF_LOG`/`TF_LOG_CORE`/`TF_LOG_PROVIDER`는 정보 노출·성능 영향을 고려하고 기존 env 값을 보존한 뒤 복원합니다. DEBUG/TRACE 원문을 그대로 Git·CI 공개 artifact에 올리지 않습니다. [공식 debug 지침](https://developer.hashicorp.com/terraform/internals/debugging)

## 기본 환경에서 재현할 두 사건

1. 로컬 실습을 완료하여 재계획 exit 0을 확보합니다. **적용하지 않고** `revision=2` 계획을 만들어 exit 2와 replacement+dependent updates를 기록합니다. wrapper가 nonzero 전부 오류로 취급하는 경우와 구분한 경우의 판정을 비교합니다. 원래 revision 계획으로 되돌아가 exit 0·기존 ID 유지가 회복 기준입니다.
2. 새로운 실습 사본에서 module의 허용 이름 규칙을 위반하는 입력을 plan에 전달합니다. 정확한 validation diagnostic과 exit 1, plan 전후 state 불변을 확인합니다. 입력만 정상으로 복귀하여 plan 통과를 확인합니다. validation을 제거하여 “고치지” 않습니다. 입력 이름/규칙은 [실제 module](../shared/modules/contract/main.tf)을 읽고 선택합니다.

lock 경쟁·provider throttling·부분 apply는 별도 격리 backend/provider의 수동 과제입니다. 제공 built-in fixture가 그 장애들을 자동 만들어 준다고 주장하지 않습니다. 두 기본 사건으로 cloud 운영 전체를 완료할 수는 없습니다.

## 14모듈에 붙일 운영 증거

TF01–02 입력·validation/diagnostic, TF03–04 resource graph·slow stage/provider, TF05–06 lock/state identity·exit/actions/plan hash, TF07–08 주소 변경·replacement 원인, TF09–10 정상/거부·drift/부분 성공, TF11–12 CI 승인·backend 복구, TF13–14 원인 코드 경로·재현/회복 보고서를 제출합니다. 각 모듈의 원리·소스 과제를 대신하는 것이 아니라 실측과 연결합니다.

기준선 1개와 서로 다른 실제 CLI 문제 2개의 진단·회복을 [보고서](../../operations/incident-report-template.md)로 제출합니다. 원리 모형 PASS만으로 제품 실습을 완료하지 않습니다. 이 문서의 새 사건 절차는 작성 시 자동 실행하지 않았으며 실제 실행 이력은 기존 [검증 기록](../shared/validation.md)과 구분합니다.
