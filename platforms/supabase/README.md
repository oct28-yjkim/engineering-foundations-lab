# Supabase Engineering Lab

Supabase를 빠른 CRUD 도구로만 다루지 않고 **PostgreSQL 권한·트랜잭션 위에 Auth, API, 실시간 전달, 객체 저장, 실행 환경이 연결되는 시스템**으로 학습합니다. 목표는 기능 사용량이 아니라, 두 tenant 사이의 격리를 반증하고 장애 후 업무 상태를 복구하며 구현 근거로 설계를 설명하는 능력입니다. 과정을 마쳤다는 사실만으로 전문가 역량이나 운영 안전성을 보증하지 않습니다.

## 과정과 시작점

14개 모듈 × 2주, 주 12시간의 **명목 28주·336시간**입니다. 처음에는 [공통 기반](../../databases/shared/foundations.md)의 SQL·OS·분산 시스템을 복습합니다. PostgreSQL 전체 과정을 먼저 끝낼 필요는 없지만 JOIN, NULL, index, MVCC, role/grant, HTTP, 비동기 JavaScript, 기본 테스트 작성은 필요합니다. HTTP·JavaScript는 별도로 보충할 선수 지식이며, 트랜잭션·권한 심화는 [PostgreSQL 트랙](../../databases/postgresql/README.md)을 참조합니다. 이해가 부족하면 다음 주차로 넘어가는 대신 해당 통과 기준을 반복합니다.

1. [상세 커리큘럼](curriculum.md)에서 진입 모듈과 증거물을 정합니다.
2. [실제 운영 실습](operations.md)에서 연결·lock·query·Auth/RLS·Realtime/Storage baseline을 관측하고 [로컬 준비 및 안전 범위](labs/local-lab.md)를 확인합니다. 이 저장소가 완성된 Supabase 전체 스택이나 프런트엔드 앱을 제공하는 것은 아닙니다.
3. [공통 실험 방법](../../databases/shared/experiment-method.md)에 따라 가설·독립 oracle·실패 주입·복원 결과를 남깁니다.
4. [소스 읽기](source-reading.md)와 [평가](assessment.md)로 구현 추적 및 필수 gate를 검증합니다.

| 강의 | 모듈 | 최종 설명할 수 있어야 하는 질문 |
| --- | --- | --- |
| [플랫폼과 PostgreSQL](lessons/01-platform-postgres.md) | SU01–02 | 같은 SQL도 호출 경로와 role이 바뀌면 왜 보안 결과가 달라지는가? |
| [Auth·JWT·세션](lessons/02-auth-jwt.md) | SU03–04 | 유효한 서명과 현재 유효한 권한은 왜 다른가? |
| [RLS·Data API](lessons/03-rls-api.md) | SU05–06 | 조회가 안전한데 수정·RPC·view는 새는 이유는 무엇인가? |
| [Realtime](lessons/04-realtime.md) | SU07–08 | 알림이 끊겨도 업무 상태를 잃지 않으려면 무엇이 필요한가? |
| [Storage·Functions](lessons/05-storage-functions.md) | SU09–10 | 객체 bytes와 DB metadata, 외부 효과의 commit 경계는 어디인가? |
| [변경·복구·운영](lessons/06-operations-migrations.md) | SU11–12 | 배포·연결·복구가 tenant 격리를 어떻게 무너뜨릴 수 있는가? |
| [소스 연구·미니 캡스톤](lessons/07-research-capstone.md) | SU13–14 | 모르는 동작을 최소 재현하고 안전한 변경으로 연결할 수 있는가? |

## 실행 범위와 버전 규칙

기본은 실제 제품의 **지표·로그·SQL을 통한 진단과 회복**입니다. baseline 1개+서로 다른 사건 2개+회복 증거를 운영 gate로 제출하며 권한 oracle JSON/SQL 모형 검사만으로 대체하지 않습니다. 환경이 없다면 환경 미준비·설계 완료로 남깁니다. 새 클라우드 프로젝트나 유료 기능 구매를 요구하지 않습니다.

