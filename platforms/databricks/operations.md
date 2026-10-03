# Databricks 운영 실습: query·job·pipeline·비용을 연결하기

[트랙](README.md) · [공통 운영 계약](../../operations/README.md) · [장애 보고서](../../operations/incident-report-template.md)

기본 경로는 실제 Query History/Profile·Jobs·compute metrics·pipeline freshness의 증거를 읽고 원인을 설명하는 것입니다. Spark CPU 모형은 선택 원리 부록입니다. 계정이 없으면 관리자가 정제해 제공한 기존 실제 실행 자료로 분석합니다. 가짜 지표를 실제 측정이라고 쓰거나 새 유료 workspace를 자동 생성하지 않습니다. 아래 SQL/사건은 실행 지침이며 이번 개편에서 managed 실행한 결과가 아닙니다.

## 1. 실행 전 권한·비용·범위

cloud/region/workspace, DBR 또는 warehouse channel, compute/access mode, Photon, catalog/schema, 실행 principal, run/query/update ID와 관측 시간을 기록합니다. 아래 링크는 AWS 문서이며 Azure/GCP 지원·권한·스키마는 실제 cloud 문서에서 재확인합니다. 사용자는 비운영 객체의 조회 권한과 쿼리 비용/시간 상한을 먼저 확보합니다. **SELECT도 stopped warehouse를 시작하거나 과금할 수 있습니다.** 권한이 없으면 GRANT나 admin token 발급으로 우회하지 않고 권한 있는 담당자에게 최소 정제 자료를 요청합니다.

