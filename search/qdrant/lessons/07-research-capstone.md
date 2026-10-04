# 07. 고정 소스와 작은 반증 연구

[과정](../curriculum.md) · [소스 지도](../source-reading.md) · [평가](../assessment.md)

<a id="qd13"></a>
## QD13 — API 결과에서 구현의 실패 분기까지

질문 하나를 선택합니다: nested filter가 왜 다른 ID를 반환하는가, exact/ANN이 어디서 나뉘는가, timeout 뒤 write는 무엇을 남기는가, snapshot에 어떤 자료가 들어가는가. 최신 main 대신 고정 **1.19.1 commit**에서 요청/자료구조/상태/관측 지점을 추적합니다.

1. 기본 또는 수동 LAB의 실제 입력·출력·server version을 보존합니다. 아직 실행하지 않았다면 예상 결과로 표시합니다.
2. [소스 지도](../source-reading.md)의 경로에서 함수 5개, 자료구조 2개, 오류/거부 분기 1개를 선택하고 호출 관계를 정리합니다. 파일명만 제출하지 않습니다.
3. 해당 upstream 테스트의 fixture와 assertion을 읽습니다. 프로젝트 build/test 의존성·자원·외부 접근을 검토한 별도 checkout에서만 선택 실행합니다.
4. test의 전제를 깨는 입력 하나를 추가하는 연구를 설계합니다. upstream의 통과를 운영 workload 전체의 보장으로 일반화하지 않습니다.
5. 논문을 골랐다면 모델 가정/거리/tie/후보 budget/데이터 크기 중 실제 엔진과 다른 점 세 개를 적습니다.

논문 선택: HNSW는 graph 탐색 가정, RRF는 후보 순위 결합, ColBERT는 late interaction 표현과 비용을 읽습니다. Qdrant MaxSim이 계산된다는 사실과 ColBERT 모델 학습/논문 성능 재현은 다릅니다. 모델 자체 실험은 [LLM 논문 LAB](../../../ai/llm-paper-lab/README.md)에 별도 범위를 잡습니다.

제출: 관측→가설→고정 symbol→반례→결과/미실행→한계. Rust unit/integration/OpenAPI 테스트가 어떤 server/process/디스크를 요구하는지 확인하며 저장소에 제공한 Python 단위 테스트와 혼동하지 않습니다.

<a id="qd14"></a>
## QD14 — 2주 최소 변경 연구

한 collection/query 경로에 한 변경과 두 실패를 연결합니다. 예: payload 타입 계약 강화 + 잘못된 filter/누락 필드, alias 전환 + 새 모델 vector 누락/잘못된 rollback 대상, hybrid budget 변경 + 후보 누락/tenant 경계입니다. 실제 부하/HA 실험은 앞서 준비된 해당 환경이 있을 때만 선택합니다.

| 시점 | 작업 | 통과 조건 |
| --- | --- | --- |
| 1주 전반 | 기존 fixture 정상 기준선과 독립 정답 | IDs·schema·query·버전·자원 상한 기록 |
| 1주 후반 | 한 변인 변경, 기능 채택/비채택 비교 | 정합 유지와 측정 가능한 차이 |
| 2주 전반 | 서로 다른 실패 조건 두 개 | 경쟁 가설·원시 증거·제한 조치 |
| 2주 후반 | 회복 검산·구술·재현 | 동료가 임의 ID/query를 추적, 미검증 영역 명시 |

독립 oracle은 검증 대상의 같은 ranking 함수를 다시 호출하지 않습니다. 작은 literal ID/score 표나 별도 수작업 정답을 사용하고 반올림/동률 규칙을 명시합니다. 부하 도구의 successful count가 업무 성공률을 대신하지 않습니다.

최종 산출물은 정상→문제→조치→회복 시간선, 기능 판단 다섯 칸, source revision, 코드/설정 diff, 원시 지표, exact/relevance 구분, 잔존 collection/snapshot 목록입니다. 자신의 자료만 정리하고 원본 snapshot·공유 volume을 삭제하지 않습니다. “추가 실험 필요”도 유효한 결론이지만 미완료 gate를 PASS로 바꾸지는 않습니다.
