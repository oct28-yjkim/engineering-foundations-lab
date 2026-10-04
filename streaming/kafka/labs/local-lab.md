# 로컬 Kafka 실습: 실행한 범위와 보장 경계

실무 시작점은 [운영 관측·트러블슈팅](../operations.md)의 실제 baseline입니다. 아래 smoke는 환경·정확성 준비 확인이며 수료 기준이 아닙니다. 준비 후 lag·ISR·요청 지연의 읽기 전용 관측, 격리된 증상 재현, 원복과 업무 복구 증거를 남깁니다.

이 환경은 **Apache Kafka 4.3.1 JVM 이미지의 단일 combined KRaft 노드**입니다. broker와 controller가 같은 프로세스에서 동작하며, topic·key·partition·offset·클라이언트 요청을 작은 입력으로 관찰합니다. 복제 가용성, controller 다수결 상실, 호스트 장애 내구성을 검증하는 환경은 아닙니다. Kafka Connect/CDC connector, Streams 애플리케이션, Schema Registry, 모니터링 서버는 포함하지 않습니다.

모든 명령은 `engineering-foundations-lab` **저장소 루트**에서 실행합니다. 이 페이지의 `docker ...` 명령은 PowerShell/Bash에서 한 줄씩 사용할 수 있습니다. shell script는 호스트가 아닌 컨테이너의 Bash에서 실행하므로 Windows에 WSL이나 로컬 Java를 설치할 필요가 없습니다.

## 1. 구성과 실제 주소

사용 파일은 [독립 Compose](../compose.yaml)입니다. 프로젝트 이름은 `engineering-foundations-kafka-lab`이며 [PostgreSQL](../../../databases/postgresql/compose.yaml)·[ClickHouse](../../../databases/clickhouse/compose.yaml)도 각각 독립 프로젝트입니다. 각 제품의 network·volume·수명 주기를 공유하지 않고 CDC 연결도 자동 구성하지 않습니다. 모든 Kafka 명령에 `-f streaming/kafka/compose.yaml`을 유지합니다.

| 접근 위치 | bootstrap / listener | 의미 |
| --- | --- | --- |
| 호스트의 앱/CLI | `localhost:9092` / EXTERNAL | 호스트 포트는 `127.0.0.1`에만 공개 |
| Kafka 컨테이너와 동일 Compose network | `kafka:19092` / INTERNAL | 제공 script가 사용하는 주소 |
| 단일 controller voter | `1@kafka:9093` / CONTROLLER | 클라이언트 endpoint가 아니며 호스트에 publish하지 않음 |

