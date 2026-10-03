# NATS 실험 지도

[환경·안전 경계](../environment.md) → [CPU 모형](offline.md) → [실제 단일 서버](native.md) → 모듈별 확장 순서입니다. 모형, mock, 실제 SDK/서버, 다중 노드, 업무 통합은 서로 다른 증거입니다. [검증 기록](validation.md)에 실행한 범위를 확인합니다.

## 1. CPU 기본: 설치·계정·GPU 없이

```text
python -B streaming/nats/labs/offline_lab.py --lab all
python -B streaming/nats/labs/offline_lab.py --lab subject-routing
python -B streaming/nats/labs/offline_lab.py --lab publish-dedup
python -B streaming/nats/labs/offline_lab.py --lab ack-redelivery
python -B streaming/nats/labs/offline_lab.py --lab retention-gates
python -B -m unittest discover -s streaming/nats/labs -p "test_*.py" -v
python -B -O -m unittest discover -s streaming/nats/labs -p "test_*.py" -v
```

| 실험 | 손으로 먼저 계산할 것 | 이 결과로 증명하지 않는 것 |
| --- | --- | --- |
| subject-routing | literal/`*`/`>` matching, plain fanout와 queue당 선택 수 | 실제 queue 공정성·thread scheduling·클러스터 interest 전파 |
| publish-dedup | ID·시간 창·첫 payload·stream sequence | 무한 중복 제거·DB transaction·서버의 정확한 timer 경계 |
| ack-redelivery | delivery attempt·pending·deadline·업무 effect 수 | 서버 전체 AckFloor 구현·정확한 시간 보장·자동 DLQ |
| retention-gates | consumer interest·ACK·limit에 따른 잔존 메시지 | 전체 stream 설정·disk 회수 시점·복제/backup 보존 |

숫자만 맞추지 말고 모형의 가정을 적습니다. 모든 ACK를 같은 뜻으로 부르는 설명은 통과하지 못합니다. 결과 JSON과 수계산 정답이 달랐을 때 어느 상태 전이가 잘못됐는지 설명합니다.

## 2. 선택 실제 서버

```text
python -B streaming/nats/labs/native_lab.py
```

계획 확인 후 [고정 SDK/바이너리 준비](../environment.md)와 [native 실행](native.md)을 따릅니다. runner는 opt-in으로 자신의 loopback 서버를 시작·종료합니다. 기존 클러스터·DB·Docker·현재 앱 MCP 설정에는 연결하지 않습니다.

## 3. 직접 구현할 심화 실험

아래는 제공 smoke가 자동 실행하지 않는 과제입니다. 각 항목은 **사전 예측 → 정상군 → 실패군 → 독립 oracle → 복구 증거**를 갖춰야 합니다.

| 과제 | 정상군·실패군 | 독립 oracle/통과 기준 |
| --- | --- | --- |
| client drain/reconnect | subscription barrier 후 publish / 연결 끊김·buffer 한계·느린 callback | publish 시도·server 처리·consumer 관측 집합을 분리; timeout을 유실로 단정하지 않음 |
| duplicate window | 같은 ID·다른 body / window 밖 동일 ID / 다른 ID·같은 업무 key | 저장 sequence와 payload, 업무 원장의 unique key로 각각 검산 |
| consumer lifecycle | durable 재접속 / consumer 삭제·재생성 / 중간 ACK 응답 유실 | stream sequence·consumer sequence·redelivery·ack floor·업무 effect 수 비교 |
| retention/limits | Limits·Interest·WorkQueue / MaxAge·MaxMsgs·discard 설정 | ack 여부와 별개인 limit, WorkQueue filter overlap 거부, 사라진 데이터의 복구 가능성 명시 |
| file store recovery | 정상 stop/restart / 소유한 서버 crash / 별도 snapshot restore | ACK 완료 집합·저장 메시지·hash·consumer state 비교; process kill과 전원 장애 구분 |
| quorum | 3 replicas에서 1개 중단 / 과반 상실 / stale node 재가입 | client 성공 응답·group leader/commit·최종 내용; 읽기·쓰기 API별 실패를 각각 측정 |
| account security | tenant A/B, 제한 PUB/SUB/reply / 다른 account·미승인 subject·폐기 신원 | 허용/거부 표와 server audit/관측; wildcard 오허용·management API 권한 별도 검사 |
| KV/Object Store | expected revision CAS·watch·chunk upload / stale CAS·삭제·중간 실패 | revision·delete/purge 표식·복원된 bytes의 hash; DB transaction이나 shared filesystem으로 일반화하지 않음 |
| capacity | 동일 데이터·동시성·payload / slow worker·hot subject·재전달 증가 | p50/p95/p99·오류율·CPU/RSS·pending·disk·정확성; warmup/반복·환경·측정 손실 기록 |

큰 부하·다중 서버·방화벽/TLS·계정 변경·외부 클라우드는 이 기본 실습에서 자동 수행하지 않습니다. 허가된 새 환경에만 적용합니다. 메시지 보존과 백업 범위를 확인하지 않은 purge/delete/restore 실험은 진행하지 않습니다.
