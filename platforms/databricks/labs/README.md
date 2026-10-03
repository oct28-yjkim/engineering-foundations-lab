# Databricks 실습 준비와 실행 범위

[트랙](../README.md) · [평가](../assessment.md) · [Spark 로컬 실습](../../../data-processing/spark/labs/README.md)

이 저장소는 Databricks 계정·workspace·warehouse·cluster·catalog·storage credential을 만들지 않습니다. 기본 시작점은 [운영 가이드](../operations.md)의 실제 query/job/pipeline 증거 분석입니다. 사용 권한과 비용 한도가 있는 비운영 환경에서만 직접 실행하고, 환경이 없으면 정제된 기존 실측 자료를 받아 분석하되 실행 gate는 미완료로 남깁니다. Spark CPU 모형은 선택 원리 부록일 뿐입니다. 무료 제공/기능 지원은 계정·cloud·시점에 따라 다르므로 무료 실행을 보장하지 않습니다.

## 세 가지 환경을 구분

| 범위 | 제공물 | 실제 필요한 준비 |
| --- | --- | --- |
| OFFLINE | [Python 표준 라이브러리 실험](../../../data-processing/spark/labs/README.md) | Python 3.10 이상; cloud 연결 없음 |
| LOCAL-SPARK | 선택 실행용 Spark 배치·file streaming 코드 | Spark/PySpark 4.0.4, Java 17/21, 새 로컬 작업 공간 |
| MANAGED-LAB | [Delta SQL fixture](delta-contract.sql), 강의별 실험 지침 | 허가된 Databricks SQL/DBR, UC catalog/schema·최소 권한·비용 한도 |

