# 6강 — backfill, SaaS 한도, SDK rollout과 복구

[커리큘럼](../curriculum.md) · AM11–AM12 · [시간·identity](03-identity-sessions.md)

## 정상 기능: 현재 데이터의 계약부터 보존한다

웹/모바일 정상 SDK source/run의 사용자·event 집합·시간·차트 정의를 먼저 고정합니다. backfill은 기본 첫 실습이 아니라 정상 계약을 이해한 후의 **선택 수동 확장**입니다. 회사 운영 프로젝트에 historical data를 넣거나 export credential을 발급하지 않습니다.

대량 API 대신 별도 허가된 test project·소수의 synthetic 과거 event로 mapping을 검토합니다. HTTP 비교 runner가 Batch upload나 회사 backfill pipeline까지 제공하는 것은 아닙니다. 한도·요청 수·event 수·시간·비용은 [운영 실습](../operations.md)의 상한을 넘기지 않습니다.

## 원리: 과거 데이터를 넣으면 현재 분석도 바뀔 수 있다

historical event time이 더 이르면 new-user의 시작 시점이 달라질 수 있습니다. user_id mapping이 다르면 동일 제품 사용자가 다른 사용자로 보이고, 옛 user property를 다시 보내면 현재 속성에 영향을 줄 수 있습니다. 별도 project와 필요한 경우 문서의 user-property sync 제어를 검토하지만, 옵션 한 개가 identity·retention 영향을 모두 제거한다고 생각하지 않습니다. **import에는 일반적인 transaction rollback이 없습니다.** [공식 backfill 지침](https://amplitude.com/docs/data/data-backfill)

Export API의 파일을 그대로 import하지 않습니다. 조회 기준 시간, 필드 이름/타입, insert_id 형태, user/device ID, session, property, region을 별도 mapping합니다. event-time 구간과 upload-time 구간을 같은 날짜 범위로 간주하지 않습니다. [Export 차이](https://amplitude.com/docs/data/sources/export-api-differences) · [Batch API](https://amplitude.com/docs/apis/analytics/batch-event-upload)

## reconciliation 원장

| 기록 | 목적 |
| --- | --- |
| source manifest·immutable ID·내용 fingerprint | 무엇을 다시 보낼 것인지 정의 |
| partition ID·source 범위·event 수 | 중복되지 않는 작업 집합과 재개 위치 |
| business event↔insert_id↔user/device | retry와 새로운 업무 event를 구분 |
| attempted·accepted·rejected·unknown | 응답 유실을 성공/실패 어느 쪽으로도 숨기지 않음 |
| checkpoint의 의미·시각·대상 | 전송 시도와 실제 검증 완료의 진행률 분리 |
| final event/user 집합·업무 속성·시간 bucket | count가 같아도 다른 데이터인 오류 탐지 |

초기 실행과 replay가 같은 identity/dedup 범위 안에 있는지 문서·설정·실제 원장으로 확인합니다. 기간 밖이나 ID가 바뀐 재전송은 과거 dedup 성공으로 보장되지 않습니다. stable ID 설계가 서버의 무기한 exactly-once나 chart 동일성을 보증하지 않습니다.

## 문제 A — 재개했더니 중복/누락 또는 현재 property가 바뀐다

local fixture에서 partition 하나의 전송 결과를 unknown으로 표시하고 재개 결정을 연습합니다. 실제 test project 재전송은 허가된 작은 synthetic 집합과 원장을 검토한 후만 선택합니다. retry마다 새 ID, checkpoint 선행, ID/time mapping 오류, historical user property sync를 경쟁 가설로 봅니다.

조치는 sender를 멈추고 source manifest·시도 원장·실제 가시성을 대조하는 것입니다. 불확실 구간을 전체 재전송하거나 current property를 운영 값으로 덮어쓰지 않습니다. 새 테스트 run/별도 synthetic ID에서 mapping 수정 결과를 검산합니다. 이미 잘못 들어간 데이터는 분리 표기하고 삭제·재가공·재프로젝트는 별도 승인 결정으로 남깁니다.

## 문제 B — sender를 늘렸는데 429와 queue age가 늘어난다

실제 SaaS quota를 소진하지 않습니다. 승인된 기존 정제 오류 자료 또는 로컬 transport에서 429/timeout을 재현하여 retry 정책을 검사합니다. endpoint 선택, project 전체 한도, user/device별 편중, proxy가 throttle 정보를 전달하는지, 월간 volume 계약을 각각 확인합니다. API마다 목적·제한이 다르며 최신 숫자를 모든 plan에 적용하지 않습니다. [API 선택](https://amplitude.com/docs/faq/api-choice)

관측할 것은 accepted event/s와 attempted request/s, retry 비율의 분모, oldest unsent age, per-ID skew, rejected/unknown 수, payload byte, SDK/app version별 변화입니다. SDK가 내부 queue age를 노출하지 않으면 자신의 원장 age를 사용하고 SDK 내부 지표라고 부르지 않습니다.

worker/concurrency를 baseline으로 되돌리고 backoff·batch·partition 정책 중 원인 하나를 검토합니다. 응답이 불확실한 event는 원장에 남깁니다. 복구는 retry 폭주 중단·안전한 처리율/대기 추세·정확한 ID/값·업무 분석 회복이며 “노드 2배”는 SaaS 한도 해결책이 아닙니다.

## SDK rollout의 가드레일

| 단계 | 정상·음성 검사 | rollback 경계 |
| --- | --- | --- |
| 웹 신규 SDK/config | manual 정상 event, navigation, consent·autocapture off, login/logout | 이전 검토 revision과 설정 복귀; 기존 event는 취소되지 않음 |
| 모바일 신규 app/SDK | foreground/background, offline/reconnect, instance/storage, identity | app 배포 복귀만으로 이미 설치된 모든 단말이 즉시 바뀌지 않음 |
| tracking plan/chart 변경 | v1/v2 compatibility·분모/집합·시점·source 별 검산 | tracking plan, app, chart 각각의 revision을 별도 복원 |
| remote config/plugin | 실제 유효 설정·변경 수신 시점·금지 신호 | 원격값 캐시·단말 offline을 고려; 명목 설정만으로 판정 금지 |

이 LAB에서 회사 release·remote config·feature flag는 수정하지 않습니다. 작은 SDK 시험 앱 사본과 합성 run만 사용합니다. sample chart/SDK canary가 정상이어도 모든 사용자·OS·권한·region을 검증한 것은 아닙니다.

## 심화 완료 조건

backfill 전후 정확한 ID/업무 값·user 집합·new-user 날짜·동일 정의 chart를 대조합니다. 중단/재개·unknown·미확인 lag와 되돌릴 수 없는 영향을 문서화합니다. 관측하지 못한 SaaS storage/replica 상태는 추정하지 않고, 공급자 문의가 필요하면 최소 정제 evidence와 질문을 준비하되 전송은 별도 승인받습니다.
