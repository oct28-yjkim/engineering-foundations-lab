# ML DL 논문 실험의 평가와 완료 기준

[학습 경로](ml-dl-llm-roadmap.md) · [실행 환경](paper-labs-environment.md) · [논문 리뷰 양식](llm-paper-lab/templates/paper-review.md) · [실험 보고서 양식](llm-paper-lab/templates/experiment-report.md)

기간·논문 수·테스트 PASS가 아니라 **주장 하나를 계산과 증거로 방어하는 능력**을 평가합니다. 기존 양식의 실행 범위에는 새 기본 실습을 `ML-CPU` 또는 `DL-CPU`로 추가해 적습니다. `DL-CPU`는 실제 tiny network 학습이지만 기존 `CPU-MODEL`인 LLM 수학 모형과도, 원논문 성능 재현과도 다릅니다.

## 매 실험의 제출물

1. 논문 ID·정확한 version, 읽은 식/절, 논문의 주장과 이번 실험의 좁은 가설.
2. 합성 규칙 또는 허가된 데이터 출처, 표본/그룹/문서별 split과 전처리 fit 경계.
3. 코드 revision·diff·명령·Python/OS·seed·실행 시간, 학습 단계/중단 상한.
4. 손계산/독립 reference/유한차분 중 적합한 정답, baseline와 변경 하나, 실패해야 할 입력 하나.
5. 초기/최종 loss, parameter 변화, train/validation/test 구분, 업무 metric·표본 수·한계.
6. 실제 관찰·가설·원논문 결과를 다른 칸에 기록한 결론 및 반증 조건.

XOR의 네 입력을 모두 학습하고 같은 네 입력을 평가했다면 **훈련 집합 적합 성공**입니다. 새로운 합성 좌표나 다른 반복 sequence를 평가해도 원래 분포/생성 규칙과의 관계를 설명해야 합니다. heldout이라는 파일명 하나로 독립성이 생기지 않습니다.

## 점수와 필수 관문

| 영역 | 배점 | 검토 질문 |
| --- | --- | --- |
| 원리·가정 | 20 | 목적함수, shape, inductive bias와 논문의 실험 조건을 설명하는가? |
| 구현·검산 | 25 | gradient/closed form·불변식·음성 테스트가 오류를 실제로 검출하는가? |
| 실험 설계 | 25 | 누출 없는 split, baseline, 예산, 평가 지표·독립 단위가 있는가? |
| 실패 분석 | 20 | 잘되는 조건 외에 깨지는 조건과 대안 원인을 검토했는가? |
| 재현 기록 | 10 | 타인이 같은 명령과 조건으로 결과를 확인할 수 있는가? |

80점 이상이어도 **test 누출, 원논문 수치와 자체 실측 혼동, 미실행을 성공으로 표시, 정답 oracle 사후 변경** 중 하나가 있으면 통과하지 않습니다. 이는 교육용 rubric이지 외부 자격 인증이 아닙니다.

ML→DL 관문은 누출 없는 ML 비교 보고서와 logistic gradient 검산, 비선형 표현의 필요성 설명입니다. DL→LLM 관문은 학습 loop/gradient 검산과 next-token shift·causal 문맥·teacher forcing/생성 평가 구분입니다. 상세 항목은 [로드맵](ml-dl-llm-roadmap.md)에 있습니다.

## 통계와 비교에서 지킬 것

결정론 smoke test는 재현 도구입니다. 하나의 고정 seed를 여러 번 실행한 것은 새로운 독립 실험 여러 개가 아닙니다. 실제 비교에서는 사전에 고른 여러 seed/split을 짝지어 평균·산포·실패 run을 기록하고, 사람/문서 단위 상관이 있으면 resampling 단위도 맞춥니다. 표본이 작으면 우월성 결론을 보류합니다.

validation으로 모델·threshold·epoch를 고르고 최종 test는 선택 후 사용합니다. test를 본 뒤 튜닝했다면 그 test는 개발 자료가 되었음을 기록하고 새로운 최종 평가가 필요합니다. metric 여러 개 중 좋아진 것만 사후 선택하지 않습니다. 분류 accuracy와 log loss/Brier, reconstruction error와 cluster 의미, token NLL와 생성 task 성공을 바꿔 부르지 않습니다.

## 미니 연구와 확장

ML 마지막 모듈에서는 동일 split의 선형/로지스틱 또는 stump 기반 baseline에 한 변경을 비교합니다. DL 마지막 모듈에서는 tiny sequence 모델의 loss·문맥 길이·causal 오류 중 하나만 선택합니다. 모든 알고리즘·자연어 corpus·GPU 분산 학습을 한 미니 연구에 요구하지 않습니다.

논문 전체 재현은 별도 scope입니다. dataset/전처리·학습 횟수·모델 크기·optimizer·hardware·평가 절차의 차이표를 먼저 쓰고, 원논문 수치를 얻지 못해도 설명 가능한 실패를 결과로 제출합니다. [기존 LLM 재현 계약](llm-paper-lab/reproducibility.md)의 비교·실패 보존 원칙도 이어서 사용합니다.
