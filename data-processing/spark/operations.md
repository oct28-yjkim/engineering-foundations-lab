# Spark 운영 실습: 실행계획·UI·event log로 원인을 설명하기

[트랙](README.md) · [공통 운영 계약](../../operations/README.md) · [장애 보고서](../../operations/incident-report-template.md)

고정 기준은 Spark/PySpark 4.0.4입니다. 기본 실무 경로는 실제 job의 정상 baseline → stage/task 병목 → 한 변인 재현 → 결과·복구 확인입니다. CPU 원리 모형은 선택 부록입니다. 이 문서의 장애 사례는 실행 지침이며 실제 클러스터에서 통과한 결과가 아닙니다.

## 1. 실제 관측 준비

[실습 안내](labs/README.md)의 Java·PySpark·소유한 output/checkpoint 경계를 먼저 확인합니다. application ID, job/stage/task attempt, SQL execution ID, query ID/run ID를 연결하고 version·master·driver/executor 자원·입력 fingerprint·AQE 설정·시간대를 기록합니다. `local[2]`는 실제 Spark지만 다중 호스트 장애 환경이 아닙니다.

실행 중 UI의 **Jobs → Stages → 해당 stage의 task 분포**, **SQL → physical plan**, **Executors → task/GC/shuffle**, **Environment → 유효 설정**을 확인합니다. 기본 포트는 4040이지만 충돌 시 달라질 수 있으므로 실제 driver 로그의 URL을 사용합니다. job 종료 뒤 분석하려면 시작 전에 `spark.eventLog.enabled=true`와 학습자가 소유한 `spark.eventLog.dir`를 설정하고 History Server에 연결해야 합니다. 제공 runner가 event log·History Server를 자동 구성한다고 가정하지 않습니다. [4.0.4 monitoring](https://spark.apache.org/docs/4.0.4/monitoring.html)

이미 실행 중이고 loopback으로 안전하게 접근 가능한 UI의 읽기 전용 예입니다. 다른 host/공유 UI로 자동 전환하지 않습니다.

```powershell
Invoke-RestMethod 'http://127.0.0.1:4040/api/v1/applications'
```

응답의 자신의 application ID를 URL-encode하여 `/api/v1/applications/{app-id}/jobs`, `/stages`, `/executors`를 조회합니다. History Server에서 attempt가 있는 앱은 해당 attempt 경로를 사용합니다. UI/event log에는 SQL literal·파일 URI·사용자 정보가 포함될 수 있으므로 원본 전체 공개는 금지합니다. 환경에 Java/Spark가 없으면 정제된 실제 UI/event log 자료를 받아 분석하고 실행 관문은 미완료로 남깁니다.

baseline은 동일 합성 입력·동일 실행계획 조건의 정상 run을 3회 비교하는 탐색부터 시작합니다. 성능 결론에는 [공통 측정 규칙](../../databases/shared/experiment-method.md)의 warmup·반복·cache 조건이 추가됩니다. 스트리밍은 최소 5분 또는 충분한 micro-batch 수를 사전에 정하고 빈 batch를 실패/미수집과 구별합니다.

## 2. 지표를 읽는 단위

| 관측값 | 타입·단위·범위 | 잘못된 해석 방지 |
| --- | --- | --- |
| task duration·scheduler delay·executor run time | task attempt별 시간, UI 표기 단위 확인 | max/median과 분포를 비교. speculative/retried attempt 중복을 제외하는 규칙 명시 |
| shuffle read/write·fetch wait | attempt별 bytes·records·시간 | 많은 shuffle이 항상 병목은 아님. skew·join cardinality·network·stage wall time과 대조 |
| memoryBytesSpilled / diskBytesSpilled | task attempt 누적 bytes | 메모리 spill의 추정 deserialized 크기와 disk serialized 크기는 동일하지 않음. 두 수를 더해 실제 디스크 점유로 쓰지 않음 |
| JVM GC time·executor runtime | attempt 또는 executor 누적 ms | 같은 집계 범위끼리 비교. GC 시간 합을 job wall time으로 나누면 병렬 실행으로 100% 초과 가능 |
| peak execution memory·executor process 메모리 | 연산자/task peak 또는 process gauge, bytes | storage memory·JVM heap·Python worker·off-heap·driver 메모리는 서로 다른 영역 |
| streaming `numInputRows`, `durationMs` | 최근 batch 입력 rows와 단계별 ms | 누적 counter가 아니라 batch record. `batchId`·query ID/run ID와 함께 보존 |
| `inputRowsPerSecond`, `processedRowsPerSecond` | progress가 계산한 rows/s | 서로 계산 구간이 다를 수 있으며 source backlog 자체가 아님. source offset/파일 대기·업무 freshness와 함께 확인 |
| `stateOperators`의 numRowsTotal·memoryUsedBytes, eventTime.watermark | state snapshot rows·bytes, event-time 시각 | watermark를 wall-clock 지연 또는 데이터 완전성 보증으로 간주하지 않음 |

UI 항목은 [4.0.4 Web UI](https://spark.apache.org/docs/4.0.4/web-ui.html), progress는 [Structured Streaming 관측](https://spark.apache.org/docs/4.0.4/streaming/apis-on-dataframes-and-datasets.html#monitoring-streaming-queries)을 기준으로 합니다. metric sink/exporter의 이름·type·label을 직접 확인하며 애플리케이션 종료/재시작 시 누적값 reset을 표시합니다.

## 3. 네 가지 진단 카드

수동 재현은 소유한 로컬/격리 환경에만 적용합니다. 합성 입력 최대 100,000행·100 MiB, 실행 최대 5분, 동시 job 1개부터 시작하고 메모리 부족 징후가 있으면 중단합니다. production executor kill, 임의 메모리 과할당, checkpoint 삭제, disk full은 재현 수단이 아닙니다.

| 증상·제한 재현 | 경쟁 가설과 관측 순서 | 완화·원복 | 복구·정합성 증거 |
| --- | --- | --- | --- |
| 한 task가 길게 남음: 같은 크기 입력의 key 분포만 hot key로 변경 | skew / 느린 executor / 원격 fetch. task max/median·partition bytes·host·fetch wait·initial/final AQE plan 비교 | 원래 분포로 복귀. 실제 근거가 있으면 AQE 또는 의미 보존 salting 한 가지만 평가 | PK별 결과·합계 보존, task tail과 stage wall time 동시 회복 |
| spill·GC 증가: 기존 bounded 입력에서 partition 배치만 비교 | 큰 partition / join 폭증 / Python memory / driver collect. plan cardinality·spill·GC·process 메모리·driver 로그 대조 | 변경한 partition/코드 원복; collect 제거·projection 등 원인별 한 변경. 모든 경우 executor 메모리 증설로 결론내리지 않음 | 동일 output fingerprint, OOM/재시도 없음, spill·GC와 runtime 분포 회복 |
| streaming backlog·freshness 악화: bounded 파일 도착률만 높임 | source 증가 / sink 지연 / state 증가 / 늦은 event. progress·batch duration·state·source manifest·sink 최신 업무시각 대조 | 입력을 baseline으로 낮추고 sink 지연 해소. 기존 checkpoint 보존, 호환 설정만 복원 | source ID와 sink ledger 일치, backlog와 업무 freshness 회복. watermark 전진만으로 종료하지 않음 |
| 재시작 후 중복·누락 우려: 학습 query 정상 stop 후 같은 checkpoint로 재시작 | checkpoint 변경 / sink 비멱등 / source 재생성 / schema 비호환. query ID/run ID·offset·sink commit·배포 diff 확인 | 기존 호환 코드/설정으로 원복, 손상 의심 state는 보존하고 별도 복사본에서 조사 | 정상 재시작과 crash recovery의 범위를 구분하고 business ID·값·중복 검산 |

네 번째 카드의 기본 runner는 **정상 종료/재시작**만 다룹니다. crash나 executor host loss는 별도 환경과 승인된 실패 실험이 있어야 통과합니다. 성능 개선은 결과가 같다는 gate 이후에만 주장합니다.

## 4. 14모듈 관측 산출물

| 모듈 | 원리·소스와 연결할 증거 |
| --- | --- |
| SP01 | action→job/stage/task ID와 UI 실행 시각 |
| SP02 | dependency·partition·재계산과 attempt 구분 |
| SP03 | analyzed/optimized/physical 계획과 SQL 결과 |
| SP04 | UDF/built-in plan·직렬화·task 시간 비교 |
| SP05 | join cardinality·shuffle read/write·fetch wait |
| SP06 | task 분포·initial/final AQE plan·skew 대응 |
| SP07 | spill·GC·executor/driver/Python 메모리 분해 |
| SP08 | 파일 수·scan bytes·pruning·동일 행 fingerprint |
| SP09 | batch별 input/event time/watermark·late event 원장 |
| SP10 | query/run ID·checkpoint·sink commit·재시작 원장 |
| SP11 | UI·event log·metrics 접근 경계와 ID 상관관계 |
| SP12 | 장애 2개·복구 시각·정합성·비용/자원 상한 |
| SP13 | 관측 병목을 Catalyst/AQE/scheduler/state 소스에 연결 |
| SP14 | baseline·두 사건·개선 전후 plan/metrics·복구 보고서 |

운영 gate는 실제 baseline 1개, 상이한 증상 2개, 경쟁 가설·완화·원복·업무 정합성/지표 회복 증거입니다. 로컬 한계를 명시하고 cluster 관문은 별도로 유지합니다. CPU 모형·AST/mock 테스트 통과는 이 gate의 제출물이 아닙니다.
