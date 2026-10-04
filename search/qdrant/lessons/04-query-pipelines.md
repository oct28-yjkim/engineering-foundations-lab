# 04. 후보 검색, 결합, 재순위를 분리하기

[과정](../curriculum.md) · [기본 LAB](../labs/README.md) · [기능 지도](../feature-map.md)

<a id="qd07"></a>
## QD07 — hybrid는 query 한 번이지만 여러 계약이다

목적은 한 표현이 놓친 정보를 다른 표현으로 보완하는 것입니다. sparse의 indices/values는 vocabulary 계약을 갖고 named dense와 별도 설정/인덱스를 사용합니다. 합성 sparse가 동작한다는 증거는 실제 BM25·SPLADE tokenizer나 embedding 품질의 검증이 아닙니다.

Query API의 prefetch는 후단의 후보 경계를 만듭니다. RRF는 순위 신호를, DBSF는 반환된 score 분포를 사용하므로 입력 branch와 limit을 바꾸면 결과도 달라질 수 있습니다. [공식 hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)를 읽고 API 지원과 검증 여부를 분리합니다.

1. 기본 runner의 dense와 sparse query를 **따로** 읽고 후보 ID/rank를 보존합니다. 같은 point가 두 branch에 등장하는 경우를 손으로 표시합니다.
2. RRF 결과를 runner의 독립 정답과 대조합니다. tie 허용 기준을 먼저 정의합니다. 최종 top-k만 보고 한 branch가 정상이라고 결론 내리지 않습니다.
3. 별도 fixture에서 두 branch 모두 놓친 정답을 만듭니다. fusion 방식만 바꿔 복구할 수 없음을 확인합니다. prefetch limit과 final limit, offset을 별도 변수로 기록합니다.
4. DBSF는 추가 수동 query 과제입니다. 극단 score 하나/동일 score만 있는 branch를 넣어 작은 후보 표본의 영향을 비교합니다. RRF보다 항상 좋다고 주장하지 않습니다.
5. IDF modifier/BM25는 tokenizer·corpus 통계·필터 범위까지 조사합니다. sparse 내적, IDF 보정, 텍스트 임베딩 생성기를 같은 기능이라고 부르지 않습니다.

채택 판단: exact identifier와 자연어가 섞이면 hybrid를 검토하되, 단일 dense가 요구 품질을 충족하면 운영 복잡도를 추가할 근거가 필요합니다. branch 실패·빈 후보·모델 교체 시 fallback과 평가 slice를 명시합니다. 제출은 각 단계의 ID 원장, 후보 누락 반례, RRF/DBSF 선택 및 비채택 이유입니다.

<a id="qd08"></a>
## QD08 — multivector, group, 추천·탐색의 쓰임과 한계

다음 기능은 “현재 미사용”이어도 배웁니다. multivector/MaxSim의 작은 예제는 [고급 LAB](../labs/advanced.md)에 있고, 나머지는 별도 fixture를 구현하는 **E/R 과제**입니다. [vectors](https://qdrant.tech/documentation/manage-data/vectors/), [explore](https://qdrant.tech/documentation/search/explore/), [고정 API](../source-reading.md)를 참고합니다.

| 기능 | 목적·작동 | 관측·제약·채택 판단 |
| --- | --- | --- |
| multivector/MaxSim | query 행별 문서 행과의 최대 유사도들을 결합해 late interaction | 작은 행렬을 손계산하고 실제 score와 비교. token 수·후보 수 비용, query/document 방향을 확인; 일반 평균 pooling과 다름 |
| multi-stage rerank | 저비용 후보를 고비용 표현/계산으로 재정렬 | rerank 입력 IDs와 최종 IDs 보존. 후보 밖 정답 복구 불가; 전체 지연 budget 내에서만 채택 |
| group/lookup | chunk 결과를 문서 단위로 묶고 다른 자료를 연결 | group key·group_size·limit의 수량 계약 검산. 누락 key·다중 값·lookup 미존재 반례; 인가/최신성은 별도 |
| recommend | positive/negative 사례로 선호 방향 구성 | 전략과 using을 명시하고 예시 ID/최종 결과 비교. 사용자 피드백이 없으면 nearest가 더 단순 |
| discover/context | target 또는 선호 쌍의 제약으로 탐색 | 쌍의 방향을 뒤집어 결과 차이 관찰. 업무 relevance가 자동으로 보장되지는 않음 |
| formula query | 유사도 외의 명시적 점수 요소 결합 | 입력 누락·큰 boost·시간 단위 오류로 순위를 뒤집는 반례. 튜닝 데이터/holdout 분리 |
| scroll/order_by/facet/batch | 순회·정렬·집계·묶음 처리 | query top-k와 다른 계약. 동시 write, pagination 중복/누락, index/limit·부분 오류 확인 |

과제는 기능 두 개를 골라 정상 3개와 실패 2개의 정답을 작성하는 것입니다. endpoint 성공만 제출하지 말고 “다른 기능으로 대신하면 무엇이 바뀌는가”를 답합니다. grouping을 다양성 보장 전체로, recommend를 개인화 모델 학습으로, MaxSim 계산을 ColBERT 모델 재현으로 확대 해석하지 않습니다.

제출: 목적/상태/관측/제약/채택 여부 다섯 칸, 단계별 후보 ledger, 실제 실행 또는 조사 상태. 모델 논문과 검색 엔진 지원 범위는 [소스·논문 지도](../source-reading.md)에서 분리합니다.
