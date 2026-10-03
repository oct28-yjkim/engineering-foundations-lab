# 6강. OpenBao: Raft·HA·복원·업그레이드

[커리큘럼](../curriculum.md) · [공통 실습](../../shared/labs/README.md) · [소스 지도](../source-reading.md)


<a id="ob11"></a>
## OB11 — Integrated storage, Raft, HA

**선수:** consensus·leader·network partition·durable log. **불변식:** 허용된 실패 조건에서 승인된 요청의 효과가 계약에 맞게 보존되고, 결과를 모를 때 모른다고 기록해야 합니다.

`raft-quorum`은 고정 voter 집합의 다수 조건을 계산하는 CPU 모형입니다. election, term, durable append, commit/apply, log conflict, lease read, 네트워크를 구현하지 않습니다. 실제 노드 수가 아닌 voter 구성과 상호 통신 가능한 집합을 구분합니다. [Integrated storage 문서](https://openbao.org/docs/concepts/integrated-storage/)

### 추가 HA-LAB — 영속 3-node fixture

1. 전용 3-node·TLS·seal·storage·독립 node ID를 준비합니다. dev 모드는 사용하지 않습니다. 초기 join의 API endpoint와 이후 cluster 통신을 구분하여 접근·인증 경로를 검토합니다.
2. 현재 leader·voter 목록·각 노드 상태를 기록하고 요청을 어느 endpoint로 보냈는지 원장에 남깁니다.
3. KV CAS처럼 독립 기대값이 있는 작은 workload를 사용합니다. 정상 응답, 명시적 실패, timeout/연결 종료의 미확정 결과를 나눕니다.
4. 합성 환경의 leader 종료, follower 종료, 제한된 partition을 각각 수행합니다. majority가 없는 쪽의 쓰기 실패와 복구 후 실제 version을 대조합니다.
5. client의 redirect/forwarding·재시도 경로를 추적합니다. endpoint가 응답했다는 이유로 local follower에서 최신 데이터를 읽었다고 추정하지 않습니다.
6. read-after-write에는 제품·node 역할·endpoint·일관성 옵션·실제 apply 상태 조건을 명시합니다. Raft를 쓴다는 사실만으로 모든 token/secret 읽기가 조건 없이 linearizable하다고 주장하지 않습니다.

**소스 과제:** storage append/commit/apply와 core의 active/standby 요청 처리를 따로 찾습니다. leader인 사실, unsealed인 사실, API 요청을 처리할 수 있는 사실의 차이를 설명합니다.

**통과:** voter·통신 그래프, 요청 최소 20개의 결과 원장, 미확정 요청 재판정, 실패 전후 version 검산. “3대 중 2대가 떠 있음”만으로 완료하지 않습니다.

**OpenBao 과제:** OpenBao non-voter·standby·eventual consistency의 현재 문서 계약을 확인합니다. 지원 기능과 실제 활성 설정을 구별하고 다른 제품의 performance standby 의미를 그대로 대입하지 않습니다.

<a id="ob12"></a>
## OB12 — Snapshot, restore, upgrade

**불변식:** backup은 파일 생성이 아니라 필요한 키·설정·plugin·외부 의존성과 함께 별도 target에서 서비스 계약을 복구할 수 있어야 합니다.

snapshot 시점과 외부 DB credential/인증서/앱 파일 상태는 하나의 전역 원자적 snapshot이 아닙니다. 복원한 lease 기록이 현재 외부 권한 상태와 일치한다고 가정하지 않습니다. seal 자산 없이 snapshot만 보관하는 계획도 완전한 복구 계획이 아닙니다.

### 추가 RESTORE-LAB

- 현재 합성 secret version, policy, auth mapping, active lease alias, 외부 DB 사용자, Transit ciphertext version을 기준 원장에 기록합니다.
- snapshot 파일의 식별자·생성 시각·checksum·product/version·seal 종류·필요 plugin을 manifest로 만듭니다. 키 원문은 manifest에 넣지 않습니다.
- 새 격리 target에서 복원합니다. 원본 cluster 주소·DB·KMS·CA endpoint에 자동 연결되어 실제 자산을 폐기/변경하지 않게 의존성을 먼저 차단합니다.
- 복원 후 auth 양성/음성 대조군, KV 버전, 과거 ciphertext 접근, 외부 credential 상태를 각각 검산합니다.
- 오래된 snapshot을 골라 “파일은 정상이나 업무 상태는 과거”인 반례를 만듭니다. 측정한 RPO/RTO와 누락된 대상 상태를 분리해 보고합니다.
- upgrade는 지원 경로·storage schema·plugin 변경·mixed-version 기간·downgrade 가능성부터 조사합니다. 이전 바이너리를 다시 실행하는 것만으로 rollback이 보장된다고 쓰지 않습니다.

**안전 gate:** restore는 격리된 새 target만 사용합니다. force restore, peer 강제 재구성, 기존 data directory 삭제를 자동화하지 않습니다. quorum 재구성과 snapshot 복원은 손실/불확실 commit의 의미가 달라 각각 승인된 전용 실험으로 한정합니다.

**구술:** 외부 KMS 키 사용권을 잃은 복원, 과거 lease가 다시 나타난 복원, 이전 CA chain만 가진 앱은 각각 어떤 failure인가? snapshot 암호화와 snapshot 유출 시 노출 최소화는 같은 문제인가?

**통과:** 독립 복원 transcript의 비식별 요약·key custody 확인·외부 상태 대조·RPO/RTO·업그레이드 중단 기준. 제공 dev fixture에는 영속 Raft나 운영 seal이 없어 이 gate는 별도 구축 과제입니다.
