# Terragrunt 고정 소스와 공식 자료 지도

[과정](README.md) · [TG13 연구 방법](lessons/07-research-capstone.md#tg13)

확인일: **2026-10-04**. 공식 GitHub release API의 latest stable은 [v1.1.6](https://github.com/gruntwork-io/terragrunt/releases/tag/v1.1.6), 공개 시각은 2026-09-21 13:27:08 UTC였습니다. tag ref는 직접 commit **`be24121b42597ca0ba9b311e76961927b91a5b30`**을 가리킵니다. 아래 파일은 이 commit의 Git tree와 raw source로 존재를 확인했습니다. prerelease v1.2.0-rc1과 최신 main은 baseline이 아닙니다.

## 읽기 순서와 증명할 주장

| 순서 / 모듈 | 고정 소스 | 읽을 symbol·질문 |
| --- | --- | --- |
| 1 / TG01–02 | [pkg/config/config.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/pkg/config/config.go) | `TerragruntConfig`, `ParseConfigFile`, `ParseConfig`; 값은 언제 사용할 수 있는가? |
| 2 / TG02 | [pkg/config/include.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/pkg/config/include.go) | `handleInclude`, `Merge`, `DeepMerge`, `deepMergeInputs`; block과 inputs 차이 |
| 3 / TG03 | [pkg/config/dependency.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/pkg/config/dependency.go) | `Dependency`, `decodeAndRetrieveOutputs`, `shouldReturnMockOutputs`, `getTerragruntOutputIfAppliedElseConfiguredDefault`; output의 출처 |
| 4 / TG04 | [internal/queue/queue.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/queue/queue.go) | `Entry`, `Queue`, `GetReadyWithDependencies`, `FailEntry`; blocked와 terminal 전이 |
| 5 / TG04·11 | [internal/runner/runner.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/runner/runner.go) | `Runner.Run`, `FilterDiscoveredUnits`; 발견·선택·실행 분리 |
| 6 / TG05 | [internal/runner/run/download_source.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/runner/run/download_source.go), [internal/tf/source.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/tf/source.go) | `DownloadTerraformSource`, `AlreadyHaveLatestCode`, source path/identity |
| 7 / TG05·09 | [internal/runner/run/run.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/runner/run/run.go) | `Run`, `ShouldCopyLockFile`, `RunActionWithHooks`, `SetTerragruntInputsAsEnvVars`; engine 경계 |
| 8 / TG06·12 | [internal/remotestate/remote_state.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/remotestate/remote_state.go) | `RemoteState`, `NeedsBootstrap`, `Bootstrap`, `Migrate`; 작업별 부작용·권한 |
| 9 / TG07–08 | [internal/discovery/phase_graph.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/discovery/phase_graph.go), [internal/filter/filter.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/filter/filter.go) | package 함수 `Parse`, 메서드 `(*Filter).Evaluate`와 graph 발견 |

source table은 호출 순서의 완전한 call graph가 아니며 각 과제에서 실제 caller와 조건 분기를 추가해야 합니다. provider/backend 구현의 의미는 이 repository 밖의 engine·SDK·서비스 문서도 확인해야 합니다.

## 테스트와 짝짓기

- [config_test.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/pkg/config/config_test.go), [include_test.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/pkg/config/include_test.go): parsing·merge 가정이 깨지는 최소 fixture.
- [dependency_test.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/pkg/config/dependency_test.go): 실제 outputs·mock·cycle의 조건 차이.
- [queue_test.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/queue/queue_test.go), [runner_test.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/runner/runner_test.go): partial order·실패 상태·실행 대상.
- [filter_test.go](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/internal/filter/filter_test.go): 선택 집합과 graph traversal 반례.

테스트 이름 하나·입력·기대값·대상 함수를 연결하고 음성 대조군을 추가합니다. 파일 존재 확인은 테스트 실행 확인이 아닙니다. 이 문서 작성 과정에서 upstream Go suite는 실행하지 않았으며 cloud integration test를 기본 실행 명령으로 제시하지 않습니다.

## 버전 고정 문서

공식 웹 문서는 갱신됩니다. 설명이 다를 때 다음 release snapshot으로 baseline을 확인합니다.

- [HCL parsing overview](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/docs/src/content/docs/04-reference/01-hcl/01-overview.mdx)
- [HCL blocks](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/docs/src/content/docs/04-reference/01-hcl/02-blocks.mdx)
- [run command](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/docs/src/content/docs/04-reference/02-cli/02-commands/0100-run.md)
- [Run Queue](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/docs/src/content/docs/03-features/02-stacks/06-run-queue.mdx)
- [Graph filters](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/docs/src/content/docs/03-features/08-filter/05-graph.mdx)
- [Lock files](https://github.com/gruntwork-io/terragrunt/blob/be24121b42597ca0ba9b311e76961927b91a5b30/docs/src/content/docs/03-features/01-units/12-lock-files.mdx)

1.1.6 baseline에서 bounded-discovery 등의 experiment를 안정 기능으로 간주하지 않습니다. source-only 비교를 위해 읽는 기능과 실제 fixture가 사용하는 기능도 구분합니다.

## 이론·공식 자료를 실험으로 연결하기

| 자료 | 읽기 목적 | 직접 구성할 반례 |
| --- | --- | --- |
| [Build Systems à la Carte, ICFP 2018](https://www.microsoft.com/en-us/research/publication/build-systems-la-carte/) · [저자 제공 논문 PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf) | scheduling과 rebuilding 판단을 분리 | graph 순서는 맞지만 shared-input 변경 unit을 누락한 실행 |
| [Graph filter 공식 설명](https://docs.terragrunt.com/features/filter/graph/) | dependency/dependent 방향·선택 집합 | target 양쪽 closure와 exact 승인 집합이 다른 경우 |
| [Authentication](https://docs.terragrunt.com/features/units/authentication/) | engine/provider/backend/helper 신원 구분 | planner가 bootstrap 권한까지 가진 과권한 설계 |
| [Hooks](https://docs.terragrunt.com/features/units/hooks/) · [Functions](https://docs.terragrunt.com/reference/hcl/functions/) | parse/plan 실행의 부작용 | 효과 기록 뒤 timeout이 발생한 재시도 |

논문은 비교 관점이며 제품의 보증 명세가 아닙니다. 과제에는 원저자의 가정, 본인 모형의 단순화, 실제 engine에서 확인한 범위, 아직 확인하지 않은 cloud 효과를 각각 적습니다.
