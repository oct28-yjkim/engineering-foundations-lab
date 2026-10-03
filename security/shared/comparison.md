# OpenBao와 Vault: 공통 원리, 다른 계약

[보안 트랙](../README.md) · [OpenBao 소스](../openbao/source-reading.md) · [Vault 소스](../vault/source-reading.md) · [실습](labs/README.md)

확인일 **2026-10-04**. 학습 기준은 **OpenBao 2.7.1**, **HashiCorp Vault Community 2.1.1**입니다. 고정 버전은 재현 기준이지 최신 보안 상태나 모든 배포에 대한 사용 권고가 아닙니다. 실제 실행 전 [OpenBao 릴리스](https://github.com/openbao/openbao/releases)와 [Vault 보안 공지](https://discuss.hashicorp.com/c/security/52)를 다시 확인합니다.

## 무엇을 비교해야 하는가

| 항목 | 공통 개념 | 반드시 따로 확인할 계약 |
| --- | --- | --- |
| core/barrier/seal | storage 바깥의 암호 계층, sealed/unsealed 상태 | 키 계층·seal provider·rekey/rotation/migration·KMS 의존성 |
| auth/identity | 인증된 principal을 token·policy에 연결 | issuer/audience/subject, alias와 mount accessor, token 형식·TTL·parent |
| ACL | API path와 capability | selector 우선순위·namespace 해석·templating·sudo·parameter 제한 |
| KV v2 | 버전·CAS·delete/undelete/destroy | plugin 버전·mount 옵션·metadata retention·error/response schema |
| lease | 발급·갱신·만료·회수 | backend plugin의 실제 revoke·실패 재시도·DB 기존 세션 수명 |
| transit/PKI | 키와 인증서 수명 관리 | 알고리즘/옵션·role constraints·rewrap·revocation 전달·검증 client |
| Agent/SDK | 신원 부트스트랩·갱신·전달 | 지원 auth method, cache invalidation·파일 권한·앱 reload |
| Raft/HA | 복제된 상태·정족수·leader | read/forwarding 조건·membership·snapshot·seal key·upgrade 호환성 |
| 확장 기능 | namespace·복제·외부 plugin | 제품·edition·license·빌드 tag·지원되는 조합 |

API 한 번 성공한 것으로 storage format, token 수명, 실패 코드, 보안 정책의 동등성을 증명할 수 없습니다. fork 이력이나 비슷한 CLI 이름도 충분한 증거가 아닙니다.

## 제품·edition을 섞지 않기

OpenBao의 현재 문서는 [namespace](https://openbao.org/docs/concepts/namespaces/)를 제공하며, 해당 버전의 기능·격리 경계를 직접 검사합니다. Vault 문서에서 [namespace/SMT](https://developer.hashicorp.com/vault/docs/enterprise/namespaces)와 [DR/performance replication](https://developer.hashicorp.com/vault/docs/enterprise/replication)은 Enterprise 또는 해당 HCP 배포 조건이 붙습니다. 여기의 Community dev image가 이를 제공한다고 가정하지 않습니다. 두 제품의 namespace를 같은 구현이나 동일 관리 권한 경계로 취급하지 않습니다.

고정 소스의 [OpenBao LICENSE](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/LICENSE)는 MPL-2.0, [Vault LICENSE](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/LICENSE)는 Business Source License 1.1 조건을 담습니다. 개별 dependency/파일의 조건은 별도입니다. 이 문서는 법적 사용 가능성 판단이나 법률 자문을 제공하지 않습니다. Enterprise 계약·지원 범위도 별도로 확인합니다.

## 전환·마이그레이션 연구 계약

[OpenBao 공식 in-place 가이드](https://openbao.org/docs/guides/migration/)가 명시한 검증 조합은 **Vault 1.14.1 → OpenBao 2.2.0, Raft, Shamir**입니다. 최신 Vault 저장 형식에 대한 보장을 명시하지 않습니다. 따라서 이 저장소 기준인 **Vault 2.1.1 ↔ OpenBao 2.7.1 상호 snapshot restore/in-place 교체는 제공하거나 검증한 기능이 아닙니다**. 순방향 성공도 역방향 rollback 가능성을 증명하지 않습니다.

선택 연구는 먼저 별도 합성 대상에서 다음 명세를 작성합니다. 이 목록 자체는 운영 전환 승인서가 아닙니다.

1. 버전·image digest·edition·storage·seal·auth·secret engine·외부 plugin·client/Agent를 inventory로 고정합니다. mount 목록에 있다는 것과 backend가 정상 초기화됐다는 것을 구별합니다.
2. 정책의 허용/거부 matrix, KV version/CAS, token·lease·audit request ID 등 비교 가능한 계약을 정합니다. 실제 token 문자열 동일성은 목표가 아닙니다.
3. 새 신원으로 재인증/재발급하고, DB role·PKI issuer·transit key의 이동 가능성과 불가능성을 따로 분류합니다. non-exportable key를 파일 복사로 옮길 수 있다고 가정하지 않습니다.
4. 쓰기 소유자를 하나로 정하고 전환 시점·중복 발급·기존 lease·소비자 cache를 관리합니다. 단순 dual-write는 원자적 전환이 아닙니다.
5. 별도 복원 대상·원래 seal key 접근·KMS 장애 대응·승인자·stop 조건을 확보합니다. 원본 data directory에 두 제품을 동시에 붙이지 않습니다.
6. rollback은 바이너리 되돌리기가 아니라 **전환 후 생성한 데이터·외부 자격 증명·정책 변경을 포함한 상태 복구**로 시험합니다. 호환성을 증명하지 못하면 unsupported로 보고합니다.

## 논문에서 실험으로

| 원문 | 학습 질문 | 제출 실험 |
| --- | --- | --- |
| Saltzer·Schroeder, 1975, [The Protection of Information in Computer Systems](https://web.mit.edu/Saltzer/www/publications/protection/) | 최소 권한·기본 거부·완전 매개·역할 분리는 어디서 깨지는가? | `exact-acl`의 allow/deny oracle + 실제 client의 우회 경로·stale cache 반례 |
| Shamir, CACM 1979, [How to Share a Secret](https://doi.org/10.1145/359168.359176) | k-of-n 분할의 수학적 가정과 운영상 key custody는 어떻게 다른가? | share 접근권·동시 유실·보관자 공모·rekey 책임을 표로 분석; 암호 직접 구현을 제품에 사용하지 않음 |
| Ongaro·Ousterhout, 2014, [In Search of an Understandable Consensus Algorithm, extended](https://raft.github.io/raft.pdf) | leader election·log matching·commit·membership이 왜 각각 필요한가? | `raft-quorum` 후 실제 cluster의 term/index·ACK·failure timeline 비교; 단순 과반수 계산을 Raft 구현으로 부르지 않음 |

논문의 원문/증명과 제품의 구체적 구현을 연결하되 동일하다고 단정하지 않습니다. 원문 전문을 복제하지 않으며 접근이 제한된 논문의 경우 출처와 읽지 못한 범위를 기록합니다. [OpenBao 보안 모델](https://openbao.org/docs/internals/security/)과 [Vault 보안 모델](https://developer.hashicorp.com/vault/docs/internals/security)의 공격자 가정을 별도로 읽습니다.
