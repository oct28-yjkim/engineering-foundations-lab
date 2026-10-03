# Secrets & Identity Lab — OpenBao / HashiCorp Vault

비밀을 저장하는 API 사용법에서 출발해 **신뢰 경계·인가·키 수명·외부 자격 증명 회수·분산 복구를 증거로 설명하는 엔지니어**를 위한 과정입니다. 암호화를 썼다는 사실과 시스템이 안전하다는 결론을 분리합니다.

| 트랙 | 범위 | 기간 |
| --- | --- | --- |
| [OpenBao](openbao/README.md) | barrier·seal·identity·policy·KV·lease·transit·PKI·audit·Agent·Raft·복원·구현 추적 | 28주·14모듈·7강·336시간 |
| [HashiCorp Vault](vault/README.md) | 같은 핵심 원리 + Vault 구현·플러그인 경계·Community/Enterprise 구분 | 28주·14모듈·7강·336시간 |
| [제품 비교와 전환 검증](shared/comparison.md) | API·저장소·namespace·plugin·edition별 호환성 계약 | 두 트랙의 비교 과제 |
| [실제 엔진 실습](shared/labs/README.md) | 제품별 격리 dev fixture·기준선, 원리 모형은 선택 부록 | 각 트랙 실습에 포함 |
| [OpenBao 진단](openbao/operations.md) / [Vault 진단](vault/operations.md) | health·권한·lease·audit·storage/Raft·회복 검증 | 제품별 실제 관측 |
| [비밀·신원·복구 캡스톤](../capstones/secrets-identity-recovery.md) | workload 권한·DB lease·회전·감사·독립 복원 | 별도 선택 8주 |

각 모듈은 2주·24시간입니다. 두 제품을 순차로 모두 하면 56주·672시간이며 공통 기초와 선택 캡스톤은 별도입니다. 기존 데이터베이스·AI·IaC 경로에 자동 합산하지 않습니다. 이미 익힌 공통 원리는 실험·소스·실패 oracle을 제출해 진단을 통과하면 단축할 수 있지만, 한 제품의 PASS를 다른 제품의 검증으로 인정하지 않습니다.

## 시작 순서

1. HTTP/TLS, Linux 프로세스·파일 권한, JSON, 시간·재시도·분산 정족수를 점검합니다. 부족한 부분은 [공통 기초](../databases/shared/foundations.md)로 보완합니다.
2. 한 제품의 [격리 dev 실습](shared/labs/README.md)에서 실제 상태·정상/거부 결과를 확인합니다. 인증 token이 있는 환경의 endpoint·권한을 먼저 검토합니다.
3. [OpenBao](openbao/operations.md) 또는 [Vault](vault/operations.md)의 지표·로그·증상별 진단으로 원인을 좁히고 7개 강의의 내부 원리·소스로 설명합니다. 같은 path의 read/list, lease 만료/외부 회수, quorum/요청 성공의 차이를 실측과 연결합니다.
4. 기준선·두 문제의 진단·회복 결과를 제출하고, 별도 허가된 환경에서만 seal·Raft·TLS·복원으로 확장합니다. dev 성공으로 HA·암호/운영 보안을 완료하지 않습니다.

Python 원리 모형 4개는 [선택 보조자료](shared/labs/README.md)로 보존합니다. 먼저 수행할 필요가 없으며 암호 구현이나 제품 서버가 아닙니다. 실제 실행 여부는 과거 [검증 기록](shared/labs/validation.md)과 새 운영 보고서를 구분해 확인합니다.

## 핵심 경계

- root token·unseal share·recovery key·transit key·애플리케이션 secret은 목적과 회수 절차가 다릅니다.
- 온라인 서버의 root/host 장악은 저장소 barrier만으로 방어되지 않습니다. 관리자·키 보관자·감사자 역할을 나눕니다.
- CPU에서는 합성 문자열만 사용합니다. 실제 키·토큰·JWT·DB 암호·인증서 private key·snapshot·audit payload는 제출/커밋하지 않습니다.
- LLM/agent에는 원문 secret 대신 작업 식별자와 제한된 도구를 줍니다. 인증 정보는 신뢰된 실행 경계에서 주입하며 prompt·trace·Sentry payload로 흘리지 않습니다.
- [Terraform](../infrastructure/terraform/README.md) state, [Supabase](../platforms/supabase/README.md) JWT/RLS, [Sentry](../observability/sentry/README.md) telemetry와 연결하되 다른 기술의 보안 보장을 대신하지 않습니다.

커리큘럼을 읽는 것만으로 전문가가 된다고 보장하지 않습니다. 최종 기준은 처음 보는 실패를 재현하고, 비밀을 노출하지 않는 증거로 원인과 복구 한계를 설명하는 능력입니다.
