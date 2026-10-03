# S01–S02 — 텔레메트리 계약과 데이터의 의미

이 강의의 질문은 “Sentry에 몇 개가 보이는가?”가 아니라 “무엇이 몇 번 일어났으며, 어떤 단위가 어떤 조건에서 보이는가?”입니다. 모든 실험에서 업무 원장과 수집 원장을 분리합니다. [공통 실험 방법](../../../databases/shared/experiment-method.md)에 따라 기대 결과를 먼저 기록합니다.

## S01. 오류 처리 workflow를 관측 계약으로 바꾸기

### 선수 조건과 원리

HTTP status, 비동기 queue, 집합의 차집합을 이해하면 시작할 수 있습니다. Sentry는 애플리케이션의 모든 실패를 자동으로 정의해 주지 않습니다. 예를 들어 HTTP 200으로 반환한 잘못된 금액, 재시도로 숨겨진 결제 실패, 백그라운드 작업의 silent drop은 uncaught exception과 다른 업무 실패입니다. 먼저 업무 불변식과 사용자가 경험한 결과를 정의해야 합니다.

한 오류는 생성, SDK capture, SDK 처리, transport 제출, 수신, 처리, 저장, 검색, issue 갱신, 알림 전달의 상태를 거칩니다. 이 중 어느 단계도 다음 단계의 완료와 동일하지 않습니다. 특히 transport의 성공 응답은 선택한 endpoint의 요청 수락 증거이지, 모든 신호가 검색 가능해졌거나 알림이 전달되었다는 증거가 아닙니다. 오류가 수집되어도 필터·샘플링·그룹화·권한·시간 범위 때문에 기대한 화면과 다를 수 있습니다.

triage는 업무 영향과 재현 가능성으로 우선순위를 정하고, 수정 후 배포 identity와 재발 조건을 확인하는 과정입니다. issue를 resolve한 것은 원인이 제거되었다는 증명이 아닙니다. 문제를 해결한 코드가 실제 문제 environment에 배포되었는지, 새 오류가 같은 fingerprint로 들어오는지, 관측 누락으로 조용한 것인지를 함께 검토합니다.

### 실험: 생성 원장과 관측 원장의 차이를 설명하기 — `OFFLINE` / 확장 `SDK-LAB`

입력은 `request_id=1..1000`, 의도한 결과, 실제 결과, `business_event_id`, 발생 시각을 포함한 합성 원장입니다. 900건은 성공, 60건은 처리된 업무 거절, 30건은 예외, 10건은 timeout으로 정합니다. 업무 거절을 오류로 수집할지는 별도의 정책 필드로 명시합니다. 이 비율은 성능 수치가 아니라 실습 입력입니다.

1. oracle은 애플리케이션 원장에서 “수집해야 할 논리 오류”의 집합을 산출합니다. SDK 결과에서 역으로 정답을 만들지 않습니다.
2. 수집 대상 중 일부에 의도한 client filter, sample, transport 실패, 응답 유실을 주입하는 모델을 작성합니다. 각 fixture에 예상 분류를 붙입니다.
3. 단계별 기록에는 `logical_id`, `attempt_id`, `event_id`가 있는 경우 그 값, 상태, 원인, 시간, 증거 위치를 둡니다. 재시도 횟수와 논리 오류 수를 별도로 셉니다.
4. 결과를 `observed`, `intentional_drop`, `known_failure`, `unknown`으로 분류합니다. 중복 시도는 별도 열입니다. 원인 증거가 없는 누락은 `unknown`이지 “샘플링된 것”이 아닙니다.
5. SDK 확장에서는 외부 DSN을 사용하지 않는 transport로 SDK 처리 후 payload를 관찰합니다. 이 단계만으로 서버 저장·그룹화는 검증되지 않았음을 표시합니다.

