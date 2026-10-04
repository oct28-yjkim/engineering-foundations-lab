# Amplitude 소스 읽기 — 공개 SDK와 SaaS 계약의 경계

[시작](README.md) · [커리큘럼](curriculum.md) · [평가](assessment.md)

확인일 **2026-10-04**. 웹 기본 앱의 **`@amplitude/analytics-browser` 2.47.2**에 대응하는 source 기준은 tag `@amplitude/analytics-browser@2.47.2`의 peeled commit **`21b55e2576a33ca7b64d0136bc83e0389a9098ad`**입니다. 아래 TypeScript 경로는 이 commit으로 고정합니다. tag 확인은 해당 구현/테스트 전체를 실행했다는 뜻이 아닙니다. Swift/Kotlin은 회사 시험 앱의 실제 package·lockfile을 확인하고 각각 대응 tag/SHA를 별도로 기록합니다. SaaS 서버의 build·identity 저장소·query 실행 엔진은 공개 SDK에서 알아낼 수 없습니다.

## 1. 먼저 고정할 것

| 대상 | 기록 | 섞으면 안 되는 것 |
| --- | --- | --- |
| SDK | package 이름/정확 version·lockfile·번들 hash·platform/OS | Browser SDK 2, legacy JavaScript, iOS Swift, Android Kotlin 구현 |
| source | 공식 repo·tag→SHA·읽은 파일/테스트·변경 여부 | rolling docs의 기본값과 과거 package의 구현 |
| 전송 | endpoint 종류·region·직접/SDK/proxy·retry/queue 설정 | HTTP V2·Batch·SDK 자동 전송의 경계 |
| 프로젝트 | 별칭·region·허가 scope·관측 일시·plan별 가용 기능 | ingestion key와 export/관리 credential 권한 |
| 분석 | 이벤트 계약·identity/시간·chart/cohort/session revision | 현재 UI 설정을 과거 결과의 설정으로 간주 |

SDK 설치/clone은 기본 명령으로 자동 수행하지 않습니다. 이미 허가해 준비한 별도 source checkout에서만 `git rev-parse HEAD`, `git status --short`, `rg --files packages/analytics-browser packages/analytics-core`로 상태를 읽습니다. 저장소를 build하거나 테스트하기 전에 package script·네트워크 접근·테스트 credential 의존성을 검토합니다.

## 2. 공개 TypeScript SDK 탐색 지도

