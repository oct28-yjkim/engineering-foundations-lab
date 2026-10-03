# S13–S14 — 소스 연구, 최소 반례, 작은 통합 단면

전문가 수준은 구성 요소 이름을 많이 아는 것이 아니라, 관측된 현상을 재현하고 다른 설명을 배제하며 자기 주장의 적용 범위를 정확히 말하는 능력입니다. 이 강의는 연구 산출물과 실행 산출물을 구분합니다. [평가 기준](../assessment.md)과 [소스 지도](../source-reading.md)를 함께 사용합니다.

## S13. 한 동작의 원인을 revision에 고정하기

### 선수 조건과 원리

S03–S12의 실험을 설계하고 결과를 읽을 수 있어야 합니다. 하나의 Sentry 버전으로 모든 component를 대표하지 않습니다. SDK의 package version과 commit, runtime, integration, bundler, Relay/Sentry/Snuba/Symbolicator image digest, 저장소 버전, deployment mode를 가능한 범위에서 기록합니다. SDK type definition만 읽는 것과 실제 호출되는 구현을 따라가는 것도 다릅니다.

공개 source `main`의 고정 SHA는 재현 가능한 읽기 지점일 수 있지만 배포된 서버의 revision을 뜻하지 않습니다. SaaS backend revision을 알 수 없으면 SDK/프로젝트/API의 black-box 동작을 관측하고, 공개 source는 가능한 설명 또는 비교 대상으로 둡니다. 알려지지 않은 서버 내부를 확정하는 문장을 쓰지 않습니다. API 문서의 최신 동작을 오래된 설치에 그대로 적용하지 않습니다.

최소 재현은 문제가 나타나는 가장 작은 입력·설정·순서입니다. 무작위 sleep으로 우연히 발생시키는 concurrency bug는 먼저 barrier와 fake clock으로 순서를 제어합니다. profiler·log를 추가했을 때 timing이 바뀌는 경우도 기록합니다. 성능 이슈와 정확성 이슈의 oracle을 섞지 않습니다.

### 실험: 한 주장, 한 반례, 하나의 호출 경로 — `OFFLINE` / `SDK-LAB`

아래에서 한 가지를 선택합니다. 큰 repository 전체를 정독하는 대신 경계를 좁힙니다.

- background job에서 user/breadcrumb가 다른 job에 섞이는 조건.
- 200 응답의 category rate limit이 이후 payload에 적용되는 조건.
- 특정 SDK mode에서 span filter가 실행되는 시점과 삭제 가능 여부.
- Debug ID와 artifact identity가 불일치할 때의 source mapping 실패.
- 특정 release의 grouping 입력이 바뀌어 동일 오류가 분리되는 조건.
- signal별 canary가 서로 다른 scrub 경로를 지나가는 조건.

1. “설정 X와 입력 Y에서 결과 Z다”라는 한 문장 가설을 씁니다. “SDK가 이상하다”는 반증 가능한 가설이 아닙니다.
2. 가장 작은 fixture와 독립 oracle을 만듭니다. 정상과 결함 결과가 모두 나와야 하며, 테스트 자체를 무력화하면 oracle이 실패하는지도 검사합니다.
3. [소스 지도](../source-reading.md)에서 진입점→문맥/변환→전송/저장→실패 처리 경로를 최소 네 경계로 그립니다. 각 경계에 해당 SHA의 경로/심볼, 입력·출력, 상태 변경을 적습니다.
4. 가능하다면 두 SDK release 또는 두 source revision에서 동일 fixture를 실행합니다. dependency lock과 설정을 고정합니다. 다른 runtime이나 샘플링 설정을 동시에 바꾸지 않습니다.
5. 실제 차이가 있으면 change range와 관련 test를 조사합니다. 직접 수정한 로컬 패치가 있다면 그 diff와 regression test를 제시하되 upstream 수정·배포까지 했다고 주장하지 않습니다.

