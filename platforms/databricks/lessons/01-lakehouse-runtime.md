# 01. Lakehouse와 실행 환경: 같은 SQL, 다른 책임 경계

[커리큘럼](../curriculum.md) · [실습 환경](../labs/README.md)

<a id="d01"></a>
## D01 — 플랫폼을 요청·상태·identity로 분해한다

Lakehouse는 Parquet 파일에 이름을 붙이는 것만으로 완성되지 않습니다. 파일 배치와 table snapshot, catalog metadata와 권한 집행, compute scheduling과 query execution, object-store credential과 사용자의 업무 권한을 구분해야 합니다. Databricks 관리형 서비스가 제공하는 기능과 공개 Spark/Delta가 제공하는 기능을 한 상자에 넣으면 사고 원인과 비용 책임을 설명할 수 없습니다.

첫 실험은 실행이 아니라 **요청 경로 모델**입니다. 다음6개에 대해 호출자→인증→권한 검사→실행→영속 상태→응답의 순서를 적습니다.

| 경로 | 반드시 분리할 identity와 state |
| --- | --- |
| notebook의 SELECT | 로그인 사용자, compute/access mode, catalog 권한, query snapshot |
| 예약된 job의 write | deployer, job run identity, source/target privileges, commit version |
| SQL warehouse의 BI query | client credential, warehouse permission, table permission, result cache |
| object store 수집 | storage credential, external location/volume, file discovery/checkpoint |
| 외부 엔진의 table 접근 | catalog API identity, 임시 credential, 실제 object 권한, protocol 지원 |
| 공유 데이터 수신 | provider/recipient identity, 공유 권한, 수신자가 이미 복사한 데이터 |

**반례 과제:** UC SELECT를 철회했으나 사용자가 별도 cloud IAM으로 같은 object bytes를 읽을 수 있는 가상 구성을 그립니다. 어느 요청이 UC를 거치지 않았는지 표시합니다. 이 과제는 우회 시도를 운영 bucket에 실행하는 지시가 아닙니다. 관리형 서비스 밖의 credential까지 통제하지 않으면 catalog 규칙만으로 모든 접근을 설명할 수 없다는 위협 모델입니다.

control plane·classic compute plane·serverless compute의 network와 소유 계정은 cloud/상품에 따라 다릅니다. workspace에 연결할 수 있다는 사실과 workload가 egress할 수 있다는 사실도 다릅니다. [AWS 참조 아키텍처](https://docs.databricks.com/aws/en/lakehouse-architecture/reference)를 출발점으로 cloud/region과 실제 구성으로 경계를 다시 작성합니다. Azure/GCP의 IAM 이름이나 endpoint를 AWS 도표로 대체하지 않습니다.

**gate:** 각 경로의 상태 저장 위치, 장애 책임자, secret 소유자, 허용/거부 기대를 모두 적습니다. 확인할 수 없는 managed 내부 topology는 unknown으로 남깁니다. 그림의 빈칸을 추측으로 채우면 통과하지 않습니다.

<a id="d02"></a>
## D02 — runtime 지문과 실행 semantics

OSS Spark, Databricks Runtime(DBR), SQL warehouse, serverless environment는 동의어가 아닙니다. DBR에는 특정 Spark 기반과 별도 최적화/라이브러리가 포함될 수 있으며, 공개 Spark patch 번호만으로 managed 기능을 재현할 수 없습니다. 로컬 Python process가 성공했다고 remote access mode나 UC enforcement가 검증된 것도 아닙니다.

실행 전 다음 지문을 한 장에 남깁니다.

- 로컬: OS/architecture, Python·Java·Spark·Delta package, lockfile, master, memory, timezone, ANSI 설정.
- managed 선택: cloud/region, DBR 또는 serverless environment/channel, compute type·access mode, Photon enablement, UC 상태, run identity, autoscale/cache 조건.
- 비교 불가 항목: 비공개 engine build·내부 SHA는 unknown. local version을 managed 값으로 복사하지 않습니다.

**LOCAL-SPARK 과제:** [Spark 실습](../../../data-processing/spark/labs/README.md)에서 다음과 같은 synthetic 데이터의 의미를 고정합니다. 정확한 실행 명령과 baseline은 그 실습 문서를 따릅니다.

| 입력 | 계약 |
| --- | --- |
| nullable key와 duplicate key | NULL join/aggregate 의미와 business dedup 규칙을 별개로 정의 |
| 금액 0.1·0.2 또는 소수 문자열 | financial 합계는 decimal scale 또는 integer minor unit으로 oracle 작성 |
| timezone이 있는 timestamp | UTC instant와 날짜 bucket의 기준 timezone을 구분 |
| 잘못된 cast 문자열 | ANSI 설정에 따른 실패/NULL 기대를 사전에 작성 |

같은 입력의 expected PK/value를 Python 표준 라이브러리 또는 수기로 계산하고 SQL 결과를 정렬해 대조합니다. floating point를 비교한다면 absolute/relative tolerance와 NaN 처리를 명시합니다. 이후에만 `EXPLAIN`의 logical/physical plan과 실제 task metrics를 비교합니다. plan의 operator 이름이 같다는 이유로 workload 의미가 같다고 결론짓지 않습니다.

**MANAGED-OPTIONAL 과제:** 동일한 fixture와 SQL을 별도 승인된 workspace에서 실행합니다. SQL warehouse/compute 간 차이를 관찰하되 계정에 없는 환경을 억지로 생성하지 않습니다. notebook cell wall time, queue/startup, execution time, result download를 분리합니다. [Photon 문서](https://docs.databricks.com/aws/en/compute/photon)는 Catalyst와 native 실행계층의 경계를 설명합니다. Photon이 켜져 있어도 지원되지 않는 구간의 fallback을 profile에서 확인해야 하며, 로컬 Spark는 Photon이 아닙니다.

**반증:** 정답이 다르면 속도 비교를 중단하고 timezone·cast·decimal·API·runtime 차이를 줄여 최소 재현합니다. UI screenshot만 제출하지 말고 정제한 query/입력/설정/expected/actual을 함께 냅니다. 관리형 실행이 없으면 이 부분은 DESIGN이며 local gate와 별도로 표시합니다.
