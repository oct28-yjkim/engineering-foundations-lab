# LLM 실험 보고서 양식

## 실험 선언

- run ID·작성자·시작/종료 시각:
- 연결 논문/version·모듈:
- 실행 범위: CPU-MODEL / SMALL-MODEL / GPU-EXTENSION / API-EXTENSION:
- 가설·반증 조건·사전 통과 기준:
- 상태: 설계 / 실행 / oracle 검증 / 결론 보류:

## 고정한 조건

- code commit·변경 diff·실행 명령:
- Python/OS·library lock·hardware/driver:
- model/tokenizer/dataset revision 및 입력 hash:
- 데이터 출처·사용 권한·split·중복/누출 검사:
- prompt/template·token mask·길이·generation 설정:
- seed·반복·batch/concurrency·cache/warmup:
- 외부 요청/다운로드 여부, token/시간/비용 상한:
- 중단 조건·보존/정리 범위:

비밀값은 적지 않습니다. 공개할 수 없는 항목은 secret 참조/비식별 ID와 제한 이유로 대체합니다.

## 독립 정답과 대조군

- hand calculation 또는 독립 reference:
- baseline·변경 하나·ablation 하나:
- 음성 대조군과 고의 결함이 검출되는 이유:
- 실제 모델 미사용 시 무엇을 검증하지 못하는가:

| 지표·단위·분모 | 원논문 값과 조건 | 사전 기대/허용 범위 | baseline 실측 | 변경 실측 | ablation 실측 |
| --- | --- | --- | --- | --- | --- |
| 미기입 | 미기입 | 미기입 | 미실행 | 미실행 | 미실행 |

## 실패와 통계

- 항목별 raw 결과, 실패/timeout/거절/abstention/누락:
- paired 비교 단위, interval 방법·seed·반복 수:
- 품질 외 latency/memory/cost와 slice별 악화:
- test를 보고 바꾼 설정과 새 holdout 필요 여부:
- 모델/judge/환경 변동·상관·대표성의 한계:
- 원인 가설, 배제한 대안, 아직 미확정인 경계:

## 결론과 재현

- 이 증거가 지지하는 주장 한 문장:
- 지지하지 않는 더 넓은 주장:
- 개선이 실패하는 workload/조건:
- 동료가 반복할 순서와 실제 예상 관찰:
- 변경을 실무에 적용하기 전에 추가할 검증:

관련 [논문 리뷰](paper-review.md), 코드, 테스트, 비밀 제거 로그를 연결합니다. 잘못된 결과·실패 run도 보존합니다.
