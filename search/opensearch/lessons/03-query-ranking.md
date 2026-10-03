# 03. Query·랭킹 — 일치, 점수, 업무 관련성을 분리한다

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

OS05는 query 의미와 BM25, OS06은 relevance 판단의 실험 설계를 다룹니다. 제공 OFFLINE `bm25`는 수식·tokenization을 명시한 교육용 계산입니다. 실제 Lucene norm encoding, segment 통계·query rewrite·boost와 byte 단위로 같은 구현이라는 뜻이 아닙니다.

<a id="os05"></a>
## OS05 · bool·phrase·BM25와 explain

### 원리와 내부 동작

검색은 후보가 되는 문서를 결정하는 단계와 그 후보의 순위를 정하는 단계를 구분할 수 있습니다. `filter`는 score 기여 없이 조건을 적용하는 맥락이고 `must`/`should`는 query 구조에 따라 일치와 점수에 관여합니다. `should`만 있을 때와 `must`/`filter`가 함께 있을 때 `minimum_should_match`의 기본값이 달라지는 사례를 직접 확인하고 중요한 업무 조건은 명시합니다. [공식 bool query](https://docs.opensearch.org/latest/query-dsl/compound/bool/)와 실제 query 결과를 대조합니다.

phrase는 term들이 있다는 사실에 더해 위치 관계를 검사합니다. slop을 늘리는 것은 철자 오타 교정과 다르며 같은 token bag의 두 문장을 다른 결과로 만들 수 있습니다. multi-field의 term 분포·field 길이·boost, `dis_max`와 bool의 결합 의미도 query rewrite와 explain을 통해 구별합니다.

교육용 BM25 한 term의 기여는 다음 형태로 계산할 수 있습니다. 실제 점수의 상수·norm 근사·overlap 처리 등은 고정 Lucene 구현과 대조합니다.

```text
idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
tf_part = tf(t,d) * (k1 + 1) / (tf(t,d) + k1 * (1 - b + b * len(d)/avg_len))
score(d,q) = sum(idf(t) * tf_part for selected query terms)
```

`k1`의 TF 포화, `b`의 길이 보정, 희귀 term의 IDF가 각각 어떤 비교를 바꾸는지 분리합니다. score는 확률이나 다른 query 사이의 공통 관련성 척도가 아닙니다. segment/shard 범위의 통계와 field별 문서 수를 무시한 수작업 점수를 엔진 버그의 증거로 쓰지 않습니다. 분산 통계는 OS07에서 확장합니다.

### 추가 실험

1. 희귀 term 1회, 흔한 term 반복, 긴 문서, 짧은 문서, 일치 term 없는 문서로 최소 8개 corpus를 만듭니다. `k1`, `b` 중 하나만 바꾸어 예상 순서를 적습니다.
2. `should` 단독 query에 tenant filter를 추가하고 `minimum_should_match`를 생략한 경우와 명시한 경우를 비교합니다. tenant filter가 업무 접근 조건이더라도 실제 authorization의 대체물이 아님을 표시합니다.
3. `_explain`에서 일치 여부·term별 기여·norm 관련 값을 기록합니다. 검색 요청의 `profile: true`는 실행 경로 진단에 사용하되 계측 오버헤드가 있는 시간을 일반 사용자 latency로 보고하지 않습니다.
4. 동일한 term 빈도라도 phrase 순서가 다른 문서, 빈 field, field가 없는 문서를 넣어 score 0과 non-match를 분리합니다.
5. 색인 corpus에 query와 무관해 보이는 문서를 추가한 뒤 상대 점수가 바뀌는지 확인합니다. corpus 통계 변화와 새로운 관련 문서 추가 효과를 구분합니다.

### 통과 기준

손으로 계산한 작은 BM25 oracle과 엔진 결과 차이를 설명합니다. query 조건을 바꿔 candidate가 달라졌는데 이를 scoring 개선으로만 해석하면 미통과입니다. 소스에서 query builder→Lucene query/weight/scorer→top-doc collector 경로를 찾아 설명합니다.

<a id="os06"></a>
## OS06 · judgment·지표·통계·실패 slice

### 원리

정확한 구현도 사용자의 질문에 부적절한 문서를 높게 배치할 수 있습니다. query별 문서 relevance를 등급으로 정의하고 domain·시점·권한을 포함한 judgment 계약을 먼저 만듭니다. click은 위치 편향·노출 선택 편향을 포함하며, 미판정 문서를 자동으로 부관련이라고 단정하는 평가도 편향을 만듭니다.

MRR은 첫 관련 문서의 위치, nDCG는 등급 relevance와 순위 할인, Recall@k는 관련 문서를 얼마나 회수했는지 봅니다. 각 지표의 k, relevance threshold, gain, tie, 관련 문서가 없는 query의 처리 규칙을 명시합니다. 서로 다른 candidate pool의 불완전 judgment로 얻은 숫자를 절대적인 승패로 쓰지 않습니다.

### 추가 실험

1. 탐색형, 정확 ID형, 짧은 다의어, 한국어, 오탈자, 시간 민감, 권한 제한 query로 최소 30개 작은 평가셋을 직접 만듭니다. 합성 corpus에서 시작하고 사용 권한 없는 문서는 수집하지 않습니다.
2. baseline과 변경안이 검색한 문서를 함께 pool하여 시스템 이름을 숨기고 판단합니다. 일부 query는 두 평가자가 독립 판단하고 불일치 사유를 기록합니다.
3. 문서 family·중복 cluster·시간 경계를 고려해 tuning과 holdout을 분리합니다. 동일 문서의 chunk를 서로 다른 split에 두어 쉬워진 성능을 탐지합니다.
4. BM25 parameter 또는 analyzer 한 변인을 바꿉니다. 전체 평균뿐 아니라 query slice별 nDCG@10, MRR, miss 원인을 기록합니다. query 단위 paired 차이와 bootstrap 구간을 함께 제시합니다.
5. judgment를 보기 전에 holdout 변경을 동결합니다. 30개는 교육용 최소치일 뿐 production 유의성 보장이 아니며 효과 크기·신뢰구간·평가자 차이를 함께 해석합니다.

### 제출·반례

상위 10개가 모두 같은 원문 chunk인 경우, 삭제된 최신성 위반 문서가 높은 relevance를 받는 경우, 다른 tenant 문서를 잘 찾는 경우를 각각 만듭니다. 단일 nDCG만으로 세 경우를 정상이라고 평가하는 시스템은 gate를 통과하지 못합니다.

실험 보고서에는 judgment 원장·split fingerprint·metric 구현의 손계산 fixture·query별 변화·최악 slice·채택/보류 결론을 포함합니다. [LLM 논문 실험](../../../ai/llm-paper-lab/README.md)의 RAG 평가로 확장할 때도 retrieval 성공과 생성 답변의 근거 충실성을 별도로 평가합니다.
