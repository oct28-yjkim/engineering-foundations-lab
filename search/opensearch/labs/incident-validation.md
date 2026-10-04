# 기본 LAB 재편·OpenSearch 신규 실습 검증 기록

확인일: 2026-10-04. 작성된 실습 지침, 로컬 정적/계약 검사, 실제 엔진 검증을 분리합니다. [이전 OpenSearch 기록](validation.md)과 [이전 공통 운영 기록](../../../operations/validation.md)은 과거 상태로 보존합니다.

## 변경 범위

- 공통 [기본 LAB 규격](../../../operations/lab-contract.md)·[보고서](../../../operations/incident-report-template.md): 정상 기능 → 동작 원리 → 모니터링 → 제약 → 사건 진단·복구.
- LLM 논문을 제외한 15개 도구 트랙의 진입/운영 문서: 제품별 정상 기능·관측 방법·제약·사건과 회복 기준. MCP는 도구 트랙에 포함합니다. 다른 14개 트랙에 새 자동 장애 runner를 추가한 것은 아닙니다.
- OpenSearch: 정상 REST fixture는 보존하고 [5개 단계형 사건](incidents.md), [query 관측](observation.md), [선택 3→4노드 확장](scaling-incidents.md)을 연결했습니다.
- 기본 LAB과 28주 심화 완료를 구분합니다. LLM CPU 기본·GPU/API 선택 경로, 기존 제품 원리 모형과 과거 검증 기록은 보존합니다.

## 실제로 수행한 검사

| 검사 | 결과 | 증명하지 않는 것 |
| --- | --- | --- |
| Python 3.12.14, OpenSearch 전체 `test_*.py` | 일반 모드 185개, `-O` 모드 185개 통과 | OpenSearch 설치/가동/REST 호환/실제 성능 |
| 신규 incident 계약 테스트 25개 | 5개 사건의 단계별 HTTP double, 소유권·폐쇄 경로·오류·정확한 값 검산 | 실제 장애 상태·복구 성공 |
| 신규 observation 계약 테스트 21개 | fixture/정답, CLI 무통신, 샘플 집계·reset·누락, 범위/예산, HTTP double 비교 흐름 | 실제 script 비용·지연 개선·429/GC 압력 |
| 기존 테스트 139개 | 원리 모형 96 + 기존 REST 계약 43 회귀 통과 | 실제 제품 운영 숙련·HA |
| Compose `config` | 기존 단일 노드와 신규 cluster 파일, 선택 expansion profile 구성 검사 통과 | image 다운로드·container 기동·node join·복제 |
| 확장 문서 PowerShell | 10개 코드 블록 구문, helper의 소유권/ack/설정 검산 및 성공·사건 실패·재기동 실패 경로를 함수 mock으로 검사 | 실제 Docker/HTTP 실행, 강제 셸 종료 시 자동 복구 |
| Markdown 경로·anchor·fence 및 `git diff --check` | 정적 검사 통과 | 외부 링크의 영구성·각 명령의 런타임 성공 |

테스트는 네트워크 없이 Python HTTP double/mock으로 실행합니다. `-O` 통과는 `assert` 제거로 핵심 검산이 사라지지 않는지 확인하는 보조 증거입니다. 기대 응답과 실제 OpenSearch 응답이 같다는 증거로 취급하지 않습니다.

재실행 명령은 저장소 루트 기준입니다.

```text
python -B -m unittest discover -s search/opensearch/labs -p "test_*.py"
python -O -B -m unittest discover -s search/opensearch/labs -p "test_*.py"
python -B search/opensearch/labs/incident_lab.py --list
python -B search/opensearch/labs/observe_lab.py --plan
docker compose -f search/opensearch/compose.yaml config --quiet
docker compose -f search/opensearch/compose.cluster.yaml config --quiet
docker compose -f search/opensearch/compose.cluster.yaml --profile expansion config --services
```

## 실제 엔진 상태와 미수행 범위

이 호스트의 `docker info`는 `dockerDesktopLinuxEngine` named pipe를 찾지 못했습니다. Docker CLI의 Compose 구성 검사는 가능했지만 **Linux 엔진은 연결되지 않았습니다.** Docker 시작·이미지 pull·host/sysctl 변경·container 생성·실제 REST 쓰기·장애 주입을 수행하지 않았습니다.

따라서 5개 사건의 실제 `PREPARED/VERIFIED`, 관측 runner의 실제 `MEASURED`·성능 수치, 3→4노드 join·yellow/red·node 복귀·routing 분포는 **아직 미검증**입니다. TLS/권한·snapshot restore·ANN·실제 disk-full·지속 부하·cloud 확장도 실행하지 않았습니다. 수동 write-block이나 작은 routing 편중을 실제 disk pressure/포화 재현으로 부르지 않습니다.

실제 실행 후에는 버전/digest·자원·commit·실행 시각·index/run ID·정제된 원시 결과·정답·가설·제약을 별도 실측 기록으로 추가합니다. 이 과거 검증 기록을 실제 실행한 것처럼 바꾸지 않습니다. 자원 예산·격리 조건이 맞는 사용자의 환경에서 정상 기능부터 선택 실행해야 합니다.
