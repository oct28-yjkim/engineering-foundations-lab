# 4강. HashiCorp Vault: Transit·암호·PKI·인증서 수명

[커리큘럼](../curriculum.md) · [공통 실습](../../shared/labs/README.md) · [소스 지도](../source-reading.md)


<a id="vl07"></a>
## VL07 — Transit: 암호 연산과 키 수명

**선수:** 암호화·서명·MAC·encoding의 차이, AEAD의 무결성, 키 버전. **불변식:** 올바른 주체와 컨텍스트에서만 필요한 암호 연산이 가능하고, 변조·잘못된 키/컨텍스트는 실패해야 합니다.

Transit을 secret 원문 저장소나 모든 클라우드 KMS와 동일한 API라고 부르지 않습니다. 애플리케이션 ciphertext 보관과 server-side key 관리의 책임을 나누고, 암호화·복호화·서명·검증 중 선택한 key type이 지원하는 연산만 실험합니다. [Transit 문서](https://developer.hashicorp.com/vault/docs/secrets/transit)

### 추가 CRYPTO-LAB — 검증된 구현을 사용

1. 합성 평문과 별도 key를 준비합니다. 원문 대신 fixture label과 길이만 보고서에 남깁니다. encode/decode를 encryption/decryption으로 잘못 표현하지 않습니다.
2. encrypt→decrypt 결과가 입력 bytes와 같은지 메모리에서 검산하고, ciphertext 변조·다른 key·잘못된 context를 음성 대조군으로 둡니다. 알고리즘별 조건을 문서로 확인합니다.
3. encrypt-only와 decrypt 가능한 주체를 분리합니다. 암호화 API 성공을 복호화 권한 증명으로 쓰지 않습니다.
4. v1 ciphertext를 보관한 채 key를 v2로 rotate합니다. 새 암호문의 version과 기존 v1의 복호화 가능성을 따로 확인합니다. rotation은 이미 저장한 ciphertext를 자동으로 바꾸지 않습니다.
5. rewrap을 별도 시도하여 앱이 평문을 직접 받지 않는 경로와 결과 version을 확인합니다. 단순히 prefix만 바꾼 암호문은 유효한 rewrap이 아닙니다.
6. minimum decryption version 등의 제한은 과거 암호문 접근을 막을 수 있습니다. 먼저 합성 fixture의 복구 계획을 작성하고, 이전 ciphertext 처리 상태를 모르는 운영 key에는 적용하지 않습니다.

**원리 질문:** nonce·associated context·derived key가 보호하는 성질은 무엇인가? “key를 외부로 export하지 않음”이 “authorized decrypt API로 평문을 얻을 수 없음”을 의미하는가? key 백업과 애플리케이션 ciphertext 백업은 어떤 조합이어야 복구 가능한가?

**소스 과제:** API 입력 검증→권한→key version 선택→암호 primitive 호출→응답 포맷을 추적합니다. CPU 실험에 암호 구현이 없다는 점을 명시하며, 교육용 XOR·직접 구현한 AES/Shamir를 보안 증거로 제출하지 않습니다.

**통과:** round-trip·변조 거부·권한 거부, rotate 전후 version 행렬, 기존 데이터 migration 계획과 미처리 ciphertext 수를 제출합니다. 고정 ciphertext bytes를 oracle로 삼기보다 지원 알고리즘의 의미를 검산합니다.

<a id="vl08"></a>
## VL08 — PKI: 발급·신뢰·만료·폐기

**불변식:** 인증서는 의도한 subject/SAN·용도·유효 기간·trust chain 안에서만 소비되어야 합니다. 서명된 인증서를 얻는 것과 특정 TLS client가 올바르게 검증하는 것은 별도 사건입니다. [PKI 문서](https://developer.hashicorp.com/vault/docs/secrets/pki)

### 추가 PKI-LAB

격리된 실습 CA와 `*.invalid` 같은 합성 이름을 사용합니다. 운영 trust store에 CA를 추가하지 않습니다. private key·CSR 내 식별정보·실제 SAN을 저장소에 넣지 않습니다.

| 사건 | 독립 관측 |
| --- | --- |
| 허용 SAN 발급 | SAN·EKU·issuer·기간과 role 제한 검산 |
| 미허용 SAN 요청 | 발급 거부; 다른 role로 우회 성공시키지 않음 |
| 올바른 chain 접속 | client의 hostname·chain 검증 성공 |
| 다른 hostname/CA/만료 | certificate가 존재해도 client 거부 |
| revoke와 CRL 갱신 | 서버 기록·CRL serial·게시 상태 각각 관측 |
| 소비자 폐기 검사 | 해당 client가 최신 CRL/OCSP를 실제 사용하는지 검증 |

CA/issuer rotation에서는 새 chain 발급, 기존 chain 신뢰, intermediate 배포, client reload, 폐기 정보 배포를 분리합니다. 짧은 TTL은 최대 노출 시간을 줄이는 수단이지 시간 동기화·재발급·trust distribution을 제거하는 수단이 아닙니다.

**Vault 확장:** 이 과정의 기본 PKI 결과는 Community에 한정합니다. Enterprise의 추가 PKI 기능이나 managed 서비스 운영을 같은 실행 결과에 포함하지 않습니다.

**반증 과제:** 서버의 revoke 성공 후에도 기존 연결이나 폐기 검사를 하지 않는 client가 왜 즉시 종료되지 않을 수 있는지 재현 설계로 보여 줍니다. 공격 도구 없이 자신의 합성 인증서·로컬 client만 사용합니다.

**통과:** 발급 행렬·client별 검증 설정·만료/폐기 시간선·issuer rotation rollback 조건. LOCAL-DEV의 단순 KV 성공은 암호/PKI gate를 충족하지 않습니다.