공식 저장소는 [Amplitude-TypeScript](https://github.com/amplitude/Amplitude-TypeScript)입니다. 선택 revision의 파일명·symbol 존재를 실제 checkout으로 확인하며 아래 탐색어가 곧 public API 계약이라는 뜻은 아닙니다.

| 조사 질문 | 공식 source 입구 | 찾을 연결·반례 |
| --- | --- | --- |
| init 전후 queue와 context는 언제 결합되는가? | [analytics-browser/src](https://github.com/amplitude/Amplitude-TypeScript/tree/21b55e2576a33ca7b64d0136bc83e0389a9098ad/packages/analytics-browser/src) | init/track·identity·session 설정→core 호출; init 누락·중복 init 반례 |
| user/device reset·storage는 무엇을 바꾸는가? | [browser 구현](https://github.com/amplitude/Amplitude-TypeScript/tree/21b55e2576a33ca7b64d0136bc83e0389a9098ad/packages/analytics-browser/src) | `setUserId`, `setDeviceId`, `reset`, storage adapter; 변경 전 queue의 identity가 언제 확정되는지 |
| flush 성공이 의미하는 완료점은 어디인가? | [analytics-core/src](https://github.com/amplitude/Amplitude-TypeScript/tree/21b55e2576a33ca7b64d0136bc83e0389a9098ad/packages/analytics-core/src) | track→plugin/enrichment→destination→queue/storage→transport→retry/flush 결과 |
| opt-out과 callback·오류 분류는 어떻게 결합되는가? | [core 구현](https://github.com/amplitude/Amplitude-TypeScript/tree/21b55e2576a33ca7b64d0136bc83e0389a9098ad/packages/analytics-core/src) | `optOut`, `flush`, `retry`, `insert_id`; drop·requeue·응답 해석의 실제 분기 |
| 무엇을 mock하고 무엇을 실제 실행하는가? | [browser/test](https://github.com/amplitude/Amplitude-TypeScript/tree/21b55e2576a33ca7b64d0136bc83e0389a9098ad/packages/analytics-browser/test), [core/test](https://github.com/amplitude/Amplitude-TypeScript/tree/21b55e2576a33ca7b64d0136bc83e0389a9098ad/packages/analytics-core/test) | clock/storage/network mock과 assert의 관찰점; mocked 200을 SaaS 성공으로 확대하지 않음 |
| 브라우저 lifecycle 차이는 테스트되는가? | [browser/e2e](https://github.com/amplitude/Amplitude-TypeScript/tree/21b55e2576a33ca7b64d0136bc83e0389a9098ad/packages/analytics-browser/e2e) | page lifecycle·browser 종류·실제 network 포함 여부; 테스트 설정과 fixture 선검토 |

읽기 순서는 type/config→entry method→queue/transport→오류 분기→관련 테스트→작은 실제 SDK 재현입니다. 한 파일에서 찾은 필드 이름을 Prometheus 지표나 서버 내부 queue 이름으로 바꾸어 설명하지 않습니다. 확인하지 않은 retry 횟수·저장소 기본값은 추측하지 않습니다.

## 모바일 공개 SDK도 별도로 고정한다

회사에서 사용하는 플랫폼부터 [Amplitude-Swift](https://github.com/amplitude/Amplitude-Swift) 또는 [Amplitude-Kotlin](https://github.com/amplitude/Amplitude-Kotlin)을 읽습니다. 선택 release의 init/instance·queue/storage·flush·app lifecycle·offline/reconnect·reset/opt-out 구현과 해당 테스트를 찾습니다. native source 경로는 버전마다 확인하고 웹 SHA를 모바일 revision으로 쓰지 않습니다.

- Swift: Package.resolved 등 실제 dependency 지문, 앱/OS·scene/lifecycle, 비동기 flush, background와 강제 종료의 차이를 기록합니다. [Swift SDK 문서](https://amplitude.com/docs/sdks/analytics/ios/ios-swift-sdk)
- Kotlin: Gradle dependency/lock 지문, instance와 공유 storage·identity, network 상태 인식의 권한/설정, retry·background flush를 확인합니다. [Kotlin SDK 문서](https://amplitude.com/docs/sdks/analytics/android/android-kotlin-sdk)
- 같은 `flush/reset/optOut` 이름이 같은 lifecycle·저장·재시도 보장을 의미하지 않습니다. 구형 iOS/Android SDK 문서를 신형 Swift/Kotlin 설정에 섞지 않습니다.

[모바일 수동 LAB](labs/mobile-lab.md)은 준비 지침이며 native 앱은 미제공입니다. 실제 device/simulator 테스트 전에는 source 읽기/기대 계약만 완료한 것으로 기록합니다.

## 3. 문서 계약과 source 관측의 교차 검증

| 계약 | 공식 문서 | source/실험으로 추가 확인할 것 |
| --- | --- | --- |
| SDK 초기화·전송·identity | [Browser SDK 2](https://amplitude.com/docs/sdks/analytics/browser/browser-sdk-2) | 실제 package option·promise/callback 완료 의미 |
| consent·cookies·unsent event 저장 | [Cookies and consent](https://amplitude.com/docs/sdks/analytics/browser/cookies-and-consent-management) | init 시 side effect, identity/event storage 차이, plugin/remote config의 실제 상태 |
| HTTP validation·응답·dedup | [HTTP V2](https://amplitude.com/docs/apis/analytics/http-v2) | SDK의 분류/분할/재전송이 endpoint 계약과 맞는지 |
| user/device/Amplitude identity | [Track unique users](https://amplitude.com/docs/data/sources/instrument-track-unique-users) | client가 보낸 ID·시각까지는 source, 최종 합병은 test project 관측 |
| session·시간 | [Track sessions](https://amplitude.com/docs/data/sources/instrument-track-sessions) | client session 설정과 project chart 정의의 차이 |
| 분석 의미 | [Funnels](https://amplitude.com/docs/analytics/charts/funnel-analysis/funnel-analysis-how-amplitude-computes), [Retention 시간](https://amplitude.com/docs/analytics/charts/retention-analysis/retention-analysis-time) | 문서와 tiny oracle/chart가 일치하는지; query server source 검증으로 부르지 않음 |

문서와 실제 package가 다르면 revision·설정·입력·관측점을 나눈 최소 반례를 먼저 만듭니다. 회사 프로젝트 설정을 바꿔 문서에 맞추지 않습니다. 기존 SDK의 의도된 동작·버그·문서 지연을 분리하고, 외부 issue 작성은 사용자 승인을 받은 별도 작업입니다.

## 4. 연구 과제 3개

1. **Queue identity 경계:** 시험 앱에서 서로 다른 합성 identity 전환 전후의 track/flush 순서를 바꿉니다. 각 payload의 ID를 관찰하고 source의 snapshot/참조 시점으로 설명합니다. 실제 개인 계정·공용 장치로 하지 않습니다.
2. **실패 후 재전송:** 로컬 transport fixture에 timeout/400/413/429를 입력하여 retry/drop/split 결과를 관찰합니다. 같은 business event의 insert_id와 새 업무 이벤트의 ID를 구분합니다. mock 결과는 SaaS rate-limit 테스트가 아닙니다.
3. **Consent·storage:** init 전·후, opt-out 전·후, 선택 storage 조건에서 가짜 marker가 cookie/event queue/전송에 남는지 확인합니다. 동의 전 실제 행동을 queue에 쌓는 실험은 하지 않습니다. observer는 비밀 없는 synthetic scope만 읽습니다.

각 과제는 구현 permalink 2개 이상·관련 테스트 2개 이상·한 음성 대조군·실제 실행 상태·모르는 서버 경계가 산출물입니다. 테스트 실행은 읽기와 다르고, upstream suite 전체 통과를 기본 LAB 필수 조건으로 삼지 않습니다.

## 5. 주장 금지선

- 공개 SDK의 queue를 SaaS의 영속 queue·복제 보장으로 설명하지 않습니다.
- Amplitude가 특정 DB/Kafka/Lucene를 쓴다고 추정하여 운영 명령을 제시하지 않습니다.
- API 200·SDK flush·preview 화면 하나로 identity·cohort·모든 차트 정합성을 통과시키지 않습니다.
- `insert_id`를 무기한 exactly-once 계약으로 해석하거나 다른 프로젝트/ID 조합에서도 같은 dedup 결과를 보장하지 않습니다.
- 외부 기능·limit·라이선스/plan 문서는 실행 당시 확인하며 latest라고 하드코딩하지 않습니다.

이 선 안에서 깊이는 줄지 않습니다. 공개 SDK 상태 전이, black-box 계약의 반증, 분석 집합의 정확한 검산, 재시도·보존·변경 통제의 증거가 전문가 수준의 연구 대상입니다.
