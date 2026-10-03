# OpenSearch 28주 심화 커리큘럼

## 운영 중심 진행과 모듈별 진단 증거

주 실습은 [실제 제품 운영 runbook](operations.md)의 **정상 기준선 → 지표/로그 → 경쟁 가설 → 제한된 재현 → 조치 → 회복 검산**입니다. 기존 28주·14모듈·336시간과 원리/내부 구현의 깊이는 유지합니다. 모듈당 실험 10시간은 정상 관측 2시간, 사건/반례와 진단 5시간, 조치·회복 검산 3시간을 기본 배분으로 삼습니다. 원리 모형은 필요할 때 선택하는 보조 자료이며 필수 선행 조건이 아닙니다.

| 모듈 | 실제 제품에서 추가로 남길 진단 증거 |
| --- | --- |
| OS01 | analyzer/token·문서 정답·버전 기준선 |
| OS02 | mapping 오류의 status/error type 분류 |
| OS03 | ACK/GET/search·refresh 상태 진단 |
| OS04 | bulk item별 오류·OCC·안전한 재시도 |
| OS05 | explain/profile과 후보/점수 원인 구분 |
| OS06 | query/judgment slice와 품질 회귀 진단 |
| OS07 | shard/routing·partial 결과·집계 누락 |
| OS08 | allocation decider·replica·복구 상태 |
| OS09 | node stats·GC·queue/rejected·I/O 가설 |
| OS10 | 권한 실패·snapshot 독립 복원 검산 |
| OS11 | exact 대비 ANN recall·latency·memory |
| OS12 | 후보 누락·fusion·필터·최신성 검증 |
| OS13 | 실제 관측→Lucene/OpenSearch source 경계 |
| OS14 | 실제 사건 2개·복구 후 검색/업무 검산 |

각 증거에는 버전·관측 지점·지표 단위/형식/창·경쟁 가설·회복 기준을 붙입니다. 별도 복제/복원/보안 환경이 필요한 항목은 설계와 실행을 분리합니다. 단일 노드 운영 관문은 실제 baseline 1개와 실제 사건 2개 이상 및 회복 후 업무 검산입니다. 환경 미준비·모형/단위 테스트만 통과한 상태는 운영 미완료입니다. 기존 개별 모듈의 더 엄격한 요구는 그대로 적용합니다.


14모듈 × 2주 × 주 12시간 = 약 336시간입니다. 모듈당 원리·공식 자료 6시간, 실험 10시간, 소스 추적 4시간, 분석·구술 4시간을 기준으로 합니다. Java/Lucene 보충, 별도 cluster·보안 환경 구축, 미통과 실험의 재수행 시간은 추가로 확보합니다.

## 모듈 지도

