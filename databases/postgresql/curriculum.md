# PostgreSQL 심화 커리큘럼: 실행 결과에서 구현과 운영 판단까지

## 운영 중심 진행과 모듈별 진단 증거

주 실습은 [실제 제품 운영 runbook](operations.md)의 **정상 기준선 → 지표/로그 → 경쟁 가설 → 제한된 재현 → 조치 → 회복 검산**입니다. 기존 28주·14모듈·336시간과 원리/내부 구현의 깊이는 유지합니다. 모듈당 실험 10시간은 정상 관측 2시간, 사건/반례와 진단 5시간, 조치·회복 검산 3시간을 기본 배분으로 삼습니다. 원리 모형은 필요할 때 선택하는 보조 자료이며 필수 선행 조건이 아닙니다.

| 모듈 | 실제 제품에서 추가로 남길 진단 증거 |
| --- | --- |
| M01 | SQL 정답 원장·서버/데이터 fingerprint |
| M02 | 세션 상태·wait_event·pool/DB 대기 구별 |
| M03 | heap/index/TOAST 크기와 읽기 증폭 |
| M04 | WAL byte/s·I/O·commit 지연의 구간 비교 |
| M05 | 긴 transaction과 snapshot 영향 시간선 |
| M06 | blocking graph·timeout/deadlock·안전한 해제 |
| M07 | 추정/실제 rows 및 통계 변경의 영향 |
| M08 | 접근 경로·buffer·heap fetch·쓰기 비용 |
| M09 | spill/temp byte·worker·memory 경쟁 가설 |
| M10 | vacuum horizon·dead tuple 추정·회복 증거 |
| M11 | 독립 복원과 업무 원장·RPO/RTO |
| M12 | sent/write/flush/replay LSN·slot·읽기 가시성 |
| M13 | 기준선 대비 incident 진단·한정 조치·회복 |
| M14 | 관측→실제 source 경계→재현 가능한 개선 |

각 증거에는 버전·관측 지점·지표 단위/형식/창·경쟁 가설·회복 기준을 붙입니다. 별도 복제/복원/보안 환경이 필요한 항목은 설계와 실행을 분리합니다. 단일 노드 운영 관문은 실제 baseline 1개와 실제 사건 2개 이상 및 회복 후 업무 검산입니다. 환경 미준비·모형/단위 테스트만 통과한 상태는 운영 미완료입니다. 기존 개별 모듈의 더 엄격한 요구는 그대로 적용합니다.


## 진입과 학습 방법

입문자는 M01부터 시작합니다. 필요한 기초는 파일·프로세스·메모리의 구분, 터미널에서 명령 실행, 정수·집합·정렬의 개념입니다. 부족한 영역은 첫 2주에 SQL 실험과 함께 보충합니다. C 포인터·구조체·함수 호출, Git, 디버거는 M14의 선수 지식이며 시작부터 모두 알아야 하지는 않습니다.

경험자는 M01 SQL 반례 3개, M06 두 세션 동시성 실행, M07 실행 계획의 추정 오차 설명을 먼저 제출합니다. 이미 아는 모듈도 증거가 없으면 생략하지 않습니다. 학습 시간은 예산이며 전문성 보장이 아닙니다.

2주 한 모듈의 권장 24시간은 원리·공식 문서 6시간, 실험 10시간, 소스 탐색 4시간, 보고·재현 검토 4시간입니다. 처음 2개 모듈의 소스 시간은 아키텍처 그림과 기본 디버깅 공부로 대체할 수 있습니다. T/B 환경 준비와 예상치 못한 장애는 추가 시간이 필요할 수 있습니다.

매 실험은 `질문 → 사전 예측 → 독립 변수 1개 변경 → 원본 관측 → 반례/교란요인 → 결론 범위`로 진행합니다. 성능 실험의 3회 반복은 예비 조사이며, 최종 비교는 워밍업을 제외한 조건별 20회 이상 측정과 [공통 실험 방법](../shared/experiment-method.md)을 따릅니다. 작은 실행 시간 차이를 개선이라고 단정하지 않습니다. 동시성 실험은 실행 순서를, 성능 실험은 데이터/캐시/설정을, 복구 실험은 타임라인과 검증 원장을 함께 보관합니다.

## 28주 지도와 모듈별 관문

각 강의에는 선수 지식, 원리, 실험, 실패 양상, 산출물, 통과 기준이 들어 있습니다. 아래 기준과 강의의 기준을 모두 충족해야 다음 의존 모듈로 진행합니다.

