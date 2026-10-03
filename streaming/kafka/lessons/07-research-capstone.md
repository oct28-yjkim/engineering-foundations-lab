# K13–K14. 내부 구현 연구와 최소 시스템의 설계 방어

[커리큘럼](../curriculum.md) · 이전: [Streams와 Connect](06-streams-connect.md) · [평가](../assessment.md)

## K13 현상에서 내부 구현까지 BUILD

**선수 조건:** K01–K12의 실행 가능한 범위를 완료하고 남은 미검증 항목을 표시한 상태. Java/Scala, lock·event loop·buffer lifecycle·test fixture를 읽을 수 있어야 합니다.

### 연구 방법

최상위 숙련도의 목표는 source 파일을 많이 읽은 사람이 아니라 **새 현상을 줄여 재현하고 보장·구현·측정의 불일치를 설명하는 사람**입니다. 문서 문장을 먼저 결론으로 정해 로그를 끼워 맞추지 않습니다. 사용 runtime과 client·broker source tag/commit·feature level을 맞추고, 어느 경로가 실제 선택되는지 확인합니다. [고정 버전 소스 지도](../source-reading.md)를 탐색 출발점으로 사용합니다.

먼저 한 현상을 선택합니다. 예를 들어 “read_committed lag는 있는데 output이 멈춘다”, “rejoin 때 중복 효과가 발생한다”, “batch 크기를 늘려도 네트워크 요청이 줄지 않는다”, “controller 복구 후에도 topic 변경이 실패한다” 중 하나입니다. producer·topic·payload·partition·client 수를 줄이고 현상을 유지하는 최소 조건을 찾습니다. 이 단계에서 문제가 사라지는 조건도 중요한 결과입니다.

세 층의 설명을 분리합니다. API의 보장은 모든 지원 조건에 대한 계약이고, source 한 경로는 특정 버전의 구현이며, 실행 trace는 그 실험이 지나간 경로의 표본입니다. 스택에서 못 봤다고 호출이 불가능하다는 뜻은 아니고, 코드에 분기가 있다고 현재 설정에서 반드시 실행되는 것도 아닙니다. 오류 경로와 정상 경로를 둘 다 읽습니다.

### 구현 과제 중 하나 선택

| 과제 | 구현 범위 | 독립 oracle과 통과 기준 |
| --- | --- | --- |
| teaching log | append·logical offset·sparse index·segment roll | 임의 입력 1,000개에서 순차 scan과 indexed seek 결과 일치; offset/byte 구별 |
| commit frontier | partition별 비동기 완료 집합과 next-offset 계산 | 완료 순서를 permutation해도 미완료 record를 넘겨 commit하지 않음 |
| visibility model | HW·열린 transaction·abort를 반영하는 단순 모델 | hand-calculated history와 reader의 visible ID 집합 일치 |
| Kafka regression test | 실제 4.3.1 경로에 대한 최소 입력 | 테스트가 겨냥한 불변식·전제·실패 조건을 명시; 관계없는 sleep 의존 제거 |

teaching 구현은 운영용 Kafka 대체물이 아닙니다. checksum·crash consistency·fsync·replication·format compatibility·security를 생략했다면 그 범위를 쓰고, 모델을 단순화한 이유를 설명합니다. 버그가 아닌 명세상 동작을 bugfix로 포장하지 않습니다. 실제 patch를 선택한다면 수정 전 실패/후 성공, 관련 회귀 테스트, 동시성·성능 영향까지 검증합니다. upstream 공개나 PR 생성은 이 과제의 필수 결과물이 아닙니다.

teaching 구현을 선택해도 고급 G13 관문에는 [소스 지도](../source-reading.md)의 Kafka baseline 빌드/테스트와 최소 한 경로의 debugger 또는 계측 테스트 증거가 필요합니다. 모형의 테스트 통과를 실제 Kafka source 실행 검증으로 대체하지 않습니다. 정상·retry·fatal/fencing의 세 경로를 설명하고, 선택한 실제 경로를 최소 입력으로 실행합니다.

