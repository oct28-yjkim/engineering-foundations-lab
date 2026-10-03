# Supabase Zero to Hero: 신뢰 경계를 검증하는 28주

[시작 안내](README.md) · [평가](assessment.md) · [소스 지도](source-reading.md) · [환경 준비](labs/local-lab.md)

“API가 응답했다”에서 끝내지 않습니다. 요청의 credential이 role로 변환되는 경로, 데이터가 commit되는 경계, 전달 실패와 복구의 범위, 그 주장을 지지하는 소스와 반례를 함께 배웁니다. 시간은 학습량 예산이며 통과 보증이 아닙니다. 모듈당 24시간은 원리·문서6, 실험/구현10, 소스4, 증거·동료 리뷰4시간을 기본으로 조정합니다.

## 14개 모듈

실험 시간은 [운영 runbook](operations.md)의 실제 baseline·지표/로그/SQL 기반 triage·제한 변경·회복 증거를 우선합니다. SU01–02 연결/lock, SU03–06 Auth/RLS·slow query, SU07–10 Realtime/Storage, SU11–14 변경/복구/사고 보고서를 누적합니다. 기존 28주·14모듈과 원리/소스 심화는 유지합니다. fixture JSON·SQL claim 모사는 기대값 보조 자료이며 실제 제품 운영 gate는 아닙니다.

| 모듈·주차 | 선행 | 원리와 핵심 검증 | 필수 산출물·통과 기준 |
| --- | --- | --- | --- |
| SU01 · 1–2 | 공통 SQL/HTTP | PostgreSQL 중심 구성, control/data plane, 각 서비스 trust boundary | [01강](lessons/01-platform-postgres.md#su01)의 6개 요청 경로에 credential·role·상태 저장 위치·실패 책임 표시; component fingerprint 빈칸은 미확인으로 표시 |
| SU02 · 3–4 | SU01, transaction/index | 제약·MVCC·exposed schema, direct/session/transaction 연결 | 중복/음수/동시 변경 반례, direct와 pooler의 역할 차이; schema·grant·pool 예산 증거 |
| SU03 · 5–6 | SU01, 암호 기초 | 새 API key/legacy key, JWT 서명·claim·JWKS | [02강](lessons/02-auth-jwt.md#su03)의 6 credential 조합, 위변조·만료 거부, secret 무노출 검사 |
| SU04 · 7–8 | SU03 | refresh rotation, PKCE/SSR, cache와 요청별 client | 2사용자 교차 세션 누출0, refresh 응답 유실 시나리오, 탈퇴/권한철회 시간 경계 |
| SU05 · 9–10 | SU02–04 | role/grant/RLS, USING/WITH CHECK, 3값 논리 | [03강](lessons/03-rls-api.md#su05)의 두 tenant × 읽기/쓰기 matrix; anon·privileged·stale claims 반례 모두 기록 |
| SU06 · 11–12 | SU05, query plan | PostgREST request transaction, view/RPC 권한, policy 비용 | API와 SQL 동일 oracle; invoker view/RPC 음성 테스트, index 전후 role 동일 계획 비교 |
| SU07 · 13–14 | SU05–06, WAL 기초 | publication/slot/logical decoding, RLS event fan-out | [04강](lessons/04-realtime.md#su07)의 disconnect 후 DB 재조정으로 상태 일치; delete 노출 계약 검증 |
| SU08 · 15–16 | SU04, SU07 | Broadcast/Presence, channel auth, bounded queue | 타 tenant private join 거부, reconnect/revocation 시간선, 느린 수신자 queue 상한 |
| SU09 · 17–18 | SU05 | Storage metadata/bytes, bucket·path policy, upload | [05강](lessons/05-storage-functions.md#su09)의 타 tenant object 접근 거부, upsert·signed URL·checksum 검증 |
| SU10 · 19–20 | SU03–06, retry | Edge runtime, gateway/handler auth, idempotent business transaction | 인증 음성 테스트와 응답 유실 후 재시도에서 업무 효과1회; 외부 효과 보장 한계 명시 |
| SU11 · 21–22 | SU02/06/10 | migration 이력, expand/contract, CI·pooler | [06강](lessons/06-operations-migrations.md#su11)의 빈DB/구버전DB 두 경로 수렴, schema뿐 아니라 권한 회귀0 |
| SU12 · 23–24 | SU09–11, restore 기초 | backup/PITR 범위, secrets·observability, RPO/RTO | 새 대상에 실제 data·RLS·bytes 복원; hosted 미실행 항목은 별도 설계 판정 |
| SU13 · 25–26 | SU01–12 | source call chain, test oracle, 최소 재현 | [07강](lessons/07-research-capstone.md#su13)의 commit 고정 재현1건·반증1건·회귀 테스트1건 |
| SU14 · 27–28 | SU05/09/10/12/13 | bounded tenant app slice와 확장 의사결정 | 2주 제한 구현, 2개 실패 주입, 정확성·복원·보안 gate, 전체 통합은 후속 설계 |

## 학습자의 작업 방식

매 실험은 먼저 “무엇이 성공인가”를 쓰고 실행합니다. API body만 비교하지 말고 허용된 PK 집합, 영향을 받은 행, 트랜잭션 결과, object hash를 별도 원장과 대조합니다. HTTP 상태가 같아도 grant 거부, RLS 빈 결과, token invalid, service outage는 원인이 다릅니다. 원문 credential 대신 key 종류·role·사용자 가명·request ID·시간만 기록합니다.

각 강의의 SQL은 LOCAL-PREP 후 실행 예제입니다. browser/SDK/Edge client는 BUILD 과제로 명시된 최소 harness를 직접 작성해야 합니다. HOSTED-DESIGN은 비용/권한이 필요한 운영 환경을 자동 구성한다는 뜻이 아닙니다. 환경을 확보하지 못하면 설계 gate는 평가할 수 있으나 실행 gate는 미완료로 둡니다. 증거가 빈 곳을 예상 출력으로 채우지 않습니다.

## 교차 트랙 순서

PostgreSQL의 MVCC·RLS·복구를 더 이해하고 싶으면 [PostgreSQL 트랙](../../databases/postgresql/README.md)으로 돌아갑니다. Realtime 알림과 replay 가능한 데이터 파이프라인을 비교할 때 [Kafka 트랙](../../streaming/kafka/README.md)을, 분석 복제를 설계할 때 [ClickHouse 트랙](../../databases/clickhouse/README.md)을 연결합니다. 이 세 트랙 전체 완료를 SU14 시작 조건으로 만들지는 않습니다.

SU14는 두 tenant의 업무 API·파일·재시도·복구를 포함한 작은 2주 결과물입니다. 전체 Supabase·Sentry 앱의 관측·보안·복구 통합은 별도8주 [보안·관측 앱 캡스톤](../../capstones/secure-observable-app.md)으로 확장합니다. 대규모 multi-region, 완전 CDC, 모든 서비스 HA, production 배포는 자동 포함되지 않습니다. 데이터 분석 파이프라인은 [공통 DB 캡스톤](../../databases/shared/capstone.md)의 선택 경로입니다.
