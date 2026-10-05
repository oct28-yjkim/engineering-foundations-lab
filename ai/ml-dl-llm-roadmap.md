# ML에서 DL과 LLM으로 이어지는 논문 학습 경로

[AI 전체](README.md) · [선수 기초](foundations.md) · [수학 보충](math-foundations/README.md) · [ML 시스템 설계](ml-systems/README.md) · [실행 환경](paper-labs-environment.md) · [단계별 평가](paper-labs-assessment.md)

목표는 논문 이름을 외우는 것이 아니라 **데이터로부터 무엇을 학습하는지 설명하고, 계산을 구현하며, 성능 개선의 원인을 검증하는 것**입니다. ML은 DL을 배우고 버리는 옛 기술이 아닙니다. 데이터 분할·일반화·최적화·평가의 기준을 만들고, DL은 학습 가능한 표현을 추가하며, LLM은 이를 언어의 조건부 확률과 대규모 학습·추론으로 확장합니다. 업무에 따라 선형 모델이나 트리 모델을 선택하는 것도 올바른 결론입니다.

## 단계와 진입 조건

| 단계 | 중심 질문 | 과정·자료 | 다음 단계로 넘길 증거 |
| --- | --- | --- | --- |
| 선택 기초 | 벡터·미분·확률·코드를 연결할 수 있는가? | [4주 빠른 순환](foundations.md), [12문항 진단·보충](math-foundations/diagnostic.md) | shape 계산, 손실/gradient 손계산, train/test 구분; 부족한 영역은 추가 학습 |
| ML | 어떤 가정 아래 데이터 밖에서도 예측하는가? | [16주·8모듈](ml-paper-lab/curriculum.md), [논문](ml-paper-lab/papers.md), CPU LAB 4개 | 누출 없는 baseline, loss와 업무 지표의 차이, regularization·앙상블·표현의 한계 |
| DL | 특징 자체를 학습할 때 무엇이 달라지는가? | [20주·10모듈](dl-paper-lab/curriculum.md), [논문](dl-paper-lab/papers.md), CPU LAB 4개 | 역전파 검산, 실제 parameter 업데이트, 학습 실패 진단, 시퀀스와 causal 조건 |
| LLM | 다음 token 학습을 어떤 모델·추론·평가 시스템으로 확장하는가? | [기존 28주·14모듈](llm-paper-lab/curriculum.md), [논문 20편](llm-paper-lab/papers.md), CPU 모형 6개 | attention·적응·정렬·추론·검색·평가의 가정과 실제 모델 실험 구분 |

주 12시간 기준 **ML 192 + DL 240 + LLM 336 = 768시간, 순차 64주**를 명목 예산으로 둡니다. 선수 기초 4주·48시간까지 필요하면 68주·816시간입니다. 기존 데이터베이스 공통 기초 8주, MCP 28주, 제품별 과정은 이 합계에 포함하지 않습니다. 기간은 숙련도 보증이 아니며 진단을 통과한 내용은 줄이고 실패한 관문은 반복합니다.

수학을 처음 배우면 4주보다 더 필요할 수 있습니다. [수학 자료 지도](math-foundations/resources.md)에서 약한 영역의 첫 자료와 확장 자료를 고르고 재검산을 통과할 때 복귀합니다. **[ML 시스템 설계 16주](ml-systems/curriculum.md)는 별도 선택 병행 경로**입니다. 모델/평가 기초를 익힌 ML 단계부터 시작할 수 있고 LLM 종료까지 기다리지 않습니다. 64주 합계에 자동 가산하지 않습니다.

## 같은 질문을 단계마다 확장하기

| 공통 축 | ML에서 배우는 것 | DL에서 추가되는 것 | LLM으로 가져갈 것 |
| --- | --- | --- | --- |
| 데이터 | 행/사람/시간 단위 split, 전처리 fit 범위 | augmentation·batch·학습/평가 모드 | 문서 중복·tokenizer·packing·prompt/answer 누출 |
| 표현 | 수작업 feature, kernel, PCA | hidden representation, convolution, embedding | token embedding·attention·retrieval representation |
| 목적함수 | MSE·log loss·margin과 metric의 차이 | 계산 그래프·chain rule·optimizer state | token NLL·mask·SFT·preference objective |
| 일반화 | regularization·모델 선택·표본 불확실성 | capacity·dropout·normalization·사전학습 | domain shift·오염·fine-tuning·benchmark 전이 |
| 효율 | feature/표본 수와 계산·메모리 | activation·backward·batch·device | context·KV cache·precision·serving budget |
| 실패 | 누출·불균형·과적합 | gradient 오류·발산·모드 혼동 | 미래 token 노출·평가 오염·검색/생성 실패 혼동 |

## 처음 일주일의 진행