### trace 제출 형식

```text
현상 / 반증할 두 가설:
broker version / client version / source commit / feature level:
최소 입력과 실행 순서:
진입 API -> symbol 1 -> 자료구조 -> symbol 2 -> 상태 전이 -> 관측값
필요한 lock/event-loop/ownership/lifecycle:
정상 경로 / retry 경로 / fatal 또는 fencing 경로:
고정된 oracle / 실제 결과 / 아직 확인하지 못한 호출:
독립 반복·회귀 테스트 / 비용 변화 / 원복 상태:
```

필수 범위는 실제 symbol 5개 이상, 자료구조 2개 이상, 오류/재시도 경계 1개 이상, 동기화 또는 소유권 경계 1개 이상입니다. 소스의 줄 번호만 복사하지 말고 commit permalink와 문맥을 함께 남깁니다. heap dump·packet capture에 사용자 payload/secret이 들어갈 수 있으므로 합성 데이터만 사용하는 연구 환경에서 필요한 필드만 보존합니다.

### 반증 실험

예를 들어 open transaction 가설을 택했다면 transaction을 닫는 변인과 consumer 처리 속도 변인을 분리합니다. LSO가 움직여도 handler가 멈출 수 있고, handler가 빨라도 LSO가 막히면 visible output이 없을 수 있습니다. 두 조건을 만들고 서로 다른 metrics/원장으로 구분해야 합니다. test timeout을 무한히 늘려 가설을 참으로 만들지 않습니다.

**기대 증거:** 최소 재현, 실행 당시 설정·로그, source trace, 독립 oracle, 실패했던 입력 또는 반례, 수정/설계 선택 근거. build를 못 했다면 정적 trace와 runtime 검증 완료를 따로 표시합니다.

**실패 모드:** master source를 4.3.1 구현으로 간주, source 파일명만 나열, 디버그 build와 릴리스 build 시간 비교, 긴 sleep으로 race를 숨김, 테스트가 구현과 같은 오류를 공유, 알려진 사실을 새 발견이라고 서술.

**제출·통과:** 다른 사람이 같은 manifest로 현상과 oracle을 재현해야 합니다. 어떤 API 보장을 확인했는지와 어떤 부분이 구현상 관찰에 한정되는지 10분 안에 구별합니다.

## K14 최소 시스템과 통합 설계 BUILD INTEGRATION-DESIGN

**선수 조건:** K13. PostgreSQL·ClickHouse를 먼저 배우지 않아도 Kafka 최소 시스템으로 실행 과제를 수행할 수 있습니다. 두 DB를 연결한 완전한 운영 검증은 [공통 8주 통합 연구](../../../databases/shared/capstone.md)의 후속 범위입니다.

### 2주 실행 범위

K08에서 만든 consume-transform-produce를 작은 서비스로 정리합니다. input topic → validation/transform → output topic의 흐름에 producer 원장, consumer group offsets, read_committed 결과 검증기를 붙입니다. 별도 완성 애플리케이션은 제공되지 않으며 앞 모듈의 구현과 실행 증거를 재사용합니다.

입력은 stable event_id 10,000개와 source_version·business_key·정수 cents를 포함합니다. 변환은 `output.cents = input.cents * 2`처럼 독립적으로 계산 가능한 것으로 시작하고, overflow를 막을 입력 범위를 정합니다. “최신 상태”와 “모든 이벤트 합”은 다른 산출물이므로 이번 실험의 지표를 고정합니다. malformed 입력은 오류로 분류하되 조용히 사라지지 않도록 ID·사유를 추적합니다.

1주차에는 정상 실행·oracle·source trace를 완성합니다. 2주차에는 **실패 2종**을 수행합니다. 첫째, output을 쓰고 transaction commit하기 전 중단하여 abort/replay 후 visible 결과를 확인합니다. 둘째, transaction commit 후 앱의 로컬 확인 원장을 기록하기 전에 중단하여 재시작 판단과 committed offsets를 확인합니다. 두 번째는 “앱 확인 기록 유실” 실험이며 network ACK 유실을 직접 주입한 것이라고 이름붙이지 않습니다.

