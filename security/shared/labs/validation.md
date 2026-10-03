# OpenBao / Vault 검증 기록

확인일 **2026-10-04**, Windows·CPython **3.12.14**, Docker CLI 27.5.1·Compose 2.32.4-desktop.1. Python 3.10+을 대상으로 하지만 모든 minor/OS 조합에서 실행한 것은 아닙니다.

## 수행 결과

| 검사 | 결과 | 증거 범위 |
| --- | --- | --- |
| CPU `--lab all` | 4개 PASS, 일반/`-O` 각각 실행 | exact ACL·KV/CAS·lease clock·정적 voter quorum 모형 |
| `test_offline_lab.py` | 80개 PASS, 일반/`-O` | 독립 기대값·경계·불변성·실패 대조군 |
| `test_engine_lab.py` | 52개 PASS, 일반/`-O` | Docker/CLI 모의 응답·fixture guard·토큰 전달·HTTP 오류 oracle |
| 신규 전체 | 132개 PASS, 일반/`-O` 각각 | 같은 132개를 두 실행 모드로 검사; 실제 서버 테스트 아님 |
| native `--help` / opt-in gate | PASS | 도움말 및 명시적 동의 없는 실행은 subprocess 없음 |
| 두 Compose `config --quiet` | PASS | 설정 구문/구조, 컨테이너 실행·image pull 아님 |
| 기존 MySQL·OpenSearch·LLM·IaC 회귀 | 각각 139·139·50·82개 PASS | 변경 전 기존 CPU/mock 실습과의 회귀 검사 |
| Markdown·내부 링크 | 208문서·1,238링크, 오류 0 | 파일/anchor 존재·code fence, 제품별 7강·14 module anchor |
| 고정 소스 링크 | 63개 참조 경로 확인 | OpenBao·Vault·Vault KV plugin의 Git tree와 대조, 빌드 아님 |

핵심 runtime oracle은 `-O`에서 제거되지 않는 예외 기반 검사입니다. native mock은 실제 서버의 응답을 대체해 runner의 분기만 검증합니다. 성공 응답을 생성한 mock을 제품 보안·호환성 증거로 부르지 않습니다.

## 실제 엔진은 미검증

Docker Linux engine pipe `dockerDesktopLinuxEngine`이 없어 서버에 연결할 수 없었습니다. **image pull·컨테이너 생성·OpenBao/Vault 실제 명령 실행은 수행하지 않았습니다.** Docker Desktop 자동 시작·host 설정 변경·계정·클라우드 자원 생성도 하지 않았습니다.

공식 release/tag/commit, Docker Hub의 지정 tag 제공 여부, source 파일 경로와 주요 심볼, Dockerfile/entrypoint, Vault 외부 KV plugin pin을 읽기 전용으로 확인했습니다. [OpenBao 소스 지도](../../openbao/source-reading.md)·[Vault 소스 지도](../../vault/source-reading.md)의 Go 빌드/upstream test는 미수행입니다. 문서의 기대값·강의 과제를 실측으로 기록하지 않았습니다. 공식 문서를 열람했지만 외부 링크 전부의 접근성을 검사한 것은 아니며 Shamir 논문의 ACM 원문 페이지는 403으로 열리지 않았습니다.

seal·Shamir/auto-unseal·키 보관·storage 암호·TLS·audit device·실제 workload auth·동적 DB 자격 증명·transit·PKI·Agent·Raft·durable snapshot restore·Enterprise 기능·제품 간 migration은 별도 미검증입니다.

## 사용자 환경에서 확인할 것

[실습 준비·안전 경계](README.md)를 읽고 개인 로컬 Docker 대상만 선택합니다. 실제 실행의 JSON에서 제품/version과 `mode:"local_dev_engine"`, `status:"PASS"`, 8개 oracle, child token 회수를 확인합니다. image digest·실행 날짜·비식별 결과·실패 stage를 별도 보고서에 남깁니다.

실제 엔진에서 실패하면 먼저 fixture/version/CLI 응답의 차이를 검토합니다. 통과시키기 위해 원격 대상 guard·version guard·403/CAS oracle을 삭제하지 않습니다. 작은 dev fixture가 통과해도 위의 운영·복구 미검증 범위는 그대로 남습니다.
