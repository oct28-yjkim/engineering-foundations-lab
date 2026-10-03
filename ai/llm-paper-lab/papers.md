# LLM 엔지니어 핵심 논문 20편

[커리큘럼](curriculum.md) · [실습](labs/README.md) · [논문 리뷰 양식](templates/paper-review.md)

선정 기준은 최신 순위가 아니라 **실무 설계의 근거가 되는 원리, 작은 반례를 만들 수 있는 주장, 서로 연결되는 시스템 경계**입니다. 연도는 최초 arXiv 공개 연도이며 학회 게재·개정 연도와 다를 수 있습니다. 원문 확인일은 2026-10-04입니다. 아래 arXiv 링크는 최신 개정본으로 이동할 수 있으므로 실험 시작 때 읽은 `vN`과 날짜를 별도로 고정합니다.

각 행의 마지막 열은 이 교육 과정의 실험 설계입니다. 저자가 그 CPU 실험을 제공했다거나, 해당 실험 통과로 원논문 benchmark를 재현했다는 뜻이 아닙니다.

## 구조와 학습

| ID·연도 | 원논문 | 읽을 이유 | 연결 실험 |
| --- | --- | --- | --- |
| P01 · 2017 | [Attention Is All You Need](https://arxiv.org/abs/1706.03762) | scaled dot-product attention, mask, encoder-decoder 구성 | M01 `attention`: 정보 접근 불변식; 번역 성능 재현 아님 |
| P02 · 2020 | [Language Models are Few-Shot Learners](https://arxiv.org/abs/2005.14165) | 모델 학습과 in-context 예시 사용의 차이 | M01 prompt/평가 조건 설계; GPT-3 학습 미제공 |
| P03 · 2022 | [Training Compute-Optimal Large Language Models](https://arxiv.org/abs/2203.15556) | 고정 compute에서 모델 크기와 학습 token 배분 | M02 작은 예산표·축소 학습 계획; 원 scaling law 검증 아님 |
| P04 · 2021 | [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685) | frozen weight와 저랭크 update의 분리 | M03 `lora`: 병합 동치·초기 gradient |
| P05 · 2023 | [QLoRA: Efficient Finetuning of Quantized LLMs](https://arxiv.org/abs/2305.14314) | base weight 양자화와 adapter 학습의 구별 | M03 선택 GPU 실험; NF4·paged optimizer는 CPU 코드 미구현 |
| P06 · 2022 | [Training language models to follow instructions with human feedback](https://arxiv.org/abs/2203.02155) | SFT·선호 데이터·reward model·정책 최적화의 계약 | M04 단계별 데이터/목적·실패 분석; 실제 RLHF는 선택 구현 |
| P07 · 2023 | [Direct Preference Optimization: Your Language Model is Secretly a Reward Model](https://arxiv.org/abs/2305.18290) | reference 대비 preference log-ratio와 최적화 | M05 `dpo`: 손실·gradient 검산; 선호 품질은 별도 평가 |

## 추론과 검색

| ID·연도 | 원논문 | 읽을 이유 | 연결 실험 |
| --- | --- | --- | --- |
| P08 · 2022 | [FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness](https://arxiv.org/abs/2205.14135) | attention 계산과 메모리 IO 비용의 분리 | M06 선택 GPU output/gradient·성능 비교; CUDA 커널 미제공 |
| P09 · 2023 | [Efficient Memory Management for Large Language Model Serving with PagedAttention](https://arxiv.org/abs/2309.06180) | KV cache 배치와 서빙 workload의 상호작용 | M06 `kv-cache`: 이상적 bytes; paging/scheduling 구현 아님 |
| P10 · 2022 | [Fast Inference from Transformers via Speculative Decoding](https://arxiv.org/abs/2211.17192) | draft 검증·수락/보정과 target 분포 보존 조건 | M07 유한 분포 손계산·선택 구현; ICML 게재는 2023년 |
| P11 · 2020 | [Dense Passage Retrieval for Open-Domain Question Answering](https://arxiv.org/abs/2004.04906) | dual encoder, positive/negative와 검색 평가 | M08 `retrieval`: lexical 기준선만 제공, dense 학습 미제공 |
| P12 · 2020 | [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) | parametric/non-parametric memory와 생성의 결합 | M08 검색·생성 오류 분리; 원 RAG 모델 학습은 확장 |
| P13 · 2023 | [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) | context 길이와 실제 정보 사용 능력의 차이 | M09 근거 위치 paired 실험; 현재 모델에서 재측정 |

## 추론 전략과 평가

| ID·연도 | 원논문 | 읽을 이유 | 연결 실험 |
| --- | --- | --- | --- |
| P14 · 2022 | [Chain-of-Thought Prompting Elicits Reasoning in Large Language Models](https://arxiv.org/abs/2201.11903) | 예시/출력 전략과 task 성능의 관계 | M10 정답·비용 비교; 출력 설명을 내부 추론의 증명으로 보지 않음 |
| P15 · 2022 | [Self-Consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171) | 여러 sample의 답 집계와 계산 예산 | M10 동일 budget·오답 상관·정규화 비교 |
| P16 · 2022 | [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) | 관측과 tool action을 교차하는 상호작용 | M11 mock tool 상태·권한·실패 시험 |
| P17 · 2023 | [Toolformer: Language Models Can Teach Themselves to Use Tools](https://arxiv.org/abs/2302.04761) | 도구 호출 데이터 생성·필터·학습의 구별 | M11 학습 데이터 설계; API 호출 루프만으로 재현 아님 |
| P18 · 2022 | [Holistic Evaluation of Language Models](https://arxiv.org/abs/2211.09110) | task·metric·조건을 함께 보는 다면 평가 | M12 `evaluation`: 작은 paired 모형, 공식 HELM 실행 아님 |
| P19 · 2023 | [Instruction-Following Evaluation for Large Language Models](https://arxiv.org/abs/2311.07911) | 검증 가능한 지시와 평가기의 계약 | M12 deterministic 검사·edge case; 공식 IFEval 점수 아님 |
| P20 · 2023 | [Ragas: Automated Evaluation of Retrieval Augmented Generation](https://arxiv.org/abs/2309.15217) | RAG 평가 차원과 자동 평가의 한계 | M12 judge/인간/실행 oracle 대조 설계; 라이브러리 기본값과 논문 정의 구별 |

## 처음 읽을 순서

첫 순환은 P01 → P04 → P07 → P11/P12 → P19입니다. attention, update, objective, retrieval, 검증 가능한 평가로 연결하면 “어떤 값을 바꾸고 무엇으로 성공을 판정하는가”가 드러납니다. 나머지는 [모듈 순서](curriculum.md)에 따라 읽습니다. 첫 순환도 GPU 없이 작은 모형과 설계까지 시작할 수 있습니다.

두 번째 순환은 병목에 맞춥니다. 학습 비용이면 P03/P05, serving이면 P08–10, context/agent 실패면 P13–17, 평가 신뢰성이면 P18/P20으로 돌아갑니다. 이는 권장 학습 순서이며 논문의 우열이나 보편적인 제품 선택 순위가 아닙니다.

## 서지 데이터와 확장

같은 20편의 기계 판독용 metadata는 [기초/학습/추론 JSON](references/foundations.json)과 [검색/에이전트/평가 JSON](references/applications.json)에 있습니다. `year`는 최초 공개 연도, `reproduction_limit`는 이 저장소의 구현 한계입니다. 논문 전문·dataset·가중치는 복제하지 않고 원문을 연결합니다.

RoPE, GQA/MQA, MoE, 양자화 세부 알고리즘, 데이터 중복 제거, multimodal, 분산 학습, test-time compute와 최신 reasoning 학습은 다음 연구 후보입니다. 이 20편만으로 해당 영역을 다뤘다고 하지 않습니다. 새 논문을 추가할 때도 원문·비교군·실험·반례·자원 예산·재현 범위를 함께 추가합니다.
