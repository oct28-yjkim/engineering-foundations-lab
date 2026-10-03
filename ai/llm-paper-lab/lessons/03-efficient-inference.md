# 03. 효율적 추론: FLOPs, IO, 메모리 관리, 분포 보존

[트랙 소개](../README.md) · [논문 목록](../papers.md) · [실행 환경과 CPU 실습](../labs/README.md) · [평가 기준](../assessment.md)

M06–M07, 총 4주 과정이다. “빨라졌다”는 주장은 동일한 품질·workload·측정 경계에서만 비교한다. CPU 축소 모형으로 correctness의 일부를 검증하고, GPU kernel·실제 serving 성능은 학습자 구현 과제로 분리한다.

원문 확인일: 2026-10-04. 읽기 기준은 P08 arXiv v2, P09 v1, P10 v2다. P10의 첫 arXiv 공개는 2022년이며 후속 학회 발표 연도와 구분한다. 최신 라이브러리의 기능·기본값을 과거 논문의 구현과 동일시하지 않는다.

## 측정 언어부터 고정하기

| 측정값 | 이 Lab에서 기록할 경계 | 흔한 혼동 |
| --- | --- | --- |
| TTFT | 요청 접수부터 첫 token 도착, queue 포함 여부 명시 | prefill kernel 시간과 동일시 |
| Inter-token latency | decode 중 token 사이 시간 분포 | 전체 latency를 token 수로 나눈 평균과 혼합 |
| End-to-end latency | 요청 접수부터 종료·실패 | 성공한 짧은 요청만 선택 |
| Throughput | 측정 구간의 완료 요청 또는 출력 token | 생성 요청량과 완료 처리량 혼합 |
| Goodput | 사전에 정한 latency·정확성 SLO를 만족한 처리량 | SLO 위반 결과까지 모두 성공 처리 |
| Memory | weights, KV, activation, allocator reserve, host 별도 | KV 이론값을 프로세스 peak VRAM으로 보고 |

측정 시간, warm-up, 동시성 또는 도착률, prompt/output 길이 분포, 요청 취소·실패율, precision, GPU·driver·kernel revision을 저장한다. 기존 DB·Kafka·Sentry 과정은 실험 결과 수집에 연결할 수 있지만, 계측이 없는 동작을 추정해 채우지는 않는다.

<a id="m06"></a>
## M06 · FlashAttention과 PagedAttention — 11–12주

### 두 논문이 푸는 문제가 다르다