| 주차·모듈 | 선수 | 학습 범위·실험 | 필수 산출물·측정 가능한 관문 |
| --- | --- | --- | --- |
| 1–2 · M01 | 터미널·기초 집합 | 관계/중복/NULL, 키·함수 종속·3NF, JOIN·윈도 함수, 금액·시간 의미. [강의 1](lessons/01-foundations-and-architecture.md) S | NULL·중복·JOIN fan-out 반례 각 1개와 수정 SQL. 손계산한 5행 데이터와 결과 일치 |
| 3–4 · M02 | M01 | backend/process, simple/extended protocol, parse→rewrite→plan→execute, 세션·pool. [강의 1](lessons/01-foundations-and-architecture.md) S | 요청 경로 그림, 세션 3개 관측표. idle/active/idle-in-transaction을 실제로 구별 |
| 5–6 · M03 | M02, byte·파일 | heap page/line pointer/tuple, TOAST, FSM/VM, 페이지 크기·정렬. [강의 2](lessons/02-storage-buffer-wal.md) S/E | 자기 테이블 페이지 1개의 구조와 ctid 연결, heap/index/TOAST 크기 분리. 확장 미실행은 별도 표시 |
| 7–8 · M04 | M03 | buffer pin/lock/dirty, WAL-before-data, LSN·commit·checkpoint·FPI. [강의 2](lessons/02-storage-buffer-wal.md) S | 변경 전후 LSN·WAL·buffer 로그. rollback과 WAL 증가가 양립하는 이유, durability 경계 설명 |
| 9–10 · M05 | M03–04 | snapshot/xmin/xmax, visibility, RC/RR, 긴 snapshot·horizon. [강의 3](lessons/03-mvcc-ssi-locking.md) S | RC/RR 각각 두 세션 시간표 2회. 트랜잭션 시작과 snapshot 확정 시점 구별 |
| 11–12 · M06 | M05 | write skew·SSI, SIReadLock, row/transaction/DDL lock, deadlock, 재시도. [강의 3](lessons/03-mvcc-ssi-locking.md) S | RR 불변식 위반과 Serializable 실패를 재현. 40001/40P01/55P03 대응 구별 |
| 13–14 · M07 | M01, M05 | selectivity·histogram/MCV/ndistinct, 상관관계·extended stats, cost·plan cache. [강의 4](lessons/04-planner-and-indexes.md) S | 추정/실제 행 오차 표, 통계 전후 동일 쿼리 결과. 추정 개선과 속도 개선을 별도 판정 |
| 15–16 · M08 | M03, M07 | B-tree 구조·split, 복합/부분/covering, VM·index-only, BRIN/GIN/GiST, PG18 skip scan. [강의 4](lessons/04-planner-and-indexes.md) S/E | 3개 접근 경로 비교, index 크기·쓰기 비용 기록. heap fetch가 발생하는 반례 |
| 17–18 · M09 | M04, M07–08 | iterator/executor, NL/hash/merge join, spill·병렬·memory context, PG18 AIO. [강의 5](lessons/05-executor-and-maintenance.md) S | work_mem 2수준×예비 3회, 최종 각 20회 이상. temp/buffer/worker 관측과 동시 실행 메모리 위험 계산 |
| 19–20 · M10 | M03–06, M09 | HOT·pruning·vacuum·freeze·MultiXact, autovacuum horizon, analyze. [강의 5](lessons/05-executor-and-maintenance.md) S/E | 장기 snapshot 유지/해제 전후 vacuum 증거, HOT 조건 반례, XID/테이블 연령 보고 |
| 21–22 · M11 | M04, M10 | 논리/물리 백업, crash recovery, archive·PITR·timeline, RPO/RTO. [강의 6](lessons/06-recovery-and-replication.md) S/T | 격리 DB 논리 복원 비교 필수. 상급 통과는 별도 클러스터 PITR와 실제 RPO/RTO 기록 |
| 23–24 · M12 | M06, M11 | streaming/physical vs logical, flush/replay, slot·retention·CDC, failover·fencing. [강의 6](lessons/06-recovery-and-replication.md) S/T | 토폴로지 설계·장애 매트릭스. 상급 통과는 지연/slot/장애조치/재연결 실제 기록 |
| 25–26 · M13 | M01–12 | SLO·부하·pool·권한·DDL migration·관측·incident triage. [강의 7](lessons/07-production-and-capstone.md) S/T | 장애 3종 진단, 취소/종료/변경 선택 근거, 마이그레이션 전후 불변식과 롤백 기준 |
| 27–28 · M14 | M13, C·Git·debugger | runtime와 소스 연결, 회귀/격리 테스트, 재고·주문 서비스 캡스톤. [강의 7](lessons/07-production-and-capstone.md) S/B/T | 소스 경로 3개 구두 방어, 최소 재현·테스트, 동시성·성능·복원 증거와 동료 재현 |

## 단계별 역량 확인

- **기초 통과(M01–04):** SQL 의미와 물리 저장/내구성을 구분하고 자기 실험의 환경·결과를 재현합니다.
- **내부 동작 통과(M05–10):** snapshot, planner, executor, vacuum의 인과관계를 반례로 설명하고 소스 함수와 관측치를 연결합니다.
- **단일 노드 운영 통과(M11–14의 S):** 동시성 안전한 설계, 논리 복원, 부하·장애 분석을 입증합니다.
- **고급 검증 통과(T/B 포함):** PITR, 복제 장애, 소스 빌드/테스트까지 실제 환경에서 수행하고 타인의 검토를 받습니다. T/B가 설계만 끝났다면 이 단계는 미완료입니다.

## 필수 질문 묶음

1. `SELECT`가 쓰기를 하지 않는다는 말은 어떤 계층에서만 맞는가? hint bit와 buffer dirty를 연결합니다.
2. WAL flush, data page write, checkpoint, COMMIT 응답은 어떤 순서 관계가 필수이고 무엇이 자유로운가?
3. SERIALIZABLE에서 성공한 개별 문장이 있어도 전체 트랜잭션을 다시 해야 하는 이유는 무엇인가?
4. `actual rows`, `loops`, inclusive timing을 어떻게 읽어야 중복 계산하지 않는가?
5. 큰 shared-buffer hit 비율만으로 성능이 좋다고 말할 수 있는가?
6. vacuum이 실행됐는데 파일 크기와 dead tuple 추정치가 기대대로 변하지 않는 이유는 무엇인가?
7. standby에 WAL을 전송했다는 사실이 클라이언트의 read-your-writes를 보장하는가?
8. 백업 파일 checksum 통과와 서비스 복원 성공의 차이는 무엇인가?

답변마다 관측 증거 1개, 반례 1개, [소스 경로](source-reading.md) 1개를 붙입니다. [평가표](assessment.md)의 필수 게이트를 총점으로 대체할 수 없습니다.
