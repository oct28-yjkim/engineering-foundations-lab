# Qdrant 기능 지도 — 사용하지 않는 기능도 판단할 수 있게

[기본 LAB](labs/README.md) · [수동 고급 기능](labs/advanced.md) · [분산 LAB](labs/cluster.md) · [과정](curriculum.md)

기준은 **1.19.1**입니다. 아래 상태는 저장소의 **제공 방식**이며 실행 성공 인증이 아닙니다. 실제 수행 증거는 [validation](labs/validation.md)에 분리합니다. `P`=runner 코드 제공, `M`=수동 절차, `E`=추가 환경/fixture 필요, `R`=문서·소스 조사 과제. `M/E`는 일부 수동 예제와 더 큰 환경 과제가 공존한다는 뜻입니다.

## 저장·검색 표현

| 기능 / 학습 위치 | 목적·작동/상태 | 관측·제약/반례·채택 판단 | 제공 |
| --- | --- | --- | --- |
| dense·distance·named vectors / [QD01](lessons/01-vectors-contracts.md#qd01) | point에 검색 표현과 이름/차원/거리 계약 부여 | count뿐 아니라 ID·score·vector name 검산. 이름/차원 오류와 낮은 의미 품질은 다름. 모델별 표현 분리가 필요할 때 named 채택 | P: [기본](labs/README.md); 다른 거리 비교 E |
| sparse·IDF / [QD07](lessons/04-query-pipelines.md#qd07) | 비영 값과 index로 어휘적 신호 검색 | dense와 별도 구조/설정. tokenizer·vocabulary가 다르면 같은 index 숫자가 다른 의미. 제공 sparse는 합성 값이며 BM25 학습/추론 아님 | sparse P; IDF/BM25 E/R |
| multivector·MaxSim / [QD08](lessons/04-query-pipelines.md#qd08) | 한 point의 여러 벡터로 late interaction | 후보 수·토큰 수에 따른 비용, 평균 벡터와 다른 순위. 문서 수준 정밀 매칭에 채택, 단순 임베딩에는 불필요할 수 있음 | M: [고급](labs/advanced.md) |
| payload match/range·타입 / [QD02](lessons/01-vectors-contracts.md#qd02) | 벡터 유사도와 별도로 후보 자격 결정 | 숫자와 문자열은 같은 조건 아님. filter 0건을 ANN 장애로 오진하지 않음 | match/타입 P; range E |
| nested·missing/null/empty / [QD02](lessons/01-vectors-contracts.md#qd02) | 배열 내 같은 객체 조건과 값 부재를 구별 | 교차 원소 false positive와 명시 null을 별도 정답으로 작성. SQL NULL 규칙 복사 금지 | nested M; null/empty E |
| payload/vector index·HNSW·exact / [QD05](lessons/03-index-quality.md#qd05) | 필터 선택도와 근사 탐색 비용 제어 | 작은 segment는 exact 경로일 수 있음. index 설정 성공≠HNSW 구축/사용 증명. exact는 검산용이나 큰 요청 비용 있음 | index/exact P; ANN 규모 E |
| optimizer·indexed_only / [QD04](lessons/02-write-state.md#qd04) | segment 구성과 인덱스 생성/정리, 미인덱스 검색 범위 제어 | 검색 가능 수와 인덱스 수를 분리. indexed_only의 누락 가능성과 fresh data 요구를 비교 | 관측 M: [운영](operations.md); backlog E |
| quantization·datatype / [QD06](lessons/03-index-quality.md#qd06) | 표현 비용 절감, 원본 재점수와 절충 | scalar/product/binary/turbo, float32/float16/uint8/turbo4의 지원 문맥을 확인. 압축률만으로 승자 선정 금지 | E/R |
| memory·on-disk / [QD06](lessons/03-index-quality.md#qd06) | vector/graph/payload/quantized 자료의 메모리 배치 선택 | 1.19.1에서 legacy on_disk보다 memory 우선, dense에 pinned 미지원. cold라도 RAM 0이 아니며 cache 영향 측정 | E/R |

## Query API의 기능 표면

| 기능 / 학습 위치 | 목적·작동/상태 | 관측·제약/반례·채택 판단 | 제공 |
| --- | --- | --- | --- |
| prefetch·RRF / [QD07](lessons/04-query-pipelines.md#qd07) | 다른 retrieval의 후보를 순위 기반 결합 | branch별 ID/rank를 먼저 저장. prefetch에 없는 정답을 fusion이 복구할 수 없음 | P |
| DBSF·formula·multi-stage rerank / [QD07–08](lessons/04-query-pipelines.md) | score 분포 결합·명시적 업무 점수·후보 재평가 | top-k 표본/극단값·후보 budget·formula missing input 반례. eval 없이 임의 가중치 도입 금지 | E/R |
| grouping·lookup / [QD08](lessons/04-query-pipelines.md#qd08) | chunk 중복을 줄이고 문서 단위 결과 구성 | group size와 top-k point 수는 다름. 다른 collection lookup은 권한/최신성도 확인 | E/R |
| recommend·discover/context / [QD08](lessons/04-query-pipelines.md#qd08) | positive/negative 사례 또는 선호 관계로 탐색 | 사용자 의도·부정 예시가 없으면 일반 nearest로 충분. 자기 예시 포함/제외·차원·using 조건 검산 | E/R |
| scroll/order_by/facet·배치 / [QD08](lessons/04-query-pipelines.md#qd08) | 순회·payload 정렬/집계·요청 오버헤드 제어 | similarity top-k와 다른 계약. 동시 write 중 일관 snapshot으로 가정하지 않음; index/limit 확인 | E/R |

## 변경·복구·운영 기능

| 기능 / 학습 위치 | 목적·작동/상태 | 관측·제약/반례·채택 판단 | 제공 |
| --- | --- | --- | --- |
| upsert/update/delete·WAL·wait / [QD03](lessons/02-write-state.md#qd03) | ID 기반 변경과 영속/적용 경계 | receipt→retrieve/query 검산. 같은 ID 재전송이 새 business version의 보호를 뜻하지 않음 | CRUD/wait P; crash/WAL E |
| insert_only/update_only·조건부 갱신 / [QD03](lessons/02-write-state.md#qd03) | 생성/갱신 의도와 stale writer 제한 | 1.19 API의 정확한 condition/mode 지원을 읽고 경쟁 반례 설계. SQL transaction과 같다고 주장 금지 | R |
| alias·vector schema migration / [QD10](lessons/05-governance-recovery.md#qd10) | 논리 이름 전환 또는 named vector 추가/삭제 | alias 전환은 벡터 재생성/dual write/모든 client 전환을 대신하지 않음. cutover 전후 ID/모델 계약 확인 | alias M; schema migration E |
| snapshot·restore / [QD10](lessons/05-governance-recovery.md#qd10) | 특정 시점 자료를 별도 대상으로 복구 | 생성 성공≠복원 성공. 버전·scope·checksum·동시 write·업무 ledger 확인 | M; 전체 cluster/DR E |
| strict mode·quotas / [QD09](lessons/05-governance-recovery.md#qd09) | 비싼 요청/증가량 제한 | enabled만으로 모든 제한이 생기지 않음. 인증/tenant 인가 대체 아님. 거부 이유를 보고 index/요청을 교정 | strict M; node quotas E/R |
| API key·TLS·JWT RBAC·tenant / [QD09](lessons/05-governance-recovery.md#qd09) | 주체와 접근 범위 통제 | 기본 localhost LAB는 보안 검증 아님. payload filter는 신뢰하지 않는 client가 빼버릴 수 있음 | E: 별도 보안 환경 |
| shard·replica·ordering·read consistency / [QD11](lessons/06-distributed-operations.md#qd11) | 데이터 분산과 write/read 보장 선택 | Raft metadata와 point 복제 분리. peer 추가≠자동 data 재배치. 강한 옵션도 범위/가용성 비용 있음 | M/E: [cluster](labs/cluster.md) |
| custom sharding·rebalance·resharding / [QD12](lessons/06-distributed-operations.md#qd12) | tenant locality·hot shard·용량 분산 | 수동 shard 이동과 shard 수 변경은 다름. 문서상 managed reshard/자동 rebalance를 self-host 기본 기능으로 약속하지 않음 | custom/transfer E; Cloud reshard R/E |
| metrics·telemetry·slow log / [QD04](lessons/02-write-state.md#qd04) | 실패 원인을 query·index·I/O·node 경계로 좁힘 | counter reset·histogram 분모·label cardinality, client 시간과 서버 시간을 분리 | metrics/collection P/M: [운영](operations.md); telemetry/slow log E/R |
| SDK retry·upgrade / [QD10–12](lessons/06-distributed-operations.md#qd12) | 과부하 제어와 계약 유지 | timeout은 실패 확정 아님. 재시도 budget/동일 ID/업무 revision 검산. downgrade가 복구라고 가정 금지 | E/R |

## 현재 선택하지 않는 제품/환경도 조사

Cloud inference·FastEmbed·GPU indexing·Qdrant Edge는 기본 서버 fixture와 별도입니다. Qdrant가 항상 embedding을 자체 생성하거나 GPU를 필요로 한다고 가정하지 않습니다. 이 항목은 **R**이며 비용·모델/장치·데이터 전송·지원 API 차이를 먼저 조사합니다. 모델 자체의 재현 실험은 [LLM 논문 LAB](../../ai/llm-paper-lab/README.md)과 연결합니다.

고급 기능을 채택하지 않은 보고서도 목적/대안/관측/반례/재검토 조건을 갖춰야 합니다. 단순히 “미사용” 또는 “나중에”로 기입하면 기능 학습 완료가 아닙니다. API 계약은 [고정 OpenAPI](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/docs/redoc/v1.19.x/openapi.json), 배포 차이는 [공식 분산 운영](https://qdrant.tech/documentation/scaling/distributed_deployment/)에서 확인합니다.
