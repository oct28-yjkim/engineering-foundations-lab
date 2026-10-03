# 05. 부작용, 재시도, 실행 신뢰

[과정](../README.md) · [소스 지도](../source-reading.md)

<a id="tg09"></a>
## TG09 — 선언형 입력이 실행을 순수 함수로 만들지는 않는다

`run_cmd`는 HCL 평가 중 명령을 실행할 수 있고 hook은 engine 작업 전후 또는 오류 경로에서 외부 동작을 수행합니다. 출력 캐싱과 멱등성은 다릅니다. 동일 명령이 여러 parser pass, 다른 unit, 재시도, 새 CI job에서 몇 번 실행될지는 실행 조건과 cache scope에 달려 있습니다. [공식 Functions](https://docs.terragrunt.com/reference/hcl/functions/#run_cmd), [Hooks](https://docs.terragrunt.com/features/units/hooks/)

plan에서 외부 API를 호출하는 hook, data source의 custom executable, 인증 helper가 있다면 “plan만 실행했다”는 말로 변경 부재를 보장할 수 없습니다. 기본 fixture는 외부 명령·cloud provider 없이 유지하고, 아래 확장은 합성 local effect ledger만 사용합니다.

### 학습자 확장 실험

1. 전용 새 실습 폴더에만 기록하는 helper를 작성합니다. invocation ID, unit, phase, attempt, operation key를 append-only ledger에 저장합니다. 운영 API·이메일·과금 작업은 사용하지 않습니다.
2. 외부 효과 기록 뒤 오류를 반환하는 helper와 효과 기록 전 오류를 반환하는 helper를 비교합니다. 둘 다 exit 1이지만 재시도 판단에 필요한 정보는 다릅니다.
3. operation key에 deduplication이 없는 경우와 atomic check-and-record가 있는 경우를 비교합니다. process-local 메모리의 체크는 다음 process의 재시도를 막지 못합니다.
4. unknown outcome 상태를 도입합니다. 응답 timeout이 발생했지만 효과가 실행됐는지 모르면 “실패이므로 재시도” 대신 원장·대상 조회가 필요합니다.

각 실패는 transient, deterministic invalid configuration, permission denied, ambiguous external effect로 분류합니다. 재시도는 횟수·전체 기한·backoff·허용 오류를 제한하고, 전체 unit 재실행이 이미 성공한 hook을 다시 수행할 수 있는지 기록합니다. 오류 무시로 성공처럼 보이게 만드는 규칙은 부정 시험으로 걸러냅니다. [오류·retry 제어](https://docs.terragrunt.com/features/units/runtime-control/)

**불변식:** 승인된 operation key당 외부 효과 최대 한 번이라는 계약을 정했다면 crash/retry 구간에서 ledger로 검사합니다. 로그 메시지 한 줄만 보고 deduplication 성공을 판단하지 않습니다. 이 조건은 별도 helper의 계약이며 Terraform/Terragrunt가 임의 외부 효과에 제공하는 보장이 아닙니다.

**소스:** `internal/runner/run/run.go`의 `RunActionWithHooks` 주변 실패 반환과 실행 순서를 추적합니다. helper의 idempotency와 Terragrunt의 retry 정책을 분리해서 테스트합니다.

<a id="tg10"></a>
## TG10 — 같은 프로세스 계열 안에도 여러 신원이 있다

Terragrunt의 dependency output 조회, backend bootstrap/migration, Terraform backend, provider API, source 다운로드, hook은 각각 다른 신원과 신뢰 대상에 접근할 수 있습니다. provider의 assume-role 설정이 모든 Terragrunt 작업에 자동 적용된다고 가정하지 않습니다. [공식 Authentication](https://docs.terragrunt.com/features/units/authentication/)

기본 과정에서는 실제 토큰을 발급하지 않고 아래 matrix를 설계합니다. cloud 선택 확장은 별도 sandbox와 승인이 있을 때만 수행합니다.

| 상황 | 기대 | 검증해야 할 근거 |
| --- | --- | --- |
| 승인된 repository·branch·environment의 짧은 세션 | 명시한 plan 범위 허용 | subject/audience/issuer·세션·대상 identity |
| fork PR 또는 다른 branch | privileged role 거부 | trust policy deny와 정상 대조군 |
| 만료되거나 다른 audience 토큰 | 거부 | 실제 인증 오류; 단순 네트워크 오류와 분리 |
| planner의 backend 생성·권한 변경 | 거부 | bootstrap/admin 권한과 분리 |
| applier의 미승인 환경·unit | 거부 | identity policy와 별도 exact 대상 allowlist |

“OIDC 사용” 자체는 least privilege의 증거가 아닙니다. claim 조건이 넓거나 untrusted PR 코드가 privileged job에서 실행되면 장기 키가 없어도 위험합니다. 권한 없는 secret 값 접근은 아무 내용도 출력하지 않는 deny 시험으로 검사하고, 정상 identity의 성공을 함께 확인해 test 자체의 오류를 배제합니다.

### 공급망 과제

- Terragrunt와 Terraform executable의 version·출처·checksum을 기록합니다. 서명/attestation 확인은 해당 릴리스가 제공하는 검증 절차를 따라 별도 기록합니다.
- Git source commit, provider lock·checksum, CI action commit, helper 코드·실행 인자를 모두 review 대상에 넣습니다. source pin은 신뢰 결정을 고정할 뿐 코드의 선함을 증명하지 않습니다.
- provider cache와 download cache에 여러 신뢰 영역의 job이 동시에 쓰게 하지 않습니다. shared cache를 최적화하기 전에 소유권·검증·동시 접근 계약을 정합니다.
- plan JSON, state, debug inputs, crash log를 secret-bearing artifact로 취급합니다. stdout masking을 저장 데이터 암호화라고 부르지 않습니다.

**통과:** 허용/거부 사례가 분리되고 어떤 executable이 어떤 신원으로 어떤 대상에 접근하는지 설명해야 합니다. 설계 matrix만 있으면 `CLOUD-DESIGN`이며 실제 IAM 거부를 검증했다고 쓰지 않습니다.
