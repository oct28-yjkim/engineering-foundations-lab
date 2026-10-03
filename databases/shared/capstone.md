# 통합 연구: 원본 transaction에서 분석 결과까지 8주

선행: 두 트랙의 내부 구조·동시성·집계·복구 과제. 목표는 주문 데이터의 진실이 PostgreSQL에서 ClickHouse 분석 결과까지 어떤 계약으로 전달되는지 설계하고 검증하는 것입니다. **통합 파이프라인은 구현 과제이며 현재 저장소가 실행 가능한 CDC 환경을 제공하지는 않습니다.**

## 업무 계약

주문 생성·결제·취소·부분 환불이 가능한 서비스를 설계합니다. source of truth는 PostgreSQL이고, ClickHouse에는 변경 이벤트 및 분석용 상태를 구성합니다. 하나의 주문에 여러 변경이 생기고 이벤트는 중복·역순·지연될 수 있습니다.

먼저 다음 값을 학습용 목표로 설정하고, 실제 자원 예산과 측정에 따라 조정합니다.

| 항목 | 출발 목표 예시 | 검증 방법 |
| --- | --- | --- |
| 정확성 | 동기화가 수렴한 후 주문 상태·순매출 mismatch 0 | ID/version·상태·금액 차이 검출 |
| 신선도 | 정상 부하에서 event-to-query p95 10초 이내 | source commit 기준의 관측 정의와 clock 오차 기록 |
| 조회 | 지정된 핵심 집계 p95 1초 이내 | 데이터 크기·동시성·cache 조건을 함께 보고 |
| 복구 | 연구 환경 RPO ≤60초, RTO ≤15분 | backup→별도 restore→정확성 확인의 실측 |
| 자원 | CPU·RAM·disk 상한을 학습자가 먼저 선언 | 전체 실행·복구·backfill의 peak 측정 |

목표를 달성하지 못하면 측정값과 병목 근거를 제출하고, 요구사항 또는 설계의 조정안을 리뷰합니다. 수치를 문서에 적은 것만으로 달성한 것으로 평가하지 않습니다. 빈 테이블의 빠른 쿼리도 통과 증거가 아닙니다.

## 1–2주: correctness 계약과 모델

이벤트에 stable `event_id`, `order_id`, source 내 순서를 비교할 수 있는 version/position, event type, 변경 전후 표현, schema version을 정의합니다. 시계 시각만으로 순서를 정하지 않습니다. source transaction 경계를 소비 측에 전달할지, 어떤 단위의 원자성이 필요한지 명시합니다.

변경 획득 방식은 logical decoding/connector 또는 transactional outbox 중 하나를 선택합니다. outbox라면 업무 변경과 outbox INSERT가 같은 PostgreSQL transaction에 들어가고, publish와 ack 사이의 중복을 어떻게 다룰지 설명합니다. 단순 `updated_at > last_seen` polling은 같은 timestamp, transaction commit 순서, 삭제 누락의 반례를 검증하기 전에는 무손실 해법으로 인정하지 않습니다.

**제출**: 상태 전이도, key/version 계약, 중복 처리 범위, schema evolution 규칙, 작은 hand-computed event history. append log·latest state·일별 합계가 동일한 저장 형태를 필요로 하지 않는 이유를 설명합니다.

## 3–4주: 파이프라인과 집계 구현

초기 snapshot과 변경 stream의 경계를 정의합니다. snapshot 도중 변경된 주문이 빠지거나 두 번 적용되지 않는지 검증합니다. snapshot watermark/LSN 또는 선택한 connector의 정확한 계약을 기록합니다. ClickHouse insert batch, retry, acknowledgment, source offset commit의 순서를 정합니다.

증분 materialized view가 받는 입력을 구분합니다. 같은 주문의 상태 버전 여러 개를 그대로 합하면 매출이 왜 중복되는지 작은 반례로 재현합니다. latest state 조회, correction delta, 주기적 rebuild 등 대안을 비교하고 선택한 방식의 backfill·취소 처리·정확성 비용을 설명합니다.

**제출**: 직접 작성한 환경 구성과 실행 지침, 정확성 oracle, 초기 적재 + 정상 변경 검증 로그, backfill 경계·중복 처리의 증거. “한 번 잘 됨” 외에 batch 경계와 재시작 위치를 바꿔 반복합니다.

## 5–6주: 장애, 복구, 용량

격리된 환경에서 다음을 각각 수행합니다. 장애마다 중단 조건·로그·복구 절차를 사전 기록합니다.

| 주입 조건 | 검증할 질문 |
| --- | --- |
| source commit 직후 consumer 중단 | 재개 시 누락·중복이 있는가? |
| sink write 성공 후 offset ack 이전 중단 | 동일 batch 재처리가 매출을 두 번 늘리는가? |
| source/consumer 사이 일시 단절 | backlog와 WAL/slot 보관량을 감당하는가? |
| 늦은 update와 삭제 뒤 과거 이벤트 | 삭제/최신 상태가 되살아나는가? |
| 분석 replica 지연 또는 분리 | 어떤 조회가 오래된 결과를 허용하는가? |
| backfill과 실시간 적재의 겹침 | 어떤 키·watermark로 중복을 검출하는가? |
| 별도 인스턴스로 backup 복구 | restore된 원본과 분석 결과의 기준 시점이 일치하는가? |

capacity 계산은 source 증가량, WAL/변경량, batch와 part 수, replica 수, retention, index·집계·임시 공간을 나눕니다. 지속 처리율이 유입률보다 낮은 경우 backlog가 사라질 수 없는 이유를 계산합니다. 평균 속도 외에 recovery 중 추가 부하와 재적재 시간을 측정합니다.

**제출**: 최소 5종의 장애 실측(중복 ack 실패와 restore는 필수), incident report, RPO/RTO 측정, 여유 공간 계산. 필요한 E2 환경을 구성하지 못한 경우 이 단계는 “설계 완료, 실행 미완료”로 남깁니다.

## 7–8주: 내부 추적, 리뷰, 연구 결과

서비스에서 관측한 병목 또는 correctness 문제를 하나 선택합니다. 관련 PG/CH 코드 경로와 입력·자료구조·동기화·출력의 관계를 설명합니다. 익숙하지 않은 사람도 실행할 수 있는 최소 재현을 만듭니다.

선택 심화는 작은 teaching engine(append log, snapshot/visibility, sparse marks, mergeable aggregate 중 하나), 엔진 regression test, source patch 중 하나입니다. 실습용 단순화와 실제 엔진에서 생략한 문제를 적습니다. 실제 source 변경은 빌드·기능 test·회귀·성능 측정이 필요합니다.

**최종 제출물**:

1. 재현 가능한 저장소 경로와 정확한 버전/설정
2. 아키텍처·correctness 계약·대안 비교·선택 근거
3. 원본/분석 정합성 보고서와 실패 이력
4. 성능·자원·backfill·restore 실측 결과
5. 최소 재현 + source trace + regression/teaching implementation
6. 아직 검증하지 못한 범위와 다음 실험

## 90분 설계 방어

첫 20분은 데이터 흐름과 보장, 다음 30분은 리뷰어가 고른 실패 시나리오, 20분은 source trace, 마지막 20분은 예상과 다른 결과를 토론합니다. “이 조건에서는 보장하지 못한다”를 정확히 말하고 대안을 제시하는 것도 평가합니다.

공통 100점 rubric에 더해 **정확성 oracle 통과, 별도 restore 성공, 중복/역순 처리 입증, 실행된 최소 재현**을 모두 필수로 봅니다. 자료 작성이나 구성도만으로 최종 완료 처리하지 않습니다.
