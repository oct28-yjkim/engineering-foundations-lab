# 실무 운영 학습: 실행·관측·진단·복구

이 저장소의 제품·도구 트랙은 **실제 제품에서 정상 기준선 수집 → 증상 재현 → 지표·로그·실행 계획으로 원인 구분 → 내부 구현 연결 → 조치·복구 확인**을 기본 실습으로 삼습니다. 기존 원리·내부동작·소스 읽기는 유지합니다. 모니터링 화면을 많이 만드는 것도, 작은 Python 모형을 통과하는 것도 단독 완료 기준이 아닙니다.

## 왜 학습 경로를 바꾸는가

기존 “CPU 실험”은 제품 자체를 실행하는 것이 아니라 주로 Python으로 상태 전이를 계산하는 **원리 모형**이었습니다. GPU가 필요 없다는 실행 조건과 제품 실무 역량이라는 학습 목표를 혼동하기 쉬운 이름입니다. DB·broker·IaC 도구도 CPU에서 실행되므로 CPU/GPU로 커리큘럼을 분류하지 않습니다. 실제 CPU 사용률은 여전히 중요한 관측 지표입니다.

| 학습 유형 | 기본 경로 | 보조/확장 |
| --- | --- | --- |
| LLM 논문 | 기존 CPU 수학·알고리즘 실험과 독립 평가 | GPU/API 재현은 선택 확장, 기존 선호 유지 |
| DB·검색·메시징·처리 엔진 | 실제 엔진, 실행 계획·상태·로그·지표, 장애·복구 | 메모리 원리 모형은 이해가 막힐 때만 |
| 관리형 플랫폼·관측 제품 | 허가된 환경의 UI/API/SQL, 제품별 운영 신호 | 계정/비용 없으면 정제된 기존 기록으로 진단 연습; 실측 완료와 구분 |
| Terraform·Terragrunt | 실제 CLI, plan/state·대상/승인·실행 로그·부분 실패 | 그래프/CAS 모형은 보조, 클라우드 생성은 별도 선택 |
| MCP | 실제 client/server, 요청 단위 계측·오류 층·권한·복구 | 합성 계약 모형 보조; 모델/GPU/API 불필요 |

기존 `offline_lab.py`·테스트·과거 `validation.md`는 삭제하지 않습니다. 코드 경로와 기록을 보존하되 **선택 원리 보조자료/회귀 테스트**로 재분류합니다. 테스트 수가 많다는 사실로 관측·운영·트러블슈팅 과제를 대체하지 않습니다.

이번 문서 개편의 검사 결과와 실제 미실행 범위는 [개편 검증 기록](validation.md)에 분리합니다.

## 제품별 시작점

아래는 runbook과 학습 지침입니다. 모든 dashboard/exporter/장애 주입기가 자동 배포되어 있다는 뜻은 아닙니다. 각 문서의 “제공/수동 과제/실제 검증” 경계를 확인합니다.

| 제품 | 관측·진단에서 먼저 보는 것 |
| --- | --- |
| [PostgreSQL](../databases/postgresql/operations.md) | active session·wait·blocking·계획·vacuum·복제/WAL |
| [ClickHouse](../databases/clickhouse/operations.md) | query log·parts/merges·memory·replication queue·Keeper |
| [MySQL](../databases/mysql/operations.md) | Performance Schema·lock·InnoDB·statement digest·복제 |
| [OpenSearch](../search/opensearch/operations.md) | shard allocation·heap/GC·rejection·index/search latency |
| [Kafka](../streaming/kafka/operations.md) | lag·ISR·offline partition·request latency·producer 오류 |
| [NATS](../streaming/nats/operations.md) | consumer pending/ACK·redelivery·slow consumer·stream/storage·quorum |
| [Spark](../data-processing/spark/operations.md) | SQL/DAG/Stage·task skew·shuffle/spill·GC·streaming backlog |
| [Databricks](../platforms/databricks/operations.md) | query profile·job timeline·권한·compute·freshness·비용 |
| [Sentry](../observability/sentry/operations.md) | 사용자 영향·오류·trace·release·ingestion/drop·sampling |
| [Supabase](../platforms/supabase/operations.md) | DB/pool·Auth·RLS·Realtime·Storage별 실패 층 |
| [OpenBao](../security/openbao/operations.md) | seal/health·auth·lease·audit·storage/Raft |
| [Vault](../security/vault/operations.md) | seal/standby·policy·lease·audit·storage/Raft·edition |
| [Terraform](../infrastructure/terraform/operations.md) | plan 결과·lock 대기·provider 지연·drift·부분 적용 |
| [Terragrunt](../infrastructure/terragrunt/operations.md) | 선택 unit·dependency·실행 시간·실패/조기 종료·서로 다른 state |
| [MCP](../ai/mcp/operations.md) | transport/RPC/tool/business 오류·timeout·종료·권한/부작용 |

## 공통 실습 루프

