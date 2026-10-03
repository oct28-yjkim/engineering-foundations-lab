# 2강. HashiCorp Vault: identity·auth·ACL·token

[커리큘럼](../curriculum.md) · [공통 실습](../../shared/labs/README.md) · [소스 지도](../source-reading.md)


<a id="vl03"></a>
## VL03 — Identity와 인증의 계약

**선수:** JWT claim, TLS trust, workload identity의 bootstrap. **불변식:** “유효한 서명”뿐 아니라 이 workload를 위한 issuer·audience·subject/role binding이 맞아야 로그인할 수 있어야 합니다.

사람의 OIDC 로그인과 서비스의 AppRole/JWT/Kubernetes 인증을 구분합니다. 외부 identity, auth mount, alias, entity, group, policy, 발급 token을 하나의 ID로 합치지 않습니다. 이름을 재사용하거나 auth mount를 다시 만들 때 기존 identity 연결이 어떻게 달라지는지는 제품별 실험 대상입니다.

### 추가 AUTH-LAB

1. 합성 identity `orders-dev`, `orders-prod`, `auditor`와 각각의 허용 경로를 먼저 정의합니다.
2. 사용할 auth method 하나를 선택하고 토큰/claim 원문 없이 issuer·audience·role binding·TTL·mount accessor의 검산 항목을 기록합니다.
3. 정상 claim, 다른 audience, 다른 namespace/subject, 만료, 위조 서명, 폐기된 외부 identity를 각각 시험합니다. 지원하지 않는 음성 케이스는 미검증으로 남깁니다.
4. 재로그인 후 기존 token이 자동 무효화되었다고 가정하지 않습니다. 두 token을 별도 alias로 추적하고 수명·명시적 폐기·외부 identity 변경의 영향을 구별합니다.
5. AppRole 확장에서는 RoleID와 SecretID 전달·wrap·unwrap·재사용 실패를 분리합니다. 값을 화면·argv·로그에 노출하는 편의 스크립트를 만들지 않습니다.

**통과:** 로그인 성공 하나로 끝내지 않고 최소 4개 잘못된 증거의 거부, 발급 후 권한 검사, identity mapping 변경 시나리오를 제출합니다. [공식 인증 개념](https://developer.hashicorp.com/vault/docs/concepts/auth)에서 선택 method의 계약으로 이동합니다.

<a id="vl04"></a>
## VL04 — ACL selector, capability, token tree

CPU `exact-acl`은 exact path만의 결정 모형입니다. 실제 제품의 path 우선순위, glob `*`, segment wildcard `+`, templated policy와 parameter 제약을 구현하지 않습니다. glob은 정규식이 아닙니다. 선택되는 path 규칙과 동일 selector의 capability 결합을 먼저 판정하고, 그 결과에서 명시적 deny를 검토합니다. 단순히 모든 일치 패턴의 allow를 합치는 모형은 제품 oracle이 아닙니다. [정책 문서](https://developer.hashicorp.com/vault/docs/concepts/policies)

### 합성 fixture의 최소 정책

KV v2 mount를 `lab-kv`로 준비했을 때 다음은 특정 secret의 data 읽기만 표현하는 예입니다. 실제 fixture의 mount 이름은 [실습 안내](../../shared/labs/README.md)를 따릅니다.

```hcl
path "lab-kv/data/orders/config" {
  capabilities = ["read"]
}
```

서버 관리 주체가 이 정책을 부여한 제한 token을 준비한 뒤 data 읽기 허용, 같은 경로 쓰기 거부, `payments/config` 읽기 거부, metadata list 거부를 검산합니다. list를 허용하는 추가 실험에서는 key 이름이 다른 read 정책에 따라 숨겨질 것이라 가정하지 않습니다. 민감 정보를 경로명에 넣지 않습니다.

### 심화 실험

- exact·prefix·segment selector가 충돌하는 정책 쌍을 만들고 문서 우선순위로 예상 결과를 손으로 계산합니다. 실제 token으로 결과를 대조합니다.
- `data`, `metadata`, `delete`, `undelete`, `destroy`는 KV v2에서 서로 다른 API 권한 경계임을 확인합니다.
- service/batch, parent/child, orphan, periodic/explicit max TTL은 다른 축입니다. 선택 token 유형에서 실제 제공되는 lookup·renew·revoke 행위를 확인하고, 부모 폐기 시 자식과 lease 영향을 시간선으로 기록합니다.
- token 발급·정책 수정·재로그인·token 폐기 네 사건을 섞지 않습니다. `sudo` capability를 모든 경로의 전역 관리자 권한으로 해석하지 않습니다.

**Edition 과제:** Vault namespaces는 Enterprise 문서의 범위로 표시합니다. Community에서 경로 prefix를 나눈 것을 별도 namespace와 같은 격리라고 부르지 않습니다. [Vault namespaces](https://developer.hashicorp.com/vault/docs/enterprise/namespaces)

**통과:** 주체×경로×연산×시간의 최소 12행 행렬, 허용/거부의 실제 결과, token tree와 폐기 원장을 제출합니다. [운영 실습](../operations.md)에서 status·capability·sanitized audit로 403의 경쟁 가설을 구분합니다. CPU 모형을 선택했다면 누락 기능도 별도 기록하되 모형 실행은 필수가 아닙니다.
