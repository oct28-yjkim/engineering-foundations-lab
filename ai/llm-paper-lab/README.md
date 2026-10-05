# LLM 엔지니어를 위한 논문 실험실

논문을 요약하는 데서 멈추지 않고 **주장 → 식과 구현 → 통제 실험 → 반례 → 실무 의사결정**으로 연결합니다. Transformer, 효율적 학습·정렬, 추론, RAG, 에이전트, 평가를 다루는 핵심 논문 20편을 선정했습니다. 최신 논문 순위나 모든 분야를 망라한 목록이 아니라, 후속 연구를 이해하기 위한 기초 연구 지도입니다.

처음 시작하면 [ML → DL → LLM 경로](../ml-dl-llm-roadmap.md)를 사용합니다. [ML](../ml-paper-lab/README.md)의 일반화·평가와 [DL](../dl-paper-lab/README.md)의 역전파·시퀀스·causal 문맥을 먼저 학습하고 이 과정의 M01로 이어집니다. 이미 해당 진입 관문을 통과했다면 앞 과정을 다시 모두 이수할 필요는 없습니다.

기본 경로는 **CPU·오프라인**, GPU·외부 API는 선택 확장입니다. 주 12시간, 모듈당 2주인 **28주·14모듈·336시간**을 명목 예산으로 삼되 모르는 수학·Python은 별도로 보충합니다. 기간 이수나 작은 모형의 테스트 통과를 전문가 역량·원논문 성능 재현의 보증으로 취급하지 않습니다.

## 바로 실행

저장소 루트에서 Python 3.10 이상으로 실행합니다. Python 자체를 제외한 추가 패키지가 필요하지 않습니다.

```text
python ai/llm-paper-lab/labs/lab.py --lab all
python -B -m unittest discover -s ai/llm-paper-lab/labs -p test_lab.py -v
```

`python`이 설치되지 않았거나 Windows Store 별칭이라 실행되지 않으면 보유한 실제 Python 실행 파일의 경로를 사용합니다. 자세한 내용은 [환경과 비용 경계](environment.md), 개별 명령과 검증 범위는 [실습 안내](labs/README.md)를 봅니다. 이 명령은 API 키·Docker·GPU 없이 합성 데이터와 수치 모형을 검사합니다.

## 읽는 순서

| 자료 | 역할 |
| --- | --- |
| [핵심 논문 20편](papers.md) | 원문 링크, 선정 이유, 모듈·실험 대응 |
| [28주 커리큘럼](curriculum.md) | 선수 조건, 주차별 산출물과 통과 기준 |
| [구조와 스케일링](lessons/01-transformers-scaling.md) | M01–02, attention·언어모델·compute/data |
| [적응과 정렬](lessons/02-adaptation-alignment.md) | M03–05, LoRA·QLoRA·SFT/RLHF·DPO |
| [효율적 추론](lessons/03-efficient-inference.md) | M06–07, FlashAttention·PagedAttention·speculative decoding |
| [검색과 문맥](lessons/04-retrieval-context.md) | M08–09, DPR·RAG·문맥 위치와 검색 실패 |
| [추론 전략과 에이전트](lessons/05-reasoning-agents.md) | M10–11, CoT·self-consistency·ReAct·Toolformer |
| [평가 설계](lessons/06-evaluation.md) | M12, HELM·IFEval·RAGAS·평가 편향 |
| [최소 재현과 캡스톤](lessons/07-research-capstone.md) | M13–14, 한 주장에 대한 반증과 설계 방어 |
| [실험 계약](reproducibility.md) · [소스 읽기](source-reading.md) | split·baseline·seed·revision·지표·통계·한계 |
| [평가 기준](assessment.md) | 영역별 점수와 필수 게이트 |

## 제공 범위

| 단계 | 이 저장소의 제공물 | 완료로 부를 수 있는 범위 |
| --- | --- | --- |
| CPU-MODEL | 실행 코드 6개 선택지, 자체 합성 fixture, 단위 테스트 | 식·불변식·검산 로직의 작은 모형 검증 |
| SMALL-MODEL | 강의별 작은 모델 학습·추론 실험 설계 | 학습자가 실제 구현·실행한 축소 조건의 결과 |
| GPU-EXTENSION | 고정 모델/데이터/커널의 비교·ablation 지침 | 실제 GPU에서 측정한 해당 설정의 결과 |
| API-EXTENSION | 요청 예산·평가·권한·기록 지침 | 사용자가 선택한 API·시점·데이터의 black-box 결과 |
| PAPER-REPRODUCTION | 원논문과 차이를 기록하는 재현 양식 | 원래 조건과의 차이 및 검증한 주장까지 명시한 결과 |

제공된 `lab.py`는 실제 Transformer 학습기, NF4 구현, CUDA 커널, PagedAttention allocator, dense retriever, 생성 모델, 에이전트, HELM/IFEval/RAGAS 공식 실행기가 아닙니다. 각 모형에서 통과한 내용을 다른 단계의 성능이나 모델 안전성으로 확대하지 않습니다. 모델·데이터·SDK 설치 및 다운로드, 유료 호출, 클라우드 GPU 생성은 자동 수행하지 않습니다.

## 선택 경로

- **처음 시작:** M01 → M03 → M05 → M08 → M12의 CPU 모형과 논문 읽기로 식·권한·평가 기초를 잡습니다. 전체 과정을 완료한 것은 아닙니다.
- **모델/추론 엔지니어:** M01–07을 깊게 구현하고 M12–14에서 품질과 자원 비용을 함께 방어합니다.
- **RAG/에이전트 엔지니어:** M01·M08–12를 중심으로 진행하고 M03–07의 학습·서빙 제약을 보완합니다.

SQL/OS/분산 시스템은 [공통 기초](../../databases/shared/foundations.md)를 참고합니다. 행렬 곱·미분·로그 확률·최적화·Python 테스트 작성은 별도 선수 지식입니다. 기존 5개 제품 트랙을 모두 이수할 필요는 없고 이 28주를 기존 156주 경로에 자동으로 더하지 않습니다.
