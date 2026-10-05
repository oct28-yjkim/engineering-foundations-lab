# 12문항 기초 진단

[시작 안내](README.md) · [공식 자료 안내](resources.md)

30~60분 동안 종이와 계산기로 풉니다. 각 문제에 **답 + 계산 한 줄 + 확신 여부**를 남깁니다. 코드를 돌려 얻은 답은 별도로 표시합니다. 아직 모르는 문제는 공부할 위치를 알려 주는 표지이지 실패가 아닙니다.

총점으로 실력을 단정하지 않습니다. 각 영역의 세 문제를 보고 어떤 설명이 필요한지 찾습니다. 정답을 맞혀도 계산 이유를 설명하지 못하면 아래 연결표의 해당 절을 봅니다. 해설은 문제 아래에 접어 두었습니다.

## A. 벡터·행렬 — Q01~Q03

**Q01.** 벡터 `[2, -1]`과 `[3, 4]`의 내적은 얼마인가요? 원소별 곱 `[6, -4]`와 무엇이 다른가요?

**Q02.** 행렬 `A`가 `2×3`, `B`가 `3×2`이면 `AB`와 `BA`는 각각 가능한가요? 가능하다면 결과 크기는 무엇인가요? `A`와 길이 2인 열벡터를 곱할 수 있나요?

**Q03.** `x=(2,3)`을 `u=(1,0)` 방향의 직선에 직각으로 내린 투영은 무엇인가요? `x - 투영`과 `u`의 내적도 구하세요.

<details>
<summary>A 영역 해설 — 먼저 직접 계산하세요</summary>

- Q01: `2×3 + (-1)×4 = 2`. 내적은 대응 원소의 곱을 더한 **숫자 하나**입니다. 원소별 곱은 두 숫자를 가진 벡터입니다.
- Q02: `AB`는 `2×2`, `BA`는 `3×3`입니다. 중간 크기가 각각 3, 2로 같아 둘 다 가능합니다. `A(2×3)`와 `v(2×1)`은 중간 크기 3과 2가 달라 곱할 수 없습니다.
- Q03: 투영은 `(2,0)`, 남는 벡터는 `(0,3)`입니다. `(0,3)·(1,0)=0`이므로 남는 성분은 기준 방향에 직각입니다.

</details>

## B. 미분·연쇄법칙 — Q04~Q06

**Q04.** `f(x)=3x²`일 때 `x=2`에서 미분값은 얼마인가요? 함수값과 미분값은 각각 무엇을 나타내나요?

**Q05.** `L(w)=(3w-1)²/2`일 때 `w=1`에서 `dL/dw`를 구하세요. 바깥 함수와 안쪽 함수의 미분을 각각 적으세요.

**Q06.** 예측 `ŷ=wx+b`, 손실 `L=(ŷ-y)²/2`입니다. `x=2, y=5, w=1, b=1`에서 `∂L/∂w`, `∂L/∂b`를 각각 구하세요. 여기서 `x,y`는 고정된 관측값입니다.

<details>
<summary>B 영역 해설 — 먼저 직접 계산하세요</summary>

- Q04: `f'(x)=6x`이므로 미분값은 `12`입니다. 우연히 함수값 `f(2)=12`도 같습니다. 전자는 그 지점의 변화율이고 후자는 함수의 높이이므로 같은 개념은 아닙니다.
- Q05: `z=3w-1`, `dL/dz=z`, `dz/dw=3`. `w=1`이면 `z=2`이므로 `dL/dw=2×3=6`입니다.
- Q06: `ŷ=3`, 오차 `ŷ-y=-2`. 따라서 `∂L/∂w=(-2)×2=-4`, `∂L/∂b=-2`입니다. 정답 `y-ŷ`로 오차를 뒤집으면 식 전체도 일관되게 다시 미분해야 합니다.

</details>

## C. 확률·통계 — Q07~Q09

**Q07.** 가상의 부품 검사입니다. 전체의 10%가 불량이고, 불량 중 80%가 경고를 받습니다. 정상 중 20%도 경고를 받습니다. 경고를 받은 부품이 실제 불량일 확률은 얼마인가요? 100개 부품의 표로 풀어도 됩니다.

**Q08.** 값 `[1,2,3]`을 같은 확률로 뽑는 분포의 평균과 분산을 구하세요. 같은 숫자를 세 개의 독립 관측 sample로 보고 표본분산을 계산하면 분모와 결과가 어떻게 달라지나요?

**Q09.** 실제 정답에 확률 `0.25`를 준 예측과 `0.5`를 준 예측 중 NLL이 더 작은 것은 무엇인가요? 자연로그를 사용해 두 값을 비교하세요. 두 정답 token 각각에 `0.5`를 준 경우, 평균 NLL과 perplexity는 얼마인가요?

<details>
<summary>C 영역 해설 — 먼저 직접 계산하세요</summary>

- Q07: 불량 10개 중 경고 8개, 정상 90개 중 경고 18개입니다. 전체 경고 26개 중 불량은 8개이므로 `8/26=4/13≈0.3077`입니다. 80%가 아닙니다.
- Q08: 평균은 `2`. 제곱 편차 합은 `1+0+1=2`. 분포의 분산은 `2/3`, 통상적인 불편 표본분산은 `2/(3-1)=1`입니다. 두 계산의 질문과 분모가 다릅니다.
- Q09: `-ln(0.25)=ln4≈1.3863`, `-ln(0.5)=ln2≈0.6931`이므로 후자가 작습니다. 평균 NLL은 `ln2`, perplexity는 `exp(ln2)=2`입니다. NLL을 단순 확률 평균으로 계산하지 않습니다.

</details>

## D. 최적화·수치 계산 — Q10~Q12

