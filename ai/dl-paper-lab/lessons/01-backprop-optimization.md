# 계산 그래프 역전파와 최적화

[DL 과정](../curriculum.md) · [논문 DL01과 DL07](../papers.md) · [실습](../labs/README.md)

## forward의 중간값은 왜 필요한가

층의 출력 `h=φ(Wx+b)`는 입력의 표현을 바꾸고 다음 층에 전달합니다. backward에서는 loss가 h를 통해 W와 x에 어떻게 변하는지 chain rule로 계산합니다. reverse-mode autodiff는 출력에서 입력 방향으로 vector-Jacobian product를 누적하며, 모든 parameter를 한 번씩 미세하게 바꾸는 numerical differentiation과 다른 계산입니다.

같은 parameter가 두 경로에 쓰이면 gradient도 두 경로의 기여를 더합니다. 수기 예로 `u=w*x`, `L=u*u+u`, x=2,w=3이면 u=6,L=42, `dL/dw=(2u+1)x=26`입니다. graph traversal에서 같은 node를 두 번 갱신하거나, 부모의 gradient를 덮어쓰면 잘못된 값이 됩니다. 제공 scalar graph의 테스트에서 이 공유 구조와 central difference를 확인합니다.

```text
python -B ai/dl-paper-lab/labs/lab.py --lab backprop
```

코드는 XOR용 작은 MLP를 실제로 학습합니다. forward → loss → gradient 초기화 → backward → optimizer step의 순서를 추적하고 초기/최종 loss, parameter 변화, gradient error를 기록합니다. 알려진 네 점의 정확도는 fitting 증거이고 주변 합성 좌표의 평가는 그 생성 규칙에 한정됩니다. 일상 데이터의 일반화를 검증한 것이 아닙니다.

## optimizer는 graph와 별도의 상태다

SGD는 gradient 방향을 사용하고 momentum은 이전 갱신의 상태를 유지합니다. Adam은 gradient의 1차/2차 moment 추정과 초기 bias 보정을 사용합니다. 학습 parameter θ와 optimizer의 m,v,step을 구분합니다. checkpoint에서 θ만 복원하는 것과 학습 상태 전체를 복원하는 것은 다릅니다.

Adam의 대표 convention은 `mₜ=β₁mₜ₋₁+(1−β₁)gₜ`, `vₜ=β₂vₜ₋₁+(1−β₂)gₜ²`, `m̂=mₜ/(1−β₁ᵗ)`, `v̂=vₜ/(1−β₂ᵗ)`, `θ←θ−ηm̂/(sqrt(v̂)+ε)`입니다. epsilon 위치와 momentum 식은 구현별 convention을 확인합니다. [원문 Algorithm 1](https://arxiv.org/abs/1412.6980)과 실제 코드를 대조합니다.

```text
python -B ai/dl-paper-lab/labs/lab.py --lab optimization
```

기본 비교는 작은 고정 목적함수의 계산·상태·수렴 경로입니다. 같은 learning rate 숫자가 optimizer 간 동등한 tuning 예산을 뜻하지 않으며, 이 결과로 Adam이 SGD보다 항상 좋다고 하지 않습니다. Adam과 decoupled weight decay를 쓰는 AdamW도 구분합니다. scheduler·AdamW·checkpoint 복원은 추가 구현 과제입니다.

## 학습 실패를 진단하는 순서

| 증상 | 먼저 보는 값 | 원인을 가르는 작은 실험 |
| --- | --- | --- |
| loss가 그대로임 | parameter 전후·gradient norm | 표본 하나 overfit, gradient 누락/zeroing 순서/step 호출 확인 |
| loss가 발산함 | finite 여부·activation 범위·update norm | 작은 learning rate로 비교, 안정한 exp/log, 손실 sum/mean 대조 |
| gradient가 예상보다 큼 | batch/공유 횟수·누적 상태 | parameter 한 개 유한차분, 두 step 사이 grad 초기화 검산 |
| 깊어지면 초반부터 포화 | 층별 activation·gradient 분포 | 초기 scale·activation 하나만 바꾼 비교; 가설과 관측 분리 |

초기화의 영향은 [Glorot와 Bengio의 초기화 연구](https://proceedings.mlr.press/v9/glorot10a.html)를 선택 읽기로 연결합니다. 이것은 핵심 DL 목록 12편과 별도의 보충 논문입니다. 작은 scalar 엔진은 tensor broadcasting, device, mixed precision, 병렬 reduction을 구현하지 않습니다. framework 확장은 같은 초기값으로 **출력 → gradient → 한 step → 짧은 학습** 순서로 대조합니다.

완료 기준은 한 공유 node의 손미분, finite difference의 허용 오차와 부적절한 지점 설명, 실제 학습 결과, 잘못된 gradient 초기화가 실패하는 회귀 테스트입니다. loss 감소만으로 gradient 전체가 올바르다고 결론 내리지 않습니다.
