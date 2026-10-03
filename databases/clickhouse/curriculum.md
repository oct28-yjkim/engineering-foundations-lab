# ClickHouse 심화 커리큘럼

## 운영 중심 진행과 모듈별 진단 증거

주 실습은 [실제 제품 운영 runbook](operations.md)의 **정상 기준선 → 지표/로그 → 경쟁 가설 → 제한된 재현 → 조치 → 회복 검산**입니다. 기존 28주·14모듈·336시간과 원리/내부 구현의 깊이는 유지합니다. 모듈당 실험 10시간은 정상 관측 2시간, 사건/반례와 진단 5시간, 조치·회복 검산 3시간을 기본 배분으로 삼습니다. 원리 모형은 필요할 때 선택하는 보조 자료이며 필수 선행 조건이 아닙니다.

| 모듈 | 실제 제품에서 추가로 남길 진단 증거 |
| --- | --- |
| M01 | 정상 query 지연·읽기량·정확성 기준선 |
| M02 | 타입/압축 변경의 read byte·메모리·값 보존 |
| M03 | partition별 active part·mark·읽기량 |
| M04 | pruning 실패·동일 결과의 읽기 증폭 |
| M05 | plan/pipeline과 query log 책임 경계 |
| M06 | thread·memory·동시성·I/O 경쟁 가설 |
| M07 | JOIN fan-out·알고리즘·peak memory |
| M08 | exact/approx 정확성과 집계 메모리 |
| M09 | 작은 insert·part 증가·merge 처리량 |
| M10 | mutation ID·parts_to_do·실패 이유·논리 결과 |
| M11 | MV 지연/중복과 raw/target 검산 |
| M12 | backfill 범위·TTL 지연·보존 상태 |
| M13 | replica queue·Keeper·fetch/merge 원인 구별 |
| M14 | 독립 복원·지표 회복·워크로드/권한 검산 |

각 증거에는 버전·관측 지점·지표 단위/형식/창·경쟁 가설·회복 기준을 붙입니다. 별도 복제/복원/보안 환경이 필요한 항목은 설계와 실행을 분리합니다. 단일 노드 운영 관문은 실제 baseline 1개와 실제 사건 2개 이상 및 회복 후 업무 검산입니다. 환경 미준비·모형/단위 테스트만 통과한 상태는 운영 미완료입니다. 기존 개별 모듈의 더 엄격한 요구는 그대로 적용합니다.


## 도착점과 학습 운영

이 과정은 DB 사용자 → 성능 분석자 → 내부 구조를 읽는 엔지니어 → 실패를 포함해 설계하는 운영자로 진행합니다. 최종 목표는 질문을 들었을 때 설정 이름부터 제시하는 대신, 처리 경로와 실패 경계를 그린 후 재현 가능한 검증을 설계하는 것입니다.

명목상 **28주, 14개 모듈, 주 12시간**입니다. 두 주당 개념·공식 문서 6시간, 실험 10시간, 코드 추적 4시간, 보고서·구술 4시간을 배분합니다. Linux·SQL·C++가 처음이면 별도 보충 시간이 필요합니다. 빠른 학습자는 기존 증거로 통과할 수 있고, 통과하지 못하면 시간을 늘립니다. 낮은 지연 한 번 측정, README 독서 완료, 튜닝 설정 암기는 통과 증거가 아닙니다.

권장 선수 지식은 셸/Docker, SELECT/GROUP BY/JOIN, 이진수·정수·부동소수점, 배열·해시 테이블, 프로세스/스레드/가상 메모리입니다. 모르면 M01에서 보충합니다. SOURCE 단계에는 C++ 클래스·템플릿·RAII·소유권과 동시성 기초를 추가합니다. OS page cache와 DB cache, 디스크 쓰기 완료와 내구성의 차이도 구술 항목입니다.

## 모듈 계획

각 강의에 실제 설명·명령·실험 설계가 있습니다. 아래 표의 산출물은 해당 강의를 수행한 뒤 작성합니다.