1. [수학 진단 12문항](math-foundations/diagnostic.md)을 풀고 모르는 영역을 보충합니다. [기초 요약](foundations.md)의 네 예제는 빠른 복습용입니다.
2. ML `ridge`를 실행하기 전에 train 평균과 shrinkage 방향을 적습니다.
3. 실행 결과에서 손계산과 맞는 항목 하나, 일반화 결론을 내릴 수 없는 항목 하나를 찾습니다.
4. [ML 첫 강의](ml-paper-lab/lessons/01-generalization.md)와 ML02/ML10 논문을 읽고 baseline·분할·반증 조건을 기록합니다.
5. 코드를 한 번 바꾸어 누출 또는 잘못된 gradient 검출 테스트가 실패하는지 확인한 뒤 되돌립니다. 이 변경은 자신의 학습 브랜치에서 하며 정답 oracle을 결과에 맞추지 않습니다.

모든 논문을 읽은 뒤 코딩을 시작할 필요는 없습니다. **작은 동작을 예측 → 실행 → 식으로 설명 → 원문 조건 확인 → 실패 조건 추가**를 반복합니다.

## ML에서 DL로 넘어가는 관문

- 학습·검증·최종 평가 데이터의 용도를 설명하고 전처리/특징 선택의 fit 범위를 도식 또는 코드로 추적합니다.
- linear/logistic 모델의 목적함수와 gradient를 손계산·유한차분으로 확인합니다.
- 단순 baseline보다 복잡한 모델이 나빠지는 사례를 남깁니다. tree bagging을 Random Forest 전체 재현이라고 부르지 않습니다.
- XOR에 단일 선형 결정 경계가 부족한 이유를 설명하고 hidden layer의 비선형성이 해결할 수 있는 표현 문제로 연결합니다.

## DL에서 LLM으로 넘어가는 관문

- 공유 parameter의 gradient가 사용 횟수만큼 누적되는 이유와 optimizer step 전 gradient 초기화를 설명합니다.
- sequence의 입력/정답을 한 칸 이동시키고, padding/미래 token이 손실·문맥에 들어가는 위치를 추적합니다.
- teacher-forced NLL와 실제 autoregressive 생성 결과를 별도로 평가합니다. 합성 반복 문자열의 낮은 loss는 자연어 이해가 아닙니다.
- [DL 언어모델 연결 강의](dl-paper-lab/lessons/04-language-model-bridge.md)를 마친 뒤 기존 [LLM M01](llm-paper-lab/lessons/01-transformers-scaling.md)로 이동합니다. Transformer 논문은 여기서 다시 만나지만 새 논문 한 편으로 중복 집계하지 않습니다.

## 연구와 업무로 확장하기

### 모델 연구와 시스템 설계를 함께 배우기

ML의 모델/평가 기초를 배운 뒤 [시스템 설계 과정](ml-systems/README.md)을 병행합니다. 공개 Stanford CS329S Winter 2022의 문제 정의·데이터·배포·관측 주제를 참고한 **독자적인 실습**이며 공식 강의 복제나 이수 과정이 아닙니다. [공식 자료와 대응표](ml-systems/references.md)에 참고 범위와 저장소의 추가 설계를 구분했습니다.

| 연구 단계에서 갖춘 것 | 시스템 과제로 확장 | 정상/실패/회복 증거 |
| --- | --- | --- |
| ML split·metric·baseline | 데이터/label 시점, feature 계약, 비ML 대안 | 미래/늦게 도착한 feature 누출과 올바른 snapshot 비교 |
| DL representation·학습 상태 | 전처리/모델 bundle 버전·batch/online serving | 요청 계약 오류·수정 후 동일 예측, 작은 HTTP 서비스 관측 |
| LLM 평가·검색·서빙 제약 | 품질/지연/비용 예산·rollout·feedback | slice regression·label 지연·rollback 판단과 복구 검산 |

시스템 기본 LAB의 모델은 학습된 대형 모델이 아니라 고정 합성 logistic artefact입니다. 실제 loopback HTTP 요청과 contract/rollback을 확인하고, point-in-time/label/drift는 별도 fixture로 검산합니다. cloud·Kubernetes·feature store·분산 serving·실제 A/B test를 자동 제공하지 않습니다.

기본 코드는 합성 데이터의 계산·학습 경로를 재현합니다. 실제 데이터 확장은 라이선스·민감 정보·split·평가 예산을 먼저 정하고, 기준선 하나와 변경 하나만 선택합니다. GPU/API 없이도 ML과 작은 DL 학습이 가능합니다. GPU 확장은 같은 코드가 빠르게 도는지뿐 아니라 수치·batch·메모리·동일 품질 조건이 유지되는지를 검증합니다.

RAG는 언어모델 기초 이후 [Qdrant](../search/qdrant/README.md)·[OpenSearch](../search/opensearch/README.md)에서 검색 품질·필터·운영을, 도구 사용은 [MCP](mcp/README.md)에서 프로토콜·권한·실행을 학습합니다. 이 제품들을 설치하는 것은 ML/DL 기본 LAB의 선수 조건이 아닙니다.

논문 읽기 양식은 [기존 paper review](llm-paper-lab/templates/paper-review.md)를 재사용합니다. 실험 보고서는 [공통 평가 규칙](paper-labs-assessment.md)에 따라 범위를 `ML-CPU` 또는 `DL-CPU`로 명시합니다. 구현·실행·원논문 재현은 서로 다른 완료 상태입니다.
