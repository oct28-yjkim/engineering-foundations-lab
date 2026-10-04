# OpenBao 운영 실습: 접근 거부·수명·감사·Raft 진단

[시작](README.md) · [커리큘럼](curriculum.md) · [공통 수집·안전 규약](../shared/operations.md) · [사고 보고서](../../operations/incident-report-template.md)

기본은 **OpenBao 2.7.1의 실제 baseline과 troubleshooting**입니다. CPU 모형은 선택 부록이며 Vault 측정치를 OpenBao 증거로 대체하지 않습니다. read-only부터 시작하고 이 문서를 읽는 것만으로 서버·계정·키가 생성되지는 않습니다.

<a id="basic-lab"></a>

## 기본 LAB: 정상 동작에서 장애 복구까지

**정상 기능 → 동작 원리 → 관측 → 제약 → 진단·복구** 순서의 입문 카드입니다. 최소 권한 child로 정상 KV 읽기를 확인한 뒤 capability·서버 상태·TTL과 소비자 동작을 연결합니다. [공통 LAB 계약](../../operations/lab-contract.md)에 따라 정상 결과를 먼저 검산한 뒤 아래 상세 절차로 진행합니다. 28주 심화는 선수 조건이 아니며, 이 카드 추가가 새 자동 실행기 제공이나 실제 장애 검증 완료를 뜻하지 않습니다.

| 단계 | 실행·관측·판정 |
| --- | --- |
| 정상 기능부터 | [공통 LOCAL-DEV 실습](../shared/labs/README.md)의 자기 UUID KV v2/policy를 준비합니다. 허용된 `data/item` 읽기의 합성 값/버전과 금지 metadata/list의 거부를 확인합니다. root가 아니라 준비한 최소 권한 child를 기준으로 정상 계약을 기록합니다. |
| 동작 원리 | 인증 주체→policy capability→KV 경로/버전→token/lease 수명을 연결합니다. 서버 unsealed 상태와 개별 요청의 권한·유효기간은 다른 경계이며 만료 token의 복구는 과거 값을 되살리는 작업이 아닙니다. |
| 직접 볼 지표·방법 | 아래 `bao status`, capability 조회·응답 종류·TTL/client 시간선을 관측합니다. 승인된 경우에만 sys/metrics/audit/Raft를 읽고 원명·실제 sink/TYPE을 확인합니다. OpenBao의 실제 metric prefix 설정을 확인하며 비밀 원문은 남기지 않습니다. |
| 먼저 확인할 제약 | dev는 in-memory·단일 노드·자동 unseal이며 TLS/감사/Raft 복구를 제공하지 않습니다. 수동 사건은 새 child/auth flow와 안전한 token 전달을 준비해야 합니다. 5분·20요청·동시 1·실제 응답 TTL 30–60초 상한을 지킵니다. |
| 자주 마주치는 사건 2개 | 아래 권한 거부 사건: 정상 status와 허용/금지 path capability·403을 비교해 서버 불가와 ACL을 나눕니다. TTL 사건: 별도 child의 만료 전/후 같은 허용 요청을 비교해 만료·client cache·대상 오류를 구분합니다. |
| 조치와 회복 oracle | 권한을 넓히지 않고 원래 허용 요청으로 복귀합니다. 만료 후에는 같은 최소 권한 정상 auth flow로 새 child를 얻어 합성 값/버전 일치·금지 path 거부·실제 client 사용을 검산합니다. 공유 token revoke나 root 대체는 하지 않습니다. |
| 제공물·추가 준비 | 격리 dev Compose·KV/ACL fixture·아래 수동 지침을 제공합니다. 자동 runner가 폐기한 child를 재사용하지 않습니다. TTL auth 준비가 없으면 미실행이며 audit 장애·Raft·독립 restore는 별도 영속 환경 LAB입니다. |

두 사건의 결과가 예상과 다르면 관측한 상태를 기록하고 발생기/변경부터 멈춥니다. 정상 baseline·사건별 경쟁 가설·제한 조치·회복 oracle·미실행 범위를 [사건 보고서](../../operations/incident-report-template.md)에 남깁니다.

## 1. 대상 확인과 읽기 전용 명령

기존 승인된 환경의 endpoint·CA·CLI 인증 세션과 제품 version을 먼저 확인합니다. `BAO_ADDR` 같은 환경 설정의 **이름과 대상 별칭**을 검토하되 환경 전체와 token 값을 출력하지 않습니다. 아래 명령은 그 사전 확인 이후에만 실행합니다.

