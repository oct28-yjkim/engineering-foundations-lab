# Sentry 실습 준비: 실제 관측·troubleshooting 중심

이 저장소는 Sentry 전체 서버, SDK 앱, 계정, DSN, 프로젝트를 자동 생성하지 않습니다. 제공 파일은 [샘플링 oracle](sampling-oracle.mjs)과 실험 명세입니다. SDK 계측·테스트 transport·self-hosted 구축은 학습자가 구현합니다. **오프라인 계산의 PASS를 Sentry 수집·처리·가시성 검증으로 제출하지 않습니다.**

## 실행 범위

먼저 [운영 실습](../operations.md)의 읽기 전용 preflight와 baseline을 수행합니다. 실제 project의 오류율·p95·ingestion 상태·회복 검증이 기본이고 아래 오프라인 계산은 선택 부록입니다. 기존 승인 환경이 없으면 준비 상태로 기록하며 새 계정·과금·전송을 자동 요구하지 않습니다.

| 수준 | 준비 | 여기서 확인할 수 있는 것 | 아직 확인하지 못하는 것 |
| --- | --- | --- | --- |
| SDK-LAB | 버전 고정 SDK 앱, 메모리 transport와 합성 입력을 직접 구현 | scope/context·hook·envelope·flush 경계 | 서버 ingestion·grouping·검색 가시성 |
| PROJECT-LAB | 별도 학습 프로젝트 및 합성 데이터 송신 허용 | 실제 수집·분류·symbolication·trace·알림 | 서버 내부 장애·backup restore |
| SELF-HOST-DESIGN | 고정 upstream manifest, 격리 자원·운영 환경 | 내부 처리 경로·backlog·복구·업그레이드 | SaaS와 모든 기능/운영 보장의 동일성 |
| OFFLINE 선택 부록 | Node.js, 제공 `.mjs` | 원본 분모·표본 편향·추가 유실의 계산 | SDK·네트워크·Sentry 저장/조회·운영 gate |

마지막 두 수준은 계정·자원·보존·비용·전송 범위를 먼저 결정합니다. 기존 업무 프로젝트, 고객 데이터, 실제 장애 알림 수신자는 실습 대상이 아닙니다. 이 커리큘럼을 추가하면서 클라우드 프로젝트나 외부 송신을 수행하지 않았습니다.

## 1. 버전과 배포 지문

Sentry에는 모든 컴포넌트를 대표하는 하나의 설치 버전이 없습니다. 다음 값을 비밀 없이 기록합니다.

```text
실험일 / run_id / 실행 환경 / 합성 데이터 범위
SDK 패키지·정확 버전·lockfile / 언어 runtime / framework / OTel 조합
capture 대상(error/span/log/replay 등) / 활성 integration / tracing mode
transport·sampling·filter·scrubbing 설정의 비밀 제외 사본
프로젝트의 배포 유형(SaaS/self-hosted) / 기능 확인일 / 보존·quota 조건
self-hosted이면 manifest SHA, 이미지 digest, Relay/Snuba/저장소 버전
연결 서비스·정상 종료/강제 종료 방식 / source-reading 기준 SHA
```

실제 runtime과 [소스 탐색](../source-reading.md)의 읽기 기준 snapshot은 별도입니다. 의존성은 선택한 호환 버전을 고정하고 공식 migration 문서를 대조합니다. 신규 SDK의 default나 hook를 과거 버전으로 옮겨 가정하지 않습니다.

## 2. 무외부송신 SDK 실험 명세

먼저 별도 앱에 선택 SDK를 설치하고 테스트 transport를 구현합니다. 실제 프로젝트 DSN을 넣지 말고, 해당 SDK가 capture 경로를 활성화하는 데 요구하는 시험용 설정과 메모리 transport를 조합합니다. DSN이 없어서 SDK 자체가 비활성화된 상태를 “PII 필터가 성공해 전송이 없다”로 오해하지 않습니다. **transport와 네트워크 차단으로 외부 송신이 없는지 검증**하고 기능별 별도 전송 경로도 조사합니다. 완성 앱은 제공하지 않습니다.

합성 요청 100개에 `run_id`, 안전한 `request_id`, release/environment, 의도된 오류 여부를 기록합니다. 동시 요청 A/B의 가짜 사용자·tenant label을 달리하고 scope/context가 섞이지 않는지 envelope를 검사합니다. 동시성 1/10, 정상 종료/종료 직전 capture, filter 통과/제외를 한 조건씩 바꿉니다.

oracle는 앱의 입력 원장입니다. 원장에는 `capture 대상 → SDK 처리/제외 → transport 인계 → flush 결과`를 구별하며, 내부 transport 수신을 서버 저장 성공으로 이름 붙이지 않습니다. 오류 event ID·trace ID·span ID도 업무 request ID와 같은 의미가 아닙니다.

개인정보 fixture는 실제 토큰 대신 `SYNTHETIC_SECRET_A` 같은 표식을 request URL/query, headers, user, breadcrumb, error message, span attribute, log, attachment 내용 등 지원하는 경로별로 넣습니다. 한 hook가 모든 데이터 종류를 처리한다고 가정하지 말고 outgoing payload별 금지 표식 검사를 작성합니다. replay·profile·source map은 지원/활성 여부와 별도 처리 경로를 명시합니다. 테스트 transport 하나의 성공을 모든 기능의 privacy 증명으로 확대하지 않습니다.

