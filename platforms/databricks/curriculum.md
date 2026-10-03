# Databricks Zero to Hero: 관리형 플랫폼의 경계까지 검증하는 28주

[시작](README.md) · [실습](labs/README.md) · [소스·논문](source-reading.md) · [평가](assessment.md)

모듈당24시간은 원리·문서6, 실험10, 소스/논문4, 증거·리뷰4시간을 기본으로 합니다. 주차는 예산이고 통과 보장이 아닙니다. managed 계정이 없는 학습자는 로컬 증거와 설계 증거를 제출할 수 있지만 실제 UC·Photon·Auto Loader·배포 검증 상태를 별도로 남깁니다.

| 모듈·주차 | 선행 | 내부 원리와 실험 질문 | 필수 증거·gate |
| --- | --- | --- | --- |
| D01 · 1–2 | SQL/Python/OS | [01강](lessons/01-lakehouse-runtime.md#d01): control/data plane, object store와 catalog, 책임 경계 | 6개 요청 경로의 identity·state·실패 영역; cloud별 미확인 칸 공개 |
| D02 · 3–4 | D01, Spark plan | DBR/classic/serverless/SQL warehouse/Photon, driver/executor | 로컬·managed fingerprint 분리; 동일 SQL의 semantics oracle와 plan 비교 |
| D03 · 5–6 | D02, MVCC | [02강](lessons/02-delta-transactions.md#d03): log action, snapshot, OCC, commit visibility | 2writer history와 read/write set, committed version별 PK·값 oracle; conflict/retry 구분 |
| D04 · 7–8 | D03 | MERGE·schema/protocol·CDF·retention·time travel | 중복/역순 update 재적용 불변식; 지원 reader matrix; 파괴 없는 retention 실패 모델 |
| D05 · 9–10 | D01/03 | [03강](lessons/03-unity-catalog.md#d05): principal·USE·SELECT/MODIFY·소유권·run identity | 2tenant×3principal의 allow/deny matrix, 별도 실제 identity 테스트 |
| D06 · 11–12 | D05, IAM 기초 | managed/external asset, credential/location, lineage/audit/sharing | object direct access 우회 위협; 메타데이터 노출/수신자 copy/철회 범위 명시 |
| D07 · 13–14 | D04, Spark stream | [04강](lessons/04-ingestion-streaming.md#d07): Auto Loader 발견·schema·checkpoint | 같은 event가 두 파일에 있을 때의 반례; source file 원장과 business ID 원장 대조 |
| D08 · 15–16 | D07 | 선언형 graph, materialized view/streaming table, quality/CDC | retry·late event·malformed input의 독립 oracle; checkpoint 호환 범위 및 full refresh 위험 |
| D09 · 17–18 | D02/04, shuffle | [05강](lessons/05-performance-cost.md#d09): Photon fallback, AQE, stats/data skipping·layout | 정답 동일·20반복·실행계획/scan bytes; cold/warm와 compute 조건 분리 |
| D10 · 19–20 | D09 | DBU·infra·storage/network·billing correction·cost allocation | synthetic 비용 원장의 수정/유효기간 join 검증; 실청구서와 추정치 구분 |
| D11 · 21–22 | D05/08 | [06강](lessons/06-delivery-recovery.md#d11): Lakeflow Jobs·Bundles·CI·run_as | validate/plan/deploy/run 증거 분리; 대상 workspace·identity·변경 범위 확인 |
| D12 · 23–24 | D03–11 | data/log/catalog/identity/code/checkpoint 복구, RPO/RTO | 새 대상 restore 계획과 실제 수행 범위; 정답·권한·source 재처리 gate |
| D13 · 25–26 | D03/09/12 | [07강](lessons/07-research-capstone.md#d13): Delta/Photon/Lakehouse 논문과 공개 source | 고정 commit call chain·테스트3개·재현1개·주장 반증1개 |
| D14 · 27–28 | D04/05/08/12/13 | 2주 한정 orders 변환·재시도·권한 설계 | 두 실패 주입·독립 oracle·새 대상 복원; 관리형 미실행 항목 명확 분리 |

## 모든 모듈의 실험 형식

가설·버전·입력 seed·동일성 기준·바꾸는 변수1개·기대 결과·실제 결과·반례·후속 질문을 기록합니다. row count 하나로 정답을 판정하지 말고 PK별 값, 중복 ID, 거부되어야 할 identity, 금액 합계, 허용 오차와 정렬 규칙을 대조합니다. 재시도 성공 로그와 business mutation 1회는 같은 지표가 아닙니다.

원본 workload·plan·metrics·비용 원장은 최소한으로 정제해 보관합니다. object URI, SQL literal, principal 이름, workspace URL 등도 조직에 따라 민감할 수 있습니다. credential 원문과 실제 개인정보는 넣지 않습니다. 자세한 원칙은 [공통 실험 방법](../../databases/shared/experiment-method.md)을 따릅니다.

## 교차 트랙과 범위

Spark는 엔진 원리, Databricks는 그 엔진 위의 저장·권한·운영 계약에 집중합니다. [Kafka](../../streaming/kafka/README.md)는 replay/offset 경계, [PostgreSQL](../../databases/postgresql/README.md)은 OLTP transaction/CDC source, [ClickHouse](../../databases/clickhouse/README.md)는 serving 분석 경계와 비교합니다. [LLM 논문 실험실](../../ai/llm-paper-lab/README.md)의 학습/평가용 데이터 준비에 적용할 때는 데이터 snapshot·삭제 요청 전파·train/eval leakage를 추가합니다. 모든 트랙 전체 수료가 선행 조건은 아닙니다.

D14는 이전 실험을 재사용한 **2주 미니 캡스톤**입니다. 새로운 managed cloud 기반 전체 플랫폼, multi-region HA, 실서비스 모델 학습, 운영 트래픽 전환을 포함하지 않습니다. 더 큰 통합은 [거버넌스 Lakehouse 캡스톤](../../capstones/governed-lakehouse.md)의 후속8주 범위로 별도 설계합니다. 기존 [공통 데이터 캡스톤](../../databases/shared/capstone.md)은 CDC·분석 serving 중심의 다른 선택 경로입니다.
