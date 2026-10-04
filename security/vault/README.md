# HashiCorp Vault: Zero to Hero → Secrets, Identity & Recovery Engineering

비밀 저장을 시작점으로 인증·정책·수명·암호·운영·구현을 연결하는 **28주·14모듈·7강**입니다. 목표는 명령어 암기가 아니라 “누가 언제 무엇을 할 수 있고, 실패 후 어떤 상태가 남는가”를 독립적인 검산과 소스 근거로 설명하는 능력입니다. 기간 자체가 전문성을 보장하지 않습니다.

재현 기준은 **HashiCorp Vault Community 2.1.1**입니다. [릴리스](https://github.com/hashicorp/vault/releases/tag/v2.1.1)와 [소스 읽기 지도](source-reading.md)의 고정 revision을 사용하며, 실행마다 바이너리 버전·이미지 digest·plugin 버전·설정을 기록합니다. 기본 실습은 Community 범위입니다. Enterprise namespaces·복제·performance standby 및 HCP 관리형 서비스는 별도 제품·권한·환경이 필요한 비교 과제로 표시합니다. 공개 소스의 존재를 모든 버전의 오픈소스 라이선스나 Enterprise 기능 제공으로 해석하지 않습니다.

## 기본 LAB 입구

**정상 기능 → 동작 원리 → 관측 → 제약 → 진단·복구** 순서로 시작합니다. Community dev의 정상 KV·권한 경계를 먼저 확인하고 health·TTL·소비자 회복을 분리해서 진단합니다. [제품별 기본 LAB 카드](operations.md#basic-lab)에서 정상 결과·직접 볼 지표·자주 만나는 사건 2개·회복 검산과 환경 제공 범위를 확인합니다.

[공통 LAB 계약](../../operations/lab-contract.md)을 적용하며 **28주 심화 과정을 먼저 마칠 필요는 없습니다.** 실행 환경이나 수동 준비가 필요한 단계는 준비/미실행으로 구분하고, 아래 심화 커리큘럼은 기본 LAB 이후 필요한 부분부터 확장합니다.

## 학습 순서

1. [커리큘럼](curriculum.md)의 선수 조건을 점검합니다. Linux 프로세스/권한·HTTP/TLS·JWT·시간·트랜잭션·합의 기초가 부족하면 별도 보충합니다.
2. [실제 운영 실습](operations.md)에서 status·지표·감사·소비자 baseline을 수집하고 증상별 경쟁 가설을 검증합니다. 환경 준비는 [공통 실습](../shared/labs/README.md)을 따릅니다.
3. 아래 강의의 추가 수동 실험으로 범위를 넓히고 [소스](source-reading.md)에서 실제 책임 경계를 찾습니다.
4. [평가표](assessment.md)에 실행한 범위와 미검증 항목을 분리하여 제출합니다.

| 모듈 | 강의 | 핵심 질문 |
| --- | --- | --- |
| VL01–02 | [위협 모델·core·barrier·seal](lessons/01-threat-model-seal.md) | 보호 대상과 복호화 권한의 경계는 어디인가? |
| VL03–04 | [identity·auth·ACL·token](lessons/02-identity-policy.md) | 누구에게 어느 경로의 어떤 연산을 허용하는가? |
| VL05–06 | [KV v2·CAS·lease·동적 자격 증명](lessons/03-kv-leases.md) | 버전 충돌과 만료 이후의 외부 상태를 어떻게 검산하는가? |
| VL07–08 | [Transit·암호·PKI·인증서 수명](lessons/04-transit-pki.md) | 키 변경과 암호문·인증서 소비자 변경은 어떻게 다른가? |
| VL09–10 | [감사·관측·Agent·workload identity](lessons/05-audit-workloads.md) | 비밀 유출 없이 접근과 배포 상태를 설명할 수 있는가? |
| VL11–12 | [Raft·HA·복원·업그레이드](lessons/06-raft-recovery.md) | 복제된 데이터와 실제 사용 가능한 서비스는 같은가? |
| VL13–14 | [소스·제품 차이·이전·미니 연구](lessons/07-source-migration-research.md) | 호환성 가설을 구현과 실패 실험으로 반증할 수 있는가? |

권장 시간은 **28주 × 주 12시간 = 336시간**입니다. VL14는 기존 자산으로 수행하는 2주 미니 연구이며, 별도 [8주 비밀·identity·복구 캡스톤](../../capstones/secrets-identity-recovery.md)은 추가 과정입니다. 제품 두 개를 병행하면 공통 원리는 재사용할 수 있으나 제품별 실행 증거를 서로 대신 제출할 수 없습니다.

## 제공 범위와 증거 경계

| 범위 | 제공물 또는 추가 과제 | 통과 증거·한계 |
| --- | --- | --- |
| OPS-BASELINE | [제품별 운영 runbook](operations.md): 실제 상태·핵심 지표·사건 triage | baseline·두 사건·회복 증거가 운영 gate; 실제 환경과 권한 필요 |
| OFFLINE 선택 부록 | 공통 원리 모형 4개: `exact-acl`, `kv-cas`, `lease-clock`, `raft-quorum` | 결정 모형·수작업 oracle. 실제 제품 운영 gate를 대체하지 않음 |
| LOCAL-DEV | 선택 실행용 제품별 Compose와 수동 절차 | 격리된 일회용 dev 서버의 API 결과. 자동 unseal·메모리 저장·단일 노드 |
| AUTH-LAB | 별도 주체·claim·정책·token·TLS 추가 실험 | 허용뿐 아니라 거부 증거. root로 실행한 성공은 일반 주체 권한 증거가 아님 |
| LIFECYCLE-LAB | DB dynamic secret·Transit·PKI·Agent 추가 실험 | 실제 외부 소비자 검산·만료/회전/재로드 시간선. 자동 환경 제공 없음 |
| HA/RESTORE-LAB | 영속 다중 노드·seal·snapshot·복원·업그레이드 설계 | 독립 target·장애 원장·RPO/RTO. dev 모드로 대체 불가 |
| BUILD | 고정 소스의 symbol·test 추적과 선택 빌드 | 읽기와 빌드/테스트 성공을 분리 |

실제 dev fixture는 컨테이너 내부 loopback에서만 듣고 host port를 열지 않는 격리 실습입니다. dev 모드에는 운영용 TLS·seal ceremony·영속성·HA 보장이 없습니다. 실제 비밀, 운영 자격 증명, 운영 CA, KMS 계정을 넣지 않습니다. 현재 실행 여부는 [검증 기록](../shared/labs/validation.md)을 확인합니다.

학습은 [운영 runbook](operations.md)의 읽기 전용 preflight로 시작합니다. 환경이 없으면 미준비·설계 상태로 남기며 실제 운영 통과로 표시하지 않습니다. 원리 반례를 보충할 때만 아래 선택 모형을 실행합니다.

```bash
python -B security/shared/labs/offline_lab.py --lab all
```

Community/Enterprise/HCP의 기능·운영 책임을 분리하고, 지원되지 않는 Enterprise API를 Community 성공 사례로 보고하지 않습니다. 잘못된 정책·폐기·복원은 접근 상실이나 데이터 손실을 일으킬 수 있으므로 강의의 파괴적 과제는 전용 합성 자산에만 적용합니다. 실행하지 않은 보안·복구는 설계 완료 또는 미검증으로 남깁니다.
