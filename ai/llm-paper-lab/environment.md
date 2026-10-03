# 실행 환경과 비용 경계

[시작](README.md) · [실습](labs/README.md) · [실험 계약](reproducibility.md)

기본 경로는 사용자가 선택한 **CPU + GPU/API 선택 확장**입니다. 제공 코드 실행에 모델 계정·키·GPU·Docker·pip 설치가 필요하지 않습니다. 다른 DB 실습의 컨테이너를 시작할 이유도 없습니다.

## CPU 기본 환경

Python 3.10 이상과 이 저장소만 사용합니다. 코드의 합성 fixture와 숫자는 교육용이며 논문 원본 dataset이 아닙니다. 출력은 표준 출력의 JSON입니다. 파일 기록을 원할 때만 비밀이 없는지 검토한 뒤 사용자가 별도로 보관합니다.

```text
python --version
python ai/llm-paper-lab/labs/lab.py --lab all
python -B -m unittest discover -s ai/llm-paper-lab/labs -p test_lab.py -v
```

PowerShell에서 공백이 포함된 실행 파일 경로를 쓸 때는 `& "C:\path\to\python.exe"` 형태로 `python`을 대체합니다. 특정 개발자의 절대 경로를 저장소 공용 명령에 넣지 않습니다. `python --version`이 Store를 열거나 실패하면 실제 설치/실행 경로를 먼저 확인합니다.

`-B`는 단위 테스트의 bytecode cache 작성을 막습니다. 실험 코드는 별도 네트워크 요청·모델 다운로드·외부 명령 실행을 하지 않습니다. 출력 수치가 다른 경우 코드/런타임/입력 차이를 확인하고 기대값을 결과에 맞춰 고치지 않습니다. 검증한 Python 버전과 테스트 결과는 [검증 기록](validation.md)에 남깁니다.

## 작은 모델과 GPU 선택 확장

GPU가 없어도 논문 읽기와 CPU 모형은 완료할 수 있습니다. 실제 작은 모델 실험은 별도 디렉터리·가상 환경에서 구현합니다. 초기에는 단일 장치·작은 입력으로 correctness를 확인한 뒤 규모를 늘립니다. 이 저장소는 PyTorch/CUDA/transformers/vLLM/bitsandbytes의 조합을 설치하거나 호환성을 보장하지 않습니다.

실행 전 manifest에 다음을 고정합니다.

- OS, CPU/RAM, GPU 모델·개수·VRAM, driver, CUDA와 framework의 정확 버전.
- 모델/토크나이저의 repository·revision·dtype·context length·attention backend. tokenizer나 chat template 변경도 실험 변수입니다.
- dataset revision·hash·split·전처리·max length·packing과 special token/loss mask.
- batch/microbatch/gradient accumulation, optimizer·scheduler, seed, step/token 예산, precision, checkpoint 정책.
- 다운로드 용량, 디스크·RAM/VRAM·시간·비용 상한, OOM·오류율 중단 조건, 종료·보존 범위.

가중치 메모리만으로 VRAM 요구량을 계산하지 않습니다. optimizer state·gradient·activation·KV cache·임시 buffer·allocator 여유가 추가됩니다. CPU `kv-cache`는 그중 KV tensor의 이상적 bytes 모형일 뿐 GPU 할당량이나 처리량을 측정하지 않습니다.

모델·dataset의 접근 조건과 사용/재배포 조건은 다운로드 전에 해당 원본에서 확인합니다. gated/private 자료를 우회하지 않습니다. 다운로드한 remote Python 코드나 repository 설치 스크립트를 자동 실행하지 말고 별도 검토합니다. 실제 고객 데이터와 credentials를 학습 fixture로 사용하지 않습니다.

## 외부 모델 API 선택 확장

API 호출 코드는 기본 제공되지 않습니다. 원하는 제공자·모델·endpoint를 사용자가 정한 뒤 별도 구현합니다. CPU 테스트 성공은 API 연결 확인이 아닙니다.

1. 합성 데이터 또는 사용 권한이 있는 비민감 평가 항목만 고릅니다. 보존·학습 사용·리전·공유 설정은 선택 서비스의 실제 계약을 확인합니다.
2. 정확한 모델 식별자와 호출 날짜, decoding 설정, 응답 format, context 한도, retry/timeout을 기록합니다. 고정 모델 revision을 알 수 없으면 unknown으로 표시합니다.
3. 요청 수·동시성·입출력 token·최대 응답 길이·총비용·실패 시 중단 한도를 사전에 정합니다. 가격은 실행일의 공식 요금으로 계산하고 cache/재시도/추가 도구 비용을 빠뜨리지 않습니다.
4. 기본 키를 코드에 넣지 않습니다. secret manager 또는 환경 변수를 사용하고 header·쿠키·전체 환경 변수·원본 prompt를 debug 로그에 출력하지 않습니다.
5. 같은 항목을 paired 비교하되 실행 순서·시간 변화·cache를 통제합니다. rate limit·실패·빈 응답·거절도 분모와 결과에 남깁니다. 성공한 요청만으로 품질을 계산하지 않습니다.

이 문서와 기본 테스트는 비용 발생, 클라우드 생성, 외부 tool 실행, 이메일 발송, 원격 변경을 승인하거나 자동 수행하지 않습니다. 에이전트 tool은 처음에 순수 함수/mock으로 제한하고 실제 부작용에는 별도 권한·확인·중복 방지가 필요합니다.

## 결과와 Git

원시 결과는 필요하면 저장소의 무시된 `lab-workspaces/` 아래 별도 run 디렉터리에 보관합니다. 다른 실습의 데이터나 volume을 지우지 않습니다. 공유할 최소 fixture·비밀 제거 manifest·테스트·보고서만 검토해 커밋합니다. `gitignore`는 이미 추적 중인 파일이나 외부 로그의 비밀을 제거해 주지 않습니다.
