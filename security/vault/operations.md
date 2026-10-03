# Vault 운영 실습: node health에서 소비자 회복까지

[시작](README.md) · [커리큘럼](curriculum.md) · [공통 수집·안전 규약](../shared/operations.md) · [사고 보고서](../../operations/incident-report-template.md)

기본 경로는 **Vault Community 2.1.1의 실제 baseline·지표·감사·troubleshooting**입니다. CPU 모형은 선택 원리 부록입니다. Enterprise/HCP의 namespaces·DR replication·performance standby를 Community 필수 실습으로 요구하지 않습니다. OpenBao와 API가 비슷해도 제품별 실행 증거가 필요합니다.

## 1. 읽기 전용 사전 확인

이미 승인된 환경의 endpoint·CA·CLI 인증 세션을 확인하고 `VAULT_ADDR`·namespace 설정이 의도한 대상인지 검토합니다. 토큰 값이나 환경 전체는 출력하지 않습니다. target이 불명확하거나 TLS 검증을 끄고 접속해야 한다면 진행하지 않습니다. 별도 계정·server·키 발급을 자동 수행하지 않습니다.

```text
vault version
vault status -format=json
vault token capabilities sys/metrics
vault token capabilities sys/audit
vault token capabilities sys/storage/raft/configuration
```

node별 `initialized`, `sealed`, `version`, `storage_type`, HA/standby 정보·exit code·관측 시각을 기록합니다. status가 sealed여서 nonzero인 경우와 transport 오류를 구분합니다. 필요한 read/list 및 해당 endpoint의 추가 권한이 **이미 승인된 관측자**에게 있을 때만 다음을 실행합니다.

```text
vault read -format=json sys/metrics
vault audit list
vault operator raft list-peers
```

