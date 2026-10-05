# ML Systems Design 커리큘럼

[시작](README.md) · [출처·읽기](references.md) · [실행](labs/README.md) · [운영 진단](operations.md) · [수학 보충](../math-foundations/README.md)

**8모듈 × 2주 × 주 12시간 = 16주·192시간**의 독자적인 선택 트랙입니다. 모듈별 읽기/개념 4h, 계약/설계 6h, 실험/진단 10h, 기록/리뷰 4h를 배정합니다. [ML 기본](../ml-paper-lab/curriculum.md)을 이해한 뒤 DL·LLM과 병행할 수 있으며 기존 64주 경로의 마지막 필수 단계로 붙이지 않습니다.

`P`는 제공 로컬 fixture/코드, `M`은 수기 검산·설계·리뷰, `E`는 별도 구현 또는 승인된 환경 확장입니다. `P`라고 해도 실측 완료는 [검증 기록](validation.md)을 확인해야 합니다. 모든 모듈은 **목적 → 계산·상태 → 관측 → 제약·반례 → 채택/비채택** 순서로 학습합니다.

| 모듈·주차 | 선수·읽기 | 설계와 내부 동작 | 실습·관측·통과 증거 |
| --- | --- | --- | --- |
| SYS-M01 · 1–2 | ML baseline/metric, R03 | 예측 task와 실제 의사결정·사용자 목표 분리; 비ML baseline·실패 비용·SLO·예산 | `M` 요구사항 1장: action/owner/latency/freshness/오류 비용·비채택 조건. `P` 정상 로컬 요청의 버전·응답 확인. 복잡한 모델 없이도 계약을 검증하는 이유를 설명 |
| SYS-M02 · 3–4 | split·조건부 확률, R01 §3 | 수집·label 정의·관측 지연·point-in-time 선택·학습 시점·유효 시점 | `P` event time만 보면 유입되는 late-arrival 누출을 available time과 독립 expected fixture로 검출. `M` 그룹/시간 split·label maturity·보관/삭제/lineage 계약. cutoff 이후 알게 된 사실을 배제 |
| SYS-M03 · 5–6 | M02·함수/scale, R02 Data 1/7·Monitor 3 | feature schema·단위·default·결측·버전·train/serve parity·staleness | `P` schema/type/dimension·feature/preprocessing version·오래된 입력을 거부하고 정상 계약으로 복구. `M` offline/online 동일 입력의 변환값 비교표. feature 버전 label만 같아도 의미가 다를 수 있는 반례 |
| SYS-M04 · 7–8 | ML 평가·기댓값, R02 Model 2/5/6 | threshold와 probability·calibration·slice·표본 수·선택 편향·offline/online 차이 | `P` label coverage와 입력 분포/quality 대조 fixture. `M` Brier·confusion matrix·reliability bin을 손계산하고 검정/CI 계획. 전체 평균 개선이 핵심 slice 악화를 숨기는 경우·미도착 label을 0으로 취급하는 오류 설명 |
| SYS-M05 · 9–10 | M01/M03·HTTP 기초, R03 #5/32/37 | batch/online 선택·request/response·model/feature 호환성·timeout·fallback | `P` 짧은 loopback HTTP 서비스의 정상/비정상 계약. `M` batch 재실행·멱등 output, online deadline·overload·capacity 표. `E` queue/load test. 로컬 지연을 production SLO 달성 증거로 사용하지 않음 |
| SYS-M06 · 11–12 | M04–05, R02 Infra 6/7·§V | 후보 검증→승격→관측→복귀; serving health와 품질·label 지연의 서로 다른 시계 | `P` 제한된 quality gate/rollback과 전후 정상 예측. `M` shadow/canary/A-B 목적·guardrail·승인자·지연 label 판단 보류. 모델뿐 아니라 feature 계약도 복구되어야 함을 증명 |
| SYS-M07 · 13–14 | M02/M04/M06, R01 §4/7 | drift 종류·피드백·노출 편향·retraining trigger·재검증·데이터 책임 | `P` 입력 분포 변화와 품질 변화의 서로 다른 fixture. `M` population mix 분석·원인/조치 매트릭스·retrain/repair/rollback/wait 선택. 입력 drift만으로 모델 퇴화나 자동 재학습 필요성을 결론내리지 않음 |
| SYS-M08 · 15–16 | M01–07, R01/R02 재검토 | 비용·신뢰성·privacy/fairness·ownership을 포함한 수명주기 설계 | `M/P` 한 실패의 탐지→진단→복구와 regression 증거. 비용 단위·책임자·data/model 카드·승격/중지 기준. `E` 실데이터/다중 replica 확장은 승인·예산 뒤 별도 수행 |

R01–R03은 [출처 문서](references.md)의 시스템 논문/가이드 식별자입니다. Stanford의 주제 순서를 그대로 재현하거나 원 과제를 풀이하는 과정이 아닙니다.

## 모듈별 필수 설계 산출물

### M01–02 · 문제와 데이터가 성립하는지 먼저 확인

