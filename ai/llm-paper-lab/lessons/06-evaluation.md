# M12. HELM·IFEval·Ragas: 평가기를 먼저 의심하는 법

[트랙 안내](../README.md) · [논문 지도](../papers.md) · [실행 가능한 CPU 실험](../labs/README.md) · [평가](../assessment.md)

2주·24시간 모듈입니다. 제공 CPU evaluation 모형, 학습자가 구현하는 checker, 실제 model/judge 실행을 구분합니다. 논문 benchmark 전체 데이터·모델 결과·현재 evaluation package를 이미 실행한 과정이 아닙니다.

<a id="m12"></a>
## 세 논문이 나누는 평가의 층

[P18 HELM](https://arxiv.org/abs/2211.09110)은 scenario와 여러 평가 차원을 드러내고 표준화된 조건에서 모델을 비교하는 접근입니다. 점수 하나의 순위보다 어떤 사용 사례·집단·위험이 빠졌는지 명시하는 태도를 배웁니다. 자신의 작은 업무 fixture를 HELM 전체 benchmark라고 부르지 않습니다.

[P19 IFEval](https://arxiv.org/abs/2311.07911)은 프로그램으로 확인 가능한 지시에 집중합니다. 지시 준수는 중요하지만 규칙을 모두 지킨 답이 사실에 맞거나 유용하거나 안전하다는 뜻은 아닙니다. 직접 만든 checker는 공식 데이터/공식 구현과 동일하지 않으면 “IFEval-inspired”로 표시합니다.

[P20 Ragas](https://arxiv.org/abs/2309.15217)는 RAG의 검색·근거 충실성·생성 품질을 나누는 reference-free 평가를 다룹니다. reference-free는 reference answer가 필요 없는 proxy라는 뜻이지 ground truth가 없어도 사실을 확정한다는 뜻이 아닙니다. 원 논문 버전과 현재 package의 metric 정의·judge prompt·API를 같다고 가정하지 않습니다.

## 1. 평가 계약을 코드보다 먼저 고정

작은 업무 목표를 “자기 tenant의 현재 문서에서 답하고, 근거가 없으면 유보하며, 지정한 JSON 형식을 지킨다”로 둡니다. 평가는 다음 축을 분리합니다.

| 축 | 독립 정답/관측 | 속이기 쉬운 지점 |
| --- | --- | --- |
| 정답성 | 사전 작성 정답 집합 또는 deterministic solver | 정답 생성기를 평가 대상 모델과 공유 |
| 검색 | query별 relevant source ID | retrieved 문서를 그대로 gold로 사용 |
| 충실성 | claim와 근거의 대응을 검토한 annotation | citation 존재만 검사 |
| 지시 준수 | 명시된 schema/format checker | substring·문자 수만으로 의미 판정 |
| 안전·권한 | 허용 resource와 실제 실행 원장 | 최종 답만 가리고 prompt 유출 무시 |
| 운영 | 모든 attempt·timeout·token·latency 기록 | 성공한 요청만 분모에 포함 |

정답이 애매한 항목은 억지로 한 문자열로 만들지 않습니다. annotator 둘의 독립 판단, 불일치 조정, 허용 답 집합·유보 규칙을 기록합니다. 모델 output을 본 뒤 label을 바꾸는 경우 수정 이유와 모든 시스템의 재평가를 남깁니다.

## 2. 실행형 checker와 checker 자체의 test

학습자는 작은 JSON 응답 계약을 구현합니다. 예를 들어 `answer`는 문자열, `source_ids`는 허용 ID의 배열, `abstain`은 boolean이고 다른 필드는 금지합니다. parse 성공뿐 아니라 타입·중복 key 정책·추가 텍스트·정해진 필드의 의미를 검사합니다. 정답성/근거성은 별도 checker로 둡니다.

필수 음성 fixture는 빈 출력, 잘린 JSON, code fence로 감싼 출력, 정답 substring만 우연히 포함한 문장, 숫자 대신 문자열, Unicode 공백, 거짓 citation, 형식만 맞춘 무의미 답변입니다. 이 형식 계약은 강의용 설계이며 IFEval 공식 instruction 종류나 strict/loose 집계와 동일하다고 주장하지 않습니다. 공식 benchmark를 재현할 때는 공식 evaluator commit·data revision·정규화 정책을 별도로 고정합니다.

prompt에 여러 instruction이 있으면 **instruction-level** 성공 비율과 **prompt-level all-pass** 비율을 구별합니다. 쉬운 지시가 많은 prompt가 전체 평균을 지배하는지 함께 확인합니다. timeout/parser 실패를 제외해 점수를 높이지 말고 분모·실패 처리 규칙을 먼저 고정합니다.

## 3. CPU 통계 모형에서 실제 실험으로

저장소 루트에서 다음 명령을 실행할 수 있습니다. 세부 출력과 fixture 범위는 [실습 안내](../labs/README.md)가 기준입니다.

```powershell
python ai/llm-paper-lab/labs/lab.py --lab evaluation
```

제공 코드는 synthetic paired 결과의 통계 계약을 살펴보는 CPU toy입니다. LLM을 호출하거나 HELM·IFEval·Ragas 전체를 실행하지 않습니다. toy 성공은 model superiority가 아니라 해당 작은 계산/집계의 검증입니다.

학습자가 실제 실험으로 확장할 때는 동일 query ID에 baseline과 variant 결과를 붙이고, 비교 전에 주 지표·sample 수·run 중단 조건·실용적 최소 효과를 고정합니다. `d_i = score_variant_i - score_baseline_i`의 평균과 query 단위 paired interval을 보고합니다. 같은 질문을 열 번 실행했다고 질문 수가 열 배가 된 것은 아닙니다. 질문과 random run이 중첩되면 그 구조를 보존해 resampling합니다.

dev로 threshold/prompt를 선택한 뒤 untouched test를 사용합니다. 20개 설정 중 최고값만 선택한 비교에는 selection 효과가 있습니다. 작은 표본에서 interval이 넓으면 불확실함을 결론으로 남기며, 유의하지 않음을 동등성 증명으로 바꾸지 않습니다. 실제 accuracy가 비슷한지 판단할 margin은 결과를 보기 전에 정해야 합니다.

## 4. LLM judge를 추가할 때의 교정 실험

judge는 선택 확장입니다. 계정·데이터 전송 권한·비용·모델 snapshot이 확인된 환경에서만 학습자가 실행합니다. 기본 repo는 judge API를 자동 호출하지 않습니다. 답변과 evidence를 judge에 전달할 경우 합성 데이터만 사용하고 secret/tenant 경계를 검사합니다.

작은 human-labeled calibration set을 먼저 고정합니다. 같은 답의 순서를 뒤집고, 길이만 늘리고, 무관한 권위 문구를 넣고, 근거에 없는 자신감 있는 주장을 추가합니다. judge prompt·모델·출력 parser·실패 처리·repeat를 기록하고 사람 판정 대비 혼동행렬과 실패 유형을 봅니다. calibration set에 맞춰 judge를 수정한 뒤에는 별도 holdout을 둡니다.

RAG 평가는 적어도 세 경우를 분리합니다: 올바른 답이지만 제공 근거로는 지지되지 않음, 근거를 충실히 요약했지만 근거 자체가 오래되었거나 틀림, 관련 문서가 검색됐지만 답변이 다른 주장을 생성함. 하나의 LLM 점수로 셋을 합치면 어느 구성요소를 고칠지 알 수 없습니다.

reference-free proxy, 사람이 만든 label, 외부 사실 원장은 증거 수준이 다릅니다. proxy와 사람 판정의 상관이 높아도 모든 개별 답의 정확성 보장은 아니며, 이 실험 분포 밖의 안전성을 증명하지 않습니다.

## 5. Ablation·실패 주입·2주 계획

1주차 12시간: 원문 비교 3시간, 평가 계약/label 4시간, checker/CPU 통계 검산 5시간. 2주차 12시간: checker mutation 3시간, bounded model/judge 실험 또는 미실행 설계 5시간, 분석·동료 리뷰 4시간.

필수 mutation은 “빈 출력도 정답으로 인정”, “실패 요청을 분모에서 제외”, “존재하지 않는 source ID를 허용” 중 두 개 이상입니다. 테스트가 이 잘못된 evaluator에서 실패하고 원래 evaluator에서 통과해야 합니다. 모델을 개선하지 않고도 평가기 bug로 점수가 오르는 사례를 보고서에 남깁니다.

통과 산출물은 scenario/metric coverage, 빠진 집단과 위험, independent gold, checker 단위 테스트, 전체 시도 원장, query별 paired 차이, 불확실성, 비용/지연, 통계/보안 한계입니다. 실제 모델 또는 judge가 없다면 미실행을 표시합니다. 점수가 높은 시스템이 아니라 **잘못된 점수 상승을 잡는 실험**을 만든 것이 이 모듈의 성과입니다.

PostgreSQL/Supabase는 평가 annotation 권한·version 관리, ClickHouse는 query/attempt별 집계, Sentry는 secret 없는 실패 분류에 선택적으로 연결할 수 있습니다. 제품 도구를 설치하는 일과 evaluator correctness는 별개의 게이트입니다.
