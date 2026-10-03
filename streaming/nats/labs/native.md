# 실제 Core NATS·JetStream 정확성 실습

고정 **nats-server 2.15.0 + nats-py 2.16.0**으로 합성 메시지를 교환합니다. SDK mock이나 CPU 모델을 실제 서버 결과로 집계하지 않습니다. [환경 준비](../environment.md)를 완료한 뒤 저장소 루트에서 실행합니다.

## 실행

기본은 계획 출력이며 어떤 서버에도 접속하지 않습니다.

```text
python -B streaming/nats/labs/native_lab.py
```

Windows PowerShell, 공식 amd64 archive를 환경 안내의 경로에 준비한 경우:

```powershell
$natsLabBinary = (Resolve-Path ./lab-workspaces/nats-server-2.15.0/nats-server-v2.15.0-windows-amd64/nats-server.exe).Path
& ./lab-workspaces/nats-sdk-2.16.0/Scripts/python.exe -B streaming/nats/labs/native_lab.py --run-local --server-binary $natsLabBinary
& ./lab-workspaces/nats-sdk-2.16.0/Scripts/python.exe -B -O streaming/nats/labs/native_lab.py --run-local --server-binary $natsLabBinary
```

Linux/macOS는 해당 OS archive를 사용하고 venv 경로를 `bin/python`, executable 경로를 실제 추출한 `nats-server`의 **절대 경로**로 바꿉니다. 다른 OS를 Windows에서 검증했다고 주장하지 않습니다. `--server-binary`는 이미 신뢰를 확인한 파일만 지정하며 상대 경로는 거부합니다.

## 사전 예측과 oracle

| 순서 | 동작 | 예상 관측 |
| --- | --- | --- |
| Core | SUB를 flush한 뒤 합성 PUB | 지정 subject·payload 수신. flush는 업무 처리 ACK가 아님 |
| no responder | 아무 subscriber도 없는 request subject | NoResponders 오류. 일반 timeout을 같은 성공으로 취급하지 않음 |
| publish dedup | 같은 `Nats-Msg-Id`로 두 번 publish, body는 다르게 | 두 PubAck의 stream sequence 동일, 두 번째 duplicate 표시, 저장 body는 처음 것 |
| delivery | explicit ACK durable pull consumer로 첫 fetch | stream sequence와 첫 delivery attempt 확인 |
| retry | 첫 메시지 NAK 뒤 다시 fetch | 같은 stream sequence, 증가한 delivery count; 새 메시지가 아니라 재전달 |
| ACK 확인 | 재전달 메시지 `ack_sync` | consumer pending ACK가 0으로 수렴 |
| 저장과 소비 분리 | ACK 후 Limits stream 상태 조회 | 메시지 1건이 여전히 보존됨. ACK가 모든 정책의 삭제 조건은 아님 |
| 업무 처리 비교 | 같은 합성 업무 key를 두 delivery에서 처리 | 단순 횟수 2, 중복 방지 집합 기반 effect 1 |

업무 effect 비교는 **프로세스 메모리의 작은 oracle**입니다. 실제 DB의 unique constraint·transaction·crash durability를 검증하지 않습니다. PubAck와 double ACK를 확인해도 외부 결제·DB·메일이 exactly-once라는 결론은 나오지 않습니다.

runner는 새 이름의 stream/consumer를 자기 서버에만 생성하며 기존 서버/stream 삭제를 요구하지 않습니다. 정상/실패 종료에서 owned process와 임시 저장소 정리를 시도합니다. 강제 OS 종료까지 보장하지 않으며 다운로드한 바이너리와 venv는 남깁니다.

## 실패를 성공으로 읽지 않기

- 버전 불일치: 준비한 binary와 실행 venv를 확인합니다. 고정 값을 임의로 바꿔 검사를 우회하지 않습니다.
- 권한/로컬 socket/process 실행 거부: 현재 실행 환경의 허용 범위를 확인합니다. timeout이나 PermissionError는 메시지 거부 실험 PASS가 아닙니다. 보안 설정을 전역 해제하지 않습니다.
- 기동/응답 timeout: server exit·잘못된 실행 파일·자원 상태를 점검하고 원래 증거를 보존합니다. deadline을 크게 늘렸다는 사실만으로 안정성을 주장하지 않습니다.
- 예상과 다른 duplicate/metadata/pending 결과: 고정 SDK/서버 소스와 config를 대조합니다. JSON에 기대값을 직접 써 넣거나 assertion을 제거하지 않습니다.

## 이 실습 밖의 보장

재연결 buffer, Core queue fairness, dedup window 만료의 실제 경계, AckWait timer, MaxDeliver 고갈, retention별 삭제, consumer 재시작, fsync/전원 장애, Raft 복제, route/gateway/leaf node, TLS/accounts/JWT, cross-language, KV/Object Store, backup/restore, DB 통합, 장시간 부하를 검증하지 않습니다. 이 항목은 [추가 실험](README.md)과 강의에서 독립적으로 수행합니다.
