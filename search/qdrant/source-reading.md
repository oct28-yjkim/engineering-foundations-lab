# Qdrant 고정 소스·공식 문서·논문 읽기 지도

[과정](curriculum.md) · [기능 지도](feature-map.md) · [연구 강의](lessons/07-research-capstone.md)

2026-10-04에 [공식 v1.19.1 release](https://github.com/qdrant/qdrant/releases/tag/v1.19.1), 공개 tag/파일 tree, 아래 일부 원문을 읽기 전용으로 확인했습니다. annotated tag 객체는 `de333e3c04660fe475d6275e9efc9fb9f54138fe`, 실제 **peeled commit은 `6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de`**입니다. 아래 링크는 후자를 고정합니다. 소스 경로 확인은 빌드/테스트/서버 실행 증거가 아닙니다.

## API와 기능 버전의 출발점

[고정 v1.19.x OpenAPI](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/docs/redoc/v1.19.x/openapi.json)에서 `QueryRequest`, `SearchParams`, `VectorParams`, `StrictModeConfig`, `WriteOrdering`, `ReadConsistency`를 읽습니다. 최신 웹 예제와 다를 때 서버가 실제 수용하는 schema와 SDK 버전을 함께 기록합니다. SDK의 메서드 존재가 서버 기능 사용 가능성을 증명하지 않습니다.

1.19.1 schema 확인 항목: named vector 생성/삭제 경로, `QueryRequest.prefetch`, exact/quantization/indexed_only, scalar/product/binary/turbo, `memory`와 deprecated `on_disk`, `insert_only/update_only`, read/write 보장 옵션입니다. 이 항목은 **기능 지원 확인**이며 모든 동작을 이 저장소에서 실행했다는 주장이 아닙니다.

## 요청과 자료구조의 연결

| 질문 / 모듈 | 고정 소스 | 읽고 검증할 경계 |
| --- | --- | --- |
| API 문법 / QD01–03 | [points OpenAPI](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/openapi/openapi-points.ytt.yaml) | query/upsert/update 요청과 timeout/wait/options를 별도 분류 |
| payload 선택도 / QD02·05 | [filtering.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/segment/src/index/struct_payload_index/read_view/filtering.rs) | `estimate_field_condition`, `optimized_filter`, `condition_cardinality`; 추정과 실제 일치 집합의 차이 |
| HNSW 실행 경계 / QD05 | [vector_index_impl.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/segment/src/index/hnsw_index/hnsw/vector_index_impl.rs) | `VectorIndexRead`/`VectorIndex` 구현에서 read view로 이어지는 경로; 설정과 실제 search 선택을 구분 |
| HNSW 탐색 / QD05 | [read_view/search.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/segment/src/index/hnsw_index/hnsw/read_view/search.rs) | filter/후보/종료 조건을 논문 가정과 대조; 실제 함수명은 원문에서 기록 |
| 압축 / QD06 | [quantized_vectors/config.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/segment/src/vector_storage/quantized/quantized_vectors/config.rs) | 압축 설정과 원본 datatype/메모리 배치가 다른 계층인지 추적 |
| query 조정 / QD07–08 | [collection/query.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/collection/src/collection/query.rs) | `query`, `query_batch`, `merge_intermediate_results_from_shards`; 단계·shard 결과를 합치는 경계 |
| local query / QD07–08 | [local_shard/query.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/collection/src/shards/local_shard/query.rs) | prefetch 후보→후단 처리와 collection-level 조정의 역할 구분 |
| WAL 관련 상태 / QD03·12 | [wal_ops.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/collection/src/shards/local_shard/wal_ops.rs) | retention·미적용 WAL 처리와 실제 write/flush 경로를 추가로 연결; 이 파일만으로 내구성 결론 금지 |
| replica 변경 / QD11 | [replica_set/update.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/collection/src/shards/replica_set/update.rs) | `update_with_consistency`, `update_local`, `forward_update`; wait·실패 결과 결합·leader 경계 |
| alias / QD10 | [alias_mapping.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/storage/src/content_manager/alias_mapping.rs) | `AliasMapping`의 get/insert/remove/save와 상위 transaction 처리 연결 |
| snapshot / QD10 | [collection/snapshots.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/collection/src/collection/snapshots.rs) | collection/local shard 범위와 restore 시점/버전/우선순위의 경계 |
| node 설정 / QD04·09 | [config.yaml](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/config/config.yaml) | API collection 설정과 process/node 설정을 분리하고 적용 시점 확인 |

최소 제출: `입력 / 예상 상태 / 함수 5개 / 자료구조 2개 / 실패 분기 / 실제 관측 / 반례 / 미검증`입니다. 함수 하나를 읽고 모든 배포의 내구성·quorum·권한을 단정하지 않습니다.

## 테스트에서 반례 찾기

다음 경로의 존재를 확인했습니다. 테스트가 읽는 환경 변수·서버 endpoint·fixture 생성/삭제·Rust feature·toolchain을 검토하기 전에는 실행하지 않습니다. 현재 저장소의 mock 테스트와 upstream integration test는 다른 증거입니다.

| 고정 테스트 | 연구 질문 |
| --- | --- |
| [nested_filtering_test.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/segment/tests/integration/nested_filtering_test.rs) | 배열의 다른 원소를 섞은 거짓 일치를 어느 assertion이 잡는가? |
| [hnsw_quantized_search_test.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/segment/tests/integration/hnsw_quantized_search_test.rs) | corpus·거리·품질 허용치가 실무 workload와 어떻게 다른가? |
| [test_query.py](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/tests/openapi/test_query.py) | branch별 후보와 최종 ranking을 독립적으로 검사하는가? |
| [test_strictmode.py](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/tests/openapi/test_strictmode.py) | 어떤 요청이 어떤 제한 때문에 거부되는가? |
| [snapshot_tests.rs](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/collection/src/shards/local_shard/snapshot_tests.rs) | `test_snapshot_all`, `test_snapshot_includes_segment_manifest`의 snapshot 범위는 무엇인가? |
| [test_memory_placement.py](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/tests/openapi/test_memory_placement.py) | 요청 수용·거부와 실제 OS 메모리 성능 측정은 어떻게 다른가? |

## 선택 논문 — 논문 결과와 제품 기능을 구별

| 1차 자료 | 최소 실험 질문 | 경계 |
| --- | --- | --- |
| Malkov & Yashunin, [HNSW](https://arxiv.org/abs/1603.09320) | 같은 exact 정답에서 탐색 폭·recall·지연을 비교하고 필터가 추가되면 어떤 가정이 바뀌는가? | 논문 graph와 Qdrant의 payload/segment/분산 구현을 동일시하지 않음 |
| Cormack et al., [Reciprocal Rank Fusion](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) | 작은 두 rank list의 결합과 후보 누락을 손계산, 서버 결과와 tie 비교 | 논문 상수·rank 기준을 서버 기본값에 무검증 대입하지 않음 |
| Khattab & Zaharia, [ColBERT](https://arxiv.org/abs/2004.12832) | 평균 vector와 late interaction의 순위 차이·토큰 수 비용을 비교 | 합성 MaxSim API 실습은 모델 학습이나 논문 benchmark 재현이 아님 |

모델/코퍼스 다운로드·GPU/API 확장은 별도 선택입니다. Qdrant 운영 LAB의 필수 조건이 아니며 벡터 DB의 지표/장애 학습을 CPU 모델 계산으로 대체하지 않습니다. 실제 서비스 채택은 논문 headline 수치 대신 자기 query slice·권한·삭제·복구 요구를 근거로 결정합니다.
