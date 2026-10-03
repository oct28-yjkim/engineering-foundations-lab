# Terragrunt 28주 심화 커리큘럼

14모듈 × 2주 × 주 12시간 = 약 336시간입니다. 각 모듈의 24시간은 원리·공식 자료 6, 실험 10, 소스 추적 4, 기록·구술 4시간으로 배분합니다. 실제 IAM/remote backend 준비와 보충 학습 시간은 별도입니다.

## 모듈 지도

| 모듈 / 주 | 선수 조건 | 핵심 질문 | 최소 제출·통과 증거 |
| --- | --- | --- | --- |
| TG01 / 1–2 | Terraform plan/state/module | [두 실행 계층](lessons/01-evaluation-composition.md#tg01) | module/unit/stack·engine·cwd·state identity를 분리한 실행 원장 |
| TG02 / 3–4 | TG01, HCL | [평가·include·merge](lessons/01-evaluation-composition.md#tg02) | 4종 merge 기대값, locals 의존 순서 오류, 공유 설정 변경 범위 |
| TG03 / 5–6 | TG02, output/state | [dependency·mock](lessons/02-dependency-queue.md#tg03) | 미배포·기존·schema 변경 outputs 비교, apply에서 mock 거부 |
| TG04 / 7–8 | TG03, DAG | [큐·부분 성공](lessons/02-dependency-queue.md#tg04) | diamond 그래프와 독립 branch, 실패/blocked/success 집합 검산 |
| TG05 / 9–10 | TG02, filesystem | [source·cache·lock file](lessons/03-cache-backend.md#tg05) | source/ref/cwd/state/lock의 서로 다른 identity, cache 교체 영향 |
| TG06 / 11–12 | TG05, Terraform backend | [state 경계·bootstrap](lessons/03-cache-backend.md#tg06) | backend key 충돌 부정 시험, 읽기/초기화/생성 권한 분리 설계 |
| TG07 / 13–14 | TG02–TG06 | [unit·stack 구성](lessons/04-stacks-blast-radius.md#tg07) | implicit/explicit 구성을 같은 unit 계약으로 비교, 생성물 fingerprint |
| TG08 / 15–16 | TG04, 집합·Git diff | [변경 영향·filter](lessons/04-stacks-blast-radius.md#tg08) | forward/reverse closure, 공유 파일·이동·삭제·외부 dependency 검산 |
| TG09 / 17–18 | TG04–TG06, process | [hook·retry·부작용](lessons/05-effects-security.md#tg09) | 중복/부분 성공 원장, 오류 분류·상한·멱등성 조건 |
| TG10 / 19–20 | TG09, IAM 기본 | [신원·공급망](lessons/05-effects-security.md#tg10) | plan/apply/backend identity, OIDC claim 거부 matrix·artifact 무결성 |
| TG11 / 21–22 | TG07–TG10 | [plan/apply 계약](lessons/06-delivery-recovery.md#tg11) | commit·unit·plan hash·dependency output snapshot별 승인 연결 |
| TG12 / 23–24 | TG06, TG11 | [관측·DR·비용](lessons/06-delivery-recovery.md#tg12) | state별 복구 ledger, dependency 일관성·원인별 시간·비용 예산 |
| TG13 / 25–26 | TG01–TG12, Go 읽기 | [고정 소스 연구](lessons/07-research-capstone.md#tg13) | 5symbol·2자료구조·1회귀 테스트·경쟁 가설 검토 |
| TG14 / 27–28 | TG13 | [2주 미니 연구](lessons/07-research-capstone.md#tg14) | local unit 2–3개, 변경 1개, 실패 2개, 독립 oracle·복구 기록 |

## 관찰 단위를 먼저 정의하기

Terraform의 resource address, Terragrunt unit 경로, backend identity, Git source commit, engine 프로세스, CI job은 서로 대체 가능한 ID가 아닙니다. 한 unit의 성공과 전체 서비스 불변식의 성공도 다릅니다. 아래 원장을 unit별로 남깁니다.

```text
run_id / repository_commit / Terragrunt_version / engine_path+version
OS / working_directory / source_commit / generated_config_hash / lock_file_hash
unit_path / selected_reason / dependencies / dependency_outputs_fingerprint
backend_type+nonsecret_identity / state_lineage+serial(if available)
plan_artifact_hash / policy_version / approval_identity+time+scope
queued_at / started_at / completed_at / status / engine_exit_code / attempt
external_effect_ledger / recovery_decision / expected_vs_actual / unverified_scope
```

state/plan/outputs의 원문·자격 증명은 공개 제출물에 넣지 않습니다. synthetic fixture만 사용하고 secret-bearing artifact는 암호화·보존 기한·접근 기록이 있는 별도 저장소로 분리합니다. hash도 저엔트로피 비밀의 안전한 익명화 수단이라고 가정하지 않습니다.

## 단계별 Gate

- G1, TG01–04: 평가 순서·현재 state output·두 DAG·실패 전파를 구분합니다. `run --all -- plan`을 미래 output 전달 장치로 설명하면 미통과입니다.
- G2, TG05–08: source/cache/state identity와 선택 집합을 검산합니다. 현재 디렉터리 하나만 보고 실제 대상 경계가 제한됐다고 단정하지 않습니다.
- G3, TG09–12: parse/plan의 부작용, 신원, artifact별 승인, 부분 성공 복구를 분리합니다. 재시도나 state backup 하나로 자동 롤백을 주장하지 않습니다.
- G4, TG13–14: 고정 revision에서 반례를 찾고 작은 재현을 제출합니다. 미실행 시나리오는 설계 결과로만 기록합니다.

[평가표](assessment.md)는 정확성 25, 원리·소스 25, 실험·반증 25, 운영·재현성 25점입니다. 총 80점 이상, 영역별 15점 이상, 필수 gate 전체 통과를 함께 요구합니다. 더 큰 조직·멀티 계정 확장은 [8주 캡스톤](../../capstones/reproducible-infrastructure.md)으로 분리합니다.

## 매 모듈 제출 형식

업무 질문 → 가정·실패 모델 → 실행 범위 → 손으로 계산한 기대 집합/값 → baseline → 단일 변인·부정 시험 → 실제 원장 → 소스 근거 → 경쟁 설명 → 복구·미검증 항목 순서로 작성합니다. [공통 실험 방법](../../databases/shared/experiment-method.md)을 사용하되 처리량보다 선택 대상·권한·state 일관성을 먼저 평가합니다.
