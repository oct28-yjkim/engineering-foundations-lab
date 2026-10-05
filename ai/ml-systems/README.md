# ML Systems Design LAB

[AI 학습 경로](../ml-dl-llm-roadmap.md) · [수학 보충](../math-foundations/README.md) · [커리큘럼](curriculum.md)

모델이 예측을 잘하는 것과 그 예측을 업무에서 안전하게 계속 사용하는 것은 다른 문제입니다. 이 트랙은 **문제 정의 → 데이터/특징 계약 → 평가 → 서빙 → 관측 → 진단·복구**를 하나의 수명주기로 다룹니다. 먼저 정상 동작과 그 증거를 확인하고, 잘못된 입력·늦은 데이터·배포 회귀를 일부러 만든 뒤 원인에 맞는 복구를 연습합니다.

Stanford CS329S의 **Winter 2022 공개 자료**를 참고한 독자적 학습 경로입니다. 최신 학기 강의·공식 번역·과제 복제·제휴/인증 과정이 아닙니다. 원전과 참고한 주제, 저장소에서 추가한 설계는 [출처·대응표](references.md)에 분리했습니다. [공식 강의 홈](https://stanford-cs329s.github.io/) · [공개 syllabus](https://stanford-cs329s.github.io/syllabus.html)

## 언제 시작하나요?

[ML 기초 과정](../ml-paper-lab/README.md)의 train/validation/test, logistic probability, loss/metric, baseline을 이해하면 시작할 수 있습니다. **DL·LLM을 모두 마칠 때까지 기다릴 필요가 없습니다.** [수학 보충](../math-foundations/README.md)의 확률·통계·평가 내용을 필요한 모듈과 병행합니다.

독립적인 **8모듈·16주·주 12시간, 192시간** 선택 트랙입니다. 기존 ML→DL→LLM의 64주·768시간 합계는 그대로이며 이 트랙은 그 합계에 포함하지 않습니다. 병행할 때는 주간 학습량을 나누어 일정을 조정합니다. 기간 이수나 toy LAB 통과가 production-ready 인증은 아닙니다.

## 자료와 진행 순서

| 자료 | 무엇을 확인하나요? |
| --- | --- |
| [커리큘럼](curriculum.md) | 8모듈의 선수 조건·설계 질문·실행/수동 과제·통과 증거 |
| [출처와 읽기](references.md) | Stanford 공개판 범위, 시스템 원전 3개, 우리 설계의 경계 |
| [LAB 안내](labs/README.md) | 안전한 실행 방식·관측 필드·각 negative fixture의 예상값 |
| [운영 진단](operations.md) | 정상 계약·주요 지표·실패 주입·원인 분리·복구 확인 |
| [설계 리뷰 양식](templates/design-review.md) | 업무 목표·정보 경계·배포 판단·복구 책임을 한 문제에 적용 |
| [검증 기록](validation.md) | 실제 실행한 항목, 실행 환경, 미검증 범위 |

1. `--plan`으로 어떤 로컬 실험과 실패 주입을 하는지 확인합니다.
2. 요청/특징/모델 버전과 예상 출력, 오류 조건을 먼저 적습니다.
3. `--run`을 명시해 로컬 실험을 실행합니다.
4. 관측만으로 설명할 수 있는 사실과 label 도착을 기다려야 하는 판단을 나눕니다.
5. 같은 정상 요청을 다시 보내 복구를 확인하고, 회귀 테스트와 설계 결정을 기록합니다.

```text
python -B ai/ml-systems/labs/lab.py --plan
python -B ai/ml-systems/labs/lab.py --run
```

명령은 저장소 루트 기준입니다. 기본 동작은 계획 출력이며, 실행은 명시적으로 선택합니다. Python 표준 라이브러리·작은 합성 데이터·고정된 logistic 모델 버전으로 데이터/추론 계약을 검증하며 새 모델을 학습하는 LAB은 아닙니다. GPU·외부 모델 API·Docker·클라우드 계정은 필요 없습니다. 실행 중 loopback HTTP 서비스를 잠깐 시작하고 종료하는 구조이므로 일반적인 외부 endpoint나 운영 시스템에 요청을 보내는 LAB이 아닙니다.

## 실행되는 것과 배워야 할 확장

| 기본 로컬 실행 범위 | 수기/설계 또는 별도 환경 확장 |
| --- | --- |
| 작은 logistic 예측의 로컬 HTTP 서빙과 입력 계약 검사 | 분산 training/serving, 대량 처리량·tail latency benchmark |
| schema·type/dimension·freshness·feature/preprocessing-version 오류의 거부와 정상 복구 | 실제 feature store·stream processor·모델 registry·CI/CD |
| event time/available time을 구분하는 point-in-time fixture | CDC·late event·backfill·삭제 요구를 포함한 실데이터 파이프라인 |
| 합성 label coverage·입력 분포 변화/품질 변화 구분 | 실제 population mix 분석·실사용자 label 수집·장기 A/B·인과 추정·공정성 검증 |
| 제한된 로컬 quality gate·버전 전환/rollback | 다중 replica canary, 트래픽 라우팅, durable registry, 클라우드 rollout |

이 트랙에서 CPU는 **저렴한 로컬 실행 환경**이지 핵심 학습 목표가 아닙니다. 핵심은 데이터가 언제 존재했는지, 어떤 계약으로 예측했는지, 무엇을 관측할 수 있는지, 실패 시 무엇을 되돌려야 하는지입니다. 보안·비용·확장성 주제도 배우지만, 기본 구현이 TLS/IAM·Kubernetes·feature store를 제공하는 것은 아닙니다.

배포 대조에서는 baseline과 후보를 전용 fixture에서 HTTP로 평가하고, 후보가 전체 정확도 기준을 통과해도 특정 slice가 악화되면 quality gate가 거부한 뒤 baseline을 복원·검증합니다. 후보 실행은 격리된 로컬 평가용 주입이며 운영 승격을 뜻하지 않습니다. label 도착 지연과 drift 대조는 별도 합성 fixture입니다. 지연으로 accuracy가 뒤늦게 낮아지는 경우, 입력 분포는 변해도 품질은 유지되는 경우, 같은 입력에서 label 관계가 바뀌어 품질이 나빠지는 경우를 구별합니다.

## 완료 기준

“서버가 200을 반환한다”를 넘어서 **정확한 버전·데이터 시점·동일 feature 계산·품질 표본·복구 상태**를 설명해야 합니다. 최소 하나의 실패에 대해 가설 두 개를 비교하고, 관측 증거로 원인을 좁힌 뒤 복구 전후의 동일 요청을 검증합니다. 배포하지 않기, 단순 규칙을 유지하기, label이 충분할 때까지 판단을 보류하기도 근거가 있으면 올바른 결론입니다.
