# 01. Lucene·분석·mapping — 문자열이 검색 가능한 증거가 되는 과정

[커리큘럼](../curriculum.md) · [소스 지도](../source-reading.md) · [실습 안내](../labs/README.md)

이 강의의 목표는 “검색이 안 된다”를 analyzer, indexed term, field 자료구조, query 의미 중 어느 경계의 문제인지 좁히는 것입니다. OS01은 언어·token, OS02는 저장 구조·schema 계약을 담당합니다. 기본 LOCAL-ENGINE은 term/match/phrase 결과 비교를 제공합니다. `_analyze`의 단계별 관찰, 복잡한 동의어·한국어·nested 과제는 추가 구현입니다.

<a id="os01"></a>
## OS01 · 문자에서 token graph까지

### 원리와 내부 동작

char filter → tokenizer → token filter를 문자열 함수 세 개 정도로 축소하지 않습니다. token text뿐 아니라 offset, position increment, position length가 다음 query의 의미를 바꿉니다. stopword를 제거해도 문장 간격이 사라지는 것은 아니며 동의어가 한 token을 여러 token으로 바꾸면 graph 경로가 생깁니다. index analyzer와 search analyzer는 같은 이름일 필요가 없지만 서로 호환되는 token 계약이 필요합니다.

`term`은 분석된 term 사전을 대상으로 하는 정확한 term 조회이고 `match`는 query text를 분석합니다. 원문 `"Search Engine"`과 indexed term `"search"`는 다른 대상입니다. 기본 analyzer의 동작을 한국어 형태소 분석 능력으로 일반화하지 않습니다. 형태소 analyzer를 선택할 경우 plugin·사전·복합명사·사용자 사전 버전을 corpus와 함께 고정합니다. [공식 term query](https://docs.opensearch.org/latest/query-dsl/term/term/)와 [분석 API](https://docs.opensearch.org/latest/api-reference/analyze-apis/)에서 계약을 확인합니다.

### 추가 실험

1. 영문 대소문자, 하이픈, 숫자 ID, 한국어 복합명사, emoji, 빈 문자열, stopword만 있는 문장 각 2개로 14개 이상 fixture를 만듭니다. 기대 token을 API 실행 전에 적습니다.
2. `_analyze`의 상세 결과에서 각 단계의 token·offset·position을 보존합니다. offset은 원문에서의 위치, position은 query 위치 관계임을 구분합니다.
3. 같은 text에 `term`, `match`, `match_phrase`를 적용합니다. 일치 여부와 score를 별도 표로 만듭니다. 원문의 부분 문자열 검색과 term 검색도 구별합니다.
4. `"ssd"`와 `"solid state drive"` 같은 다단어 동의어를 search-time graph 방식으로 비교합니다. 동의어 없는 대조군과 인접하지 않은 phrase 음성 사례를 반드시 넣습니다.
5. 분석 변경 전후 기존 index가 자동 재분석되지 않는 사례를 만듭니다. 새 index의 결과와 기존 index의 search analyzer만 바꾼 결과를 구분합니다.

graph의 `positionLength`가 index-time 저장에서 query-time graph와 같은 의미로 보존된다고 가정하지 않습니다. [Token graphs](https://docs.opensearch.org/latest/analyzers/token-graph/)의 제약을 읽고 어떤 경로를 query가 생성하는지 그립니다. 동의어를 무제한 늘리는 것은 recall 개선과 같지 않으며 query 확장량·오탐·latency도 평가합니다.

### 통과 기준과 구술

- 원문 하나를 골라 3단계 분석과 최종 term/position을 설명하고, term와 phrase의 서로 다른 결과를 예측합니다.
- token text 집합은 같지만 position이 다른 두 문서의 phrase 결과가 달라지는 반례를 제출합니다.
- 검색 실패를 analyzer 문제와 mapping 문제 중 하나로 좁히는 최소 진단 순서를 제시합니다.
- 소스에서 token stream 생성·query builder 변환·Lucene query 경계를 찾아, 분석 API 결과가 실제 scoring 실행 전체를 보여 주지 않는 이유를 설명합니다.

<a id="os02"></a>
## OS02 · postings·doc values·BKD와 schema

### 원리와 내부 동작

postings는 term에서 문서·빈도·위치로 가는 접근을, doc values는 문서에서 field 값으로 가는 접근을 제공합니다. 숫자/공간 range의 point 구조와 text postings를 동일한 인덱스로 부르지 않습니다. Lucene의 BKD 관련 소스에서 point 차원 분할·block·leaf 방문을 추적하되 모든 numeric query가 항상 같은 물리 경로를 사용한다고 단정하지 않습니다.

`text`는 분석·full-text, `keyword`는 단일 값의 정확 일치·정렬·집계에 주로 사용합니다. `_source`는 검색용 자료구조 그 자체가 아니며 doc values가 원본 JSON의 순서·중복·표현을 그대로 복원한다고 가정하지 않습니다. `text`의 fielddata 활성화를 집계 오류의 무조건적인 해결책으로 삼지 않습니다. [Doc values 문서](https://docs.opensearch.org/latest/mappings/mapping-parameters/doc-values/)와 실제 mapping·stats를 함께 읽습니다.

### 추가 실험

1. `doc_id`, `tenant_id`는 keyword, 본문은 text, 금액은 정수 최소 단위, 발생 시각은 명시적 date로 선언합니다. 분석/정렬용 multi-field를 필요한 곳에만 추가하고 dynamic mapping 허용 범위를 적습니다.
2. field 없음, JSON null, 빈 문자열, 빈 배열, 값 배열을 분리합니다. `exists`와 `_source`의 존재가 언제 다를 수 있는지 mapping의 null/ignore 설정까지 기록합니다.
3. `[ {"color":"red","size":"S"}, {"color":"blue","size":"L"} ]`를 일반 object와 nested로 각각 index합니다. `red AND L`이 같은 객체의 조건인지 문서 전체 조건인지 명시해 거짓 일치 oracle을 만듭니다.
4. text/keyword/numeric field 각각에 filter·sort·aggregation을 적용하고 어떤 자료구조를 기대하는지 먼저 예측합니다. query profile·field capabilities·mapping을 대조하되 wall-clock 원인 증명은 별도 측정합니다.
5. 임의 JSON key가 늘어나는 입력을 작은 상한 안에서 생성합니다. mapping field 수·cluster metadata·parse 실패 원장을 만들고 모든 key를 무제한 field로 바꾸지 않는 schema 계약을 설계합니다.

### 제출·실패 gate

field별 원문/분석 term/저장 형태/사용 query/정렬·집계 계약을 제출합니다. 금액을 부동소수점으로 바꿔도 정확하다고 주장하거나 object와 nested가 항상 같다고 주장하면 미통과입니다. `ignore_above`, malformed 처리 등으로 검색 불가능해진 값을 누락 원장 없이 정상 데이터로 집계해도 미통과입니다.

소스 연구에서는 mapper가 만드는 Lucene field, inverted index와 doc values 생성, point query의 세 경계를 연결합니다. 실제 byte layout 전체를 읽기 전에 10개 문서의 동작을 독립 oracle로 설명할 수 있어야 합니다.
