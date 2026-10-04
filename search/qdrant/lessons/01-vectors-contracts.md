# 01. 벡터와 payload의 계약

[과정](../curriculum.md) · [기본 실습](../labs/README.md) · [기능 지도](../feature-map.md)

<a id="qd01"></a>
## QD01 — 유사도를 계산하기 전에 표현의 계약을 맞춘다

목적은 point ID, payload, vector를 분리하고 “같은 의미 공간”이라는 전제를 설명하는 것입니다. named vector는 동일 point의 여러 표현을 구분하며, multivector의 여러 행과 같은 개념이 아닙니다. 차원이 같아도 모델/전처리가 다르면 의미 호환성을 보장하지 않습니다. [공식 vectors](https://qdrant.tech/documentation/manage-data/vectors/)와 [collections](https://qdrant.tech/documentation/manage-data/collections/)를 읽습니다.

기본 runner의 합성 dense/name/dimension을 먼저 기록합니다. 다음 거리 비교는 **별도 작은 collection을 준비하는 수동 확장 과제**입니다. 원래 LAB collection을 바꾸지 않습니다.

1. query `[1,0]`, A=`[1,0]`, B=`[2,0]`, C=`[0,1]`를 손으로 계산합니다. Cosine은 A/B가 동률, Dot은 B>A>C, Euclid는 A가 가장 가깝습니다. tie를 하나의 ID 순서로 강제하지 않습니다.
2. 같은 세 point를 거리별 별도 collection에 넣고 query의 ID/score와 수작업 값을 대조합니다. Cosine의 정규화 때문에 반환 vector가 원본 byte와 같을 것이라 기대하지 않습니다.
3. dimension 오류와 없는 `using` 이름을 각각 호출해 diagnostic을 분류합니다. 실패 요청 전후 point 원장이 같은지 확인합니다. 기본 runner가 다루는 해당 사건과 연결합니다.
4. 모델 revision만 다른 두 vector를 섞으면 syntax는 통과해도 relevance가 무너질 수 있음을 별도 judgment로 설명합니다. 합성 축 벡터는 이 의미 품질을 측정하지 않습니다.

관측은 collection의 vector 설정, point ID/저장 값, query score, client/server 오류입니다. 채택 기준: 단일 표현이면 단순한 vector schema, 서로 다른 검색 목적/모델 이행이면 named vector를 검토합니다. 불필요하게 모든 모델 표현을 저장하지 말고 비용·완료율·삭제 규칙을 정합니다.

제출: 표현 manifest, 세 거리 정답 표, 오류 두 개, 같은 차원≠같은 의미 공간의 반례. 크기 4의 합성 vector를 실제 768/1536차원 성능 근거로 삼지 않습니다.

<a id="qd02"></a>
## QD02 — filter는 자격 조건이고 인증 시스템은 아니다

payload 조건은 유사도와 별도로 후보를 제한합니다. match/range, must/should/must_not, 배열/nested, missing/null/empty를 분리합니다. [공식 filtering](https://qdrant.tech/documentation/search/filtering/)의 실제 조건 문법으로 정답 ID 집합을 먼저 만듭니다.

| 반례 fixture | 비교 질문 | 관측·회복 |
| --- | --- | --- |
| `tier: 2`와 `tier: "2"` | 타입이 다른 match가 왜 0건인가? | retrieve로 원값 확인→계약에 맞는 query→기대 ID 복구 |
| `items=[{kind:a,ok:false},{kind:b,ok:true}]` | kind=a와 ok=true가 서로 다른 원소에서 맞는가? | flat 조건과 nested 조건 ID 차이→nested로 같은 원소 조건 보장 |
| 필드 없음 / `null` / `[]` / `""` | is_empty와 is_null이 무엇을 포함하는가? | 네 point의 literal truth table→실제 count/scroll ID와 대조 |
| tenant=A/B | filter를 삭제할 수 있는 client가 있으면? | 검색 조건과 신뢰 주체의 인가 경계를 따로 기록 |

기본 타입 사건은 runner, nested는 [고급 수동 LAB](../labs/advanced.md), null/empty truth table은 학습자 확장입니다. payload index는 조건별 타입·선택도를 보고 생성하며 모든 필드를 무조건 색인하지 않습니다. index 추가 전후 **정답 집합이 유지되는지**가 먼저이고 지연 비교는 충분한 규모의 별도 실험입니다.

제약: index는 느린 조건을 빠르게 할 수 있지만 잘못된 business predicate를 고치지 않습니다. tenant filter를 지우거나 다른 tenant 값으로 바꿀 수 있는 호출자를 차단하지 못하면 인가 실습 통과가 아닙니다.

제출: 8개 이상 filter의 예상/실제 ID, nested 반례, 필드 타입 계약, index 채택/비채택 근거. 내부 경로는 `struct_payload_index`의 조건별 cardinality와 filtering을 [소스 지도](../source-reading.md)에서 추적합니다.