- **LOCAL-PREP**: 학습자가 CLI·Docker·독립 로컬 프로젝트를 준비한 뒤 실행하는 SQL/API 실험입니다. 환경이 준비되지 않았다면 실행 완료가 아니라 미실행으로 표시합니다.
- **BUILD**: 작은 client, 서버, 테스트 harness를 학습자가 구현하는 과제입니다. 코드 조각은 완성 앱·자동 채점기의 제공을 뜻하지 않습니다.
- **HOSTED-DESIGN**: 유료 기능, 프로젝트 설정, 운영 키 회전, hosted backup/PITR 등입니다. 별도 승인된 폐기 가능 프로젝트가 없으면 설계·tabletop만 수행하고 실제 검증과 구분합니다.
- **INTEGRATION-DESIGN**: PostgreSQL·Kafka·ClickHouse·Sentry 등과의 경계 설계입니다. SU14의 2주 범위를 넘는 실제 Supabase·Sentry 통합은 [보안·관측 앱 캡스톤](../../capstones/secure-observable-app.md)에서 별도로 수행합니다. 데이터 파이프라인 확장은 [공통 DB 캡스톤](../../databases/shared/capstone.md)의 별도 경로입니다.

Supabase에는 이 모든 구성요소를 고정하는 단일 버전 번호가 없습니다. CLI, PostgreSQL server/extensions, Auth, PostgREST, Realtime, Storage, Edge Runtime, gateway/pooler, SDK/SSR package 각각의 version·image digest·commit·설정을 기록합니다. 로컬 CLI 개발환경, 공식 self-hosted 배포, hosted 서비스는 기능·운영 책임·업그레이드 경로가 서로 다릅니다. 현재 [아키텍처](https://supabase.com/docs/guides/getting-started/architecture)와 실행 환경을 대조하고 gateway 제품명이나 내부 topology를 추측하지 않습니다.

문서 기준 확인일은 2026-10-04입니다. current 문서와 실제 배포 사이에 차이가 있으면 [소스 읽기](source-reading.md)의 runtime fingerprint를 우선하여 차이를 기록합니다. 특히 API key 체계, signing keys, Realtime 기능, Edge Functions 인증은 오래된 예제를 그대로 혼합하지 않습니다.

## 안전과 제출 계약

모든 SQL 생성·변경은 **비운영 독립 로컬 프로젝트**에만 적용합니다. 예제 객체는 `su_lab_` 접두사이며 최초 한 번 생성합니다. 이름 충돌 시 기존 테이블을 지우지 말고 별도 프로젝트나 새 suffix를 사용합니다. 실제 `auth.users`나 내부 `storage` metadata를 직접 수정하여 테스트 사용자를 만들지 않습니다. SQL에서 claims를 모사한 테스트는 암호 검증·Auth 세션 검증을 대체하지 않습니다.

secret/service-role key, refresh token, DB password, 쿠키 원문은 Git·보고서·스크린샷·로그에서 제외합니다. publishable key가 공개 가능하다는 말은 데이터가 공개여도 된다는 뜻이 아닙니다. row count 외에도 tenant별 PK 집합, 허용/금지 operation, object bytes checksum, 재시도 후 업무 결과를 비교합니다. 새 키와 legacy JWT 키의 역할 차이는 [API keys](https://supabase.com/docs/guides/getting-started/api-keys)를 기준으로 검증합니다.

성능 비교는 warmup 후 동일 workload의 **최소 20개 측정 반복/구간**, raw data와 자원·오류율을 포함합니다. p99에는 충분한 요청 수가 추가로 필요합니다. 설계만 수행한 HA/hosted 복구, 실행하지 않은 코드는 완료 증거로 인정하지 않습니다. 최종 기준은 정확성25·원리/소스25·실험/반증25·운영/재현성25, 총80 이상·각15 이상과 필수 gate 통과입니다.
