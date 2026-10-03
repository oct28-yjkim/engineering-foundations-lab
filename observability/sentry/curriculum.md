# Sentry 전문가 커리큘럼 — 28주 / 14모듈

## 운영 방식

기본 실습 경로는 [운영 runbook](operations.md)의 실제 project baseline → 지표·event·trace 기반 경쟁 가설 → 제한된 개선 → 회복 검증입니다. 아래 강의의 `OFFLINE` 모형/확률 과제는 선택 원리 부록으로 활용하고 제품의 실제 관측을 대신하지 않습니다. S01–02에 분모/baseline, S03–08에 앱 결함·관측 누락 사건, S09–12에 platform health/복구, S13–14에 source 근거와 사고 보고서를 누적합니다. 14모듈·28주를 유지하며 모듈의 실험 시간은 해당 운영 증거를 우선하는 시간입니다.

한 모듈은 명목상 2주·24시간입니다. 첫 주에 원리·프로토콜·소스를 읽고 가설과 oracle을 작성합니다. 둘째 주에 정상·실패 입력을 비교하고 재현 자료와 운영 결정을 제출합니다. 시간은 조정할 수 있지만 정확성 gate는 생략하지 않습니다. 네 평가 영역은 정확성, 원리·소스, 실험·반증, 운영·재현성 각 25점이며 총 80점 이상·각 15점 이상과 필수 gate를 함께 충족해야 합니다. 세부 사항은 [평가](assessment.md)를 따릅니다.

아래의 통과 수치는 학습용 목표입니다. 벤치마크를 최종 주장할 때는 [공통 실험 방법](../../databases/shared/experiment-method.md)에 따라 warmup 후 최소 20회 측정하고 환경·원시 표본·분산을 공개합니다. 기능 정확성 실험은 반복 횟수보다 독립된 oracle과 모든 fixture의 판정이 우선입니다.

## 모듈 지도

| 모듈 / 주차 | 선수 조건 | 설명할 메커니즘 | 실험·산출물 | 필수 통과 조건 |
| --- | --- | --- | --- | --- |
| S01 / 1–2주 | HTTP·집합·기초 통계 | 오류 탐지에서 triage·복구까지의 상태, 생성/수신/조회/알림 경계 | 1,000개 합성 요청의 업무 원장과 단계별 관측 계약 | 오류 원장의 모든 항목을 수집·필터·실패·미확인으로 분류; 미확인을 0으로 위장하지 않음 |
| S02 / 3–4주 | S01 | event·issue·transaction·span·log·Replay·metric·session의 단위 | 12종 fixture의 분류표와 식별자·분모 표 | 12/12 단위 분류; issue·error event·session을 바꿔 계산하는 세 반례 설명 |
| S03 / 5–6주 | S02, 비동기·UTF-8 | scope/context, async 격리, Envelope 프레이밍 | 메모리 transport + 100개 교차 요청 + 다중바이트 fixture | canary 교차 오염 0; byte length 기반 parser와 음성 fixture 모두 판정 |
| S04 / 7–8주 | S03, HTTP | category별 제한, 폐기·재시도·queue·shutdown 경계 | 가짜 시계와 200/429/5xx/timeout 응답 행렬 | category·deadline oracle 일치; capture/flush가 보장하지 않는 상태 구별 |
| S05 / 9–10주 | S03, 빌드 기초 | fingerprint, grouping, stack frame, Debug ID·symbolication | 6오류 계열 + 맞는/틀린 artifact 비교 | 업무 oracle 대비 false merge/split 판정; 빌드 매핑 불일치 검출 |
| S06 / 11–12주 | S05 | release·dist·environment·deploy·regression·session health | vA/vB 및 staging/prod의 2×2 합성 행렬 | release별 결함·회귀 조건 설명; crash-free와 error-free를 구별 |
| S07 / 13–14주 | S03, parent/child 개념 | span lifecycle, async 전파, Sentry/OTel 연결, trust boundary | 3구간 trace와 병렬/지연 실행, 허용·차단 목적지 비교 | trace/parent 관계 oracle 일치; 비허용 목적지 전파 0; 이중 instrumentation 검출 |
| S08 / 15–16주 | S07, 확률·가중 평균 | head/retention sampling, 포함 확률·선택 편향·metric 추출 경계 | 실제 프로젝트 sampling/outcomes와 독립 요청 분모 대조; oracle은 선택 보충 | naive 편향·가중 추정 조건·복구 불가능 결측을 설명하고 실제 관측의 모집단 한계 명시 |
| S09 / 17–18주 | S04, queue 개념 | Relay→Kafka→처리→Snuba/저장→조회, 메타데이터·blob 경계 | 선택 revision의 deployment graph와 event 단계 증거 | 최소 6경계·식별자·실패 상태 매핑; 오류 경로를 모든 신호에 일반화하지 않음 |
| S10 / 19–20주 | S09 | backlog·lag·freshness, 재처리·중복·retention·일관성 | 장애 시나리오 3종의 원장/대시보드/복구 계획 | ACK와 조회 가시성 분리; 입력 집합 기반 누락/중복 판정; retention 내 복구 계산 |
| S11 / 21–22주 | S03–S04, S07 | 신호별 개인정보 경로, 키·토큰·DSN, tenant 경계 | 합성 canary 위협 모델 + 전체 egress 검사 행렬 | 금지 canary 외부 payload 0; error hook만으로 전체 보호를 주장하지 않음 |
| S12 / 23–24주 | S09–S11 | SLO, 장애 도메인, self-hosted 운영·백업·업그레이드 | 독립 복구 runbook·일관성 계획·rollback 검토 | metadata/event/blob/config 복구 범위 명시; 실행 미검증과 측정 RPO/RTO 분리 |
| S13 / 25–26주 | S03–S12 | 최소 재현, version bisect, 호출 경로·불변식·회귀 테스트 | 한 동작의 pinned-source 연구와 최소 반례 | 가설을 반박할 수 있는 테스트·동일 입력 diff·commit 증거 제출 |
| S14 / 27–28주 | S01–S13 | 수집 계약·정확성·개인정보·샘플링의 결합 | 최소 합성 서비스 단면 + 두 장애 + 통합 설계 검토 | 1,000요청 원장·신호별 oracle·격리/제한 실패 검증·미검증 범위 공개 |

