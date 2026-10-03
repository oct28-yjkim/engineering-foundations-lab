# 05. Raft 그룹·토폴로지·장애 모델·snapshot·독립 복구

[커리큘럼](../curriculum.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="nt09"></a>
## NT09: 서버 세 대가 아니라 어떤 합의 그룹이 살아 있는지 묻는다

선수 조건: NT05–08, leader election, quorum, failure model. NATS의 route·gateway·leaf 연결과 JetStream replica group은 같은 구성 단위가 아닙니다. Core routing 경로가 연결됐다고 모든 stream/consumer의 합의가 가능한 것은 아닙니다. [JetStream in a cluster](https://docs.nats.io/learn/topologies/jetstream-in-a-cluster), [Clustering & Replication](https://docs.nats.io/learn/clustering/)

### 원리와 내부동작

메타데이터, stream, consumer의 Raft 책임과 실제 구성원·leader·replica 설정을 분리합니다. 홀수/짝수 replica 수에 대해 다수 quorum `floor(R/2)+1`과 허용 실패 수를 계산하되, membership 변경·공통 장애·disk 상태·placement가 그 계산 밖에 있음을 표시합니다.

Raft term/index/commit/applied와 JetStream stream/consumer sequence를 동일 번호로 보지 않습니다. leader election은 새 프로세스가 켜지는 사건과 다릅니다. quorum commit, local storage write, sync 정책, publish 응답의 관계는 고정 서버 구현과 실제 설정에 연결하고 무조건적인 전원 장애 RPO=0을 가정하지 않습니다.

가설 H9: “NATS 서버 세 대 중 두 대가 실행 중이면 모든 R=3 stream의 publish와 관리 작업이 반드시 성공한다.”

### 실험

1. OFFLINE에서는 R=1/2/3/5의 quorum을 손으로 계산하고 그룹 membership이 다른 예시를 만듭니다. 이는 consensus 구현이나 실제 장애 검증이 아닙니다.
2. CLUSTER-RECOVERY 확장에서는 전용 3노드와 합성 stream을 만들고 메타/stream/consumer leader·members·placement를 먼저 수집합니다. 단일 호스트 3프로세스면 host failure domain 하나임을 명시합니다.
3. follower 하나 종료, stream leader 종료, quorum 상실을 각각 별도 실행으로 비교합니다. publish success/timeout/rejection, consumer delivery/ACK, leader 전환 시간, 최종 ID/digest를 기록합니다.
4. 네트워크 분할은 소유한 격리 환경의 명시한 link에만 적용합니다. minority/majority에서 client가 어떤 서버에 연결되는지 적고 “프로세스 alive”와 “quorum reachable”을 구별합니다.
5. route/gateway/leaf topology는 source와 설계 과제로 먼저 비교합니다. leaf 연결이 모든 저장 데이터를 자동 복제하거나 모든 cluster가 하나의 global Raft group을 공유한다고 가정하지 않습니다. mirror/source 구성은 별도 데이터 흐름으로 추적합니다.

독립 oracle: 실행 전 publish ID 원장, 확인된 PubAck 집합, timeout으로 결과가 불명인 시도 집합, 안정화 후 읽어 온 집합입니다. 확인된 메시지의 손실을 검사하되 retention으로 합법적으로 삭제된 메시지는 먼저 제외합니다. timeout을 미저장으로 분류하여 거짓 유실/성공 판정을 만들지 않습니다.

실패 조건: leader 재선출 도중 publish, lagging replica, quorum 없는 restart, 일치하지 않는 placement, route 정상/합의 불가, replica가 같은 디스크에 있는 공통 장애. 실패 주입을 실행하지 못한 경우 예상만 제출합니다.

소스 과제: `server/raft.go`, `server/jetstream_cluster.go`, stream/consumer의 replicated state 적용 지점을 읽습니다. Raft 논문의 안전성 주장과 이 구현의 disk/transport 가정을 별도 칸에 적습니다. [Raft 원 논문](https://raft.github.io/raft.pdf)

제출물·통과: 그룹별 topology, quorum 계산, 실패 타임라인, 성공/불명/거부 분류, source/test 연결. 단일 서버 smoke test를 Raft/HA 검증으로 표시하거나 replication을 backup이라고 부르면 미통과입니다.

<a id="nt10"></a>
## NT10: 복구는 원본을 다시 켠 것이 아니라 기대 상태를 되찾은 것이다

선수 조건: NT09, RPO/RTO, manifest, backup lifecycle. 복제는 잘못된 삭제나 변경도 전파할 수 있으므로 별도 복구 자산과 절차가 필요합니다. [Backup & Recovery](https://docs.nats.io/learn/backup-recovery/)

### 원리와 내부동작

stream snapshot/restore, consumer 상태, account/config/권한, client 설정, 외부 업무 DB를 각각 다른 복구 자산으로 분류합니다. snapshot을 만들었다는 성공 응답만으로 데이터 내용·consumer cursor·업무 상태가 일관되게 복구된다고 가정하지 않습니다. mirror/source는 전파 지연과 삭제/재시작 의미를 따로 가진 데이터 흐름이지 항상 독립 백업은 아닙니다.

RPO는 어떤 시점의 어느 종류 데이터에 대한 허용 손실인지, RTO는 어떤 기능의 회복 시점인지 정의합니다. 서버 health green, publish 재개, backlog 해소, 업무 원장 일치는 서로 다른 RTO 지표입니다.

가설 H10: “snapshot 파일이 있고 restore가 성공하면 업무 시스템도 이전과 동일하게 이어진다.”

### 실험

1. 전용 stream에 30개 ID를 저장하고 일부만 ACK합니다. stream config·consumer config/state·ID/digest·업무 완료 집합·기준 시각을 manifest로 작성합니다. 민감한 credential은 manifest에 넣지 않습니다.
2. 고정 버전의 지원되는 backup 절차로 자산을 만들고 checksum·tool version·snapshot 시점을 기록합니다. 실행 중인 store directory를 임의 파일 복사하는 것으로 일관된 snapshot을 대신하지 않습니다.
3. 원본과 다른 전용 저장 경로·서버·namespace에 restore합니다. 원본을 지우거나 덮어쓰지 않습니다. 실제 snapshot에 consumer 상태가 무엇까지 포함됐는지 직접 조회합니다.
4. restore 후 retained ID/digest, consumer config·pending/ACK 상태, 재전달, 외부 업무 완료 집합을 각각 비교합니다. 업무 원장이 더 최신/더 오래된 경우의 재처리·충돌 정책을 별도 실행 또는 설계로 검산합니다.
5. 버전 이전 확장은 릴리스 지침을 읽고 backup·호환성·rollback 조건을 먼저 고정합니다. binary를 옛 버전으로 교체하는 것을 안전한 데이터 downgrade라고 가정하지 않습니다. rolling restart와 실제 format migration을 구분합니다.

독립 oracle: backup 이전에 작성한 ID/digest manifest와 외부 업무 원장입니다. restore된 서버가 보고하는 count/config만 사용하면 잘못된 backup을 정상으로 오인할 수 있습니다. source에서 restore가 바꾸는 상태와 재생성하는 상태를 구분합니다.

실패 조건: 오래된 backup, 불완전 artifact, 잘못된 account/config, consumer state 누락, 외부 DB와 시점 차이, 공간 부족, 이전 실패. 손상 실험은 backup의 별도 복사본과 독립 대상에서만 수행하고 원본 파일은 보존합니다.

소스 과제: stream snapshot/restore API 진입점, `server/filestore.go`의 snapshot/recovery, consumer state 복원 경로와 관련 시험을 추적합니다. restart recovery와 다른 서버로의 restore가 공유하는 코드와 다른 검증을 설명합니다.

제출물·통과: 복구 manifest, 원본/대상 분리 증거, checksum, 세 상태(메시지/consumer/업무)의 비교, RPO/RTO와 rollback runbook. 서버 시작 성공만으로 복구 완료라고 하면 미통과입니다.
