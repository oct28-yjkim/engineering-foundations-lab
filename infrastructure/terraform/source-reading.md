# Terraform 소스·공식 자료 지도

[과정](curriculum.md) · [연구 과제](lessons/07-research-capstone.md#tf13)

## 재현 가능한 revision

기준은 [v1.16.5 릴리스](https://github.com/hashicorp/terraform/releases/tag/v1.16.5)와 commit [`ef47237fd0e03d6e93bdc510b526287f06e94c03`](https://github.com/hashicorp/terraform/tree/ef47237fd0e03d6e93bdc510b526287f06e94c03)입니다. 2026-10-04에 공식 GitHub ref가 이 commit을 직접 가리킴을 확인했고 recursive tree의 `truncated=false`, 아래 source/test 경로와 주요 symbol을 확인했습니다. 파일을 읽었다는 것은 Go 테스트 실행 통과를 뜻하지 않습니다.

고정 [go.mod](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/go.mod)의 Go·HCL·cty 의존성도 기록합니다. 이 revision의 `github.com/zclconf/go-cty`는 `v1.18.1`입니다. 현재 문서나 `main` 브랜치 설명과 고정 소스가 다르면 차이를 보고하고 실제 실행한 version을 우선합니다. 별도 cloud provider의 소스·schema·SDK도 따로 고정해야 합니다.

## 질문별 추적 경로

| 질문 / 모듈 | 고정 구현과 symbol | 확인할 증거 |
| --- | --- | --- |
| unknown한 instance key / TF02 | [eval_for_each.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/terraform/eval_for_each.go): `forEachEvaluator.ResourceValue`, `ensureKnownForResource` | 타입·knownness·민감/ephemeral 제약이 각각 진단되는 위치 |
| block과 instance 구분 / TF03·TF07 | [expander.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/instances/expander.go): `Expander`, `SetResourceForEach`; [resource.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/addrs/resource.go): `ResourceInstance`, `AbsResourceInstance` | module path·key·resource type/name과 unknown expansion의 구분 |
| 참조 edge / TF03 | [transform_reference.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/terraform/transform_reference.go): `ReferenceTransformer`, `ReferenceMap` | 참조 추출과 연결, 명시 의존과 값 의존의 역할 |
| plan/apply 그래프 / TF03 | [graph_builder_plan.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/terraform/graph_builder_plan.go): `PlanGraphBuilder.Steps`; [graph_builder_apply.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/terraform/graph_builder_apply.go): `ApplyGraphBuilder.Steps` | transformer 순서·resource expansion·destroy edge 차이 |
| Core/provider 경계 / TF04 | [provider.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/providers/provider.go): `Interface`, request/response 타입 | schema·read·plan·apply 계약과 실제 원격 API 구현의 부재 |
| 계보·버전 비교 / TF05 | [lineage.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/states/statemgr/lineage.go): `NewLineage`; [migrate.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/states/statemgr/migrate.go): `SnapshotMeta.Compare` | 다른 계보와 이전·이후 snapshot 구분, 메타데이터 없는 경우 |
| 계획된 state 쓰기 / TF05 | [plan.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/states/statemgr/plan.go): `PlannedStateUpdate`, `WritePlannedStateUpdate` | lineage/serial 불일치 거부와 state manager 지원 범위 |
| lock 계약 / TF05·TF12 | [locker.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/states/statemgr/locker.go), [lock.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/states/statemgr/lock.go) | interface와 backend별 구현을 나눠 읽기; 원격 프로토콜까지 추정 금지 |
| saved plan 구성 / TF06 | [writer.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/plans/planfile/writer.go): `CreateArgs`, `Create` | 구성 snapshot·계획·상태 관련 payload와 민감 artifact 취급 |
| JSON의 unknown·sensitive / TF06 | [jsonplan/plan.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/command/jsonplan/plan.go): `Change`, `Marshal`, `MarshalResourceChanges` | before/after 값과 별도 mask를 함께 해석; mask가 encryption은 아님 |

이 표는 entry point입니다. 한 symbol에서 5단계 이상 무작정 확장하지 말고 실제 실험의 호출 경로와 실패 분기만 좁혀 읽습니다. runtime state 파일을 손으로 수정해 소스 가설을 검증하지 않습니다.

## 검증된 회귀 테스트 위치

| 테스트 파일 | 실제 존재하는 시작점 | 연구 과제 |
| --- | --- | --- |
| [eval_for_each_test.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/terraform/eval_for_each_test.go) | `TestEvaluateForEachExpression_errors`, `TestEvaluateForEachExpression_allowUnknown` | 같은 map에서 keys/values knownness를 바꾸면 무엇이 달라지는가 |
| [graph_builder_plan_test.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/terraform/graph_builder_plan_test.go) | `TestPlanGraphBuilder_forEach` | 블록 하나와 instance 여러 개의 graph 차이 |
| [context_plan_test.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/terraform/context_plan_test.go) | `TestContext2Plan_moduleCycle`, `TestContext2Plan_createBefore_deposed` | cycle와 deposed 객체의 계획 경계 |
| [context_apply_test.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/terraform/context_apply_test.go) | `TestContext2Apply_stop`, `TestContext2Apply_createBeforeDestroy` | 취소·replacement의 기대 state와 테스트 provider의 한계 |
| [migrate_test.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/states/statemgr/migrate_test.go) | `TestCheckValidImport` | state snapshot import 검증이며 resource import와 같은 기능이 아님 |
| [jsonplan/plan_test.go](https://github.com/hashicorp/terraform/blob/ef47237fd0e03d6e93bdc510b526287f06e94c03/internal/command/jsonplan/plan_test.go) | `TestOmitUnknowns`, `TestUnknownAsBool`, `TestOutputs` | JSON 값 표현과 unknown mask가 왜 따로 필요한가 |

Go 환경과 고정 source checkout을 별도로 준비한 학습자는 `go test ./internal/terraform -run '^TestEvaluateForEachExpression_errors$' -count=1`처럼 작은 테스트부터 선택합니다. dependency 다운로드 가능성·toolchain·실행 시간·실제 결과를 기록하고, 이 저장소의 Python 테스트 통과와 혼동하지 않습니다. 외부 provider acceptance test는 기본 경로에 넣지 않습니다.

## 공식 자료 읽기 순서

1. TF01–TF02: [내장 terraform_data](https://developer.hashicorp.com/terraform/language/resources/terraform-data), [타입과 값](https://developer.hashicorp.com/terraform/language/expressions/types), [for_each](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each), [try](https://developer.hashicorp.com/terraform/language/functions/try), [can](https://developer.hashicorp.com/terraform/language/functions/can).
2. TF03–TF04: [dependency graph](https://developer.hashicorp.com/terraform/internals/graph), [plugin 동작](https://developer.hashicorp.com/terraform/plugin/how-terraform-works), [plugin protocol](https://developer.hashicorp.com/terraform/plugin/terraform-plugin-protocol). 교육용 graph 설명의 node 명칭과 실제 version의 구현 타입을 구분합니다.
3. TF05–TF06: [locking](https://developer.hashicorp.com/terraform/language/state/locking), [dependency lock](https://developer.hashicorp.com/terraform/language/files/dependency-lock), [plan](https://developer.hashicorp.com/terraform/cli/commands/plan), [JSON](https://developer.hashicorp.com/terraform/internals/json-format), [민감 데이터](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).
4. TF07–TF08: [module provider 전달](https://developer.hashicorp.com/terraform/language/modules/develop/providers), [refactoring](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring), [lifecycle](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle), [import](https://developer.hashicorp.com/terraform/language/import), [removed](https://developer.hashicorp.com/terraform/language/block/removed).
5. TF09–TF12: [validation](https://developer.hashicorp.com/terraform/language/validate), [tests](https://developer.hashicorp.com/terraform/language/tests), [mocks](https://developer.hashicorp.com/terraform/language/tests/mocking), [CLI config](https://developer.hashicorp.com/terraform/cli/config/config-file), [workspaces](https://developer.hashicorp.com/terraform/language/state/workspaces), [backend](https://developer.hashicorp.com/terraform/language/backend).

## 연구 노트 최소 형식

`질문 / 관찰 / revision / source path+symbol / 입력 / 예상 분기 / 실제 결과 / 반례 / provider·backend 미검증 / 수정안`을 남깁니다. 학술 논문처럼 가정과 불변식을 쓰되 Terraform이 임의의 분산 transaction이나 consensus를 구현한다고 확장 해석하지 않습니다. 문서·실제 CLI·mock Core 테스트·cloud 실측의 증거 강도를 각각 표시하는 것이 전문가 수준의 핵심입니다.
