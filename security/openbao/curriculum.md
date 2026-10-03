# OpenBao 28주 심화 커리큘럼

14모듈 × 2주 × 주 12시간 = **336시간**입니다. 모듈당 원리·공식 자료 6시간, 실험 10시간, 소스 추적 4시간, 분석·구술 4시간을 권장합니다. 별도 DB/Kubernetes/다중 노드 구축·도구 설치·실패 재실행 시간은 추가입니다.

## 모듈 지도

기본 실험은 [운영 runbook](operations.md)의 실제 baseline → 지표·감사·소비자 상태 대조 → 경쟁 가설 → 제한 조치 → 회복 검산입니다. OB01–04는 status/인가 baseline, OB05–08은 수명/소비자, OB09–12는 audit/HA/복구, OB13–14는 source·사고 보고서를 누적합니다. 모형은 선택 원리 부록으로 이동하며 28주·14모듈과 깊은 내부 동작 학습은 유지합니다.

| 모듈 / 주 | 선수 조건 | 핵심 질문 | 최소 제출물 |
| --- | --- | --- | --- |
| OB01 / 1–2 | HTTP·OS·접근 제어 기초 | [위협 모델·요청 경로](lessons/01-threat-model-seal.md#ob01) | 위협 주체 5종·요청 경로·보호/비보호 자산 |
| OB02 / 3–4 | 01, 암호 기초 | [barrier·seal·키 계층](lessons/01-threat-model-seal.md#ob02) | init/unseal/rekey/rotate 구별·seal 의존성·custody 설계 |
| OB03 / 5–6 | 01–02, JWT/TLS 기초 | [identity·auth method](lessons/02-identity-policy.md#ob03) | 인간/워크로드 로그인 계약·entity/alias·잘못된 claim 거부 |
| OB04 / 7–8 | 03, HCL·집합 | [ACL·token·권한 수명](lessons/02-identity-policy.md#ob04) | 정확한 API 경로별 허용/거부·selector 경계·token tree |
| OB05 / 9–10 | 04, 동시성 | [KV v2·CAS·버전](lessons/03-kv-leases.md#ob05) | 동일 버전 경쟁·CAS=0·soft delete/undelete/destroy 구분 |
| OB06 / 11–12 | 04–05, 시간·재시도 | [lease·동적 secret](lessons/03-kv-leases.md#ob06) | 발급/갱신/만료/폐기 상태·외부 DB 접속 검산 |
| OB07 / 13–14 | 02, 암호 기초 | [Transit·키 수명](lessons/04-transit-pki.md#ob07) | round-trip·변조 거부·rotation/rewrap·키 접근 경계 |
| OB08 / 15–16 | 07, X.509/TLS | [PKI·인증서 수명](lessons/04-transit-pki.md#ob08) | SAN/chain/EKU·만료·revocation·client 검증 분리 |
| OB09 / 17–18 | 03–08 | [audit·관측·사고 대응](lessons/05-audit-workloads.md#ob09) | 요청/응답 상관·민감 필드·audit 장애와 가용성 |
| OB10 / 19–20 | 03–06, 프로세스·파일 | [Agent·workload identity](lessons/05-audit-workloads.md#ob10) | bootstrap·renew·render·앱 reload·stale credential 시간선 |
| OB11 / 21–22 | 02, 06, 분산 시스템 | [Raft·HA·읽기 경로](lessons/06-raft-recovery.md#ob11) | voter/quorum·leader·apply/read·장애 중 결과 원장 |
| OB12 / 23–24 | 11, 파일·키 관리 | [snapshot·복원·업그레이드](lessons/06-raft-recovery.md#ob12) | 독립 target 복원·seal 접근·외부 secret 상태·rollback 제약 |
| OB13 / 25–26 | 01–12, Go 기초 | [소스·제품·마이그레이션](lessons/07-source-migration-research.md#ob13) | 5symbol·2자료구조·1test·호환/불일치 행렬 |
| OB14 / 27–28 | 13, 앞선 fixture | [2주 최소 연구](lessons/07-source-migration-research.md#ob14) | 한 경로·한 개선·실패 2개·독립 oracle·한계 |

## 증거 중심의 실험 계약

모든 모듈을 업무 질문 → 자산/위협 → 불변식 → 실패 모델 → 독립 기대값 → 실행 → 관측 → 경쟁 가설 → 구현 근거 → 한계 순으로 제출합니다. [공통 실험 방법](../../databases/shared/experiment-method.md)을 재사용하되 비밀 원문은 기록하지 않습니다.

```text
run_id / product+edition / binary version / image digest / plugin version / source revision
scope / node roles / storage+seal configuration / synthetic fixture identifiers
principal label / auth mount / entity+alias mapping / policy revision / namespace context
operation+API path / requested capability / expected allow-or-deny / actual status
token or lease alias (not token value) / issue-renew-expire-revoke timeline / clock assumptions
KV version+CAS / deletion metadata / ciphertext version (not plaintext or private keys)
audit request ID / sanitized result / consumer reload or DB authentication observation
Raft voter set / term+commit+applied indices if observed / request outcome ledger
snapshot identity / seal-key custody check / isolated restore target / measured RPO+RTO
```

토큰·SecretID·unseal/recovery share·개인 키·DB 암호·복호화 평문은 출력·스크린샷·Git·CI artifact에 남기지 않습니다. accessor·entity ID·경로명도 식별 정보가 될 수 있어 합성 label로 보고합니다. HMAC 처리 여부만으로 로그 전체를 공개해도 된다고 판단하지 않습니다.

실패는 `denied`, `expired`, `backend unavailable`, `uncertain outcome`, `not executed`로 분리합니다. timeout만 보고 쓰기나 폐기 실패를 확정하지 않습니다. monotonic elapsed time, 서버가 돌려준 TTL, 실제 외부 인증 성공/실패를 서로 대신 쓰지 않습니다.

## Gate와 완료 범위

- G1, OB01–04: 위협·seal·인증·정책. root나 host 침해를 storage 암호화만으로 막는다고 주장하거나 CPU exact matcher를 제품 ACL 전체와 같다고 설명하면 미통과입니다.
- G2, OB05–08: CAS·lease·Transit·PKI. lease 만료와 외부 권한 제거, key rotation과 기존 암호문 재암호화, revoke 기록과 TLS client 거부를 분리합니다.
- G3, OB09–12: 감사·소비자·HA·복구. dev 서버나 quorum 산술만으로 운영 보안·읽기 일관성·복원 가능성을 증명하지 않습니다.
- G4, OB13–14: 제품 범위·소스·반증. 다른 edition의 기능이나 이전 방향을 확인 없이 상호 호환으로 표시하지 않습니다.

[평가표](assessment.md)의 정확성·원리/소스·실험/반증·운영/재현성은 각 25점입니다. **80/100 이상, 각 15/25 이상, 필수 gate 전체 통과**가 선언 범위의 완료 조건입니다. 운영 완료에는 baseline·서로 다른 두 사건·회복 증거가 필요합니다. OFFLINE만 수행하면 선택 원리 부록 완료이며 운영 미실행입니다. LOCAL-DEV의 운영 증거는 dev 범위로만 표시하고 AUTH·LIFECYCLE·HA/RESTORE·BUILD는 각각 별도 상태를 남깁니다.

## 제품별 마지막 4주

OB13에서 OpenBao의 namespaces·CEL·storage 변화 중 하나를 선정하여 공통 API와 별개인 제품 계약을 검증합니다. 기능 이름이 같더라도 API 응답·정책·token·plugin·storage contract를 행 단위로 대조합니다. OB14에서는 한 경로·개선 하나·실패 조건 둘을 골라 작은 연구로 마감합니다.

기존 증거를 재사용하지 못하는 새로운 다중 cluster·PKI trust migration·Kubernetes 통합은 2주 미니 연구에 넣지 않습니다. 넓은 운영 통합은 별도 [8주 캡스톤](../../capstones/secrets-identity-recovery.md)으로 진행합니다.
