# OpenBao: Zero to Hero → Secrets, Identity & Recovery Engineering

비밀 저장을 시작점으로 인증·정책·수명·암호·운영·구현을 연결하는 **28주·14모듈·7강**입니다. 목표는 명령어 암기가 아니라 “누가 언제 무엇을 할 수 있고, 실패 후 어떤 상태가 남는가”를 독립적인 검산과 소스 근거로 설명하는 능력입니다. 기간 자체가 전문성을 보장하지 않습니다.

재현 기준은 **OpenBao 2.7.1**입니다. [릴리스](https://github.com/openbao/openbao/releases/tag/v2.7.1)와 [소스 읽기 지도](source-reading.md)의 고정 revision을 사용하며, 실행마다 바이너리 버전·이미지 digest·plugin 버전·설정을 기록합니다. OpenBao 고유 기능은 OpenBao 문서·해당 revision으로 확인합니다. Vault와 기원이 같아도 namespaces·정책 확장·저장소·plugin·토큰 동작의 현재 호환성을 가정하지 않습니다.

## 학습 순서

1. [커리큘럼](curriculum.md)의 선수 조건을 점검합니다. Linux 프로세스/권한·HTTP/TLS·JWT·시간·트랜잭션·합의 기초가 부족하면 별도 보충합니다.
2. [공통 CPU·로컬 실습](../shared/labs/README.md)에서 기대값과 반례를 만듭니다.
3. 아래 강의의 추가 수동 실험으로 범위를 넓히고 [소스](source-reading.md)에서 실제 책임 경계를 찾습니다.
4. [평가표](assessment.md)에 실행한 범위와 미검증 항목을 분리하여 제출합니다.

| 모듈 | 강의 | 핵심 질문 |
| --- | --- | --- |
| OB01–02 | [위협 모델·core·barrier·seal](lessons/01-threat-model-seal.md) | 보호 대상과 복호화 권한의 경계는 어디인가? |
| OB03–04 | [identity·auth·ACL·token](lessons/02-identity-policy.md) | 누구에게 어느 경로의 어떤 연산을 허용하는가? |
| OB05–06 | [KV v2·CAS·lease·동적 자격 증명](lessons/03-kv-leases.md) | 버전 충돌과 만료 이후의 외부 상태를 어떻게 검산하는가? |
| OB07–08 | [Transit·암호·PKI·인증서 수명](lessons/04-transit-pki.md) | 키 변경과 암호문·인증서 소비자 변경은 어떻게 다른가? |
| OB09–10 | [감사·관측·Agent·workload identity](lessons/05-audit-workloads.md) | 비밀 유출 없이 접근과 배포 상태를 설명할 수 있는가? |
| OB11–12 | [Raft·HA·복원·업그레이드](lessons/06-raft-recovery.md) | 복제된 데이터와 실제 사용 가능한 서비스는 같은가? |
| OB13–14 | [소스·제품 차이·이전·미니 연구](lessons/07-source-migration-research.md) | 호환성 가설을 구현과 실패 실험으로 반증할 수 있는가? |

권장 시간은 **28주 × 주 12시간 = 336시간**입니다. OB14는 기존 자산으로 수행하는 2주 미니 연구이며, 별도 [8주 비밀·identity·복구 캡스톤](../../capstones/secrets-identity-recovery.md)은 추가 과정입니다. 제품 두 개를 병행하면 공통 원리는 재사용할 수 있으나 제품별 실행 증거를 서로 대신 제출할 수 없습니다.

## 제공 범위와 증거 경계

| 범위 | 제공물 또는 추가 과제 | 통과 증거·한계 |
| --- | --- | --- |
| OFFLINE | 공통 CPU 4개: `exact-acl`, `kv-cas`, `lease-clock`, `raft-quorum` | 결정 모형·수작업 oracle. 실제 정책 matcher·암호·Shamir·Raft 구현이 아님 |
| LOCAL-DEV | 선택 실행용 제품별 Compose와 수동 절차 | 격리된 일회용 dev 서버의 API 결과. 자동 unseal·메모리 저장·단일 노드 |
| AUTH-LAB | 별도 주체·claim·정책·token·TLS 추가 실험 | 허용뿐 아니라 거부 증거. root로 실행한 성공은 일반 주체 권한 증거가 아님 |
| LIFECYCLE-LAB | DB dynamic secret·Transit·PKI·Agent 추가 실험 | 실제 외부 소비자 검산·만료/회전/재로드 시간선. 자동 환경 제공 없음 |
| HA/RESTORE-LAB | 영속 다중 노드·seal·snapshot·복원·업그레이드 설계 | 독립 target·장애 원장·RPO/RTO. dev 모드로 대체 불가 |
| BUILD | 고정 소스의 symbol·test 추적과 선택 빌드 | 읽기와 빌드/테스트 성공을 분리 |

실제 dev fixture는 컨테이너 내부 loopback에서만 듣고 host port를 열지 않는 격리 실습입니다. dev 모드에는 운영용 TLS·seal ceremony·영속성·HA 보장이 없습니다. 실제 비밀, 운영 자격 증명, 운영 CA, KMS 계정을 넣지 않습니다. 현재 실행 여부는 [검증 기록](../shared/labs/validation.md)을 확인합니다.

저장소 루트에서 CPU 모형부터 실행합니다.

```bash
python -B security/shared/labs/offline_lab.py --lab all
```

OpenBao의 namespaces·CEL·storage 변화 중 하나를 선정하여 공통 API와 별개인 제품 계약을 검증합니다. 잘못된 정책·폐기·복원은 접근 상실이나 데이터 손실을 일으킬 수 있으므로 강의의 파괴적 과제는 전용 합성 자산에만 적용합니다. 실행하지 않은 보안·복구는 설계 완료 또는 미검증으로 남깁니다.
