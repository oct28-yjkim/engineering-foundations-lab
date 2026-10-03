# 변경과 복구를 검증하는 IaC 통합 연구 8주

[Terraform](../infrastructure/terraform/README.md)과 [Terragrunt](../infrastructure/terragrunt/README.md)의 2주 미니 캡스톤 다음에 선택하는 별도 8주 과정입니다. 모든 cloud를 배포하는 프로젝트가 아니라 **계획한 변경, 승인한 변경, 실제 반영된 상태가 언제 달라지는지** 추적합니다.

## 범위와 불변식

기본은 제공된 built-in 로컬 fixture를 확장한 foundation → application → observer와 독립 sandbox unit입니다. 명칭은 업무 역할일 뿐 실제 network/app/monitoring service를 만들지 않습니다. 클라우드 구현을 선택한다면 계정·region·권한·비용·리소스 수·중단 책임부터 별도 승인합니다. prod는 기본 대상이 아닙니다.

| 불변식 | 검사할 증거 |
| --- | --- |
| 같은 unit의 코드·입력·provider가 재현됨 | commit·CLI·module digest·lock selections·입력 provenance |
| 계획의 검토 대상과 적용 대상이 일치 | plan digest·생성 시각·state identity·승인 주체·적용 결과 |
| 미확정·민감 값은 정책을 우회하지 않음 | unknown/sensitive 양성·음성 사례, JSON 공유 제한 |
| 다른 unit 실패가 전체 rollback처럼 보이지 않음 | unit별 시작/성공/실패·state serial·실제 output 원장 |
| 변경 영향에서 consumer가 빠지지 않음 | dependency/참조 파일/공유 module closure와 포함·제외 목록 |
| 복구가 상태 파일 재배치만으로 끝나지 않음 | ownership·remote object·consumer output·접근 권한의 재검산 |

## 1–2주: 신뢰 경계와 작은 모델

unit/resource instance/state/backend/workspace/identity를 따로 정의합니다. 디렉터리 이름으로 prod 권한이 제한된다고 가정하지 않습니다. provider lock file과 state lock을 구별하고, plan·state의 비밀 취급을 문서화합니다. 원본 fixture와 독립 기대 결과를 보존합니다.

## 3–4주: 정상 경로와 승인 패킷

unit별 새 plan을 만든 뒤 작은 scope를 검토하고 해당 plan만 적용합니다. mock 기반 consumer plan은 producer 적용 뒤 폐기 대상으로 표시하고 실제 output으로 재계획합니다. UUID 같은 비결정 값 대신 business attributes·resource 주소·관계·재계획 diff를 비교합니다. 승인되지 않은 unit은 실행되지 않았다는 음성 증거가 필요합니다.

## 5–6주: 최소 다섯 반례

- component key rename과 값 변경의 서로 다른 identity 영향.
- unknown 필수 identity 또는 replacement가 정책 gate에 들어오는 경우.
- producer output의 변경 계획과 아직 구버전인 실제 state output.
- 한 unit 적용 성공 뒤 downstream 실패: 성공 상태 보존과 새 계획·재승인.
- stale snapshot/다른 lineage에 대한 쓰기 거부. CPU 모형과 backend 실제 검증은 별도.
- shared module/root include 변경을 파일 diff만으로 선택해 consumer를 누락하는 경우.
- cache 안 state 경로라는 잘못된 설계. 실제 state를 지우지 않고 새 fixture로 위치·복구 가정을 검토.

각 사례에 초기 상태·실패 지점·독립 oracle·새 계획·검토·후속 조치·영향받지 않은 unit을 남깁니다. 잠금 우회나 실패 무시 flag로 초록색 CI를 만드는 것은 해결이 아닙니다. 원격 backend 경쟁·API timeout은 승인된 환경에서만 실제 실행으로 분류합니다.

## 7–8주: 복구와 연구 방어

quiesce한 합성 환경의 state·code·입력·의존성 계약을 별도 새 대상으로 복원합니다. 실제 cloud object의 소유권을 두 독립 state가 동시에 관리하도록 연결하지 않습니다. remote 객체가 있는 복구는 backend 전환과 state ownership 이양·writer 중단·확인 절차까지 포함해야 합니다.

RTO는 state 파일을 열 수 있는 시점이 아니라 정상 plan·업무 output·consumer·권한 검증이 완료되는 시점까지 정의합니다. RPO는 마지막 확인된 적용과 복구 지점의 차이를 실제 변경 원장으로 설명합니다. 오래된 state를 복사한 행위를 안전한 infrastructure rollback이라 부르지 않습니다.

최종 제출: 실행 fingerprint, unit graph, 승인 패킷, 정상 경로, 다섯 반례, 복원 보고서, source trace, 남은 미검증 경계. 공통 **정확성·원리/소스·실험/반증·운영/재현성 각 25점, 총 80 이상·각 15 이상 및 선언한 범위의 필수 gate**를 적용합니다. Terraform/Terragrunt 소스 테스트를 읽기만 했으면 실제 빌드·회귀 성공으로 기록하지 않습니다.

선택 확장: Databricks workspace, DB/Kafka sandbox 또는 LLM serving의 인프라 정의. 이 경우 제품별 데이터 정합성·보안·복구 gate는 별도로 다시 수행하고 IaC exit 0을 서비스 건강성으로 쓰지 않습니다.
