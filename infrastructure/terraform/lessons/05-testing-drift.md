# 05. 테스트의 경계와 부분 성공

[과정](../curriculum.md) · [평가](../assessment.md)

<a id="tf09"></a>
## TF09 — 테스트라는 이름이 실행 위험을 없애지 않는다

### 원리

`terraform test`의 run은 기본적으로 apply입니다. cloud provider가 포함된 미검토 테스트를 실행하면 실제 리소스·비용이 생길 수 있습니다. `command = plan`은 생성 적용과 다르지만 provider 초기화·read·data source 등의 실행 경계를 없애지 않습니다. mock provider는 응답을 대체하는 시험 수단이고 API·권한·quota·실제 실패를 검증하지 않습니다. [tests](https://developer.hashicorp.com/terraform/language/tests)와 [mocking](https://developer.hashicorp.com/terraform/language/tests/mocking)을 읽고 시작합니다.

검증 계층을 나눕니다: 문법/타입, 입력 계약, planned action, 적용 후 결과, API 통합, 복구·잔존 객체. `check`의 비차단적 진단과 validation/precondition/test assert 등 다른 실패 효과도 구별합니다. provider mock을 사용하더라도 모든 provider alias와 실제 실행 경로가 mock 처리됐는지 확인해야 합니다. mock만으로 필요한 plugin schema 설치까지 항상 생략된다고 가정하지 않습니다.

### 실험

1. 제공 native fixture의 `.tftest.hcl`에서 모든 `run`의 command와 사용 resource를 먼저 목록화합니다. 실행 여부는 실습 안내의 사전 조건을 따릅니다.
2. 올바른 입력과 틀린 입력, 예상 output·주소 집합을 작성합니다. 정상 테스트만 통과하는 구현을 deliberately 잘못된 입력으로 깨뜨립니다.
3. 학습자 확장으로 plan-only 테스트와 mock 기반 테스트를 각각 하나 작성합니다. computed 값의 mock default에 기대지 말고 필요한 값을 명시합니다.
4. unsupported type·잘못된 instance key·예상하지 않은 replacement를 음성 대조군으로 둡니다. assert가 확인하는 필드가 actual 값이 아니라 자기 입력 복사본이면 검증의 공백을 기록합니다.

test의 임시 state와 자동 cleanup 의도를 이해하되, 비정상 종료·cleanup 실패 후 실제 잔존 객체가 없다고 가정하지 않습니다. 실클라우드 확장에는 종료 후 객체 원장과 비용 잔여 확인이 필요합니다. 산출물은 테스트 계층별 보장/비보장 표와 실패해야 하는 테스트 3개입니다.

<a id="tf10"></a>
## TF10 — drift와 실패 후 재시도

### 원리

구성 변경(config↔state), 외부 drift(state↔actual), 관측 시점 차이(read↔apply)를 분리합니다. refresh-only는 발견한 외부 변화를 state에 반영하는 계획 모드이지 원격을 구성대로 복원하는 apply가 아닙니다. `-refresh=false`는 최신 실제 상태를 확인하지 않는 대가가 있고, `-target`은 전체 구성의 정합성을 입증하는 통상 운영 대체물이 아닙니다. [plan 모드와 옵션](https://developer.hashicorp.com/terraform/cli/commands/plan)을 확인합니다.

여러 resource의 apply에는 전역 rollback이 없습니다. 성공한 객체와 실패한 객체가 공존할 수 있으며, API 성공 뒤 응답 유실·state 저장 실패처럼 “무슨 일이 일어났는지 아직 모름”인 경우도 있습니다. 명령 재실행보다 먼저 실제 객체 identity, 변경 기록, state, lock owner를 확인합니다. 완전 no-op 계획도 관리하지 않는 속성·객체의 무결성까지 보증하지 않습니다.

### 실패 원장 실험

1. 4개 객체 중 A·B 성공, C 응답 유실, D 미실행이라는 합성 trace를 작성합니다. C를 실패로 단정하지 않고 미확정 상태로 기록합니다.
2. CPU graph/plan 모형과 별도로 순차 독립 oracle을 작성해 기대 주소·속성을 대조합니다. 제공 모형이 실제 partial apply를 자동 재현하지 않는다는 한계를 표시합니다.
3. LOCAL-TERRAFORM에서는 내장 fixture의 계획 불일치·유효성 실패를 사용합니다. 실 API timeout·원격 drift는 별도 fake provider 또는 승인한 격리 cloud 실험으로만 확장합니다.
4. 수정 후 full plan과 독립 객체 원장을 확인합니다. 일부 target이 성공했다는 이유로 전체 시스템을 정상으로 표시하는 검사를 음성 대조군으로 둡니다.

제출은 실패 시점마다 `known success / known failure / not attempted / uncertain`을 구분한 원장, 중단 조건, 다시 읽기 전략입니다. state를 옛 snapshot으로 바꾸면 실제 A·B도 되돌아간다는 주장을 기각하고 TF12 복구 절차로 연결합니다.
