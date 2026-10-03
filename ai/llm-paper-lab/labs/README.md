# Offline paper-mechanism labs

GPU·모델·API 없이 논문의 핵심 식과 실패 조건부터 확인하는 Python 표준 라이브러리 실험이다. **6개 모두 실제 논문 재현이나 모델 성능 벤치마크가 아니다.** 작은 반례를 직접 설명한 뒤 [커리큘럼](../curriculum.md)의 모델·시스템 확장 실험으로 진행한다. 논문 ID는 [논문 카탈로그](../papers.md)에서 확인한다.

## 실행 계약

- Python 3.10 이상만 필요하다. 추가 패키지, 가상환경, API key, Docker가 필요하지 않다.
- 이 코드는 네트워크·외부 모델·데이터 다운로드·파일 쓰기를 수행하지 않는다. 모든 데이터는 코드 안의 자체 작성 synthetic fixture다.
- `-B`는 Python의 import bytecode cache 생성도 막는다. 출력은 stdout JSON이며 파일로 저장하려면 사용자가 명시적으로 리다이렉션한다.
- 부트스트랩만 seed `20261004`를 사용한다. 나머지는 고정 배열·정해진 계산이다. 실험 중 검증 실패는 `ValueError`, CLI 인자 오류는 비정상 종료로 처리한다. `python -O`로 제거되는 `assert` 문에 의존하지 않는다.
- 소수점 마지막 자리는 Python/플랫폼에 따라 달라질 수 있다. 수치 비교는 테스트에 명시된 오차 범위를 따른다. 런타임 버전은 JSON의 `runtime`에 포함하며 실행 시간 자체는 성능 지표로 보고하지 않는다.

저장소 루트에서 Bash 또는 PowerShell 모두 같은 명령을 사용할 수 있다.

```text
python --version
python -B ai/llm-paper-lab/labs/lab.py --lab all
python -B ai/llm-paper-lab/labs/lab.py --lab attention
python -B ai/llm-paper-lab/labs/lab.py --lab lora
python -B ai/llm-paper-lab/labs/lab.py --lab dpo
python -B ai/llm-paper-lab/labs/lab.py --lab kv-cache
python -B ai/llm-paper-lab/labs/lab.py --lab retrieval
python -B ai/llm-paper-lab/labs/lab.py --lab evaluation
python -B -m unittest discover -s ai/llm-paper-lab/labs -p "test_*.py" -v
```

Windows에서 `python`이 Microsoft Store alias만 가리키면 설치된 Python의 **확인한 실제 경로**를 사용하거나 `py -3`로 대체한다. 이 랩은 런타임을 자동 설치하지 않는다. PowerShell의 공백 포함 실행 파일 경로는 `& 'C:/실제 경로/python.exe' -B ...` 형식으로 호출한다.

## 6개 실험과 검증 경계

| CLI | 연결 | 실제 계산·반례 | 이 랩으로 주장할 수 없는 것 |
|---|---|---|---|
| `attention` | M01 / P01 | 안정적인 masked softmax, 인과적 prefix 불변성, 미래 토큰 누출 negative control, key padding | Transformer 학습 재현, multihead 구현, GPU 커널 성능 |
| `lora` | M03 / P04 | `Wx + (alpha/r)BAx`와 merged weight 동치, parameter 수, 초기 `B=0`에서 A/B 유한차분 gradient | 실제 fine-tuning 품질·메모리 절감률, QLoRA, optimizer 상태 |
| `dpo` | M05 / P07 | reference-relative log-ratio margin, 안정적 log-sigmoid, `log(2)` 기준, 선호/비선호 gradient 방향 | 학습된 policy 분포, 선호 데이터 타당성, alignment·안전성 향상 |
| `kv-cache` | M06 / P09 | MHA/GQA KV payload 식, head 수·sequence 길이 변화 | PagedAttention allocator 구현, 실측 GPU 메모리, latency·throughput |
| `retrieval` | M08 / P11·P12 | 단어 집합 교집합 baseline, Recall/MRR/NDCG 손계산 oracle, tenant prefilter, 분리한 query split | BM25·DPR·embedding 모델, RAG 생성, prompt-injection 방어 일반화 |
| `evaluation` | M12 / P18·P19·P20 | 고정 paired prediction exact match, seeded bootstrap, family dependence·gold-copy leakage 반례 | HELM·IFEval·RAGAS 실행, LLM judge 신뢰성, 배포 승인 |

### Attention: mask가 식의 일부다

