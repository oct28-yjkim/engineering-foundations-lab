# Terraform 28주 심화 커리큘럼

14모듈 × 2주 × 주 12시간 = 약 336시간입니다. 모듈당 원리·공식 자료 6시간, 실험 10시간, 소스 추적 4시간, 보고·구술 4시간을 기준으로 합니다. HCL·Go·클라우드 IAM 보충, 실제 원격 실습 준비는 별도입니다.

## 모듈 지도

| 모듈 / 주 | 선수 조건 | 핵심 질문 | 제출·최소 통과 |
| --- | --- | --- | --- |
| TF01 / 1–2 | Git·JSON·프로세스 | [구성과 수렴](lessons/01-language-values.md#tf01) | config/state/remote object/plan 네 원장, 반복 실행의 전제 |
| TF02 / 3–4 | TF01, 자료형 | [HCL·cty·unknown·null](lessons/01-language-values.md#tf02) | 값 상태 4종, 구조와 leaf의 knownness, 타입 변환 반례 |
| TF03 / 5–6 | TF02, DAG | [instance·dependency graph](lessons/02-graph-provider.md#tf03) | reference edge·cycle·replacement의 작업 그래프, 부분 순서 |
| TF04 / 7–8 | TF03, HTTP/RPC | [Core/provider 계약](lessons/02-graph-provider.md#tf04) | schema→read→plan→apply 추적, Core와 provider 책임 구별 |
| TF05 / 9–10 | TF04, 동시성 | [state·lineage·serial·lock](lessons/03-state-plan.md#tf05) | lost update·stale plan 반례와 lock/버전 검사 구분 |
| TF06 / 11–12 | TF05, JSON | [saved plan·정책·민감 정보](lessons/03-state-plan.md#tf06) | actions 전체·unknown 마스크·민감 산출물·artifact 결박 |
| TF07 / 13–14 | TF02–TF06 | [module·instance identity](lessons/04-modules-lifecycle.md#tf07) | count/for_each 재정렬, 주소·원격 ID·업무 키의 차이 |
| TF08 / 15–16 | TF07 | [lifecycle·import·moved·removed](lessons/04-modules-lifecycle.md#tf08) | 1:1 소유권 이관, 예상 delete/replacement 0과 실제 검산 |
| TF09 / 17–18 | TF06–TF08 | [validation·test·mocks](lessons/05-testing-drift.md#tf09) | plan/apply/default의 구분, 정상·음성·mock 한계 증거 |
| TF10 / 19–20 | TF05–TF09 | [drift·partial apply·재시도](lessons/05-testing-drift.md#tf10) | 세 종류 불일치, 부분 성공 원장·복구 후 전체 계획 |
| TF11 / 21–22 | TF06·TF09 | [CI·OIDC·공급망](lessons/06-delivery-recovery.md#tf11) | 신뢰 경계·승인 artifact·권한 거부·의존성 고정 |
| TF12 / 23–24 | TF10–TF11 | [backend·권한·복구](lessons/06-delivery-recovery.md#tf12) | principal/backend/workspace 구분, writer 차단·복구 검산 |
| TF13 / 25–26 | TF01–TF12, Go | [고정 소스·회귀 연구](lessons/07-research-capstone.md#tf13) | 5symbol·2자료구조·1실패 분기·재현 테스트 |
| TF14 / 27–28 | TF13 | [2주 최소 변경 연구](lessons/07-research-capstone.md#tf14) | 한 root·한 변경·두 실패·독립 oracle·후속 no-op |

## 실험 계약

정확성은 “명령 성공”이나 “변경 개수 동일”만으로 판정하지 않습니다. resource instance 주소, 원격 ID 또는 합성 ID, 의도한 속성, provider 설정 주소, 삭제·교체 여부를 대조합니다. 오류를 의도한 입력은 반드시 실패해야 하며, 미확정 값은 허용으로 변환하지 않습니다. JSON plan은 별도 보안 정책 엔진의 완성품이 아니라 문서화된 format version과 지원 범위를 확인해야 하는 입력입니다.

```text
run_id / source_commit / config_hash / cli_version / platform
module_revisions / provider_selections+checksums / environment_allowlist
backend_identity / workspace / principal / state_lineage+serial
plan_hash / expected_addresses / change_actions / unknown_sensitive_paths
approval_identity / apply_result / partial_success_ledger / residual_objects
independent_oracle / recovery_action / followup_full_plan / not_tested
```

비밀 값은 원문 대신 합성 값·비민감 ID로 대체합니다. state·saved plan·JSON·debug log는 비밀을 포함할 수 있으므로 보고서에 그대로 첨부하지 않습니다. plan이나 state의 해시도 비밀 원문의 공개를 허용하는 장치는 아닙니다.

## Gate와 완료 상태

- G1, TF01–TF04: 선언·knownness·instance graph·provider 책임을 구분합니다. 그래프의 한 topological order를 유일한 실제 실행 순서라고 주장하지 않습니다.
- G2, TF05–TF08: 동시성·계획·identity·이관 계약을 증명합니다. state lock과 provider lock file을 혼동하면 재학습합니다.
- G3, TF09–TF12: 실제 apply 위험, mock 한계, 부분 성공, credential·artifact 경계와 복구를 설명합니다.
- G4, TF13–TF14: 소스 가설을 반증 가능한 작은 실험으로 연결하고 실제 실행과 설계를 구분합니다.

[평가](assessment.md)는 정확성·원리/소스·실험/반증·운영/재현성 각 25점입니다. 총 80점 이상, 모든 영역 15점 이상, 필수 gate 모두를 만족해야 합니다. OFFLINE 통과는 LOCAL-TERRAFORM 또는 CLOUD-LAB 통과를 대신하지 않습니다.

매 보고서는 업무 질문 → 실패 모델 → 예상 변경 원장 → 실행 범위 → 증거 → 경쟁 가설 → 고정 소스 → 미검증 영역 순서로 작성합니다. [공통 실험 방법](../../databases/shared/experiment-method.md)을 사용하되 비용 실험은 실제 계정 승인 없이는 설계로 남깁니다.
