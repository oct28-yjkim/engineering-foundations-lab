# 02. Outputs, 두 DAG, 부분 성공

[과정](../README.md) · [공통 CPU 모형](../../shared/labs/README.md)

<a id="tg03"></a>
## TG03 — 현재 output과 미래 plan은 다르다

`dependency`는 다른 unit의 output을 값으로 읽는 관계를 표현합니다. `dependencies`는 순서 관계를 선언하지만 output namespace를 제공하지 않습니다. dependency output은 적용된 state의 관측값이며, upstream plan에서 계산한 미래 output을 downstream plan으로 자동 전달하는 기능이 아닙니다. [공식 dependency 정의](https://docs.terragrunt.com/reference/hcl/blocks/#dependency)

예를 들어 network state의 schema가 v1이고 아직 적용하지 않은 plan은 v2를 제안한다면, consumer plan이 보는 실제 output은 여전히 v1일 수 있습니다. 그래프 순서만 맞추면 future-value 전달이 해결된다는 가정을 버립니다. upstream 적용 후 consumer 재계획은 다른 artifact이며 새 검토 대상입니다.

### 네 가지 상태의 실험

| upstream 상태 | consumer에서 검증할 것 | 허용되는 해석 |
| --- | --- | --- |
| state 없음 | output 조회 실패 또는 명시적 mock | 실배포 유효성이 아닌 구성 검증 |
| v1 적용 완료 | v1 값과 output fingerprint | 관측 시점 현재 계약 |
| v2 plan만 존재 | v1 관측과 v2 예상 차이 | plan 간 자동 전달 없음 |
| v2 적용 완료 | 새 output으로 새 plan 생성 | 이전 consumer plan 승인 재사용 불가 |

학습용 dependency fragment는 다음처럼 command allowlist를 제한합니다. 완성 fixture의 경로·engine 설정은 [실습 안내](../labs/README.md)를 따릅니다.

```hcl
dependency "network" {
  config_path = "../network"
  mock_outputs = {
    contract = { schema_version = 1, network_id = "mock-network" }
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}
```

mock을 무조건 실 output보다 우선한다고 가정하지 않습니다. 실제 outputs 유무와 mock merge 전략에 따라 선택이 달라집니다. 이 과정은 `skip_outputs=true`나 mock/state merge로 apply 검증을 우회하지 않습니다. sentinel `mock-network`가 승인 가능한 실배포 plan에 들어가면 정책에서 거부합니다.

command allowlist는 과거에 mock으로 생성한 saved plan의 내용을 실제 output으로 바꾸지 않습니다. upstream 적용 후 새 consumer plan을 만들고 검토해야 하며, “apply에 mock을 금지했으니 어떤 saved plan도 안전하다”는 추론은 금지합니다.

**과제:** 미배포·v1·v2 상황의 origin ledger를 작성합니다. apply에서 mock이 허용되지 않는 부정 시험은 local-only unit에서 수행하고 실제 cloud 리소스를 만들지 않습니다. 타입뿐 아니라 schema version, 의미, 소비자의 backward compatibility를 검사합니다. 두 unit이 서로 output을 요구하는 cycle을 만들고 parse/graph/실행 중 어디서 거부되는지 기록합니다.

**통과:** 결과 count 대신 output의 필드·버전·출처·관측 시점을 비교합니다. mock plan PASS를 실행 가능한 production plan PASS로 분류하면 미통과입니다.

<a id="tg04"></a>
## TG04 — 실행 큐는 다중 state transaction이 아니다

이 강의는 `A → B`를 “B가 A에 의존한다”로 정의합니다. A→B, A→C, B→D, C→D의 diamond와 독립 unit X를 만듭니다. 생성·갱신 순서는 prerequisite가 먼저, 제거는 그 역관계가 필요하지만 실제 resource별 lifecycle은 Terraform가 결정합니다. [공식 Run Queue](https://docs.terragrunt.com/features/stacks/run-queue/)

공통 `graph` CPU 모형에서 순서를 검산한 뒤, 선택 local 환경에서는 unit별 시작·종료와 오류를 기록합니다. CPU 모형이 실제 scheduler의 경쟁·취소·실행 중 상태까지 재현한다고 주장하지 않습니다.

### 실패 원장

1. A 성공 뒤 B에서 deterministic 오류를 유발합니다. D는 failed dependency 때문에 실행 불가이며 C/X의 상태는 실제 일정과 정책에 따라 기록합니다.
2. 실행 중인 C/X가 취소될 것이라고 추측하지 말고 실제 종료 상태를 확인합니다. fail-fast는 이미 발생한 효과의 원자적 취소가 아닙니다.
3. `selected`, `started`, `succeeded`, `failed`, `blocked`, `not_started` 집합을 분리합니다. 이름은 학습 원장의 표준화 명칭이며 CLI report enum과 매핑을 남깁니다.
4. 오류를 고친 뒤 이미 성공한 unit과 미실행 unit을 재관측하고 새로운 plan을 검토합니다. “전체 실패” 메시지가 A/C의 state를 자동으로 원복했다고 가정하지 않습니다.

`--queue-ignore-errors`나 DAG 순서 무시는 진단 범위를 바꾸는 옵션입니다. apply의 복구 전략으로 습관적으로 사용하지 않습니다. unit 병렬도와 unit 내부 Terraform resource 병렬도도 다른 knob입니다. 총 동시 provider 요청 수는 둘의 단순 곱으로 항상 같지는 않지만 두 계층의 제한을 함께 고려해야 합니다.

**독립 oracle:** 그래프의 모든 간선에 대해 prerequisite 완료 전에 dependent가 시작했는지 검사합니다. 병렬 branch의 정확한 timestamp 순서는 강제하지 않고 partial order만 검사합니다. 성능은 같은 선택 집합·정확성 gate 통과 뒤 측정합니다.

**구술:** 왜 state lock 하나가 다른 state의 변경을 직렬화하지 않는가? 성공한 A를 destroy하면 왜 항상 B 실패를 보상하지 못하는가? engine exit code와 stack 요약 exit code가 각각 보존해야 할 정보는 무엇인가?

**소스:** `internal/queue/queue.go`의 `Entry`, `Queue`, `GetReadyWithDependencies`, `FailEntry`와 queue 테스트를 추적합니다. status 전이 전에 효과가 발생할 수 있는 구간을 찾아 [소스 지도](../source-reading.md)에 정리합니다.
