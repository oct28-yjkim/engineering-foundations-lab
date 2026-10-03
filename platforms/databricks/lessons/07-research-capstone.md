# 07. 연구와 미니 캡스톤: 주장 하나를 끝까지 추적한다

[커리큘럼](../curriculum.md) · [소스·논문 지도](../source-reading.md) · [평가](../assessment.md)

<a id="d13"></a>
## D13 — 논문·공개 코드·관측으로 아는 범위를 구분한다

Delta·Photon·Lakehouse를 읽는 목표는 유명 시스템의 이름을 기억하는 일이 아니라 논문이 필요한 가정을 찾아 현재 workload에서 시험하는 것입니다. 논문 출판 시점의 object store consistency·runtime·hardware·benchmark 규모와 현재 환경을 분리합니다. 현재 cloud store가 과거와 동일한 consistency 조건이라고 인용하지 않습니다.

**필수 연구 패킷:** [소스 지도](../source-reading.md)의 세 논문에서 각1개 가설을 작성한 뒤 하나를 골라 구현합니다.

| 논문 | 작은 가설 과제 | 반증/비교 기준 |
| --- | --- | --- |
| Delta Lake, PVLDB2020 | committed snapshot만 읽으면 물리 orphan file은 결과에 포함되지 않아야 한다 | action 모델과 실제 Delta engine을 분리하고 version별 PK를 비교 |
| Lakehouse, CIDR2021 | 같은 canonical snapshot을 공유하면 중복 ETL 관리 부담을 줄일 수 있다 | freshness/format 호환/격리/egress의 반대 비용을 함께 모델링 |
| Photon, SIGMOD2022 | vectorization이 유리한 workload와 그렇지 않은 workload가 다르다 | managed native/fallback profile 또는 CPU toy loop 비교; 후자는 Photon 재현 아님 |

논문 benchmark를 재현하려면 dataset scale·query set·hardware·cache·runtime·가격 기준까지 맞아야 합니다. 작은 fixture는 원리 재현이고 원논문 성능 재현이 아닙니다. managed Photon 소스 코드는 이 저장소에서 제공하지 않으며 비공개 구현을 읽었다고 주장하지 않습니다.

**source 과제:** 고정 Delta commit에서 구현4개 이상과 테스트3개를 연결합니다. entry point→snapshot→read/write set→conflict→commit→reader visibility의 call chain을 작성하고 예외 하나의 경로를 추적합니다. 문서에 쓰인 조건, 코드가 확인한 조건, 자신이 테스트한 조건을 각각 표시합니다. 실제 DBR 내부와 동일 코드라고 가정하지 않습니다.

**최소 재현:** 원인 후보 하나만 남기도록 입력·concurrency·feature set을 줄입니다. 예: 같은 source key 중복과 writer conflict를 동시에 넣지 말고 분리합니다. failed assertion은 expected와 actual을 모두 남깁니다. 수정 proposal은 회귀 테스트와 기존 semantics 호환 위험을 포함합니다. upstream issue/PR 발행은 별도 판단·승인 단계이며 과제 제출이 자동 발행을 의미하지 않습니다.

**gate:** 고정 ref·source 위치·실행 fingerprint·independent oracle·반례·한계가 하나의 패킷 안에 있어야 합니다. upstream test가 skip되거나0개 실행됐는데 PASS라 쓰면 실패입니다.

<a id="d14"></a>
## D14 — 2주 한정 orders lakehouse slice

새 플랫폼을 재구축하지 않습니다. 앞 모듈의 fixture·harness·정책 설계를 재사용해 **단일 orders current-state projection**만 완성합니다. ML training, vector search, 모든 cloud의 DR, 다수 SaaS connector, 대규모 production ingestion은 범위 밖입니다.

### 1주차: 계약과 정상 경로

1. 입력에 entity_id, event_id, sequence, operation, integer amount, tenant_id, synthetic provenance를 둡니다. 동일 sequence 상충 입력·NULL key·음수 금액 처리와 replay horizon을 문서화합니다.
2. source canonicalization→latest-state projection→tenant별 합계를 구성합니다. 승인된 환경의 [Delta SQL](../labs/delta-contract.sql) 또는 정제된 실제 실행 증거에서 시작하고, CPU merge 모형은 필요할 때만 원리 보충으로 사용합니다. 서로 다른 fixture의 oracle를 혼합하지 않습니다.
3. independent Python/수기 oracle와 실제 chosen runtime 결과의 PK/value/tombstone을 비교합니다. managed 계정이 없으면 local/model 구현만 완료로 표시하고 UC 권한은 matrix 설계로 둡니다.
4. 배포 artifact·지문·리소스 상한·secret 무노출 규칙을 기록합니다. 자동 계정 생성이나 유료 compute 실행은 포함하지 않습니다.

### 2주차: 두 실패와 새 대상 복구

- **실패 A: 응답 유실 뒤 같은 batch 재시도.** 업무 state는 같고 accepted/stale/duplicate 분류 원장은 설명 가능해야 합니다. 실제 managed driver 강제 종료 대신 local harness의 commit/ack 경계 모델로 수행했다면 그 범위를 명시합니다.
- **실패 B: DELETE 뒤 오래된 UPSERT 도착.** tombstone 또는 동등한 version ledger로 부활을 방지하고 ledger retention 만료 시의 보장 한계를 씁니다.
- **복구:** 새 학습용 대상으로 source·결과·계약을 복원하여 checksum·key/value·권한 기대를 다시 검증합니다. 모델 파일 복원을 managed UC/Delta DR로 표현하지 않습니다.
- **보안 선택 실행:** 승인된 managed 환경이 있으면 D05의 실제 별도 principal로 positive/negative read/write tests를 수행합니다. 없으면 미실행이며 해당 gate는 추후 확인 대상입니다.

### 제출물과 완료 범위

짧은 README, 실행 명령, 입력/seed, exact oracle, raw 결과, 실패 time line, source trace, 복구 report, 비용/보안 제한을 냅니다. 문서에는 CPU-MODEL, LOCAL-SPARK, LOCAL-DELTA, MANAGED-OPTIONAL, DESIGN별 실행 상태를 분리합니다. 공통 점수는 정확성25·원리/소스25·실험/반증25·운영/재현성25이며 총80 이상·각15 이상, 선택한 실행 범위의 필수 gate가 모두 필요합니다. 관리형 미실행을 숨긴 전체 플랫폼 수료 주장은 허용하지 않습니다.

더 큰 설계는 [거버넌스 Lakehouse 캡스톤](../../../capstones/governed-lakehouse.md)의 후속8주에 별도로 연결합니다. 기존 [공통 데이터 캡스톤](../../../databases/shared/capstone.md)은 CDC·serving 중심의 다른 선택 경로입니다. PostgreSQL CDC→Kafka→Spark/Delta→ClickHouse로 확장한다면 source transaction, Kafka offset, Delta commit, serving projection의 각 정답과 재처리 경계를 새로 검증해야 합니다. LLM 학습 corpus로 확장할 때도 snapshot·license·train/eval leakage·삭제 전파를 추가하고 D14의2주 안에 자동 포함하지 않습니다.
