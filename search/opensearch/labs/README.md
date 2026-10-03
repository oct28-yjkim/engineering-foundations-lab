# OpenSearch 실습 — 실제 엔진 관측과 트러블슈팅

[트랙](../README.md) · [운영 runbook](../operations.md) · [선택 원리 부록](offline.md) · [검증 기록](validation.md)

기본은 실제 OpenSearch의 요청·node/cluster 지표·검색 결과를 연결해 진단하는 경로입니다. 아래 환경과 [운영 runbook](../operations.md)을 사용합니다. 환경이 없으면 설계/원리 학습으로 진행하고 운영 관문은 미완료로 남깁니다. 모든 명령은 저장소 루트에서 실행합니다.

## 1. 실제 로컬 OpenSearch 3.9.0 준비

준비물은 Docker Desktop/Linux 컨테이너 엔진, Compose v2, 이미지 다운로드 네트워크와 디스크입니다. [공식 Docker 설치 안내](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/)는 Docker Desktop에 최소 4GB 메모리 할당, Linux VM의 `vm.max_map_count` 등 host 조건을 설명합니다. 설정 위치는 Linux·WSL·Docker Desktop 버전에 따라 다릅니다. 이 저장소나 runner는 host 설정을 변경하지 않습니다.

[Compose](../compose.yaml)는 노드 memory 2GB 제한·heap 512MB·CPU 2개를 작은 fixture의 출발 예산으로 둡니다. Docker VM 전체 예산과 Java heap, 컨테이너 제한은 서로 다릅니다. 이것이 대량 색인·벡터 검색에 충분하다는 뜻은 아닙니다. OOM/부팅 실패 시 로그·host 조건·예산을 먼저 확인하고 무조건 재시작하지 않습니다.

**보안 경계:** 이 환경은 보안 플러그인·TLS·인증을 끕니다. HTTP는 `127.0.0.1:19200`에만 바인딩하고 transport/성능 포트와 Dashboards는 노출하지 않습니다. 그래도 같은 호스트 사용자·포트 포워딩·같은 컨테이너 네트워크로부터 보호하는 인증 경계는 아닙니다. 공유 서버·원격 VM·운영·실제 문서/개인정보에 사용하지 않습니다. tenant query filter도 인가가 아닙니다. 실제 DLS/FLS·역할·권한 음성 검증은 별도 보안 환경 과제입니다.

```text
docker version
docker compose -f search/opensearch/compose.yaml config --quiet
docker compose -f search/opensearch/compose.yaml up -d --wait
docker compose -f search/opensearch/compose.yaml ps
docker compose -f search/opensearch/compose.yaml logs --tail=60 opensearch
python -B search/opensearch/labs/engine_lab.py --help
python -B search/opensearch/labs/engine_lab.py --run-local
```

`up`은 이미지를 내려받고 로컬 컨테이너·network·named volume을 생성합니다. DB/Kafka와 프로젝트·network·volume이 분리돼 있으며 root Compose와 자동 연결되지 않습니다. Docker daemon이 꺼져 있으면 여기서 중단하고 사용자 환경에서 직접 준비합니다. healthcheck 통과는 아래 fixture 검증이나 HA 보장이 아닙니다.

### REST runner의 쓰기 범위

`--help`와 인자 없는 실행은 네트워크를 호출하지 않습니다. `--run-local`만 쓰기를 시작하며 URL/host/index override는 없습니다. `http://127.0.0.1:19200`의 distribution=`opensearch`, version=`3.9.0`, cluster=`engineering-foundations-opensearch-lab`, node=`opensearch-lab`를 먼저 확인합니다. 이 식별자는 실수 방지이며 서버 진위 인증이 아닙니다.

매번 `efl-os-<UUID>` 신규 index 하나만 생성하고 합성 문서 6개를 넣습니다. 기본 환경 proxy와 redirect는 사용하지 않으며 응답 크기 5MiB, 요청 32회, socket 작업당 timeout 10초를 제한합니다. 전체 실행 wall-clock deadline 보장은 아닙니다. 기존 index 수정·삭제, 전체 index 탐색, 원격 연결, 임의 endpoint 호출 기능은 없습니다.

실패하면 stage·신규 index 식별자를 출력하고 중단합니다. 재시도는 새 index를 만들며 실패한 index를 덮어쓰거나 자동 삭제하지 않습니다. 반복 실행 시 데이터가 누적되므로 출력한 index와 용량을 실습 원장에 기록합니다. 오류 상세에 비밀이 있을 수 있어 원격 응답 body를 그대로 출력하지 않습니다.

### fixture와 정확성 oracle

`title`은 standard analyzer를 쓰는 text, `title.raw`/`tenant`/`doc_id`는 keyword, `price`는 강제 형변환을 끈 integer입니다. dynamic mapping은 strict, primary 1개·replica 0개·자동 refresh off(`-1`)입니다.

