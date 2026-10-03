# 03. Source, 실행 디렉터리, State 소유권

[과정](../README.md) · [로컬 실습](../labs/README.md)

<a id="tg05"></a>
## TG05 — cache는 실행 산출물이지 항상 버려도 되는 데이터가 아니다

Terragrunt 1.x는 source block이 없는 경우에도 `.terragrunt-cache`에서 engine을 실행합니다. source URL의 다운로드 루트와 `//subdir`, 호출 unit 경로, 실제 작업 경로를 분리합니다. 상대 경로가 cache 기준으로 해석되는지 unit 기준으로 계산된 절대 경로인지 확인해야 합니다. [1.0 변경](https://github.com/gruntwork-io/terragrunt/discussions/5765), [cache 설명](https://docs.terragrunt.com/features/units/terragrunt-cache/)

특히 local backend의 state가 cache 안에 있으면 일반적인 cache 삭제가 state 손실이 됩니다. 이 과정은 local state를 명시적으로 식별 가능한 실습 경로에 두고, state·plan·generated config의 위치를 확인하기 전 어떤 cache도 재귀 삭제하지 않습니다. cloud backend를 쓴다는 이유만으로 cache에 민감 정보가 없다고 가정하지 않습니다.

### Identity 분해 실험

| 대상 | 재현에 필요한 identity | 바뀌었을 때 질문 |
| --- | --- | --- |
| module source | 저장소·immutable commit·subdir | 같은 URL이 다른 코드를 가리키는가? |
| unit | 정규화된 경로·입력·include | rename이 backend key를 바꾸는가? |
| engine | executable·version·provider selection | 같은 source가 다른 plan을 만드는가? |
| cache | 실제 경로·source fingerprint | stale source나 다른 생성물이 섞였는가? |
| backend | 유형·account/project·container·key/workspace | 다른 unit과 같은 state를 공유하는가? |

제공 fixture를 새로운 run 경로에 복사해 두 번 실행합니다. cache hit/miss 자체가 아니라 effective `.tf`·generated config·inputs·lock file fingerprint가 동일한지 비교합니다. 정리 대신 기존 run을 보존하고 새 run을 만드는 것이 기본입니다.

`.terraform.lock.hcl`은 provider selection과 checksum을 기록하며 module source commit이나 전체 dependency graph를 잠그는 파일이 아닙니다. Terragrunt는 기본적으로 unit 쪽 lock file을 engine 작업 경로에 복사하고 결과를 다시 unit 쪽으로 복사합니다. `copy_terraform_lock_file=false`로 결과 복사를 끌 수 있으므로 실제 설정·변경 diff를 검토하고 source pin과 provider lock을 각각 관리합니다. [lock file handling](https://docs.terragrunt.com/features/units/lock-files/)

**반례:** branch ref만 고정한 source, checksum이 없는 provider 신뢰, unit 밖 상대경로 파일 누락, 이름은 같은데 backend key가 바뀐 rename을 하나씩 검사합니다. local fixture에는 외부 provider가 없을 수 있으므로 “lock file이 안 생김”과 “lock 보호가 검증됨”을 구별합니다.

**소스:** `internal/runner/run/download_source.go`, `internal/tf/source.go`, `internal/runner/run/run.go`의 source 준비와 lock 복사 경계를 추적합니다. cache 구현의 이름만으로 보안 무결성을 보증하지 않습니다.

<a id="tg06"></a>
## TG06 — Backend 초기화와 리소스 생성은 별도 권한이다

backend 설정 파일 생성, engine init, 기존 state 읽기, state lock 획득, 저장소 bootstrap은 각각 다른 효과입니다. remote backend 구성은 credential·기존 리소스·정책에 따라 추가 작업을 요구하며, bootstrap 명령은 계정에 실제 리소스를 만들 수 있습니다. 기본 CPU/local 과정은 cloud backend를 사용하지 않습니다. [State Backend](https://docs.terragrunt.com/features/units/state-backend/), [backend bootstrap](https://docs.terragrunt.com/reference/cli/commands/backend/bootstrap/)

### 설계 과제: identity와 권한 matrix

두 환경 dev/prod, 두 unit network/app에 대해 backend identity tuple을 작성합니다. 동일 key 충돌, 대소문자·경로 정규화, 디렉터리 rename, workspace 이름 변경, 다른 account지만 같은 표시 이름을 음성 대조군으로 둡니다. “prod” 문자열을 포함한 key는 IAM 격리 증거가 아닙니다.

다음은 실제 cloud 실행이 아닌 기본 설계 제출물입니다.

- reader, planner, applier, backend administrator의 읽기·쓰기·lock·생성·정책 변경 권한을 분리합니다. Terraform provider 신원과 Terragrunt backend 작업 신원도 대조합니다.
- 존재하지 않는 backend는 기본적으로 중단하도록 조직 절차를 정합니다. 실습 편의를 이유로 자동 bootstrap 권한을 모든 CI job에 주지 않습니다.
- object versioning/암호화/접근 로그와 lock은 다른 문제를 해결합니다. versioning이 동시 writer 충돌을 막거나 민감 정보 접근을 차단하지 않습니다.
- 이름 변경 전 기존 state→새 구성 address의 소유권 mapping을 만듭니다. 이동과 복제는 다르며, 동일 실제 객체를 두 state가 소유하지 않도록 검사합니다.

공통 `state-cas` 모형에서 stale version 쓰기 거부를 확인합니다. 이것은 실제 backend lock 프로토콜·네트워크 분할·lease 회수의 구현이 아닙니다. backend migration/복원은 별도 승인된 격리 환경에서 backup fingerprint·lineage·serial·실제 객체 identity를 대조해야 하며, 강제 unlock/push를 일반 복구 명령으로 제공하지 않습니다.

**독립 oracle:** unit→backend identity는 일대일이어야 한다는 이 실습의 정책을 검사합니다. 의도적인 state 공유라는 예외를 두려면 ownership과 동시 실행 계약을 별도 작성해야 합니다. key 충돌을 잡지 못한 정책은 미통과입니다.

**구술:** snapshot을 이전 버전으로 되돌리면 원격 객체도 되돌아가는가? 삭제된 state object의 version이 남아 있어도 키/권한/region 손실 때 복구 가능한가? Terraform init 성공은 backend 재해 복구 시험을 대신하는가?
