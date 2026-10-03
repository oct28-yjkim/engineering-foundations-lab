# 실험 보고서: [엔진 / 모듈 / 질문]

## 주장과 반증

- 가설:
- 경쟁 가설:
- 예상 결과와 근거:
- 가설이 틀렸다고 판단할 관측:

## 환경과 입력

- DB version / image digest / source commit:
- OS / CPU / RAM / disk / container limits:
- 설정·extension·topology:
- generator commit / row count / distribution / skew / NULL·duplicate 비율:
- cache 상태 / background 작업 / timestamp·timezone:

## 정확성

- 한 행의 의미 / key / 상태 전이 / 금액·시간 정의:
- 독립 oracle:
- 작은 반례와 expected result:
- 큰 입력 비교 결과 및 mismatch:

## 재현 순서

1. 준비와 scope:
2. baseline:
3. 한 변수 변경:
4. 결과·관측 수집:
5. 반례 실험:
6. 명시적인 대상의 cleanup:

## 측정 기록

| run | 조건 | client ms | server ms | rows/bytes 또는 buffers | CPU / peak memory / temp I/O | 정확성 |
| --- | --- | --- | --- | --- | --- | --- |
| [실측값] | | | | | | |

반복 수, warm-up, 분포 요약, 사용한 quantile 정의, 원본 로그 경로를 기록합니다. 미실행 칸을 예상 수치로 채우지 않습니다.

## 내부 동작과 결론

- SQL → 함수/자료구조 → 상태 변경 → 관측 지표:
- version과 영구 source 링크:
- 대안의 읽기·쓰기·저장·운영 비용:
- 결과 해석과 경쟁 가설 판단:
- 적용 가능한 범위 / 반례 / 미검증 범위:
- 리뷰 지적과 보완 실험:
