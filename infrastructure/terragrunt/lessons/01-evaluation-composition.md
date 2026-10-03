# 01. 평가 순서와 구성의 경계

[과정](../README.md) · [소스 지도](../source-reading.md) · [로컬 실습](../labs/README.md)

<a id="tg01"></a>
## TG01 — Terraform 밖에 추가된 실행 계층

Terraform module은 `.tf` 구성의 재사용 단위입니다. Terragrunt unit은 engine 실행의 설정 단위이며 보통 독립 state를 가집니다. stack은 unit을 묶거나 생성하는 구성 계층입니다. 디렉터리를 나눈 사실만으로 state가 분리되지 않으며 같은 backend key를 지정한 두 unit은 충돌할 수 있습니다. [공식 용어](https://docs.terragrunt.com/getting-started/terminology/)

실행을 `configuration → discovery/selection → ordered units → engine process → state/provider effects`로 분해합니다. Terraform는 한 root module 내부 resource graph를 평가하고, Terragrunt는 그 engine 실행들 사이의 관계를 관리합니다. 이 계층 추가는 전역 transaction coordinator의 도입이 아닙니다.

### 수행 과제

1. [제공 local fixture](../labs/README.md)를 먼저 읽고 Terraform executable, version, unit 경로, source 경로, engine cwd, state 경로를 빈 표에 예상합니다. engine 선택은 명시적이어야 합니다.
2. 별도 준비된 local 환경에서 단일 unit의 validate/plan을 실행하고 실제 값과 대조합니다. engine/provider 설치나 cloud credential 요청이 나오면 자동 승인하지 말고 실행 범위를 재검토합니다.
3. 출력이 같은 두 unit을 만들더라도 독립 backend identity를 사용합니다. 반대로 같은 key가 발견되면 실행 전에 실패시키는 identity uniqueness 검사 과제를 추가합니다.
4. 읽기 전용 진단, 로컬 파일 작성, provider 호출, remote state 접근을 구분한 effect ledger를 작성합니다. 처음 보는 HCL의 render/discovery도 명령 실행을 포함할 수 있다는 가정을 검사합니다.

**독립 oracle:** unit별 예상 backend identity 목록을 사람이 먼저 작성합니다. 실행 로그의 경로를 그대로 복사해 기대값으로 삼지 않습니다. 제출물은 ID 매핑과 1개 잘못된 backend identity를 잡는 부정 시험입니다.

**구술:** 같은 `.tf` source를 공유하는 두 unit의 plan은 왜 달라질 수 있는가? unit 경로를 rename하면 어떤 identifier가 유지되고 어떤 값이 달라지는가? Terraform binary를 바꿨지만 HCL이 같으면 같은 실험인가?

<a id="tg02"></a>
## TG02 — HCL은 평가 시점이 있는 프로그램이다

단일 구성에서는 include·locals·인증 관련 값·의존성·나머지 표현식의 평가 순서가 중요합니다. locals에서 아직 얻지 않은 dependency output을 사용할 수 없습니다. `--all`은 unit graph 발견을 위한 부분 평가와 unit 실행 시 평가를 나누므로, 첫 pass에서 존재하지 않는 output으로 dependency 경로를 결정하도록 설계하지 않습니다. 정확한 단계는 [공식 parsing order](https://docs.terragrunt.com/reference/hcl/)와 고정 소스를 대조합니다.

공유 파일은 `root.hcl`, 실행 unit은 `terragrunt.hcl`로 구분합니다. root 파일이 실행 unit으로 발견되는 모호함을 제거하는 것이 목적이며 이름 변경만으로 설정이 안전해지지는 않습니다. [root 구성 migration](https://docs.terragrunt.com/migrate/migrating-from-root-terragrunt-hcl/)

### Merge를 손으로 검산하기

다음은 **inputs의 값**을 deep merge할 때의 작은 oracle입니다. 블록 전체와 inputs 값의 규칙을 혼동하지 않습니다.

| 종류 | 부모 / 자식 | 예상 결과 |
| --- | --- | --- |
| scalar | `region="a"` / `region="b"` | `region="b"` |
| list | `zones=["a"]` / `zones=["b"]` | `zones=["a","b"]` |
| map | `{a=1,nested={x=2}}` / `{nested={y=3}}` | `{a=1,nested={x=2,y=3}}` |
| locals | 부모 `local.region` / 자식 locals | 자동 병합 아님; expose된 namespace와 구분 |

`remote_state`·`generate`에는 deep merge 예외가 있습니다. 모든 block이 JSON처럼 재귀 병합된다고 가정하면 backend 설정이 예상과 달라집니다. `expose=true`는 값 참조 기능이지 모든 평가 단계에서 모든 dependency 값이 존재한다는 뜻이 아닙니다. [공식 include·merge 정의](https://docs.terragrunt.com/reference/hcl/blocks/#include)

### 반례 실험과 제출

- 순수 synthetic 설정에서 shallow/deep/no_merge 세 구성을 비교합니다. list에 중복 원소를 넣어 집합 union과 list concatenation을 구별합니다.
- 부모 locals를 자동 상속한다고 가정한 구성을 실패시키고, expose 참조와 이름 충돌의 결과를 명시합니다.
- dependency output을 locals에 연결한 실패를 “값이 빈 경우”와 “평가 순서상 사용할 수 없는 경우”로 구분합니다.
- root 설정 한 줄이 두 환경의 inputs를 바꾸는 예를 만듭니다. DRY의 줄 수 절약과 변경 영향 범위 확대를 동시에 측정합니다.
- 각 출력 값에 origin file·merge rule·evaluation phase를 붙입니다. secret-bearing render 결과를 공개 저장소에 올리지 않습니다.

**소스 과제:** `pkg/config/config.go`, `pkg/config/include.go`, 관련 테스트에서 merge 입력과 결과를 연결합니다. 정적 표와 실제 parser 결과가 다르면 버전·실험 flag·expose·동명 block을 먼저 조사합니다. 실행하지 않았다면 예상 oracle과 설계만 제출합니다.
