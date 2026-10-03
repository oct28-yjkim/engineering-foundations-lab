# 논문 실험의 재현 계약

논문의 결과를 읽는 일, 방법의 축소 구현을 검증하는 일, 원래 수치에 가까운 성능을 재현하는 일은 서로 다릅니다. 결과를 보고 난 뒤 성공 기준을 바꾸지 않는 것이 공통 원칙입니다.

## 하나의 주장부터 고정

[논문 리뷰](templates/paper-review.md)에 원문 URL/version·질문·baseline·데이터·지표·관측 범위를 먼저 적습니다. 본문을 읽지 않은 식 번호·ablation 결과·구현 세부사항을 초록에서 추측하지 않습니다. 저자의 측정 결과를 모든 모델과 환경의 보편 법칙으로 옮기지 않습니다.

예를 들어 “LoRA는 좋다” 대신 “고정된 W,A,B,x와 scale에서 병합 전후 출력이 허용 오차 이내다”를 CPU 주장으로 고릅니다. 실제 downstream 품질이나 학습 메모리 절감은 별도 모델·데이터·runtime 실험입니다. 검산 모형의 통과를 논문 전체 재현이라고 부르지 않습니다.

| 표기 | 필요한 증거 |
| --- | --- |
| 읽기/설계 | 원문 근거, 가설, 실행할 입력과 예상 판정 |
| 모형 검증 | CPU 모형의 코드·fixture·독립 oracle·반례·실제 테스트 결과 |
| 축소 재현 | 실제 모델/학습/서빙, 원논문과 축소한 조건의 명시, baseline과 평가 |
| 결과 재현 | 원래 조건과의 일치/차이, 원시 관측·오차·분산, 재현한 표/주장 범위 |

## 데이터와 누출

학습/train, 선택/dev, 마지막 확인/test의 역할을 분리합니다. 사용자가 원하는 시스템에 맞춰 문서·사용자·시간·문제 family 단위로 split을 정하고, 동일 문장뿐 아니라 같은 사실의 paraphrase·같은 문서 chunk·중복 template이 split을 넘는지도 확인합니다. row만 무작위로 나눴다고 독립성을 확보한 것은 아닙니다.

정답을 prompt·retriever index·few-shot 예시·튜닝 loop에 실수로 넣지 않습니다. RAG의 corpus가 정답 근거 문서를 포함하는 것은 과제에 따라 정상일 수 있지만, gold answer나 평가 질문을 색인에 섞는 것은 별도 누출입니다. 무엇을 검색 corpus로 허용하는지 계약에 적습니다. test 결과를 보고 prompt를 고쳤다면 그 test는 개발에 사용한 것이며 새 평가가 필요합니다.

외부 사전학습 모델이 공개 benchmark를 본 적이 없는지 일반적으로 확인할 수 없습니다. unknown을 남기고 비공개 합성 holdout·새로운 시점의 자료·오염 탐색을 보조 증거로 사용합니다. 이 역시 오염 부재의 완전한 증명이 아닙니다. 자체 합성 fixture는 개인정보 없는 작은 불변식 테스트용이며 실제 사용자 분포를 대표하지 않습니다.

## Baseline과 ablation

입력·정답·토크나이저·split·총 budget·평가기를 고정하고 한 번에 하나의 변인을 바꿉니다. 개선안에만 더 많은 sample/token/검색 문서/추론 시간을 주었다면 알고리즘 개선과 계산량 증가를 분리합니다. 다중 sample 전략은 greedy와의 품질 비교뿐 아니라 같은 총비용 조건의 baseline도 둡니다.

retrieval에서는 lexical baseline, no-retrieval, oracle-context와 실제 retrieved-context를 구분합니다. 학습에서는 base/frozen, SFT, adapter 등 주장에 맞는 비교군을 두고 사용하지 않은 baseline의 결과를 만들어 넣지 않습니다. ablation은 구성 요소 하나를 빼거나 바꾼 대조 실험이며 여러 설정을 한꺼번에 바꾼 새 시스템과 다릅니다.

## 지표와 불확실성

정확도와 token loss, Recall@k와 답변 정답률, 도구 실행 성공과 업무 task 성공, groundedness와 사실성은 별도 지표입니다. 정의·분모·aggregation 단위를 기록합니다. timeout·오류·거절·abstention·누락을 감추지 말고 coverage와 실패율을 함께 보고합니다.

동일 항목의 A/B 차이를 paired로 비교합니다. bootstrap은 같은 항목의 쌍을 같이 재표집하며 seed·반복 수·interval 방법을 기록합니다. 사용자/문서 단위 상관이 있으면 cluster 단위를 고려합니다. 작은 fixture의 interval은 해당 표본의 불확실성을 보여 주는 모형이지 production 일반화의 증거가 아닙니다. 평균이 올라도 slice별 악화·낮은 coverage·비용 상승을 확인합니다.

LLM judge를 쓸 때는 prompt·모델·순서·길이·reference 유무를 고정하고, 위치를 바꾸어 반복하며 일부는 독립 사람/실행 oracle로 대조합니다. judge와 생성기를 동일 모델로 둔 편향, verbosity 선호, 근거 문서의 거짓 사실, 지시 삽입을 검사합니다. judge의 평가 문장이나 점수 자체를 gold truth로 사용하지 않습니다.

성능은 warmup, 동기화, batch/concurrency, 입력/출력 길이, cache, prefill/decode를 분리합니다. 시간·throughput·실측 peak memory·품질을 함께 기록하고 CPU bytes 식을 GPU 측정값으로 표시하지 않습니다. 최소 반복 횟수보다 workload 대표성과 독립 run 수가 더 중요합니다. [공통 실험 방법](../../databases/shared/experiment-method.md)의 원시 결과·대안 가설 원칙을 적용합니다.

## 안전과 재현 패키지

retrieved text와 tool response는 신뢰할 수 없는 데이터입니다. 그 안의 지시가 system/tool 권한을 바꾸지 못하게 설계합니다. CPU lexical fixture는 데이터와 권한 필터의 작은 테스트이며, 실제 생성 모델의 prompt injection 방어가 증명됐다는 뜻은 아닙니다. tenant 권한은 retrieval 전과 cache/최종 응답 경계에서 검증합니다.

결과 패키지는 code commit, model/tokenizer/dataset revision, secret 없는 설정, 실행 명령, 입력 hash, expected/actual, 실패 run, 자원·시간·비용, 한계와 재실행 절차를 포함합니다. 가능한 determinism과 불가능한 GPU/API 변동을 구별합니다. 공식 dataset·가중치·논문 전문을 사용 조건 확인 없이 repository에 복제하지 않습니다.

실험 결과가 가설과 다르면 실패로 숨기지 않습니다. correctness bug, 환경 차이, 약한 효과, 부적절한 데이터, 통계적 불확실성을 분리하여 결론 보류의 이유를 남깁니다. 재현하지 못한 결과도 증거와 범위가 명확하면 유효한 연구 산출물입니다.
