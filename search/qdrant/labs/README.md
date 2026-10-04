# Qdrant 기본 기능과 진단 LAB

[환경](../environment.md) · [운영 신호](../operations.md) · [기능 지도](../feature-map.md) · [검증 기록](validation.md)

기본 흐름은 **정상 입력과 정답→원리→관측→제약→오류 재현→같은 정답으로 복구 검증**입니다. 로컬 Qdrant 서버를 실제로 사용하며 별도 embedding 모델·GPU·SDK local mode가 필요 없습니다. [fixture.json](fixture.json)은 독립 검산용이고 runner에는 같은 합성 데이터가 고정되어 있습니다. 파일을 편집해 임의 고객 데이터를 업로드하는 기능은 없습니다.

## 1. 입력과 결과를 먼저 예측하기

point ID는 1–6, dense named vector는 `dense`(4차원 Cosine), sparse named vector는 `lexical`입니다. dense 입력은 모두 길이 1인 벡터입니다. `tenant`, `doc`, `rating`은 합성 payload이며 실제 tenant 권한을 나타내지 않습니다.

| ID | dense 첫 두 값 | lexical 차원 0의 값 | tenant | rating |
| --- | --- | --- | --- | --- |
| 1 | 1, 0 | 4 | alpha | 5 |
| 2 | 0.8, 0.6 | 6 | alpha | 4 |
| 3 | 0.6, 0.8 | 3 | beta | 3 |
| 4 | 0, 1 | 5 | alpha | 2 |
| 5 | -0.6, 0.8 | 2 | beta | 1 |
| 6 | -1, 0 | 1 | beta | 0 |

dense 나머지 두 값은 0입니다. query `[1,0,0,0]`의 기대 순서는 **1,2,3,4,5,6**, 점수 **1,.8,.6,0,-.6,-1**입니다. alpha filter는 **1,2,4**, sparse query `{indices:[0],values:[1]}`는 **2,4,1,3,5,6** 순서입니다. sparse가 임의 정수 가중치인 이 실험을 BM25·SPLADE 모델 품질 평가로 부르지 않습니다.

## 2. 무송신 계획과 실제 실행

저장소 루트에서 먼저 준비 범위를 출력합니다. `--plan`이 기본이며 서버 호출·파일 읽기·키 접근을 하지 않습니다.

```text
python -B search/qdrant/labs/qdrant_lab.py --plan --scenario all
```

[환경](../environment.md)대로 **전용 단일 노드**를 시작하고 `/`의 1.19.1과 `/readyz`를 확인한 후 실제 실행을 선택합니다.

```text
python -B search/qdrant/labs/qdrant_lab.py --run --base-url http://127.0.0.1:16333 --scenario basics
python -B search/qdrant/labs/qdrant_lab.py --run --base-url http://127.0.0.1:16333 --scenario features
python -B search/qdrant/labs/qdrant_lab.py --run --base-url http://127.0.0.1:16333 --scenario incidents
```

처음에는 하나씩 실행합니다. 한 번에 모두 실행하려면 마지막 인자를 `all`로 선택합니다. 각 실행은 **독립적인 새 collection**을 생성하므로 위 세 명령을 하나의 collection의 연속 단계로 해석하지 않습니다. features/incidents도 정상 baseline부터 검증합니다.

| scenario | 실제 요청과 회복 oracle |
| --- | --- |
| basics | fresh collection 생성, `wait=true` upsert, retrieve·exact count=6, dense/tenant-filter ID·점수 비교 |
| features | payload index(keyword/integer) 생성 전후 결과 동일, sparse·RRF 검산, 같은 ID payload 갱신·원복, point 2 삭제(count5)→재삽입(count6) |
| incidents | 3차원 잘못된 벡터 400·ID7 부재→4차원 복구(count7)→임시 point 제거(count6); 문자열 rating 필터 0건→정수 5 필터 ID1; 잘못된 vector 이름400→정상 검색 |
| all | 위 전체와 최종 원래 6개의 payload/vector·exact 결과 검증, collection/metrics 관측 |

