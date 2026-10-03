# 04. 수집과 스트리밍: 파일·event·업무 상태의 세 원장

[커리큘럼](../curriculum.md) · [Spark 실습](../../../data-processing/spark/labs/README.md)

<a id="d07"></a>
## D07 — Auto Loader의 발견과 업무 중복 제거

Auto Loader의 `cloudFiles`는 관리형 환경의 증분 파일 수집 경로입니다. 파일 발견 상태·schema 추적·stream checkpoint·Delta sink commit을 연결하지만, 동일한 business event를 담은 서로 다른 두 파일을 자동으로 같은 업무 event로 만드는 계약은 아닙니다. checkpoint를 유지한 source/sink 조합의 exactly-once 설명을 모든 외부 API side effect에 확장하지 않습니다. [Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader)

**세 개의 원장:** 입력 파일 목록(path, synthetic checksum, 생성 시각), 파일 안 event 목록(event_id, entity_id, sequence), 최종 업무 state를 각각 만듭니다. 하나의 파일에10개의 event가 있고 다른 파일에 그중2개가 중복되어 있으면 파일 수2, 읽은 row12, unique business event10을 서로 다른 측정값으로 기록합니다.

**CPU 기본:** 제공된 [로컬 실습 안내](../labs/README.md)의 merge/watermark 모델로 중복·역순·지연 경계를 연습합니다. 이것은 Auto Loader의 RocksDB/checkpoint나 file notification을 실행한 결과가 아닙니다. 로컬 Spark file stream도 `cloudFiles` 구현을 재현하지 않습니다.

**MANAGED-OPTIONAL 파일 시나리오:** 새 synthetic 전용 volume/location과 신규 checkpoint를 사용합니다. 파일 발견 mode·사용 region·권한·source overwrite 정책을 지문에 포함합니다. cloud event mode는 계정 설정과 외부 자원 비용이 생길 수 있으므로 자동 생성하지 않습니다.

| 입력/장애 | 사전 기대와 확인할 증거 |
| --- | --- |
| f1 정상, f2에 f1의 event 일부 중복 | 두 파일 발견과 business dedup를 분리; 최종 ID/sequence oracle |
| nullable field 추가 | schema evolution mode별 성공/중단/rescue와 restart 경계 |
| 숫자 field에 문자열 | rescue/quarantine 기대; 정상 row와 불량 row 총수 보존 |
| sink commit 후 응답/driver 종료 | 같은 checkpoint로 복구 후 table state 불변식 |
| 오래 뒤 새 파일 도착 | discovery 순서와 event time 순서를 분리 |

모든 장애는 테스트 workload에만 주입합니다. 기존 checkpoint 삭제나 shared cluster 종료를 재시도 방법으로 쓰지 않습니다. 각 ingestion workload의 checkpoint 소유자를 하나로 두고 같은 checkpoint를 여러 독립 query에 공유하지 않습니다. [schema 문서](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema)에서 schema location과 query checkpoint의 역할·형식별 inference 차이를 확인합니다.

**gate:** discovered file ledger, accepted/quarantined event ledger, final state가 모두 맞아야 합니다. `_rescued_data`가 존재하는데 정상 성공 row로 조용히 집계하거나, checkpoint를 새로 만들어 replay 위험을 숨기면 실패입니다.

<a id="d08"></a>
## D08 — 선언형 graph·CDC·checkpoint 계약

선언형 pipeline의 dataset 함수는 실행 순서에 따라 부작용을 내는 imperative script가 아니라 DataFrame graph를 기술합니다. 함수 평가 중 외부 API 전송·임의 INSERT·비멱등 파일 쓰기를 넣으면 planning/재평가 시점과 business effect 횟수가 분리됩니다. Python closure를 loop에서 만들 때 모든 node가 마지막 변수값을 참조하는 버그도 작은 fixture로 검출해야 합니다.

2026-10-04 공식 문서 기준, OSS `pyspark.pipelines`는 **Spark4.1부터**이며 이 저장소의 Spark4.0.4 기본 로컬 환경에는 해당 API가 없습니다. Lakeflow의 `create_auto_cdc_flow`, expectations 등 관리형 확장은 OSS에 그대로 포함된다고 가정하지 않습니다. 본 모듈의 API 실험은 지원되는 managed 환경 또는 별도로 호환성을 검증한 선택 환경에서 수행합니다. [Python pipeline 문서](https://docs.databricks.com/aws/en/ldp/developer/python-dev), [프레임워크 구분](https://docs.databricks.com/aws/en/ldp/)

**graph 설계:** bronze(raw + provenance)→silver(canonical event + quarantine)→gold(current order state 또는 합계)를 선언합니다. bronze/silver/gold는 이름이지 정확성 보장 기능이 아닙니다. streaming table, materialized view, batch recomputation의 갱신 의미를 선택 이유와 함께 적습니다. incremental refresh 여부는 실제 plan/event log로 확인하고 “MV이므로 언제나 증분”이라고 하지 않습니다.

**독립 oracle:** D04의 event fixture에 다음3개를 더합니다. 모든 기대는 실행 전에 적습니다.

1. 과거 event time이지만 새 sequence인 수정: event-time window 폐기와 latest entity state를 같은 정책으로 처리하면 어떤 요구를 놓치는가?
2. 같은 entity·sequence에 다른 payload: 결정 불가 입력을 error/quarantine으로 분리하는가?
3. NULL key 또는 음수 금액: expectation의 warn/drop/fail 선택이 총수·업무 SLO에 어떤 결과를 주는가?

quarantine row는 비밀 없이 원인·source file·event ID를 보존합니다. `input = accepted + quarantined + 명시적으로 분류한 duplicate/stale`의 accounting 계약을 정의합니다. 집합이 겹치지 않도록 분류 우선순위를 고정해야 합니다.

**failure 과제:** 같은 checkpoint 재시작, query logic/schema 변경, source retention 초과를 서로 다른 실험으로 둡니다. 정상 stop/restart 가능한 변경과 새 checkpoint/재수집이 필요한 변경을 실제 버전 문서로 검토합니다. full refresh는 보존된 source로부터 재계산하는 동작일 수 있으므로 source가 이미 사라졌다면 과거 결과를 재구성할 수 없습니다. 전체 pipeline reset/full refresh를 기본 복구 명령으로 실행하지 않습니다.

**gate:** DAG, source retention, checkpoint owner, output table version, quarantine, replay oracle와 quality metric의 관계를 설명합니다. 지연 event를 버리는 정책을 “정확성 문제 없음”으로 표현하지 말고 허용한 데이터 손실 계약과 보정 경로를 제출합니다.
