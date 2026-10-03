# 06. 배포 신뢰 경계와 복구

[과정](../curriculum.md) · [Terragrunt 확장](../../terragrunt/README.md)

<a id="tf11"></a>
## TF11 — 승인한 코드, 의존성, plan, 권한을 결박한다

### 원리

CI는 Terraform 명령을 실행하는 신뢰 주체입니다. fork PR·외부 module·provider binary·build artifact·backend credential·apply role을 같은 신뢰 수준으로 취급하지 않습니다. 외부 기여자가 제어한 configuration은 provider/data source/프로세스 실행으로 권한을 사용할 수 있으므로 “PR에서는 plan만 하니까 비밀을 줘도 된다”는 설계를 피합니다.

provider version constraint는 허용 범위이고 dependency lock file은 선택과 checksum을 기록합니다. module revision은 별도로 고정합니다. checksum은 기대 byte와 일치함을 확인할 뿐, 악성이나 취약점이 없음을 증명하지 않습니다. CLI·provider·module·CI action의 출처·불변 revision·검증 정책을 각각 문서화합니다. [dependency lock](https://developer.hashicorp.com/terraform/language/files/dependency-lock)과 [provider 설치 설정](https://developer.hashicorp.com/terraform/cli/config/config-file#provider-installation)을 근거로 mirror/cache의 신뢰 경계를 검토합니다.

OIDC 기반 짧은 수명 credential은 장기 비밀의 배포를 줄일 수 있지만 과도한 trust policy를 자동 해결하지 않습니다. issuer, audience, subject, repository/branch 또는 environment 조건을 구체화합니다. cloud별 claim과 policy 문법은 해당 공식 문서로 별도 검증하며 한 cloud의 예제를 다른 cloud에 복사하지 않습니다.

### 위협 모델 과제

1. untrusted PR → 검증 job → 보호된 plan → 승인 → apply → artifact 보존의 경계를 그립니다. 인증 정보와 쓰기 권한을 받는 지점을 표시합니다.
2. 승인된 plan hash가 다른 artifact로 바뀌는 경우, provider lock이 변경되는 경우, module ref가 움직이는 경우를 각각 거부하도록 설계합니다.
3. plan을 생성한 backend/workspace와 apply 대상이 같은지 확인하는 manifest를 작성합니다. 문자열 env 이름만 비교하지 않습니다.
4. 만료 token, 잘못된 audience, 다른 환경 subject의 부정 시험을 설계합니다. 실제 identity provider가 없으면 DESIGN이며 권한 거부를 실측했다고 하지 않습니다.

산출물은 신뢰 경계 5개 이상, 공격 입력 3개, 승인 artifact manifest, source 변경 시 재승인 규칙입니다. 제공 로컬 fixture에는 production CI credential·workflow 배포가 포함되지 않습니다.

<a id="tf12"></a>
## TF12 — state 복원과 서비스 복원은 다른 작업이다

### 원리

backend 선택은 저장 위치만의 문제가 아닙니다. 접근 제어·encryption·locking·versioning·audit·장애 복구 권한을 분리해서 봅니다. CLI workspace는 동일 configuration/backend 아래 state를 나누는 기능이며 독립 credential과 접근 통제가 필요한 환경 분리의 충분조건이 아닙니다. HCP Terraform workspace도 CLI workspace와 같지 않습니다. [workspaces](https://developer.hashicorp.com/terraform/language/state/workspaces)와 [backend 개요](https://developer.hashicorp.com/terraform/language/backend)를 읽습니다.

state snapshot은 database row, object bytes, KMS key, DNS cache, IAM session을 백업하지 않습니다. 이전 state를 덮으면 실제 자원이 복구되는 것이 아니라 실제와 binding의 불일치가 커질 수 있습니다. 복구는 writer 중단, 현재 증거 보존, snapshot 계보·시점 확인, 실제 객체 재조사, 제한된 수선, full plan·업무 health 검증의 순서로 설계합니다. `state push -force` 같은 우회가 기본 복구 절차가 되어서는 안 됩니다.

### 복구 리허설

| 사고 | 먼저 보존·확인할 것 | 금지할 성급한 결론 |
| --- | --- | --- |
| CI 중단 뒤 lock | owner·run 생존·backend lock identity | 기다리기 싫으니 무조건 강제 해제 |
| state 쓰기 실패 | provider/API 결과·현재 snapshot·진단 artifact | apply 실패이니 원격 변화도 0건 |
| 잘못된 snapshot | lineage·serial·version history·실제 binding | serial만 크면 정답 |
| 실제 DB 손실 | 별도 데이터 백업·복원 시점·service health | state를 복원하면 row도 복구 |

OFFLINE에서는 합성 snapshot과 객체 ledger만 사용합니다. LOCAL-TERRAFORM 확장은 disposable 작업 폴더의 자체 상태만 사용하고 원본 파일 덮어쓰기 없이 새 복사에서 검토합니다. 원격 lock·IAM·retention의 실제 검증은 별도 CLOUD-LAB입니다.

RTO는 장애 인지부터 어떤 health gate가 회복될 때까지인지 정하고, RPO는 state snapshot 간격과 업무 데이터 손실을 분리합니다. 복구 뒤 예상 외 삭제·교체 0건, 모든 객체의 owner·주소·ID 일치, 금지 principal의 접근 거부를 확인합니다. 미실행 gate는 목표값으로만 표시합니다.
