# Secrets 운영 공통 규약: 상태·지표·감사·외부 소비자

[OpenBao runbook](../openbao/operations.md) · [Vault runbook](../vault/operations.md) · [운영 공통](../../operations/README.md) · [사고 보고서](../../operations/incident-report-template.md)

운영 실습은 제품별 실제 상태와 지표를 먼저 수집하고 원인을 좁히는 과정입니다. exact ACL·CAS·lease clock·quorum Python 모형은 **선택 원리 부록**입니다. 모형의 정답이나 dev API 성공은 seal·Raft·감사·외부 credential 회복 능력을 증명하지 않습니다.

## 사전 확인과 최소 권한

기존에 승인된 자기 학습 환경만 사용합니다. 제품·edition·서버/CLI/plugin 버전·endpoint 별칭·TLS CA·namespace(지원되는 경우)·storage type·seal 방식·node role을 확인합니다. 프록시/LB 주소와 개별 node 주소를 분리합니다. 초기화/unseal·KMS·클라우드 자원·Enterprise 기능을 자동 구성하지 않습니다. 연결 대상이나 권한을 모르면 실행하지 않습니다.

CLI는 기존 안전한 인증 세션/token helper를 사용합니다. 토큰을 argv, command history, 채팅, `.md`, Git, CI artifact에 넣지 않습니다. TLS 검증을 비활성화하지 않고 HTTP는 repo의 컨테이너 내부 loopback dev fixture에서만 허용합니다. 아래 product runbook의 조회는 read-only지만 일반 사용자의 필요보다 높은 운영 통계·audit·Raft 조회 권한이 필요할 수 있습니다. 권한이 없으면 `관측 불가`이며 root token으로 대체하지 않습니다.

capability 조회·status·metrics·audit 목록·Raft peer 조회는 secret 값의 읽기와 별개입니다. `token lookup` 전체 출력에는 식별/민감 정보가 포함될 수 있으므로 기본 수집에서 제외합니다. audit가 HMAC을 사용해도 경로·식별자·일부 metadata가 민감할 수 있습니다. raw audit/로그/metrics 원본은 승인된 보관소에서만 다루고 제출물에는 별칭, 시각, 집계, sanitized request ID만 남깁니다. [OpenBao 감사](https://openbao.org/docs/audit/), [Vault 감사](https://developer.hashicorp.com/vault/docs/audit)

## 수집 순서와 지표 계약

1. 부하를 만들지 않고 status와 read-only 권한을 확인합니다. node별 초기화·sealed·standby·version·storage 상태를 기록합니다. LB의 HTTP 200만으로 모든 node의 상태를 추론하지 않습니다.
2. 기존 telemetry와 감사 장치의 **존재와 수집 가능성**을 확인합니다. telemetry가 없으면 새 공개 endpoint를 열지 않고 설치/권한 요청 항목으로 남깁니다. replica에서 scrape가 안 되는 것이 제품 장애인지, auth/standby 계약인지 먼저 구분합니다.
3. 동일 node·role·window로 정상 15분과 사건 15분을 비교합니다. 운영 상태 snapshot은 30초 간격·5분 등 제한된 수집을 사용하고 과도한 polling을 피합니다. lease gauge의 실제 refresh interval이 더 길면 그 주기를 포함하도록 창을 늘립니다.
4. node, metric 원명, 실제 exporter 이름, `HELP/TYPE`, unit, sink, label, scrape/aggregation interval, counter reset 여부를 지표 사전에 씁니다. OpenBao와 Vault 이름이 같아도 runtime에서 확인되지 않으면 미수집입니다.

| 자료 종류 | 허용 해석 | 피해야 할 결론 |
| --- | --- | --- |
| health/status | 그 node의 관측 시점 상태·HTTP code/JSON·CLI exit code | 429를 무조건 rate limit으로 해석하거나 nonzero exit를 모두 network 오류로 해석 |
| gauge | 현재 개수·bytes·0/1·ms; 시점/갱신 지연 기록 | gauge에 `rate()`를 무조건 적용, 미수집을 0으로 채움 |
| Prometheus cumulative counter | 동일 시계열의 reset-aware `rate(...[5m])`는 건/초, `increase(...[5m])`는 구간 증가량 | 기간 집계형 in-memory counter를 cumulative로 간주 |
| latency summary | 표본 count·sum의 창별 차이로 평균 계산; 제공 quantile은 node 단위 | 여러 node p95 평균, summary에 없는 histogram bucket을 만들어 `histogram_quantile` 사용 |
| 감사 request/response | ID·시각·주체 별칭·operation·path 별칭·오류를 상관 | 모든 endpoint가 감사되거나 request 존재가 실제 성공이라는 주장 |
| 소비자 원장 | 로그인/갱신·파일 교체·앱 reload·외부 DB 새 인증의 시간선 | lease 삭제나 revoke 응답만으로 기존 DB session이 종료됐다는 주장 |

OpenBao의 in-memory 집계와 장기 시계열 보관은 다릅니다. telemetry의 retention이 durable 저장을 뜻하지 않습니다. Vault의 raw interval counter와 Prometheus counter 표현도 구분합니다. [OpenBao telemetry](https://openbao.org/docs/internals/telemetry/), [Vault telemetry](https://developer.hashicorp.com/vault/docs/internals/telemetry)

임계치는 문서의 예시 숫자가 아니라 자기 환경의 정상 분포·SLO·credential TTL·복구 예산으로 정합니다. 평균 latency가 정상이어도 소비자의 갱신 deadline을 놓치면 사건입니다. 부족한 시계열을 CPU 모형 숫자로 채우지 않습니다.

## 변경·중단·회복 계약

모든 실패 재현은 제품 runbook이 지정하는 합성 자산에만 수동 수행합니다. 봉인, 재초기화, audit disable, mass revoke, force revoke, peer 제거, snapshot restore는 baseline 단계의 명령이 아닙니다. 특히 **관측을 편하게 하려고 audit를 끄거나 root 정책을 확대하지 않습니다**.

원복은 credential을 다시 살리는 것과 같지 않습니다. 만료/폐기된 토큰은 되돌릴 수 없으므로 정상 auth flow로 새 최소 권한 credential을 얻는 것이 회복일 수 있습니다. snapshot 복원은 별도 대상·seal 자산·외부 credential 상태를 함께 검산해야 합니다. container 재시작은 dev의 모든 memory 상태를 잃으며 HA 복구 실습이 아닙니다.

운영 gate는 **baseline 1개 + 서로 다른 사건 2개 + 사건별 경쟁 가설·증거·제한 조치·원복/재발급·회복 검산**입니다. 개인 dev 환경만 있으면 권한/TTL/client 범위에서 수행하고 audit/Raft/DR은 미실행으로 분리합니다. 운영 관측 권한/환경이 없으면 설계 완료 또는 환경 미준비로 보고하며 모형 PASS를 운영 완료로 인정하지 않습니다.
