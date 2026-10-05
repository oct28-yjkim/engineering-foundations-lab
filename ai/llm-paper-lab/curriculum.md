# LLM 논문 실험 커리큘럼

[시작](README.md) · [논문 목록](papers.md) · [CPU 실습](labs/README.md) · [평가](assessment.md)

이 과정은 [ML→DL→LLM 로드맵](../ml-dl-llm-roadmap.md)의 세 번째 단계입니다. [DL 언어모델 연결 강의](../dl-paper-lab/lessons/04-language-model-bridge.md)에서 token shift·gradient·teacher forcing·causal 조건을 확인한 뒤 M01로 진입합니다. ML/DL을 이미 이해한 학습자는 관문만 확인하고 시작합니다. 앞 단계의 실제 tiny network 학습과 이 과정의 CPU 수학 모형은 제공 범위가 다릅니다.

14개 모듈 × 2주 × 주 12시간을 기본 예산으로 잡습니다. 각 모듈의 24시간은 원문/수학 6, 구현/실험 10, 소스/반례 4, 기록/리뷰 4시간으로 배분합니다. GPU나 API가 없는 모듈은 설계와 수기 검산까지 수행하고 실제 모델 검증 상태는 미실행으로 남깁니다. CPU 경로를 선택했다고 실행하지 않은 모델 결과를 제출할 필요는 없습니다.

| 모듈·주차 | 선수 조건 | 논문과 핵심 질문 | 실험·통과 증거 |
| --- | --- | --- | --- |
| M01 · 1–2 | Python, 행렬·확률 | P01/P02, attention의 정보 접근과 다음 token 예측은 어떻게 연결되는가? | `attention`, 미래 token 변화에 prefix 불변·잘못된 mask 반례; encoder-decoder와 decoder-only 구별 |
| M02 · 3–4 | M01, 로그·회귀 | P03, 고정 compute 아래 parameter/data를 어떻게 비교하는가? | 작은 compute 예산표·data/token 통제 실험 계획; 좁은 곡선을 대규모 법칙으로 외삽하지 않음 |
| M03 · 5–6 | M01, 미분 | P04/P05, 저랭크 적응과 양자화는 무엇을 바꾸는가? | `lora`, merged/unmerged 동치·초기 gradient·parameter 수; NF4/QLoRA 미구현 경계 |
| M04 · 7–8 | M01, loss·학습 split | P06, SFT·reward model·정책 최적화의 데이터와 목적은 어떻게 다른가? | 단계별 데이터 계약, preference labeling 반례, 실제 학습과 설계-only 구분 |
| M05 · 9–10 | M03–04, log probability | P07, reference와 preference margin이 손실을 어떻게 결정하는가? | `dpo`, 안정 loss·gradient 방향·reference 영향; 보상/정렬 성능 개선은 별도 검증 |
| M06 · 11–12 | M01, 메모리 계층 | P08/P09, IO 감소와 KV 관리가 해결하는 병목은 같은가? | `kv-cache`, 구조별 bytes 손계산; GPU 확장 시 동일 workload·품질·메모리·지연 비교 |
| M07 · 13–14 | M01/M06, 조건부 확률 | P10, draft를 검증하면서 target 분포를 유지하는 조건은 무엇인가? | 작은 유한 분포의 acceptance/residual 검산; 생성 길이·온도·draft 비용을 포함한 확장 설계 |
| M08 · 15–16 | 집합·ranking·M01 | P11/P12, 검색 성공과 답변 정답은 왜 다른가? | `retrieval`, Recall/MRR/nDCG oracle와 tenant 사전 필터; lexical baseline을 dense RAG로 부르지 않음 |
| M09 · 17–18 | M08, token budget | P13, 관련 정보가 문맥 어느 위치에 있는지가 결과를 바꾸는가? | 동일 사실·길이의 위치 교환 계획; 실제 모델 없이 위치 효과를 측정했다고 하지 않음 |
| M10 · 19–20 | M01/M12 지표 기초 | P14/P15, 생성 전략 개선과 더 많은 계산의 효과를 어떻게 구별하는가? | 동일 budget baseline·다중 sample 집계·오답 상관 분석; 출력 설명을 내부 추론의 충실한 기록으로 보지 않음 |
| M11 · 21–22 | M08/M10, 상태기계 | P16/P17, 도구 호출 루프와 도구 사용 학습은 어떻게 다른가? | mock tool 권한·인자·budget·중복 부작용 시험; 외부 실행은 승인된 sandbox만 |
| M12 · 23–24 | 이전 모듈 1개 이상 | P18/P19/P20, 점수 변화가 사용자 품질 개선을 뜻하는 조건은 무엇인가? | `evaluation`, paired 집계·bootstrap·검증 가능한 조건·judge 오류; 원 benchmark 재현과 구별 |
| M13 · 25–26 | 선택 모듈·M12 | 구현/논문/측정의 경계를 하나의 주장으로 연결할 수 있는가? | paper version·code commit·dataset revision, 최소 반례·regression test와 외삽 한계 |
| M14 · 27–28 | M13 | 개선안 하나를 제3자가 반박하고 재현할 수 있는가? | 이전 코드 재사용, baseline+변경 1개+ablation 1개+실패 조건, 재현 패키지·구술 방어 |

M10에 필요한 지표 기초는 M12 강의의 평가 정의를 먼저 읽는다는 뜻이며, M12 전체 실습의 선행 완료가 아닙니다. 선수 지식이 부족하면 순서를 바꾸고 실제 수행한 모듈 목록을 기록합니다.

## 강의와 작업 방식

M01–02는 [구조·스케일링](lessons/01-transformers-scaling.md), M03–05는 [적응·정렬](lessons/02-adaptation-alignment.md), M06–07은 [추론 최적화](lessons/03-efficient-inference.md)를 사용합니다. M08–09는 [검색·문맥](lessons/04-retrieval-context.md), M10–11은 [추론 전략·에이전트](lessons/05-reasoning-agents.md), M12는 [평가](lessons/06-evaluation.md), M13–14는 [연구·캡스톤](lessons/07-research-capstone.md)으로 이어집니다.

매 실험은 [논문 리뷰](templates/paper-review.md)와 [실험 보고서](templates/experiment-report.md)를 작성합니다. 먼저 논문의 측정 조건과 재현하려는 주장 하나를 정하고, 구현 전 예상 결과와 실패 조건을 고정합니다. 원문 수치·우리 기대값·실제 측정값을 서로 다른 칸에 둡니다.

M14는 한 가설을 다루는 **2주 미니 프로젝트**입니다. 실제 모델 전체 재학습·분산 서빙·RAG·에이전트·5개 제품 통합을 모두 24시간에 요구하지 않습니다. 필요하면 후속 프로젝트를 별도로 계획하며, [Supabase·Sentry 캡스톤](../../capstones/secure-observable-app.md)이나 [데이터 통합 연구](../../databases/shared/capstone.md)에 AI 계약을 추가하는 것은 선택 확장입니다.
