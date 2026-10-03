# Observability Engineering

관측의 목표는 대시보드가 많은 상태가 아니라 **사용자가 겪은 문제와 수집 시스템 자체의 한계를 분리해서 설명하는 것**입니다. 첫 트랙인 [Sentry](sentry/README.md)는 앱의 capture부터 오류 분류·trace·저장·검색·알림·복구까지 추적합니다.

## 시작점

- [28주 커리큘럼](sentry/curriculum.md): 14모듈, 원리·실험·내부 추적·운영
- [실제 관측·진단 실습](sentry/operations.md): 오류·trace·release·ingestion 지표, 경쟁 가설과 회복 검증
- [실습 준비와 선택 원리 부록](sentry/labs/local-lab.md): SDK/서버 준비, 검증 범위, 원본 분모와 표본
- [소스 지도](sentry/source-reading.md): 컴포넌트별 snapshot과 실제 runtime의 차이
- [평가](sentry/assessment.md): 오류 정확성·privacy·수집 손실·복구의 필수 관문
- [보안·관측 앱 캡스톤](../capstones/secure-observable-app.md): Supabase 기반 앱의 권한·상태·관측 검증

공통 [실험 방법](../databases/shared/experiment-method.md)과 [보고서 양식](../databases/shared/templates/experiment-report.md)을 재사용합니다. Sentry는 “에러가 있으면 알림이 온다”로만 배우지 않습니다. 이벤트가 없어도 앱에 오류가 없었다고 단정하지 않고, 입력 원장→수집 시도→처리/제외→가시성→사용자 조치의 경계를 분리합니다.

## 다른 트랙과 연결

| 연결 | 함께 검증할 질문 | 피할 오해 |
| --- | --- | --- |
| [Kafka](../streaming/kafka/README.md) | ingestion backlog·유실·중복·재처리가 검색 결과에 어떻게 나타나는가? | SDK flush 성공이면 downstream 처리도 완료 |
| [ClickHouse](../databases/clickhouse/README.md) | 저장·pruning·집계·TTL·조회 비용이 관측에 어떤 편향을 주는가? | 같은 DB 제품이면 임의 lab을 Sentry 내부 저장소로 교체 가능 |
| [Supabase](../platforms/supabase/README.md) | 인증 오류·권한 거절·DB 지연을 어떻게 비밀 없이 구별하는가? | Authorization header나 사용자 본문 전체를 보내야 진단 가능 |

Kafka/ClickHouse 전 과정을 먼저 끝내야 Sentry를 시작할 수 있는 것은 아닙니다. SDK·오류 분석부터 시작하고 내부 pipeline 과제에서 필요한 원리를 보충합니다. hosted 제품의 내부를 직접 관측하지 못했다면 그 부분은 추론/미검증으로 남깁니다. source 공개 여부와 사용·배포 조건도 각 컴포넌트의 실제 라이선스에서 확인합니다.
