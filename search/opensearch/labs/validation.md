# 검증 기록 — 제공물과 미검증 경계

확인일: **2026-10-04**. 환경: Windows, CPython **3.12.14**, Docker CLI 27.5.1 / Compose **2.32.4-desktop.1**. 지원 문법 기준은 Python 3.10 이상이지만 Python 모든 minor 버전·OS 조합을 실행한 것은 아닙니다.

## 수행한 검사

| 항목 | 결과 | 해석 |
| --- | --- | --- |
| CPU CLI `--lab all` | 4개 PASS, 일반/`-O` 각각 수행 | 명시된 수학·가시성·후보 모델의 oracle |
| `test_offline_lab.py` | 96개 PASS, 일반/`-O` 각각 수행 | 정상·경계·반례·입력 검증·독립 손계산 |
| `test_engine_lab.py` | 43개 PASS, 일반/`-O` 각각 수행 | 소켓 없는 fake HTTP 응답으로 client 계약 검증 |
| 전체 신규 테스트 | 139개 PASS, 일반/`-O` 각각 수행 | 같은 139개를 두 모드로 실행한 것이며 서로 다른 테스트 278개가 아님 |
| native `--help` | 정상, HTTP 호출 없음 | 선택 실행 인자 안내 |
| Docker Compose `config --quiet` | PASS | YAML/Compose 구문, 실제 container 시작 아님 |
| 기존 LLM·IaC 테스트 | 50개·82개 PASS | 기존 CPU 실습의 회귀 검사 |
| 저장소 Markdown 링크·fence 검사 | 164문서·내부 링크 950개, 오류 0 | 파일/anchor 존재와 코드 fence 짝 검사 |
| 새 트랙의 OpenSearch 공식 문서 링크 | 32개 HTTP 200 | 링크 접근성 확인, 전체 설명의 실행 검증은 아님 |

단위 테스트는 테스트용 `assert`를 사용할 수 있지만, 실습의 핵심 oracle은 최적화 모드에서 제거되지 않는 예외 기반 검사입니다. mock workflow의 응답은 실제 서버가 생성한 데이터가 아니며 OpenSearch 동작의 실측 증거가 아닙니다. 독립 코드 리뷰에서도 문서 top-k의 충분조건과 bucket/RRF 반례, fresh-index 쓰기 범위를 검토했습니다.

## 수행하지 못했거나 범위 밖인 검사

- 실제 OpenSearch 이미지 다운로드·container 시작·REST fixture 실행은 **미수행**입니다. Docker Linux 엔진 pipe `dockerDesktopLinuxEngine`이 없어서 server 연결을 할 수 없었습니다. Docker Desktop을 자동 실행하거나 host kernel 설정을 바꾸지 않았습니다.
- OpenSearch 3.9.0·Lucene 10.5.1·k-NN 3.9.0.0의 release/commit/소스 경로는 확인했지만 source build와 Java 회귀 테스트는 수행하지 않았습니다. [소스 지도](../source-reading.md)를 참고합니다.
- replica·manager 선출·실패 주입·crash 내구성·snapshot/restore·TLS/DLS/FLS는 미검증입니다.
- 실제 embedding·HNSW·ANN 성능·production relevance·RAG 답변은 미검증입니다.
- 클라우드 계정·AWS OpenSearch Service/Serverless·유료 자원은 생성하지 않았습니다.

## 사용자 환경의 실제 엔진 검증

[준비와 안전 범위](README.md)를 읽은 뒤 별도 선택 실행합니다.

```text
docker compose -f search/opensearch/compose.yaml config --quiet
docker compose -f search/opensearch/compose.yaml up -d --wait
python -B search/opensearch/labs/engine_lab.py --run-local
```

실제 runner의 `mode: local_engine`과 `status: PASS`, 신규 index 이름, 최종 문서 6개 oracle을 확인하고 image digest·서버/플러그인·host fingerprint를 보고서에 남깁니다. 실패했다면 stage와 보존 index를 기록하고 검증 상태를 실패/미완료로 유지합니다. healthcheck나 mock PASS로 대체하지 않습니다. 성공해도 단일 노드 합성 fixture만 통과한 것이며 위의 미검증 항목은 자동으로 완료되지 않습니다.
