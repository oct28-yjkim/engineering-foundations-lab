# NATS 환경과 증거 경계

기준일 **2026-10-04**, 서버 **2.15.0**, 선택 Python client **nats-py 2.16.0**입니다. Core NATS와 JetStream을 다루며, 과거 NATS Streaming(STAN)의 채널·프로토콜·운영 방법을 JetStream과 혼합하지 않습니다. [서버 릴리스](https://github.com/nats-io/nats-server/releases/tag/v2.15.0), [Python 릴리스](https://github.com/nats-io/nats.py/releases/tag/v2.16.0).

## 실행 수준

| 수준 | 제공물 | 추가 준비와 한계 |
| --- | --- | --- |
| OFFLINE | Python 표준 라이브러리 CPU 모형 4개 | Python 3.10+; 네트워크·패키지·Docker·GPU·계정 불필요 |
| LOCAL-NATIVE | 고정 SDK + 직접 소유하는 단일 서버 정확성 runner | 공식 바이너리 수동 준비, 격리 venv; loopback TCP만 사용 |
| CLIENT/STORE-BUILD | 재연결·slow consumer·파일 저장·KV/CAS·Object Store 확장 과제 | 학습자가 client·계측·장애 주입 구현 |
| CLUSTER/SECURITY | Raft quorum·leader 전환·계정·JWT·권한·TLS·독립 restore | 별도 폐기 가능한 클러스터/인증서/합성 신원 구성 필요 |
| INTEGRATION | outbox/inbox·DB 업무 불변식·재처리 | PostgreSQL/MySQL 등 별도 선택; 자동 연결 없음 |

CPU 결과를 실제 서버 측정으로, 단일 서버의 성공을 HA·전원 장애 내구성·안전한 운영 배포로 쓰지 않습니다. 실제 실행 범위는 [검증 기록](labs/validation.md)에 따로 남깁니다. rolling 공식 문서의 최신 API와 고정 버전 구현이 다르면 [소스 지도](source-reading.md)와 실제 오류를 우선 대조합니다.

## 기본 경로

저장소 루트에서 실행합니다. Python 이름은 자신의 환경에 맞춥니다.

```text
python -B streaming/nats/labs/offline_lab.py --lab all
python -B -m unittest discover -s streaming/nats/labs -p "test_*.py" -v
python -B -O -m unittest discover -s streaming/nats/labs -p "test_*.py" -v
python -B streaming/nats/labs/native_lab.py
```

마지막 명령은 실행 계획만 출력합니다. 실제 SDK import·네트워크 연결·서버 시작·저장 디렉터리 생성은 opt-in 실행에서만 수행합니다. `-O`에서도 검사 조건이 사라지지 않아야 합니다.

## 선택 SDK 준비

설치는 네트워크를 사용합니다. 패키지·실행 파일을 전역 설치하거나 기존 MCP/LLM venv에 섞지 않습니다. 다음 디렉터리가 이미 존재하면 먼저 내용을 확인하고 새로 만들지 않습니다.

```text
python -m venv lab-workspaces/nats-sdk-2.16.0
```

Windows PowerShell:

```powershell
& ./lab-workspaces/nats-sdk-2.16.0/Scripts/python.exe -m pip --isolated install --only-binary=:all: --index-url https://pypi.org/simple -r streaming/nats/labs/requirements.txt
& ./lab-workspaces/nats-sdk-2.16.0/Scripts/python.exe -m pip check
& ./lab-workspaces/nats-sdk-2.16.0/Scripts/python.exe -m pip freeze
```

Linux/macOS에서는 해당 실행 파일을 `./lab-workspaces/nats-sdk-2.16.0/bin/python`으로 바꿉니다. 활성화는 필수가 아닙니다. Python import 이름은 `nats`, 배포 패키지 이름은 `nats-py`입니다. 같은 repository의 새로운 `nats-core` 등 다른 패키지와 이 fixture의 SDK를 혼합하지 않습니다.

## 선택 서버 준비

[공식 v2.15.0 릴리스](https://github.com/nats-io/nats-server/releases/tag/v2.15.0)에서 OS/CPU에 맞는 archive와 `SHA256SUMS`를 받아 전용 `lab-workspaces/nats-server-2.15.0` 아래에 보관합니다. 공식 배포처와 checksum을 확인하고 안전한 하위 경로로만 압축을 풉니다. 서비스 등록·PATH 변경·방화벽 변경·관리자 설치는 필요하지 않습니다. 이 저장소의 runner는 바이너리를 자동 다운로드하지 않습니다.

2026-10-04에 확인한 Windows amd64 archive의 공식 release API digest:

```text
asset: nats-server-v2.15.0-windows-amd64.zip
SHA256: 2d0861dc2ca3567d17f7d19611d7b346cc2ccbd7086a0a77cc957a2c71663200
```

위 값은 **zip 파일**의 digest이며 추출한 exe나 Linux/macOS archive의 digest가 아닙니다. [고정 릴리스 API](https://api.github.com/repos/nats-io/nats-server/releases/tags/v2.15.0)와 [SHA256SUMS](https://github.com/nats-io/nats-server/releases/download/v2.15.0/SHA256SUMS)를 교차 확인합니다. 같은 배포처의 digest 일치는 전송/파일 일치 검사이지 독립적인 공급망 보안 증명이 아닙니다.

```powershell
Get-FileHash -Algorithm SHA256 ./lab-workspaces/nats-server-2.15.0/nats-server-v2.15.0-windows-amd64.zip
& ./lab-workspaces/nats-server-2.15.0/nats-server-v2.15.0-windows-amd64/nats-server.exe -v
```

확인 후 [실제 실습](labs/native.md)의 opt-in 명령을 사용합니다. 서버를 미리 시작할 필요가 없으며 현재 실행 중인 NATS에 접속하는 runner가 아닙니다.

## 안전·자원·정리

- 단일 owned child server, `127.0.0.1`의 임시 포트, 새 server name, 합성 메시지, 임시 저장소를 사용합니다. 별도 monitoring/route/gateway/leaf 포트를 열지 않습니다.
- 인증용 임시 값은 실행마다 생성하며 운영 인증 설계나 TLS 실습을 대신하지 않습니다. 로컬 평문 TCP와 프로세스 인자에 접근할 수 있는 같은 OS 사용자를 공격자로부터 격리하는 sandbox가 아닙니다.
- 연결 URL·외부 credentials·기존 store를 인자로 받지 않습니다. 바이너리 경로는 사용자가 신뢰를 확인한 실행 파일이어야 하며 `-v` 검사는 악성 실행 파일 검증 수단이 아닙니다.
- 수십 개 이하 합성 메시지의 정확성 실습입니다. 제한 시간 안에 실패하면 원인을 확인하고 부하를 자동 확대하지 않습니다. 처리량 benchmark나 실무 sizing 수치가 아닙니다.
- runner는 자신이 시작한 서버만 종료하고 자신이 생성한 임시 저장소를 정리합니다. 강제 앱/OS 종료로 잔존물이 생긴 경우 정확한 PID·명령줄·`lab-workspaces/nats-native` 하위 경로 소유권을 확인한 뒤 수동 정리합니다. 기존 서버를 이름 검색만으로 일괄 종료하지 않습니다.
- venv와 다운로드한 archive/binary는 반복 학습을 위해 남으며 Git에 포함하지 않습니다. `.env`, NKey seed, JWT credentials, TLS private key, 실제 payload를 커밋하지 않습니다.

3-node 실습에서도 같은 노트북의 세 프로세스는 host 전원·disk 장애 도메인을 공유합니다. Raft commit, OS cache, fsync, storage device 보장, 백업 보존은 서로 다른 질문으로 기록합니다. 인증·클러스터·업그레이드·복원은 제공된 smoke를 확장해 직접 검증해야 합니다.