## 3. 실제 프로젝트와 self-hosted 확장

PROJECT-LAB은 위 입력만 허용하는 별도 학습 프로젝트를 사용합니다. DSN은 ingestion 라우팅용 설정이며 관리 API token과 구별합니다. 공개 가능하다는 설명을 남용·quota·rate limit 위험이 없다는 뜻으로 해석하지 않습니다. source map 업로드용 token, 세션·사용자 토큰, 서버 관리자 credential을 소스나 실험 로그에 넣지 않습니다.

합성 event별로 SDK 시도·인계·서버 응답·수집 처리·검색 가능·issue 연결을 대조합니다. 모르는 상태는 unknown으로 남기고, 2xx나 SDK flush 성공만으로 모든 저장·색인·알림 처리가 끝났다고 판정하지 않습니다. 알림은 실습 전용 수신자로 제한하고 비활성화/원복 절차를 준비합니다.

self-hosted는 [공식 배포 저장소](https://github.com/getsentry/self-hosted)와 [설치 안내](https://develop.sentry.dev/self-hosted/)의 선택 release/commit에서 시작합니다. 복합 스택의 의존 서비스·자원·포트·데이터 수명을 조사하고, upstream manifest를 고정한 독립 폴더/환경에 구성합니다. 이 저장소의 PostgreSQL·Kafka·ClickHouse Compose를 Sentry의 내부 서비스로 임의 연결하지 않습니다. 이름이 같아도 지원 버전·topic/schema·설정 계약이 다릅니다. upstream self-hosted의 PoC/저용량 범위를 읽고 운영 HA가 자동 제공된다고 가정하지 않습니다.

## 4. 기록과 검증 상태

제출물은 입력 원장, 비밀 제거한 설정, SDK/transport 증거, 실제 프로젝트 처리 이력, privacy 음성 테스트, 미검증 범위를 분리합니다. self-hosted를 구성한 경우에만 내부 장애·restore 결과를 제출합니다. 개인정보 표식 검사는 synthetic 데이터를 대상으로 하며 실사용자 데이터를 가져오지 않습니다.

2026-10-04 작성 환경에서 제공 오프라인 oracle를 실행하여 assertions PASS를 확인했습니다. **Sentry SDK 앱·서버·외부 프로젝트·실제 수집은 실행하지 않았습니다.** 해당 환경에서 Docker Linux 엔진도 실행되지 않았습니다. 다음은 [28주 과정](../curriculum.md)의 SDK/서버별 과제로 이어집니다.

## 선택 원리 부록: 오프라인 샘플링 계산

저장소 루트에서 실행합니다. 외부 패키지 설치가 필요 없고 네트워크 요청·파일 쓰기를 하지 않습니다. Node.js가 필요하며 작성 환경에서는 Node `v24.19.0`으로 실행했습니다.

```text
node observability/sentry/labs/sampling-oracle.mjs
```

합성 모집단은 일반 요청 10,000개 중 실패 100개, 중요 요청 1,000개 중 실패 200개입니다. 각 층에서 1/10, 1/2을 남기는 결정적 fixture를 만듭니다. 각 층의 성공·실패에도 같은 유지 비율이 되도록 **교육용으로 균형을 맞췄습니다**. 실제 SDK의 난수·결정적 trace sampling 알고리즘이나 수집 보장을 구현한 것이 아닙니다.

| 계산 대상 | 요청 분모 | 실패 분자 | 실패 비율 |
| --- | --- | --- | --- |
| 전체 모집단 | 11,000 | 300 | 약 2.7273% |
| 선택된 표본을 그대로 계산 | 1,500 | 110 | 약 7.3333% |
| 각 층의 유지 비율로 가중한 교육용 fixture | 11,000 | 300 | 약 2.7273% |
| 표본에서 일부 실패만 추가 유실한 뒤 같은 가중치 적용 | 10,900 | 200 | 약 1.8349% |

이 실험은 계층별 수집률이 다르면 표본의 단순 비율이 원본 비율과 달라질 수 있음을 보입니다. 가중 후 정확히 맞는 것은 이 fixture의 구성 결과입니다. 임의 표본에서 매번 정확한 복원이나 불편 추정·신뢰구간을 입증한 것이 아닙니다. 실제 분석에는 포함 확률, 상관·중복, 추출 단위, 0%로 제외된 집단, 알 수 없는 추가 유실을 고려해야 합니다.

`distinctSyntheticCauses=2`는 300개 실패를 두 합성 원인으로 나눈 값입니다. 이 수가 요청 실패 횟수나 Sentry의 실제 grouping 결과라는 뜻은 아닙니다. issue 수를 요청 수의 분모로 나누어 서비스 오류율을 만들지 않습니다. Sentry가 제공하는 추정·집계 지표도 해당 지표의 정의와 수집 경로를 별도로 확인합니다. [공식 sampling 문서](https://docs.sentry.io/platforms/javascript/sampling/)

**과제:** 층별 규모·실패율·유지 비율을 바꾸고 손계산 oracle도 함께 수정합니다. 가중치로 보정하지 못하는 `미수집 집단`, `실패에서만 발생한 유실`, `중복 재전송`의 반례를 하나씩 추가합니다. 표본 비율을 늘리기만 하면 선택 편향이 반드시 사라지는지 설명합니다.
