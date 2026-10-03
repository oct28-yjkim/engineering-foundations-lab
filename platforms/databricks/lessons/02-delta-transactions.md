# 02. Delta: 파일 존재와 table commit은 다른 사건이다

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md)

<a id="d03"></a>
## D03 — snapshot·OCC·commit의 불변식

Delta의 현재 table은 directory listing의 모든 Parquet 파일이 아닙니다. reader는 protocol·metadata와 log action을 해석해 특정 snapshot의 active file 집합을 구성합니다. writer가 새 파일을 만들었어도 commit되지 않으면 그 snapshot에는 나타나지 않아야 합니다. 체크포인트는 log replay 비용을 줄이는 표현이지 별도 business transaction이나 독립 backup이 아닙니다. 세부 표현은 protocol version에 따라 확장되므로 JSON의 `add`/`remove`만 아는 parser를 범용 Delta reader라고 부르지 않습니다. [고정 protocol](https://github.com/delta-io/delta/blob/6d055c5c8a2e16bbf4458268a1bc271c7afcc4d2/PROTOCOL.md)

**CPU-MODEL 설계 과제:** 학생이 작은 action reducer를 만들고 다음 모델의 expected set을 수기로 먼저 작성합니다. 이는 실제 Delta writer/locking/object store 구현이 아닙니다.

| version | 모델 action | active files oracle |
| --- | --- | --- |
| 0 | add A, add B | A,B |
| 1 | remove A, add C | B,C |
| 미commit | 물리 파일 X 생성만 | 여전히 B,C |
| 2 | remove B, add D | C,D |

동일 action을 반영한 snapshot 재구성과 실제 row 결과의 검증은 다른 oracle입니다. 중복 row를 가진 파일을 합치면 file set은 맞아도 업무 결과가 틀릴 수 있습니다. 반드시 key/value 집합도 비교합니다.

**LOCAL-DELTA 선택 과제:** [호환표](https://docs.delta.io/releases/)에 맞는 별도 환경에서 작은 synthetic table을 만들고 version별 history·schema·PK/값을 저장합니다. 초기 table은 새 학습용 디렉터리만 사용합니다. log 파일을 직접 편집하거나 object를 지우지 않습니다. [소스 지도](../source-reading.md)의 `DeltaLog`→`Snapshot`→`OptimisticTransaction`→`ConflictChecker`에서 read set, write set, commit attempt, conflict 검사 위치를 찾습니다.

**2writer 실험:** 두 writer가 같은 snapshot에서 같은 key 변경을 계산하도록 barrier를 둡니다. 서로 다른 key/동일 key, append/read-modify-write를 별도 실험으로 구성합니다. 성공 commit version, 예외 종류, retry 전에 다시 읽은 version, 최종 key/value를 기록합니다. 실패하지 않았다는 사실을 lost update가 없다는 증거로 쓰지 않습니다. 재시도는 stale 계산을 그대로 재발행하는 것과 새 snapshot에서 재계산하는 것을 구분합니다.

관리형의 WriteSerializable/Serializable 및 row-level concurrency는 table feature·runtime·연산 조건에 따라 다릅니다. OSS의 file-level conflict 실험을 managed row-level concurrency 증거로 제시하지 않습니다. 이 강의의 기본 보장 범위는 **선택한 table 하나**입니다. multi-table transaction이 필요한 경우 실제 제품/기능/제약을 별도로 확인하고 기본 실험에서 자동 보장하지 않습니다. [관리형 isolation](https://docs.databricks.com/aws/en/optimizations/isolation), [row-level concurrency](https://docs.databricks.com/aws/en/optimizations/isolation/row-level-concurrency)

**gate:** reader snapshot, 물리 파일 생성, atomic commit, 응답 수신의 시점을 구분한 history와 정답을 제출합니다. “ACID이므로 어떤 앱 재시도도 안전”이라는 설명은 실패입니다.

<a id="d04"></a>
## D04 — MERGE·schema·CDF·retention

MERGE 문장을 썼다고 source가 저절로 canonical해지지는 않습니다. 같은 business key의 source 중복, 역순 event, stale sequence, delete 뒤 오래된 upsert를 어떤 규칙으로 처리할지 먼저 정해야 합니다. 매칭 duplicate의 허용/오류 판정도 DBR 조건과 절에 따라 달라질 수 있으므로 특정 버전의 문서를 기록합니다.

저장소의 별도 [Delta SQL 실습](../labs/delta-contract.sql)은 새 관리형 학습 table을 대상으로 source 정규화·monotonic MERGE·tombstone·정답을 확인하는 시작점입니다. [실습 안내](../labs/README.md)의 대상/비용/권한 준비를 먼저 읽습니다. 아래 fixture는 추가 연구 과제로 입력이 다르며 해당 SQL의 예상 결과와 혼합하지 않습니다. 관리형 SQL은 이 교재 작성 과정에서 실행하지 않았습니다.

**수기 oracle fixture:** 금액은 integer cents, event ID는 globally unique, 동일 entity sequence의 상충 payload는 quarantine으로 정합니다. 아래는 저장소 실행 파일이 아니라 학생 구현 과제입니다.

| 도착 순서 | event | 기대 latest state |
| --- | --- | --- |
| 1 | e1: order A, seq1, UPSERT 1000 | A=1000, seq1 |
| 2 | e2: order A, seq2, UPSERT 1500 | A=1500, seq2 |
| 3 | e2와 동일한 replay | 변하지 않음 |
| 4 | e3: order A, seq1, UPSERT 800 | stale로 적용하지 않음 |
| 5 | e4: order B, seq1, UPSERT 500 | A=1500,B=500 |
| 6 | e5: order A, seq3, DELETE | visible B=500; A seq3 tombstone 유지 |
| 7 | e1 replay | A를 부활시키지 않음 |

물리 DELETE만 하고 latest sequence를 잃으면 7번에서 A가 부활할 수 있습니다. tombstone/version ledger의 retention도 business replay horizon과 연결해야 합니다. source를 정규화한 뒤 target과 병합하고, 전체 batch 두 번 적용·잘린 batch 뒤 재시작·도착 순서 변화에 대해 visible state와 ledger를 비교합니다. DBR `MERGE` 실행 자체는 MANAGED-OPTIONAL이며 CPU 정답 모델과 구분합니다.

**schema/protocol 과제:** nullable column 추가, incompatible type, column rename/drop, reader/writer feature 변경을 각각 독립 table에서 설계합니다. schema evolution 허용과 reader protocol 호환성은 다른 축입니다. 이전 client로 읽기/쓰기 가능한지 matrix를 만들고, 실행 불가 조합은 문서 근거와 미실행을 표시합니다. 전역 auto-merge를 켜서 모든 잘못된 입력을 받아들이지 않습니다.

**CDF 과제:** insert/update preimage/postimage/delete와 commit version을 업무 ID 원장에 대조합니다. CDF를 켜기 전 history나 보존 창 밖의 변경을 무제한 제공한다고 가정하지 않습니다. consumer가 보존 창을 넘겨 중단됐다면 snapshot 재동기화와 version 경계를 어떻게 정할지 설계합니다. source change 1건과 downstream write 1건은 같지 않으며 consumer의 idempotency가 추가로 필요합니다. [CDF 문서](https://docs.databricks.com/aws/en/delta/delta-change-data-feed)

**파괴 없는 retention 실험:** 수기 모델에서 과거 version이 참조하는 data/log를 unavailable로 표시하여 restore 실패를 확인합니다. 실제 managed에서는 history 조회와 지원되는 dry-run 계획까지만 기본 범위로 삼습니다. retention safety를 끄거나 보존기간을 줄여 파일을 지우는 명령은 제공하지 않습니다. time travel에는 data와 log가 함께 필요하며 `RESTORE`는 새로운 변경을 만들어 downstream에서 재처리될 수 있습니다. [history/restore](https://docs.databricks.com/aws/en/tables/history), [VACUUM](https://docs.databricks.com/aws/en/tables/operations/vacuum)

**gate:** replay 후 정확한 key/value/tombstone, 충돌 입력의 격리, protocol reader matrix, 보존기간과 최대 지연의 계약을 제출합니다. “history가 보이므로 backup 완료”는 실패입니다.
