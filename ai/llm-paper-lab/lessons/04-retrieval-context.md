# M08–M09. 검색을 붙이는 것에서 근거 사용을 검증하는 것으로

[트랙 안내](../README.md) · [논문 지도](../papers.md) · [실행 가능한 CPU 실험](../labs/README.md) · [평가](../assessment.md)

각 모듈은 2주·24시간입니다. 아래 상세 실험은 별도 표시가 없는 한 **학습자가 구현할 과제**이며, CPU 제공 코드는 작은 계약 검증에 한정됩니다. 모델 다운로드·GPU 학습·외부 API 호출을 자동 실행하지 않습니다.

<a id="m08"></a>
## M08. DPR와 원래 RAG: 검색 분포와 생성 분포를 분리하기

### 원 논문에서 확인할 것

[P11 DPR](https://arxiv.org/abs/2004.04906)은 질문과 passage를 각각 인코딩해 검색하는 dual-encoder 접근을 다룹니다. 읽을 때 negative 선택, 학습 데이터, 검색 평가와 후속 QA 평가를 나눕니다. dense가 자신의 업무 데이터에서도 sparse보다 낫다는 결론은 새 실험이 필요합니다.

[P12 RAG](https://arxiv.org/abs/2005.11401)는 학습된 생성기와 검색 가능한 외부 기억을 결합합니다. 원문의 RAG-Sequence와 RAG-Token은 latent document를 주변화하는 위치가 다릅니다. 단순히 검색 문서를 한 prompt에 이어 붙이는 오늘날의 RAG 앱을 만들었다고 원 논문 구조를 재현했다고 부르지 않습니다.

### 원리와 손 계산

학습용으로 질문 벡터 `q`, 문서 벡터 `d`, 점수 `s=q·d`를 두고, 정답 passage와 negative들의 softmax에서 정답의 음의 로그 확률을 계산합니다. negative가 진짜 오답인지, 같은 질문의 또 다른 정답인지 구분해야 합니다. 학습 중 사용할 수 있었던 정보와 서빙 시 사용할 수 있는 정보를 따로 적습니다.

원문의 RAG 모델식을 다음 간략 표기로 다시 유도합니다. `r(z|x)`는 검색 문서의 가중치, `g_i(z)=p_theta(y_i|x,z,y_<i)`는 질문·해당 문서·이전 정답 token을 조건으로 한 다음 정답 token 확률입니다. token들이 조건 없이 독립이라는 뜻이 아닙니다. top-k 절단과 정규화 방식을 원문/구현에서 확인합니다.

- sequence 수준: `sum_z r(z|x) * product_i g_i(z)`
- token 수준: `product_i sum_z r(z|x) * g_i(z)`

문서 두 개와 출력 두 token에 대해 `r=(0.5,0.5)`, `g_1=(0.9,0.1)`, `g_2=(0.1,0.9)`를 넣습니다. sequence 값은 `0.09`, token 값은 `0.25`입니다. 이는 합과 곱의 순서를 바꾸면 서로 다른 모형이 된다는 **손 계산 oracle**이지 QA 성능 예측이 아닙니다. [원문 모델 정의](https://arxiv.org/html/2005.11401v4)를 읽고 어떤 가정에서 둘이 같아지는지 반례와 함께 설명합니다.

### 실험 계약

먼저 합성 corpus를 만듭니다. 문서에는 `doc_id`, `version`, `tenant_id`, `effective_at`, 본문을 둡니다. query별로 정답 문서 ID, 허용 tenant, 정답 또는 `unanswerable`을 **retriever와 독립적인 사람이 먼저 고정**합니다. 문서/질문의 근접 중복과 같은 업무 entity가 train/dev/test에 섞이는지 검사합니다.

1. CPU 기본 실험에서 lexical ranker의 `recall@k`/순위 계약을 확인합니다. [실습 안내](../labs/README.md)의 `lab.py --lab retrieval`은 lexical toy이며 DPR의 dense 학습 또는 생성기를 제공하지 않습니다.
2. 학습자가 구현하는 확장에서는 동일 corpus로 sparse baseline과 허가된 frozen embedding 검색을 비교합니다. embedding model/revision, tokenizer, pooling, normalization, 거리 함수를 기록합니다. cosine과 inner product는 normalization 조건 없이 같은 점수가 아닙니다.
3. 작은 corpus의 exact search 결과를 oracle로 고정한 뒤 ANN을 추가합니다. **ANN recall**(exact 결과와의 일치)과 **task relevance recall**(정답 문서 포함)을 별개로 측정합니다.
4. generator 비교는 no-context, oracle-context, retrieved-context, deliberately-wrong-context 네 조건을 둡니다. 모델/decoding/질문을 고정하고 context만 바꾸어 검색과 근거 사용 문제를 분리합니다.
5. 생성 정확성, 근거 ID의 실제 존재, claim별 뒷받침, 답할 수 없는 질문에서의 abstention, 비용·지연을 각각 기록합니다. 문서를 인용했다는 사실만으로 문장이 지지된다고 판정하지 않습니다.

### Ablation과 실패 주입

한 번에 하나의 요인만 바꾸는 1차 실험 후 상호작용을 확인합니다: chunk 크기/overlap, top-k, negative 종류, reranking, embedding revision, metadata filter 위치. chunk 수 증가로 query당 token 예산이 늘었다면 별도의 예산 효과로 표시합니다. 부정 예시는 아래를 포함합니다.

| 주입 | 관측해야 하는 실패 | 독립 oracle |
| --- | --- | --- |
| 정답과 같은 단어를 가진 오답 문서 추가 | lexical rank 상승과 실제 관련성의 분리 | 사전 고정 정답 문서 ID |
| 최신 문서를 바꾸되 index 갱신 지연 | stale 검색·답변 | 원본 version/hash와 index manifest |
| 삭제/권한 철회 후 cache 재사용 | 권한 없는 문서 노출 가능성 | 요청자의 현재 권한 목록 |
| duplicate passage를 대량 추가 | 다양성 감소·평가 count 왜곡 | unique source ID와 원문 범위 |
| 문서 안에 “규칙을 무시하라”는 문구 추가 | 데이터가 지시로 승격되는지 | 고정된 앱 지시와 도구 허용 목록 |

권한 filter는 보안 경계입니다. 응답 최종 단계만 가리고 모델 prompt/로그에 다른 tenant 문서를 넣는 것은 성공이 아닙니다. 인덱스와 cache까지 정책 적용 범위를 명시하며 이 보안 실험을 원 논문이 보장한 기능으로 돌리지 않습니다.

### 2주 진행·통과

1주차 12시간: 원문/식 4시간, corpus·oracle 4시간, lexical/exact baseline 4시간. 2주차 12시간: 제한된 확장 또는 모형 실험 6시간, 실패 주입 3시간, 분석·리뷰 3시간. 모델 실행 권한/자원이 없으면 확장은 설계로 남기고 모델 효과를 주장하지 않습니다.

산출물은 손 계산, corpus manifest, query별 rank와 결과, 변경 변수, 원시 실패 기록, 채택/기각한 가설입니다. 검색이 좋아도 생성이 틀리는 사례와 검색이 실패했는데 모델이 기억으로 맞히는 사례를 분리해야 통과합니다. 원 논문 수치 재현을 주장하려면 데이터 split·checkpoint·학습·평가 protocol의 일치 증거가 추가로 필요합니다.

<a id="m09"></a>
## M09. Lost in the Middle: context window 크기와 활용 능력

### 원리

[P13 Lost in the Middle](https://arxiv.org/abs/2307.03172)은 입력에서 관련 정보의 위치를 바꾸며 multi-document QA와 key-value retrieval을 평가합니다. 이 과정은 “지금 선택한 모델도 중간 근거를 놓치는가?”를 새로 묻습니다. 과거 모델의 위치 효과를 모든 최신 모델의 필연적인 성질로 가정하지 않습니다.

**token 한도**, **실제로 전달된 token 수**, **근거가 남은 위치**, **모델이 근거를 사용한 결과**는 다른 변수입니다. 긴 context를 허용한다는 API 설명은 모든 위치에서 같은 신뢰도를 보장하지 않습니다. 응답 실패를 attention 자체의 원인이라고 단정하기 전에 truncation·prompt template·tokenization을 제거합니다.

### Paired position 실험

학습자가 만드는 fixture는 동일 질문·동일 문서 집합·동일 정답에 대해 정답 근거 위치만 앞/중간/뒤로 바꿉니다. distractor 순서는 별도의 seed로 counterbalance하며 총 token 수와 문서 경계 형식은 최대한 맞춥니다. query마다 세 위치 결과를 한 묶음으로 보존합니다. 위치별로 다른 질문을 배정하면 난이도 차이가 섞입니다.

두 종류를 분리합니다. A는 무작위 합성 key-value와 exact answer oracle, B는 직접 작성한 작은 업무 문서의 근거 기반 QA와 사전 검토한 answer set입니다. key-value 성공을 장문 업무 추론 성공으로 일반화하지 않습니다. 답이 없는 항목도 포함하고 모델이 기억으로 맞힐 수 없게 합성 entity를 씁니다.

- 독립변수: 근거 위치, distractor 수, 내용 유사성. 초기에는 한 축만 바꿉니다.
- 고정: 모델/revision, prompt, decoding, 출력 한도, tokenizer, 같은 query ID.
- 관측: 실제 prompt token 수, 근거 잔존 여부, 위치별 정답률, abstention, latency, 비용. API가 tokenization 정보를 제공하지 않으면 추정치임을 표시합니다.
- 통계: query 단위 paired 차이와 confidence interval을 보고합니다. 같은 query의 세 위치를 독립 표본 세 개로 세지 않습니다. 모델 randomness 반복과 query 수 증가도 다른 축입니다.

### 원인을 가르는 대조군

1. 실제 전달 직전 prompt를 synthetic-only로 저장하고 정답 근거의 offset/hash를 계산합니다. 서버측 숨은 preprocessing은 관측 불가로 남깁니다.
2. truncated input, duplicate key, 상충하는 최신/과거 문서, 답과 무관한 긴 서문을 따로 주입합니다. 중복 key의 정답 규칙은 실험 전에 고정합니다.
3. oracle chunk 하나만 주었을 때도 실패하면 context 위치만의 문제라는 가설을 보류합니다.
4. 근거 앞뒤 배치·rerank·요약을 개선안으로 비교하되 정답 정보를 요약기에 미리 주지 않습니다. 요약 비용과 원문 정보 손실도 기록합니다.
5. dev에서 고른 전략을 untouched test에서 한 번 평가합니다. test에서 위치/길이를 바꿔가며 가장 좋은 결과만 보고하지 않습니다.

### 통과와 업무 연결

1주차는 fixture/길이 감사/paired harness, 2주차는 사전에 정한 작은 모델 실험 또는 미실행 설계·통계 모형 검증에 씁니다. 실제 모델 결과가 없다면 “위치 효과 검증 완료”라고 적지 않습니다. 출력에는 raw query별 결과, 실패 분류, interval, 비용, 모델 변경 시 다시 검증할 항목이 있어야 합니다.

PostgreSQL의 문서 version 원장, Kafka의 index 갱신 event, ClickHouse의 query별 평가 집계는 선택 확장입니다. 벡터 DB·메시지 브로커 전체를 먼저 설치하는 것이 학습 통과 조건은 아닙니다. 이 과제의 핵심은 **문서가 존재함 → 검색됨 → prompt에 남음 → 답에서 올바르게 사용됨**을 각각 독립적으로 확인하는 것입니다.
