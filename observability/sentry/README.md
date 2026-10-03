# Sentry: Zero to Hero, 텔레메트리 계약에서 운영 증명까지

목표는 SDK를 설치하는 사람이 아니라 **어떤 신호가 어떤 경로에서 사라지거나 변형되었는지 설명하고, 오류 탐지·개인정보·비용·복구를 함께 설계하는 엔지니어**입니다. 14개 모듈, 명목상 28주·주 12시간입니다. 기간보다 가설, 반례, 원시 증거, 소스 추적, 복구 검증으로 진도를 결정합니다.

Sentry를 하나의 버전 번호로 고정하지 않습니다. SDK·runtime·bundler·OpenTelemetry 설정, Sentry/self-hosted·Relay·Snuba·Symbolicator, Kafka·ClickHouse·PostgreSQL 및 이미지 digest가 각각 다를 수 있습니다. 실험 시점의 버전과 기능 설정을 manifest에 기록하고 같은 revision의 구현을 읽습니다. SaaS의 배포 revision을 알 수 없다면 관측 날짜·SDK 버전·프로젝트 설정·API 응답 계약을 기록하고 서버 내부 구현은 확인 불가로 남깁니다. [소스 읽기와 버전 정책](source-reading.md)

## 읽는 순서

1. 필요하면 [공통 기초](../../databases/shared/foundations.md)에서 OS·확률·분산 시스템을 복습하고 [실험 방법](../../databases/shared/experiment-method.md)을 적용합니다. HTTP와 JavaScript/runtime의 비동기 실행은 별도로 보충할 선수 지식입니다.
2. [28주 커리큘럼](curriculum.md)과 [로컬 실습 범위](labs/local-lab.md)를 확인합니다.
3. [텔레메트리 계약과 의미](lessons/01-telemetry-contracts.md): S01–S02.
4. [SDK·Envelope·수집 제어](lessons/02-sdk-ingestion.md): S03–S04.
5. [그룹화·심볼리케이션·릴리스](lessons/03-grouping-releases.md): S05–S06.
6. [추적·비동기 문맥·샘플링](lessons/04-tracing-sampling.md): S07–S08.
7. [수집 파이프라인·저장 일관성](lessons/05-data-pipeline.md): S09–S10.
8. [개인정보·보안·운영·복구](lessons/06-operations-privacy.md): S11–S12.
9. [소스 연구·최소 캡스톤](lessons/07-research-capstone.md): S13–S14.
10. [소스 지도](source-reading.md)와 [평가·구술 리뷰](assessment.md)로 증거를 정리합니다.

28주 과정 뒤에는 [Supabase·Sentry 보안·관측 앱 캡스톤](../../capstones/secure-observable-app.md)으로 확장할 수 있습니다. 이는 별도 8주 통합 프로젝트이며 S14의 작은 단면과 구별합니다.

Kafka나 ClickHouse 전체 과정을 먼저 끝낼 필요는 없습니다. S09에서 필요한 partition·consumer offset·배치·컬럼 저장 개념부터 학습하고, 필요할 때 [Kafka 과정](../../streaming/kafka/README.md)과 [ClickHouse 과정](../../databases/clickhouse/README.md)을 참조합니다.

## 제공되는 것과 직접 구현할 것

| 표시 | 범위 | 제공 상태 |
| --- | --- | --- |
| `OFFLINE` | 합성 fixture, 계약 검토, 확률 계산 | 실습 안내와 [샘플링 oracle](labs/sampling-oracle.mjs) 제공; 다른 본문 실험은 요구사항에 따라 직접 구현 |
| `SDK-LAB` | 고정 버전 SDK + 메모리 transport/loopback 수신기, 비동기·Envelope 검사 | harness 구현 과제; 완성 애플리케이션 미제공 |
| `PROJECT-LAB` | 사용 권한이 있는 별도 시험 프로젝트의 그룹화·조회·알림 검증 | 계정·DSN·토큰·외부 송신·업로드 자동 설정 없음 |
| `SELF-HOST-DESIGN` | 격리 self-hosted의 파이프라인·장애·백업·업그레이드 | 설계와 검증 기준 제공; 전체 스택 Compose 및 HA 환경 미제공 |

먼저 오프라인 oracle을 실행하고, SDK 실험도 외부 송신이 없는 transport부터 구현합니다. 실제 전송이 필요한 과제는 합성 데이터만 사용하고 대상·보존·비용·권한을 확인한 뒤 수행합니다. README를 읽는 것만으로 계정 생성이나 서비스 전송이 이루어지지 않습니다.

## 반드시 구별할 경계

- `event_id`, error event, issue, envelope, trace, span은 같은 단위가 아닙니다. issue 수로 오류 발생 횟수를 계산하지 않습니다.
- SDK capture 호출, transport 수락, Relay의 HTTP 응답, 저장, 검색 가능, issue 갱신, 알림 전달은 별도 상태입니다.
- 에러, trace/span, 로그, Replay, application metric은 서로 다른 필터·샘플링·개인정보 경로를 가질 수 있습니다.
- client-side head sampling으로 보내지 않은 데이터는 서버에서 복원할 수 없습니다. 저장된 trace만으로 모집단 SLO를 계산하려면 포함 확률과 결측 가정을 먼저 검증해야 합니다.
- `beforeSend` 하나로 모든 첨부파일·프로파일·Replay·로그의 비밀정보가 제거된다고 가정하지 않습니다.
- self-hosted는 SaaS 기능·규모·지원·보안 운영이 동일하다는 뜻이 아닙니다. 공식 배포의 기능 차이와 선택한 revision을 확인합니다.
- 일부 설정을 내보내는 JSON 백업은 전체 이력·파일·분산 저장소의 복구 증거가 아닙니다.

각 모듈의 수량·시간 목표는 학습용 입력 또는 검증 기준이며, 실제 시스템에서 측정한 성능이나 보장 수치가 아닙니다. 설계만 한 과제는 실행 미검증으로 표시합니다. [공식 self-hosted 안내](https://develop.sentry.dev/self-hosted/)
