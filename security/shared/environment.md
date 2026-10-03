# Secrets lab 환경·안전 경계

[실습 실행](labs/README.md) · [제품 비교](comparison.md) · [검증 기록](labs/validation.md)

## 환경 수준

| 수준 | 제공 여부 | 가능한 증거 | 불가능한 결론 |
| --- | --- | --- | --- |
| S0 CPU | Python 표준 라이브러리, 기본 제공 | exact ACL·CAS·시간·정족수의 작은 반례 | 제품 전체 인가·암호·scheduler·Raft 검증 |
| S1 dev | 두 Compose + 선택 native runner 제공 | 실제 KV v2/CAS·제한 token 허용/403·회수 | seal·내구성·HA·동적 DB 자격 증명·운영 보안 |
| S2 운영 원리 | 학습자가 격리 환경 구성 | TLS·Shamir/auto-unseal·Raft·audit·복원 | 다른 edition·다른 seal/provider의 동일 보장 |
| S3 소스 연구 | 고정 source 지도, 빌드 환경 별도 | upstream test·관측·패치·회귀 | 정적 소스 읽기만으로 runtime 통과 주장 |

S1은 **인메모리 dev**입니다. 자동 초기화·자동 unseal·공개 dummy root token·컨테이너 내부 loopback HTTP를 사용합니다. network mode `none`으로 컨테이너 밖 통신을 끊고 host port와 bind mount를 제공하지 않습니다. Docker daemon 권한을 가진 사용자나 host 침해로부터 격리한다는 뜻은 아닙니다. 암호화되지 않은 HTTP를 운영에서 권장하는 구성이 아닙니다.

## 버전과 리소스

확인일 2026-10-04, `openbao/openbao:2.7.1`, `hashicorp/vault:2.1.1`. 소스 tag/commit·이미지 공개 tag는 공식 저장소에서 확인했지만 **이 컴퓨터에서 이미지를 pull하거나 실제 엔진을 시작하지 않았습니다**. tag는 바뀔 수 있으므로 실제 보고서에는 image ID/digest와 서버 응답 version을 추가합니다. runner의 exact version guard는 version 변경 시 검토 없이 실행되지 않도록 하는 장치입니다.

S0: Python 3.10+, 추가 패키지 없음. S1: 개인 로컬 Docker Linux engine와 Compose v2, 제품당 메모리 상한 512MiB·CPU 상한 1개. 두 제품을 동시에 실행할 필요가 없습니다. 이 상한은 운영 sizing 또는 성능 benchmark가 아닙니다. Windows에서는 Docker Desktop Linux containers가 필요하며 앱 설치·시작·host 설정을 자동 수행하지 않습니다.

## 저장과 비밀의 수명

- 제품 상태는 memory에만 존재합니다. **stop/start, restart, 컨테이너 재생성 시 KV·policy·token 등 모든 실습 상태가 사라집니다.** 일반 DB volume과 같은 보존을 기대하지 않습니다.
- Vault image가 선언한 `/vault/logs`, `/vault/file`은 Compose가 정확히 두 tmpfs로 덮습니다. 영속·익명 volume을 쓰지 않습니다. OpenBao fixture에는 mount가 없습니다.
- dev 부트스트랩이 출력하는 token/share를 Docker log에 남기지 않도록 logging driver `none`을 사용합니다. 이를 감사 로그 구성으로 취급하지 않습니다.
- repo에 적힌 `efl-local-...-not-for-production`은 누구나 아는 dummy 값입니다. 실제 인증 정보나 운영 root로 재사용하지 않습니다.
- native runner의 새 child token은 stdin으로만 전달하며 출력/host argv에 넣지 않습니다. container process memory/env·host 관리자에게는 보일 수 있습니다. 성공 시 자기 child token만 회수합니다. 실패 시 짧은 TTL까지 남을 수 있으며 재시작하면 전부 소멸합니다.
- native가 만든 새 UUID mount/policy는 비교를 위해 남습니다. 기존 mount/policy/secret은 변경하거나 지우지 않습니다. 여러 번 실행하면 메모리 사용이 증가하므로 학습 증거를 정리한 후 폐기합니다.

## S2 확장 시 먼저 승인할 것

제품별 별도 프로젝트·data directory·키 보관자·cluster 주소를 지정합니다. root token은 bootstrap/break-glass에만 한정하고 이후 업무 principal로 검증합니다. snapshot과 seal key는 서로 독립적으로 통제합니다. 외부 KMS/클라우드 계정·유료 자원·Enterprise 환경·실제 DB와 연결하는 과정은 기본 runner에 없습니다.

운영 secret을 복제하지 않고 합성 DB 계정·비운영 CA·공개 test payload만 사용합니다. 로그·trace·Terraform state에도 비밀이 남을 수 있습니다. 산출물은 접근 통제된 별도 위치에서 관리하고, 저장소의 `/lab-workspaces/` ignore만으로 암호화·접근 제어가 된다고 생각하지 않습니다. Git에는 비식별 측정치와 재현 절차만 제출합니다.
