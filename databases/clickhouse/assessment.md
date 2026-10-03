# ClickHouse 실력 검증과 종합 프로젝트

## 공통 필수 운영 관문

[운영 runbook](operations.md)의 실제 서버 정상 기준선 1개, 서로 다른 사건 최소 2개, 각 사건의 경쟁 가설 2개 이상·원시 지표/로그·제한된 조치·되돌림/회복 후 업무 검산을 제출합니다. 지표는 gauge/counter/event, 단위·집계 창·reset 여부를 표시합니다. 임계값 암기나 dashboard 화면만으로는 통과하지 않습니다.

원리 모형·손계산·mock/단위 테스트는 선택 보조 증거입니다. 이를 생략했다고 운영 과정 진입을 막지 않으며, 성공했다고 실제 운영 점수를 주지도 않습니다. 기존 점수 기준 및 제품별 정확성·복원·권한 관문은 유지합니다. 환경이 없으면 설계/원리 학습 완료와 운영 미완료를 구별하고, 실제 baseline/사건 증거 없이 전체 운영 완료를 선언하지 않습니다.


[커리큘럼](curriculum.md) · [공통 실험 방법](../shared/experiment-method.md) · [통합 연구](../shared/capstone.md)

## 통과는 증거로 판단한다

매 모듈은 설명·정확성 실험·관찰 증거·운영 판단을 함께 평가합니다. 공통 rubric에 맞춰 네 영역을 각각 25점으로 평가하고 **총 80점 이상, 각 영역 15점 이상**, 해당 모듈의 필수 gate를 모두 만족해야 통과합니다. 원시 결과가 없는 완성도 높은 보고서는 실행 영역 점수를 대체하지 않습니다.

| 영역 | 0–9점 | 10–14점 | 15–20점 | 21–25점 |
| --- | --- | --- | --- | --- |
| 원리·내부 동작 | 키워드 설명 | 큰 흐름만 설명 | 불변식·자료구조·경계 설명 | 실제 commit의 분기·소유권·반례로 설명 |
| 정확성·재현 실험 | 결과 또는 입력 없음 | 정상 입력만 검사 | 고정 버전·oracle·경계값·재현 | 독립 oracle과 장애/역순/중복까지 검증 |
| 성능·관측·분석 | 속도 주장만 있음 | 단일 지표·적은 표본 | 통제된 20회 이상 측정·자원 비교 | 대안·skew·규모·원인 반증까지 설명 |
| 운영 판단·소통 | 설정 추천만 있음 | 제한·복구 불명확 | 실패 경계·runbook·선택 근거 | 실제 복구·SLO·잔여 위험·다른 사람이 재현 |

정확성 mismatch, runtime/source 미대응, 실행하지 않은 결과의 실측 표기, backfill 중복을 설명하지 못함, 복구 과제의 restore 미실행은 점수와 무관하게 해당 gate 미통과입니다. M01의 운영 판단은 거대한 클러스터 구축이 아니라 입력 계약과 실패 판정을 설명하는 수준으로 채점하고, M14에서는 실제 restore와 제한 계정 검증이 필요합니다.

## 프로젝트 A: 정확한 이벤트 분석 엔진 LOCAL

**입력:** 기본 50만 events와 학습자가 만든 최소 1만 행의 추가 fixture. fixture에는 같은 사용자의 여러 세션, 이벤트 중복, 같은 timestamp, 늦은 arrival, NULL/경계 날짜를 포함합니다. 각 행의 의미를 생성식과 기대 불변식으로 기록합니다.

**요구사항:** 시간/국가/기기별 다섯 KPI, 세션 내 순차 퍼널, exact 매출·구매 건수·고유 사용자 기준선, 고유 사용자 근사 대안, raw/MV 경로를 구현합니다. 순차 퍼널은 같은 사용자의 다른 세션 이벤트를 섞지 않고 시간 순서·동률·최대 window 계약을 정의합니다.

**실험:** 정렬 키 2개 × 쿼리 5개를 각 20회 이상 비교합니다. sparse index pruning, part 분포, 읽기량, wall/CPU, memory, 저장량, insert 비용을 함께 봅니다. query 1개만 빠르게 만든 전체 설계는 다른 네 query의 퇴보도 명시합니다.

**필수 gate:** exact 지표를 모든 차원 그룹에서 대조하여 mismatch 0; 근사 지표는 사전에 정한 오차 예산으로 별도 평가; 이벤트 중복과 MV backfill의 중복을 각각 검출; static data와 live insert를 구별한 보고서. 조건을 충족하지 못하면 성능 향상 점수로 상쇄하지 않습니다.

**제출물:** DDL·SQL·fixture·원시 query 로그·설계 ADR·재현 순서. 자신의 쿼리가 답안과 다르면 어느 계약을 개선했는지 설명합니다.

## 프로젝트 B: 적재와 최신 상태의 정확성 LOCAL + CLUSTER-DESIGN

**입력:** 10,000개 entity, 각 entity에 1–5개 version, retry duplicate, version 역순 도착, 같은 version의 충돌, 삭제 뒤 과거 version 도착. stable event_id와 source version 순서를 분리합니다.

**요구사항:** append history와 최신 상태 조회를 구분합니다. key/version/tombstone 계약, async ACK·retry 정책, mutation 또는 보정 이벤트 선택, raw→집계 전달 시 delta 또는 재계산 전략을 문서화합니다.