`listeners`는 서버가 bind할 주소, `advertised.listeners`는 metadata 응답에서 클라이언트에 알려 줄 주소입니다. bootstrap에 한 번 접속했다고 후속 broker 접속까지 성공한 것은 아닙니다. 컨테이너가 호스트용 `localhost:9092`를 metadata로 받으면 자기 자신을 가리킬 수 있으므로 listener를 분리합니다. 원격 PC 접근이나 TLS/SASL은 이 구성의 범위 밖입니다. [공식 listener 설명](https://kafka.apache.org/43/security/listener-configuration/)

Kafka 4.3.1 자체의 KRaft 기능과 Docker entrypoint의 선택을 구별합니다. 이 릴리스의 공식 Docker wrapper는 호환성을 위해 **static `controller.quorum.voters`**를 사용해 storage format을 호출합니다. 이 Compose도 `1@kafka:9093`를 사용하며, dynamic quorum의 초기화/멤버 변경 절차를 실행한 것으로 간주하지 않습니다. [4.3.1 Docker wrapper](https://github.com/apache/kafka/blob/4.3.1/core/src/main/scala/kafka/docker/KafkaDockerWrapper.scala), [공식 이미지 예제](https://github.com/apache/kafka/blob/4.3.1/docker/examples/docker-compose-files/single-node/plaintext/docker-compose.yml)

일반 topic의 기본 partition 수는 3, replication factor와 `min.insync.replicas`는 1입니다. `__consumer_offsets`, transaction state 및 share coordinator state의 replication 관련 값도 한 노드에서 생성 가능하도록 1로 설정했습니다. 내부 offset/transaction topic의 partition 수는 작은 실습을 위해 3입니다. 이것은 운영 권장값이 아닙니다. `acks=all`도 이 환경에서는 현재 ISR의 한 replica 응답을 기다리는 것이며, 복제본 여러 개나 매체 강제 flush의 증명이 아닙니다.

## 2. 시작과 환경 지문

Docker Desktop의 Linux 컨테이너 엔진과 Compose v2가 필요합니다. broker의 JVM heap은 256–768MiB, 컨테이너 메모리 제한은 2GiB입니다. heap 외 native memory, page cache, 함께 실행하는 CLI도 예산에 포함됩니다. 이것은 모든 학습 workload의 최소 메모리 보장이 아닙니다.

```text
docker version
docker compose -f streaming/kafka/compose.yaml config --quiet
docker compose -f streaming/kafka/compose.yaml up -d --wait --wait-timeout 180
docker compose -f streaming/kafka/compose.yaml ps
docker compose -f streaming/kafka/compose.yaml logs --tail=80 kafka
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/00-inspect.sh
docker image inspect apache/kafka:4.3.1 --format '{{json .RepoDigests}}'
```

`00-inspect.sh`는 버전, 선택한 설정, storage identity, broker API, metadata quorum, 지원/확정된 feature level, topic/group 목록을 조회합니다. 바이너리 버전만으로 `metadata.version`, `kraft.version`, ELR 등 feature의 활성 상태를 단정하지 말고 실제 finalized level을 기록합니다. 기존 topic이나 offset을 변경하지 않습니다. fresh 환경에서 consumer group 목록이 비어 있어도 정상입니다. healthcheck는 API 응답 확인이며 데이터 정합성 시험은 다음 smoke가 맡습니다.

정확 버전·image digest·OS/CPU/메모리 제한·실행 시각을 기록합니다. [공식 Docker 안내](https://kafka.apache.org/43/getting-started/docker/)의 4.3.1 이미지와 같은 release의 소스를 기준으로 했으며, `latest` 태그나 다른 vendor 이미지의 환경변수를 섞지 않습니다. 필요하면 관측한 image digest로 별도 override를 작성하되 기존 volume의 호환성부터 검토합니다.

## 3. 결정적 smoke와 exact oracle

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/01-smoke.sh
```

자동 생성한 `RUN_ID`와 `TOPIC`을 출력합니다. 이름을 직접 정하려면 아래처럼 **이번 실행에 새 이름**을 전달합니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/01-smoke.sh lesson01-run01
```

topic은 `efl-smoke-lesson01-run01-events`가 됩니다. 같은 이름이 있으면 produce 전에 중단합니다. 새 topic 생성 후 중간에 실패해도 topic을 자동 삭제하지 않습니다. 실패 증거를 먼저 조사하고 새 run ID로 다시 실행합니다. script는 다른 topic을 수정하거나 consumer group offset을 reset하지 않습니다.

smoke는 한 producer가 3개의 UTF-8 key를 번갈아 보내며 key별 `seq=1..4`인 총 12개 record를 만듭니다. value에는 고유 event ID, sequence, 정수 cents가 있습니다. 4.3.1 기본 keyed partitioner, 이 key byte들, partition 수 3을 고정했을 때의 예상은 다음과 같습니다.

| key | partition | seq | 해당 partition의 offset | cents |
| --- | --- | --- | --- | --- |
| `account-B` | 0 | 1, 2, 3, 4 | 0, 1, 2, 3 | 1, 2, 3, 4 |
| `account-A` | 1 | 1, 2, 3, 4 | 0, 1, 2, 3 | 101, 102, 103, 104 |
| `beta` | 2 | 1, 2, 3, 4 | 0, 1, 2, 3 | 201, 202, 203, 204 |

이 mapping은 `toPositive(murmur2(serializedKey)) % partitionCount`를 기준으로 만든 고정 fixture입니다. 키 직렬화, partitioner, partition 수를 바꾸면 oracle도 다시 검토해야 합니다. 서로 다른 key가 반드시 서로 다른 partition을 사용하는 것은 아닙니다. [4.3.1 BuiltInPartitioner](https://github.com/apache/kafka/blob/4.3.1/clients/src/main/java/org/apache/kafka/clients/producer/internals/BuiltInPartitioner.java)

producer는 `--sync`, `acks=all`, `enable.idempotence=true`, `max.in.flight.requests.per.connection=1`로 작은 입력을 전송하고 전송 실패 시 중단합니다. 이 설정은 성능 benchmark용이 아닙니다. consumer는 partition을 직접 assign하고 auto commit을 끈 채 읽습니다. 애플리케이션의 기존 consumer group offset을 진행시키지 않으며 rebalance 자체를 시험하지도 않습니다.

각 partition의 **key/value/seq/offset 전체 문자열**을 독립적인 예상 문자열과 대조하고, 읽기 전후 end offset이 각각 4인지 확인합니다. 모든 비교가 맞으면 `PASS`와 합계 `1230 cents`를 출력합니다. 반환 행 수만 세는 시험이 아니므로 값 바뀜·누락·중복·partition 이동·순서 변화가 비교 실패로 드러납니다. timeout 이후 consumer가 종료되었다는 사실만으로 성공 처리하지 않습니다.

이 fixture는 신규 topic, 단일 writer, nontransactional record, compaction·retention 정리가 아직 없는 상태입니다. 이 조건에서만 offset 0..3과 4개 record를 직접 대응시킵니다. compaction, retention, transaction control batch가 있는 일반 topic에서 `end - start = 업무 record 수`라고 적용하지 않습니다. partition을 0→1→2로 읽어 출력하므로 화면 순서는 전체 생산 순서가 아닙니다. Kafka의 partition 내 순서와 partition 간 전체 순서는 별도 계약입니다.

기본 보존 기간은 7일입니다. retention은 정리 가능 시점과 segment 상태에 영향을 받으므로 영구 보관이나 정확한 삭제 시각을 보장하지 않습니다. 필요한 transcript와 환경 지문은 별도로 저장합니다. script는 마지막에 `TOPIC`을 남기며, PASS 출력은 실제 실행했을 때만 보고서에 붙입니다.

## 4. 읽기 전용 재관측

아래 topic 이름을 자신의 smoke 출력으로 바꿉니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/02-observe.sh efl-smoke-lesson01-run01-events
```

`02-observe.sh`는 topic metadata/config, earliest/latest offset, log directory metadata를 조회합니다. 자체적으로 consume하지 않습니다. 이후 강의에서 만든 `efl-` 접두사 consumer group을 추가 인자로 주면 group state와 committed offset도 조회합니다. 아직 commit이 없거나 group이 없는 결과를 lag 0으로 해석하지 않습니다.

```text
docker compose -f streaming/kafka/compose.yaml exec -T kafka bash /lab/scripts/02-observe.sh efl-smoke-lesson01-run01-events efl-lesson-group01
```

CLI의 위치는 `/opt/kafka/bin`, [labs 디렉터리](.)는 `/lab`에 읽기 전용 mount됩니다. 4.3.1 CLI에서는 producer의 `--reader-property`, consumer의 `--formatter-property`, client 설정의 `--command-property`를 사용합니다. 이전 이름은 해당 버전에서 deprecated 출력이 생길 수 있으므로 정확 비교용 stdout과 운영 로그를 구분합니다.

## 5. 영속성과 반복 실습

named volume `kafka-data`는 `/var/lib/kafka/data`에 연결되며 그 아래 `logs`와 `metadata`를 함께 보존합니다. 공식 4.3.1 이미지의 Dockerfile은 이 디렉터리를 비-root `appuser`가 쓸 수 있도록 준비합니다. 새 named volume은 이미지 디렉터리의 초기 소유권을 사용하므로 기본 실습에 host bind mount나 전역 chmod를 추가하지 않습니다. [4.3.1 Dockerfile](https://github.com/apache/kafka/blob/4.3.1/docker/jvm/Dockerfile)

`CLUSTER_ID`는 이 독립 학습 클러스터용 고정값입니다. 이미 format된 volume의 cluster ID, node ID, quorum 설정을 임의로 바꾸거나 다시 format하지 않습니다. image entrypoint는 설정을 만든 뒤 format을 시도하며 이미 format된 상태를 처리하는 별도 경로가 있습니다. 이것을 데이터 migration이나 손상 복구 기능으로 해석하지 않습니다. [4.3.1 launch](https://github.com/apache/kafka/blob/4.3.1/docker/jvm/launch)

일반 종료·재개는 다음과 같습니다.

```text
docker compose -f streaming/kafka/compose.yaml stop
docker compose -f streaming/kafka/compose.yaml up -d --wait --wait-timeout 180
docker compose -f streaming/kafka/compose.yaml ps
```

재시작 후 `00-inspect.sh`에서 storage identity와 cluster ID를, 같은 topic의 `02-observe.sh`에서 topic/offset metadata를 비교합니다. 이 두 script는 기존 payload 전체의 보존까지 검산하지 않습니다. payload 보존 검증은 기존 topic을 partition별·범위 제한으로 다시 읽고 이전 smoke transcript의 exact oracle과 대조하는 별도 시험입니다. 정상 stop/start의 성공은 전원 손실·디스크 손상·다중 노드 장애 복구의 증거가 아닙니다. 다시 produce하고 싶으면 새로운 run ID를 사용합니다. 이 실습에는 topic/volume 삭제 및 offset reset을 자동 수행하는 cleanup script가 없습니다.

## 6. 실패를 분류하기

| 증상 | 먼저 확인할 것 | 피해야 할 결론 |
| --- | --- | --- |
| `dockerDesktopLinuxEngine` pipe 없음 | Docker Desktop Linux 엔진 상태, Docker context | Compose/SQL 문법 오류라고 단정 |
| host 9092 bind 실패 | 이미 그 포트를 사용하는 로컬 프로세스/다른 실습 | broker 데이터 삭제로 해결 |
| bootstrap은 되지만 produce timeout | metadata가 반환한 advertised address와 접속 위치 | bootstrap TCP 성공이면 listener 정상 |
| storage permission/cluster ID 오류 | volume 대상·기존 meta.properties·이미지 사용자·로그 | root/chmod 777/재format부터 실행 |
| 건강 상태 성공, smoke 실패 | topic metadata, actual/expected records, producer 오류 | healthcheck가 정확성까지 입증 |
| oracle의 key partition 불일치 | key bytes·partition count·producer 설정·다른 writer | 임의 sort/중복 제거로 출력을 맞춤 |

2026-10-04 작성 환경에서 Compose 구문 검사와 Bash syntax 검사는 수행할 수 있었지만 Docker Linux 엔진이 실행되지 않아 **이미지 기동과 실제 smoke는 미검증**입니다. 독자는 자신의 환경에서 inspect와 smoke 결과를 얻은 뒤 런타임 검증 여부를 갱신합니다.

## 7. 다음 확장 과제

producer 재시도와 애플리케이션 재전송, group subscription/commit/rebalance, transaction의 `read_committed` 가시성은 별도 실험입니다. smoke의 idempotence 설정이나 `read_committed` consumer가 이 시험들을 자동 완료하지 않습니다.

복제·ISR 축소·leader election·controller quorum을 검증하려면 별도 프로젝트에 3 controller와 여러 broker를 구성하고, 서로 다른 장애 영역·RF/minISR·timeout·정지/복귀 절차를 명시합니다. 현재 한 노드에 replica 수만 3으로 지정하면 복제 실험 환경이 되는 것이 아닙니다. Kafka→DB side effect, CDC, Streams EOS도 필요한 클라이언트/서비스와 외부 결과 oracle을 직접 구현한 후 완료 판정합니다. 구체 모듈은 [Kafka 커리큘럼](../curriculum.md)으로 이어집니다.
