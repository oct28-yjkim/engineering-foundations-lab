# IaC 선택 원리 부록 — 그래프·정책·state·변경 영향 범위

[Terraform 과정](../../terraform/README.md) · [Terragrunt 과정](../../terragrunt/README.md) · [저장소](../../../README.md)

기본 실습은 [실제 Terraform](../../terraform/labs/README.md)·[실제 Terragrunt](../../terragrunt/labs/README.md) → [Terraform 진단](../../terraform/operations.md)·[Terragrunt 진단](../../terragrunt/operations.md)입니다. 이 모형은 이해를 위한 선택 보조자료이며 먼저 통과할 필요가 없고, 완료 점수를 운영 실습으로 대체하지 않습니다.

Python 3.10 이상과 표준 라이브러리만 사용한다. Terraform/Terragrunt 설치, 계정, 자격 증명, GPU, API 결제가 필요 없다. 코드는 메모리에서만 계산하고 표준 출력으로 결과를 표시한다. 파일·네트워크·하위 프로세스 접근은 없으며, `-B`는 Python의 바이트코드 캐시 생성도 막는다.

이 실험은 **제품 구현을 축소 재현한 시뮬레이터가 아니라, 명시적인 가정을 가진 교육 모델**이다. `PASS`는 모델의 고정된 정답과 결과가 일치한다는 뜻이다. Terraform plan/apply 성공, Terragrunt 실행 순서 검증, backend 동시성 안전성, 클라우드 권한 검증을 뜻하지 않는다.

## 실행

저장소 루트에서 실행한다. Windows에서 `python`이 설치 안내만 표시하면 실제 Python 실행 파일 또는 설치된 `py -3`를 사용한다. 이 명령은 도구를 자동 설치하지 않는다.

```bash
python -B infrastructure/shared/labs/offline_lab.py --lab all
python -B -m unittest discover -s infrastructure/shared/labs -p "test_*.py" -v
python -B -O -m unittest discover -s infrastructure/shared/labs -p "test_*.py" -v
```

첫 명령은 `status: PASS`인 JSON 4줄을 출력한다. 나머지 두 명령은 각각 82개 테스트를 실행한다. 핵심 검증은 `assert` 문이 아닌 `ValueError`를 사용하므로 최적화 모드 `-O`에서도 사라지지 않는다. 테스트는 정상 경로뿐 아니라 잘못된 입력, 변경 전 데이터 보존, 실패 후 부분 상태, 독립적인 리터럴 정답을 검증한다. 실제 HCL·provider·원격 state·클라우드는 실행하지 않는다.

| 명령의 `--lab` 값 | 질문 | 고정 정답의 핵심 |
| --- | --- | --- |
| `graph` | 어떤 unit이 먼저 실행 가능하고 실패는 어디까지 전파되는가? | database 실패 → api 차단, 독립 dashboard 성공 |
| `plan-policy` | 알려진 범위의 변경인가? 파괴적 변경이나 unknown은 없는가? | 알려진 create 허용, 두 replacement 순서와 region unknown 거부 |
| `state-cas` | stale state·다른 lineage·다른 lock owner를 구분하는가? | network serial=1, database serial=0의 부분 완료 상태 |
| `blast-radius` | 변경 파일만 선택하면 무엇을 놓치는가? | database 영향은 api·worker까지, 실행 전제에는 network·identity 추가 |

## 1. Dependency graph — 순서와 실패를 분리하기

```bash
python -B infrastructure/shared/labs/offline_lab.py --lab graph
```

`graph[unit]`에는 그 unit이 의존하는 선행 unit 이름을 넣는다. `topological_layers()`의 결과는 실행 가능 계층이며, 실제 스레드 수·시작 시각·작업 시간은 아니다.

```text
계층 0: network, telemetry
계층 1: dashboard, database
계층 2: api

database = FAILED
api = BLOCKED
network, telemetry, dashboard = SUCCEEDED
```

실험 순서:

1. 각 unit의 직접 의존성과 전이 의존성을 손으로 구한다.
2. database에 실패를 주고 api는 실행되지 않는다는 정답을 적는다. telemetry 쪽은 계속 완료되어야 한다.
3. 실패 목록에 api도 넣는다. 선행 실패 때문에 실행되지 않았으므로 api 결과는 `FAILED`가 아니라 `BLOCKED`다.
4. 누락된 이름·자기 자신을 참조하는 edge·여러 unit 사이의 cycle을 넣어 `ValueError`를 확인한다.
5. 입력 순서를 바꾸어도 같은 계층과 결과가 나오는지 확인한다.