**실험:** batch 크기 3조건, 정상/timeout 재시도, source mutation 후 MV mismatch, 늦은 tombstone/낮은 version, cutoff를 넘어온 과거 event_time을 검사합니다. 분산 단계는 M13 토폴로지를 구현하고 4개 장애를 주입합니다. 클러스터가 없으면 단일 노드 프로젝트만 완료이며 분산 gate는 남습니다.

**필수 gate:** 독립적인 latest-state oracle과 논리 결과 mismatch 0; timeout의 unknown 상태를 누락하지 않는 ACK 원장; duplicate event_id의 효과 설명; 원복 후 replica/aggregate 대조. `FINAL`을 붙인 것 자체는 정확성 증명이 아닙니다.

**제출물:** 작은 hand-calculated history, 실제 대규모 입력과 oracle, ACK timeline, 재시도와 삭제 ADR, 장애 보고서. 동일 key/version의 충돌을 자동으로 최신이라고 포장하지 않고 producer 계약 또는 충돌 처리 정책을 제시합니다.

## 프로젝트 C: 독립 복구와 성능 방어 OPS-DESIGN + SOURCE

**환경:** 독립 백업 destination·빈 restore 대상·제한된 분석 계정·혼합 부하 발생기를 학습자가 추가 구성합니다. 소스 분석용 checkout은 runtime commit에 맞춥니다.

**목표 예시:** 정상 혼합 부하에서 dashboard p95 1초, 신선도 p95 10초, restore RPO 60초·RTO 15분. 실제 자원과 업무 요구에 따라 시작 전에 다른 값을 정할 수 있습니다. 예시 숫자는 달성 결과가 아니며 결과에서 목표를 소급 변경하지 않습니다.

**실험:** baseline/혼합/회복 구간, 1,000개 이상의 latency 표본, query 제한 동작, 별도 restore 후 모든 그룹 정합성·접근 권한·신규 insert/MV 동작 검증. 대표 병목 한 개를 최소 5개 source symbol과 연결합니다. 운영 조회에는 active parts, merge, mutation, memory, disk, replica queue, freshness를 포함하고 경보마다 실제 조치와 확인 query를 둡니다.

**필수 gate:** 독립 restore 성공, raw/MV·권한 검증, RPO/RTO 실측, 1개 최소 재현과 source trace. 분산 가용성을 주장하면 서로 다른 failure domain에서 검증한 범위를 밝혀야 합니다.

**연구 확장 중 하나:** 작은 sparse-index/mergeable-aggregate teaching engine, 엔진 regression test, 실제 source patch. 단순화한 구현이 생략한 concurrency/durability/format 호환성 문제를 명시합니다. patch 선택 시 해당·회귀 test와 성능 영향을 제출합니다.

## 90분 전문가 구술 리뷰

20분은 자신의 시스템 설명, 30분은 미리 고르지 않은 실패 질문, 20분은 source trace, 20분은 예상과 다른 실험 결과를 리뷰합니다. 모르는 것은 모른다고 말하고 다음에 확인할 증거를 구체적으로 제시할 수 있어야 합니다.

1. primary key가 유일하지 않다면 ClickHouse에서 “한 행”의 정체성을 어디서 보장하는가?
2. ORDER BY를 그대로 두고 PRIMARY KEY만 줄이면 압축·인덱스 메모리·pruning에 어떤 가설을 세우는가?
3. granule이 8192행보다 작은 이유를 두 가지 제시하고 mark/압축 블록과 구별하라.
4. read_rows는 같은데 latency가 두 배라면 어떤 순서로 조사하고 어떤 가설을 반박할 것인가?
5. build-side cardinality는 작은데 JOIN 메모리가 큰 경우의 설명은?
6. 부분 distinct를 더할 수 없는 이유와 근사 state를 합치는 조건은?
7. ACK를 받은 async insert가 모든 replica에서 즉시 조회된다는 주장을 어떻게 검증하거나 반박하는가?
8. Replacing version 동률과 삭제 후 과거 이벤트를 어떻게 처리하는가?
9. source에 FINAL을 붙이면 MV revenue도 맞아진다는 주장의 최소 반례는?
10. backfill cutoff 시각보다 오래된 이벤트가 cutoff 이후 도착하면 어느 경로에서 처리하는가?
11. Keeper quorum, insert quorum, Distributed write, 다중 테이블 원자성의 차이는?
12. 복구된 count가 원본과 같아도 잘못된 복구일 수 있는 이유는?

각 답변은 정의 → 불변식 → 실제 관측/코드 → 반례 → 선택의 순서를 권장합니다. 암기한 답을 말하는 대신 리뷰어가 값을 바꾼 fixture에서도 결과를 예측해야 합니다.

## 완료 기록

마지막 보고서에 G1/G2/G3/G4, 프로젝트 A/B/C, source 정적 추적, 동적 프로파일링, cluster 실행, restore 실행을 각각 완료/미완료로 표시합니다. 미검증 항목과 원인을 적고 실제 수행 범위에 맞춰 “단일 노드 심화 완료” 또는 “분산·복구까지 검증 완료”로 표현합니다. 다음 단계는 PostgreSQL 변경의 의미를 ClickHouse까지 보존하는 [통합 연구](../shared/capstone.md)입니다.