`softmax(QK^T / sqrt(d_k))V`의 단일 head만 계산한다. 허용된 logit의 최댓값을 먼저 빼서 큰 양수 logit의 지수 overflow를 피한다. 미래 key/value를 크게 변경해도 인과적 출력의 앞부분은 같아야 한다. 인과적 mask를 제거하면 앞부분이 달라져야 한다. 두 검증을 같이 수행해야 "우연히 변화가 없었다"를 구별할 수 있다.

padding mask는 **key 열**을 제거하며 padded query의 출력을 자동으로 0으로 만들지 않는다. 모든 key가 차단된 행은 이 구현의 정의역 밖이므로 오류를 낸다. 실제 라이브러리의 all-masked 처리 계약은 별도로 확인한다. NaN/무한대 logit은 mask 뒤에 숨기지 않고 거부한다.

### LoRA: 동치와 학습 경로를 분리한다

`W[out,in]`, `A[rank,in]`, `B[out,rank]`, `scale=alpha/r`를 사용한다. base parameter 수는 `out*in`, trainable adapter 수는 `r*(in+out)`이다. 이 작은 예제는 base 6개에 adapter 5개이므로 큰 절감률을 보여주는 데 적합한 크기가 아니다. adapter를 붙인 전체 저장 parameter 수와 **학습 대상** parameter 수도 혼동하지 않는다.

초기 `B=0`에서 adapter update는 0이고 A gradient도 0이다. B gradient는 입력·target·A가 퇴화하지 않은 이 fixture에서 0이 아니다. `A=0`까지 함께 초기화하거나 residual이 0인 반례에서는 B도 0일 수 있다. 유한차분은 analytic B gradient와 비교하며 작은 step에 따른 수치 오차를 허용한다. 실제 backprop/autograd·optimizer step은 수행하지 않는다.

### DPO: reference를 빼지 않으면 다른 목적함수다

고정 prompt의 chosen/rejected completion에 대한 **sequence log-probability 합** 네 개를 입력으로 본다. `z = beta * [(log p_chosen - log p_rejected) - (log ref_chosen - log ref_rejected)]`, `loss = -log sigmoid(z)`다. policy가 reference와 같으면 beta에 관계없이 `log(2)`다.

chosen log-probability를 올리거나 rejected 값을 내리면 이 고정 pair의 loss가 줄어든다. 이는 독립 scalar에 대한 미분이며, 실제 모델 parameter를 갱신하면 다른 모든 token 확률과 정규화가 함께 바뀐다. loss만으로 품질 향상을 추론하지 않는다. 큰 양의 margin에서 loss가 floating-point 0이 되는 현상은 명시적 수치 한계다.

### KV cache: 정확한 식에도 가정이 있다

`bytes = 2 * layers * batch * sequence * kv_heads * head_dim * dtype_bytes`를 사용한다. `2`는 K와 V다. query head 수는 GQA grouping의 유효성을 확인하는 데만 사용하며, cache head 수에 곱하지 않는다. 모든 layer/sequence가 같은 full-attention 구조이고 batch의 각 요청이 같은 길이를 유지한다는 가정이다.

가중치·activation·allocator page·fragmentation·quantization scale·padding·tensor-parallel 복제/분할·prefix sharing·sliding window는 포함하지 않는다. 따라서 이 결과를 "필요한 GPU VRAM" 또는 "vLLM 속도"라고 부르면 안 된다. PagedAttention 논문 확장 실험에서는 논리 token 수와 할당된 block 수를 따로 관측한다.

### Retrieval: 점수 이전에 권한을 제한한다

6개 자체 작성 문서와 train 1 / dev 1 / test 2 query를 사용한다. 문서 corpus는 split 간 공유하지만 query ID와 정규화한 query 문자열은 분리한다. **학습·튜닝은 하지 않으며** test 결과를 보고 설정을 선택하지 않는다. 이 검사는 exact overlap만 탐지하고 paraphrase·문서 출처·문제 family 누출을 보장하지 않는다. 모델 실험으로 확대할 때는 family/source/time 기준 split 설계가 필요하다.

`retrieve`는 인증된 호출자가 전달했다고 가정하는 tenant ID로 먼저 후보 문서를 제한하고, 고유 단어 교집합 수로 정렬한다. 동점이면 문서 ID 사전순이다. top-k를 먼저 구한 다음 권한 없는 문서를 지우면 허용된 문서를 놓칠 수 있다는 반례를 테스트한다. 낮은 단계의 `lexical_rank`에는 권한 검사가 없으므로 외부 API로 노출하면 안 된다. 이 랩의 tenant 문자열 자체는 인증 수단이 아니다.