oracle의 보존식은 각 단계의 **동일 단위·동일 cohort**에만 적용합니다. `generated = accepted + filtered + rate_limited`를 임의의 대시보드 숫자에 적용하면 시간 지연, client 미보고 폐기, 재시도, 단위 차이가 숨습니다. Client report도 전송에 실패할 수 있으므로 손실의 완전한 회계 장부가 아닙니다. [공식 Stats 설명](https://docs.sentry.io/product/stats/)

### 실패 반례와 통과 기준

- HTTP 200 응답 후 수신기 데이터를 지워 봅니다. transport 성공과 영속 저장이 분리됨을 모델에서 설명해야 합니다.
- 하나의 논리 오류를 두 번 capture합니다. 두 event가 하나의 issue로 보이는 경우 “중복 없음”이라는 결론이 왜 틀렸는지 설명합니다.
- 10건을 보고하지 않고 누락시킵니다. 원장 차집합이 이를 찾는지 확인합니다.

산출물은 계약서, 1,000행 입력 원장, 단계별 상태표, 손실/중복 구분 보고서입니다. 모든 논리 오류를 분류하고, 의도한 폐기와 미확인을 구별하며, 동료가 같은 fixture로 같은 분류를 얻으면 통과합니다. 알림을 평가하려면 별도 수신 확인과 중복/지연 oracle이 필요합니다. 알림 규칙의 저장만으로 알림 전달을 주장하지 않습니다.

## S02. event·issue·span·Replay·metric의 단위를 분해하기

### 선수 조건과 원리

S01의 논리 오류/시도/관측 단위를 설명할 수 있어야 합니다. Sentry 문서에서 `event`는 일반 payload나 특정 event 유형을 뜻할 수 있으므로 문맥을 붙입니다. “event 1개” 대신 “error event 1개” 또는 “transaction payload 1개”처럼 말합니다. 다음 표는 개념 계약이며 모든 SDK가 모든 유형을 지원한다는 뜻은 아닙니다.

| 개념 | 의미와 식별 경계 | 바꾸어 세면 안 되는 것 |
| --- | --- | --- |
| Error/message event | 한 번의 오류 또는 message capture에 대한 구조화된 관측 payload | 논리 업무 실패, issue 수 |
| Issue | 오류 또는 특정 문제 유형을 그룹화하여 추적하는 제품 객체 | 원인 그 자체, 원시 event 하나 |
| Trace / span | 분산 작업의 연결 관계 / 이름·시간·속성·부모를 가진 작업 구간 | 요청 수, 전역적으로 완전한 실행 기록 |
| Transaction | SDK·모드에 따라 root 작업과 포함 span을 표현하는 transaction 모델/payload | 모든 현대 span이 반드시 transaction envelope에 포함된다는 가정 |
| Structured log | timestamp·level·message·attributes 등의 로그 신호 | console breadcrumb, error event |
| Replay | 사용자 상호작용 및 화면 상태를 재구성하기 위한 녹화 데이터와 관련 메타데이터 | Release Health session, 요청 trace, 단순 영상 파일 |
| Application metric | counter·gauge·distribution 등 집계 대상 측정값 | error count, 사용량 Stats, 자동 추출된 span metric 전체 |
| Session health | SDK/플랫폼에 따른 사용자 또는 요청 session의 건강 상태 | Replay recording, 오류 event 한 건 |
| Envelope | header와 유형별 item을 담는 전송 컨테이너 | event·span·요청 한 건과의 일대일 대응 |

현대 JavaScript 문서는 span streaming과 static transaction 모드를 구별하고, 별도의 Logs와 Application Metrics API를 설명합니다. 따라서 과거 transaction 중심 예제를 최신 SDK의 모든 span에 적용하지 않습니다. 사용 SDK의 정확한 버전·API 지원·trace lifecycle 설정을 기록합니다. [JS 필터링](https://docs.sentry.io/platforms/javascript/configuration/filtering/), [Logs](https://docs.sentry.io/platforms/javascript/logs/), [Metrics](https://docs.sentry.io/platforms/javascript/metrics/)

Envelope에는 item 조합 제약이 있습니다. event/transaction/feedback의 관계, attachment가 어느 event에 붙는지, Replay item의 짝, span batch의 trace 문맥을 현재 프로토콜로 확인해야 합니다. 모든 신호를 한 Envelope에 임의로 섞을 수 있다고 가르치지 않습니다. [Envelope item 규약](https://develop.sentry.dev/sdk/foundations/envelopes/envelope-items/)

### 실험: 12종 fixture의 의미를 판정하기 — `OFFLINE`

다음 fixture의 최소 JSON 또는 표를 직접 작성합니다. 실제 비밀정보나 사용자 정보를 넣지 않습니다.

1. 같은 stack을 가진 error event 3개.
2. 다른 논리 원인이지만 강제 fingerprint가 같은 event 2개.
3. 하나의 root와 자식 3개를 가진 trace.
4. root가 수집되지 않은 span.
5. transaction mode payload.
6. console breadcrumb만 기록된 요청.
7. structured log 2개.
8. Replay recording과 metadata.
9. counter 증가 3회.
10. distribution에 기록한 세 지연시간.
11. 오류가 두 번 발생한 session 하나.
12. attachment가 포함된 error Envelope.

각 fixture에 `logical entity`, `wire unit`, `query unit`, `count denominator`, `identity`, `retention boundary`, `privacy path`를 채웁니다. 서버 미실행이면 실제 issue ID나 서버 집계 결과를 만들어 넣지 않습니다. “같은 default fingerprint라고 가정한 grouping 모델”과 “서버에서 관측한 grouping 결과”를 별도 상태로 표기합니다.

oracle은 직접 정한 입력 관계입니다. 예를 들어 root+자식3개는 4개의 span이지만 4개의 사용자 요청이라고 단정할 수 없습니다. session 하나에서 오류가 두 번 발생해도 session denominator는 둘이 되지 않습니다. distribution의 count·sum은 측정 입력과 비교할 수 있지만 임의 backend percentile을 원본 표본과 동일한 정확도라고 가정할 수 없습니다.

### 실패 반례와 통과 기준

breadcrumb를 생성했는데 Logs 탐색에 보이지 않는 것은 반드시 전송 실패가 아닙니다. crash-free session과 error-free request는 다른 질문입니다. query의 시간 구간·timezone·권한·dataset·sampling 상태를 기록하지 않은 비교는 판정 불가로 둡니다. [Release Health](https://docs.sentry.io/product/releases/health/)

12종 분류가 모두 단위와 일관되고, issue/event/session 분모 혼동 3개를 반례로 설명해야 통과합니다. 제출물에는 SDK/제품 기능 지원표와 “선택 버전에서 확인하지 못한 항목”도 포함합니다. 소스는 [읽기 지도](../source-reading.md)에서 SDK event 모델·Envelope serializer와 서버 grouping 객체의 책임 경계를 비교합니다.