1. **대상 확인:** version·실제 endpoint·principal·namespace·edition·데이터 소유권·변경 범위를 기록합니다. 운영 계정이 연결된 도구에서 제공 예제를 그대로 실행하지 않습니다.
2. **기준선:** 동일한 합성 workload와 관측 구간에서 정상 결과·지연·오류·자원·관련 상태를 수집합니다. 단일 health 응답은 기준선의 일부입니다.
3. **증상 하나:** 예를 들어 p95 상승·lag 누적·lock 대기·403 증가·plan 실패 중 하나를 고릅니다. 관련 없는 실패를 동시에 넣지 않습니다.
4. **경쟁 가설:** 최소 두 원인을 구분할 수 있는 관측을 고릅니다. “CPU가 높다”에서 끝내지 말고 workload 증가·bad plan·retry·GC 등 해당 제품의 경로를 좁힙니다.
5. **원리·소스 연결:** 지표를 만든 자료구조·queue·lock·저장/전송 경로와 대조합니다. 상관관계만으로 원인을 확정하지 않습니다.
6. **조치:** 변경 하나와 예상 효과·부작용·되돌리는 방법을 먼저 씁니다. 읽기 전용 진단에서 변경 작업으로 넘어갈 때 권한을 다시 확인합니다.
7. **회복 확인:** 원래 workload로 재검증하고 정확성·오류율·tail·backlog·권한이 같이 회복됐는지 확인합니다. process 재시작이나 오류 메시지 소멸만으로 완료하지 않습니다.

[장애 보고 양식](incident-report-template.md)에 기준선·실패·조치 후 값을 나란히 남깁니다. 기존 [실험 방법](../databases/shared/experiment-method.md)의 독립 정답·반증·반복 원칙을 그대로 적용합니다.

## 지표를 읽는 계약

- **counter:** 동일 대상의 누적값 차이/시간으로 rate를 계산합니다. restart/reset·label 변경을 먼저 처리하며 음수 차이를 처리량으로 쓰지 않습니다.
- **gauge:** 현재 pending·연결 수·heap 등은 관측 시점의 상태입니다. 이름에 `total`이 없어도 의미를 확인하고, gauge를 누적 counter처럼 해석하지 않습니다.
- **latency:** 단위와 측정 시작/끝, 표본 수·sampling·성공/실패 포함 여부를 기록합니다. 여러 instance p99의 단순 평균은 전체 p99가 아닙니다.
- **오류율:** 오류 분류와 분모를 고정합니다. 요청 수·유효 요청 수·trace 표본 수·고유 사용자 수는 서로 다른 분모입니다. 의도적 거부 실습은 실제 장애와 구분합니다.
- **capacity/lag:** 절대량뿐 아니라 유입률·처리율·최고 오래된 항목의 나이·여유 공간을 같이 봅니다. 사용률 하나를 모든 제품의 보편적 임계값으로 쓰지 않습니다.
- **부재:** 지표 미제공·권한 부족·extension 비활성·수집 지연은 0이 아닙니다. exporter 이름과 native API 필드의 변환도 기록합니다.

학습용 관측 구간은 예를 들어 정상 60초 → 제한된 재현 60초 → 회복 60초로 정할 수 있습니다. 제품 startup·retention·batch 주기에 맞춰 바꾸고, 이를 운영 SLO/경보 임계값으로 복사하지 않습니다. 운영 경보는 실제 사용자 영향과 정상 분포·보존/오류 예산에 근거해야 합니다.

## 안전과 완료 기준

읽기 전용 API도 부하·권한·민감 정보 위험이 있습니다. 쿼리에 행수/시간 제한을 두고 payload·token·query literal·state/plan 원문을 공유하지 않습니다. `EXPLAIN ANALYZE`, Terraform plan, 일부 진단 도구는 이름과 달리 실행/부작용이 있으므로 제품별 주의사항을 따릅니다. 부하·disk-full·quorum 상실·권한 변경은 전용 폐기 환경에서만 수동 선택합니다. 자동 cloud 생성·모니터링 포트 공개·운영 장애 주입은 하지 않습니다.

기존 28주·14모듈의 이론·소스 깊이는 유지합니다. 실험 시간을 실제 관측과 진단에 먼저 배정하고, 원리 모형은 필요할 때 보충합니다. 제품별 운영 실습 완료에는 **실제 기준선 1개 + 서로 다른 증상 2개 + 원인을 가르는 증거 + 조치/회복 비교 + 미검증 범위**를 요구합니다. 정답 데이터·권한 불변식이 깨진 성능 개선은 통과하지 않습니다.

환경이 없으면 “원리 학습” 또는 “제공된 기록을 이용한 진단 연습”으로 제출할 수 있습니다. 실제 제품 검증·운영 완료와 같은 상태를 부여하지 않습니다. DB·broker를 모두 설치하거나 모든 cloud 계정을 만들 필요는 없으며 업무 우선순위의 트랙 하나부터 선택합니다.
