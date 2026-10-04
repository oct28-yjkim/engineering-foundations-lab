# 관측과 제품 분석 학습

이 경로는 **앱에서 일어난 일과 수집·분석 시스템이 보여 주는 결과의 차이**를 설명하는 학습입니다. [Sentry](sentry/README.md)는 오류·trace·사용자 영향을, [Amplitude](amplitude/README.md)는 행동 이벤트·사용자 식별·전환·유지를 다룹니다. 같은 SDK 수집 문제가 있어도 목적과 지표는 다르며 Amplitude를 서버/APM 모니터링 제품으로 취급하지 않습니다.

## Sentry 시작점

- [28주 커리큘럼](sentry/curriculum.md): 14모듈, 원리·실험·내부 추적·운영
- [실제 관측·진단 실습](sentry/operations.md): 오류·trace·release·ingestion 지표, 경쟁 가설과 회복 검증
- [실습 준비와 선택 원리 부록](sentry/labs/local-lab.md): SDK/서버 준비, 검증 범위, 원본 분모와 표본
- [소스 지도](sentry/source-reading.md): 컴포넌트별 snapshot과 실제 runtime의 차이
- [평가](sentry/assessment.md): 오류 정확성·privacy·수집 손실·복구의 필수 관문
- [보안·관측 앱 캡스톤](../capstones/secure-observable-app.md): Supabase 기반 앱의 권한·상태·관측 검증

공통 [실험 방법](../databases/shared/experiment-method.md)과 [보고서 양식](../databases/shared/templates/experiment-report.md)을 재사용합니다. Sentry는 “에러가 있으면 알림이 온다”로만 배우지 않습니다. 이벤트가 없어도 앱에 오류가 없었다고 단정하지 않고, 입력 원장→수집 시도→처리/제외→가시성→사용자 조치의 경계를 분리합니다.

## Amplitude 시작점

회사의 웹·모바일 SDK 경로에 맞춰 **정상 행동 → SDK 전송 → 수집 확인 → identity와 차트 검산 → 누락·중복·수치 불일치의 진단·복구**를 기본으로 합니다. CPU 원리 모형이나 HTTP 직접 전송이 SDK의 lifecycle·queue·storage 검증을 대신하지 않습니다.

- [기본 LAB](amplitude/labs/README.md): 고정 버전 웹 SDK 앱과 단계별 사건, 모바일 수동 실습
- [환경 준비](amplitude/environment.md): 허가된 합성 데이터 테스트 프로젝트·region·버전·관측 범위
- [운영 지침](amplitude/operations.md): 수집 오류·identity·funnel/retention·품질·확장 제약
- [28주 커리큘럼](amplitude/curriculum.md): 14모듈·7강, 공개 SDK 내부 동작과 분석 계약 연구
- [소스 지도](amplitude/source-reading.md) · [평가](amplitude/assessment.md) · [실제 검증 범위](amplitude/labs/validation.md)

실행 앱·절차를 제공했다는 것과 실제 SaaS 검증을 마쳤다는 것은 다릅니다. 회사 계정·키·사용자 데이터에는 접근하지 않으며, native 모바일 앱과 Amplitude 서버는 포함하지 않습니다. 웹 LAB도 승인한 테스트 프로젝트를 사용자가 명시적으로 선택하기 전에는 SDK를 로드하지 않습니다.

## 다른 트랙과 연결

| 연결 | 함께 검증할 질문 | 피할 오해 |
| --- | --- | --- |
| [Kafka](../streaming/kafka/README.md) | ingestion backlog·유실·중복·재처리가 검색 결과에 어떻게 나타나는가? | SDK flush 성공이면 downstream 처리도 완료 |
| [ClickHouse](../databases/clickhouse/README.md) | 저장·pruning·집계·TTL·조회 비용이 관측에 어떤 편향을 주는가? | 같은 DB 제품이면 임의 lab을 Sentry 내부 저장소로 교체 가능 |
| [Supabase](../platforms/supabase/README.md) | 인증 오류·권한 거절·DB 지연을 어떻게 비밀 없이 구별하는가? | Authorization header나 사용자 본문 전체를 보내야 진단 가능 |

Kafka/ClickHouse 전 과정을 먼저 끝내야 Sentry를 시작할 수 있는 것은 아닙니다. SDK·오류 분석부터 시작하고 내부 pipeline 과제에서 필요한 원리를 보충합니다. hosted 제품의 내부를 직접 관측하지 못했다면 그 부분은 추론/미검증으로 남깁니다. source 공개 여부와 사용·배포 조건도 각 컴포넌트의 실제 라이선스에서 확인합니다.
