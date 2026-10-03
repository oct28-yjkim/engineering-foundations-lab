# 권한과 재처리를 검증하는 Lakehouse 연구 8주

[Spark](../data-processing/spark/README.md)와 [Databricks](../platforms/databricks/README.md)의 작은 실험을 재사용하는 선택 통합 과정입니다. 기존 [데이터 파이프라인](../databases/shared/capstone.md)·[보안 관측 앱](secure-observable-app.md) 캡스톤과 다른 주제이며 모두를 필수로 더하지 않습니다.

managed 환경이 없으면 OSS/local 구현과 managed 설계를 구분합니다. 전체 Databricks 기능을 로컬 모형으로 대체했다고 보고하지 않습니다. 이 문서는 완성 pipeline·workspace·cluster·credentials를 제공하거나 자동 배포하지 않습니다.

## 업무 계약

두 tenant의 합성 주문 변경 이벤트를 원본 원장 → raw/Bronze → current-state/Silver → 집계/Gold로 처리합니다. Bronze/Silver/Gold는 품질·책임을 나누는 설계이며 이름만으로 정합성이나 원자성이 생기지 않습니다. 입력은 file fixture로 시작할 수 있고 Kafka/CDC 연결은 선택 확장입니다.

| 불변식 | 독립 정답 |
| --- | --- |
| 중복·순서 뒤바뀜에도 올바른 최신 업무 상태 | entity ID·source epoch/version·payload·tombstone 원장 |
| 상충한 동일 version은 임의 winner로 숨기지 않음 | conflict 격리 집합과 사람 검토 기준 |
| 다른 tenant의 데이터가 조회/직접 경로/cache로 새지 않음 | 두 실제 principal의 table/volume/storage 허용·거절 matrix |
| 집계는 선언한 Silver snapshot과 일치 | 같은 시점·버전의 단순 reference query와 sum/count |
| 재시작·별도 복원 후 업무 상태와 권한이 맞음 | ID별 값·물리 객체·권한·job/checkpoint 계약 |

## 1–2주 모델과 실행 경계

schema, primary business key, event ID, source epoch/version, delete/recreate, null, late 기준을 고정합니다. fixture를 100–1,000개 수준에서 시작하고 duplicate·stale·delete·conflict를 의도적으로 포함합니다. 원본 event ledger를 출력 테이블에서 역생성하지 않습니다.

runtime·source/sink·storage·catalog·job identity·resource/cost manifest를 작성합니다. batch/streaming, append/upsert, stateful/stateless를 분리합니다. managed는 사용 권한 있는 별도 대상만 선택하며 가격·사용량·예산은 실제 실행 시점 기준으로 기록합니다.

## 3–4주 작은 정상 경로

가능한 가장 작은 변환·MERGE·집계부터 구현합니다. Spark plan과 output oracle을 같이 저장하고 source dedup과 target idempotency를 별도 검증합니다. 둘 이상의 테이블에 쓰는 경우 중간 실패의 가시성을 정의합니다. 채택한 제품/기능에서 실제 multi-statement transaction을 지원하는지 확인하지 않고 원자적이라고 가정하지 않습니다.

두 identity의 positive/negative test를 수행하고 UC 권한 외 storage 직접 경로와 cache도 검토합니다. 실제 플랫폼이 없으면 이 항목은 설계 결과이며 managed 검증이 아닙니다. 실제 engine이 없으면 CPU 모형 단계까지만 표시합니다.

## 5–6주 실패와 비용 비교

다음 중 최소 다섯 조건을 독립 run으로 검증합니다. runtime/권한이 필요한 조건은 사용자가 준비한 격리 환경에서만 실행합니다.

- 동일 batch/event 재전송과 늦게 도착한 삭제 이전 version.
- 동일 key/version의 상충 payload, schema 변경 또는 잘못된 타입.
- 응답/ACK 유실로 업무 반영 여부를 알 수 없는 상태와 재시도.
- streaming 중단 후 **호환되는 동일 checkpoint** 재시작; checkpoint 변경 실험은 새 경로/명시적 재처리 계약으로 분리.
- 권한 철회 뒤 새 요청·cache·실행 identity의 가시성.
- skew 또는 작은 파일 증가로 plan/task/memory 비용이 달라지는 경우.
- Silver 성공·Gold 실패처럼 여러 단계 사이에서 발생한 부분 성공.

count를 맞추기 위해 checkpoint·원본·outcome 로그를 지우지 않습니다. 실패 run의 근거를 보존하고 재처리를 멱등하게 수렴시킵니다. partition 모형에서 load가 고르게 됐다는 사실은 실제 job speedup이 아닙니다. 성능 비교는 동일 데이터·권한·품질·compute·cache 조건과 actual plan, task metrics, 비용을 함께 기록합니다.

## 7–8주 독립 복원과 설계 방어

별도 대상으로 원본/업무 데이터·필요 파일/log·catalog/권한·job/config·checkpoint 또는 선언한 재처리 경로를 복원합니다. time travel·RESTORE가 원본 파일·보존 정책에 의존하는 범위를 적고 independent backup과 구별합니다. 관리형 기능을 실제 사용하지 않았다면 복구 설계까지만 표시합니다.

RTO/RPO 목표는 실험 전에 선언합니다. 실제 복구 시간은 프로세스 기동이 아니라 업무/권한 oracle 통과까지 측정하고, 누락된 성공 응답 event ID와 일관된 복원 시점을 원장에 대조합니다. 마지막 쓰기 뒤의 유휴 시간을 데이터 손실로 계산하지 않습니다.

최종 제출은 코드/환경 지문, 정상 run, 다섯 실패 결과, 독립 복원, 비용/권한 검산, 소스/논문 근거와 미검증 경계입니다. 공통 기준은 정확성·원리/소스·실험/반증·운영/재현성 각 25점, 총 80 이상·각 15 이상과 필수 게이트입니다.

LLM/RAG로 확장할 때는 corpus/embedding/index/eval revision과 tenant filter를 추가하고 데이터 pipeline 성공과 모델 답변 품질을 따로 평가합니다. 이는 추가 선택 주제이며 8주에 모든 모델 학습·에이전트 구축까지 요구하지 않습니다.