system table은 UC와 해당 schema의 가용성·활성 상태 및 `USE CATALOG`, `USE SCHEMA`, `SELECT`가 필요합니다. 접근 가능한 행, 수집 지연, 보존기간은 table/region별로 확인합니다. 빈 결과는 장애 없음 또는 사용량 0의 증명이 아닙니다. [System tables](https://docs.databricks.com/aws/en/admin/system-tables/)

## 2. 실제 관측 위치와 읽기 전용 예

1. **SQL → Query History → 소유 query → Query Profile**: 대기/실행 시간, scan·join·shuffle·spill과 계획을 확인합니다. 프로필 미지원/미보존과 실행 안 됨을 구분합니다. [Query Profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile)
2. **Jobs & Pipelines → 소유 job → run → task**: queue·setup·execution·retry·오류·Spark UI를 같은 run ID로 연결합니다. 시스템 테이블 timeline의 한 행이 run 한 개는 아닙니다. [Jobs tables](https://docs.databricks.com/aws/en/admin/system-tables/jobs)
3. **Compute → 해당 classic compute → Metrics / Spark UI**: CPU·메모리·network·driver/executor를 확인합니다. serverless와 SQL warehouse에 classic compute 화면·지표가 동일하게 제공된다고 가정하지 않습니다. [Compute metrics](https://docs.databricks.com/aws/en/compute/cluster-metrics)
4. **소유 pipeline → update/flow 상세·event log**: 진행·오류·data quality와 target freshness를 비교합니다. update 성공과 최신 업무 데이터 반영은 별개입니다. [Pipeline monitoring](https://docs.databricks.com/aws/en/ldp/observability)

승인된 query editor에서 실행할 수 있는 읽기 전용 SQL입니다. `:workspace_id`는 실제 허가 범위의 named parameter로 설정합니다. 먼저 `DESCRIBE TABLE system.query.history`로 열 존재를 확인하고 민감한 statement text는 선택하지 않습니다.

```sql
SELECT statement_id, start_time, execution_status,
       total_duration_ms, waiting_for_compute_duration_ms,
       waiting_at_capacity_duration_ms, execution_duration_ms
FROM system.query.history
WHERE workspace_id = :workspace_id
  AND start_time >= current_timestamp() - INTERVAL 1 HOUR
ORDER BY start_time DESC
LIMIT 100;
```

열의 의미·수집 대상은 [Query history schema](https://docs.databricks.com/aws/en/admin/system-tables/query-history)와 비교합니다. query text를 보지 않고도 statement ID로 허가된 UI에 연결할 수 있습니다. 아래는 job **timeline 구간** 조회이며 결과 행 수를 실행 횟수로 세지 않습니다. 실행 식별자는 workspace/job/run 조합으로 보존합니다.

```sql
SELECT workspace_id, job_id, run_id, period_start_time,
       period_end_time, result_state
FROM system.lakeflow.job_run_timeline
WHERE workspace_id = :workspace_id
  AND period_start_time >= current_timestamp() - INTERVAL 1 DAY
ORDER BY period_start_time DESC
LIMIT 100;
```

LIMIT는 전체 scan 비용 상한을 보장하지 않습니다. time·workspace 필터와 실행 시간 상한을 함께 사용합니다. 알려진 정상 query/job 3회의 profile과 동일 업무 시간대의 1시간 창을 baseline으로 잡되 cache·동시성·입력·compute 크기를 기록합니다. 최종 성능 비교는 별도 충분한 반복을 수행합니다.

## 3. 지표 계약

| 관측값 | 타입·단위·집계 창 | 주의점 |
| --- | --- | --- |
| query total/waiting/execution duration | statement별 ms | total은 결과 fetch 제외. capacity 대기와 compute 준비 대기 분리; p95를 만들 때 실패·취소 분모 공개 |
| query profile scan/shuffle/spill | query/operator별 bytes·rows·시간 | runtime·engine에 따라 제공 필드가 다름. wall time과 task 시간 합을 혼합하지 않음 |
| job run result·timeline | 상태와 시간 구간 | 시간 경계에 걸친 장기 run과 repair/retry를 구분; COUNT(*)는 run 수 아님 |
| compute CPU·memory·network | UI의 percent/bytes/rate 및 집계 간격 | driver/executor·node별 관측; serverless에서 미노출이면 unknown |
| pipeline freshness | 관측 시각 − 검증된 최신 업무 반영 시각, seconds | source event clock과 ingestion/commit 시각 구분. max(event_time)만으로 누락·미래 시각 이상을 숨기지 않음 |
| `system.billing.usage` usage_quantity / usage_unit | 사용 기간별 청구 사용량 record | process counter 아님. unit·SKU·기간·retraction/restatement를 고려. DBU가 통화 비용이나 최종 invoice와 같지 않음 |

비용 분석에는 [billing usage schema](https://docs.databricks.com/aws/en/admin/system-tables/billing)를 사용하고 계약 단가·유효기간·추가 cloud 비용·세금을 별도 처리합니다. 시스템 테이블 수집 지연 때문에 실시간 비용 차단을 대신하지 못합니다.

## 4. 네 가지 트러블슈팅 카드

기본은 기존 정제 incident 분석입니다. 실제 재현은 사용자가 승인한 비운영 workspace·자신의 job/table·합성 입력 최대 100,000행·동시 실행 1개·최대 10분 및 금액 상한을 갖춘 경우만 수동 선택합니다. 유료 resource 증설, 타인 작업 취소, storage/IAM 변경, full refresh, VACUUM, checkpoint 삭제를 자동 수행하지 않습니다.

| 증상·선택 재현 | 경쟁 가설·검증 순서 | 완화·원복 | 복구 증거 |
| --- | --- | --- | --- |
| query p95 증가: 자신의 bounded query에서 한 predicate/입력 배치만 변경 | capacity queue / compute cold start / scan 증가 / join skew. query history 대기 분해→profile→compute 상태·cache 비교 | 이전 query/입력으로 복원, 자신의 불필요 실행만 중지. 증설은 별도 비용 승인 후 | 동일 결과 fingerprint·대기/실행 시간 분포·오류·query당 비용 비교 |
| job 재시도 증가·실행 지연: 비운영 task에 즉시 실패하는 합성 검증 조건 1회 | 데이터 품질 / transient dependency / 권한 / run_as 변경. task error·실행 identity·배포 diff·입력 schema 비교 | 잘못된 조건/배포만 원복, 재실행 전 멱등성 검증; retry 횟수부터 늘리지 않음 | 최종 성공뿐 아니라 중복 mutation 없음·동일 ID 결과·실패 분모·전체 복구 시간 |
| pipeline 성공이나 target가 오래됨: fixture의 제한된 source 도착 지연 | source 정체 / quality reject / flow backlog / 잘못된 event time. source manifest·flow/event log·target PK/commit/freshness 연결 | source 지연 제거·오류 입력을 소유 격리 영역에서 수정. 무조건 full refresh하지 않음 | source→target ID 대응·quality 거절 원장·freshness 회복·checkpoint 보존 |
| 비용 증가: 실제 지출 재현 대신 기존 usage/profile 창 비교 | 사용량 증가 / SKU·compute 변경 / retries / idle / billing correction. 같은 업무량·시간·단위로 job/query와 usage 기록을 대조 | 소유 실습의 예약·동시성/실행 설정을 원래대로 복원. 실제 종료·예약 변경은 사용자 승인 범위에서만 | 단위 업무당 사용량·성능·정합성 회복, 지연 도착/수정 billing 기록까지 재검산 |

## 5. 14모듈 운영 산출물

| 모듈 | 관측·진단 제출물 |
| --- | --- |
| D01 | workspace/identity/compute/storage 관측 경계 지도 |
| D02 | query/run ID·runtime 지문·plan·정상 profile |
| D03 | Delta history·충돌/retry·commit version·PK oracle |
| D04 | MERGE 입력 중복·변경 이력·schema/protocol 경계 |
| D05 | 실제 합성 주체 allow/deny·run_as·접근 오류 |
| D06 | audit/lineage 가용 범위와 직접 storage 경로 위협 |
| D07 | 발견 파일 원장·ingest progress·target freshness |
| D08 | flow/update·quality rejection·재시도·누락 검산 |
| D09 | Query History/Profile·scan/skew·cache별 비교 |
| D10 | SKU/unit/기간별 비용 원장·수정·업무량 대비 사용량 |
| D11 | deploy/run identity·job/task timeline·rollback diff |
| D12 | 격리 복구의 데이터·권한·checkpoint·RPO/RTO |
| D13 | 공개 source/논문 가설과 관측 가능한 managed 경계 |
| D14 | baseline·상이한 사건 2개·복구·정합성·비용 한계 |

실제 운영 gate는 정상 baseline 1개, 상이한 사건 2개, 경쟁 가설 배제, 완화/원복과 업무·지표 회복 증거입니다. 새 유료 장애를 만들 필요는 없으며 권한 있는 기존 사건의 실제 회복 기록도 사용 가능합니다. 자료 분석만 가능하면 분석 gate를 기록하고 직접 실행/복구 gate는 미완료로 둡니다. CPU 모델로 관리형 기능 수료를 대체하지 않습니다.
