# Apache Kafka: Zero to Hero, 로그에서 장애 복구까지

Kafka를 설정하거나 연결하는 수준에서 출발해, **한 이벤트가 producer·broker·replica·consumer·외부 DB를 통과할 때 순서와 중복, 가시성, 복구 경계를 설명하는 수준**을 목표로 합니다. 14개 모듈을 명목상 28주, 주 12시간으로 구성했습니다. 학습 기간보다 실제 결과·반례·소스 추적·복구 증거로 진도를 판단합니다.

기준은 **Apache Kafka 4.3.1, KRaft**입니다. broker와 client 버전, 이미지 digest, feature level은 실험마다 기록합니다. 최신 문서나 과거 ZooKeeper 기반 설명을 현재 설정에 그대로 적용하지 않습니다. [공식 Docker 안내](https://kafka.apache.org/43/getting-started/docker/)

## 읽는 순서

공통 기초가 필요하면 [자료구조·OS·분산 원리](../../databases/shared/foundations.md)부터 시작하고, [공통 실험 방법](../../databases/shared/experiment-method.md)을 적용합니다.

1. [28주 커리큘럼](curriculum.md): K01–K14의 선수 조건·산출물·통과 기준.
2. [운영 관측·트러블슈팅](operations.md): 정상 baseline → lag·ISR·latency 진단 → 복구 증거. [로컬 실습 안내](labs/local-lab.md)에서 실제 명령과 검증 범위를 확인합니다.
3. [로그·저장 구조](lessons/01-log-storage.md): K01–K02.
4. [Producer·복제](lessons/02-producer-replication.md): K03–K04.
5. [Consumer·그룹 프로토콜](lessons/03-consumer-groups.md): K05–K06.
6. [전달 의미·트랜잭션](lessons/04-transactions.md): K07–K08.
7. [KRaft·운영·보안·복구](lessons/05-kraft-operations.md): K09–K10.
8. [Streams·Connect·CDC](lessons/06-streams-connect.md): K11–K12.
9. [소스 연구·통합 캡스톤](lessons/07-research-capstone.md): K13–K14.
10. [버전별 소스 읽기](source-reading.md), [평가와 구술 리뷰](assessment.md).

## 제공 환경과 추가 구현 과제

| 표시 | 실행 범위 | 제공 여부 |
| --- | --- | --- |
| `LOCAL` | 단일 combined broker/controller, topic·producer·consumer CLI와 기본 oracle | Compose와 `labs/scripts` 제공 |
| `BUILD` | Java producer/consumer, transaction, Streams, 프로파일링·회귀 테스트 | 구현 요구사항과 oracle 제공; 완성 Java 애플리케이션은 미제공 |
| `CLUSTER-DESIGN` | 다중 broker·controller, 복제 장애·quorum·리더 전환 | 별도 격리 클러스터를 추가 구축하는 과제 |
| `INTEGRATION-DESIGN` | Connect·Debezium·PostgreSQL·ClickHouse E2E | 계약·실험·검증 기준 제공; CDC 배포 환경은 미제공 |

단일 노드에서 ACK가 왔다는 사실로 replica 장애 내성이나 클러스터 가용성을 증명할 수 없습니다. Java/클러스터/통합 과제를 수행하지 못했으면 “설계 완료, 실행 미검증”으로 남깁니다. 4.3에는 일반 consumer group 외에 별도 소비 모델도 있지만 이 과정의 기본은 partition ownership 기반 `KafkaConsumer`입니다. Share Consumer 보장을 혼합하지 않습니다.

## 빠른 시작

모든 명령은 저장소 루트에서 실행합니다. 데이터베이스 Compose와 별도의 파일입니다.

```text
docker compose -f streaming/kafka/compose.yaml up -d --wait
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/00-inspect.sh
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/01-smoke.sh
```

내부 CLI/컨테이너 client는 `kafka:19092`, host에서 실행하는 Java client는 `localhost:9092`를 사용합니다. bootstrap 연결 뒤 broker가 돌려주는 advertised 주소도 client에서 접근 가능해야 합니다. `/lab`에는 `labs` 디렉터리가 마운트됩니다.

- [`00-inspect.sh`](labs/scripts/00-inspect.sh): 버전·클러스터 상태 읽기.
- [`01-smoke.sh`](labs/scripts/01-smoke.sh): 실행별 새 topic과 정확성 oracle을 사용하는 기본 실습.
- [`02-observe.sh`](labs/scripts/02-observe.sh): topic/group 상태 관찰. 인수와 출력은 [실습 안내](labs/local-lab.md) 참조.

교재의 직접 명령은 별도 `k01-...-exp1` 같은 실험 topic을 생성합니다. 재실행할 때 새 suffix로 분리하고 기존 topic을 자동 삭제하지 않습니다. 테스트 데이터가 이미 있는 topic의 offset을 새 실험 기준선으로 오해하지 않습니다. `docker compose down`과 `down -v`는 다릅니다. 볼륨 삭제는 이 시작 절차에 포함되지 않습니다.

## 반드시 구별할 개념

- partition offset은 파일 byte 위치도, 업무 event_id도 아닙니다. offset 차이는 항상 사용자 레코드 수가 아닙니다.
- producer의 `send()` 반환, ACK, transaction commit, consumer 처리, offset commit, 외부 DB commit은 서로 다른 경계입니다.
- partition 내부의 로그 순서와 여러 partition의 전역 순서, 처리 완료 순서는 다릅니다.
- idempotent producer는 임의 애플리케이션 재전송을 business key로 제거하는 기능이 아닙니다.
- Kafka transaction은 임의 PostgreSQL/ClickHouse 쓰기를 자동으로 포함하지 않습니다.
- consumer lag는 데이터 정확성·신선도·업무 처리 완료를 단독으로 증명하지 않습니다.
- replication, MirrorMaker, 백업, 애플리케이션의 재처리 가능 기간은 같은 보장이 아닙니다.

각 실험은 가설 → 예상 불변식 → 실행 → 원시 증거 → 실패 반례 → 설계 결정으로 작성합니다. 이 자료의 처리량·RPO·RTO 숫자는 입력 규모나 학습용 목표이며 측정 결과를 주장하는 값이 아닙니다.
