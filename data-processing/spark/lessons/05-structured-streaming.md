# 강의 5 — 시간·state·재처리의 계약

기준 Spark 4.0.4, 기본은 Structured Streaming micro-batch입니다. DStreams나 continuous processing으로 보장을 옮겨 쓰지 않습니다. [제공 streaming 과제](../labs/README.md)는 작은 파일 source·sink·checkpoint 실습이며 이 강의의 event-time 집계·외부 sink·장애 주입은 추가 구현입니다.

<a id="sp09"></a>
## SP09 — watermark는 현재 시각도, 모든 늦은 데이터의 삭제 규칙도 아니다

### 원리

event time, source 도착 순서, processing time, trigger 실행 시각을 별도 기록합니다. watermark는 관측된 event-time 진행과 지연 허용을 이용하는 state 관리 경계입니다. 지연 임계값보다 덜 늦은 데이터가 누락되지 않는다는 보장은 단방향이며, 더 늦은 데이터가 **반드시 모두 삭제된다**는 보장은 아닙니다. 정리 시점·operator·output mode·batch 경계도 결과에 영향을 줍니다. [공식 watermark·state 설명](https://spark.apache.org/docs/4.0.4/streaming/apis-on-dataframes-and-datasets.html).

아래는 원리를 계산하기 위한 모형입니다. 실제 Spark 구현의 단계 순서 전체를 모사하지 않습니다.

```text
관측 최대 event time = M, 지연 허용 = Δ, 설명용 경계 W = M - Δ
window [start,end)의 완료 후보: end가 정리 경계를 지남
```

timestamp가 미래로 잘못 찍힌 한 이벤트가 진행도를 왜곡할 수 있습니다. clock skew·시간 단위 오류는 성능 문제가 아니라 정확성 계약 문제입니다.

### 독립 기대값 fixture

UTC 10분 tumbling window에 이벤트를 배치합니다.

```text
e1 00:01 amount=10
e2 00:07 amount=20
e3 00:12 amount=30
e4 00:04 amount=40  (도착만 늦음)
```

모두 포함하는 bounded batch의 기대값은 `[00:00,00:10)=70`, `[00:10,00:20)=30`입니다. 이것은 스트리밍 lateness 정책이 적용된 결과와 자동으로 같은 oracle이 아닙니다. stream oracle은 각 도착 batch와 정책상 보장되는 포함/허용되는 누락 범위를 별도로 가집니다.

### 추가 구현 실험

1. 모든 이벤트가 지연 허용 안에 들어오도록 배치하고 batch oracle과 비교합니다. watermark를 충분히 진행시키는 별도 synthetic 이벤트는 별도 key로 두고 출력 검증에서 명시적으로 분리합니다.
2. e4가 충분히 늦게 도착하도록 batch 순서를 바꾸고 `lastProgress`의 eventTime·watermark·state rows·dropped rows 지표를 기록합니다. 매우 늦은 e4의 포함 여부는 실측하고 무조건 drop이라는 assertion은 하지 않습니다.
3. watermark 없음/있음에서 key 수와 state 크기의 추세를 비교합니다. 실행 시간이 짧아서 증가가 작으면 장기 안정성을 증명했다고 쓰지 않습니다.
4. append/update/complete 모드의 허용 질의와 출력 의미를 확인합니다. 누적 snapshot을 변화량으로 다시 더하는 잘못된 sink를 만들어 중복 집계 반례를 보여 줍니다.
5. stream-stream join은 별도 확장으로 진행하고 양쪽 watermark·time constraint·정체된 source의 state 영향을 설계합니다.

### 최소 통과

bounded batch 정답, 순서별 micro-batch 원장, watermark 진행과 state 정리의 관측을 제출합니다. one-sided guarantee를 자신의 말로 설명하고 “window 종료 시각=즉시 출력 wall clock”이라는 주장을 반박해야 합니다. 오프라인 watermark 모형만 실행했다면 실제 Spark state cleanup은 미검증입니다.

<a id="sp10"></a>
## SP10 — checkpoint와 외부 commit 사이의 간격

### 원리

source offset, query batch ID, state version, sink commit은 별도 진행 상태입니다. replay 가능한 source와 적절한 sink commit 계약이 맞물려야 최종 결과의 중복·누락을 제어할 수 있습니다. checkpoint 디렉터리를 두 질의가 공유하거나 임의로 수정/삭제하면 같은 실험이 아닙니다. query 변경 시 호환성은 공식 recovery semantics에서 확인합니다.

`foreachBatch`는 기본적으로 재실행될 수 있습니다. `batchId`를 기록했다는 사실만으로 중간에 일부 행만 쓴 상태까지 exactly-once가 되지 않습니다. 서로 다른 query/checkpoint 수명에서 batch ID가 재사용될 가능성도 이름 공간으로 분리해야 합니다.

교육용 외부 DB sink의 원자성 계약을 다음처럼 설계합니다. 이것은 추가 구현용 의사코드이지 제공 Spark 코드의 기능이 아닙니다.

```text
BEGIN
  UNIQUE(pipeline_identity, checkpoint_generation, batch_id) 확인/예약
  해당 batch의 모든 업무 갱신
  동일 transaction 안에서 batch 완료 기록
COMMIT
```

partial write, 동시 실행, transaction 실패를 같은 DB 원자성으로 제어해야 합니다. 외부 HTTP side effect가 있다면 별도 outbox/업무 멱등성 계약이 필요하며 DB transaction이 HTTP 호출까지 원자화하지 않습니다.

### 추가 장애 실험

격리된 합성 입력과 새 checkpoint·sink 경로를 사용합니다. 원본을 변경하지 말고 다음 세 실패 경계를 테스트합니다.

1. sink 쓰기 전 실패: 재시작 시 아직 없는 결과가 생기는지 확인합니다.
2. sink commit 후 callback 성공 반환 전 실패: replay에서 중복이 발생하는 비멱등 sink와 중복을 막는 sink를 비교합니다.
3. 일부 업무 행만 저장한 뒤 실패: 완료 marker만 추가한 잘못된 구현이 누락을 만드는지 검사합니다.

동일 checkpoint 재시작에서 query ID와 run ID, batch ID·offset·sink 업무 ID를 대조합니다. 프로세스를 멈췄다 다시 켰다는 사실은 네트워크 분할·host 소실·공유 저장소 손상을 검증한 것이 아닙니다. memory/console sink와 replay 불가능한 socket source로 durable EOS를 주장하지 않습니다.

### state와 upgrade 확장

HDFS-backed/RocksDB state store는 versioned state를 관리하지만 지원 operator·설정·배포에 맞춰 선택합니다. state schema·partition 수·query topology 변경은 기존 checkpoint와 호환되지 않을 수 있습니다. 먼저 복제된 합성 input으로 새 checkpoint에서 전체 replay해 결과를 비교하고, 호환성 근거 없이 운영 checkpoint 파일을 편집하지 않습니다.

### 소스·최소 통과

[MicroBatchExecution·FileStreamSink·ForeachBatchSink·state provider](../source-reading.md)를 읽어 offset log→batch 실행→sink 호출→commit 진행을 연결합니다. 실제 순서는 코드의 호출 관계로 확인합니다. 최소 통과는 정상 실행과 세 실패 경계의 ID별 차이, 중복·누락 oracle, 원자성 가정, 실제 실행하지 않은 장애 목록입니다.