| 모듈 / 주 | 선수 조건 | 핵심 질문 | 제출·최소 통과 |
| --- | --- | --- | --- |
| OS01 / 1–2 | HTTP·문자열·집합 | [분석·token graph](lessons/01-lucene-schema.md#os01) | char/token/position/offset 원장; term와 match의 반례 |
| OS02 / 3–4 | OS01, 자료구조 | [postings·doc values·BKD·mapping](lessons/01-lucene-schema.md#os02) | field→자료구조→query 계약, object/nested 거짓 일치 반례 |
| OS03 / 5–6 | OS02, OS I/O | [segment·refresh·flush·translog](lessons/02-write-state.md#os03) | ACK·GET·search·fsync·commit 시간선; 가시성과 내구성 분리 |
| OS04 / 7–8 | OS03, transaction | [OCC·bulk·재전송](lessons/02-write-state.md#os04) | stale write 409·부분 성공 원장·업무 version/삭제 불변식 |
| OS05 / 9–10 | OS01–OS04 | [bool·phrase·BM25](lessons/03-query-ranking.md#os05) | 후보 선정과 점수 분리, explain·수식·NULL/미존재 계약 |
| OS06 / 11–12 | OS05, 기초 통계 | [검색 품질·평가 설계](lessons/03-query-ranking.md#os06) | judgment·누수 없는 split·slice별 nDCG/MRR·오답 분류 |
| OS07 / 13–14 | OS05, hashing | [routing·query/fetch·집계·PIT](lessons/04-distributed-search.md#os07) | 후보 누락·shard 통계·terms 오차·pagination 중복/누락 원장 |
| OS08 / 15–16 | OS03–OS04, OS07 | [replication·coordination·recovery](lessons/04-distributed-search.md#os08) | write ACK와 voting quorum 구분·승격/재합류 실패 모델 |
| OS09 / 17–18 | OS07–OS08, JVM | [memory·merge·backpressure](lessons/05-operations-security.md#os09) | heap/native/page cache·queue·I/O 경쟁 가설 및 부하 상한 |
| OS10 / 19–20 | OS04, OS08–OS09 | [권한·lifecycle·snapshot/DR](lessons/05-operations-security.md#os10) | 두 주체 권한 matrix·reindex cutover·독립 복원 검산 |
| OS11 / 21–22 | OS06–OS07, 선형대수 | [exact·ANN·HNSW·filter](lessons/06-vectors-evaluation.md#os11) | 고정 벡터 exact oracle·filtered recall·메모리/지연 frontier |
| OS12 / 23–24 | OS06, OS11 | [hybrid·RRF·RAG 평가](lessons/06-vectors-evaluation.md#os12) | 후보 손실과 fusion 분리·holdout·권한/삭제/RAG 계약 |
| OS13 / 25–26 | OS01–OS12, Java | [소스·논문 반증](lessons/07-research-capstone.md#os13) | 5symbol·2자료구조·1회귀 테스트·논문과 구현 가정 차이 |
| OS14 / 27–28 | OS13 | [2주 최소 연구](lessons/07-research-capstone.md#os14) | 한 검색 경로·두 실패 조건·독립 oracle·한계 보고서 |

## 실험 원칙

[공통 실험 방법](../../databases/shared/experiment-method.md)을 따릅니다. 정확한 합성 fixture로 성공·실패 조건을 먼저 증명하고 규모를 늘립니다. 검색 hit count만으로 판정하지 않고 업무 ID·version·삭제 상태·권한·순위·후보 집합을 기록합니다. ANN recall의 정답은 같은 벡터·거리·필터·tie 규칙의 exhaustive search이고, 사람의 relevance judgment와는 다른 정답입니다.

성능은 같은 결과/품질 계약에서 비교합니다. client end-to-end latency와 서버 `took`, query profile의 계측 시간, indexing ACK latency와 search visibility latency를 섞지 않습니다. cache warm/cold·merge 진행·segment 수·replica·shard 배치·concurrency·오류율을 기록하고 A/B 순서를 섞습니다. p99는 작은 표본의 단일 수치로 확신하지 않고 표본 수·측정 구간·불확실성을 함께 냅니다.

```text
run_id / corpus+query+judgment fingerprints / source commit / OpenSearch+Lucene+plugin versions
index UUID / mapping+analysis+similarity / shard+replica+replication type / routing
write ID+business version / seq_no+primary_term / ACK+visibility times / item status
query DSL / candidate IDs / scores+explain / filter+principal / expected+actual ranking
PIT ID lifetime / sort tuple / timed_out+failed shards / aggregation error fields
heap+native+RSS+page-cache indicators / segment+merge+queue+breaker / concurrency+latency
snapshot ID+shard status / restore target / lost+stale+unauthorized IDs / RTO+RPO
```

로그·profile·query literal·snapshot metadata에는 합성 값만 넣습니다. 실제 토큰·문서 본문·개인정보를 git에 올리지 않습니다. 성능 비교용 raw payload를 공개할 때도 비밀 제거를 별도로 검사합니다.

## Gate와 완료 범위

- G1, OS01–OS04: 실제 analyzer·자료구조·가시성·내구성·write 불변식. 선택 모형을 썼다면 실제 Lucene과 다른 지점을 설명합니다.
- G2, OS05–OS08: 일치·순위·분산 후보·실패 경계. 검색 결과를 정확성, relevance, freshness로 나누고 shard 실패를 숨기지 않습니다.
- G3, OS09–OS12: resource·권한·복구·ANN·hybrid. workload filter를 인증/인가로 오인하거나 replica를 backup으로 오인하면 미통과입니다.
- G4, OS13–OS14: 구현 근거·반증·제한된 연구. 실행하지 않은 보안·분산·ANN·복원을 PASS로 표시하지 않습니다.

[평가표](assessment.md)는 정확성 25, 원리·소스 25, 실험·반증 25, 운영·재현성 25점입니다. 총 80점 이상, 모든 영역 15점 이상, 필수 gate를 함께 충족해야 합니다. 모형만 했다면 원리 학습으로, 실제 기준선·사건·회복 관문을 통과했다면 단일 노드 운영으로 기록합니다. CLUSTER-LAB·SECURITY-LAB·ANN-LAB은 별도 상태로 남깁니다.

매 모듈은 업무 질문 → 불변식·실패 모델 → 입력·기대값 → 실행 범위 → 관찰 → 경쟁 가설 → 소스 근거 → 한계 순으로 제출합니다. HTTP 200·cluster green·높은 nDCG 중 어느 하나도 다른 gate를 대신하지 않습니다.
