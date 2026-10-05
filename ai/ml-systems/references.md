# 참고 자료와 독자 설계의 경계

[시작](README.md) · [커리큘럼](curriculum.md)

확인일: **2026-10-05**. 아래 공개 원문을 직접 확인했으며 특정 강의의 전체 자료·동영상·과제 풀이를 모두 검토했다고 주장하지 않습니다. 읽기 자료의 주장을 그대로 제품 선택 규칙으로 만들지 말고 우리 환경의 가정과 반례를 추가합니다.

## Stanford CS329S: 참고한 공개판

[공식 홈](https://stanford-cs329s.github.io/)은 운영 가능한 ML 시스템과 설계 trade-off를 다룹니다. 문의처가 `cs329s-win2022`이고 [syllabus](https://stanford-cs329s.github.io/syllabus.html)의 이전 강의 링크가 [2021판](https://stanford-cs329s.github.io/2021/syllabus.html)으로 연결되므로 여기서는 **Winter 2022 공개판**으로 식별합니다. 최신 학기 syllabus라는 뜻이 아닙니다.

아래 왼쪽은 해당 syllabus에서 확인한 주제, 오른쪽은 **이 저장소가 독자적으로 만든 학습 설계**입니다. 원 강의의 과제·정답·평가 배점은 복제하지 않으며 Stanford/강사진의 승인·제휴·수료 인증을 의미하지 않습니다. 원 강의는 framework 경험을 포함한 ML 배경을 전제하지만, 우리 로컬 LAB은 기본 ML·Python 지식으로 진입하도록 축소했습니다.

| 공개 syllabus의 참고 주제 | 우리 설계: SYS 모듈·추가 증거 |
| --- | --- |
| 업무 적용·데이터 시스템 | M01의 비ML baseline·요구사항·중지 조건 |
| 학습 데이터 | M02의 event/available-time 독립 fixture·label maturity |
| 특징 설계 | M03의 버전·freshness·schema negative test |
| 모델 선택·오프라인 평가 | M04의 coverage·slice·calibration 설계 |
| 배포 | M05의 짧은 loopback HTTP 계약 검사 |
| 장애 진단·관측 | M06의 로컬 quality gate·복구 재검증 |
| 분포 변화·지속 학습 | M07의 drift/quality 분리와 조치 선택 |
| 플랫폼·사업 가치·공정성/보안 | M08의 비용·책임·위험 검토 캡스톤 |

기본 코드가 강의의 Ray Serve·실험 추적·모니터링 제품 튜토리얼을 실행하거나, 실제 feature store·클라우드 플랫폼을 구축하는 것은 아닙니다. 공개 강의자료 링크의 접근 가능성·도구 버전은 달라질 수 있습니다.

## R01 · Hidden Technical Debt in Machine Learning Systems

D. Sculley, Gary Holt, Daniel Golovin, Eugene Davydov, Todd Phillips, Dietmar Ebner, Vinay Chaudhary, Michael Young, Jean-François Crespo, Dan Dennison, **2015**, *NIPS*, 2503–2511. [학회 원문](https://papers.neurips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems.pdf) · [저자 기관 서지](https://research.google/pubs/hidden-technical-debt-in-machine-learning-systems/)

- **확인·읽을 구간**: §2 경계/결합, §3 데이터 의존성, §4 feedback, §5–7 시스템·설정·외부 변화.
- **핵심**: 학습 코드의 정확성만으로 장기 유지보수를 설명할 수 없으며 데이터·소비자·설정의 결합이 별도 위험을 만듭니다.
- **우리 과제**: 모델·feature·label·사용처의 의존성 그림과 owner를 작성하고 한 upstream 변경의 영향·원복 범위를 추적합니다.
- **한계**: 새 알고리즘이나 보편적인 정량 위험 점수가 아닙니다. 모든 조직이 같은 구조를 갖는다는 주장이나 특정 제품 도입의 근거로 사용하지 않습니다.

## R02 · The ML Test Score

Eric Breck, Shanqing Cai, Eric Nielsen, Michael Salib, D. Sculley, **The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction**, **2017**, *IEEE Big Data*. [공식 원문](https://storage.googleapis.com/gweb-research2023-media/pubtools/4156.pdf) · [저자 기관 서지](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/)

- **확인·읽을 구간**: §II data/feature, §III model, §IV infrastructure, §V monitoring; 특히 Data 1/7, Model 2/5/6, Infra 6/7, Monitor 3/7. §VI는 점수 산정 방식입니다.
- **핵심**: 테스트와 관측을 데이터·모델·인프라·모니터링으로 나눈 28개 점검 항목을 제안합니다. 원문의 총점은 네 영역 점수의 합이 아니라 **영역별 점수 중 최솟값**입니다.
- **우리 과제**: 선택한 항목마다 자동/수동/미구현과 근거 파일·실행 기록을 남깁니다. schema·parity·rollback 증거를 평가합니다.
- **한계**: 일부 toy 검사 통과를 원문 전체 통과나 production readiness 인증으로 바꾸지 않습니다. 체크리스트는 실제 트래픽·보안·조직 대응·피해 검증을 대체하지 않습니다.

## R03 · Rules of Machine Learning

Martin Zinkevich, **Rules of Machine Learning: Best Practices for ML Engineering**, Google 공식 엔지니어링 가이드. [공식 문서](https://developers.google.com/machine-learning/guides/rules-of-ml). 확인 당시 페이지의 수정일 표시는 **2025-08-25 UTC**이며 이것을 최초 발표 연도로 해석하지 않습니다. 학회 논문이 아닌 실무 가이드입니다.

- **확인·읽을 구간**: #1/#4의 단순 출발, #5 독립 infrastructure test, #8–10 freshness/배포 전 검사/침묵하는 실패, #29–37의 training-serving 차이.
- **핵심**: 간단한 기준 모델과 견고한 데이터·서빙 경로를 먼저 검증하고, 학습 목적과 사용자 결과를 구별합니다.
- **우리 과제**: ML을 쓰지 않는 대안, stale data 탐지, 동일 입력의 training/serving 출력 대조, version 계약 위반 fixture를 연결합니다.
- **한계**: 특정 조직에서 축적된 경험입니다. 보편적 표본 수·latency threshold·architecture 정답으로 적용하지 않으며, 오래된 제품 예시와 현재 도구 지원을 구별합니다.

## 읽기에서 실험으로 넘어갈 때

원문 내용을 길게 옮기는 대신 다음 다섯 줄을 작성합니다: `검증할 주장 / 성립 가정 / 독립 예상값 / 반례 / 우리 환경의 선택`. 기본 제공 여부는 [LAB 안내](labs/README.md), 실행 여부는 [검증 기록](validation.md)을 따릅니다. 설계 문서를 썼다는 사실과 외부 플랫폼에서 동작을 검증했다는 사실은 다릅니다.
