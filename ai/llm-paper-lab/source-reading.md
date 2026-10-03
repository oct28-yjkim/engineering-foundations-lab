# 논문에서 실제 소스와 테스트로 이동하기

[논문 목록](papers.md) · [실험 계약](reproducibility.md) · [평가](assessment.md)

논문의 식과 현재 library의 구현은 자동으로 같은 것이 아닙니다. 저자 공개 코드의 논문 당시 버전, 현재 유지보수 버전, 실제 설치 runtime, 이 저장소의 CPU 모형을 각각 구분합니다. 아래 공식/저자 repository는 2026-10-04 존재와 README를 확인한 **탐색 출발점**이며 고정된 실험 revision이 아닙니다.

## 읽기 경로

| 논문·대상 | 출발점 | 연결할 질문 |
| --- | --- | --- |
| P04 LoRA | [microsoft/LoRA](https://github.com/microsoft/LoRA), `loralib`와 예제 | frozen base·A/B 초기화·scale·merge·train/eval 전환이 어떤 함수에 있는가? |
| P07 DPO | [저자 reference implementation](https://github.com/eric-mitchell/direct-preference-optimization), `trainers.py`·`preference_datasets.py` | chosen/rejected token mask·sequence log-prob·reference·beta를 어디서 결합하는가? |
| P08 FlashAttention | [Dao-AILab/flash-attention](https://github.com/Dao-AILab/flash-attention), reference 비교 테스트 | 선택 backend·dtype·causal mask에서 output과 gradient 허용 오차를 어떻게 검사하는가? |
| P09 PagedAttention | [vllm-project/vllm](https://github.com/vllm-project/vllm), 선택 release의 기여/설계 문서 | scheduler·KV 관리·backend에서 논문의 개념과 현재 구현이 어떻게 달라졌는가? |
| P11 DPR | [facebookresearch/DPR](https://github.com/facebookresearch/DPR), dataset/encoder/retrieval 경로 | negative 구성·dual encoder·index·정답 포함 여부와 실제 QA 정답은 어디서 갈리는가? |

README의 설치/전체 학습 명령을 먼저 실행하지 않습니다. 오래된 연구 코드의 dependency와 현재 runtime은 충돌할 수 있습니다. 실제 버전에 맞는 환경을 따로 준비하고 모델·데이터 다운로드, 컴파일, GPU 자원 사용은 [선택 확장](environment.md)으로 취급합니다. 위 저장소 전체를 이 교재 작성 중 빌드·학습·benchmark 실행한 것은 아닙니다.

## Revision 고정

사용자가 별도로 확보한 source checkout에서 다음 읽기 전용 정보를 기록합니다. 아직 clone하지 않은 경로에 명령을 실행하거나 현재 lab repository의 SHA를 upstream SHA로 대신 쓰지 않습니다.

```text
git rev-parse HEAD
git status --short
git describe --tags --always
```

그 SHA를 포함하는 GitHub `blob/<commit>/<path>` permalink와 함수/클래스 이름을 보고서에 넣습니다. line 번호는 보조 자료이며 코드 이동에 취약합니다. 설치 package version, wheel/build hash, model/tokenizer/dataset revision은 별도입니다. source-only checkout을 runtime과 동일하다고 주장하려면 매핑 근거가 필요합니다.

## 한 경계의 연구 노트

1. 입력 fixture 하나와 반증할 주장 하나를 고릅니다. 예: “prompt token의 log probability도 preference loss에 포함된다.”
2. 입력 구성 → mask/변환 → 핵심 계산 → 결과/실패의 네 경계를 추적합니다. 각 지점에 shape·dtype·상태·호출자를 적습니다.
3. 관련 upstream test의 입력·assertion·mock·미검증 범위를 읽습니다. 테스트 이름을 제품 전체 보장으로 해석하지 않습니다.
4. 이 저장소의 작은 모형과 대응시켜 무엇이 빠져 있는지 씁니다. 예: CPU DPO scalar에는 tokenizer, token mask, model forward, optimizer가 없습니다.
5. 선택한 독립 개발 환경에서 표적 test 하나를 실행하거나, 실행할 수 없으면 필요한 dependency와 정확한 실행 계획을 남깁니다. 미실행은 실패가 아니라 상태 표시이며 실행 gate를 대신하지 않습니다.
6. 결함 변형에서 oracle이 실패하고 정상/수정 구현에서 통과하는지 비교합니다. benchmark 수치 변화와 correctness 변화는 나눕니다.

M13 제출 노트는 최소 5개 구현 지점을 연결해 실제 관련된 호출/데이터 경계 하나를 끝까지 설명합니다. 파일 경로 수를 나열하는 것으로 이 추적을 대신하지 않으며 여러 지점이 같은 파일에 있어도 됩니다. 소수 테스트로 전체 시스템의 안전·품질·성능을 보장하지 않습니다. upstream issue/PR 생성이나 원격 변경은 이 읽기 과제의 필수 단계가 아닙니다.
