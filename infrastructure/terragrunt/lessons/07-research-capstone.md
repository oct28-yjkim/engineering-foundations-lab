# 07. 고정 소스 연구와 2주 미니 캡스톤

[과정](../README.md) · [소스 지도](../source-reading.md) · [평가표](../assessment.md)

<a id="tg13"></a>
## TG13 — “소스를 읽었다”를 반증 가능한 주장으로 바꾸기

Terragrunt `v1.1.6`의 commit `be24121b42597ca0ba9b311e76961927b91a5b30`을 기준으로 source reading을 수행합니다. 최신 main의 구현을 과거 release 설명에 섞지 않습니다. module cache의 버전, engine subprocess, provider 동작은 Terragrunt repository 하나로 모두 증명할 수 없습니다.

### 연구 질문 하나 선택

| 가설 | 작은 반증 실험 | 필요한 소스 경계 |
| --- | --- | --- |
| deep merge는 모든 HCL block에 동일하다 | remote_state와 inputs의 결과 차이 | config/include와 merge test |
| upstream plan이 있으면 consumer는 미래 output을 본다 | applied v1과 planned v2를 분리 | dependency output 조회·mock 선택 |
| failed unit이 있으면 어떤 unit도 성공 상태를 남기지 않는다 | diamond+독립 branch 원장 | queue status·runner 실패 경로 |
| source가 같으면 같은 unit이다 | 다른 inputs/backend/engine | source 준비·unit 옵션·state identity |
| Git diff path만 알면 영향 범위가 완전하다 | shared file·rename·external dependency | discovery·read tracking·filter |

각 주장은 5개 이상의 관련 symbol, 2개의 자료구조, 정상 경로와 오류 경로를 연결합니다. 소스 위치를 많이 나열하는 대신 `관찰 → 가설 → 분기 조건 → 자료구조 변화 → 테스트 기대값`을 한 줄씩 적습니다. 함수가 존재한다는 사실과 실제 호출됐다는 증거를 구별합니다.

실제 Go 테스트 확장은 별도 checkout에서 필요한 패키지·fixture만 선택합니다. upstream 전체 integration suite는 cloud credential·외부 실행을 요구할 수 있으므로 무작정 실행하지 않습니다. 기존 unit test의 정상 조건 하나를 바꿔 실패시키고, 최소 수정 후 다시 통과하는 회귀 테스트를 제출합니다. 소스만 읽었으면 `SOURCE-READ`, 실행했으면 해당 package·명령·결과를 추가합니다.

### 논문과의 연결

[Build Systems à la Carte, ICFP 2018](https://www.microsoft.com/en-us/research/publication/build-systems-la-carte/)에서 실행 순서를 정하는 scheduling과 재실행 필요성을 정하는 rebuilding을 분리해 읽습니다. 이 분리는 Terragrunt의 queue와 change selection을 비교하는 연구 렌즈이며 Terragrunt가 논문 모델을 그대로 구현했다는 근거는 아닙니다.

학습자 과제는 입력 파일·unit output을 순수 값으로 둔 모형과, 시간에 따라 외부 상태가 바뀌는 provider-backed 실행을 비교하는 것입니다. “입력 hash가 같으면 실행을 건너뛴다”는 정책이 외부 drift·권한 변경·provider 변경을 놓치는 반례를 만듭니다. 논문의 correctness 조건 중 어떤 가정이 인프라 오케스트레이션에서 깨지는지 세 가지 적습니다.

**구술:** scheduling 정합성이 change-selection 완전성을 증명하는가? cache를 맞게 사용했지만 오래된 output을 소비할 수 있는가? tool의 오류 반환과 운영 시스템의 일관성 사이를 누가 책임지는가?

<a id="tg14"></a>
## TG14 — 2주 미니 연구: 검토 가능한 두 단계 변경

목표는 새 cloud 플랫폼 구축이 아니라 기존 [local fixture](../labs/README.md)와 앞선 실험을 재사용하여 작은 변경 하나의 correctness를 검증하는 것입니다. unit은 foundation/application 두 개, 선택 independent audit 한 개까지로 제한합니다. cloud provider·remote backend·멀티 계정은 이 2주 범위에 포함하지 않습니다.

### 1주차: 계약과 baseline

1. unit 경로·별도 local state·engine 버전·source·입력·output schema를 고정합니다. [공통 CPU 모형](../../shared/labs/README.md)의 그래프/영향 분석과 실제 CLI 결과를 별도로 기록합니다.
2. fixture의 정상 흐름을 재현합니다. 미적용 producer의 mock plan은 구성 확인으로만 분류하고, producer 실제 output을 얻은 뒤 consumer plan을 새로 만듭니다.
3. 변경 하나를 선택합니다. 예: foundation output 계약의 additive 필드 추가와 application 소비. 기대 출력은 literal ledger나 독립 구현으로 먼저 정의합니다.

### 2주차: 실패 두 개와 복구

- 실패 A: consumer가 필요한 실제 upstream output 없이 실행될 상황을 준비합니다. mock apply 또는 거짓 output으로 조용히 진행하지 않고 중단되는지 확인합니다.
- 실패 B: 공유 설정 변화의 consumer 누락 또는 미승인 unit 초과 포함을 만듭니다. exact set oracle이 잘못된 선택을 잡아야 합니다.
- 실패마다 “어떤 state/효과가 이미 남았는가”를 기록하고 새 관측·새 plan·승인으로 복구합니다. 기존 state를 지워 새 성공처럼 보이게 만들지 않습니다.
- 마지막에는 unit별 기대 output과 graph/identity를 대조하고, 정상 상태에서 새로운 plan이 예상대로 무변경인지 확인합니다. 무변경 code 하나는 앞의 output 검산을 대체하지 않습니다.

### 완료 산출물

환경 manifest, source·plan 식별자, 선택 집합 oracle, 두 실패 기록, 단위별 상태/효과 원장, 복구 결과, 소스 근거, 남은 미검증 범위를 제출합니다. 동료가 임의 unit 하나를 골라 입력→의존성→계획→승인→결과까지 추적할 수 있어야 합니다.

[평가표](../assessment.md)의 80점·영역별 15점·필수 gate 조건을 만족해야 합니다. actual CLI가 없으면 OFFLINE 결과와 LOCAL 설계만 제출하며 LOCAL 완료로 선언하지 않습니다. 더 큰 조직·정책·복구·데이터 플랫폼 통합은 별도 [8주 인프라 캡스톤](../../../capstones/reproducible-infrastructure.md)으로 이어갑니다.
