# Qdrant LAB 검증 기록

검증일 **2026-10-04**, Windows amd64, Python 3.12.14. 이 기록은 코드·문서·구성 검사를 실제 서버 검증과 분리합니다. Docker CLI는 있으나 Docker Desktop Linux engine pipe가 없어 **실제 서버를 시작하지 못했습니다**. 이미지 다운로드·Qdrant API 실행·collection 생성·node stop/start는 하지 않았습니다.

## 수행한 검사

| 검사 | 결과 | 입증하지 못하는 것 |
| --- | --- | --- |
| Python client 단위 테스트 | socket 차단 mock 테스트 **21개 PASS** | 실제 서버의 요청 수락·검색·WAL·optimizer·복제 |
| 최적화 모드 | 같은 suite `python -O` **21개 PASS** | 다른 Python/OS/서버 버전의 동일 동작 |
| 기본 `--plan --scenario all` | 무송신 계획 출력 PASS | 실제 collection 생성/회복 |
| 단일 Compose | `config --services`=qdrant, 정규화 JSON 확인 | 이미지 존재/실제 기동·network·volume 동작 |
| 선택 cluster Compose | qdrant1/2/3, 별도 project·volume·loopback REST·1GiB/node 설정 확인 | bootstrap·3 peer/9 copies·노드 장애·가용성 |
| PowerShell 수동 안내 | 13개 fenced block 구문 오류 0; multivector JSON 배열 모양 별도 검산 | 해당 요청의 실제 실행과 기대값 |
| 공개 source/API | annotated tag와 peeled SHA 구분, Docker CMD·config·OpenAPI·RRF 코드 대조 | upstream suite·Rust build·버전 간 호환성 |
| 문서 연결 | 저장소 Markdown 303개·내부 링크 2,159개 검사, 오류 0; Qdrant 공식 문서 URL 25개 HTTP 200 확인 | 외부 문서의 장기 유지·모든 기능의 실제 동작 |
| 변경 형식 | `git diff --check` PASS | 문서의 실제 렌더링·제품 성능 |

태그 `v1.19.1`의 실제 commit은 **`6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de`**입니다. `de333e3c04660fe475d6275e9efc9fb9f54138fe`는 annotated tag object이며 구현 revision으로 사용하지 않습니다. [고정 소스 지도](../source-reading.md)

코드 테스트는 literal ID/점수와 별도 rank 계산으로 oracle을 검산합니다. float oracle의 1ULP 차이는 근사 비교로 처리하며 서버 점수 tolerance는 `1e-5`입니다. 정상·비정상 URL/버전·기존 collection 거부, 요청/응답 크기·시간/횟수 상한, redirect/재시도 부재, raw error 비출력, 실제 socket 차단도 검사합니다. mock의 PASS를 API 실행 PASS로 승격시키지 않습니다.

## 재실행

저장소 루트에서 다음 검사는 서버 없이 실행할 수 있습니다.

```text
python -B -m unittest discover -s search/qdrant/labs -p test_qdrant_lab.py -v
python -B -O -m unittest discover -s search/qdrant/labs -p test_qdrant_lab.py -v
python -B search/qdrant/labs/qdrant_lab.py --plan --scenario all
docker compose -f search/qdrant/compose.yaml config --services
docker compose -f search/qdrant/compose.cluster.yaml config --services
```

실제 엔진 시험은 Docker를 준비한 후 [환경](../environment.md)→[기본](README.md)→[고급 기능](advanced.md)→[별도 3노드](cluster.md) 순서로 선택합니다. 자신의 실행일·OS·engine/Compose·image digest·서버 응답 version·collection·요청 원장·실제 결과를 추가 기록합니다. 기존 기록을 덮어쓰지 않습니다.

## 미검증 범위

- 기본 runner의 실제 1.19.1 API 응답, dense/sparse/RRF 결과, 잘못된 입력 거부와 복구
- nested/MaxSim/strict mode/alias/snapshot 수동 LAB의 실제 결과·timeout 이후 상태
- 3노드 bootstrap, replica 배치/transfer, write/read consistency와 한 노드 이탈/복귀
- Docker 이미지 pull·startup·internal network/loopback의 OS별 동작, persistence·재시작
- ANN 인덱스 사용/Recall@k·quantization·memory tier·cold/warm 성능·장시간 부하
- 인증·TLS·JWT/tenant 인가, remote backup·host/AZ 손실·partition·upgrade/reshard

기능 설명과 실행 절차가 제공돼도 실측은 별도 관문입니다. [기능 지도](../feature-map.md)의 E/R 항목은 추가 환경·구현 또는 조사 과제이며 자동 제공으로 해석하지 않습니다. 회사 리소스·credential·사용자 데이터에는 접근하지 않았습니다.