| 모듈 / 주 | 선수 조건 | 핵심 질문과 실험 | 제출물 / 통과 조건 |
| --- | --- | --- | --- |
| M01 / 1–2 | 없음; SELECT 보충 | [열 지향·관계 의미·측정](lessons/01-foundations-and-types.md#m01-실행-환경과-비용-모델-local): 읽은 행과 반환 행은 왜 다른가? | 버전 명세, 5개 KPI, 3개 반례; 중복·NULL·순서·빈 날짜 의미를 구별 |
| M02 / 3–4 | M01 | [자료형·압축·CPU](lessons/01-foundations-and-types.md#m02-자료형은-정확성과-비용의-계약-local): 표현을 바꾸면 비용과 의미가 어떻게 변하는가? | 타입별 비교표와 3개 경계값; 값 보존 확인, 저장·읽기·CPU를 분리 |
| M03 / 5–6 | M02 | [part·mark·granule](lessons/02-storage-and-pruning.md#m03-part에서-열을-읽는-경로-local): 인덱스는 무엇을 건너뛰는가? | 1개 part의 읽기 도식, rows/marks 관찰; granule=항상 8192 오답 배제 |
| M04 / 7–8 | M03 | [키·pruning·skip index](lessons/02-storage-and-pruning.md#m04-정렬-키와-읽기-범위-선택-local): 동일 쿼리가 어떤 키에서 덜 읽는가? | 2개 키 × 3개 워크로드의 계획·실측; 동등 결과, 효과 없는 경우 포함 |
| M05 / 9–10 | M04, AST 기초 | [Analyzer와 Planner](lessons/03-query-engine.md#m05-텍스트에서-실행-계획까지-local-source) | 동일 쿼리의 AST/query tree/plan/pipeline 연결; 실제 소스 3곳 추적 |
| M06 / 11–12 | M05, 스레드/메모리 | [Processor와 병렬 실행](lessons/03-query-engine.md#m06-processor-병렬성-메모리와-관측-local-source) | thread 조건 3개 × 5회; 실행 슬롯/CPU 코어 구별, 계측 한계 명시 |
| M07 / 13–14 | M06, 해시 테이블 | [JOIN 정확성과 알고리즘](lessons/04-joins-and-aggregation.md#m07-join은-먼저-관계의-계약이다-local) | 중복·미매칭 fixture, 알고리즘 2개 비교; ALL/ANY/NULL 의미 설명 |
| M08 / 15–16 | M07, 확률 기초 | [집계 상태와 오차](lessons/04-joins-and-aggregation.md#m08-상태-병합과-근사-오차-local-source) | exact 기준선, 10개 독립 데이터 구성, 오차 분포; 함수별 오차 가정 구별 |
| M09 / 17–18 | M03, M06 | [적재와 ack](lessons/05-ingestion-and-correctness.md#m09-삽입-응답부터-병합-부채까지-local) | batch 크기 3개 비교, ack 상태도; 재시도·중복 제거 범위 명시 |
| M10 / 19–20 | M09 | [Replacing·mutation](lessons/05-ingestion-and-correctness.md#m10-replacing-버전과-갱신의-정확성-local) | 역순·동률·삭제 3개 fixture; FINAL 논리 결과와 디스크 상태 구별 |
| M11 / 21–22 | M08, M10 | [MV와 상태](lessons/06-materialization-and-lifecycle.md#m11-삽입-블록과-집계-상태-local) | raw/target 대조, 기존 데이터·추가 insert·수정 반례; exact/approx 구별 |
| M12 / 23–24 | M11 | [backfill·TTL](lessons/06-materialization-and-lifecycle.md#m12-backfill과-수명-주기의-경계-local-ops-design) | 겹침 없는 범위 증명, late event/retry 계획; TTL 지연과 삭제 보장 구별 |
| M13 / 25–26 | M09–M12, 합의 기초 | [shard·replica·Keeper](lessons/07-distributed-and-recovery.md#m13-분산-경계와-합의-cluster-design) | 2 shard × 2 replica + 3 Keeper 명세; 장애 4종의 실제 증거 또는 미실행 표시 |
| M14 / 27–28 | M01–M13 | [복구·SLO·용량·보안](lessons/07-distributed-and-recovery.md#m14-복구와-워크로드-경계-ops-design): 복구한 결과가 맞음을 어떻게 아는가? | 독립 restore·혼합 부하·제한 계정 검증, [종합 평가](assessment.md) 통과 |

## 실험 보고서의 최소 계약

보고서는 별도 개인 실험 디렉터리에 다음 내용을 남깁니다. 이름만 있는 문서를 채점하지 않습니다.

```text
experiment-id, 날짜, 작성자
문제 / 업무상의 정확성·신선도·지연 요구
가설 / 반박되면 바꿀 설계
서버 버전 / 소스 commit / 이미지 digest / CPU·RAM / 저장 장치
데이터 생성식 / 행 수 / distinct 수 / 분포 / skew / part 상태
SQL / 설정 / 동시성 / warm-up / 측정 순서 / query_id
실제 결과와 원시 증거 / 단위 / 오차 / 누락 로그
정확성 대조 / 반례 / 원인 추적 / 선택과 포기한 대안
재현 명령 / 다음 검증 / 종료·복구 상태
```

강의에 나오는 5회 측정은 가설을 탐색하는 pilot입니다. 최종 모듈/프로젝트 성능 결론은 [공통 실험 규칙](../shared/experiment-method.md)에 따라 warm-up 뒤 **조건당 최소 20회** 측정하고 순서를 교차합니다. 중앙값·범위와 `read_rows/read_bytes/memory_usage`를 기록합니다. 5개 또는 20개 표본만으로 안정적인 p99를 주장하지 않습니다. p95/p99는 별도 지속 부하에서 충분한 표본·표본 수·백분위 계산법과 함께 보고합니다. 캐시 삭제·서버 재시작은 별도 변인이므로 단순 비교 도중 섞지 않습니다.

`system.query_log`는 비동기 기록입니다. 실행 직후 기록이 없다고 실행 실패라 판단하지 않습니다. 허용된 환경이면 `SYSTEM FLUSH LOGS`로 기록을 반영하고, 권한이 없으면 기록 주기를 기다린 사실을 적습니다. `query_duration_ms`는 클라이언트 전체 지연을 대신하지 않고, `read_bytes`도 물리 디스크 바이트를 그대로 뜻하지 않습니다. 전역 `system.events` 차이는 다른 세션의 영향을 받으므로 query별 `ProfileEvents`와 구분합니다.

## 단계별 판정

- G1, M01–M04: SQL 의미와 저장 모델. 쿼리 결과 대조에 실패하거나 PK 유일성을 가정하면 재시험.
- G2, M05–M08: 계획·실행·오차. 설명한 처리 경로와 실제 plan/코드가 불일치하면 원인을 해결한 뒤 통과.
- G3, M09–M12: 적재·갱신·사전 집계. backfill 중복, 버전 역전, tombstone 처리의 반례를 모두 설명.
- G4, M13–M14: 분산·운영. 설계 리뷰와 실제 실행을 분리해 기록. 복구 증거 없는 RPO/RTO 달성 주장은 불합격.

출석이나 분량으로 부족한 증거를 대체하지 않습니다. 상세 채점은 [assessment.md](assessment.md)를 사용합니다.
