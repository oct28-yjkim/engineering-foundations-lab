# 검증 기록과 미실행 범위

확인일: 2026-10-04. Windows의 **CPython 3.12.14**, Python 표준 라이브러리만 사용했습니다. 공용 명령의 `python` 대신 호스트에 이미 준비된 실제 Python 실행 파일을 사용했으며 추가 설치는 하지 않았습니다.

| 실행·검사 | 실제 결과 | 의미 |
| --- | --- | --- |
| `lab.py --lab all` | 6개 결과 모두 PASS | 제공된 작은 모형과 불변식 검사 |
| 각 `--lab` 선택지 개별 실행 | 6/6 PASS, 각 결과 1개 | CLI 분기와 JSON 응답 확인 |
| `python -B -m unittest discover -s ai/llm-paper-lab/labs -p test_lab.py -v` | 50개 PASS | 양성/음성 입력·오류·수식·집계 검산 |
| 같은 테스트에 `-O` 추가 | 50개 PASS | 최적화 모드에서도 검증 조건 유지 |
| Python 3.10 grammar로 AST parse | 두 Python 파일 PASS | 문법 호환 확인, 3.10 runtime 실행은 아님 |
| 논문 metadata 두 JSON | P01–P20 고유 ID 20개 | 원문 링크·최초 공개 연도·읽기 초점·재현 한계 포함 |
| 전체 문서 링크·코드 fence | Markdown 92개·내부 링크 529개, 누락/미닫힘 0 | 외부 페이지 전체의 미래 가용성 보장은 아님 |

LoRA 병합 오차와 gradient, DPO scalar loss, KV 이론 bytes, retrieval 지표, paired bootstrap 값은 [실습 문서](labs/README.md)의 기대값/실측 구분을 따릅니다. 테스트 실행 시간은 작은 fixture의 도구 실행 시간이며 LLM 추론 benchmark로 해석하지 않습니다.

기존 Sentry sampling oracle와 두 Compose의 `config --quiet` 검사도 통과했습니다. 이는 Compose 문법/구성 확인이지 컨테이너를 띄우거나 제품 기능을 재검증한 것이 아닙니다.

## 검증하지 않은 것

- Python 3.10/3.11 등 다른 버전과 OS 조합 전체. 문법상 지원 목표와 실제 테스트 행렬은 다릅니다.
- 실제 모델 학습·생성·adapter fine-tuning·dense embedding·모델/judge API 호출.
- NF4·FlashAttention CUDA 커널·PagedAttention allocator·speculative decoder 구현과 GPU 성능.
- 공식 HELM/IFEval/RAGAS benchmark 또는 논문 20편의 원래 성능 수치 재현.
- 외부 계정·cloud GPU·유료 API·운영 데이터 연결과 제품 전체 보안 검증.

논문은 원문을 연결하고 연구 방법과 검증 경계를 설명했습니다. 제공 코드의 통과와 원논문 결과 재현은 구분하며, 실제 모델 확장은 학습자가 환경·데이터·비용 계약을 정한 뒤 별도로 수행합니다.
