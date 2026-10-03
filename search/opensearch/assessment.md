# OpenSearch 심화 과정 평가 기준

## 공통 필수 운영 관문

[운영 runbook](operations.md)의 실제 서버 정상 기준선 1개, 서로 다른 사건 최소 2개, 각 사건의 경쟁 가설 2개 이상·원시 지표/로그·제한된 조치·되돌림/회복 후 업무 검산을 제출합니다. 지표는 gauge/counter/event, 단위·집계 창·reset 여부를 표시합니다. 임계값 암기나 dashboard 화면만으로는 통과하지 않습니다.

원리 모형·손계산·mock/단위 테스트는 선택 보조 증거입니다. 이를 생략했다고 운영 과정 진입을 막지 않으며, 성공했다고 실제 운영 점수를 주지도 않습니다. 기존 점수 기준 및 제품별 정확성·복원·권한 관문은 유지합니다. 환경이 없으면 설계/원리 학습 완료와 운영 미완료를 구별하고, 실제 baseline/사건 증거 없이 전체 운영 완료를 선언하지 않습니다.


[커리큘럼](curriculum.md) · [실습 범위](labs/README.md) · [소스 지도](source-reading.md)

평가의 대상은 DSL 암기량이 아니라 **검색 의미·물리 실행·복구·권한·품질의 경계를 증거로 설명하는 능력**입니다. OFFLINE, LOCAL-ENGINE, CLUSTER-LAB, SECURITY-LAB, ANN-LAB, BUILD를 구별하며 하위 실험의 성공을 상위 환경의 보장으로 확대하지 않습니다.

## 점수와 필수 gate

각 25점, 총 **80/100 이상·모든 영역 15/25 이상**과 필수 gate 전부 통과가 선언한 범위의 완료 기준입니다.

| 영역 | 최소 증거 | 높은 수준의 증거 |
| --- | --- | --- |
| 정확성 25 | token·ID·version·삭제·권한·순위/집계의 독립 oracle | retry·late event·failover·복원 뒤에도 불변식 검사 |
| 원리/소스 25 | analyzer→Lucene→shard→coordinator 경계와 고정 revision | 실제 구현·자료구조·회귀 테스트·논문 가정과 관찰의 일치/차이 |
| 실험/반증 25 | baseline·한 변인·음성 대조군·원시 결과 | candidate와 ranking 원인 분리, slice·반복·불확실성·오답 분석 |
| 운영/재현성 25 | 환경·자원 상한·scope·비밀 제거·미검증 상태 | backlog·권한·snapshot·재처리 원장을 포함한 재현 가능한 복구 |

1. **버전·범위:** 서버·Lucene·plugin·mapping·replication type·shard 배치를 기록합니다. 보안 비활성 단일 노드의 성공을 보안/HA 통과로 부르지 않습니다.
2. **검색 의미:** `term`/`match`, token position, `text`/`keyword`, missing/NULL, object/nested를 구분합니다. 점수가 같다는 사실과 업무 relevance가 같다는 사실을 혼동하지 않습니다.
3. **write·복구:** ACK·search visibility·translog fsync·Lucene commit을 분리합니다. Bulk의 모든 item과 모호한 timeout을 추적하고 재시도로 stale overwrite·삭제 부활을 만들지 않습니다.
4. **분산 결과:** `_shards.failed`, `timed_out`, total-hit relation, bucket 오차와 pagination 누락을 확인합니다. 단순 local top-k 모형의 실패를 모든 실제 query phase의 구조적 부정확성으로 일반화하지 않습니다.
5. **권한:** tenant field의 query filter와 role 기반 인가를 분리합니다. DLS/FLS는 write 권한 제한의 대체물이 아닙니다. 실제 서로 다른 자격 증명, 허용 양성 대조군, 금지 음성 대조군이 없으면 SECURITY-LAB 미검증입니다.
6. **품질:** ANN recall과 relevance를 별도 평가하고 training/tuning/holdout을 분리합니다. filter를 적용한 같은 corpus에서 exact ground truth를 구하며 fusion이 미검색 후보를 복구한다고 주장하지 않습니다.
7. **안전·정직성:** 공유 index·snapshot·volume을 삭제하지 않습니다. 실행하지 않은 엔진·권한·장애·복원을 PASS라고 쓰지 않으며 mock/AST 테스트를 실제 서버 테스트와 구별합니다.

## 최소 결과물

| 범위 | 제출물 | 미검증 경계 |
| --- | --- | --- |
| OFFLINE (선택 보조) | 선택한 모형·반례·단순화 목록·수작업 oracle; 운영 과정 필수 아님 | Lucene scoring, fsync, HNSW, Security plugin |
| LOCAL-ENGINE | 고정 서버·합성 fixture·term/match/phrase·refresh/OCC/bulk 항목 원장 | HA·quorum·실제 authZ·ANN·DR |
| CLUSTER-LAB | 여러 process/node·실패 이력·승격/복제/복구 시점 | 시험하지 않은 AZ·storage·network·managed service |
| SECURITY-LAB | TLS 검증·주체별 권한·read/write 부정 시험 | 정책을 실제 호출로 확인하지 않은 API·복원 후 정책 |
| ANN-LAB | exact oracle·엔진/method·후보수·recall/latency/memory | embedding 자체의 의미 품질·production 트래픽 |
| RESTORE-LAB | 독립 target 복원·업무 ledger·권한·cutover 검산 | 실행하지 않은 region/account·전체 조직 DR |

OS01–04는 분석·저장·write, OS05–08은 query·분산 검색, OS09–12는 운영·보안·복구·vector 품질, OS13–14는 소스 연구와 작은 통합 단면을 평가합니다. 상세 제출물은 각 강의에 따릅니다.

## OS14의 2주 미니 캡스톤

앞선 fixture·코드를 재사용하여 한 경로의 baseline, 변경 하나, 실패 조건 두 개를 검증합니다. 예를 들어 analyzer 변경+동의어 오탐, bulk 재전송+stale version, filtered ANN+후보 부족 중 하나입니다. 실제 cluster·DB·Kafka·embedding 모델·RAG 앱 전체를 새로 구축하는 2주가 아닙니다.

동료가 임의 query 5개와 문서 ID 최대 10개를 골라 일치/제외/정렬/삭제/권한 원인을 추적할 수 있어야 합니다. 잘못된 구현에서 실패하는 테스트와 정상·실패·수정/복구 실행을 함께 냅니다. 설계만 작성한 실패 조건은 실제 실행 gate를 대신하지 않습니다.

큰 통합은 선택 [8주 검색 품질·복구 캡스톤](../../capstones/search-quality-recovery.md)으로 분리합니다. [실험 보고서](../../databases/shared/templates/experiment-report.md)와 [장애 기록](../../databases/shared/templates/incident-review.md)에 corpus/judgment fingerprint, index UUID, principal, query candidate, snapshot/restore 검산 항목을 추가합니다.