RRF는 dense/sparse 각각 top 3만 후보로 사용합니다. 고정 버전 기본 `k=2`와 0-based rank로 `Σ 1/(rank+2)`를 검산하면 **ID 2,1,4,3**, 점수 **5/6,3/4,1/3,1/4**입니다. source의 기본값은 [고정 RRF 구현](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/segment/src/common/reciprocal_rank_fusion.rs)을 확인합니다. 다른 제품의 RRF 상수를 가져오지 않습니다. 후보에 없는 5,6을 fusion이 복원하지 못하는 것도 제약입니다.

## 3. 관측과 완료 판단

출력의 `RUN_START`에 생성 예정 이름이 있습니다. `stage/expected/observed`와 score tolerance `1e-5`를 기록합니다. `STOPPED`면 다음 단계로 진행하지 말고 code·생성 시도/확정 여부를 확인합니다. timeout 후 collection이 남을 수 있으며 실패 출력은 rollback 증거가 아닙니다.

현재 runner의 400 출력은 서버 원문을 공개하지 않습니다. 원인 진단은 이 합성 환경의 동일 실행 시각·API 경로·요청 계약과 [운영 관측](../operations.md)을 대조합니다. 사용자 데이터를 담을 수 있는 원문 logs/telemetry를 공용 artifact로 올리지 않습니다.

정상 최종 결과는 `LOCAL_ENGINE_PASS`, exact count=6, 모든 원래 ID/payload/vector와 dense 순위 복구입니다. `points_count`·`indexed_vectors_count` 등 collection info는 정확한 count API와 동일 지표로 취급하지 않습니다. metric 누락은 0이 아닙니다.

## 4. 실행 상한과 남는 것

- 대상은 정확히 `http://127.0.0.1:16333`만 허용합니다. 원격 URL·proxy·redirect·API key·기존 collection 이름을 받지 않습니다.
- 최대 64요청, 요청 body 32KiB, 응답 2MiB, socket timeout 최대 10초, 요청 시작 시 실행 경과 180초 제한입니다. 네트워크 전체의 강제 취소 시한과는 다릅니다.
- 처음 6 points, dimension 사건 복구 중 최대 7 points입니다. collection은 종료 시 **보존**하며 collection 자동 삭제·정리·실패 재시도가 없습니다.
- scalar vectors가 아주 적어 HNSW가 실제 사용됐는지 보장하지 않습니다. `exact=true`의 정답 확인이 ANN recall·성능 시험을 대체하지 않습니다.
- 같은 ID upsert는 이 동일 입력의 count를 늘리지 않지만 out-of-order 업무 update·재시도 부작용 전체를 해결하지 않습니다.
- 단일 노드 `wait=true` 성공을 다중 replica quorum·backup·권한 검증으로 확대하지 않습니다.

## 5. 기능과 운영으로 확장

[수동 고급 LAB](advanced.md)은 nested filter·MaxSim multivector·strict mode·alias 원복·snapshot clone 복구를 제공합니다. [3노드 LAB](cluster.md)은 독립 Compose에서 metadata/replica 관측과 한 노드 이탈을 다룹니다. HNSW/quantization 대규모 품질·성능, security·custom sharding 등은 [기능 지도](../feature-map.md)의 별도 범위를 확인합니다.

기본 완료는 정상 동작 설명·직접 관측·제약과 서로 다른 문제 두 개의 진단/회복 증거입니다. runner 결과만 복사하지 않고 [사건 보고서](../../../operations/incident-report-template.md)에 원인 후보·판정 근거·조치 전후·추가 미검증을 기록합니다.

## 네트워크 없는 코드 검사

```text
python -B -m unittest discover -s search/qdrant/labs -p test_qdrant_lab.py -v
```

테스트는 fake transport와 socket 차단으로 client의 입력/요청/판정 계약을 검사합니다. 실제 Qdrant API·optimizer·저장·장애 복구를 실행하지 않습니다.
