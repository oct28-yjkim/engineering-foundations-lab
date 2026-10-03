# 02. 의존 그래프와 provider 경계

[과정](../curriculum.md) · [소스 지도](../source-reading.md)

<a id="tf03"></a>
## TF03 — 블록이 아니라 instance와 작업을 추적한다

### 원리

파일 순서가 실행 순서를 정하지 않습니다. 참조는 의존 관계를 만들고 `depends_on`은 값 참조로 드러나지 않는 의존을 표현합니다. 그러나 과도한 module 수준 의존은 필요 이상의 대기·unknown을 만들 수 있습니다. resource 블록, `count`/`for_each` instance, provider configuration, 생성·파괴 작업을 따로 그립니다. plan용 그래프와 apply용 그래프는 같은 입력·같은 node 집합을 보장하지 않습니다. replacement에는 create와 destroy의 순서 제약이 추가됩니다. [공식 그래프 설명](https://developer.hashicorp.com/terraform/internals/graph)을 고정 구현과 대조합니다.

`-parallelism`은 실행 가능한 그래프 작업의 동시성 제한이지 전체 클라우드의 API rate limiter가 아닙니다. provider 내부 retry·추가 호출·다른 runner의 요청은 별도입니다. 순환이 없다는 사실도 권한·quota·외부 API 성공을 보장하지 않습니다.

### 실험

1. 공통 [graph CPU 모형](../../shared/labs/README.md)의 edge 방향과 출력 의미를 먼저 적습니다. topology가 같은 여러 유효 순서가 존재함을 확인합니다.
2. native 확장에서는 내장 resource 4개로 diamond 구조를 만듭니다. reference 하나를 제거한 경우, 명시 의존을 추가한 경우, cycle을 넣은 경우를 비교합니다.
3. 계획의 주소 집합과 자신의 예상 DAG를 대조합니다. GUI의 그림만으로 실제 scheduling 시간을 측정했다고 하지 않습니다.
4. replacement를 “node 하나 업데이트”로 그린 단순 모델이 생성 전 파괴와 파괴 전 생성의 차이를 표현하지 못함을 보입니다.

제출은 두 DAG, cycle 경로, 유효 부분 순서, 실제 관측/추론 구분입니다. SOURCE에서는 `PlanGraphBuilder.Steps`와 `ApplyGraphBuilder.Steps`의 transformer 순서 중 reference·provider·destroy edge를 연결합니다. “의존이 없는 두 객체 중 누가 먼저 실행되는가?”에 단정적인 파일 순서를 답하면 재학습합니다.

<a id="tf04"></a>
## TF04 — Core는 클라우드 API 자체가 아니다

### 원리

Core는 구성 평가, graph, 계획·상태와 plugin 연결을 담당합니다. provider는 schema, validation, read/plan/apply 등 계약에 따라 특정 시스템의 의미를 구현합니다. 같은 속성 변화도 provider의 schema와 계획 수정 로직에 따라 update 또는 replacement가 될 수 있습니다. 단순화한 흐름은 `schema/validation → refresh/read → plan → apply → state update`이지만 data source 지연, unknown, 재시도, import, ephemeral 동작 때문에 실제 RPC가 항상 이 순서로 한 번씩만 발생하지는 않습니다. [plugin 구조](https://developer.hashicorp.com/terraform/plugin/how-terraform-works)와 [protocol](https://developer.hashicorp.com/terraform/plugin/terraform-plugin-protocol)을 읽습니다.

읽기라고 불리는 동작도 자격 증명 획득·외부 프로세스·네트워크를 사용할 수 있습니다. provider와 configuration을 신뢰하지 않는 상태에서 plan을 보안 검증용 무해한 실행으로 취급하지 않습니다. logging은 합성 fixture에서도 token·환경 변수를 누출하지 않도록 검토합니다.

### 연구 실험

1. `terraform providers schema -json`을 승인된 로컬 fixture에서 관찰하고 required/optional/computed/sensitive 등 schema 정보를 분류합니다. schema JSON만으로 모든 원격 API 제약을 안다고 가정하지 않습니다.
2. 고정 Core의 `providers.Interface`에서 `GetProviderSchema`, `ReadResource`, `PlanResourceChange`, `ApplyResourceChange`의 요청·응답을 추적합니다. 예상 state와 실제 반환 state의 합치 조건을 질문합니다.
3. 별도 SOURCE 과제에서는 기존 fake/mock provider를 이용하는 Core 회귀 테스트 한 개를 실행합니다. 실제 cloud provider 다운로드·계정 호출 없이 실패 분기를 설명합니다.
4. 시간 초과 뒤 API 요청이 실제 성공했을 가능성과, read 후 외부 변경이 생기는 간격을 순서도로 작성합니다. 바로 재시도하면 중복 객체가 생길 조건과 provider가 확인해야 할 identity를 적습니다.

산출물은 Core/provider/API 세 경계와 5개 이상 메시지의 trace입니다. 내부 RPC 이름을 외워도 실패 후 실제 객체와 state가 다를 수 있음을 설명하지 못하면 통과하지 않습니다. SOURCE mock 성공은 해당 cloud API의 멱등성 검증이 아닙니다.
