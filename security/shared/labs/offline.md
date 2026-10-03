# CPU 모델: 권한·버전·만료·quorum의 경계를 반례로 이해하기

[공통 실습](README.md) · [OpenBao](../../openbao/README.md) · [Vault](../../vault/README.md) · [구현](offline_lab.py) · [테스트](test_offline_lab.py)

Python 3.10 이상과 표준 라이브러리만으로 실행한다. 패키지 설치·Docker·클라우드·API key·네트워크·파일 읽기/쓰기·외부 프로세스·실제 시계가 필요 없다. 아래 `-B`는 bytecode cache 생성도 막는다. 입력은 공개된 가상 문자열과 정수이며 **운영 secret을 넣지 않는다**.

네 모델은 제품의 호환 구현이나 보안 검증 도구가 아니다. 내부 계약에 대한 정답을 작은 입력으로 계산하고, 제품에서 추가로 확보해야 하는 증거를 식별하는 도구다. 암호화·Shamir secret sharing을 자체 구현하지 않는다.

```bash
# 저장소 루트에서 실행
python -B security/shared/labs/offline_lab.py --list
python -B security/shared/labs/offline_lab.py --lab all
python -B -m unittest discover -s security/shared/labs -p test_offline_lab.py -v
python -B -O -m unittest discover -s security/shared/labs -p test_offline_lab.py -v
```

실행 이름은 `exact-acl`, `kv-cas`, `lease-clock`, `raft-quorum`이다. `--lab all`은 JSON 배열에 네 `status: "PASS"`를 출력한다. 인자 없이 실행하면 도움말만 출력한다. 일반 실행과 `-O` 실행에서 각각 **80 tests / OK**가 기대된다. 모델의 입력 검증과 내장 정답 검사는 제거 가능한 `assert` 대신 명시적 예외를 사용한다.

Windows PowerShell에서 Python이 설치 별칭으로만 잡히면 검증한 Python executable의 절대 경로를 `& '.../python.exe'`로 지정한다. 로컬 경로는 학습자의 환경에 맞게 선택하며, 이 랩을 위해 호스트 설정을 변경할 필요는 없다.

| 실행 이름 | 손계산 핵심 | 제품에서 별도 확인할 것 |
| --- | --- | --- |
| `exact-acl` | 같은 exact path의 capability union과 deny | wildcard 우선순위, canonicalization, auth/identity/namespace |
| `kv-cas` | current metadata version과 CAS, soft delete/destroy 차이 | HTTP 오류, storage, retention, 실제 삭제 범위 |
| `lease-clock` | 현재 시각 기준 renewal과 maximum lifetime | backend grant, expiration worker, revoke 실패·지연 |
| `raft-quorum` | 고정 voting membership의 과반수 | election/log/commit/read path, 재구성·복구 |

## 1. exact-acl: 권한은 문자열의 분위기가 아니라 정확한 계약이다

```bash
python -B security/shared/labs/offline_lab.py --lab exact-acl
```

### 모델 계약

`PolicyRule`은 하나의 explicit API path와 immutable capability 집합이다. `authorize`는 **완전히 같은 path**의 규칙만 합친다. 그 집합에 `deny`가 있으면 거부하고, 아니면 요청 capability의 포함 여부를 본다. 일치 규칙이 없거나 capability가 없으면 거부한다. 규칙 순서를 바꿔도 결과는 같다.

허용 capability는 `create`, `read`, `update`, `patch`, `delete`, `list`, `deny`라는 교육용 부분집합이다. `sudo`, 제품별 추가 capability, root token bypass, ACL parameter 제한, identity template은 구현하지 않는다. 요청에서 `deny`를 operation으로 지정하는 것도 거부한다.

입력 path는 ASCII 문자·숫자·`_`·`-` segment로 이루어지고 선택적으로 끝 `/`를 가진다. `*`, `+`, `..`, 중복 `/`, URL encoding, query string, template을 거부한다. **실제 제품이 해당 path를 모두 거부한다는 뜻은 아니다.** 이 함수는 이미 서버가 정규화한 API path를 받는다고 가정하며, slash 추가·URL decoding·대소문자 정규화를 하지 않는다. 예를 들어 LIST의 canonical prefix `secret/metadata/apps/`와 끝 `/`가 없는 문자열은 여기서는 다르다.

