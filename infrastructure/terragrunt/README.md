# Terragrunt: Zero to Research-grade Infrastructure Orchestration

Terragrunt를 설정 중복 제거 도구로만 배우지 않습니다. **HCL 평가 → unit 발견 → 의존성 그래프 → 실행 큐 → 여러 state의 부분 성공 → 복구**를 설명하고, 변경 영향 범위와 승인 경계를 검증하는 28주 심화 과정입니다. 과정 수료는 모든 운영 환경의 전문성을 보장하지 않으며 제출한 증거 범위만 인증합니다.

[28주 커리큘럼](curriculum.md) · [평가 기준](assessment.md) · [운영·트러블슈팅](operations.md) · [고정 소스 지도](source-reading.md) · [로컬 실습](labs/README.md) · [선택 원리 모형](../shared/labs/README.md)

## 시작 조건과 버전

- Git, shell, 디렉터리·프로세스·환경 변수, JSON/HCL의 기본 문법을 알아야 합니다. Terraform plan/state/module을 먼저 [Terraform 과정](../terraform/README.md)에서 학습합니다.
- 학습 기준은 **Terragrunt 1.1.6 + Terraform 1.16.5**입니다. Terragrunt 공식 release API가 2026-10-04에 반환한 최신 안정판은 `v1.1.6`이며 `v1.2.0-rc1`은 제외했습니다. [공식 릴리스](https://github.com/gruntwork-io/terragrunt/releases/tag/v1.1.6)
- Terraform과 OpenTofu는 선택 가능한 서로 다른 engine입니다. 이 과정은 Terraform을 명시적으로 선택하고 실제 executable·version을 기록합니다. Terragrunt 버전만 고정하고 engine을 PATH 탐색에 맡기지 않습니다.
- 문서는 업데이트될 수 있으므로 [source-reading.md](source-reading.md)의 commit을 기준으로 동작을 대조합니다. 최신 문서에 보이는 실험 기능을 1.1.6의 안정 기능으로 간주하지 않습니다.

## 안전 경계

**`run --all`의 apply/destroy는 기본적으로 Terraform에 `-auto-approve`를 추가합니다.** unit마다 확인 질문이 나올 것이라 기대하지 마세요. 이 저장소는 전체 환경 apply/destroy 명령을 시작 명령으로 제공하지 않습니다. `--no-auto-approve` 옵션 하나가 조직의 변경 승인·대상 검증·복구 절차를 대체하지도 않습니다. [공식 run 경고](https://docs.terragrunt.com/reference/cli/commands/run/)

`plan`도 무해한 텍스트 해석이 아닙니다. HCL의 `run_cmd`, hook, provider/data source, source 다운로드, backend 초기화 및 인증 과정이 실행될 수 있습니다. 처음 받은 설정을 클라우드 자격 증명이 있는 shell에서 실행하지 않습니다. backend 생성·migration·강제 unlock·state push·cache 정리는 기본 실습에 포함하지 않습니다.

## 학습 지도

| 강의 | 모듈 | 검증할 관계 |
| --- | --- | --- |
| [01. 평가·구성](lessons/01-evaluation-composition.md) | TG01–02 | module/unit/stack, include·locals·다단계 평가, merge |
| [02. 의존성·큐](lessons/02-dependency-queue.md) | TG03–04 | 현재 outputs, mock 경계, 두 DAG, 실패 전파·부분 성공 |
| [03. 실행 디렉터리·state](lessons/03-cache-backend.md) | TG05–06 | source·cache·lock file, backend identity·bootstrap·복구 |
| [04. stack·변경 영향](lessons/04-stacks-blast-radius.md) | TG07–08 | 생성된 unit, graph closure, 공유 설정·삭제·filter 부정 시험 |
| [05. 실행 보안](lessons/05-effects-security.md) | TG09–10 | hook·retry·멱등성, OIDC·신뢰 경계·공급망 |
| [06. 전달·복구](lessons/06-delivery-recovery.md) | TG11–12 | artifact별 승인, 다중 state rollout, 관측·DR·비용 |
| [07. 소스·최소 연구](lessons/07-research-capstone.md) | TG13–14 | 반증 가능한 가설, 회귀 테스트, 2주 미니 캡스톤 |

## 제공 코드와 학습자 확장

[로컬 Terragrunt fixture](labs/README.md)에서 실제 engine·CLI를 준비하여 두 unit의 정상 결과를 확인한 뒤, [운영 실습](operations.md)에서 unit별 시간·선택/실행/실패 집합·dependency·state를 진단합니다. 7개 강의의 확장 실험은 학습자가 구현·수행할 과제이며 모두 완성된 executable로 제공되지는 않습니다. 기본 환경은 cloud 자원을 만들지 않습니다.

[공통 원리 모형](../shared/labs/README.md)은 graph·plan policy·state CAS·변경 영향 범위를 보충하는 선택 부록입니다. 실제 Terragrunt parser/queue/backend가 아니며 운영 실습의 선수 조건이나 완료 증거가 아닙니다.

완료 상태는 `OFFLINE`, `LOCAL-TERRAGRUNT`, `CLOUD-DESIGN`, `CLOUD-VERIFIED`로 구분합니다. CPU 테스트 성공을 실 engine·클라우드의 lock 내구성, IAM 거부, 복구 성공이라고 보고하지 않습니다. 14모듈 × 2주, 주 12시간으로 약 336시간이며 [8주 인프라 통합 캡스톤](../../capstones/reproducible-infrastructure.md)은 별도 선택 과정입니다.