network ACK 유실이나 서버 durability가 없는 loopback test를 “분산 저장소 복구 검증”이라고 부르지 않습니다. fake transport가 어떤 SDK 코드 경로를 건너뛰었는지도 source note에 명시합니다. 원인을 찾지 못한 경우 재현 가능한 증거와 남은 가설을 제출하는 것이 추측을 사실로 바꾸는 것보다 낫습니다.

### 산출물·통과 기준

제출물은 component manifest, 100줄 안팎을 목표로 한 최소 재현 또는 최소화가 어려운 이유, 원시 결과, source trace, 회귀 test, 적용 범위입니다. 줄 수 자체는 절대 기준이 아니며 필수 입력을 제거하면 현상이 사라지는지 설명해야 합니다.

동료가 외부 서비스 없이 같은 판정을 재현하거나, PROJECT-LAB인 경우 승인된 환경·정확한 실행 순서·검증 query로 재현할 수 있어야 합니다. 정상/결함 oracle, 고정 revision 증거, 대안 설명 두 가지의 배제가 필수 gate입니다. 실제로 실행하지 않은 version comparison은 연구 계획으로 표시합니다.

## S14. 2주 최소 캡스톤: 합성 서비스의 관측 계약

### 범위와 선수 조건

S01–S13 산출물을 재사용합니다. 목표는 전체 self-hosted 운영 스택을 2주 만에 구축하는 것이 아닙니다. **합성 서비스 한 개, 1,000개 입력 요청, SDK의 외부 송신 없는 수집 경계, 두 장애, 신호별 oracle**을 검증하고 향후 운영 배치를 설계합니다. Supabase·Kafka·ClickHouse를 아직 학습하지 않았다면 구현 선수 조건으로 요구하지 않습니다.

완성 애플리케이션은 이 저장소에 제공되지 않습니다. [실습 안내](../labs/local-lab.md)에 따라 학습자가 고정 버전 SDK harness를 구현합니다. 환경 제약으로 SDK를 실행하지 못했다면 OFFLINE 모델·설계까지만 완료했다고 보고하며 SDK 실행 gate를 충족했다고 표시하지 않습니다.

### 시스템과 입력 계약

서비스는 `request_id`, `tenant_canary`, `release_id`, `operation`, 의도한 결과, 실제 결과를 기록합니다. 요청 1,000개 중 성공·처리된 거절·예외·timeout의 비율은 S01 fixture를 재사용하거나 변경 이유를 명시합니다. 하나의 요청이 여러 span/log를 만들 수 있으므로 각 신호의 기대 수를 별도 정의합니다. 발생 시각과 capture/transport 시각도 분리합니다.

기본 신호는 error event와 span입니다. 선택한 SDK가 지원하면 structured log도 추가합니다. 지원하지 않는 신호를 fake JSON으로 만들어 실제 SDK 지원 검증이라고 부르지 않습니다. Replay/profile/attachment는 S11의 별도 privacy 연구에 남겨도 됩니다. source map은 S05의 오프라인 identity 증거를 재사용할 수 있으며 외부 업로드는 필수가 아닙니다.

### 두 장애와 독립 oracle

첫 장애는 **비동기 scope 오염**입니다. 두 tenant의 작업을 barrier로 교차시키고 shared/global 문맥을 사용하는 결함 버전에서 타 tenant canary가 섞이는지 찾습니다. 수정 버전은 작업별 문맥 경계를 적용하여 같은 schedule에서 누출 0을 검증합니다. 이 결과는 SDK context 격리 증거이지 SaaS/DB의 tenant authorization 증거가 아닙니다.

둘째 장애는 **category 제한**입니다. fake clock/loopback 응답으로 특정 신호 category의 제한을 전달하고, 해당 기간의 시도·폐기·유지 및 다른 category 영향을 S04 oracle과 비교합니다. 실제 quota를 소모하거나 서비스에 부하를 가하지 않습니다. 이것을 Kafka 장애·네트워크 ACK 유실·서버 장애 복구라고 이름 붙이지 않습니다.

두 장애 모두 입력 원장이 정답이며 SDK 결과로 정답을 다시 쓰지 않습니다. sampling은 연결성/격리 기준선에서 끄거나 전량 유지하도록 지원 설정을 명시한 뒤 별도 단계로 바꿉니다. S08 [오프라인 샘플링 oracle](../labs/sampling-oracle.mjs)을 첨부하여 관측 subset과 모집단 집계의 차이를 설명합니다.

### 제출 evidence 묶음

| 항목 | 최소 증거 | 실패 판정 |
| --- | --- | --- |
| Version/설정 | SDK lock, runtime, mode, integration, 외부 송신 차단 방식 | `latest` 또는 알 수 없는 mode로 재현 불가 |
| 입력 계약 | 1,000요청 원장과 signal별 기대 관계 | 요청 수를 event/span/log 수와 동일시 |
| SDK 정상 경로 | raw Envelope/item, ID/parent/canary oracle | capture 호출 수만 기록하고 처리 후 payload 미검사 |
| 두 장애 | 결함 검출·수정 후 결과·fake clock/schedule | 의도한 실패가 oracle에서 통과 |
| Privacy | 금지 canary가 검사한 egress에서 0 | error만 검사하고 모든 신호 보호를 주장 |
| Sampling | population·naive·weighted 의미와 식별 불가 조건 | sample의 단순 평균을 모집단 SLO로 주장 |
| 운영 설계 | 수집→조회 경계, 권한·retention·독립 probe·복구 범위 | local transport 수락을 서버 저장/HA 증명으로 주장 |

리뷰어는 10개의 임의 입력 ID를 선택하여 업무 결과→capture→payload 또는 의도한 폐기까지 추적합니다. 별도의 10개 privacy fixture와 parent relation fixture를 검증합니다. 모든 입력에 완벽한 end-to-end 서버 상태를 주장하는 대신 관측할 수 없는 경계를 명확히 남기는 것이 필수입니다.

### 전문가 구술 리뷰

다음 질문에 설정 설명만이 아니라 본인의 증거 또는 반례로 답합니다.

1. 200인데 issue가 없을 때 다음 조사 순서를 어떻게 정하고, 어떤 증거로 가설을 제거하는가?
2. 같은 issue가 같은 원인이라는 주장은 어떤 fixture에서 깨지는가?
3. 요청별 context와 tenant authorization은 왜 서로 대체할 수 없는가?
4. trace가 연결되어 있는데 latency SLO를 추정할 수 없는 경우는 무엇인가?
5. beforeSend에서 값이 사라졌는데도 비밀정보가 유출될 수 있는 경로는 무엇인가?
6. 부분 JSON backup과 전체 서비스 복구 사이에 어떤 증거가 더 필요한가?
7. 공개 source snapshot과 SaaS runtime이 다르면 어느 주장까지 할 수 있는가?

## 다음 8주: 실제 통합 운영 검증으로 확장

[Supabase·Sentry 보안·관측 앱 캡스톤](../../../capstones/secure-observable-app.md)에서는 authentication/authorization, 개인정보, 장애, 복구를 실제 애플리케이션 경계에서 검증합니다. [데이터 파이프라인 통합 캡스톤](../../../databases/shared/capstone.md)은 PostgreSQL·Kafka·ClickHouse의 전달/저장 계약과 연결하는 다른 경로입니다. 두 캡스톤을 모두 필수로 요구하지 않습니다.

전체 배포의 장애 도메인, 다섯 실패 시나리오, 실제 restore와 RPO/RTO 증거는 선택한 8주 통합 프로젝트의 범위에서 계획합니다. S14의 두 SDK 경계 실험은 이를 대신하지 않습니다. 이전 모듈에서 이미 수집한 증거를 재사용하되 변경된 version·schema·privacy 설정이 영향을 주면 재검증합니다.
