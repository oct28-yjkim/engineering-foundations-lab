# Terragrunt 평가 기준

[커리큘럼](curriculum.md) · [소스 지도](source-reading.md) · [로컬 실습](labs/README.md)

총 **80/100 이상**, **네 영역 모두 15/25 이상**, 아래 필수 gate 전체 통과가 선언한 실행 범위의 완료 기준입니다. 더 많은 unit을 병렬 실행하거나 HCL을 짧게 만든 것 자체에는 점수를 주지 않습니다.

| 영역 | 최소 증거 | 높은 수준의 증거 |
| --- | --- | --- |
| 정확성 25 | 선택 unit·dependency 순서·입출력·state identity를 독립 검산 | 현재/미래 output 혼동, 삭제·rename·부분 실패를 반례로 검출 |
| 원리·소스 25 | parser, discovery, queue, engine, backend 경계 설명 | 고정 revision 함수·자료구조·테스트로 관측과 failure path 연결 |
| 실험·반증 25 | baseline·한 변인·기대값·실패해야 하는 테스트 | 승인·신원·cache·retry의 경쟁 가설을 독립 대조군으로 분리 |
| 운영·재현성 25 | version·commit·명령·run ID·비밀 제거·대상 경계 | artifact별 승인·효과 원장·중단 상한·정합 복구·미검증 명시 |

## 필수 gate

제품 운영 실습은 [실제 기준선·두 문제의 진단·회복 비교](operations.md)가 있어야 완료합니다. unit별 상태·시간·dependency·조치 전후 outputs/state와 미검증 범위를 [운영 보고서](../../operations/incident-report-template.md)에 제출합니다. 원리 모형 또는 제공된 로그 분석만으로 실제 scheduler/backend 운영 통과를 선언하지 않습니다.

1. **두 DAG:** Terraform resource DAG와 Terragrunt unit DAG를 다른 그림/자료구조로 제시합니다. 여러 state를 하나의 원자적 transaction으로 주장하지 않습니다.
2. **선택 집합:** intended/selected/started/succeeded/failed/blocked 집합을 별도로 기록합니다. 포함 누락과 초과 포함 양쪽을 검사합니다. Git diff만으로 공유 설정 영향이 완전하다고 주장하지 않습니다.
3. **Outputs:** dependency는 기존 적용 결과를 읽으며 upstream plan의 미래 값을 downstream plan에 자동 전파하지 않습니다. mock과 실제 값의 출처를 표시하고 apply에 mock을 허용하지 않습니다.
4. **승인·부작용:** `run --all` apply/destroy의 자동 승인 기본값을 설명합니다. parse·plan·hook·auto-init이 무부작용이라는 가정을 기각합니다. untrusted HCL/PR에 privileged credential을 주지 않습니다.
5. **State·복구:** backend identity와 cache 경로를 구분합니다. 공유 state 삭제/강제 push/unlock을 기본 해결책으로 쓰지 않습니다. backup 복원은 실제 원격 객체·다른 state와의 정합성을 별도 검증해야 합니다.
6. **증거 정직성:** CPU 모형, mock subprocess 테스트, 실제 local CLI, cloud 설계, cloud 검증을 구분합니다. exit 0만으로 보안·복구·정합성을 PASS 처리하지 않습니다.

## 실행 범위별 판정

| 범위 | 필요 증거 | 통과해도 증명되지 않는 것 |
| --- | --- | --- |
| OFFLINE | 4개 공통 모형, 정상/음성 시험, 모형 가정 | 실제 HCL parser·Terragrunt scheduler·provider/backend |
| LOCAL-TERRAGRUNT | 고정 CLI+Terraform, local state fixture, 선택 unit·plan·outputs 원장 | cloud IAM·remote lock 내구성·실제 과금·분산 장애 |
| CLOUD-DESIGN | 대상·권한·비용·복구·중단 기준이 있는 실행 계획 | 실제 deny/allow·복구 성공·비용 수치 |
| CLOUD-VERIFIED | 별도 승인된 sandbox, 실제 identity·부정 시험·정합 복구 | 다른 cloud/provider/version과 미시험 장애 영역 |

TG14는 2주 동안 local unit 2–3개와 이미 작성한 코드만 사용합니다. 두 실패 조건은 예를 들어 upstream output 계약 변경과 잘못된 영향 범위 선택입니다. 실제 실패 주입을 하지 못했으면 해당 실행 gate를 미검증으로 남깁니다.

동료가 unit 한 개의 출처부터 선택 이유, 의존성, 계획, 승인, 효과, 복구까지 추적할 수 있어야 합니다. 복구 후 output count뿐 아니라 ID·값·버전·state ownership을 검사합니다. [실험 보고서](../../databases/shared/templates/experiment-report.md), [장애 기록](../../databases/shared/templates/incident-review.md), 선택 [8주 캡스톤](../../capstones/reproducible-infrastructure.md)을 사용합니다.