```text
bao version
bao status -format=json
bao token capabilities sys/metrics
bao token capabilities sys/audit
bao token capabilities sys/storage/raft/configuration
```

`status`의 `initialized`, `sealed`, `standby`/HA 정보, `storage_type`, `version`과 CLI exit code를 분리해서 기록합니다. 필드가 배포에 없으면 없는 것으로 남깁니다. sealed/uninitialized 상태를 API rate limit이나 단순 login failure로 처리하지 않습니다. `status`는 secret 읽기를 증명하지 않습니다. [status CLI](https://openbao.org/docs/commands/status/)

필요한 read/list 또는 해당 endpoint가 요구하는 sudo 권한을 운영자가 이미 승인한 경우에만 다음을 수행합니다. metrics는 현재 active node의 telemetry 계약을 확인합니다. 지원되지 않는 storage에서는 Raft 명령을 생략합니다.

```text
bao read -format=json sys/metrics
bao audit list
bao operator raft list-peers
```

`audit list`는 감사 장치의 설정 목록이지 성공적인 감사 기록을 증명하지 않습니다. peer 목록의 node/address는 외부 보고서에서 별칭으로 바꿉니다. dev fixture는 inmem·단일 node·logging none이므로 Raft/audit를 검증한 것으로 쓰지 않습니다. endpoint가 403이면 필요 권한을 기록하고 중단하며 모니터링을 위해 root를 재사용하지 않습니다.

HTTP 관측은 승인된 모니터의 **GET `/v1/sys/health`** 결과를 node별로 비교합니다. status code를 임의 매핑하는 query parameter/LB rule이 있는지 확인하고 `initialized/sealed/standby` body와 함께 읽습니다. 전체 코드 표를 Vault에서 복사하지 않고 선택 OpenBao revision의 API/구현을 대조합니다. [OpenBao health API](https://openbao.org/api-docs/system/health/)

## 2. 핵심 지표

다음은 공식 지표 원명입니다. OpenBao 2.7.x의 기본 metric prefix는 **`vault`**이며 `metrics_prefix`로 변경될 수 있습니다. Prometheus의 실제 이름·label·TYPE을 scrape에서 확인합니다. `openbao_`로 일괄 치환하거나 Vault dashboard가 그대로 호환된다고 가정하지 않습니다. standby·인증·retention도 해당 설정을 대조합니다. [OpenBao telemetry 설정](https://openbao.org/docs/configuration/telemetry/)

| 관측값 | 유형·단위 | 창과 진단 질문 |
| --- | --- | --- |
| `vault.core.unsealed`, `vault.core.active` | gauge, 0/1 | node별 30초 snapshot·5분; 봉인인가 standby인가, LB가 다른 node를 보는가? |
| `vault.core.handle_request`, `vault.core.handle_login_request` | summary, ms | 5분의 count/sum·사용 가능한 node quantile; auth만 느린가 모든 요청인가? |
| `vault.core.in_flight_requests` | gauge, 요청 수 | 정상 부하와 같은 창; client retry 폭증인가 backend 대기인가? |
| `vault.expire.num_leases`, `vault.expire.num_irrevocable_leases` | gauge, lease 수 | 실제 refresh 주기를 포함한 추이; issuance 증가인지 외부 revoke 실패인지? |
| `vault.expire.lease_expiration.error` | counter, 오류 건수 | Prometheus 누적 시계열이면 5분 증가/초당 rate; 외부 DB/API 실패와 상관 |
| `vault.audit.log_request_failure`, `vault.audit.log_response_failure` | counter, 오류 건수 | sink별 표현을 먼저 확인; 감사 장치·스토리지 오류와 요청 실패를 상관 |
| `vault.ha.rpc.client.forward.errors` | counter, 오류 건수 | standby forwarding 경로·network 증상; peer 역할과 함께 판단 |

각 지표의 의미는 [core](https://openbao.org/docs/internals/telemetry/metrics/core-system/), [lease 전체 목록](https://openbao.org/docs/internals/telemetry/metrics/all/), [audit](https://openbao.org/docs/internals/telemetry/metrics/audit/), [HA](https://openbao.org/docs/internals/telemetry/metrics/availability/)에 근거합니다. audit 전역/장치별 실패 의미를 실제 버전에서 확인하고 단일 장치 실패와 전체 감사 불능을 같게 취급하지 않습니다. Raft storage라면 voter 목록·실제 leader·disk 여유 bytes·I/O latency·peer network를 함께 보고 quorum 산술만으로 가용성을 판정하지 않습니다.

## 3. 증상별 조사와 회복

| 증상 | 경쟁 가설·확인 순서 | 완화와 원복 경계 | 회복 판정 |
| --- | --- | --- | --- |
| 403/로그인 실패 증가 | 만료 token / API 경로·namespace 오지정 / ACL 변경 / auth claim 불일치. status→자기 capability→sanitized audit→Agent 갱신 로그 | 시험 client의 경로/정책 revision 하나만 수정. 이미 만료된 token은 되살리지 않고 원래 auth flow로 재발급. root·wildcard grant 금지 | 최소 권한 정상 요청 성공, 금지 path는 계속 거부, 갱신 후 소비자 정상 |
| 요청이 느리고 감사 오류 동반 | audit destination 불가 / disk·permission / backend I/O / retry 폭주. request latency·audit failure·장치 상태·자원 대조 | 승인된 audit destination 가용성/용량 복구·발생기 제한. 감사 비활성화나 로그 삭제 금지; 변경한 destination 설정은 검토된 revision으로 원복 | 감사 request/response 연계와 오류 증가 정지, 동일 부하 latency 회복, 누락 감사 범위 공개 |
| lease 증가·만료 뒤 접근 지속 | 발급 루프 / 갱신 정책 / backend revoke 실패 / 기존 consumer session 재사용. issuance 원장→lease gauges→plugin 오류→외부 신규 인증/기존 session 분리 | 시험 client의 발급 루프 중단·dependency 복구·합성 credential만 승인 절차로 처리. force revoke로 원장을 없애지 않음 | 새 최소 권한 발급/갱신 정상, 폐기된 credential의 새 인증 거부, 남은 session 계약 설명 |
| active 없음·standby에서 지연 | sealed node / quorum 또는 cluster 통신 손실 / storage stalls / LB 대상 오류. node별 status→peer→disk/network→forward errors | 공유 node를 seal/재시작하지 않음. 격리 lab의 변경 네트워크 규칙·서비스 설정만 원복. peer 강제 제거 금지 | 실제 leader·의도 voter 회복, 제한 synthetic read/write 검산, 데이터·외부 상태 확인 |

## 4. 개인 lab의 두 수동 사건

기존 [LOCAL-DEV 환경](../shared/labs/README.md)에 학습자가 준비한 자기 새 UUID fixture와 짧은 수명 최소 권한 child만 사용합니다. 자동 runner가 내부에서 폐기한 child를 꺼내 재사용하지 않습니다. 별도 학습 auth flow와 안전한 token helper/비밀 전달을 먼저 준비하며, 없으면 수동 사건은 미실행으로 남깁니다. token 값을 보고서에 쓰지 않습니다. 총 5분·최대 요청 20개·동시성 1, 관찰용 child TTL은 실제 서버 응답에서 30–60초 범위임을 확인합니다. 기존 자산 이름과 충돌하거나 예상 밖 권한이 보이면 중단합니다.

1. **경로/권한 거부**: child의 허용 `data/item` 조회 1회와 금지 metadata/list 1회를 비교합니다. status 정상 + capability/403 조합으로 서버 불가 가설을 배제합니다. 원복은 정책 확대가 아니라 원래 허용 요청으로 돌아가는 것입니다. value를 제출하지 않고 버전·합성 oracle 일치 여부만 기록합니다.
2. **수명 만료**: 별도 승인된 짧은 TTL child의 만료 전 허용 요청과 TTL 후 요청을 1회씩 관찰합니다. 서버 시각/응답·TTL·client 캐시 상태를 대조하고 정상 auth flow로 새 최소 권한 child를 얻어 회복을 확인합니다. 사용 중인 token revoke나 namespace 전체 폐기는 하지 않습니다. 만료 전/후 상태를 조작한 CPU 시계는 제품 측정을 대신하지 못합니다.

audit 장애·Raft partition·독립 restore는 영속/TLS/감사 구성과 별도 키 보관자를 갖춘 격리 환경의 심화 과제이며 이 dev fixture에서는 실행 불가입니다. baseline+두 사건+회복 증거로 운영 gate를 평가하되 dev 범위만 통과했다고 명시합니다. OB01–04 baseline/인가, OB05–08 수명·소비자, OB09–12 감사/HA/복구, OB13–14 source와 운영 보고서로 연결합니다.
