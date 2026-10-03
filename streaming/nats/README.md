# NATS: Zero to Hero → Messaging, JetStream & Recovery Engineering

Core NATS와 JetStream을 **라우팅·전달 보장·저장·복제·업무 부작용의 서로 다른 경계**로 분석하는 28주·14모듈·7강 과정입니다. 실제 서버의 정상 상태를 관측하고, 지표로 장애 가설을 검증한 뒤 wire protocol, 저장 엔진, consumer 상태 기계, Raft 소스로 원인을 설명합니다. GPU·모델 API는 필요하지 않으며 CPU 모형은 선택 원리 보충 자료입니다.

기준일은 **2026-10-04**, 서버는 **nats-server 2.15.0**, 선택 Python client는 **nats-py 2.16.0**입니다. 서버·client·CLI·문서 revision은 별도로 기록합니다. rolling 문서의 최신 기능을 고정 버전이 모두 제공한다고 가정하지 않습니다. [서버 릴리스](https://github.com/nats-io/nats-server/releases/tag/v2.15.0), [Python client 릴리스](https://github.com/nats-io/nats.py/releases/tag/v2.16.0)

## 시작 순서

1. [환경·안전 경계](environment.md), [커리큘럼](curriculum.md), [평가 기준](assessment.md)을 읽습니다. TCP·비동기 처리·트랜잭션·기초 합의 알고리즘이 부족하면 별도 보충합니다.
2. [운영 관측·트러블슈팅](operations.md)에서 실제 서버의 정상 baseline과 consumer·stream·접속 상태를 읽습니다. 환경이 없으면 정제된 실측 자료로 분석 연습을 하고 실행 gate는 미완료로 남깁니다.
3. [실제 서버 실습](labs/README.md)을 준비하고, 소유한 격리 환경에서만 장애를 재현→진단→완화→복구 검증합니다. 한 서버의 성공으로 다중 노드 내구성을 판정하지 않습니다.
4. [소스 지도](source-reading.md)를 따라 가설→자료구조→상태 전이→회귀 시험을 연결하고 [검증 기록](labs/validation.md)에 실행 증거와 미검증 항목을 남깁니다.

선택 부록인 [원리 모형](labs/offline.md)이 필요할 때만 아래 명령을 사용합니다. 필수 선수 과정이나 운영 수료 조건이 아닙니다.

```powershell
python -B streaming/nats/labs/offline_lab.py --lab all
python -B -m unittest discover -s streaming/nats/labs -p 'test_*.py'
```

실제 실습의 의존성 설치와 실행 명령은 [실습 안내](labs/README.md)를 따릅니다. 외부 broker, 조직 자격 증명, 클라우드 자원에 자동 연결하지 않습니다.

| 모듈 | 강의 | 핵심 질문 |
| --- | --- | --- |
| NT01–02 | [아키텍처·subject·라우팅](lessons/01-architecture-subjects.md) | 연결·관심·전달·영속화의 책임은 어디에서 나뉘는가? |
| NT03–04 | [전달 패턴·client 내부](lessons/02-delivery-clients.md) | queue·request/reply·재연결·drain은 무엇을 보장하지 않는가? |
| NT05–06 | [stream·저장·publish 확인](lessons/03-streams-publishing.md) | 보관·수락·중복 제거·업무 중복은 어떻게 다른가? |
| NT07–08 | [consumer·ACK·재전달](lessons/04-consumers-ack.md) | 처리 중·전달 완료·ACK 완료·업무 완료를 어떻게 검산하는가? |
| NT09–10 | [Raft·토폴로지·복구](lessons/05-raft-recovery.md) | 어떤 장애에서 어떤 그룹이 진행할 수 있으며 무엇을 복구했는가? |
| NT11–12 | [보안·관측·용량](lessons/06-security-operations.md) | 연결 인증과 subject/API 권한, 처리량과 안정성을 어떻게 분리하는가? |
| NT13–14 | [KV·Object Store·소스·연구](lessons/07-source-research.md) | 편의 API의 보장 경계를 구현과 독립 실험으로 반증할 수 있는가? |

**28주 × 주 12시간 = 336시간**입니다. NT14는 기존 fixture에서 한 결론을 검증하는 2주 미니 연구입니다. [8주 NATS 전달·복구 캡스톤](../../capstones/nats-delivery-recovery.md)은 별도 96시간 확장이며 28주에 포함되지 않습니다.

## 제공물과 실행 범위

| 범위 | 제공 또는 추가 과제 | 증명하지 않는 것 |
| --- | --- | --- |
| OFFLINE | `subject-routing`, `publish-dedup`, `ack-redelivery`, `retention-gates` 결정적 CPU 모형 | 실제 socket·client·disk·Raft·보안·성능 |
| LOCAL-NATIVE | 고정 client와 소유한 loopback 단일 서버를 이용하는 선택 fixture | 다중 노드 quorum·전원 장애 내구성·TLS·운영 인증 |
| CLIENT-LAB | 강의의 reconnect·drain·slow consumer·request timeout 추가 과제 | 모든 SDK·OS·프록시 조합 |
| CLUSTER-RECOVERY | 별도 전용 다중 노드 환경의 리더 변경·분할·복구 과제 | 단일 서버 또는 단일 호스트만으로 실제 가용 영역 장애 |
| SECURITY-OPS | 합성 계정·subject 권한·TLS·관측·용량 실험 | CPU 권한 표만으로 실제 서명 검증 또는 운영 보안 |
| BUILD/RESEARCH | 고정 source test·KV/Object Store·논문 가설·미니 연구 | 소스 읽기만으로 빌드 성공·성능 향상·형식 검증 |

LOCAL-NATIVE가 자동으로 강의의 모든 추가 과제를 실행하는 것은 아닙니다. 실행·설계·결과 검증·실패·미검증을 별도 상태로 표시합니다.

## 가장 중요한 구별

Core NATS는 best-effort, at-most-once 전달을 제공합니다. JetStream은 저장 및 consumer 상태를 추가하지만, publisher의 중복 제거와 consumer ACK 확인이 외부 DB의 트랜잭션을 대신하지는 않습니다. 같은 업무 작업이 재실행되어도 결과가 보존되는지는 별도 idempotency key·업무 원장·commit 경계로 증명해야 합니다. [Core NATS](https://docs.nats.io/learn/core-nats/), [JetStream](https://docs.nats.io/concepts/jetstream)

subject는 Kafka partition이 아니고 queue group은 Kafka consumer group과 동일한 offset/rebalance 모델이 아닙니다. 비교는 [Kafka 트랙](../kafka/README.md)과 같은 workload·실패 조건·관측 지점에서 수행합니다. 과거 **NATS Streaming(STAN)** 자료를 JetStream의 설정이나 내구성 근거로 재사용하지 않습니다.
