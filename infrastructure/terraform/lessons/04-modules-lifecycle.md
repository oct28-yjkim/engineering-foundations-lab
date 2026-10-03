# 04. Module API, identity, 안전한 이관

[과정](../curriculum.md) · [소스 지도](../source-reading.md)

<a id="tf07"></a>
## TF07 — module은 복사 방지가 아니라 변경 계약이다

### 원리

resource의 구성 이름, instance key, provider 원격 ID, 업무 key는 서로 다릅니다. `count`의 index는 입력 list의 업무 의미를 기억하지 않습니다. `for_each`의 stable key는 재정렬에 강하지만 key 자체 변경이 자동 rename을 뜻하지도 않습니다. module path도 주소 일부이므로 디렉터리 정리처럼 보이는 리팩터링이 상태 주소 변경을 만들 수 있습니다. [reference 의미](https://developer.hashicorp.com/terraform/language/expressions/references)와 [module composition](https://developer.hashicorp.com/terraform/language/modules/develop/composition)을 연결합니다.

module API에는 type, validation, nullable/default, output 의미, provider alias 계약, 허용 upgrade 경로를 포함합니다. provider configuration은 root에서 관리하고 필요한 alias를 명시적으로 전달하는 설계를 검토합니다. child가 받을 provider requirement와 실제 configuration을 혼동하지 않습니다. registry module의 버전 또는 Git source의 불변 revision을 별도로 고정해야 하며 provider lock file이 module source를 모두 잠그지는 않습니다.

### Identity 실험

1. 합성 tenant `alpha`, `beta`, `gamma`를 `count` 방식으로 모델링하고 첫 항목을 제거합니다. 주소, 업무 tenant, input 변화, 계획 action을 각각 적습니다. 모든 resource가 반드시 교체된다고 단정하지 않습니다.
2. 같은 입력을 key map으로 표현하고 순서만 바꿉니다. 이후 `beta`를 `delta`로 key 변경해 안정성의 한계를 관찰합니다.
3. 단일 root의 두 module call에 같은 local module을 전달합니다. `path.module`에 쓰는 설계가 공유 source 경로에서 충돌할 수 있음을 설명하고, output/state와 artifact 저장 위치를 분리합니다.
4. 정상 입력·알 수 없는 key·선택 속성 null·중복 업무 ID의 계약 테스트를 설계합니다. address만 다르면 중복 업무 객체가 안전하다는 주장을 기각합니다.

제출은 변경 전후 3종 identity 매핑과 version upgrade 계약입니다. SOURCE에서는 instance expansion과 address 구조를 읽습니다. 기본 fixture를 넘는 module API 실험은 학습자 구현 과제이며 제공 CLI 예제의 자동 검증 범위가 아닙니다.

<a id="tf08"></a>
## TF08 — lifecycle과 소유권 이동

### 원리

`create_before_destroy`는 graph의 순서를 바꾸지만 quota·고유 이름 충돌·데이터 이관을 해결하지 않습니다. `prevent_destroy`는 해당 규칙이 구성에 존재할 때의 보호이며 모든 외부 삭제나 구성 제거를 영구 차단하는 방패가 아닙니다. `ignore_changes`는 소유권 공유를 의도적으로 설계할 때 쓰고 drift를 숨기는 만능 해결책으로 쓰지 않습니다. [lifecycle](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle)을 확인합니다.

import는 기존 객체를 관리 주소에 연결하는 과정입니다. import 후 구성과 원격 값이 다르면 후속 plan에 변경이 생길 수 있습니다. `moved`는 state 주소 이관을 기록하지만 원격 데이터 복사나 모든 resource type 변환을 보장하지 않습니다. `removed`에서는 destroy 여부를 명시적으로 검토합니다. `destroy = false`는 실물을 보존한 채 관리에서 제외하는 의도이며 “리소스가 사라졌다”와 반대일 수 있습니다. [import](https://developer.hashicorp.com/terraform/language/import), [moved](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring), [removed](https://developer.hashicorp.com/terraform/language/block/removed)를 대조합니다.

### 이관 실험

1. 별도 local fixture 사본의 기존 `terraform_data` 주소를 변경하는 과제를 만듭니다. 먼저 moved 없는 계획을 읽고 적용하지 않습니다. moved를 추가한 계획의 이전/새 주소와 예상 원격 또는 합성 ID 보존을 확인합니다.
2. 이름 변경과 속성 변경을 같은 단계에 섞지 않습니다. 주소 이관만 한 baseline 뒤 별도 입력 변경을 계획해 원인을 구분합니다.
3. 제거 과제는 local state의 내장 resource에 한정하거나 설계로 남깁니다. removed 여부·destroy 설정·잔존 binding을 검산합니다. 운영 객체에 state rm/destroy를 연습하지 않습니다.
4. import 확장은 실제 resource type이 지원하는 ID/identity를 먼저 확인합니다. 기존 객체를 두 state가 동시에 소유하지 않도록 freeze→검증→소유권 이동→후속 계획을 설계합니다.

산출물은 객체별 `old address → new address → same identity? → action → owner` 원장입니다. “리팩터링이라 안전” 대신 의도하지 않은 delete/replacement 0건과 실제 binding 보존을 검산해야 합니다. 다른 state로 이동하는 과제는 단일 moved block의 효과로 일반화하지 않고 별도 승인된 migration으로 취급합니다.
