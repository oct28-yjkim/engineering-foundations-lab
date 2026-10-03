# Terraform 심화 과정 평가 기준

[커리큘럼](curriculum.md) · [로컬 실습](labs/README.md) · [공통 CPU 실험](../shared/labs/README.md) · [소스 지도](source-reading.md)

총 **80/100 이상·각 영역 15/25 이상·필수 gate 전부 통과**가 선언한 실행 범위의 완료 조건입니다. OFFLINE, LOCAL-TERRAFORM, SOURCE, CLOUD-DESIGN, CLOUD-LAB을 별도로 표시합니다.

| 영역 | 배점 | 기본 증거 | 높은 수준의 증거 |
| --- | --- | --- | --- |
| 정확성 | 25 | 주소·ID·속성·create/update/delete/replacement를 독립 원장과 비교 | migration·부분 성공·재시도 후에도 1:1 소유권과 불변식 보존 |
| 원리/소스 | 25 | HCL/cty→graph→provider→state의 책임 경계 | 고정 revision의 함수·구조·테스트·오류 분기로 관찰 설명 |
| 실험/반증 | 25 | baseline·한 변인·정상/음성 대조군·원시 결과 | unknown·drift·동시 writer·stale artifact의 경쟁 가설 분리 |
| 운영/재현성 | 25 | 고정 도구/의존성·격리 대상·민감 산출물 보호 | 승인 artifact 결박·최소 권한·부분 복구·잔존 객체 검산 |

## 필수 gate

제품 운영 실습에는 [정상 기준선과 서로 다른 두 문제의 진단·회복](operations.md)을 추가로 요구합니다. 명령 결과·원인 구분·조치 전후 plan/state/ID·미검증 범위를 [운영 보고서](../../operations/incident-report-template.md)에 제출합니다. OFFLINE 평가는 원리 학습에 한정되며 실제 CLI/운영 완료를 의미하지 않습니다.

1. **환경과 권한:** 실행 디렉터리·backend·workspace·principal을 구분하고 대상이 격리 실습 범위임을 확인합니다. CLI workspace 이름만으로 prod 접근이 차단됐다고 주장하지 않습니다.
2. **값과 변경:** unknown을 null·false·빈 문자열로 처리하지 않습니다. replace의 두 action 순서를 모두 고려하고 `delete` 한 개만 세는 허술한 판정을 반례로 깨뜨립니다.
3. **상태와 경쟁:** provider lock file과 runtime state lock을 구분합니다. lineage/serial, lock 지원 여부, 외부 API 변경을 각각 설명합니다. CPU CAS 모형을 특정 backend 구현의 실증으로 제출하지 않습니다.
4. **민감 정보:** state·plan·JSON·log를 공개하지 않습니다. `sensitive` 표시는 암호화가 아니며 mock 입력에도 실비밀을 쓰지 않습니다.
5. **실행 위험:** test의 기본 apply, provider/data source/외부 실행 경계, 부분 apply를 설명합니다. “plan이라 안전”이라는 근거로 미검토 코드를 실행하지 않습니다.
6. **복구·정직성:** state rollback과 실물 복원을 분리합니다. 안전한 격리 모형 또는 별도 승인한 실험만 사용하고 미실행 항목을 PASS로 쓰지 않습니다.

## 제출물과 구술

각 모듈은 [실험 보고서](../../databases/shared/templates/experiment-report.md)를 확장한 원장과 경쟁 가설 2개 이상을 제출합니다. 사고 모듈은 [장애 기록](../../databases/shared/templates/incident-review.md)에 실제 변경·중단·복구 권한·잔존 객체를 추가합니다. 각 강의에 제시한 필수 반례 중 하나라도 실패하지 않는 “테스트”는 테스트의 의미부터 재검토합니다.

구술에서는 평가자가 임의 instance 주소 3개를 골라 구성 주소, state binding, provider configuration, 원격 ID, planned action, 실패 후 상태를 추적하게 합니다. 별도 state의 동일 객체 중복 관리를 발견하면 전체 count가 맞아도 정확성 gate를 통과하지 못합니다.

TF14는 한 root module·한 변경·두 실패 조건의 2주 과제입니다. provider 개발·멀티 클라우드 구축·CI 플랫폼 운영을 동시에 요구하지 않습니다. 실제 CLI가 없다면 OFFLINE 연구까지만 통과하고 native 실행은 미검증으로 남깁니다. 큰 통합은 선택 [8주 캡스톤](../../capstones/reproducible-infrastructure.md)입니다.
