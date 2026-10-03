# 검색 품질·권한·복구 통합 연구 8주

[OpenSearch](../search/opensearch/README.md) OS14의 2주 미니 캡스톤 이후 선택하는 별도 8주 연구입니다. 검색 결과가 나오는 데서 끝내지 않고 **검색 품질, 변경의 가시성, 접근 권한, 장애 이후의 결과**를 함께 방어합니다. 모든 제품 연결을 필수로 요구하지 않습니다.

## 계약과 범위

기본 주제는 합성 다중 tenant 기술 문서 검색입니다. 원본 corpus·문서 ID·version·delete 원장, query/qrels, index mapping·analyzer·권한 정책을 별개로 버전 관리합니다. 실제 인가 검증은 보안을 활성화한 별도 환경에서만 수행합니다. 제공된 security-disabled Compose를 그대로 인가 실험에 사용하면 통과할 수 없습니다.

| 불변식 | 독립 검증 자료 |
| --- | --- |
| 검색 가능한 문서가 원본의 허용된 projection과 일치 | 원본 ID/version/delete 원장과 전수/분할 해시 비교 |
| 허용되지 않은 문서는 hit·snippet·count·aggregation·vector 후보에 노출되지 않음 | 역할별 양성/음성 oracle, direct API·alternate query 경로 |
| relevance 변화가 평가 누수로 설명되지 않음 | 고정 train/dev/test 질의·qrels, tenant별/빈도별 지표와 실패 사례 |
| freshness와 latency를 섞지 않음 | 쓰기 완료→최초 검색 가시성, query p50/p95/p99 각각 측정 |
| 복원이 데이터 파일 존재만으로 끝나지 않음 | 문서·mapping·analyzer·alias·권한·검색 품질·pipeline 재개 검사 |

본래 없는 보안·HA·RTO 숫자를 추정치로 통과시키지 않습니다. 환경·리소스·snapshot 저장소·비용 상한과 파괴 실험의 대상을 먼저 승인하고, 본인 소유 sandbox에 합성 데이터만 사용합니다.

## 1–2주: 원본과 평가 집합

최소 100개 문서·20개 질의·2개 tenant로 시작합니다. 학습 규모의 출발점이지 통계적 충분성의 보장은 아닙니다. term miss, phrase, 동의어, 희귀어, 빈 검색 결과, 삭제, 동명이의어, tenant별 표현 차이를 포함합니다. qrels를 순위 변경 뒤 맞춰 수정하지 않습니다. 후보 recall, nDCG@k/MRR의 해당 용도, 지연·freshness·인가 오류를 서로 다른 지표로 고정합니다.

query 파라미터의 tenant filter와 인증 주체에서 강제되는 접근 정책을 비교합니다. 권한이 없는 문서를 intentionally relevant로 둔 질의를 포함해 전체 corpus 품질과 사용자에게 허용된 corpus 품질을 구분합니다. RAG 확장에서는 retrieval qrels와 답변의 근거 충실성·정확성을 따로 평가합니다.

## 3–4주: 설명 가능한 baseline과 변경 1개

BM25 baseline의 tokenizer·mapping·stopword·similarity·refresh 설정을 기록합니다. 문제 질의에 대해 token→postings→scoring→collector→merge 경로를 [소스 지도](../search/opensearch/source-reading.md)로 설명합니다. relevance 개선 변경은 한 번에 하나만 적용하고 dev 질의에서 선택한 뒤 test에 고정합니다.

벡터/하이브리드는 선택 확장입니다. 동일 embedding·distance·filtered candidate set의 exact top-k를 정답으로 두고 ANN recall/latency/memory, RRF candidate depth와 query별 failure를 기록합니다. 작은 CPU rank-fusion 계산을 실제 HNSW 속도·운영 품질 결과로 대체하지 않습니다. 모델 다운로드·GPU/API·외부 문서 전송은 기본 범위가 아닙니다.

## 5–6주: 최소 다섯 반례와 재처리

- bulk 일부 item 실패 후 전체 batch 재시도: ID/version·중복·삭제 정책 검증.
- 색인 완료와 refresh 사이: realtime GET과 search가 다른 구간의 관측.
- 후보 절단 뒤 filter: 허용 문서가 존재해도 top-k가 비는 반례.
- shard별 terms 후보 누락: 문서 top-k의 충분조건을 bucket에 잘못 적용한 반례.
- mapping/analyzer 변경으로 기존 문서와 새 문서의 의미가 달라지는 경우: 새 index·reindex·alias 전환과 원복 계획.
- 권한 없는 직접 API, 다른 aggregation 경로 또는 설명/관측 출력으로 문서가 새는 경우.
- 별도 다중 노드 환경을 선택한 경우에만 primary 중단·replica lag·재선출·재할당.

각 반례에 초기 상태·실패 주입 대상·기대/실측·원인·재처리 전후 oracle을 남깁니다. 교육용 기본 index를 삭제하거나 host를 중단하는 파괴 실험을 자동 실행하지 않습니다. replica가 없는 단일 노드를 HA 결과로 제출하지 않습니다.

## 7–8주: 복원과 연구 방어

합성 writer를 quiesce하고 확인된 원장 경계를 남긴 뒤 snapshot/restore 또는 원본 재구축의 실제 경로를 수행합니다. live snapshot은 모든 shard가 같은 전역 시점이라는 보장이 아니므로, 선택한 일관성 계약과 원장 reconciliation을 설명합니다. 별도 새 대상으로 복원하고 시스템 index·보안 설정·plugin/버전 호환성은 복원 범위에 포함되는지 따로 확인합니다.

RTO는 HTTP 응답이 살아나는 순간이 아니라 역할별 접근·정답 집합·검색 품질·freshness·writer 재개 검증까지의 시간입니다. RPO는 문서/변경 원장으로 계산하고 snapshot 생성 시간만으로 주장하지 않습니다. 복제는 잘못된 삭제를 막는 backup이 아닙니다.

제출물은 실행 fingerprint, corpus/qrels 계약, relevance 표와 실패 사례, 다섯 반례, 권한 음성 검증, 복원 보고서, 소스 trace, 미검증 범위입니다. [평가](../search/opensearch/assessment.md)의 정확성·원리/소스·실험/반증·운영/재현성 각 25점, 총 80 이상·각 15 이상과 선언한 범위의 필수 gate를 적용합니다. 단일 모형만 제출하면 연구 완료가 아닌 CPU 단계 완료입니다.

선택 연계는 [PostgreSQL](../databases/postgresql/README.md) 원본 → [Kafka](../streaming/kafka/README.md) 변경 log → OpenSearch projection, [LLM](../ai/llm-paper-lab/README.md) retrieval 평가입니다. connector·CDC 삭제 처리·권한 전달·dead letter·replay 구현은 이 연구의 추가 과제이며 기본 Compose로 만들어지지 않습니다.