**Q10.** `L(w)=w²/2`, 시작 `w=4`, 학습률 `η=0.25`입니다. gradient descent 한 번 뒤 `w`와 손실은 얼마인가요? 이전 손실과 비교하세요.

**Q11.** `L(x,y)=(x²+10y²)/2`입니다. 시작 `(1,1)`에서 gradient와 학습률 `0.3`으로 한 번 이동한 좌표를 구하세요. 손실이 줄었나요? 미분이 맞아도 이런 결과가 가능한가요?

**Q12.** 점수가 `[1000,1000]`일 때 `exp(score)/sum(exp(score))`를 그대로 계산하지 않고 softmax를 구하세요. `log(sum(exp(score)))`도 큰 지수 계산 없이 식으로 표현하세요.

<details>
<summary>D 영역 해설 — 먼저 직접 계산하세요</summary>

- Q10: gradient는 `4`. `w_new=4-0.25×4=3`. 손실은 `8 → 4.5`입니다.
- Q11: gradient는 `(1,10)`. 새 좌표는 `(0.7,-2)`. 이전 손실 `5.5`보다 새 손실 `(0.49+40)/2=20.245`가 큽니다. 이 식의 가파른 축에서는 학습률이 너무 큽니다. gradient가 맞다는 것과 주어진 step이 안정적이라는 것은 다릅니다.
- Q12: 최댓값 1000을 빼면 `[0,0]`. softmax는 `[1/2,1/2]`입니다. log-sum-exp는 `1000 + ln(exp0+exp0)=1000+ln2`입니다. 로그를 구할 때는 빼 놓은 1000을 다시 더해야 합니다.

</details>

## 틀린 문제에서 바로 보충하기

공식 자료 링크는 [resources.md](resources.md)의 영역별 **첫 자료**를 가리킵니다. 그곳에서 지정된 절만 선택합니다. 재검산 번호는 각 강의 하단에 실제 문제와 해설이 있습니다.

| 진단 | 다시 읽을 절 | 공식 첫 자료에서 읽을 부분 | 새 숫자로 재검산 |
| --- | --- | --- | --- |
| Q01 | [V1. 벡터와 내적](lessons/01-vectors-matrices.md#v1) | [Stanford](resources.md#vectors) §1, §2.1 | [R01](lessons/01-vectors-matrices.md#r01) |
| Q02 | [V2. 행렬 곱과 크기](lessons/01-vectors-matrices.md#v2) | [Stanford](resources.md#vectors) §2.2~2.3 | [R02](lessons/01-vectors-matrices.md#r02) |
| Q03 | [V3. 길이와 투영](lessons/01-vectors-matrices.md#v3) | [Stanford](resources.md#vectors) §3.5, 이후 MIT 강의 15 | [R03](lessons/01-vectors-matrices.md#r03) |
| Q04 | [D1. 변화율](lessons/02-derivatives-chain-rule.md#d1) | [MIT 18.01SC](resources.md#derivatives) Session 1, 6 | [R04](lessons/02-derivatives-chain-rule.md#r04) |
| Q05 | [D2. 연쇄법칙](lessons/02-derivatives-chain-rule.md#d2) | [MIT 18.01SC](resources.md#derivatives) Session 11 | [R05](lessons/02-derivatives-chain-rule.md#r05) |
| Q06 | [D3. 여러 parameter와 평균](lessons/02-derivatives-chain-rule.md#d3) | [MIT 18.02SC](resources.md#derivatives) Session 32, 35 | [R06](lessons/02-derivatives-chain-rule.md#r06) |
| Q07 | [P1. 조건부 확률](lessons/03-probability-statistics.md#p1) | [Stanford](resources.md#probability) §1.1 | [R07](lessons/03-probability-statistics.md#r07) |
| Q08 | [P2. 평균과 분산](lessons/03-probability-statistics.md#p2) | [Stanford](resources.md#probability) §2.4~2.5 | [R08](lessons/03-probability-statistics.md#r08) |
| Q09 | [P3. 로그 확률과 NLL](lessons/03-probability-statistics.md#p3) | [Stanford](resources.md#probability) §1.1의 확률 방향 복습 후 본 강의 P3 | [R09](lessons/03-probability-statistics.md#r09) |
| Q10 | [O1. 한 번의 업데이트](lessons/04-optimization-numerics.md#o1) | [MML](resources.md#optimization) 7장, gradient descent 부분 | [R10](lessons/04-optimization-numerics.md#r10) |
| Q11 | [O2. 축별 가파름과 scale](lessons/04-optimization-numerics.md#o2) | [MML](resources.md#optimization) 7장과 5장 미분 복습 | [R11](lessons/04-optimization-numerics.md#r11) |
| Q12 | [O3. 안정적인 로그 계산](lessons/04-optimization-numerics.md#o3) | [MML](resources.md#optimization) 6장의 확률 표기 복습 후 본 강의 O3 | [R12](lessons/04-optimization-numerics.md#r12) |

외부 첫 자료가 이 저장소의 모든 주제나 코드까지 설명한다는 뜻은 아닙니다. 특히 NLL·log-sum-exp 계산은 연결한 본 강의의 손계산도 함께 봅니다.

## 다시 점검하는 방법

재검산에서 틀린 경우 답을 외우지 말고 **내가 사용한 식 → 잘못된 중간값 → 올바른 중간값 → 원인**을 적습니다. 하루 이상 뒤 같은 개념의 숫자를 바꿔 다시 풀어 봅니다. 네 영역 각각에서 계산, 이유 설명, 실패 사례 설명을 할 수 있는지를 확인한 뒤 [다음 학습 단계](README.md#무엇을-할-수-있으면-다음-단계로-가나요)로 연결합니다.