| ID | tenant | title | price |
| --- | --- | --- | --- |
| a1 | alpha | Quick brown fox | 10 |
| a2 | alpha | Quick blue fox | 20 |
| a3 | alpha | Brown fox handbook | 30 |
| b1 | beta | Quick brown fox | 15 |
| b2 | beta | Slow green turtle | 5 |
| b3 | beta | Brown fox quick guide | 25 |

아래는 **기대값**이며 [검증 기록](validation.md)에서 실제 수행 여부를 따로 확인합니다.

| 순서/질의 | 통과 조건 |
| --- | --- |
| bulk create 후 refresh 전 | realtime GET a1은 존재하지만 검색 total은 0 |
| 명시적 refresh 후 | 검색 6건·shard 실패 0·partial/timed-out 응답 거부 |
| tenant=`alpha` filter | a1,a2,a3 (권한 검사가 아닌 query 결과) |
| `title.raw` term=`Quick brown fox` | a1,b1 |
| text match `quick brown`, AND | a1,b1,b3 |
| match phrase `quick brown` | a1,b1 |
| price 10 이상 20 이하 | a1,a2,b1 |
| price 오름차순 | b2,a1,b1,a2,b3,a3 |
| tenant terms aggregation | alpha=3,beta=3 |
| OCC update a1 price 10→11 | 관측한 seq_no/primary_term으로 1회 성공, 같은 token 재사용 409 |
| negative bulk | 중복 a1 create=409, 새 ID의 잘못된 price=400, item별 검사 |
| 최종 refresh 후 전체 비교 | a1 price만 11, 나머지 원본과 동일한 정확한 6개 `_source` 및 bucket |

점수의 소수점·내부 doc ID·segment 수는 oracle로 고정하지 않습니다. bulk HTTP 200이 모든 item 성공을 의미하지 않습니다. 현재 fixture에 한해 bucket이 정확한 것이며 대규모 multi-shard terms 정확성을 증명하지 않습니다. single-node ACK와 OCC 통과도 replica 장애·선출·디스크 손실을 검증하지 않습니다.

## 2. 필수 운영 진단

[운영 runbook](../operations.md)에서 실제 정상 기준선과 가시성·mapping 오류·allocation 중 최소 두 사건을 수행합니다. 각 사건의 경쟁 가설, HTTP/item 오류, gauge/counter 차이, 조치·되돌림·정확한 문서 검산을 제출합니다. 위 runner의 정상 fixture PASS만으로 이 관문은 통과하지 않습니다.

## 3. 보존·중지·재현

```text
docker compose -f search/opensearch/compose.yaml images
docker image inspect opensearchproject/opensearch:3.9.0 --format '{{json .RepoDigests}}'
docker compose -f search/opensearch/compose.yaml stop
docker compose -f search/opensearch/compose.yaml start
```

`stop/start`는 volume을 보존합니다. 정리·volume 삭제는 자동 제공하지 않으며, 학습 결과를 보존하고 실제 프로젝트/volume/index 소유권을 확인한 뒤 별도로 결정합니다. 이 환경에 중요한 기존 데이터를 연결하지 않습니다. 엄밀한 재현에는 관측한 image digest·아키텍처·Java/OS·설정·git commit·실행 원장을 저장하고, 관측하지 않은 digest를 문서에 만들어 넣지 않습니다.

## 4. 다음 실험

OS01–04는 analyzer·mapping·visibility, OS05–06은 explain/profile·정답 집합, OS07–10은 별도 복제/보안/복원 환경, OS11–12는 실제 vector index와 exact baseline을 구성합니다. 기본 runner는 k-NN index, multi-node cluster, snapshot repository, AWS OpenSearch Service, embedding 모델을 생성하지 않습니다. 세부 과제는 [커리큘럼](../curriculum.md)과 [선택 연구](../../../capstones/search-quality-recovery.md)를 따릅니다.

## 부록: 선택 오프라인 원리 모형

Python 3.10 이상 표준 라이브러리만 필요합니다. 모형 학습을 생략해도 운영 과정의 진입에 문제가 없으며, 모형/HTTP mock 테스트의 PASS는 실제 엔진 성공을 의미하지 않습니다.

```text
python -B search/opensearch/labs/offline_lab.py --lab all
python -B -m unittest discover -s search/opensearch/labs -p "test_*.py" -v
```

| 이름 | 검산할 원리 | 증명하지 않는 것 |
| --- | --- | --- |
| `bm25` | df·tf·길이 정규화·작은 순위 반례 | Lucene의 정확한 점수·운영 품질 |
| `refresh` | realtime/search 가시성 | translog·fsync·내구성 |
| `distributed-topk` | 후보 절단·집계 누락 | shard scoring·네트워크·복제 |
| `hybrid-filter` | RRF·후보 coverage·filter | embedding·HNSW·보안·성능 |

기존 [검증 기록](validation.md)은 보조 코드 검증의 과거 기록으로 보존합니다.
