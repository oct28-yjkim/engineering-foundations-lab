# S07–S08 — trace 연결과 표본 대표성은 별개의 문제다

완전해 보이는 waterfall도 누락되거나 편향될 수 있습니다. 이 강의는 작업 관계가 올바르게 연결되는지와, 관측된 집합이 어떤 모집단을 대표하는지를 독립적으로 검증합니다.

## S07. 비동기 실행의 부모와 신뢰 경계

### 선수 조건과 원리

S03의 scope 격리, parent/child tree, HTTP header를 이해해야 합니다. span은 특정 작업 구간의 시간·속성·문맥을 표현합니다. parent relation은 인과적 작업 연결을 표현하지만 전체 프로세스의 모든 실행 순서나 업무 transaction의 원자성을 보장하지 않습니다. 병렬 child span은 서로 겹칠 수 있고, process clock 차이와 전송 지연을 고려해야 합니다. root가 관측되지 않거나 중간 span이 제거되면 보이는 tree는 실행된 tree의 부분집합입니다.

Sentry SDK의 분산 전파에서는 `sentry-trace`와 `baggage`가 중요합니다. `tracePropagationTargets`는 목적지별 header 전파를 제어하며 서버의 CORS 설정을 자동 변경하지 않습니다. browser와 backend 간 CORS 허용 header, 실제 hostname/port, proxy 통과 여부를 함께 확인합니다. `baggage`는 민감정보 운반 수단으로 사용하지 않습니다. [분산 추적](https://docs.sentry.io/platforms/javascript/tracing/distributed-tracing/)

W3C `traceparent`·OpenTelemetry context와 Sentry 전파 형식의 연결은 버전과 integration에 따라 검증합니다. 현재 Node 문서는 Sentry SDK 자체 span 경로와 OTel API capture/custom pipeline 구성을 구별하므로 “모든 Node SDK가 OTel pipeline 위에서 동작한다”는 설명은 부정확할 수 있습니다. 서로 다른 두 자동 instrumentation을 동시에 켜면 중복 span이나 context 충돌이 생길 수 있습니다. [Node와 OpenTelemetry](https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/)

### 실험: 3구간 요청과 병렬 작업 — `SDK-LAB`

외부 서비스 대신 loopback frontend/client→API→worker의 세 경계를 구성합니다. worker가 queue 소비를 흉내 내더라도 HTTP 부모를 자동으로 그대로 잇지 말고, message에 어떤 context를 실었는지 명시합니다. 실제 queue는 필수 아닙니다. fixture는 순차 child, 두 병렬 child, 지연 callback, orphan span, 허용되지 않은 목적지로의 요청입니다.

1. ground-truth DAG에 각 작업의 `operation_id`, 기대 trace identity, parent relation 또는 link 정책을 기록합니다. span ID 자체는 실행 시 생성되므로 oracle은 ID의 관계를 판정합니다.
2. SDK 처리 후 transport에서 수집한 span을 normalize하여 DAG와 비교합니다. API의 요청별 scope와 worker job scope를 분리합니다.
3. 전파 허용 주소와 비허용 주소를 loopback의 서로 다른 port로 구분하고 수신 header를 검사합니다. 넓은 정규식이 유사 hostname까지 허용하는 반례도 입력에 넣습니다.
4. sampling을 모두 유지하는 기준선에서 연결성을 먼저 검증한 뒤, parent sampling decision을 변경합니다. 처음부터 sampling을 켜면 문맥 결함과 의도적 누락을 구별하기 어렵습니다.
5. 선택 심화에서는 같은 요청에 Sentry와 OTel 자동 instrumentation을 각각 단독/동시 적용합니다. 원시 네트워크 요청 수와 span 수를 비교하여 이중 기록을 찾습니다.

통과 기준은 정상 fixture의 기대 parent 관계 일치, 요청 간 context 혼합 0, 비허용 목적지의 추적 header 전파 0입니다. orphan fixture는 실패가 탐지되어야 합니다. “완벽한 전체 trace”가 아니라 어느 구간의 연결을 검증했는지 선언합니다. 화면 waterfall만으로는 수집되지 않은 span의 존재를 알 수 없으므로 원장과 raw payload를 함께 제출합니다.

### lifecycle·filter의 버전 gate

선택한 JS SDK의 문서/타입/테스트에서 mode를 확인합니다. 현재 문서에는 streaming mode와 `traceLifecycle: 'static'`인 transaction mode가 구별됩니다. `beforeSendTransaction`을 모든 span에 적용되는 hook으로 가정하지 않습니다. `beforeSendSpan`은 finished span을 수정하는 hook이며 현재 문서에서 `null` 반환으로 삭제하는 API가 아닙니다. span 제외에는 지원되는 `ignoreSpans` 등 해당 버전 경로를 확인합니다. 부모 제거가 자식의 관계와 timing에 미치는 영향도 검증합니다. [JS filtering](https://docs.sentry.io/platforms/javascript/configuration/filtering/)

## S08. 샘플링된 관측값으로 무엇을 추정할 수 있는가

### 선수 조건과 원리

S07, 평균·확률·조건부 확률이 필요합니다. client head sampling은 실행 전체 결과를 알기 전에 일부 작업을 선택하며, 보내지 않은 데이터는 서버가 복원할 수 없습니다. 서버의 dynamic/retention sampling은 이미 도착한 데이터의 저장·조회 대상을 줄이는 단계와 관련됩니다. 도착 데이터에서 metric을 먼저 추출하는 구성이라도 그 metric이 client가 버린 요청까지 포함한다는 뜻은 아닙니다. 단계별 모집단을 붙여야 합니다. [Dynamic sampling 구조](https://develop.sentry.dev/application-architecture/dynamic-sampling/), [JS sampling](https://docs.sentry.io/platforms/javascript/sampling/)

모든 사건이 동일한 확률로 표본에 들어오는지, 오류·latency·tenant·release에 따라 확률이 달라지는지가 핵심입니다. 느린 요청을 더 많이 보관하면 저장된 span의 단순 평균은 모집단 평균보다 커질 수 있습니다. 알려진 포함 확률 `p_i > 0`가 있으면 합계는 `Σ(y_i/p_i)` 방식으로 추정할 수 있고 비율은 가중 분자/분모를 사용합니다. 비율 추정량의 통계 성질과 불확실성은 단순 합계와 다릅니다. 정확히 층별 비율을 뽑는 교육용 예의 대수적 일치를 모든 무작위 표본의 정확성으로 일반화하지 않습니다.

head sample·retention sample·network loss가 있으면 최종 포함 확률을 알아야 합니다. 단계가 독립이라는 근거 없이 비율을 곱하거나, 전송 실패가 missing-at-random이라고 가정하지 않습니다. 어떤 계층의 확률이 0이면 그 계층은 표본만으로 복원할 수 없습니다. percentile에 `1/p`를 곱하는 방식도 올바른 복원이 아닙니다.

### 실험 A: 제공되는 결정적 표본 oracle — `OFFLINE`

[샘플링 oracle](../labs/sampling-oracle.mjs)은 Node 내장 기능만 사용하며 SDK·DSN·HTTP를 사용하지 않습니다. 실행법과 실제 입력은 [실습 안내](../labs/local-lab.md)를 따릅니다. 스크립트의 입력 규모·층별 포함 규칙을 먼저 읽고, 모집단의 요청 수·오류 수·오류율, 표본의 naive 값, 포함 규칙을 적용한 weighted 값을 손으로 계산한 뒤 실행합니다. 이 스크립트에는 지연시간 표본이 없으며, latency 실험은 아래의 별도 구현 과제입니다.

판정은 “Sentry sampling이 검증됐다”가 아니라 “정의한 인공 모집단과 층별 표본에서 단순 집계가 왜곡될 수 있음을 oracle로 보였다”입니다. 출력에 있는 모집단, 단순 표본, 가중 집계의 분모를 각각 설명합니다. 스크립트를 실행하지 않았다면 결과 수치를 보고서에 만들어 넣지 않습니다.

### 실험 B: 무작위 표본과 결측 반례 — `OFFLINE` 구현 과제

확장 입력은 빠른 요청 9,000개·각 10ms와 느린 요청 1,000개·각 1,000ms입니다. 모집단 평균은 직접 계산합니다. 빠른 계층은 확률 0.1, 느린 계층은 확률 1로 포함하고 고정 seed 100개로 반복합니다. 오류 label은 latency 계층과 독립인 경우와 상관된 경우 두 가지를 준비합니다.

1. 각 seed에서 naive mean, weighted total/mean, 표본 크기를 기록합니다. 단일 seed의 우연한 일치 대신 분포·오차를 제시합니다.
2. 높은 부하일수록 SDK 전송이 실패하도록 추가 loss를 넣습니다. 초기 `p_i`만 사용한 가중치가 깨지는 반례를 확인합니다.
3. 한 tenant를 확률 0으로 제외합니다. 알려진 모집단 원장이 없다면 그 tenant의 실패율은 식별 불가능하다고 결론 내려야 합니다.
4. head sampling으로 제거한 사건을 metric 추출 단계보다 앞에서 삭제하는 모델과, 추출 후 raw 저장만 줄이는 모델을 비교합니다. 두 metric의 모집단이 달라짐을 보입니다.

oracle은 합성 원장 전체에서 계산한 exact count/sum/mean입니다. 관측값의 오차와 추정 불확실성을 구별합니다. 최대 지연시간·percentile은 전체 입력 정렬로 기준값을 만들되, 표본 quantile의 보정/신뢰구간은 별도 방법과 가정이 필요한 것으로 표시합니다.

### 산출물·실패·통과 기준

population→SDK selected→received→metric extracted→stored→query의 단계 그림과 각 분모를 제출합니다. 실제 배포에서 단계 순서가 확인되지 않은 신호는 “가설”로 표시합니다. 오류 sampleRate, trace sampling, Replay sampling, log/metric filter를 동일한 설정이라고 쓰지 않습니다.

naive bias, 알려진 포함 확률의 가중 추정, 비무작위 loss, 확률 0의 네 사례를 모두 설명하면 통과합니다. sampling이 있는 trace 데이터만으로 SLO를 주장할 때 필요한 독립 요청 counter/latency histogram과 수집 건강 지표를 제안합니다. [소스 지도](../source-reading.md)의 sampler·propagation·metric extraction 경로를 선택 revision에서 추적합니다.
