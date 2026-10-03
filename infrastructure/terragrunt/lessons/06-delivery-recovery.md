# 06. 승인 가능한 변경과 복구 가능한 운영

[과정](../README.md) · [로컬 실습](../labs/README.md)

<a id="tg11"></a>
## TG11 — 승인한 것은 commit인가, 특정 plan인가?

commit 승인, 선택 unit 승인, 정책 통과, plan artifact 승인, 실제 apply identity는 서로 다른 증거입니다. 이 과정은 새로운 local fixture에서 **foundation plan 검토·단위별 적용 → 실제 output 확인 → application 새 plan 검토·단위별 적용** 흐름을 사용합니다. 최초 mock 기반 application plan을 실제 배포 승인으로 승격하지 않습니다.

**위험한 기본값:** `terragrunt run --all`로 apply/destroy를 전달하면 `-auto-approve`가 자동 추가됩니다. 전체 실행과 개별 unit의 interactive 승인 기대를 결합하지 않습니다. 본 과정은 광범위 apply 명령 대신 [실습 문서](../labs/README.md)의 검토된 단일-unit 흐름만 제공합니다. [공식 run](https://docs.terragrunt.com/reference/cli/commands/run/)

### Artifact 승인 계약

| 항목 | 저장할 비밀 없는 식별자 | 바뀌면 필요한 행동 |
| --- | --- | --- |
| 입력 코드 | repo commit·source commit·generated config hash | 다시 계획·정책 검사 |
| 실행 범위 | exact unit set·canonical paths·backend identities | 범위 재승인 |
| 실행 도구 | engine·Terragrunt·provider lock | 호환·공급망 검토와 새 계획 |
| dependency inputs | 실제 output의 schema·비밀 없는 fingerprint | 소비자 재계획 |
| plan | unit별 artifact hash·정책 버전·생성 시각 | 새 artifact 검토 |
| 신원 | planner/applier의 허용된 역할·환경 | 새 권한 검토 |

saved plan은 한 unit의 Terraform 계획입니다. upstream state가 바뀌어도 다른 unit의 saved plan이 자동으로 적절히 갱신되지 않습니다. dependency output은 다른 state이므로 consumer 자신의 state stale 검사만으로 producer 변화가 모두 검출된다고 가정하면 안 됩니다. deployment 직전 dependency contract freshness와 환경 관측을 별도 확인합니다.

### 부정 시험

- 승인 후 plan 파일 한 byte가 바뀌면 실행 전 integrity gate가 거부해야 합니다.
- 같은 commit이지만 다른 root include/env/engine으로 생성한 plan을 승인 artifact로 인정하지 않습니다.
- foundation schema v2를 적용한 뒤 v1 입력으로 저장한 application plan의 재사용을 자체 정책에서 거부합니다.
- units A/B 중 A만 승인했는데 filter가 B까지 선택하면 gate가 실패해야 합니다.
- 정책 검사 오류·unknown value·누락된 policy result를 기본 허용으로 처리하지 않습니다. 공통 `plan-policy` 모형의 범위와 실제 Terraform JSON schema를 구분합니다.

`-detailed-exitcode`는 plan의 무변경/변경/오류를 구분하는 도구이지 승인 정책이 아닙니다. 여러 unit 실행의 aggregate code만 저장하지 말고 unit별 코드·상태를 보존합니다. [Run Report](https://docs.terragrunt.com/features/stacks/run-report/)를 실제 버전에서 대조합니다.

<a id="tg12"></a>
## TG12 — 부분 성공 후 운영은 정합성 문제다

network와 application 두 state가 다를 때 복구 목표는 “명령이 다시 성공”이 아니라 “실제 객체와 각 state의 소유권·output 계약이 일치”입니다. rollback, roll-forward, 재관측, 수동 보상은 선택 가능한 전략이며 자동 동의어가 아닙니다. state backup 복원이 이미 변경된 cloud 객체를 원복하지 않습니다.

### 복구 tabletop과 선택 실습

1. 실패 직전/직후 unit 상태, state fingerprint·lineage·serial, 실제 object identity, dependency output schema를 보존합니다. 비밀 원문은 공개 기록에서 제외합니다.
2. A가 성공하고 B가 실패한 사례에서 B만 재계획할지, A의 호환 output을 유지할지, 별도 보상이 필요한지 결정합니다. A를 즉시 destroy하는 것을 일반 해결법으로 삼지 않습니다.
3. configuration rename과 backend key 변경이 섞인 사례를 분석합니다. 소유권 이전·중복 관리·orphan을 각각 검사합니다.
4. local fixture에서는 작은 state backup을 별도 복구 경로에서 검산하는 과제를 설계합니다. cloud 복구는 명시된 대상·권한·비용·중단 조건이 있는 별도 승인 없이는 실행하지 않습니다.
5. RTO는 장애 인지부터 정합성 oracle 재통과까지, RPO는 잃은 변경/상태 정보의 범위로 정의합니다. 목표값과 실측값을 분리합니다.

### 시간·비용·관측

대기 시간, source/provider 준비, HCL 평가·dependency 조회, plan/apply, retry를 나눠 측정합니다. 병렬도가 커져 전체 latency가 줄어도 API throttle·state contention·실패 확률·CI 분 단위 비용이 늘 수 있습니다. 최소 세 가지 그래프 모양(chain, wide, diamond)을 같은 unit 수에서 비교합니다.

예산은 `허용 unit 수 × unit별 최대 실행/재시도 시간`의 상한부터 설계하고 provider별 생성 자원 한도를 별도로 둡니다. CPU 모형의 가상 비용이나 실행 종료가 실제 cloud 청구 종료를 보장하지 않습니다. 실행 후에도 존재하는 리소스와 retained storage가 있는지 확인해야 합니다.

**제출물:** run ID→unit→engine PID/attempt→state→effect 원장, 정합성 검사, recovery decision tree, 남은 수동 조치입니다. cloud 없이 완료한 경우 IAM/실제 백엔드 장애/청구는 미검증으로 적습니다. [8주 통합 캡스톤](../../../capstones/reproducible-infrastructure.md)은 별도 선택입니다.
