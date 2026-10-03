# 03. Unity Catalog: 이름·권한·object bytes를 함께 통제한다

[커리큘럼](../curriculum.md) · [실습 범위](../labs/README.md)

<a id="d05"></a>
## D05 — principal과 권한 계층

catalog.schema.object는 namespace인 동시에 권한 검토의 단위입니다. data access에는 상위 객체의 사용 권한과 대상 객체의 권한을 함께 고려해야 합니다. workspace 로그인, compute 사용 가능, table 조회 가능, 권한 재부여 가능은 서로 다릅니다. owner·admin·MANAGE principal을 일반 사용자 테스트의 대용으로 사용하면 격리 실패를 놓칩니다. [권한 참조](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/privileges-reference), [grant·owner 관리](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/)

**DESIGN 기본 과제:** synthetic tenant A/B마다 별도 schema/table을 갖고, 각 tenant에 reader·writer·운영자 principal을 정의합니다. namespace만 다르게 만든 것은 보안 설정이 아닙니다. 명시 grant, 상속, group membership, ownership, workspace binding, compute 조건을 모두 적어야 합니다.

| 실제 테스트 주체 | A 조회 | A 쓰기 | B 조회/쓰기 | 권한 변경 |
| --- | --- | --- | --- | --- |
| reader_A | 허용 | 거부 | 거부 | 거부 |
| writer_A | 허용 | 허용된 workload만 | 거부 | 거부 |
| reader_B | 거부 | 거부 | B 조회만 허용 | 거부 |
| ops principal | 승인된 명시 범위 | 승인된 명시 범위 | 별도 계약 | 감사 대상 |

현재 제품에서 MODIFY만으로 표현되는 쓰기 범위와 세분화 DML privilege의 지원 상태를 구분합니다. 문서상 beta 기능을 계정 전체의 안정 계약으로 삼지 않습니다. SELECT 필터링으로 업무 수정 권한이 해결되었다고 가정하지 않습니다.

**MANAGED-OPTIONAL:** 승인된 독립 catalog/schema와 synthetic principal들에서 matrix의 모든 칸을 실제 각각의 인증 세션으로 검사합니다. 이름만 다른 변수를 같은 admin token으로 실행하면 무효입니다. 테스트 코드가 임의의 principal을 impersonate할 수 있다고 가정하지 말고 지원된 인증·실행 identity 경로를 사용합니다. 각 request의 익명화 principal ID, 대상, operation, 기대, actual error/result, 변경 전후 state를 기록합니다.

**반례 실험:** grant를 table에서 철회했어도 상위 schema/group에서 같은 privilege를 상속하면 접근이 남을 수 있습니다. direct grant와 effective privilege를 분리하고, 실제 신규 요청으로 재검증합니다. 기존 query·이미 내려받은 결과·캐시는 별도 경계입니다. row filter/column mask/ABAC를 추가한다면 해당 runtime·access mode 지원과 직접 파일 읽기 경로까지 새 음성 테스트를 만듭니다. tag만 붙였다고 policy가 집행되지는 않습니다.

**gate:** 허용·거부 모두 증거가 있어야 하며, “query 실패”를 곧바로 권한 성공으로 판정하지 않습니다. 존재하지 않는 table·network 장애·잘못된 token도 실패를 만들므로 positive control을 함께 실행합니다. 로컬 권한 matrix 계산은 기대 정의이며 실제 UC 검증이 아닙니다.

<a id="d06"></a>
## D06 — external storage·lineage·audit·sharing

관리형 asset과 external asset은 storage lifecycle 책임이 다릅니다. table 권한, volume 권한, external location/storage credential 권한, cloud IAM을 하나의 ACL로 합치지 않습니다. managed storage의 내부 경로를 임의로 직접 수정하거나 checkpoint와 무관한 데이터를 그 경로에 섞지 않습니다. OSS Unity Catalog 구현도 관리형 UC의 모든 정책·감사·network 기능과 동일하지 않습니다. [Unity Catalog 개요](https://docs.databricks.com/aws/en/data-governance/unity-catalog/)

**경계 감사 과제:** 아래5개 경로의 허용 여부를 설계하고, 실제 실행은 본인에게 승인된 synthetic 전용 대상에서만 수행합니다.

1. catalog table 이름을 사용한 SELECT.
2. volume의 파일 경로 읽기.
3. 외부 엔진이 catalog API와 발급된 credential로 읽기.
4. UC와 별개로 소유한 cloud IAM credential의 object 직접 읽기.
5. 공유 데이터의 수신자가 자신의 저장소에 사본을 만든 뒤 provider 권한을 철회한 상황.

4번은 UC를 통과하지 않는 경로가 있을 수 있음을 위협 모델로 검토하는 것이지 무단 접근 실습이 아닙니다. 5번의 철회는 이미 전달된 사본을 소급해 없애는 보장이 아닙니다. 공유 프로토콜 명칭·지원 client·token lifespan은 현재 제품 문서를 확인하고, provider와 recipient의 책임을 별도로 적습니다.

**lineage oracle:** source fixture S, transform T, output U를 직접 아는 작은 DAG를 만듭니다. UI lineage와 expected edges를 대조하고 외부 download·Python 내 임의 side effect·지원되지 않는 path가 누락되는지 확인합니다. 보이지 않는 edge가 없다는 증거는 아닙니다. column lineage 역시 instrumented 범위의 관측입니다.

**audit oracle:** 성공 read, 거부 read, job run, grant 변경을 synthetic request ID와 시간으로 원장에 남깁니다. 제품 audit/system table에서 대응 행을 찾되 지연·권한·보존기간과 redaction을 기록합니다. query body나 error에 민감 값이 남는지도 검사합니다. 테이블을 읽을 권한이 없다는 이유로 audit event가 발생하지 않았다고 판단하지 않습니다.

**LLM AI 연결:** train/eval corpus, embedding용 원문, RAG document, 평가 결과에 각각 provenance·version·license·access policy·삭제 전파 계약을 정의합니다. UC tag 또는 lineage가 train/test leakage, 문서 사용권, vector index의 삭제 완료까지 자동 증명하지는 않습니다. snapshot ID와 corpus checksum, downstream index rebuild/삭제 증거가 별도로 필요합니다.

**gate:** 데이터 읽기 권한과 metadata 발견 권한, 복사된 데이터와 live query, audit 부재와 관측 불가를 구분합니다. principal·실제 객체 경로를 포함한 민감한 topology는 공개 보고서에서 정제합니다.
