# 03. 상태, 경쟁, 승인할 수 있는 계획

[과정](../curriculum.md) · [공통 CPU 실험](../../shared/labs/README.md)

<a id="tf05"></a>
## TF05 — state lock, lineage, serial은 서로 다른 질문에 답한다

### 원리

state는 단순 캐시가 아닙니다. 구성 주소와 객체 ID를 연결하는 소유권·관측 기록입니다. lineage는 상태 계보를, serial은 같은 계보의 snapshot 순서를 구별하는 메타데이터이며 객체의 업무 버전이나 분산 시각이 아닙니다. backend가 지원할 때 runtime lock은 경쟁 writer를 제어합니다. lock을 얻었다고 외부 콘솔 변경, 다른 state의 동일 객체 관리, provider의 부분 성공까지 막는 것은 아닙니다. [state 목적](https://developer.hashicorp.com/terraform/language/state/purpose)과 [locking](https://developer.hashicorp.com/terraform/language/state/locking)을 읽습니다.

`.terraform.lock.hcl`은 provider의 선택 버전·checksum 기록으로, runtime state lock과 용도가 전혀 다릅니다. backend마다 lock 구현·timeout·권한·versioning이 다르므로 “Terraform은 항상 같은 lock 알고리즘”이라고 일반화하지 않습니다. SOURCE의 snapshot metadata 검사 또한 backend 전체가 동일한 compare-and-swap API라는 뜻이 아닙니다.

### 경쟁 실험

1. CPU `state-cas`를 실행하고 두 writer가 같은 `(lineage, serial)`을 읽었을 때 발생하는 lost update를 설명합니다. 모형의 거부를 실제 backend의 실측이라 부르지 않습니다.
2. 순서 원장을 작성합니다: A 읽기 → B 읽기 → A 쓰기 → B 쓰기. lock, expected-version 검사, 아무 보호 없음 세 설계를 비교합니다.
3. 다른 lineage인데 serial이 더 큰 snapshot을 “더 최신”이라 수용하는 잘못된 규칙을 반례로 만듭니다.
4. local fixture의 별도 복사에서만 state metadata를 읽습니다. 원본 state를 직접 편집해 실험하지 않습니다. lock 충돌 native 과제는 격리한 자기 작업과 owner 확인 절차가 있어야 합니다.

산출물은 정상·경쟁·다른 계보 세 trace와 복구 전에 writer 생존 여부를 확인하는 runbook입니다. `force-unlock`이나 `-lock=false`를 일반적인 오류 해결책으로 제안하면 통과하지 않습니다. SOURCE에서는 `SnapshotMeta.Compare`, `WritePlannedStateUpdate`와 해당 테스트로 모형과 구현의 차이를 찾습니다.

<a id="tf06"></a>
## TF06 — plan은 보안·승인 artifact이기도 하다

### 원리

saved plan은 텍스트 요약이 아닌 실행할 변경과 필요한 정보를 담는 artifact입니다. CLI 화면의 민감 값 가림은 파일 암호화가 아닙니다. state·plan·`show -json`·debug log는 합성 값만 다루고 접근·보존 정책을 정합니다. ephemeral/write-only는 지원 문맥과 provider 조건이 있는 별도 기능이며 임의의 비밀 속성에 자동 적용되지 않습니다. [민감 데이터](https://developer.hashicorp.com/terraform/language/manage-sensitive-data)를 확인합니다.

JSON의 `change.actions`를 단일 문자열처럼 읽지 않습니다. 교체의 `delete/create`, `create/delete` 순서를 모두 고려하고, `after_unknown`의 정보 부족을 “정책 통과”로 바꾸지 않습니다. 값 표현에서 빠졌거나 null처럼 보이는 항목을 unknown 마스크 없이 확정하지 않습니다. 지원하지 않는 format version·action·구조는 자동 허용 대신 검토로 넘깁니다. [JSON 형식](https://developer.hashicorp.com/terraform/internals/json-format)이 기준이며 CPU `plan-policy`의 단순 입력은 전체 형식 구현이 아닙니다.

### 실험

1. create, update, delete, 두 교체 순서, no-op, unknown한 안전 조건의 작은 합성 계획을 만들고 기대 판정을 손으로 작성합니다.
2. 삭제 개수만 확인하는 정책이 replacement와 주소 allowlist 위반을 놓치게 합니다. 전체 actions와 주소 집합을 비교하는 규칙으로 고칩니다.
3. `approved config hash / provider+module revisions / backend identity / plan hash / approval`를 하나의 명세로 묶습니다. 다른 commit의 plan을 적용하는 CI 사례를 음성 대조군으로 둡니다.
4. native 확장은 실제 계획 JSON과 CPU 모형의 필드를 명시적으로 변환한 뒤, 모형이 생략한 drift·checks·action 관련 영역을 보고합니다. 자동 변환기가 제공된다고 가정하지 않습니다.

saved plan 적용의 stale-state 검사와 artifact 서명·권한·승인을 혼동하지 않습니다. 승인 뒤 외부 시스템이 바뀌는 TOCTOU 위험은 남으므로 유효 기간과 재계획 조건을 정의합니다. 산출물은 최소 8개 판정, 변조/누락의 거부 증거, 민감 artifact 보존·폐기 설계입니다.
