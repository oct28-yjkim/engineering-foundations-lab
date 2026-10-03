# 1강. OpenBao: 위협 모델·core·barrier·seal

[커리큘럼](../curriculum.md) · [공통 실습](../../shared/labs/README.md) · [소스 지도](../source-reading.md)


<a id="ob01"></a>
## OB01 — 위협 모델과 core 요청 경로

**선수:** 프로세스·파일 권한, HTTP/TLS, 인증과 인가의 차이. **불변식:** 승인된 주체가 승인된 연산을 하는 경우에만 합성 secret을 얻어야 합니다. 저장소 암호화와 API 접근 제어를 별개 축으로 설명합니다.

자산을 secret 원문, token, lease, policy, seal 자산, audit log, snapshot으로 나눕니다. 위협 주체도 익명 client, 제한된 token 보유자, storage 독자, server host 관리자, bootstrap/root 관리자로 구분합니다. 특히 unsealed 서버는 요청을 처리하기 위해 필요한 복호화 능력을 갖습니다. storage ciphertext의 보호를 host 침해나 root 권한 오남용의 해결책으로 확장하지 않습니다. [공식 보안 모델](https://openbao.org/docs/internals/security/)

### 실험 설계

1. 주문 서비스가 DB credential을 받는 경로에 TLS 종료점, auth verifier, identity, policy, engine, barrier, physical storage, 외부 DB를 표시합니다.
2. “암호화된 snapshot만 유출”, “정상 app token 유출”, “host 관리자 침해”에 대해 가능한 행위와 탐지 지점을 각각 작성합니다.
3. 별도 AUTH-LAB에서는 read-only app와 관리 주체를 분리합니다. 같은 secret에 대한 읽기 허용·쓰기 거부·다른 경로 거부를 실제 token으로 확인합니다. root 성공 출력은 대조군이 아닙니다.
4. 응답 timeout을 삽입하는 확장 과제에서는 미확정 결과를 원장에 남기고 현재 상태 재조회로 판정합니다. 재시도만으로 중복 발급이 없어졌다고 가정하지 않습니다.

**소스 과제:** [읽기 지도](../source-reading.md)에서 HTTP→core routing→token/ACL→logical engine→barrier→physical backend를 찾습니다. 각 단계에서 정책상 거부와 storage 오류가 어디서 결정되는지 두 경로를 추적합니다. source를 읽은 것과 실행한 것을 분리합니다.

**통과:** 5개 위협 주체와 최소 6개 자산을 포함한 경계표, 요청 하나의 경로, 음성 대조군 3개, 미보호 영역을 제출합니다.

<a id="ob02"></a>
## OB02 — Barrier, seal, key custody

init는 새로운 저장 상태의 초기 설정, unseal은 필요한 키 접근 복구, rekey는 seal 관련 키 분배 변경, barrier rotation은 저장 암호화 keyring 변경이라는 구별에서 시작합니다. auto-unseal 환경의 recovery key는 외부 seal/KMS 키가 완전히 사라져도 데이터를 복호화하는 만능 대체품이 아닙니다. 정확한 키 계층과 동작 조건은 [seal 문서](https://openbao.org/docs/concepts/seal/)와 고정 소스에서 대조합니다.

### 추가 SEAL/RESTORE 과제 — dev 모드로 실행 불가

- disposable 영속 환경과 합성 데이터, key 보관 담당자를 별도로 준비합니다. share 원문은 보고서에 넣지 않고 담당자 alias·threshold·custody 확인만 기록합니다.
- 초기화 전, 초기화 후 sealed, threshold 미달, unsealed, 재시작 후 상태를 표로 예측합니다. Shamir 조건에서 임계치 충족 전 secret 요청 거부를 확인합니다.
- rekey와 key rotation을 각각 별도 새 fixture에서 수행하여 이전 share, 기존 데이터, 새로운 쓰기, 재시작, 복원에 미치는 영향을 비교합니다. 운영 key를 연습 대상으로 사용하지 않습니다.
- auto-unseal은 선택 환경입니다. KMS 인증 실패, 네트워크 불가, 키 비활성화/유실을 구별한 설계서를 먼저 작성합니다. 실제 클라우드 변경은 별도 승인·비용·복구 계획 없이는 수행하지 않습니다.

**구술:** sealed 데이터가 존재한다는 사실과 사용할 수 있다는 사실은 왜 다른가? quorum이 있는데 seal key가 없으면 무엇이 가능한가? rekey 후 snapshot 복원에서 어떤 custody 자료를 확인해야 하는가?

**반증:** “암호화 backup이 있으므로 복구 가능”을 seal 자산 없는 복원 target으로 반박하는 설계를 제출합니다. 실제 복원하지 않았다면 미검증입니다.

**OpenBao 확장:** 현재 문서의 seal·storage 기능을 과거 Vault 운영 절차로 대체하지 않습니다. OpenBao 2.7.1의 지원 backend와 key lifecycle 변경은 릴리스·source 기준으로 확인합니다.

**완료물:** 키를 포함하지 않는 상태 전이표, 실패 원장, 별도 복원 조건, 5개 핵심 용어의 반례. 제공 LOCAL-DEV는 자동 초기화·unseal·메모리 저장이므로 이 모듈의 실증을 대신하지 않습니다.
