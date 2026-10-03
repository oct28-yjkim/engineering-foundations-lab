# 01. 선언형 구성과 값의 의미

[과정](../curriculum.md) · [로컬 실습](../labs/README.md)

<a id="tf01"></a>
## TF01 — 선언은 명령 목록이 아니다

### 핵심 원리

구성은 원하는 객체와 관계를 기술합니다. state는 구성 주소와 관리 객체의 binding 및 관측 정보를 유지하고, provider가 실제 시스템을 읽거나 변경합니다. plan은 이 입력을 비교해 제안한 실행이며 실제 시스템의 모든 미래 변화를 고정하지 않습니다. “같은 HCL을 반복하면 항상 같은 결과”에는 외부 drift, provider 버전, 동적 입력, 권한, API 가용성이 같다는 전제가 숨어 있습니다.

처음에는 provider 설치가 없는 `terraform_data` fixture로 input과 output, 계획과 적용 후 값의 차이를 읽습니다. 이 내장 resource의 상태 변화는 클라우드 API의 eventual consistency를 재현하지 않습니다. `init`, `validate`, `plan`, `apply`가 각각 어떤 파일·plugin·state·API에 접근하는지 별도 원장으로 작성합니다. `validate` 성공이 운영 자격 증명·quota·API의 성공을 증명하지는 않습니다. [내장 resource](https://developer.hashicorp.com/terraform/language/resources/terraform-data)와 [validate](https://developer.hashicorp.com/terraform/cli/commands/validate)를 참고합니다.

### 실험과 반례

1. 제공 로컬 fixture를 별도 작업 폴더로 복사하는 실습 안내를 따릅니다. 처음에는 실제 CLI 없이 구성·예상 값만 읽어도 됩니다.
2. 각 객체의 `address / intended input / observed output / operation`을 손으로 예측합니다. 최초 생성, 같은 입력 재계획, 입력 변경의 세 경우를 비교합니다.
3. 작은 속성 하나만 바꿨을 때 전체 resource 교체인지 in-place 변경인지 provider schema와 계획을 보고 판단합니다. 문자열 diff 길이로 결정하지 않습니다.
4. 잘못된 변수 타입, 의도하지 않은 instance 추가를 음성 대조군으로 넣습니다. “exit 0이면 안전” 검사와 주소별 예상 원장 검사를 비교합니다.

산출물은 네 개의 분리된 원장(config/state/observed object/plan)과 미실행 경계입니다. 구술 질문: “상태에 없지만 실제 존재하는 객체를 구성에 추가하면 자동으로 소유권이 발견되는가?” 자동 발견을 전제하지 않고 import·identity의 검토로 연결하면 통과합니다.

<a id="tf02"></a>
## TF02 — HCL, 타입, null과 unknown

### 핵심 원리

HCL의 표현식 결과를 타입과 값으로 읽습니다. 문자열·숫자·bool뿐 아니라 object/map, tuple/list/set이 서로 다른 제약을 갖습니다. 구성의 `null`은 생략 의미로 쓰일 수 있지만 provider의 필수·선택·계산 속성 및 변수의 nullable/default 조건에 따라 결과가 달라집니다. unknown은 값이 아직 결정되지 않았다는 뜻이며 null, 오류, 빈 컬렉션과 다릅니다. Core가 쓰는 cty 수준에서는 타입을 가진 null/unknown을 구분하므로 사용자 문법의 단순 설명을 내부 표현에 그대로 대입하지 않습니다. [타입](https://developer.hashicorp.com/terraform/language/expressions/types)과 [cty 값 모델](https://github.com/zclconf/go-cty/blob/main/docs/types.md)을 함께 읽습니다.

knownness는 객체 전체와 leaf가 다를 수 있습니다. 키 집합은 알려졌지만 그 값이 아직 unknown인 map과, 키 집합 자체가 unknown인 map을 구분합니다. `for_each` instance key가 계획 단계에서 결정되어야 하는 이유는 stable address를 구성해야 하기 때문입니다. 비밀 값으로 instance key를 만들면 주소 노출과 평가 제한도 생깁니다. [for_each](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each)의 제한을 확인합니다.

### 작은 실험

| 입력 조건 | 미리 예측할 것 | 반례 |
| --- | --- | --- |
| `null`, 빈 문자열, 빈 list | 생략·실제 값·collection cardinality | 세 경우를 모두 기본값으로 치환 |
| known keys + unknown values | instance 주소를 알 수 있는가 | 값 unknown을 이유로 모든 구조가 unknown이라고 단정 |
| unknown keys | 계획에서 identity를 결정할 수 있는가 | 나중에 알 값으로 `for_each` 키 구성 |
| 숫자와 숫자 문자열 | type constraint 변환과 equality | 변환 가능한 값은 항상 `==`도 같다는 주장 |

LOCAL-TERRAFORM에서는 `terraform console`과 plan JSON의 `after_unknown`을 합성 값으로 관찰합니다. 실제 unknown 생성은 fixture의 computed output을 이용하고, Python의 `None`을 Terraform unknown이라고 부르지 않습니다. `try`/`can`은 모든 unknown을 기본값으로 바꾸는 연산자가 아니므로 오류·unknown 사례를 분리해 추가 검증합니다.

산출물은 최소 8개 입력의 타입/knownness/결과 표와 예상 실패 사례 2개입니다. SOURCE 확장에서는 [소스 지도](../source-reading.md)의 평가·instance expansion 경로를 따라 동일 현상이 어디서 진단되는지 찾습니다. 구술에서 “unknown이 false가 아닌 이유”를 plan 승인 정책의 fail-closed 조건으로 연결합니다.
