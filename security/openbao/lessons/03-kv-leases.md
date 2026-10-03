# 3강. OpenBao: KV v2·CAS·lease·동적 자격 증명

[커리큘럼](../curriculum.md) · [공통 실습](../../shared/labs/README.md) · [소스 지도](../source-reading.md)


<a id="ob05"></a>
## OB05 — KV v2 버전과 compare-and-set

**선수:** OB04, 동시 쓰기·lost update. **불변식:** 읽은 버전에 기반한 변경이 다른 성공한 갱신을 몰래 덮지 않아야 합니다. KV version, secret 값 내부의 업무 version, token TTL을 혼동하지 않습니다.

[KV v2 문서](https://openbao.org/docs/secrets/kv/kv-v2/)를 읽고 최신 버전, 명시적 과거 버전, CAS, metadata, 삭제 상태를 구분합니다. soft delete는 해당 버전의 읽기를 막는 상태이며 undelete와 짝을 이루지만 destroy는 복원할 원문을 없애는 별도 동작입니다. 파괴 실험은 새 합성 key에만 제한합니다.

### 실제 엔진 실험과 선택 원리 모형

1. `kv-cas`의 v1을 두 writer가 읽는 시간표를 손으로 만듭니다. A가 CAS=1로 v2를 만든 뒤 B의 CAS=1이 실패해야 한다는 oracle를 제출합니다.
2. 실제 dev fixture에서는 두 독립 호출의 version metadata와 오류를 기록합니다. count나 “HTTP가 왔다”만으로 성공 판정하지 않습니다.
3. B는 v2를 다시 읽고 업무 병합 정책으로 재계산합니다. 무조건 마지막 값을 덮는 재시도를 “CAS가 있으므로 안전”이라고 부르지 않습니다.
4. CAS=0은 새 key 생성 조건과 연결해 시험합니다. 버전이 soft-delete되었다고 존재 이력이 사라지는 것은 아니므로 새 키와 삭제된 기존 키를 구별합니다.
5. 새 전용 key에서 v1/v2를 만든 뒤 v2 soft-delete→v1 명시 조회→v2 undelete를 비교합니다. destroy는 별도 합성 버전 하나에만 수동 수행하고 undelete로 내용이 돌아오지 않음을 확인합니다.
6. 응답 유실 실험에서는 client가 성공 응답을 못 봤어도 version은 올라갔을 수 있습니다. 재조회·CAS·업무 요청 ID를 조합한 판정 규칙을 설계합니다.

**소스 과제:** CAS 검사와 version 갱신의 원자적 경계를 찾습니다. 두 단계를 별도 무보호 작업으로 구현한 잘못된 모형과 비교합니다. 제품 plugin 코드가 core와 다른 module/revision이면 따로 기록합니다.

**통과:** 동시 writer 시간표, 실패 후 재읽기 결과, 6종 상태(new/current/old/deleted/undeleted/destroyed) 판정표, 파괴 대상의 정확한 fixture ID를 제출합니다.

<a id="ob06"></a>
## OB06 — Lease, renew, revoke와 외부 DB

**불변식:** 만료된 권한을 “아직 서버가 바쁘니 유효할 것”이라고 사용하지 않아야 하며, backend 폐기 완료는 별도 관측해야 합니다. TTL은 client가 요청한 숫자 자체가 아닙니다. server가 발급·갱신한 실제 값과 role/mount/system 제약을 확인합니다. [Lease 문서](https://openbao.org/docs/concepts/lease/)

### 선택 모형과 실제 LIFECYCLE-LAB의 경계

`lease-clock`은 결정적인 시계 입력을 받는 수명 모형입니다. 실제 scheduler, network latency, clock skew, DB plugin의 revocation 재시도를 구현하지 않습니다. CPU의 expired 표식을 DB 계정 삭제로 해석하지 않습니다.

추가 DB 환경은 전용 합성 database와 제한된 관리 계정을 사용합니다. root/superuser가 편하다는 이유로 운영 계정을 연결하지 않습니다.

- 발급 credential로 새 연결 성공을 확인하고 token alias·lease alias·외부 사용자 alias를 연결합니다. 암호는 기록하지 않습니다.
- 이른 renew, max TTL 근처 renew, 비갱신 lease, 만료 뒤 renew를 비교합니다. 요청한 increment가 그대로 수락된다는 가정을 반증합니다.
- revoke 요청 시 DB 연결 불가 조건을 별도 fixture에 주입합니다. 서버 상태와 DB 계정/새 연결 가능성을 각각 기록합니다.
- 폐기 전 생성한 기존 DB connection과 폐기 후 새 connection을 구분합니다. DB의 계정 삭제/권한/세션 계약에 따라 기존 세션이 남을 수 있어 실제 쿼리와 재연결을 각각 검산합니다.
- batch token·PKI·static KV의 수명을 일반 dynamic secret lease에 억지로 맞추지 않습니다. 해당 engine의 문서와 관측으로 분류합니다.

**구술:** 짧은 TTL이 왜 rotation 운영을 제거하지 않는가? auth token 갱신 성공만으로 DB lease가 갱신되었는가? server outage 중 앱의 허용된 행동·실패 닫힘 정책은 무엇인가?

**OpenBao 과제:** OpenBao의 expiration manager와 해당 DB plugin을 함께 추적합니다. Vault에서 관측한 retry 동작을 가져오지 말고 2.7.1 환경에서 확인합니다.

**통과:** issue→renew→expire→revoke 요청→외부 반영→소비자 전환의 시간선, 지연/실패 2종, 외부 credential 잔존 검사. 실제 DB를 실행하지 않았으면 설계 제출로 표시합니다.
