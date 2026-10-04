# Qdrant 실습 환경

[시작](README.md) · [단일 노드 LAB](labs/README.md) · [분산 LAB](labs/cluster.md)

Docker Compose v2와 Python 3.10+를 준비합니다. 추가 SDK나 모델은 설치하지 않습니다. PowerShell 수동 LAB은 PowerShell 7을 사용합니다. 이미지 다운로드·서버 기동은 학습자가 명시적으로 수행하며 회사 endpoint/credential·기존 DB를 연결하지 않습니다.

## 단일 노드

저장소 루트에서 명령을 하나씩 실행하고 오류면 중단합니다.

```text
docker compose -f search/qdrant/compose.yaml config --services
docker compose -f search/qdrant/compose.yaml up -d
docker compose -f search/qdrant/compose.yaml ps
docker compose -f search/qdrant/compose.yaml logs --tail 80 qdrant
```

기본 파일은 `qdrant` 한 서비스, host `127.0.0.1:16333` → container REST `6333`입니다. gRPC `6334`와 P2P `6335`는 host에 공개하지 않습니다. telemetry·CORS는 비활성화하고 내부 Docker network만 사용합니다. 이미지 pull은 호스트 Docker가 수행하므로 network 설정이 다운로드를 막는다는 뜻은 아닙니다.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:16333/' -TimeoutSec 10 -NoProxy
Invoke-RestMethod -Uri 'http://127.0.0.1:16333/readyz' -TimeoutSec 10 -NoProxy
```

`/`의 version이 1.19.1인지 확인합니다. `/readyz` 성공과 collection의 데이터·색인 완료는 다릅니다. 엔진에 curl이 있다고 가정한 healthcheck는 넣지 않았습니다. 시작에 시간이 필요하면 최대 60초 범위에서 직접 다시 확인하고 실패 원인을 logs에서 조사합니다. 무제한 재시도하지 않습니다.

단일 컨테이너 제한은 1GiB·2CPU이며 작은 fixture용 **학습 예산**입니다. 실제 제품의 최소 사양이나 성능 권장치가 아닙니다. 이미지·volume 여유 공간도 필요합니다. Windows 경로 bind mount 대신 Docker named volume을 사용합니다. [공식 local quickstart](https://qdrant.tech/documentation/quickstart/), [설치·스토리지 제약](https://qdrant.tech/documentation/installation/)

## 분산 환경은 별도 선택

`compose.cluster.yaml`은 다른 프로젝트·volume·포트를 쓰는 **독립 3노드**입니다. 단일 노드 파일과 여러 `-f`로 합치지 않습니다. container 제한 합계 3GiB·3CPU 외에 Docker/OS 여유 자원이 필요합니다. peer traffic은 프로젝트 내부 `6335`, REST 관찰은 host `16343/16344/16345`를 사용합니다. 시작·중단·실험 순서는 [분산 LAB](labs/cluster.md)을 따릅니다.

노드 3개를 켠 것만으로 모든 데이터가 3중 복제되는 것은 아닙니다. collection의 shard 수·replication factor·write consistency와 실제 shard 상태를 별도로 확인합니다. 인증·TLS·다른 failure domain은 제공하지 않습니다.

## 데이터와 정지

runner는 매번 새 `efl_qdrant_<32hex>` collection을 만들고 종료 시 보존합니다. 수동 LAB은 별도 `efl_qdrant_adv_...` / `efl_qdrant_cluster_...` 이름을 씁니다. 기존 collection을 비우거나 삭제해서 재사용하지 않습니다. snapshot은 원본 volume과 다른 named volume에 있지만 **같은 Docker 호스트**에 있으므로 host 장애 대비 백업이 아닙니다.

```text
docker compose -f search/qdrant/compose.yaml stop
```

stop은 데이터·snapshot을 삭제하지 않습니다. 재시작은 같은 파일의 `start`, 컨테이너/network 해제만 원할 때는 같은 파일의 `down`을 사용합니다. 기본 안내에 `down -v`, 전체 volume prune, 자동 collection delete를 넣지 않습니다. 결과 ID·입력·버전·관측·복구를 보존한 뒤 자신이 만든 정확한 대상만 별도로 정리합니다.

서비스는 무인증입니다. loopback은 다른 로컬 사용자를 막는 보안 경계가 아니며 Docker socket 접근자는 volume을 볼 수 있습니다. 실제 개인정보·키·운영 문서를 넣지 마세요. cloud API·Inference·embedding 다운로드·MCP 연결은 기본 과정 밖의 별도 선택입니다.
