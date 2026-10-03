# NATS 검증 기록

확인일 **2026-10-04**, Windows·CPython **3.12.14**에서 검사했습니다. 소스/문서는 Python 3.10+를 대상으로 하며 모든 minor/OS에서 실행한 것은 아닙니다. 실행 범위를 아래와 같이 분리합니다.

## 실행한 검사

| 검사 | 결과 | 증거 범위 |
| --- | --- | --- |
| CPU `--lab all` | **4개 runtime oracle 통과**, 일반/`-O` 각각 | routing·유한 dedup·explicit ACK/재전달·retention의 제한된 상태 모형 |
| CPU 단위 테스트 | **95개 PASS**, 일반/`-O` 각각 | 독립 literal 정답·입력 거부·불변성·시간 경계·잘못된 대조군·CLI 거짓 성공 거부 |
| native runner mock 테스트 | **63개 PASS**, 일반/`-O` 각각 | opt-in·버전·경로·loopback identity·실패 oracle·owned cleanup |
| 신규 전체 단위 테스트 | **158개 PASS**, 일반/`-O` 각각 | CPU 95 + native mock 63. 아래 실제 서버 검사와 구분 |
| 실제 고정 서버/SDK | **10개 검사 PASS**, 일반/`-O` runner 각각 | nats-server 2.15.0과 nats-py 2.16.0의 실제 loopback 통신 |
| 종료/정리 | 해당 바이너리 프로세스 **0개**, 임시 store 디렉터리 **0개** | 정상 완료 후 확인. 모든 OS 강제 종료 경로의 증명은 아님 |
| 격리 venv | 설치 후 `pip check` PASS | nats-py 2.16.0 의존성 충돌 없음; 공급망 보안 인증 아님 |
| 기존 실습 회귀 | MCP 151·LLM 50·IaC 82·보안 132·MySQL 139·OpenSearch 139개 PASS | 기존 CPU/mock 코드 유지; 해당 제품 실제 엔진의 신규 실행은 아님 |
| 고정 소스 지도 | **44개 파일 참조 존재 확인** | 두 공식 repository의 고정 tag Git tree 검사; upstream test 실행은 아님 |
| Markdown·내부 링크 | **242문서·1,470링크, 오류 0** | 전체 저장소 파일/anchor·code fence 검사, NATS 7강·14 module anchor 확인 |

일반/`-O`는 같은 시험을 두 모드로 반복한 것이며 두 배의 독립 테스트로 집계하지 않습니다. 실제 NATS 서버는 Go 바이너리이고 `-O`는 Python runner에 대한 옵션입니다. 핵심 oracle은 `assert`가 아닌 명시적 조건 검사와 예외로 구현합니다.

## 실제 결과

공식 Windows amd64 zip의 SHA256이 [환경 안내의 고정 digest](../environment.md)와 일치함을 확인한 뒤 Git ignore된 실습 폴더로 추출했습니다. `nats-py==2.16.0`은 공식 PyPI binary wheel을 격리 venv에 설치했습니다. 다운로드/설치는 네트워크를 사용했지만 실제 실험은 외부 broker·cloud·API·업무 DB·현재 앱 연결에 접속하지 않았습니다. Windows 서비스·전역 PATH·방화벽·기존 Python 환경을 바꾸지 않았습니다.

실측 검사 목록:

1. Core subscription을 flush한 뒤 지정 subject/payload 수신.
2. subscriber가 없는 요청의 `NoRespondersError` 확인.
3. 새 file-backed stream이 비어 있는 상태로 생성됨.
4. 두 publish의 `Nats-Msg-Id`가 같으면 sequence는 둘 다 **1**, 두 번째 duplicate 표시가 참.
5. 두 번째 body가 달라도 저장 body는 첫 합성 주문의 **amount=7**.
6. 첫 pull은 stream sequence **1**, consumer sequence **1**, delivery count **1**, pending ACK **1**.
7. NAK 후 pull은 stream sequence **1**, consumer sequence **2**, delivery count **2**.
8. 두 delivery의 단순 업무 합계 **14**, 메모리 멱등 원장의 합계 **7**, 적용 key **1**.
9. `ack_sync` 이후 pending ACK **0**, 남은 미전달 메시지 **0**.
10. Limits retention에서는 ACK 뒤에도 stream 메시지 **1**이 남음.

업무 원장은 실제 DB transaction이 아닙니다. native dedup 검사는 window 내부의 짧은 실행이며 window 만료·재시작 복구·동시 publisher는 확인하지 않았습니다. 첫 sandbox 제한 실행의 filesystem/process 권한 문제는 PASS로 집계하지 않았고, 허용된 scoped 실행으로 동일 fixture를 다시 검증했습니다.

다운로드한 archive/binary와 SDK venv는 재실험을 위해 `lab-workspaces`에 남겨 두었습니다. runner가 생성한 폐기용 서버와 합성 메시지 저장소만 종료·정리했습니다. 사용자 데이터나 기존 서버는 삭제하지 않았습니다.

## 검증하지 않은 것

실제 multi-node Raft, network partition, route/gateway/leaf, 전원 장애/fsync·장치 내구성, snapshot/restore, 업그레이드/downgrade, JWT/NKey/TLS/account 권한, queue fairness, reconnect/drain/slow consumer, AckWait/backoff timer 경계, MaxDeliver 고갈·DLQ 운영, Interest/WorkQueue 실제 삭제, KV/Object Store, cross-SDK, DB outbox/inbox, 장시간 부하·성능 수치, upstream 전체 suite는 실행하지 않았습니다.

[커리큘럼](../curriculum.md)과 [실험 지도](README.md)의 가설·예상값을 이 기록의 실측 결과로 읽지 않습니다. CPU·mock·실제 single-node·별도 확장·설계만 완료한 범위를 최종 보고서에서도 구분합니다.