## 단계별 학습 전환

### 1단계: “발생한 것”과 “보이는 것”을 분리 — S01–S04

[강의 1](lessons/01-telemetry-contracts.md)에서는 애플리케이션 원장을 독립된 정답으로 둡니다. Sentry에 보이는 데이터만 정답으로 삼으면 수집 누락을 영원히 발견하지 못합니다. [강의 2](lessons/02-sdk-ingestion.md)는 객체가 transport에 도달할 때의 scope 격리와 바이트 프레이밍을 다룹니다. 로컬 수신기가 200을 반환하는 것은 grouping이나 검색을 증명하지 않는다는 경계를 먼저 익힙니다.

전환 gate: “200인데 왜 issue가 없습니까?”라는 질문에 최소 다섯 경로를 구별하고, 각 경로를 배제하는 증거를 제시합니다. 의도한 sample/filter와 비의도 loss를 구별하지 못하면 S09로 넘어가지 않습니다.

### 2단계: 진단 결과를 믿을 조건 — S05–S08

[강의 3](lessons/03-grouping-releases.md)은 issue를 원인 자체가 아닌 grouping 결과로 취급합니다. artifact identity, release, environment의 교차 검증 없이 스택과 회귀를 믿지 않습니다. [강의 4](lessons/04-tracing-sampling.md)는 trace의 연결성과 표본의 대표성을 분리합니다. trace가 예쁘게 연결되어 있어도 모집단 지연시간을 대표하지 않을 수 있습니다.

전환 gate: 하나의 실제로 다른 원인이 같은 issue로 합쳐지는 반례, 동일 원인이 분리되는 반례, 샘플의 평균이 모집단과 달라지는 반례를 각각 생성합니다. 단순 대시보드 캡처는 충분한 증거가 아닙니다.

### 3단계: 관측 시스템도 운영 대상 — S09–S12

[강의 5](lessons/05-data-pipeline.md)는 현재 선택한 deployment의 데이터 흐름을 직접 그립니다. Kafka 지식이 부족하면 partition·ACK·consumer offset·retention만 보충해도 시작할 수 있습니다. [강의 6](lessons/06-operations-privacy.md)은 신호마다 다른 개인정보 경로와 분산 저장소의 복구 경계를 검증합니다.

전환 gate: “Sentry 장애 때문에 Sentry가 안 보이는” 상황에서도 확인할 독립 health/freshness 신호와 복구 원장을 제시합니다. self-hosted 설치 성공을 HA·백업 성공으로 대신하지 않습니다.

### 4단계: 전문가의 주장을 반증 가능하게 — S13–S14

[강의 7](lessons/07-research-capstone.md)에서 특정 SDK/서버 동작을 pinned revision으로 추적하고 최소 실험으로 검증합니다. S14는 2주 안의 작은 단면입니다. 전체 운영 스택의 배포, 여러 저장소의 실제 복구, 다섯 장애 실험을 모두 2주에 요구하지 않습니다. 확장 구현은 [Supabase·Sentry 8주 앱 캡스톤](../../capstones/secure-observable-app.md) 또는 [데이터 파이프라인 8주 캡스톤](../../databases/shared/capstone.md)으로 연결합니다. 해당 시스템을 아직 학습하지 않았다면 계약·실패 지점 설계만 제출합니다.

## 제출 규약

모듈마다 `manifest`, `hypothesis`, 입력 fixture, oracle, 원시 결과, 실패 반례, source note, 운영 결정과 한계를 하나의 evidence 디렉터리에 둡니다. 비밀정보·실사용자 데이터·실제 DSN/토큰은 넣지 않습니다. 외부 서비스 실험에서는 승인된 대상과 합성 데이터만 사용합니다. `OFFLINE`, `SDK-LAB`, `PROJECT-LAB`, `SELF-HOST-DESIGN`의 의미는 [README](README.md)에 있으며, 설계 산출물을 실행 증거로 표시하지 않습니다.