실제 정책의 glob은 정규식이 아니며, exact/prefix/wildcard 간 우선순위가 존재한다. 따라서 모든 matching pattern을 합쳐서 “deny가 하나라도 있으면 끝”이라고 구현하면 전체 엔진과 같은 모델이 되지 않는다. 현재 랩은 그 우선순위 문제를 지원하지 않는다고 명시적으로 제한한다. [OpenBao 정책](https://openbao.org/docs/concepts/policies/), [Vault 정책](https://developer.hashicorp.com/vault/docs/concepts/policies)

### 고정 fixture와 정답

`secret/data/apps/payments`에는 `read`와 `update`를 서로 다른 규칙으로 부여한다. `secret/metadata/apps/`에는 `list`만 부여한다. `secret/data/apps/admin`에는 `read`와 `deny` 규칙을 함께 둔다.

| 순서 | API path | 요청 capability | 허용 |
| --- | --- | --- | --- |
| 1 | `secret/data/apps/payments` | read | true |
| 2 | `secret/data/apps/payments` | update | true |
| 3 | `secret/data/apps/payments` | delete | false |
| 4 | `secret/metadata/apps/` | list | true |
| 5 | `secret/metadata/apps/payments` | read | false |
| 6 | `secret/data/apps/admin` | read | false, explicit-deny |
| 7 | `secret/data/apps/payments/child` | read | false |

JSON `allowed_in_request_order`는 `[true, true, false, true, false, false, false]`다. `data` read와 `metadata` read/list는 다른 path의 권한이다. 목록 권한을 받았다는 사실에서 개별 payload 읽기 권한을 추론하지 않는다. 반대로 LIST에서 노출되는 key 이름의 민감성도 따로 평가한다. 이 모델은 실제 listing 응답을 만들지 않는다.

### 심화 과제

1. `admin`의 deny를 다른 exact path로 옮긴 뒤 허용 여부를 먼저 손으로 예측한다.
2. 같은 제품의 CLI path, 실제 API path, 필요한 capability를 표로 연결한다. HTTP verb에서 capability를 무조건 일대일 추론하지 않는다.
3. 실제 엔진에서는 data read 성공, update 실패, metadata list 실패를 각각 관측한다. 오류를 단순 nonzero exit로만 판정하면 네트워크 장애를 정책 거부로 오인할 수 있다.
4. wildcard 정책을 실험할 때는 이 함수를 확장해 제품과 동일하다고 선언하지 말고, pinned source의 matching priority와 실제 API 결과를 독립 oracle로 사용한다.

## 2. kv-cas: payload의 가시성과 key의 존재는 다르다

```bash
python -B security/shared/labs/offline_lab.py --lab kv-cas
```

`KVState`는 1부터 이어지는 `KVVersion` tuple이다. `current_version`은 최신 metadata 번호이며, 최신 payload가 soft-deleted/destroyed여도 줄어들지 않는다. 모든 write는 CAS를 필수로 받는다. 빈 history에서만 CAS 0이 성공하며, 이후에는 현재 번호와 같은 CAS가 필요하다. 제품은 설정에 따라 CAS 없는 write를 허용할 수 있지만 이 모델에서는 의도적으로 제외한다. [Vault KV v2 API](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2), [OpenBao KV v2](https://openbao.org/docs/secrets/kv/kv-v2/)

| 순서 | 연산 | current_version | 최신 read | 별도 관측 |
| --- | --- | --- | --- | --- |
| 1 | CAS 0, `public-v1` | 1 | public-v1 | 첫 생성 |
| 2 | CAS 1, `public-v2` | 2 | public-v2 | v1도 읽을 수 있음 |
| 3 | stale CAS 1 | 2 | public-v2 | CASMismatch, history 불변 |
| 4 | v2 soft delete | 2 | null | payload는 새 state 내부에 남음 |
| 5 | v2 undelete | 2 | public-v2 | 읽기 복구 |
| 6 | v1 destroy | 2 | public-v2 | 새 state의 v1 payload는 null |
| 7 | CAS 2, `public-v3` | 3 | public-v3 | metadata 기준 다음 번호 |

JSON의 `current_versions`는 `[1, 2, 2, 2, 2, 3]`이다. 이 배열에는 거부된 write가 별도 state로 들어가지 않는다. `stale_cas_rejected`는 true, `latest_after_soft_delete`와 `version_1_after_destroy`는 null이다.

### destroy 모델에서 가장 중요한 한계

`destroy`는 **반환되는 새 Python state**에서 payload를 제거하고 destroyed flag를 기록한다. 이전 state를 참조하는 객체에는 가상 문자열이 여전히 남는다. 이는 immutable 상태 전이를 관찰하려는 설계다. 실제 memory zeroization, 디스크/백업/복제본 삭제, 암호학적 삭제를 증명하지 않는다. 기존 state에서 payload를 읽을 수 있다는 것을 제품의 destroy 취약점으로 해석해서도 안 된다.

모델은 metadata 전체 삭제, max_versions pruning, delete_version_after, patch/JSON map, 동시 thread, storage transaction, HTTP response code를 구현하지 않는다. 여러 writer는 순차적인 전이로 재현한다. 같은 CAS로 두 write를 다른 과거 state에 적용하는 것은 두 개의 가상 분기를 만드는 것이지 실제 엔진의 동시성 검증이 아니다. 성공한 첫 write의 **새 state**에 두 번째 write를 적용해야 충돌을 관찰할 수 있다.

존재하지 않는 version 선택과 destroyed version의 undelete는 학습자가 잘못된 전이를 놓치지 않도록 `ValueError`로 거부한다. 이 부분은 제품의 no-op/error 세부 동작을 재현한 계약이 아니다. 최신 read 결과가 null이어도 CAS 0으로 재생성할 수 있다고 판단하지 않는다.

### 심화 과제

1. 모든 version을 soft-delete한 경우와 destroy한 경우에 CAS 0/현재 CAS의 결과를 예측한다.
2. payload read 권한, metadata read/list 권한, destroy endpoint 권한을 분리한 정책을 설계한다.
3. 실엔진의 두 client가 같은 version을 읽은 뒤 경쟁 write하도록 barrier를 두고 성공/실패 응답과 최종 metadata를 기록한다. CPU의 순차 결과와 실제 concurrency 증거를 구분한다.
4. 백업 보존 정책과 secret 소비자 cache가 삭제의 의미를 어떻게 바꾸는지 threat model에 추가한다.

## 3. lease-clock: TTL 만료와 외부 자격 증명 폐기는 별개 관측이다

```bash
python -B security/shared/labs/offline_lab.py --lab lease-clock
```

실제 sleep이나 시스템 clock을 사용하지 않는다. `now`는 명시적 비음수 정수이며 역행할 수 없다. 처음 발급한 ordinary renewable lease의 최대 수명을 고정하고 다음 식으로 모델의 새 expiry를 정한다.

```text
max_expires_at = issued_at + max_ttl
renewed_expires_at = min(now + requested_increment, max_expires_at)
```

increment는 기존 expiry에 더하는 값이 아니라 현재 시점부터 요청하는 TTL이다. 실제 backend는 요청을 그대로 수락하지 않을 수 있으므로 응답 TTL을 확인해야 한다. 이 모델은 그 응답 선택을 위 식으로 고정한다. role/mount/system 설정 변화, periodic/batch token, parent token cascade, service token 전체 의미를 재현하지 않는다. [Vault lease](https://developer.hashicorp.com/vault/docs/concepts/lease), [OpenBao lease](https://openbao.org/docs/concepts/lease/)

| 시각 | 사건 | expires_at | 모델 client 사용 | 외부 credential 사용 가능 가정 |
| --- | --- | --- | --- | --- |
| 0 | TTL 10, maximum 25 발급 | 10 | true | true |
| 6 | increment 10 갱신 | 16 | true | true |
| 15 | increment 20 갱신 | 25 | true | true |
| 25 | 정확히 만료, revoke pending | 25 | false | true |
| 25 | backend revoke 실패, attempt 1 | 25 | false | true |
| 25 | backend revoke 성공, attempt 2 | 25 | false | false |

JSON `expiry_times`는 `[10, 16, 25]`, 세 가지 `*_lease_and_backend_usable` 값은 순서대로 `[false, true]`, `[false, true]`, `[false, false]`다. `revocation_attempts`는 2다.

여기서 `lease_usable`은 **협조적인 소비자가 로컬 계약을 지키며 사용을 계속해도 되는가**라는 모델 판단이다. 외부 DB/cloud가 이 값을 직접 검사한다는 뜻이 아니다. `backend_credential_usable`은 독립 만료가 없는 가상 credential이 revoke 성공 전까지 유효하다고 가정한다. 이 반례는 모든 backend가 같은 방식으로 만료된다는 주장이 아니다.

만료 또는 수동 revoke 요청은 `pending`으로 바꾸고 갱신을 막는다. 실제 backend 호출은 없으며, 성공/실패는 `attempt_revocation`에 boolean으로 넣는다. 성공 후 이미 열린 DB session, connection pool, 권한 cache가 어떻게 처리되는지는 범위 밖이다. 실제 revoke worker의 지연·재시도 backoff·실패 조건과 backend 관측은 별도 실험으로 확인한다.

### 심화 과제

1. 시각 25에서 갱신하면 왜 실패하는지, 시각 24에서 매우 큰 increment를 주어도 왜 최대 25인지 설명한다.
2. 발급 시각이 100인 경우 모든 deadline을 손으로 이동해 계산한다. 시간대 문자열은 이 정수 모델과 관계없다.
3. backend 일시 장애 시 “더 이상 새 사용을 시작하지 않음”, “서버 lease 처리”, “실제 credential 폐기”, “기존 session 종료”라는 네 지표를 분리한다.
4. max TTL 제한을 피하려고 무조건 신규 credential을 계속 발급하는 설계가 threat model을 만족하는지, 재인증·승인·quota와 함께 평가한다.

## 4. raft-quorum: 노드 수와 투표 수를 혼동하지 않는다

```bash
python -B security/shared/labs/offline_lab.py --lab raft-quorum
```

고정 membership에서 voting member가 `N`이면 과반수는 `floor(N/2) + 1`, 과반수를 유지하며 잃을 수 있는 voter 수는 `N - required_votes`다. nonvoter는 양쪽 계산에서 제외한다. `reachable`은 **서로 통신 가능한 살아 있는 component**라고 입력자가 가정하며, 일방향 연결이나 실제 RPC timeout을 모델링하지 않는다.

| membership / component | 전체 voters | 필요한 votes | 해당 component voters | 과반수 존재 |
| --- | --- | --- | --- | --- |
| 3 voters, 2/1 분할의 첫 component | 3 | 2 | 2 | true |
| 3 voters, 2/1 분할의 둘째 component | 3 | 2 | 1 | false |
| 5 voters, 3/2 분할의 첫 component | 5 | 3 | 3 | true |
| 5 voters, 3/2 분할의 둘째 component | 5 | 3 | 2 | false |
| 3 voters + nonvoter 1개, voter 1개 + nonvoter | 3 | 2 | 1 | false |
| 4 voters, 2/2 분할의 어느 component든 | 4 | 3 | 2 | false |

JSON `required_votes_for_3_and_5`는 `[2, 3]`, `maximum_unavailable_voters_for_3_and_5`는 `[1, 2]`, 두 split의 majority 배열은 `[true, false]`다. `one_voter_plus_nonvoter_has_majority`는 false다.

고정 membership의 서로 분리된 두 component가 동시에 voting majority를 가질 수 없는 이유를 집합 크기로 증명한다. 단, 이것만으로 leader 선출·쓰기 commit·read linearizability·snapshot 안전성을 증명하지 않는다. term, log index, log matching, previous-term entry, election restriction, joint consensus, read forwarding/consistency는 이 코드에 없다. 특히 단순히 “과반수이면 모든 API 읽기가 최신”이라는 결론을 금지한다. [Raft 논문](https://raft.github.io/raft.pdf), [OpenBao Integrated Storage](https://openbao.org/docs/concepts/integrated-storage/)

### 심화 과제

1. voter 3개에 nonvoter 10개를 추가해도 quorum 조건이 그대로인 이유를 계산한다.
2. voter 4개와 5개가 필요한 votes는 모두 3인데 voter 장애 허용 수는 왜 다른지 설명한다.
3. component에 과반수가 있어도 seal 상태·leader 부재·오래된 로그·I/O 실패로 서비스가 안 될 수 있는 경로를 나열한다.
4. 실제 failure injection을 한다면 승인된 disposable cluster에서만 실행하고, voter 구성·term/leader·요청 응답·복구 후 상태를 함께 수집한다. CPU PASS를 실클러스터 장애 복구 결과로 기록하지 않는다.

## 완료 조건

80개 테스트는 경계 정수·bool 혼동·잘못된 입력·immutable 이전 상태·literal oracle·CLI 결정성을 검사한다. 통과만으로 제품 전문가 역량을 판정하지 않는다. 각 실험마다 다음 세 가지를 짧게 제출한다.

1. 소스 코드를 보지 않고 계산한 fixture 정답과 최소 반례.
2. 모델이 보장하는 명제 1개와 보장하지 않는 명제 2개.
3. pinned 실엔진에서 필요한 추가 관측과, 예상과 다른 결과가 나왔을 때의 반증 절차.

다음 단계는 [공통 실행 안내](README.md)의 opt-in dev fixture다. dev fixture도 seal custody, 영속성, 실제 Raft quorum, PKI·동적 DB credential·감사 장애를 자동 검증하지 않는다. 운영 보안 검증의 증거로 범위를 부풀리지 않는다.
