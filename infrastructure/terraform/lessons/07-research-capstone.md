# 07. 엔진 연구와 2주 미니 캡스톤

[과정](../curriculum.md) · [소스 지도](../source-reading.md) · [평가](../assessment.md)

<a id="tf13"></a>
## TF13 — 관찰을 고정 소스와 실패 분기로 연결한다

소스를 많이 읽었다는 사실보다 **어떤 관찰을 어떤 구현이 설명하며, 무엇이 아직 추정인지**를 평가합니다. 기준은 Terraform `v1.16.5` commit `ef47237fd0e03d6e93bdc510b526287f06e94c03`입니다. provider나 HCP Terraform의 동작을 Core 코드만으로 모두 입증하지 않습니다.

### 2주 연구 루프

1. TF02·TF03·TF05·TF06 중 관찰 한 개를 고릅니다. 예: 알려지지 않은 instance key 거부, graph cycle, 다른 lineage의 state update 거부, 민감 값과 JSON mask의 분리.
2. [소스 지도](../source-reading.md)에서 entry point→자료구조→핵심 함수→오류 분기→기존 테스트를 연결합니다. 최소 5개 symbol과 2개 자료구조를 적습니다.
3. 기존 단위 테스트의 합성 fixture를 읽고 정상·음성 사례를 하나씩 설명합니다. Go 환경이 있으면 별도 source checkout에서 해당 테스트만 선택 실행하며 네트워크 의존성과 환경을 기록합니다.
4. 작은 입력 변경이 가설대로 실패하는지 확인합니다. 읽기만 했다면 SOURCE-READ, 실제 테스트면 SOURCE-TEST로 표시합니다. 테스트 이름이 같은 다른 revision의 결과를 섞지 않습니다.
5. 구현 변경 제안은 재현→원인→회귀 테스트→호환성/보안 영향→대안 순서로 2쪽 설계 노트를 작성합니다. upstream PR은 선택이며 자동 제출하지 않습니다.

### 연구 질문

- graph의 안전한 병렬 실행과 여러 API의 원자적 실행은 왜 다른가?
- state lineage/serial 검사와 실제 객체 중복 생성 방지는 어느 경계에서 각각 작동하는가?
- unknown한 민감 속성을 정책에서 허용하면 어떤 정보 부족을 숨기는가?
- 변경을 줄이는 모듈 추상화가 언제 blast radius를 더 크게 만드는가?

논문식 보고서는 문제·가정·방법·결과·반례·한계·재현 부록으로 구성합니다. 학술 용어를 붙였다고 consensus·serializability를 증명한 것은 아닙니다. 추상 모형과 실제 backend protocol의 차이를 명시합니다.

<a id="tf14"></a>
## TF14 — 한 root module, 한 변경, 두 실패

이 모듈은 2주·24시간의 작은 연구입니다. 앞선 fixture와 원장을 재사용하고 멀티 클라우드 계정·custom provider·CI 플랫폼을 새로 모두 구축하지 않습니다.

| 기간 | 작업 | 완료 조건 |
| --- | --- | --- |
| 1주 전반 | 한 root의 3–6개 내장 resource와 합성 입력, baseline 원장 | 주소·input/output·예상 action 독립 계산 |
| 1주 후반 | 주소 이관 또는 입력 계약 변경 중 하나 | 의도한 변경만 포함, 예상 외 delete/replacement 없음 |
| 2주 전반 | 실패 조건 두 개 | 잘못된 key/입력, 허용되지 않은 planned action 등 정상적으로 거부 |
| 2주 후반 | 수정·재계획·동료 재현·보고서 | 올바른 결과·후속 no-op·민감 산출물 미공개 |

LOCAL-TERRAFORM 경로는 실제 CLI로 검증한 범위만 제출합니다. CLI가 없으면 OFFLINE의 graph/plan-policy/state-cas 중 하나를 확장하여 두 반례를 제출하고 native 결과를 미검증으로 남깁니다. CPU 모형 PASS를 실제 CLI gate에 대신 넣지 않습니다.

독립 oracle은 테스트 대상과 같은 policy 함수를 다시 호출하지 않습니다. 사람이 작성한 주소별 예상 ledger 또는 별도 단순 구현과 대조합니다. 평가자는 임의 주소를 골라 “변경 전 identity → 승인 action → 변경 후 identity”를 추적합니다. 단순 count가 같아도 다른 객체가 바뀌면 실패입니다.

최종 제출은 README, 고정 버전 manifest, 합성 입력, 두 실패 재현, 복구/수정 후 full plan 요약, raw artifact의 안전한 보관 위치, 미검증 목록입니다. source 증거는 최소 하나를 연결합니다. 이후 [Terragrunt 과정](../../terragrunt/README.md)과 [8주 통합 캡스톤](../../../capstones/reproducible-infrastructure.md)은 별도 선택입니다.