독립 reader의 read_committed output multiset과 입력의 기대 output multiset이 일치해야 합니다. raw read_uncommitted output에서 abort된 record가 더 보일 수 있는 이유도 설명합니다. partition별 next-offset·transactional.id·restart 정책·관찰 제한 시간을 보존합니다. RF1 실험의 결과는 프로세스 복구·전달 의미 범위이며 broker/node 장애 내성은 K04/K09의 별도 증거가 필요합니다.

### PG → Kafka → ClickHouse 설계 리뷰

다음 설계는 실제 배포가 아니라 후속 구축을 위한 계약입니다. 이미 해당 DB 트랙을 수행했다면 기존 스키마·실험을 참고하고, 그렇지 않으면 각 시스템의 책임과 불변식을 정의하는 데 집중합니다.

```text
PostgreSQL 업무 transaction + outbox 또는 logical decoding
    -> source position / stable event_id / schema version
    -> Kafka partitioned history + Kafka 처리/offset 상태
    -> ClickHouse raw event / latest state / 검증된 분석 집계
    -> 독립 원장 대조와 재처리/복구 경로
```

반드시 답할 질문은 여섯 가지입니다.

1. 업무 변경과 발행할 이벤트가 원본에서 어느 transaction으로 묶이는가?
2. source version과 event_time이 다를 때 어떤 순서로 최신 상태를 판단하는가?
3. snapshot과 변경 stream, backfill과 live traffic은 어떤 경계로 중복·누락을 막는가?
4. Kafka output/offset commit과 ClickHouse 반영 사이의 crash를 어떻게 탐지·복구하는가?
5. 주문 취소·부분환불·삭제의 의미를 raw/latest/aggregate에 어떻게 반영하는가?
6. retention·dedup·tombstone·WAL 보관 기간 밖에서 복구해야 하면 어떤 원본을 사용하는가?

K12의 다섯 CDC 실험을 후속 계획으로 연결하고, 각 실험의 input·주입 지점·oracle·중단 조건·원복 절차를 명시합니다. 이 단계에서 실제 connector나 두 DB를 구축하지 않았으면 “통합 설계 검토 완료”라고 기록합니다. Kafka 내부 transaction을 PG/CH의 전역 transaction이라고 표현하지 않습니다.

### 최종 제출과 구술

- Kafka 최소 시스템의 코드·버전·설정·실행 지침과 10,000개 oracle.
- 두 실패의 실제 timeline, source trace, callback/commit/visible output의 차이.
- 처리량·지연·자원 예산의 측정 결과 또는 미측정 범위. 최종 성능 비교는 조건당 20개 이상 구간과 충분한 요청 표본을 사용합니다.
- PG→Kafka→CH 계약·위험·대안·후속 8주 실험 계획.
- 아직 구현하지 않은 client/cluster/security/CDC/restore 항목.

90분 구술은 흐름과 보장 20분, 리뷰어가 고른 장애 30분, 소스 추적 20분, 예상과 다른 결과 20분으로 진행합니다. 리뷰어가 “consumer는 처리했는데 lag가 0이 아니다”, “ACK가 없는데 데이터가 있다”, “복구한 topic offset이 다르다” 등의 입력을 바꾸었을 때 어떤 증거가 필요한지 답합니다.

**필수 gate:** 정상 및 두 실패의 Kafka output oracle, 실제 source trace, 실행하지 않은 통합 과제를 명확히 표시한 설계. 상세 점수는 [assessment.md](../assessment.md)를 따릅니다. 전체 통합의 5종 장애·독립 복구·RPO/RTO 실측은 후속 8주 과정에서 수행하며 이 2주 리뷰로 대체하지 않습니다.
