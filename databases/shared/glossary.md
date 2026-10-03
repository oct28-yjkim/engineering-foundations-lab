# 처음 만나는 내부 구조 용어

정의만 암기하지 말고 해당 용어를 관찰할 수 있는 SQL·plan·코드 위치를 옆에 기록합니다.

| 용어 | 이 과정에서의 뜻 | 자주 혼동하는 것 |
| --- | --- | --- |
| invariant / 불변식 | 허용된 모든 상태에서 유지돼야 하는 조건 | 평소에 대체로 맞는 통계 |
| oracle | 결과가 맞는지 독립적으로 판단할 기준 | 최적화한 쿼리 자체의 복사본 |
| cardinality | 문맥에 따른 행 수 또는 distinct 값 수 | 두 의미를 설명 없이 섞기 |
| selectivity | 조건을 만족하는 데이터의 비율 | 값의 고유 개수와 동일시 |
| skew / 편향 | 일부 값·사용자·시간에 데이터나 부하가 집중됨 | 평균 분포만으로 설명하기 |
| grain | 결과 한 행이 나타내는 업무 단위 | JOIN 뒤에도 원본 grain이 유지된다는 가정 |
| snapshot | 어떤 변경을 볼 수 있는지 정하는 읽기 기준 | 무조건 물리 파일 복사 |
| MVCC | 여러 행 버전과 가시성 판단으로 동시성을 처리하는 방식 | 모든 읽기/쓰기가 절대 대기하지 않음 |
| page | PostgreSQL 저장의 기본 블록 단위 | CH granule과 같은 구조 |
| tuple / TID | 행 버전 / heap page 안의 위치를 가리키는 식별자 | 영구 업무 ID |
| buffer pin / lock | buffer 수명 사용 표시 / 접근 동기화 | 서로 같은 보호 수단 |
| WAL / LSN | 복구용 로그 / 로그 위치 | 모든 설정에서 응답=모든 replica 반영 |
| checkpoint | crash recovery의 시작 범위를 제한하는 절차 | backup 그 자체 |
| visibility map | page의 all-visible/all-frozen 상태를 추적하는 구조 | 모든 tuple을 직접 저장하는 index |
| HOT | 조건을 만족할 때 index 갱신 부담을 줄이는 heap update | 모든 UPDATE에 자동 적용 |
| SSI | snapshot isolation 위에서 직렬화 이상을 막는 기법 | predicate lock으로 모든 충돌을 대기시키기 |
| part | ClickHouse가 관리하는 데이터 조각 | SQL PARTITION 하나와 일대일 관계 |
| mark / granule | 읽기 위치 정보 / 인덱스 판단·읽기 범위의 행 묶음 | 언제나 정확히 8192행 |
| pruning | 결과에 필요 없는 읽기 범위를 제외하기 | 이미 읽은 행을 filter하는 것 |
| vectorized execution | 여러 값을 block/열 단위로 처리하는 방식 | 모든 연산이 반드시 SIMD 명령 사용 |
| aggregate state | 부분 집계를 나중에 합칠 수 있는 중간 표현 | 완성된 평균·distinct 수를 단순 합산 |
| backfill | 과거 데이터를 새 모델/집계로 채우는 작업 | 실시간 입력과 자동으로 겹치지 않음 |
| tombstone | 삭제를 나타내는 기록 | 모든 과거 버전이 즉시 물리 삭제됨 |
| shard / replica | 데이터 분할 / 같은 데이터의 복사본 역할 | shard를 늘리면 자동 장애 복구 |
| quorum | 지정된 참여자 수/다수의 확인 조건 | 어떤 시스템이든 같은 강도의 일관성 |
| idempotency | 같은 논리 요청을 반복해도 지정한 효과가 한 번과 같음 | 요청 ID만 있으면 자동 보장 |
| RPO / RTO | 허용 손실 구간 / 복구 소요시간 목표 | backup 명령의 실행 시간 |
| SLO | 사용자 관점에서 수치화한 서비스 목표 | 내부 CPU 사용량 한 개 |
| source trace | 입력부터 함수·상태 변경·관측까지 코드로 연결 | 파일 이름 나열 |

## Kafka를 연결할 때 추가할 용어

| 용어 | 이 과정에서의 뜻 | 자주 혼동하는 것 |
| --- | --- | --- |
| partition / offset | topic의 순서 있는 로그 단위 / 그 안의 기록 위치 | 전체 topic의 전역 순서·업무 event ID |
| record batch / segment | 전송·저장의 기록 묶음 / partition log의 파일 단위 | 한 batch가 반드시 한 segment 전체 |
| LEO | 해당 replica log 끝의 다음 offset | 모든 replica가 확인한 위치 |
| HW | 복제 관점에서 읽을 수 있는 경계(high watermark) | 외부 시스템이 처리 완료한 위치 |
| LSO | transaction이 안정된 읽기 경계(last stable offset) | log start offset; 같은 약어를 구분할 것 |
| committed consumer offset | group이 저장한 재개 위치, 통상 안전하게 처리한 다음 offset | broker에 기록된 끝·외부 sink 반영 증명 |
| ISR | leader와 동기 상태로 관리되는 replica 집합 | 모든 설정된 replica 또는 KRaft voter |
| KRaft quorum | metadata log의 합의에 참여하는 controller 집합 | 데이터 topic의 ISR |
| fencing | epoch/identity 등으로 낡은 소유자의 작업을 거부하는 보호 | 이미 발생한 외부 부작용까지 자동 취소 |
| compaction | key별 상태 복원에 필요한 기록을 남기도록 과거 기록을 정리 | 읽는 순간 한 key 한 행·시간 보존 백업 |
| consumer rebalance | group 내 partition 담당을 바꾸는 과정 | topic partition 개수 변경 |
| changelog / repartition | state 복구용 기록 / 다음 연산의 key 배치를 위한 중간 topic | 원본 topic과 언제나 같은 수명·보존 계약 |

경계 offset에서 실제로 반환되는 기록은 transaction 상태, control record, compaction 등의 영향을 받습니다. offset 차이를 항상 업무 행 수로 해석하지 않습니다. 예제와 보장 범위는 [Kafka 강의](../../streaming/kafka/README.md)와 [공식 설계](https://kafka.apache.org/43/design/design/)를 함께 봅니다.