- 예측 단위·결정 시점·output 사용처·잘못된 결정의 비용·수동/규칙 baseline·사용 중지 조건을 기록합니다. accuracy가 높아도 의사결정에 도움이 없으면 비채택합니다.
- 데이터 한 행에 entity, event time, available time, feature version, label 발생/관측 시점을 표시합니다. 학습 dataset 생성 시점과 prediction 시점의 정보를 혼합하지 않습니다.
- point-in-time fixture에서 “과거에 발생했지만 당시에는 아직 도착하지 않은 값”을 제외하고 손으로 정한 정답과 대조합니다. 실제 시스템에서는 revision·backfill·삭제·timezone·clock skew도 따로 다루어야 합니다.

### M03–04 · 같은 값과 같은 평가를 말하고 있는가?

- `raw → validation → transform → feature vector → score → decision`의 각 단계에 schema·단위·허용 결측·owner를 붙입니다. training/serving에서 같은 함수를 호출해도 입력 snapshot이 다르면 parity가 깨집니다.
- 전체/중요 slice별 표본 수와 label coverage를 함께 적습니다. 작은 slice는 오차와 불확실성을 같이 보고, 충분한 label이 없으면 품질을 정상으로 판정하지 않습니다.
- calibration과 ranking/threshold 지표를 구별합니다. 보정기를 추가하는 경우 calibration split은 model fitting과 final test에서 분리하는 `M/E` 과제이며 기본 LAB에 자동 fitter가 있는 것은 아닙니다.

### M05–06 · 응답 가능과 올바른 예측을 분리

- batch와 online을 요청 시점·freshness·처리량·실패 재시도·비용 기준으로 비교합니다. 배치여도 point-in-time 계약이 필요하고, HTTP가 정상이어도 의미상 잘못된 feature가 들어올 수 있습니다.
- 배포 단위는 모델 파일 하나가 아니라 feature 계약·threshold·전처리·runtime 호환성까지 포함합니다. fallback은 별도 품질·비용 검증 대상이며 “아무 값이나 반환”이 아닙니다.
- quality gate의 threshold·대상 cohort·최소 표본·label maturity를 승격 전에 정합니다. 로컬 deterministic gate는 실제 트래픽의 통계적 canary/A-B 검증을 대체하지 않습니다.
- 기본 fixture는 baseline 평가→격리된 후보 평가→gate의 edge slice 회귀 탐지/승격 거부→baseline 복원·재검증 순서입니다. 후보 평가용 주입을 운영 승격으로 해석하지 않습니다. 복귀는 단일 프로세스의 model pointer 변경으로 제한됩니다.

### M07–08 · 신호에 맞는 복구와 장기 책임

- feature drift, label prior 변화, 조건부 관계 변화, 사용자 구성 변화, 데이터 파이프라인 장애를 별도 가설로 둡니다. 분포가 달라졌지만 품질은 유지되는 경우와 분포 요약은 같지만 품질이 나빠지는 경우를 구별합니다.
- 모델의 노출/추천이 다음 학습 데이터를 바꾸는 경로를 그립니다. 미노출 항목에 정답이 없다는 사실을 negative label로 바꾸지 않습니다. 실제 인과 추정·exploration policy는 확장 과제입니다.
- 지연 label을 고려한 retraining schedule/trigger·재학습 중지·검증·승인·rollback owner를 지정합니다. 회귀 원인이 schema라면 재학습보다 파이프라인 복구가 우선일 수 있습니다.
- privacy·보관 기간·사용 권한·정의한 사용자 집단의 피해·human escalation을 검토합니다. slice별 점수만으로 공정성이나 법적 준수를 인증하지 않습니다.

## 매번 남기는 증거

| 증거 | 최소 내용 |
| --- | --- |
| 계약 | 데이터 cutoff·feature/model 버전·schema·기준 모델·metric·threshold |
| 예상 | 독립적인 expected row/score/status·실패 조건·복구 조건 |
| 관측 | 정상/비정상 요청 결과, 표본 수·coverage·버전·적용 시점 |
| 진단 | 경쟁 가설 2개, 이를 구별하는 관측/추가 검사, 아직 모르는 것 |
| 복구 | 변경 대상·영향 범위·원복·정상 재검증·재발 방지 테스트 |
| 한계 | 로컬 fixture/설계-only/외부 환경 실측을 구분하고 외삽하지 않음 |

## 통과 관문

1. 모델을 쓰지 않는 baseline과 업무 목적을 정당화하고 latency·freshness·품질의 서로 다른 계약을 쓴다.
2. point-in-time 누출, schema 불일치, training-serving 차이를 독립 정답으로 검출한다.
3. label coverage·maturity·slice 표본을 포함해 **판단 가능한 품질과 아직 알 수 없는 품질**을 구별한다.
4. HTTP 정상·입력 drift·품질 악화를 동일한 장애로 취급하지 않고 조치를 선택한다.
5. 후보 거부 또는 승격/rollback을 재현하고 동일 요청·계약으로 복구를 확인한다.
6. 팀원에게 설계·진단 기록을 넘겼을 때 위험한 외부 작업 없이 다시 검증할 수 있다.

마지막 24시간은 한 문제의 미니 캡스톤입니다. [설계 리뷰 양식](templates/design-review.md)에 예상·실측·미확정을 나누어 제출합니다. 클라우드·Kubernetes·registry·feature store·streaming 전체를 구축하거나 실사용자 실험을 수행해야 통과하는 과정이 아닙니다. 이들 확장은 요구와 비용을 먼저 확인한 뒤 [전체 경로](../ml-dl-llm-roadmap.md)의 해당 도구 LAB으로 연결합니다.
