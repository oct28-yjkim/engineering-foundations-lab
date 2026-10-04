# Qdrant — 28주·14모듈 심화 커리큘럼

[기본 LAB](labs/README.md) → [기능 지도](feature-map.md) → 필요한 강의 → [운영·복구](operations.md) 순서로 시작합니다. 28주 이수를 기본 LAB의 선수 조건으로 두지 않습니다. 목표는 API 이름을 아는 것이 아니라 **왜 이 기능이 필요한가, 무엇이 바뀌는가, 어떻게 관측하는가, 언제 쓰지 않는가**를 증명하는 것입니다.

기준은 Qdrant **1.19.1**, commit `6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de`입니다. 서버/클라이언트/이미지 digest를 각각 기록합니다. 현재 온라인 문서가 고정 서버보다 앞설 수 있으므로 [고정 API·소스 지도](source-reading.md)를 함께 확인합니다.

## 모듈 지도

14모듈 × 2주 × 주 12시간 = 약 336시간입니다. 모듈당 원리·자료 6시간, 실험 10시간, 소스 4시간, 분석·구술 4시간을 배정합니다. 실험 시간은 정상 관측 2시간 → 반례·사건 5시간 → 조치·회복 검산 3시간이 기본입니다. 별도 부하/cluster/보안 환경 준비는 추가입니다.

| 모듈 / 주 | 선수 조건 | 핵심 질문 | 제출·최소 통과 |
| --- | --- | --- | --- |
| QD01 / 1–2 | HTTP·배열·내적 | [point·vector·거리 계약](lessons/01-vectors-contracts.md#qd01) | dense/name/dimension/distance별 수작업 정답과 오류 거부 |
| QD02 / 3–4 | QD01, 집합 | [payload·filter·nested](lessons/01-vectors-contracts.md#qd02) | 타입·missing/null·배열 교차 일치와 nested 반례 |
| QD03 / 5–6 | QD01–02, I/O | [CRUD·WAL·ACK·재전송](lessons/02-write-state.md#qd03) | point ID/업무 revision/operation 결과/재조회 원장 |
| QD04 / 7–8 | QD03, 상태 전이 | [segment·optimizer·관측](lessons/02-write-state.md#qd04) | 검색 가능·인덱스 완료·내구성의 독립 판정 |
| QD05 / 9–10 | QD02·04, 그래프 | [exact·HNSW·filter 계획](lessons/03-index-quality.md#qd05) | 동일 corpus/filter exact oracle과 ANN recall 경계 |
| QD06 / 11–12 | QD05, 통계 | [quantization·memory](lessons/03-index-quality.md#qd06) | 품질/지연/메모리 frontier와 cold/warm 반례 |
| QD07 / 13–14 | QD01·05 | [named·sparse·hybrid](lessons/04-query-pipelines.md#qd07) | 후보 누락과 RRF/DBSF 결합 효과 분리 |
| QD08 / 15–16 | QD07 | [multivector·rerank·탐색](lessons/04-query-pipelines.md#qd08) | MaxSim·group·recommend/discover의 목적·비채택 근거 |
| QD09 / 17–18 | QD03–06 | [strict mode·보안·tenant](lessons/05-governance-recovery.md#qd09) | 비용 제약과 권한 경계, 허용/거부 양성·음성 대조군 |
| QD10 / 19–20 | QD03·09 | [alias·snapshot·upgrade](lessons/05-governance-recovery.md#qd10) | 독립 복원·cutover·잔존 write·version 호환 검산 |
| QD11 / 21–22 | QD03–04, 분산 기초 | [shard·replica·consistency](lessons/06-distributed-operations.md#qd11) | metadata quorum과 데이터 복제/ACK의 분리 |
| QD12 / 23–24 | QD05·10–11 | [확장·장애·client 제어](lessons/06-distributed-operations.md#qd12) | hot shard·대기·오류의 경쟁 가설과 제한된 복구 |
| QD13 / 25–26 | QD01–12, Rust 기초 | [고정 소스·논문 반증](lessons/07-research-capstone.md#qd13) | 5symbol·2자료구조·1실패 분기·실제 API와 연결 |
| QD14 / 27–28 | QD13 | [작은 변경 연구](lessons/07-research-capstone.md#qd14) | 한 경로·한 변경·두 사건·독립 oracle·한계 보고 |

## 범위와 학습 상태

기본 runner는 작은 합성 데이터로 schema·정확한 query·CRUD·오류 진단을 학습합니다. 대량 데이터, HNSW recall/부하, 복제 장애, TLS/권한 검증을 자동 완료하지 않습니다. 기능별 제공 상태는 [기능 지도](feature-map.md)가 기준이며 실제 수행 여부는 [검증 기록](labs/validation.md)만 근거로 삼습니다.

- `PROVIDED`: 실행 코드가 제공됨. 서버 실측 PASS라는 뜻은 아닙니다.
- `MANUAL`: 요청·관측·회복 절차를 제공하며 학습자가 수행합니다.
- `SEPARATE`: 규모·인증·다중 프로세스 또는 유료 환경을 별도로 준비합니다.
- `RESEARCH`: 고정 문서/소스와 검증할 질문을 제공하며 실행 결과는 없습니다.

모든 기능은 채택하지 않더라도 목적 → 입력/상태 전이 → 관측값 → 제약/실패 반례 → 채택·비채택 판단을 작성합니다. “현재 회사에서 안 쓴다”는 이유로 학습 지도를 비우지 않습니다. 미실행 기능을 구현 지원 없음이라고 표시하지도 않습니다.

## 재현 계약

```text
run_id / source commit / server+client versions / image digest / platform
collection+vector names / dimension+distance / model+tokenizer revision
point IDs+business revision / payload types / filter+principal / expected IDs
query+prefetch limits / exact oracle / score tolerance / tie rule / actual ranks
wait+ordering+read consistency / write receipt / visibility / replay ledger
index+optimizer state / memory placement / quantization / cold-warm / sample count
latency interval+units / errors+timeouts / snapshot target / recovery gates / not tested
```

합성 벡터 정답은 같은 거리·필터의 exhaustive 결과이며 사람의 relevance와 다릅니다. ANN recall, tenant 누출, 삭제 최신성, 순위 품질, 서비스 가용성을 별도 축으로 평가합니다. 높은 recall이 잘못된 tenant 반환을 상쇄할 수 없습니다. score tie는 허용 ID 집합 또는 명시한 정렬 규칙으로 처리합니다.

## Gate

- G1 QD01–04: 정상 CRUD/query와 최소 두 오류/복구를 실제 서버에서 확인합니다. 단위 테스트만 있으면 서버 운영 미완료입니다.
- G2 QD05–08: exact/ANN/relevance와 후보/재순위 단계를 구별합니다. 작은 fixture에서 HNSW가 쓰였다고 추정하지 않습니다.
- G3 QD09–12: strict mode·filter·인증을 구별하고 독립 복원/복제 장애를 실행한 범위만 인정합니다.
- G4 QD13–14: 소스 가설을 재현 가능한 반례와 연결하고 실패·미확인·재현 불가도 보고합니다.

[평가표](assessment.md)의 총 80점 이상·모든 영역 15/25 이상·선언한 범위의 필수 gate를 함께 충족합니다. 단일 노드, 분산, 보안, 대규모 ANN, Cloud 기능은 별도 완료 상태입니다.