Raft는 integrated storage일 때만 적용합니다. `inmem` dev에서 실패한 명령을 Raft 장애로 부르지 않습니다. audit 목록은 기록 성공이 아니며 metadata/address/경로는 보고서에서 익명화합니다. 403이면 root token으로 재시도하지 않고 필요한 관측 권한을 요청합니다. [Vault status](https://developer.hashicorp.com/vault/docs/commands/status), [telemetry 구성](https://developer.hashicorp.com/vault/docs/configuration/telemetry)

승인된 기존 health monitor에서 **GET `/v1/sys/health`**의 HTTP code와 JSON을 함께 봅니다. 기본 active 200, standby 429, uninitialized 501, sealed 503은 서로 다릅니다. 429가 이 endpoint에서 항상 rate limiting은 아닙니다. Enterprise 관련 472/473, disconnected standby 474, removed 530 등은 실제 version·edition·상태와 대조합니다. `standbyok` 또는 code override/LB rewrite가 있으면 원래 상태와 분리합니다. [health API](https://developer.hashicorp.com/vault/api-docs/system/health)

## 2. 실제 metric 사전

지표 원명과 scrape의 실제 이름/TYPE을 매핑합니다. 점을 underscore로 바꾸는 것만으로 dashboard를 완성하지 말고 hostname·label·sink와 부재 이유를 확인합니다. `/sys/metrics`의 active/standby·인증 동작은 node와 edition 설정에 따라 달라질 수 있습니다. scrape를 쉽게 하려고 unauthenticated endpoint를 새로 공개하지 않습니다.

| 지표 | 종류·단위 | 창과 진단 질문 |
| --- | --- | --- |
| `vault.core.unsealed`, `vault.core.active` | gauge, 0/1 | node별 30초·5분; 봉인·standby·대상 오류 구분 |
| `vault.core.handle_request`, `vault.core.handle_login_request` | summary, ms | 동일 node의 5분 count/sum·가능한 quantile; 로그인만 느린지 확인 |
| `vault.expire.num_leases` | gauge, lease 수 | 갱신 간격을 포함한 추이; 발급/갱신 burst와 대조 |
| `vault.audit.log_request_failure`, `vault.audit.log_response_failure` | counter, 오류 건수 | Prometheus sink에서는 5분 increase 또는 rate(건/초); raw interval 형식과 혼합 금지 |
| `vault.raft.state.candidate`, `vault.raft.state.leader` | counter, 전환 건수 | 5분 증가량; 반복 선출인지 계획된 변경인지 비교 |
| `vault.raft_storage.follower.applied_index_delta` | gauge, index 차이 | node별 추이; 시간 lag로 자동 환산하지 않음 |
| `vault.raft_storage.follower.last_heartbeat_ms` | gauge, ms | 정상 peer·network·I/O와 함께 판단; 미수집은 0 아님 |
| host/storage·소비자 | disk bytes·I/O ms·메모리 bytes, 신규 인증 결과·credential age 초 | node health와 앱의 실제 사용 가능성을 연결 |

근거: [core/lease 관측](https://docs.hashicorp.com/validated-designs/vault/administration-guide/monitoring-and-observability), [audit 지표](https://developer.hashicorp.com/vault/docs/internals/telemetry/metrics/audit), [Raft 지표](https://developer.hashicorp.com/vault/docs/internals/telemetry/metrics/raft). audit raw interval 출력의 count를 오류 건수로 단순 해석하지 않습니다. summary quantile은 node 간 더하거나 평균내지 않습니다. Enterprise 전용 지표가 Community에 없는 것은 관측 결과이지 0건의 증거가 아닙니다.

## 3. 사건별 경쟁 가설·조치·회복

| 증상 | 경쟁 가설과 최소 증거 | 제한된 조치·원복 | 회복 검증 |
| --- | --- | --- | --- |
| 403·Agent 갱신 실패 | expired token / wrong auth role·path / ACL 변경 / claim 불일치. node status, capability, sanitized audit, Agent 시간선을 대조 | 시험 client의 잘못된 설정만 수정; 원래 revision 보관. 만료된 token을 복원하지 않고 정상 auth flow로 새 최소 권한 credential 발급 | 허용 요청·갱신 성공, 금지 path 거부 유지, 앱이 새 credential을 실제 사용 |
| 5xx/latency와 audit 오류 증가 | 모든 감사 경로 실패 / disk·permission / storage 지연 / client 폭주. audit device와 host·request latency 상관 | 승인된 destination·권한·용량 복구, 발생기 제한. audit disable·로그 지우기·root 확대 금지 | 감사 request/response 상관 복구, 오류 증가 정지, 같은 부하 정상, 손실 범위 공개 |
| 간헐 503·leader 전환·lag | sealed/제거 node / quorum 통신 / disk stalls / LB가 standby 계약 오판. health body→peer→전환 counter→disk/network | 격리 lab에서 앞서 변경한 규칙/설정만 원복; 운영 peer 제거·재초기화 금지. code override로 빨간 상태를 초록으로 숨기지 않음 | 의도된 node 역할·voter와 read/write 결과 회복, applied 차이 수렴, 동일 synthetic 값 대조 |
| TTL 후 앱이 계속 인증하거나 인증 불가 | 외부 revoke 실패 / connection cache / 앱 reload 누락 / lease 재발급 루프. lease·plugin·소비자 신규 인증과 기존 session 구분 | 시험 client의 발급 루프/재로드를 수정하고 실제 dependency 복구. mass/force revoke 금지 | 새 인증 거부/허용이 정책과 일치, 기존 session의 처리 계약 별도 증명, stale 파일·캐시 해소 |

audit 문제는 읽기와 쓰기 요청 모두에 영향을 줄 수 있습니다. 요청 성공만이 아니라 비밀 원문 없는 감사 상관관계를 확인합니다. [Vault audit 책임](https://developer.hashicorp.com/vault/docs/audit)

## 4. bounded 수동 실습과 gate

자기 소유 [LOCAL-DEV 환경](../shared/labs/README.md)에 학습자가 준비한 새 UUID KV/policy와 짧은 TTL child로 **권한 거부 사건**과 **TTL 만료 사건**을 수행합니다. 자동 runner가 내부에서 폐기한 child를 꺼내 재사용하지 않습니다. 별도 학습 auth flow와 안전한 token helper/비밀 전달을 먼저 준비하며, 없으면 수동 사건은 미실행으로 남깁니다. 총 5분·최대 20요청·동시성 1, 관찰용 child TTL은 실제 서버 응답에서 30–60초 범위임을 확인합니다. 실제 credential은 command line/문서에 쓰지 않습니다.

1. 정상 child의 허용 `data/item` read와 금지 metadata/list를 각각 1회 수행합니다. status는 정상인데 capability와 403이 다른 이유를 설명합니다. 정상 요청으로 복귀하고 금지 요청은 계속 거부되는지 확인합니다. 권한 확대를 원복으로 삼지 않습니다.
2. 별도 승인된 짧은 TTL child의 만료 전/후 허용 read를 관측합니다. TTL·서버 응답·Agent/client cache를 대조합니다. 실제 만료 token은 되돌릴 수 없으므로 동일 최소 권한 auth flow로 새 credential을 얻고 앱 회복을 확인합니다. 공유 token revoke나 root 재사용은 제외합니다.

실제 감사 장애·Raft partition·DR은 이 fixture에서 할 수 없습니다. 별도 영속 cluster·TLS·감사·키 보관·승인된 복구 계획이 있을 때만 심화 수행하고 Community/Enterprise/HCP 결과를 분리합니다. CPU quorum 실험이나 container restart를 HA 회복 증거로 제출하지 않습니다.

통과에는 정상 baseline, 두 사건의 경쟁 가설/배제 증거, 제한 조치·원복 또는 재발급, 동일 지표와 실제 소비자 회복이 필요합니다. VL01–04에 baseline·identity, VL05–08에 수명·소비자, VL09–12에 audit·HA·복구, VL13–14에 source와 운영 보고서를 연결합니다. 기존 28주·14모듈을 유지하며 dev만 실행한 경우 그 범위를 명확히 표시합니다.
