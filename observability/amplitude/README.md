# Amplitude — 웹·모바일 계측에서 신뢰할 수 있는 제품 분석까지

목표는 차트를 만드는 데서 그치지 않고 **사용자의 행동 → SDK 계측 → 전송/수집 → 사용자 식별 → 분석 정의 → 의사결정**의 어느 경계에서 숫자가 달라졌는지 증거로 설명하는 것입니다. 회사의 웹·모바일 SDK 중심 사용을 기준으로 정상 기능, 내부 SDK 동작, 관측, 제약, 대표 문제와 복구를 연결합니다.

Amplitude는 이 과정에서 **제품·행동 분석 SaaS**로 다룹니다. Sentry의 오류/trace나 DB·broker의 서버 지표와 역할이 다릅니다. Amplitude 서버의 CPU·shard·비공개 저장 엔진을 임의로 추정하거나 로컬 Compose가 SaaS를 재현한다고 하지 않습니다.

## 기본 LAB 입구

**정상 기능 → 동작 원리 → 모니터링 → 제약 → 진단·복구** 순서입니다. 28주 심화 이수는 선수 조건이 아닙니다.

1. [환경과 권한](environment.md): 테스트 프로젝트·region·동의·데이터 범위·관측 권한·비용을 확인합니다. 회사 운영 프로젝트에는 실습 이벤트를 보내지 않습니다.
2. [기본 LAB](labs/README.md): 제공된 웹 SDK 앱의 정상 3단계 행동과 프로젝트의 실제 이벤트·퍼널을 비교합니다.
3. [모바일 LAB](labs/mobile-lab.md): iOS/Android 시험 앱에서 foreground/background·offline/reconnect·login/logout·동의를 같은 원장으로 관측합니다.
4. [운영 runbook](operations.md#basic-lab): SDK 호출·Network·Ingestion Debugger·User Activity·차트의 차이를 좁히고 사건 최소 두 개를 복구합니다.
5. [HTTP 진단 보조](labs/http-lab.md): SDK와 무관한 10개 합성 이벤트의 정답으로 수집/분석 문제를 분리합니다. SDK 계측 성공의 대체물이 아닙니다.
6. [28주·14모듈 심화](curriculum.md), [SDK 소스 지도](source-reading.md), [평가](assessment.md)로 필요한 영역을 깊게 확장합니다.

## 무엇이 제공되는가

| 경로 | 제공물 | 직접 준비하거나 별도로 검증할 것 |
| --- | --- | --- |
| 조사·계약 검토 | tracking/identity/분석 계약, 합성 입력·정답, 지표·사건 카드 | 실제 회사 앱의 계측 구현/동의·원본 업무 분모 |
| WEB-SDK | [최소 Browser SDK 앱](labs/browser/index.html), SDK 2.47.2 고정·수동 행동/사건 버튼·로컬 원장 | 허가된 테스트 프로젝트·실제 Network/UI 관측; SDK/CDN 로드와 실제 전송은 별도 선택 |
| MOBILE-SDK | [iOS/Android 절차](labs/mobile-lab.md), lifecycle·동의·식별·복구 체크리스트 | 앱·SDK dependency pin·simulator/device·개발자 계측; 완성 모바일 앱은 미제공 |
| HTTP-DIAGNOSTIC | [합성 10건 runner](labs/http-lab.md), 기본 무송신·명시적 1회 전송 | 수집/차트/병합/dedup를 실제 프로젝트에서 확인 |
| 심화 | 7강·14모듈, 공개 SDK 소스·원리·운영 연구 | SaaS 비공개 내부는 확인 불가; paid governance/group/export 기능은 실제 권한/계약 확인 |

**CPU 모형을 기본 실습으로 두지 않습니다.** 네트워크 없는 fixture/단위 검사는 입력과 코드 계약을 검산하며 실제 SDK 전송·Amplitude 분석 결과를 증명하지 않습니다. 실제 수행과 미검증은 [검증 기록](labs/validation.md)에 구분합니다.

## 버전·제품 경계

웹 앱은 Browser SDK **2.47.2**, 공개 소스 revision `21b55e2576a33ca7b64d0136bc83e0389a9098ad`를 기준으로 합니다. 확인일은 2026-10-04이며 영구적인 최신 버전이라는 뜻은 아닙니다. 모바일 SDK/OS/app build와 회사 SDK 버전은 별도 기록합니다. SaaS backend revision·plan·UI·quota는 npm 버전과 같지 않습니다. [고정 소스 정책](source-reading.md)

기본 앱은 autocapture·remote config·diagnostic telemetry·Replay를 끄고 메모리 저장만 사용합니다. 이것은 회사의 운영 권장 설정이 아니라 **정상 명시적 이벤트와 원인을 분리하기 위한 학습 조건**입니다. 지속 저장·autocapture·CMP·Replay·외부 destination·Experiments는 별도 승인·설정 검토 이후 확장합니다.

## 다른 트랙과 연결

- [Sentry](../sentry/README.md): 실제 앱 결함 때문에 전환율이 떨어졌는지, 계측 누락 때문에 그렇게 보이는지 대조합니다. 사용자 원문·세션 replay를 무분별하게 공유하지 않습니다.
- [PostgreSQL](../../databases/postgresql/README.md) / [Supabase](../../platforms/supabase/README.md): 결제·가입 업무 원장과 분석 event의 차이를 ID·시간·취소/환불 정의로 설명합니다. 분석 차트는 결제 정산 원장의 대체물이 아닙니다.
- [Kafka](../../streaming/kafka/README.md) / [ClickHouse](../../databases/clickhouse/README.md): 전송·중복·late event·backfill·warehouse 대사를 연구합니다. 외부 시스템의 exactly-once가 사용자 행동의 단 한 번 계측까지 보장하지 않습니다.

공식 입구: [Amplitude 시작](https://amplitude.com/docs/data/data-get-started), [Browser SDK](https://amplitude.com/docs/sdks/analytics/browser/browser-sdk-2), [SDK 진단](https://amplitude.com/docs/sdks/sdk-debugging). 기능/제한을 조사한 사실과 직접 관측한 결과를 별도 칸에 기록합니다.