범위: 단일 DAG, 고정된 성공/실패 주입, 결정적 정렬만 다룬다. Terragrunt의 실제 run queue, fail-fast/queue 옵션, 동시 실행, retry, destroy 방향, hook, 읽기 의존성 발견은 구현하지 않는다. 실제 도구에서는 선택한 버전의 동작을 별도 실습으로 측정한다.

## 2. Plan policy — unknown을 승인으로 바꾸지 않기

```bash
python -B infrastructure/shared/labs/offline_lab.py --lab plan-policy
```

`evaluate_plan()`의 입력은 **의도적으로 만든 작은 JSON 형식**이다. 실제 plan JSON 파일을 그대로 읽는 기능은 없으며, 전체 Terraform JSON envelope를 넘기면 거부한다.

```json
{
  "resource_changes": [
    {
      "address": "demo.service",
      "change": {
        "actions": ["create"],
        "after": {"env": "lab", "region": "local"},
        "after_unknown": {"region": false},
        "after_sensitive": {}
      }
    }
  ]
}
```

정책과 입력 계약:

- 허용된 action sequence는 `["no-op"]`, `["read"]`, `["create"]`, `["update"]`, `["delete"]`, `["delete", "create"]`, `["create", "delete"]`뿐이다. 마지막 세 가지는 파괴적 변경으로 거부한다. 순서를 집합으로 바꾸어 replacement의 두 형태를 혼동하지 않는다.
- `after.env`와 `after.region`은 평면의 문자열 필드이며 기본 허용 값은 각각 `lab`, `local`이다. 이것은 실제 provider의 공통 필드라고 가정한 것이 아니다.
- required identity의 unknown marker가 `true`이면 그럴듯한 `after` 값이 있어도 거부한다. `after_unknown: true`이면 두 identity 모두 unknown으로 간주한다.
- required identity가 누락·null·숫자이거나 허용 범위를 벗어나면 거부한다. 다른 필드의 unknown을 허용하는 것은 이 **좁은 정책의 명시적 한계**다.
- `after_sensitive`는 표시만 한다. 민감 값 표시 자체는 암호화 구현이 아니며, 모델도 표시를 근거로 값을 숨기거나 승인하지 않는다. CLI 요약에는 입력 payload를 출력하지 않는다.
- envelope·resource·change에 모르는 필드가 있거나, 필수 marker가 없거나, 지원하지 않는 action sequence가 있으면 `ValueError`다. 호출자가 이 오류를 승인으로 해석하면 안 된다.

변형 과제:

1. create를 두 replacement 순서로 각각 바꾼 뒤 둘 다 `DENY`인지 확인한다.
2. `after.region="local"`을 유지한 채 unknown marker만 켠다. 값의 모양으로 불확실성을 덮을 수 없어야 한다.
3. 민감 표시가 있는 production 값을 넣고 여전히 거부되는지 확인한다.
4. 실제 도구 연계 전에는 원본 JSON schema/version, nested provider identity, deferred change, drift, import/move/forget, output/change 의미를 별도로 검증하는 adapter와 테스트가 필요하다고 기록한다. 이 교육 parser를 그 adapter로 사용하지 않는다.

`ALLOW`는 이 입력의 두 identity와 action 정책만 통과했다는 의미다. 비용·권한·실제 resource 상태·apply 시점의 drift·실행할 plan artifact 동일성은 증명하지 않는다. 빈 change 목록도 실제 환경을 관찰한 결과가 아니다.

## 3. State CAS — 락, 버전, 부분 완료를 서로 구분하기

```bash
python -B infrastructure/shared/labs/offline_lab.py --lab state-cas
```

`StateSnapshot`은 immutable lineage·serial·문자열 resource 쌍을 가진다. `MemoryStateStore`는 각 state에 별도 owner/generation token을 부여하고, 다음 조건을 만족할 때만 교체한다.

1. 현재 state의 lock token과 요청 token의 state ID·owner·generation이 같다.
2. expected lineage와 serial이 현재 state의 값과 같다.
3. 새 snapshot은 lineage를 유지하고 serial을 정확히 1 증가시킨다.

expected resource payload 전체를 비교하는 CAS는 아니다. 잘못된 lineage, stale serial, serial 건너뛰기, 다른 owner의 unlock, 과거 generation token 재사용은 거부한다. 거부된 요청은 현재 snapshot을 바꾸지 않아야 한다.

기본 실험은 network 교체를 완료한 후 database 교체를 실패시킨다. 정답은 다음과 같다.

```text
network:  serial 0 -> 1  완료
database: serial 0 -> 2  거부, serial 0 유지
전체 원자적 rollback: 없음
```

실험 순서:

1. 첫 snapshot을 저장하고 정상 CAS 뒤에도 그 객체의 serial/payload가 그대로인지 검사한다.
2. 같은 옛 snapshot을 재사용하여 stale 거부를 확인한다.
3. serial은 같지만 lineage가 다른 snapshot으로 시도한다.
4. 잘못된 owner로 release를 시도한다. 정상 owner의 lock은 유지되어야 한다.
5. 정상 release 후 같은 owner가 다시 acquire한다. 예전 generation token으로 새 lock을 지울 수 없어야 한다.
6. 서로 다른 두 state의 부분 완료를 관찰하고, 복구 절차에 필요한 관측·승인·보상 작업을 적는다. 한 state의 lock이 여러 state의 트랜잭션을 만들지는 않는다.

범위: 단일 프로세스·순차 호출 교육 코드다. thread-safe 분산 lock, lease·만료·crash recovery, 서버 측 fencing, 인증, 암호화, persistence, 실제 backend wire protocol을 구현하지 않는다. owner 문자열/token은 보안 credential이 아니며 위조 방지 장치도 아니다. 실제 Terraform의 state serial 증가 규칙이나 모든 backend의 CAS를 복제했다고 해석하지 않는다.

`state_id`는 명시적으로 선택한 identity다. 같은 lineage/serial이라도 state ID가 다르면 이 모델에서는 별도 state다. 디렉터리 분리만으로 state identity·IAM·tenant 격리가 자동 생성된다고 가정하면 안 된다.

## 4. Blast radius — 변경·영향·실행 전제 집합 나누기

```bash
python -B infrastructure/shared/labs/offline_lab.py --lab blast-radius
```

이 모델은 이미 파악된 `changed` unit 집합을 입력받는다. Git diff를 module 소비자에게 연결하는 기능은 없다.

```text
changed:                  database
affected:                 api, database, worker
external_dependencies:    identity, network
dependency_closure:       api, database, identity, network, worker
selected_for_execution:   api, database, identity, network, worker
```

- `affected`는 changed에 그 변경을 소비하는 모든 전이 dependent를 더한 집합이다.
- `dependency_closure`는 affected가 실행하려면 필요한 전이 prerequisite까지 포함한다.
- 여기서 external은 저장소 밖이라는 뜻이 아니라 **affected 집합 밖의 prerequisite**이라는 뜻이다.
- external dependency가 있으면 결정을 생략할 수 없다. `include`는 함께 선택한다. `assume-ready`는 실제 검증 없이 준비되었다고 가정하고 `assumed_ready`에 누락 대상을 명시한다. 후자는 승인 권고가 아니며 운영에서는 별도 증거가 필요하다.
- `include`로 더한 unchanged ancestor가 실제로 변경된다고 가정하지는 않는다. 그 ancestor의 plan에서 drift나 변경을 발견하면 changed 집합에 추가하고 영향 분석을 다시 해야 한다.

변형 과제:

1. 변경 경로와 같은 unit인 database만 선택하는 방식이 api·worker를 놓치는지 확인한다.
2. `external_decision`을 생략해 거부되는지 확인한다.
3. `assume-ready`를 사용한 결과와 `include`의 집합 차이를 설명한다. 어떤 state/output freshness 증거가 필요한지 적는다.
4. 공유 module 변경, 간접 파일 읽기, 숨은 외부 API, IAM, state address가 그래프에 누락되면 결과가 얼마나 과소평가되는지 반례를 작성한다.

이것은 선언된 edge를 바탕으로 한 영향 추정이다. 계획한 집합의 모든 unit이 실제로 resource를 변경한다는 뜻도, 선택되지 않은 unit이 절대 영향받지 않는다는 보장도 아니다. 파일 경로, unit, backend key, state lineage, cloud identity를 별도 식별자로 기록한다.

## 제출물과 종료 기준

각 실험에 다음을 남긴다. 기록할 때 실제 비밀 값이나 원격 state 원문을 저장소에 넣지 않는다.

1. 실행 명령·Python 버전·코드 revision과 리터럴 정답.
2. 하나의 정상 입력, 하나의 반례, 결과 차이를 설명하는 불변식.
3. 모델에서 검증한 것 / 실제 제품에서 아직 검증하지 않은 것의 구분.
4. 실패 후 남는 상태와 안전한 다음 조치. 오류를 무시하거나 강제 unlock하는 것이 정답이 되어서는 안 된다.
5. 실제 CLI 실습으로 옮길 때 필요한 버전·backend·credential·승인·정리 범위.

82개 테스트 통과는 출발점이다. 전문가 단계의 완료 기준은 각 불변식의 적용 범위를 설명하고, 모델이 설명하지 못하는 실제 도구 동작을 별도의 관측 가능한 실험으로 검증하는 것이다.
