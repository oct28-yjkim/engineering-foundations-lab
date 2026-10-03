# 04. Stack 구성과 변경 영향 범위

[과정](../README.md) · [공통 CPU 모형](../../shared/labs/README.md)

<a id="tg07"></a>
## TG07 — 생성 규칙과 생성된 unit은 다른 검토 대상이다

implicit stack은 발견되는 unit 집합이며 explicit stack은 `terragrunt.stack.hcl`에 unit/stack 생성 규칙을 선언합니다. 재사용 module source, 재사용 unit 설정, 여러 unit을 생성하는 stack을 같은 abstraction으로 취급하지 않습니다. 생성 후에는 실제 unit 경로·inputs·dependencies·backend identity가 실행의 기준입니다. [Explicit Stacks](https://docs.terragrunt.com/features/stacks/explicit/)

### 설계·실험 과제

1. dev/prod 두 환경에 network/app 두 unit씩 있는 총 네 unit을 손으로 작성한 구성과 생성 기반 구성으로 표현합니다. 기본 제공 fixture를 자동 확장하지 말고 별도 학습자 실습 폴더를 사용합니다.
2. 생성 전 source commit·values·설정 hash, 생성 후 unit 경로·effective inputs·dependency 경로·backend identity를 기록합니다. 네 unit이라는 count뿐 아니라 각 tuple의 정확한 동일성을 검사합니다.
3. 생성 파일을 수동 수정한 뒤 재생성 때 결과가 바뀌는 반례를 만듭니다. generated artifact를 편집할지 원본 catalog를 편집할지 책임 경계를 문서화합니다.
4. stack 내부 unit 이름 또는 path를 바꾸면 backend key와 dependency path가 어떻게 달라지는지 검토합니다. “구조 리팩터링이라 리소스 변경이 없다”는 주장을 plan으로 반증합니다.
5. config 생성, unit 발견, engine 실행을 별도 단계로 관측합니다. 일부 명령의 자동 stack generation 때문에 발견 단계가 항상 파일 시스템 읽기 전용이라고 가정하지 않습니다.

catalog는 플랫폼 팀, live values는 서비스 팀이 소유한다는 단순 모델로 변경 승인을 설계합니다. 팀 간 역할을 나눠도 신뢰하는 source code를 실행하는 권한은 남습니다. source의 tag/branch 대신 immutable commit을 사용하고 생성 후 diff를 검토합니다.

**버전 경계:** 1.1.6의 stable stack 기능만 baseline으로 사용합니다. 최신 문서의 OCI·반복 block·bounded discovery 예시는 별도 실험 상태와 요구 버전을 확인해야 합니다. 학습을 위해 모든 experiment를 한꺼번에 켜지 않습니다.

**통과:** 네 unit의 이름·backend·의존성·inputs가 기대 tuple과 일치하고 prod를 dev key에 연결한 음성 대조군이 실패해야 합니다. 생성 성공은 apply 성공 또는 실행 권한 검증이 아닙니다.

<a id="tg08"></a>
## TG08 — Changed files와 affected units는 같지 않다

`A → B`는 B가 A를 소비한다는 표기입니다. prerequisites 집합은 실행 준비 조건이고 dependents 집합은 변경의 전파 후보입니다. TG04 diamond와 독립 X에서 A의 변경 전파 후보는 A/B/C/D이며 D 실행의 prerequisites는 A/B/C/D입니다. X는 둘 모두에서 제외되어야 합니다.

graph filter에서 target 뒤의 `...`는 dependencies, 앞의 `...`는 dependents 방향입니다. [공식 graph filter](https://docs.terragrunt.com/features/filter/graph/)의 작은 예제와 손으로 계산한 집합을 비교합니다. 아래는 **검토한 synthetic 설정**에서만 쓰는 발견 명령 예입니다. discovery도 HCL 평가·인증·파일 쓰기를 유발할 수 있습니다.

```bash
terragrunt find --filter 'application...'
terragrunt find --filter '...foundation'
```

두 방향의 union이 무조건 안전한 실행 범위는 아닙니다. 영향 분석은 넓게 하되 실행은 승인된 exact unit 집합으로 제한해야 합니다. 현재 디렉터리는 authorization boundary가 아니며 graph traversal이 밖의 dependency를 찾을 수 있습니다. 1.1.6의 bounded discovery는 실험 기능이므로 이 과정은 이를 보안 격리 장치로 의존하지 않습니다.

### 여섯 가지 음성 대조군

| 변경 | 단순 Git path 필터의 위험 | 독립 기대값 |
| --- | --- | --- |
| unit HCL 한 개 | consumer 재검토 누락 | 변경 unit과 필요한 downstream 영향 |
| 공유 root.hcl | root만 선택 또는 모든 환경 무작정 선택 | 실제 include/read 소비자 집합 |
| 외부 YAML/JSON 값 | unit 폴더 밖이라 누락 | 파일→reader mapping에 따른 집합 |
| module source pin | live 파일이 다른 경로 | pin 소비 unit과 계약 영향 |
| unit rename/delete | 현재 tree에 예전 경로가 없음 | 이전/현재 identity와 state 소유권 mapping |
| 경계 밖 dependency | 환경 범위 초과 실행 | 발견 집합에 포함하되 미승인 실행 중단 |

파일→unit 대응은 학습자가 먼저 정하고, 공통 `blast-radius` 모형에는 변경된 unit 집합을 입력하여 graph closure를 검산합니다. 모형이 파일 diff·reader mapping을 구현하거나 실제 Terragrunt Git filter의 parser·worktree·read tracking을 재현하는 것은 아닙니다. 동적 `run_cmd`나 외부 시스템 입력은 파일 diff만으로 추적되지 않을 수 있으므로 누락 가능성을 기록합니다.

**실행 전 gate:** `actual_selected == approved_units`를 exact set으로 검사하고, canonical path·symlink/junction·repo boundary를 별도로 검사합니다. approved set에 모든 prerequisites가 없으면 해당 값이 이미 유효하게 배포됐는지 판단해야 하며 자동으로 경계 밖 apply를 추가하지 않습니다.

**소스 과제:** `internal/filter/filter.go`의 Parse/Evaluate, `internal/discovery/phase_graph.go`, filter 테스트를 연결합니다. 삭제된 unit을 처리하는 이전 revision worktree가 어떤 코드·state를 가리키는지 추가 조사합니다. 이 확장 연구에서 실제 destroy를 실행할 필요는 없습니다.