`a_untrusted` 문서에는 악성 명령처럼 보이는 문자열이 있다. 해당 문서를 검색 결과에 포함해도 코드는 이를 실행하거나 tenant scope로 해석하지 않는다. **LLM을 호출하지 않으므로 모델의 prompt-injection 저항성을 검증한 것은 아니다.**

관련도가 양수인 문서를 relevant로 정의한다. `Recall@k=top-k relevant 수/전체 relevant 수`, `MRR@k=첫 relevant rank의 역수(없으면 0)`다. NDCG는 gain `2^grade-1`, discount `log2(rank+1)`를 사용한다. graded qrels와 손계산 oracle로 구현을 점검한다. 작은 synthetic query가 모두 높은 점수를 받더라도 일반 검색 품질을 뜻하지 않는다.

### Evaluation: paired 비교에도 독립성 가정이 있다

12개 불변 prediction을 동일 사례별로 비교한다. accuracy 자체보다 변화량과 개선·회귀 수를 함께 본다. bootstrap은 baseline/candidate를 따로 섞지 않고 paired 차이를 resample한다. 6개 family마다 두 행이 의도적으로 상관되므로 naive row CI는 가정 위반이다. family 단위 bootstrap을 함께 출력하여 resampling 단위의 영향을 확인한다.

가족 단위 resampling은 각 family가 독립적인 모집단 표본이라는 추가 가정이 필요하다. 여기서는 고작 6개 synthetic family이므로 신뢰구간 숫자를 실제 모집단 성능의 근거로 쓰지 않는다. CI가 0을 포함하는 상황을 "candidate가 유의하게 개선됐다"라고 해석해서도 안 된다. gold answer를 prediction에 복사하면 정확도가 1이 된다는 반례는 지표가 데이터 누출을 자동 탐지하지 못함을 보여준다.

## 기대값과 실제 실행 기록

다음의 **기대값**은 fixture와 수식에서 도출한 검증 기준이다. 실행 결과는 JSON `measurements`에서 별도로 확인한다.

| 실험 | 기대값 |
|---|---|
| Attention | causal prefix 오차 0, 미래 누출 negative control은 0보다 큼, 각 확률 행 합 약 1 |
| LoRA | merged 최대 오차 `<1e-12`; A 초기 gradient 0; B analytic gradient `[0.16, -1.04]`와 유한차분 일치 |
| DPO | reference 일치 loss 약 `0.69314718`, beta `0.2`에서 chosen/rejected gradient 약 `-0.1/+0.1` |
| KV cache | 주어진 구조 MHA `8 GiB`, GQA `2 GiB`, GQA sequence 반감 시 `1 GiB`의 **계산값** |
| Retrieval | 손계산 oracle `Recall@2=0.5`, `MRR@2=0.5`, `NDCG@2≈0.52129603`; cross-tenant 결과 0 |
| Evaluation | baseline `6/12`, candidate `8/12`, 개선 4·회귀 2, paired delta `1/6` |

2026-10-04 실제 확인: Windows의 CPython **3.12.14**, `--lab all` 6개 PASS, `unittest` **50개 PASS**. 실행 시 API·GPU·추가 package를 사용하지 않았다. seed `20261004`, 2,000회 bootstrap에서 row CI는 `[-0.25, 0.5]`, family CI는 약 `[-0.33333333, 0.66666667]`로 측정됐다. 이 실행 기록은 Python 3.10 전체 호환성 테스트나 제품 stack 검증을 의미하지 않는다.

## 제출물과 다음 단계

1. 실행 명령·Python 버전·git revision·JSON 결과를 보관한다. artifact 저장 위치와 민감정보 제외 규칙은 [트랙 README](../README.md)를 따른다.
2. 최소 한 negative control을 먼저 예측하고, 코드 변경 전/후 결과가 왜 달라지는지 수식 또는 상태 흐름으로 설명한다. 테스트를 지워 PASS를 만들지 않는다.
3. 입력 크기나 fixture를 확장할 때 기대값을 먼저 만든다. 모델을 추가하기 전 손계산 oracle과 baseline이 보존되는지 확인한다.
4. GPU/model/API 확장은 별도 예산·라이선스·데이터 접근 허가·고정 revision을 기록한 뒤 학습자가 수행한다. 이 코드가 자동으로 설치·다운로드·학습·외부 전송을 시작하지 않는다.
5. "toy mechanism 확인", "bounded reproduction", "논문 전체 결과 재현"을 구분해서 보고하고, 실제 실행하지 않은 항목을 PASS로 기록하지 않는다.
