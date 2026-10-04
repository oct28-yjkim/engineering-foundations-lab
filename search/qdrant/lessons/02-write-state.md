# 02. 변경 요청, 저장 상태, 관측 지점

[과정](../curriculum.md) · [기본 실습](../labs/README.md) · [운영](../operations.md)

<a id="qd03"></a>
## QD03 — ACK, 적용, 검색, 내구성은 서로 다른 질문이다

point ID는 논리 대상을 가리키며 upsert는 같은 ID의 값을 바꿀 수 있습니다. vector 업데이트·payload 변경·point 삭제는 의도가 다릅니다. WAL과 segment의 상태를 연결하되 성공 응답 하나를 여러 자원의 원자적 transaction으로 해석하지 않습니다. [공식 points](https://qdrant.tech/documentation/manage-data/points/)와 [storage](https://qdrant.tech/documentation/manage-data/storage/)를 읽습니다.

기본 runner에서 정상 입력 → retrieve/query → point 변경 → 삭제 → 합성 원본 복구를 따라갑니다. 각 단계의 `ID / business_revision / 요청 종류 / wait / operation 상태 / 실제 값`을 기록합니다. `wait=true`를 모든 replica·backup·인덱스 구축 완료의 동의어로 쓰지 않습니다.

추가 client 실험은 **새 disposable collection**에서만 수행합니다.

1. 같은 ID와 같은 payload를 두 번 보낸 뒤 point 수와 최종 값을 비교합니다. 같은 요청 재전송과 다른 ID의 중복 business entity 생성을 구분합니다.
2. revision 2를 쓴 뒤 오래된 revision 1 요청을 재전송하는 순서를 만듭니다. ID의 멱등성만으로 오래된 writer를 막을 수 없음을 보입니다. 실제 시도 전 덮어쓸 대상 하나를 명시합니다.
3. client timeout은 `uncertain`으로 남기고 retrieve/query로 실제 상태를 확인하는 runbook을 작성합니다. 서버 요청 취소와 client 대기 중단을 같다고 가정하지 않습니다.
4. 고정 API의 `insert_only`, `update_only`, 조건부 갱신을 조사하고 기대 거부/무변경 경우를 정합니다. 이 API들은 **조사 과제**이며 runner가 경쟁 writer 보호를 제공하는 것은 아닙니다.

관측: 요청 ID/시각, transport 결과, operation 결과, 재조회 값, 중복 business ID, 삭제된 ID 재등장. 채택 판단: caller의 재시도·순서·업무 version 정책이 없으면 높은 ingestion 처리량만 최적화하지 않습니다. WAL crash/전원 손실은 별도 내구성 환경이 필요하며 기본 삭제/복구와 다른 실험입니다.

제출: 정상/중복/오래된 재전송/미확정 네 원장, 제한된 재시도 조건, 복구 후 기대 ID/값. retry 횟수 증가를 유일한 해결책으로 내면 미통과입니다.

<a id="qd04"></a>
## QD04 — 검색 가능한 데이터와 완성된 인덱스를 구분한다

optimizer는 segment와 index 구성을 변화시키므로 ingest와 query 비용이 시간에 따라 달라질 수 있습니다. 인덱스 설정값을 읽었다고 실제 segment가 그 index를 사용한다고 단정하지 않습니다. [공식 optimizer](https://qdrant.tech/documentation/ops-optimization/optimizer/)와 [monitoring](https://qdrant.tech/documentation/ops-monitoring/monitoring/)을 근거로 [운영 runbook](../operations.md)의 관측을 수행합니다.

| 질문 | 먼저 모을 증거 | 흔한 잘못된 해석 |
| --- | --- | --- |
| 입력을 받았는가? | write 응답·실제 point 조회 | client timeout이니 쓰기 0건 |
| query에 포함되는가? | 같은 필터의 exact ID와 실제 결과 | point 수가 같으니 검색도 정확 |
| 인덱스가 준비됐는가? | collection status·optimizer status·indexed 수/segment 상태 | indexed 수를 곧바로 전체 point 수와 동일시 |
| 왜 느린가? | 동일 구간 요청 histogram·오류·I/O·memory·optimizer 로그 | CPU가 높으니 vector 차원부터 축소 |

작은 LAB는 API 형태·오류 분류를 확인하는 용도입니다. backlog 재현은 point 수/차원/동시성/시간/디스크 상한을 먼저 정한 별도 부하 환경에서 수행합니다. 서버 요청 `usage`와 OS CPU 사용률, client elapsed와 서버 처리 시간을 섞지 않습니다. counter는 reset 여부와 시간창을 함께 기록합니다.

`indexed_only`는 지연을 제한하려는 선택지지만 아직 색인되지 않은 자료의 누락을 허용할 수 있습니다. 읽기 최신성이 더 중요하면 채택하지 않을 이유를 설명합니다. 실행 과제에서는 “더 빨라짐”과 함께 기대 정답의 누락 수를 반드시 측정합니다.

제출: 시간선 1개, 경쟁 가설 3개, 필요한 지표/단위/분모, 중단 조건, backlog 해소 뒤 검색 정답 검산. 모든 endpoint가 readiness를 통과했다고 모든 shard/검색 품질이 정상이라고 판단하지 않습니다.