[P08 FlashAttention](https://arxiv.org/html/2205.14135v2)은 HBM/SRAM 사이 IO를 줄이는 exact attention 알고리즘이다. tiling과 softmax 통계량을 이용하고 backward에서 일부 값을 다시 계산한다. exact는 attention을 근사하지 않는다는 뜻이며 floating-point 연산 순서까지 같은 bitwise 결과라는 뜻은 아니다. 기본 dense attention의 모든 pair 계산을 linear arithmetic으로 바꾼 것은 아니다.

[P09 PagedAttention](https://arxiv.org/html/2309.06180v1)은 sequence의 논리 KV block을 비연속 물리 block에 매핑해 fragmentation과 중복 복사를 줄인다. 공유 block, reference count, copy-on-write를 serving에 적용한다. 이는 attention의 softmax normalization을 바꾸는 논문이 아니다. 현재 vLLM 실행 결과가 원래 논문의 software/hardware baseline 재현인지는 별도 확인해야 한다.

### 11주차: online softmax와 메모리 장부

원리에 대한 독립 수기·추가 구현 과제다. 제공 실행기가 FlashAttention kernel을 구현하는 것은 아니다.

1. 하나의 query에 대한 score를 두 block으로 나눈다. block i의 최대값은 `m_i=max_j s_j`, 지수합은 `l_i=sum_j exp(s_j-m_i)`, value 가중합은 `u_i=sum_j exp(s_j-m_i)*v_j`로 정의한다. 각 합의 j는 해당 block 안의 유효 key를 순회한다. `u_i`는 value 차원의 벡터이며 아직 정규화하지 않은 합이다.
2. 두 block을 다음처럼 합치고 dense softmax 결과와 비교한다. 이는 교육용 algebra 검사다.

```text
m = max(m_1, m_2)
l = exp(m_1-m) * l_1 + exp(m_2-m) * l_2
u = exp(m_1-m) * u_1 + exp(m_2-m) * u_2
output = u / l
```

3. 단순히 block별 softmax 출력을 더하는 잘못된 구현을 대조군으로 둔다. block 길이와 score 크기가 다를 때 오류가 드러나야 한다.
4. causal mask로 block 전체가 제외될 수 있다. 초기 상태 `m=-inf, l=0, u=0`을 수치적으로 안전하게 처리하도록 설계하고, 유효 key가 전혀 없는 query는 정의 또는 거부 정책을 명시한다.
5. forward 값 비교만으로 backward gradient가 옳다고 결론 내리지 않는다. GPU 확장 시 dropout RNG와 mask, backward도 별도 검증 대상으로 둔다.

KV cache의 다음 교육용 장부를 유도한다. tensor parallel sharding·압축·quantization metadata·allocator 여유분은 우선 제외한 논리량이다.

```text
KV bytes ≈ 2 * L * B * T * H_kv * d_head * bytes_per_element
L: layer 수, B: 동일 길이 sequence 수, T: 저장 token 길이
H_kv: KV head 수, d_head: 각 head 차원
2: K와 V 두 배열
```

query head 수 대신 KV head 수를 쓰는 이유를 설명한다. 실제 variable-length batch라면 `B*T` 대신 sequence별 저장 token 수의 합을 사용한다. MHA/GQA/MQA 구성, KV quantization, prefix 공유, 분산 배치가 달라지면 장부도 다시 작성한다.

### 12주차: CPU 모형 → 선택적 GPU serving

```powershell
python ai/llm-paper-lab/labs/lab.py --lab kv-cache
```

제공 모형은 KV head 수에 따른 **논리 cache payload 바이트 계산**이다. [실습 문서](../labs/README.md)와 코드를 함께 읽는다. 이 명령은 vLLM 서버·CUDA kernel·block allocator를 시작하지 않는다. 다음 block lifecycle simulator와 GPU 실험은 학습자 확장 과제다.

- token 길이 `T`, block 크기 `b`에 대해 필요한 block 수 `ceil(T/b)`와 마지막 block의 slack을 계산한다. 물리 block 공유가 없다면 sequence당 slack은 `b` 미만이지만 weights·metadata·전역 reserve까지 무손실이라는 뜻은 아니다.
- `allocate → append → fork/share → copy-on-write → finish/cancel → release` 이벤트를 모형화한다. 공유 block을 직접 수정했을 때 다른 요청이 오염되는 반례를 만든다.
- 매 이벤트마다 reference count가 살아 있는 참조 수와 일치하는지 확인한다. free block 재사용 뒤 이전 요청의 값이 노출되지 않는지도 별도 검사한다.
- prefix 공유를 평가한다면 token ID, model/adapter revision, 위치 조건 등의 cache key 계약을 명시한다. 다중 tenant 보안 정책을 prefix 문자열 equality로 대체하지 않는다.

실제 GPU 확장에서는 아래 비교를 섞지 않는다.

| 실험 | 바꿀 항목 | 유지할 항목 | 추가 검증 |
| --- | --- | --- | --- |
| Attention kernel | dense 기준과 선택한 Flash kernel | dtype, shapes, mask, dropout 조건 | forward·backward 오차, 실제 kernel dispatch |
| Serving memory | allocator/block 정책 | model, workload, memory budget | peak KV·fragmentation·cancel 후 반환 |
| Batch scheduler | 요청 배치 정책 | kernel·allocator와 요청 도착 trace | queue time, fairness, tail latency |
| Prefix reuse | 공유 사용 여부 | 같은 prompt 집합, cache warm/cold 상태 | cache hit뿐 아니라 정확성·격리 |

kernel microbenchmark에서 GPU synchronization·warm-up을 정의한다. serving에서는 closed-loop concurrency 실험과 open-loop arrival-rate 실험을 구분하고, 부하를 고정했을 때의 p50/p95/p99를 기록한다. 최대 throughput만 보고 개별 요청의 tail latency를 숨기지 않는다.

### 반례와 통과 기준

- **통과:** softmax 합성의 정확성, KV 장부의 단위, logical/physical block의 차이를 설명하고 CPU 모형과 실제 성능 측정의 경계를 적는다.
- **실패:** CPU 실행 시간이 짧다는 사실로 FlashAttention speedup을 주장하거나, paging이 KV token당 논리량 자체를 없앤다고 설명하거나, kernel과 scheduler를 함께 바꾸고 원인을 하나로 단정한다.
- correctness·메모리 격리 실패가 있으면 성능 수치가 좋아도 불합격이다. 실제 GPU가 없으면 성능 결과는 `미실행`으로 제출한다.

제출물: memory ledger, online softmax 반례, block event trace와 invariant, GPU 확장 protocol, workload별 성능·정확성 측정표.

<a id="m07"></a>
## M07 · Speculative decoding — 13–14주

### 원리: 빠른 초안과 정확한 검증

[P10 원문](https://arxiv.org/html/2211.17192v2)에서 target 분포 `p`, draft 분포 `q`의 acceptance와 rejection을 읽는다. draft에서 뽑은 token `x`를 `min(1,p(x)/q(x))` 확률로 채택한다. 거부되면 `max(0,p-q)`를 정규화한 residual에서 다시 뽑는다. 이 보정이 target 분포 보존의 핵심이다. 여러 draft를 검증할 때 최초 거부 이후의 draft를 버리고, 전부 채택되면 target에서 추가 token을 뽑는다. sampling 설정이 반영된 분포와 실제 구현의 수치 조건이 일치해야 한다.

### 13주차: 유한 분포의 정확성 증명

제공 CPU 실행기에는 speculative decoding 구현이 없다. 다음은 종이·spreadsheet 없이도 계산할 수 있는 수치 예제와 학습자 구현 과제다.

```text
vocabulary: [a, b, c]
p = [0.6, 0.3, 0.1]       target
q = [0.2, 0.5, 0.3]       draft
accepted mass = min(p,q) = [0.2, 0.3, 0.1]
acceptance probability = 0.6
rejection probability = 0.4
normalized residual = [1.0, 0.0, 0.0]
final mass = accepted mass + 0.4 * residual = p
```

이 예제는 Lab이 만든 숫자이며 논문의 실측값이 아니다.

1. `q(x)>0`인 draft 후보에만 비율을 적용한다. `q(x)=0`인 token도 target residual에서는 나올 수 있다는 점을 증명한다.
2. `p=q`이면 rejection probability가 0이므로 residual을 0으로 나누는 코드는 실행되면 안 된다. 지지집합이 서로 겹치지 않는 경우에는 모두 거부되는 경계값을 검사한다.
3. 거부 시 residual 대신 원래 p에서 다시 뽑는 잘못된 구현의 최종 분포를 위 숫자로 계산한다. 그 결과가 p와 다름을 보여야 한다.
4. 학습자가 categorical sampler를 구현하면 exact probability 열거 검사와 Monte Carlo 빈도 검사를 나눈다. stochastic 오차 tolerance는 표본 수에 맞춰 사전 정의하고 seed 하나의 우연한 일치로 증명하지 않는다.
5. prefix마다 다른 분포를 주는 2-step 모형으로 확장한다. 단일 token marginal만 맞는 것과 joint sequence 분포가 맞는 것은 다르다.
6. temperature/top-k/top-p 같은 변환이 있다면 target baseline과 검증에 쓰인 p, 실제 draft sampling에 쓰인 q의 정규화된 분포를 각각 기록한다. 서로 다른 분포로 계산한 acceptance는 보존 증명을 적용할 수 없다.

### 14주차: 비용 모형과 선택적 실제 모델 확장

고정 acceptance `a`, draft 길이 `g`가 독립적으로 유지된다는 단순화에서 한 검증 round의 기대 생성량은 `1+a+...+a^g`다. 실제 token별 acceptance는 상관될 수 있으므로 이 식을 보장된 실제 처리량으로 쓰지 않는다. 비교 비용은 아래처럼 분해한다.

```text
baseline cost per round ≈ expected_emitted_tokens * target_one_step_time
speculative cost per round ≈ g * draft_step_time + target_verify_time(g)
                             + sampling_and_cache_overhead
```

- 먼저 draft/target tokenizer와 vocabulary, special tokens, chat template, 위치 인코딩의 호환성을 확인한다. 서로 다른 token space의 확률을 그대로 나눌 수 없다.
- 같은 target의 일반 sampling을 baseline으로 두고 동일 prompt·output cap·sampling 설정에서 비교한다. 별도 모델 품질 개선이 아니라 target 분포를 유지하며 latency를 바꾸는 질문이다.
- draft 길이, draft 모델 크기, 입력 길이, concurrency를 한 축씩 바꾼다. acceptance가 높아도 draft 비용 때문에 느려지는 사례를 포함한다.
- 첫 거부 이후 target/draft KV rollback, EOS 조기 종료, 취소, timeout을 검증한다. 이미 거부된 token을 streaming 사용자에게 먼저 확정 출력하지 않는다.
- 동일 seed가 baseline과 동일 문자열을 만드는 것이 분포 보존의 일반 조건은 아니다. RNG 소비 순서가 다를 수 있다. deterministic greedy 모드의 exact token 검사와 stochastic 분포 검사를 분리한다.
- 작은 vocabulary에서 수치 correctness를 먼저 통과하고, 실제 모델에서는 원시 출력·acceptance trace·지연 분포·메모리·실패율을 함께 기록한다.

### 통과 기준

- **통과:** acceptance+residual의 확률 합이 p임을 독립 계산하고, 고의로 잘못된 rejection 대조군을 검출하며, 실제 speedup의 비용 조건을 설명한다.
- **실패:** draft top-1이 target top-1과 자주 같다는 사실만으로 stochastic 정확성을 주장하거나, target 검증 없이 draft token을 채택하거나, acceptance 비율을 speedup으로 그대로 보고한다.
- 실제 draft/target 모델과 cache 처리를 실행하지 않았으면 `categorical 알고리즘 검사`로만 제출한다. 최신 serving 엔진의 speculative 지원 여부를 논문의 보장으로 추정하지 않는다.

제출물: 유한 분포 증명, 경계값 테스트, 잘못된 알고리즘의 반례, 비용 분해, 실제 모델 실행 여부·한계, correctness 통과 뒤의 성능 보고서.