로컬 PySpark가 Databricks Runtime, Photon 또는 Unity Catalog를 대신하지 않습니다. OSS Delta를 추가로 사용할 경우 [공식 Spark/Delta 호환표](https://docs.delta.io/releases/)를 확인합니다. 이 저장소의 기본 Spark runner는 Delta package나 Maven artifact를 내려받지 않습니다. Databricks에 OSS `pyspark`를 설치해 runtime을 덮어쓰지 않습니다.

## 관리형 실습 사전 계약

실행 전에 다음 manifest를 비밀 없이 작성합니다.

- cloud(AWS/Azure/GCP)·region·workspace 식별자, 실제 실행 날짜.
- DBR 정확 버전 또는 SQL warehouse의 channel/설정·관측 시각, compute 유형·access mode·Photon 여부. Spark minor만으로 DBR 기능을 추측하지 않습니다.
- UC catalog/schema, table/volume, storage 위치의 소유자와 읽기/쓰기 권한, 실행 identity와 job run-as identity.
- 최대 실행 시간·동시성·작업 수·비용, 자동 종료/idle 정책, 실패/재시도·데이터 보존 정책.
- 합성 fixture의 schema·business key·event ID·version·삭제 계약, 기대 결과, run ID.

관리 권한을 최소화합니다. 다른 principal의 negative test는 별도의 학습용 identity와 객체만 사용합니다. 상속 권한·owner/admin·cloud storage 직접 접근을 함께 검사하며 `SELECT` 하나의 거절을 전체 데이터 격리의 증거로 쓰지 않습니다. 자격증명·token·connection string은 SQL parameter나 보고서에 넣지 않습니다.

## Delta 계약 SQL 실행

[delta-contract.sql](delta-contract.sql)은 합성 이벤트 6개를 사용해 다음을 검증할 **미실행 예제**입니다: 동일 이벤트 중복, entity별 최신 version, 같은 version의 상충 payload 거부, tombstone 보존, 재실행 멱등성, 오래된 이벤트의 삭제 취소 방지. 관리형 SQL에서 실제 실행하면 테이블을 만들고 데이터를 씁니다. 이 문서를 작성하면서 원격 실행하지 않았습니다.

1. 운영/공유 테이블이 없는 **이미 허가된 학습 schema**를 선택합니다. 이 실습은 schema나 권한을 자동 생성하지 않습니다.
2. Databricks SQL editor에서 named parameter `lab_table`을 새 3단계 이름으로 설정합니다. 예: `training_catalog.personal_lab.efl_dbx_orders_run01`. 예시 이름이 실제 존재하거나 허가됐다는 뜻은 아닙니다. 이 fixture는 영문/숫자/underscore 식별자로 제한합니다.
3. [IDENTIFIER](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-names-identifier-clause)를 지원하는 Databricks SQL 또는 DBR 13.3 LTS 이상에서 시작합니다. 이는 식별자 기능의 최소 조건이며 전체 runtime 권장/호환성 테스트 결과가 아닙니다. 다른 cloud에서도 실제 서비스 문서를 확인합니다.
4. 새 SQL session에서 파일의 번호별 구역을 **순서대로 하나씩** 실행합니다. 전 단계 오류 시 다음 단계로 진행하지 않습니다. SQL editor/다중 statement 실행이 전체를 하나의 transaction으로 만들거나 자동 중단한다고 가정하지 않습니다.
5. `CREATE TABLE`이 이름 충돌로 실패하면 멈춥니다. `OR REPLACE`나 `IF NOT EXISTS`를 덧붙이지 말고 새 이름·새 session을 선택합니다. 기존 데이터는 삭제하지 않습니다.
6. 첫 MERGE의 결과를 독립 기대값과 비교한 뒤 지정된 replay 구역만 반복합니다. 전체 파일은 temp view/table 생성 때문에 재실행용이 아닙니다. 마지막 stale update에서도 B의 tombstone이 유지돼야 합니다.

기대 결과는 **물리 행 3개**, active 행 2개, active amount 합 **175**입니다. A는 version 2/amount 125, B는 version 2/삭제/amount NULL, C는 version 1/amount 50입니다. ID별 값과 tombstone을 함께 검사하며 count만 맞으면 통과가 아닙니다. `assert_true`는 성공 시 NULL을 반환하고 조건 실패 시 오류를 발생시킵니다. [공식 assertion 함수](https://docs.databricks.com/aws/en/sql/language-manual/functions/assert_true)

음성 확장은 별도 새 session/테이블에서 source의 같은 entity/version에 다른 amount를 추가합니다. 충돌 검사가 실패하면 중단해야 합니다. 그 실패를 무시한 뒤 row_number의 임의 winner를 정합한 CDC로 부르지 않습니다. 실행기 자체가 모든 step의 stop-on-error를 강제하지 않으므로 실제 workflow에서는 동일 precondition을 코드/작업 의존성으로 구현해야 합니다.

기본 fixture는 **단일 writer**를 전제로 합니다. 충돌 guard와 MERGE는 별도 statement이므로 두 실행 사이에 다른 writer가 변경하는 경쟁 조건을 막지 못합니다. 동시 쓰기에서는 검증과 변경의 원자성·충돌 감지·재시도 후 재검증을 별도 설계하고 실제 runtime에서 입증해야 합니다.

## 이 SQL이 증명하지 않는 것

- 동시 writer·node/storage 장애·Delta log의 원자 commit과 내구성.
- 여러 테이블/외부 sink를 묶는 transaction, Kafka offset과 sink의 end-to-end exactly-once.
- UC의 row/column 권한, cloud storage 우회 접근, managed 내부 구현, 실제 Photon 성능.
- CDF 소비자 복구, 장기 보존, 별도 backup·restore, 계정별 비용.

CDC가 삭제 후 낮은 version으로 key를 재사용할 수 있다면 이 단순 version 계약은 부족합니다. source generation/epoch·순서 보장·tombstone 보존 기간을 추가로 설계합니다. 모든 historical version의 상충 이벤트를 감지하려면 이 current-state 테이블 외 별도 원장이 필요합니다.

## 종료와 보존

query history·row oracle·설정·비용 관측을 비밀 제거 후 보관하고 학습 compute를 종료합니다. 사용자가 선택한 warehouse/compute의 실제 자동 종료 설정을 확인합니다. 파일에는 DROP, DELETE, VACUUM, RESTORE나 retention 단축을 넣지 않았습니다. 생성된 테이블은 자동 삭제하지 않으며 필요 없을 때 사용자가 정확한 대상을 확인하고 정리합니다. 테이블 삭제·VACUUM·storage 수명 정책의 복구 가능성을 동일하게 취급하지 않습니다.
