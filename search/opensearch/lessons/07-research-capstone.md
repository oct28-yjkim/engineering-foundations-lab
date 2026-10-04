# 07. 소스·논문·작은 연구 — 설명을 반증 가능한 증거로 바꾼다

[커리큘럼](../curriculum.md) · [소스·논문 지도](../source-reading.md) · [평가](../assessment.md)

이 강의는 저장소 전체를 읽는 것이 아니라 관찰한 작은 현상 한 개의 설명을 구현·논문·회귀 테스트로 좁히는 훈련입니다. OpenSearch core, Lucene, k-NN, Security 등 plugin과 관리형 서비스의 책임 경계를 분리합니다.

<a id="os13"></a>
## OS13 · 고정 소스·논문·반증

### 재현할 질문 선택

다음 중 한 가지를 고릅니다. 질문은 측정 가능한 결과와 실패 조건을 가져야 합니다.

- 동일 token 집합의 phrase 결과가 다른 이유는 position과 query rewrite 중 어디에 있는가?
- refresh 뒤 새 문서가 검색되는 reader 경계와 crash 복구의 translog 경계는 어떻게 다른가?
- bulk 일부 item만 실패했을 때 transport/primary/response 경로의 책임은 어디인가?
- shard 통계 또는 후보 truncation이 순위에 주는 영향을 독립적으로 재현할 수 있는가?
- filtered ANN의 후보 부족·exact fallback·graph 탐색 중 무엇이 지연과 recall을 바꿨는가?

### 소스 읽기 절차

1. [소스 지도](../source-reading.md)의 OpenSearch 3.9.0 고정 commit과 실제 Lucene 10.5.1 의존성을 기록합니다. plugin은 core와 별도 commit·배포 버전으로 기록합니다.
2. REST action 또는 query builder 하나를 진입점으로 고릅니다. 관련 symbol 최소 5개, 핵심 자료구조 2개, 동시성/수명주기 경계 1개를 좁혀 읽습니다.
3. 성공 경로뿐 아니라 conflict·timeout·parse 오류·resource rejection 중 하나의 응답 생성 지점을 찾습니다. 예외를 감춘 상위 caller가 있는지도 확인합니다.
4. 기존 test의 fixture와 assertion을 읽고 가장 작은 회귀 테스트를 추가 설계합니다. 실제 build를 실행했다면 도구 버전·명령·결과를, source-only이면 실행하지 않은 항목을 표시합니다.
5. 잘못된 구현 가설을 임시 mutation 또는 별도 순수 모형으로 만들어 테스트가 실패하는지 확인합니다. upstream 코드를 수정해 테스트하지 않았다면 “upstream regression test 통과”라고 쓰지 않습니다.

### 논문을 읽는 순서

[소스·논문 지도](../source-reading.md)에서 BM25/확률적 검색, HNSW, RRF와 평가 자료를 선택합니다. 두 편 이상을 읽고 논문당 다음 다섯 줄을 먼저 씁니다.

```text
주장: 무엇이 어떤 조건에서 나아진다는가?
가정: corpus·query·거리·분포·후보·hardware·failure model은 무엇인가?
검증: baseline·metric·ablation·variance가 무엇을 보여 주는가?
불일치: OpenSearch의 shard·segment·filter·quantization·ACL과 무엇이 다른가?
반증: 작은 실험에서 어떤 관찰이 내 설명을 기각하는가?
```

논문 속 단일 graph를 여러 segment·shard의 graph와 동치로 취급하지 않습니다. RRF 논문의 결과를 모든 domain에서의 절대 우월성으로 읽지 않으며, BM25 수식을 구현 norm 근사·query rewrite 없이 모든 score와 직접 일치시킬 수 있다고 가정하지 않습니다. 과거 논문은 원리의 출처이지 3.9.0의 feature 지원표가 아닙니다.

### 제출·구술

원시 실행 결과, call path, 고정 source link, 독립 oracle, 반례, 논문 가정 표를 제출합니다. 발표 중 하나의 input 또는 knob를 바꾸면 어떤 결과가 바뀔지 먼저 예측합니다. 실제 관측과 맞지 않으면 설명을 수정하고 “환경 탓”으로 끝내지 않습니다. BUILD에 필요한 compiler·JDK·의존성은 선택 환경에서 준비하며 기본 LAB이나 선택 원리 모형이 대신 설치하지 않습니다.

<a id="os14"></a>
## OS14 · 2주 최소 연구 캡스톤

### 범위

이전 모듈의 corpus·client·보고서를 재사용하여 **한 경로, 변경 하나, 실패 조건 두 개**를 다룹니다. 논문 원문 전체 재현이나 전체 검색 플랫폼 구축을 요구하지 않습니다. 아래 중 하나를 선택하고 실제 실행 범위를 명시합니다.

| 선택 | baseline과 변경 | 실패 조건 예 | 독립 oracle |
| --- | --- | --- | --- |
| 분석·랭킹 | analyzer 또는 BM25 parameter 하나 | phrase 오탐, 희귀 query 회귀 | 손으로 정한 match 집합·frozen judgment |
| write projection | bulk retry 또는 version gate 하나 | 부분 실패, late event 뒤 삭제 부활 | ID별 version·payload·삭제 원장 |
| 분산 후보 | 후보 크기 또는 shard 배치 하나 | 후보 부족, 집계 누락 | 고정 score 정렬·전체 counter |
| vector·hybrid | filter 방식 또는 fusion 하나 | restrictive filter, union 후보 누락 | 같은 필터의 exhaustive top-k·judgment |

선택 OFFLINE 부록으로는 원리 연구만 기록하며 운영 과정은 미완료입니다. 주 경로 LOCAL-ENGINE은 기본 fixture 외 [정상 기준선·실제 사건·회복 증거](../operations.md)를 추가합니다. 다중 노드·보안·ANN·복원은 필요한 환경이 이미 있을 때만 작은 범위로 선택합니다.

### 10일 작업 단위

1–2일: 가설·불변식·실행 범위·시간/자원 상한·음성 대조군 확정. 3–4일: baseline·독립 oracle·반복 가능한 입력. 5–6일: 변경 하나와 실패 조건 두 개를 실행. 7–8일: 소스 추적·경쟁 가설·holdout 또는 복구 검산. 9–10일: 동료 재현·구술·결론·미검증 항목 정리.

빠른 결과가 나왔다고 남은 시간을 기능 추가로 채우지 않습니다. 가설이 기각되거나 효과가 불확실한 연구도 정확한 증거와 한계를 남기면 의미 있는 완료입니다. 비용·복잡성이 늘어난 변경은 품질/운영 이익이 충분한지 채택 판단에 포함합니다.

### 완료 산출물

- 실행 명령·환경·server/plugin/source revision·corpus/query/judgment fingerprint.
- 정상·실패·변경/복구 결과와 ID별 차이, 실제 실행하지 않은 조건 목록.
- source symbol 5개와 관련 test·논문 가정의 연결.
- [평가표](../assessment.md)의 4개 영역 점수·필수 gate·동료의 재현 기록.
- 정리 대상 index·PIT·container·snapshot 목록. 자동 broad delete가 아닌 대상 확인·보존 계획.

더 큰 프로젝트는 별도 [8주 검색 품질·복구 캡스톤](../../../capstones/search-quality-recovery.md)입니다. PostgreSQL 원장, Kafka CDC, OpenSearch projection, RAG 권한·최신성을 연결하는 작업을 28주 마지막 2주에 숨겨 넣지 않습니다.
