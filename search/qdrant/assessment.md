# Qdrant 평가 — 구현 범위와 운영 증거를 함께 평가하기

[과정](curriculum.md) · [기능 지도](feature-map.md) · [검증 이력](labs/validation.md)

총 **80/100 이상, 모든 영역 15/25 이상**, 선언한 범위의 필수 gate를 함께 만족해야 완료입니다. 모든 고급 기능을 운영에 채택할 필요는 없지만 목적/동작/관측/제약/비채택 이유는 설명해야 합니다. 문서 읽기와 코드 제공을 실제 서버 검증으로 점수화하지 않습니다.

| 영역 | 25점의 최소 증거 | 심화 증거 |
| --- | --- | --- |
| 정확성 | point ID·vector name·distance·filter·score tolerance·삭제 정답 | replay·migration·복원 뒤에도 tenant/업무 revision/후보 불변식 유지 |
| 원리·소스 | query→index/segment→shard와 고정 소스 연결 | 분기·자료구조·회귀 테스트가 관측을 설명하거나 반박 |
| 실험·반증 | 정상/오류/회복, 독립 oracle, 한 변인 비교 | ANN와 relevance 분리, holdout·반복·불확실성·실패 slice |
| 운영·재현성 | 환경/자원 상한·로그/지표 의미·미실행 경계 | snapshot·권한·복제·재시도 원장, 잔존 상태까지 검산 |

## 기본 LAB gate

1. schema와 작은 합성 데이터로 정상 upsert/retrieve/query의 **ID와 값**을 확인합니다. HTTP 200이나 count만으로 통과하지 않습니다.
2. 잘못된 dimension/vector name, payload 타입 오해처럼 원인이 다른 사건 두 개를 재현합니다. 오류 status/diagnostic과 오답 0건을 구별하고 정상으로 회복합니다.
3. 변경/삭제 후 기대 결과와 원상 회복을 검산합니다. 응답이 모호하면 미확정으로 표시하고 무제한 재전송하지 않습니다.
4. `/metrics`, collection info, 실제 로그 중 어느 증거로 가설을 구분했는지 설명합니다. 도구가 내준 PASS 문구가 설명을 대신하지 않습니다.
5. 작은 데이터에서는 HNSW를 구축/사용했는지 입증하지 못하며 filter는 인증 경계가 아니라는 한계를 답합니다.

## 별도 gate

| 범위 | 통과 조건 | 기본 runner가 대신하지 못하는 것 |
| --- | --- | --- |
| FEATURE | [수동 고급 절차](labs/advanced.md)의 nested/multivector/alias/strict mode의 예상·반례·회복 | 기능별 설정 존재만 확인하고 동작 완료 주장 |
| ANN | 같은 corpus/distance/filter의 exact oracle, index 완료 증거, recall/latency/memory 비교 | 작은 점 몇 개의 exact 결과를 HNSW 성능으로 부르기 |
| RESTORE | 새 target에서 snapshot 복원 후 IDs·payload·vector schema·검색 정답 확인 | snapshot 파일 생성 성공만으로 DR 완료 주장 |
| SECURITY | 서로 다른 주체의 허용·거부, TLS 검증, 읽기/쓰기/관리 경계 | tenant filter를 뺀 client를 차단하지 못하는 검증 |
| CLUSTER | replica/metadata 상태·실패 시점·write/read 결과·복구 후 ledger | 같은 host 3프로세스를 AZ 장애 내성으로 일반화 |
| CLOUD | 승인된 서비스·권한·기능·비용 상한의 실제 증거 | self-host 소스에 코드가 있다는 이유로 관리 기능 지원 단정 |

미실행 범위는 미완료이고, 환경 없음은 실패와 별개입니다. 모의 HTTP 테스트/문서 검사/소스 경로 확인은 각각 그 범위의 증거로만 기록합니다.

## 구술과 결과물

- query 5개를 골라 제외/포함 ID, branch별 후보, score, final rank를 추적합니다. 정답 후보가 prefetch에서 빠진 경우 reranker 탓으로 돌리지 않습니다.
- 상태 변화 원장에는 `known success / known failure / not attempted / uncertain`을 구별합니다. timeout을 자동 failure로 치환하면 재학습합니다.
- memory/quantization/ordering/consistency 중 두 기능을 **쓰지 않기로 한 결정**을 제출합니다. 비용과 정확성 요구, 대안, 재검토 조건이 있어야 합니다.
- [실험 보고서](../../databases/shared/templates/experiment-report.md)와 [사건 보고서](../../operations/incident-report-template.md)에 query/corpus fingerprint·collection/schema·실행 버전·원시 결과·제한 조치·회복 정답·미검증 항목을 첨부합니다. 실사용 문서·token·snapshot 원문은 올리지 않습니다.

QD14는 기존 환경의 한 검색 경로를 대상으로 한 변경과 두 실패를 검증하는 2주 연구입니다. 임베딩 모델 학습·다중 region·전체 RAG 서비스를 한꺼번에 새로 만들지 않습니다. 성능 개선이 tenant 누출이나 삭제 부활을 동반하면 점수와 관계없이 미통과입니다.
