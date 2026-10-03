# MySQL 트랜잭션·재처리·복구 통합 연구 8주

[MySQL 트랙](../databases/mysql/README.md) MY14의 2주 미니 캡스톤 이후 선택하는 별도 8주 연구입니다. 합성 주문/계정 원장을 대상으로 **업무 불변식, 동시 실행, 모호한 commit 결과, 복제 지연, 실제 복원**을 연결합니다. 제공 단일 노드 fixture를 실행하는 것만으로 완료되지 않습니다.

## 범위와 정답 계약

주제는 합성 계정 간 이체와 주문 승인입니다. 실제 결제·금융 계정·개인정보를 사용하지 않습니다. 최소 단위 정수 또는 scale을 고정한 DECIMAL로 금액을 표현하고, currency·업무 operation ID·입력 digest·상태 전이·중복 처리 계약을 정의합니다. root 실습 계정은 운영 application role 모델이 아닙니다.

| 불변식 | 독립 oracle |
| --- | --- |
| 이체 전후 총액이 보존되고 허용되지 않은 잔액이 없음 | ID별 기대 balance와 외부 합성 operation ledger, 총액만으로 끝내지 않기 |
| 같은 operation의 재전송이 두 번 적용되지 않음 | unique key·요청 내용 digest·기존 결과의 일치/충돌 검사 |
| transaction retry가 일부 statement만 중복하지 않음 | 시도별 transaction 경계·오류 번호·commit 결과 원장 |
| replica 읽기가 선언한 freshness 계약을 만족 | source 성공 원장·replica 적용된 GTID 집합·실제 업무 row 비교 |
| 복원이 schema/data만이 아닌 앱 계약을 회복 | ID/version·금액·제약·권한·charset/collation·대표 query·재시도 검사 |

평가에는 정상·실패·미확정 상태가 모두 필요합니다. ACK를 못 받은 요청을 무조건 실패 처리하거나 GTID 숫자가 커졌다는 이유만으로 최신 행을 읽었다고 판단하지 않습니다. 비용/디스크/요청 수·중단 조건을 먼저 정하고, 장애 주입은 소유권이 명확한 scratch 환경에만 수행합니다.

## 1–2주: 모델·원장·isolation

schema와 최소 fixture, 정답 ledger를 코드와 독립적으로 작성합니다. 같은 데이터에서 NULL·중복·outer join·collation에 따른 결과를 검산하고 transaction 경계·session sql_mode·timezone·isolation을 기록합니다. 모든 timestamp를 임의 문자열로 비교하지 않습니다.

RC와 RR에서 첫 consistent read 전후의 사건을 표로 만들고, locking read/DML은 같은 snapshot을 읽는다고 가정하지 않습니다. 업무 불변식을 두 row로 나누었을 때의 write skew와 명시적인 동기화/제약 설계를 비교합니다. [CPU read-view](../databases/mysql/labs/offline.md)는 시작점이고 실제 두 세션 검증은 별도입니다.

## 3–4주: 정상 경로와 plan의 변화

원장 삽입·balance 변경·결과 저장을 하나의 명시적인 transaction에 묶습니다. operation ID가 같지만 입력이 다르면 재전송 성공으로 취급하지 않습니다. deadlock retry는 전체 transaction을 다시 판정하고 시간·시도 상한을 적용합니다. transaction 종료가 모호하면 ledger 조회로 처리 상태를 확인할 수 있어야 합니다.

동일 결과를 반환하는 scan/secondary/covering 설계의 plan·실측 rows/loops·latency를 비교합니다. skew·데이터 증가·히스토그램/통계 갱신·복합 인덱스 순서를 한 번에 하나씩 바꿉니다. CPU 논리 lookup 수를 물리 I/O 또는 처리량으로 보고하지 않습니다. 읽기 개선과 write amplification·공간·DDL/lock 비용을 함께 판단합니다.

## 5–6주: 실패 다섯 가지와 백업 계약

- 두 transaction의 반대 lock 순서로 cycle을 만들고 한 transaction 실패 뒤의 업무 원장을 검산합니다. victim ID는 고정 정답으로 요구하지 않습니다.
- lock wait timeout의 기본 statement rollback과 deadlock의 transaction rollback을 구별합니다. 오류를 잡고 나머지를 commit해 부분 업무 처리가 되는 잘못된 구현을 탐지합니다.
- commit 응답 유실 또는 client 중단을 모호한 상태로 기록하고 같은 operation ID의 재시도를 검증합니다. 단순 process kill을 전원 손실로 부르지 않습니다.
- 오래 열린 read view가 purge/undo 보존에 주는 영향 또는 긴 transaction의 MDL이 DDL을 지연시키는 경우를 자원 상한 안에서 관찰합니다.
- 별도 replica를 구성한 경우에만 lag·applier 오류·failover 후 stale read/중복 쓰기를 검사합니다. GTID 설정만 켠 단일 노드는 replication lab이 아닙니다.

백업은 논리 dump와 물리 backup의 전제·복원 도구·버전·가용 기능을 구분해 하나를 선택합니다. Community에 제공되지 않은 도구나 Enterprise 기능을 기본으로 가정하지 않습니다. `--single-transaction`이 모든 storage engine·동시 DDL·계정·외부 파일까지 자동으로 일관된 백업을 만든다고 주장하지 않습니다. snapshot·binlog 보관과 restore 시 필요한 계정/권한·키·설정을 별도로 보존합니다.

## 7–8주: 독립 복원·PITR·방어

원본과 연결되지 않은 새 target에 복원합니다. binary log를 replay할 경우 backup의 기준 좌표/GTID, 보관 누락, event 순서, 종료 지점, 이미 적용한 transaction의 처리 규칙을 먼저 정합니다. 복구 대상에 임의 GTID를 주입하거나 error skip으로 초록 상태만 만드는 것은 정합성 복구가 아닙니다. live 원본·기존 volume·동일 server UUID를 복사해 바로 운영 topology에 연결하지 않습니다.

RTO는 mysqld 접속 성공이 아니라 앱 권한·제약·금액/ID 원장·대표 query·재시도·writer 재개 검증까지입니다. RPO는 목표와 실측을 분리하고 마지막 확인된 업무 operation과 복원 결과 차이로 설명합니다. replica가 있다고 잘못된 DELETE로부터 보호되는 backup이 생기는 것은 아닙니다.

최종 제출물은 환경 fingerprint, schema/권한·transaction 계약, plan 비교, 다섯 반례, 백업/복원 및 선택 PITR 원장, 소스 trace, 남은 미검증 항목입니다. [평가](../databases/mysql/assessment.md)의 4영역 각 25점·총 80 이상·각 15 이상·선언 범위의 필수 gate를 적용합니다. 실제 복원 없이 연구 전체를 완료했다고 표시하지 않습니다.

선택 확장은 MySQL outbox/CDC → [Kafka](../streaming/kafka/README.md) → [ClickHouse](../databases/clickhouse/README.md) 또는 [OpenSearch](../search/opensearch/README.md) projection입니다. source commit·connector offset·destination 적용은 다른 단계이며, 기본 Compose는 connector나 이 pipeline을 구성하지 않습니다. PostgreSQL과 비교할 때도 isolation 이름만 맞추지 말고 같은 업무 불변식·사건 순서로 비교합니다.
