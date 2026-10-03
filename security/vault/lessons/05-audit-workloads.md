# 5강. HashiCorp Vault: 감사·관측·Agent·workload identity

[커리큘럼](../curriculum.md) · [공통 실습](../../shared/labs/README.md) · [소스 지도](../source-reading.md)


<a id="vl09"></a>
## VL09 — Audit, 가용성, 사고 분석

**선수:** VL03–08, 구조화 로그·correlation ID·파일 I/O. **불변식:** 비밀 원문을 유출하지 않으면서 어떤 주체의 어떤 요청이 승인/거부되었는지 추적해야 합니다.

audit와 operational log·metric은 다른 자료입니다. HMAC 처리되는 데이터가 있어도 경로·metadata·일부 비문자 값 등 모든 필드가 비밀 제거되는 것은 아닙니다. endpoint 예외와 device 옵션을 실제 문서에서 확인합니다. [Audit 문서](https://developer.hashicorp.com/vault/docs/audit)

### 추가 AUDIT-LAB

1. 합성 fixture에 전용 audit 출력을 준비합니다. 원문 로그를 Git이나 채팅에 붙이지 않고 허용된 필드만 별도 요약합니다.
2. 정상 read, policy deny, 만료 token, 존재하지 않는 경로의 요청을 수행하여 request/response를 상관시킵니다. raw token이나 인증 값으로 join하지 않습니다.
3. 감사 대상 요청에서 한 device 출력이 실패하는 경우와 모든 enabled device가 실패하는 경우를 비교합니다. 인증·인가 실패와 감사 출력 문제를 분리하고 가용성에 미치는 영향을 기록합니다.
4. failure injection은 실습 전용 device에만 제한합니다. 시스템 디스크 전체를 채우거나 공유 audit directory 권한을 바꾸지 않습니다.
5. metric의 latency·error·pending revocation·storage 상태가 실패 원장을 어떻게 보조하는지 설명합니다. 관측할 수 없는 내부 상태는 추론으로 표시합니다.

**원리 질문:** fail-closed 감사 경계는 보안과 가용성 사이에 어떤 의존성을 만드는가? 두 로그 사본이 있다고 변조 방지가 완성되는가? 특정 raw value의 HMAC을 확인하는 행위 자체에 어떤 권한과 노출 위험이 있는가?

**반례:** “로그에 성공 응답 없음 → secret 발급 없음”, “HMAC이므로 모든 로그 공개 가능”, “health endpoint 정상 → 모든 요청 감사 정상” 각각의 경쟁 가설을 작성합니다.

**통과:** 4개 요청의 비식별 상관 기록, device 실패 상태표, 관측 공백 3개, incident timeline. 실제 device 실패를 수행하지 않았다면 설계 제출입니다.

<a id="vl10"></a>
## VL10 — Agent와 workload identity: 전달 후가 더 중요하다

Agent/Proxy는 auth·renew·template·cache 등의 client 통합을 돕지만 앱의 권한 모델과 secret 소비 계약을 없애지 않습니다. bootstrap identity→로그인 token→secret lease→template 파일→app reload→외부 연결을 각각 추적합니다. [Agent/Proxy 문서](https://developer.hashicorp.com/vault/docs/agent-and-proxy)

### 추가 WORKLOAD-LAB

- 전용 합성 app와 파일 위치·소유권·권한을 정합니다. 실제 credentials를 환경변수 dump, crash report, process argument, Git에 남기지 않습니다.
- auth 성공 직후 app가 아직 옛 값을 사용하도록 지연을 만들고, template 렌더링 시각과 실제 app reload 시각을 별도로 측정합니다.
- server 일시 불가, auth role 변경, lease renewal 거부, 파일 쓰기 실패, app reload 실패를 독립적으로 주입합니다. 한 실패가 다른 모든 단계의 실패와 같다고 가정하지 않습니다.
- 파일이 갱신되어도 오래된 DB connection은 남을 수 있습니다. 새 credential로 새 연결 성공, 옛 credential로 새 연결 거부, 기존 connection 처리를 각각 확인합니다.
- workload 교체·scale-out·종료 시 identity와 token·lease가 어떻게 정리되는지 원장으로 검산합니다. shutdown hook 성공을 항상 보장하는 설계를 피합니다.

### 시간 예산 연습

합성 서비스에서 credential TTL을 T, renew 시도 시작을 R, 최대 재시도·jitter·network budget을 B, template+reload 상한을 A로 놓습니다. `R+B+A < T`를 기대 조건으로 제시하되 실제 TTL 변경, clock uncertainty, 정책 변경으로 깨질 수 있음을 시험합니다. 상한을 측정하지 못했다면 보장 대신 가설로 표현합니다. CPU `lease-clock`은 이 분산 시간선을 구현하지 않습니다.

**Vault 확장:** Vault Agent/Proxy와 외부 Kubernetes injector/operator를 구분합니다. injector 설치 성공을 auth role 최소 권한·secret rotation·앱 reload 완료로 취급하지 않습니다.

**소스 과제:** renew loop, backoff, template render, sink write, process reload 중 선택한 두 경로를 읽습니다. 라이브러리가 별도 module이면 revision을 추가합니다.

**통과:** 6단계 수명 원장·옛/새 credential의 소비자 결과·실패 2종과 회복·허용 가능한 stale interval. 자동으로 배포되는 workload 환경은 제공하지 않습니다.
