# 5강 — 계측 품질, 모니터링, consent와 거버넌스

[커리큘럼](../curriculum.md) · AM09–AM10 · [운영 카드](../operations.md)

## 정상 기능: 무엇이 수집돼야 하는가

정상 웹 SDK run의 수동 업무 원장과 실제 event를 같은 source/run으로 묶습니다. 모바일은 플랫폼별 SDK·app revision·foreground/network 조건을 별도 기록합니다. 분석을 보고 있는 시스템만으로 자기 누락을 판정하지 않고 앱의 합성 행동 원장을 독립 분모로 사용합니다.

| 단계 | 질문 | 관측 자료 |
| --- | --- | --- |
| offered | 동의된 합성 행동 중 계측하기로 한 것은 몇 개인가? | 앱의 업무 marker 원장 |
| attempted | 어떤 event를 몇 번 전송 시도했는가? | 정제된 SDK/transport attempt와 event ID |
| accepted/rejected/unknown | 응답과 payload 계약으로 어디까지 아는가? | HTTP 상태·SDK callback·상세 오류의 비민감 분류 |
| visible | 어느 시점·프로젝트·필터에서 확인했는가? | User Lookup/event stream·chart·선택 export |
| analyzed | 같은 정의에서 업무 정답과 맞는가? | event/user 집합·속성·시간·차트 정의 |

이 항목들은 학습용 논리 관측치이지 Amplitude가 동일한 이름의 server metric을 제공한다는 뜻이 아닙니다. accepted 수, event 총수, unique 사용자, 시도 요청 수의 분모를 섞지 않습니다.

## 품질과 모니터링은 수집 정책과 다르다

Observe는 도착한 event와 tracking plan을 비교하여 품질 상태를 보여줍니다. upstream에서 차단/삭제된 event는 Observe가 볼 수 없으므로 초록 상태만으로 누락 0을 증명하지 못합니다. 원래 source·version·선택 시간 창을 기록합니다. [Observe](https://amplitude.com/docs/data/validate-events)

Schema 정책은 unexpected event/property를 어떻게 처리할지 정합니다. 관측 경고와 ingestion 거절은 다른 동작이며 property 거절과 event 전체 거절도 구분합니다. 기능 제공 여부·권한은 실제 plan에서 확인합니다. 운영 schema를 테스트 목적으로 강제 reject로 바꾸지 않습니다. [Schema 보호](https://amplitude.com/docs/data/configure-schema)

실제 플랫폼에서 읽을 수 있는 품질 status·invalid/전체 event·source별 volume, synthetic freshness, SDK 오류·동의된 행동 대비 계측 비율을 같은 관측 창에서 확인합니다. 큰 변화에는 배포 revision·autocapture/remote config·network/lifecycle 분포·분석 조건 diff를 붙입니다. “품질 문제율 0”과 “표본 없음”을 구분합니다.

## 문제 A — event가 줄었는데 제품 문제인가 수집 문제인가?

정상 run과 제한된 비교 run에서 synthetic marker 하나의 계측 누락 또는 잘못된 이름을 사용합니다. 제공 앱이 임의 fault 옵션을 제공하지 않으면 별도 사본의 작은 변경 과제입니다. 무단으로 회사 feature flag·tracking plan을 바꾸지 않습니다.

원장→SDK 호출→transport→품질 화면→chart 순서로 같은 marker를 찾습니다. 행동 감소, init/consent 조건, SDK queue, schema, 잘못된 query filter를 경쟁 가설로 둡니다. 앱 수정 전후의 정상 계약을 새 run으로 검산하고 누락 발생 구간을 보존합니다. 이미 누락된 event를 추정해 재생성하지 않습니다.

## 문제 B — SDK 설정은 껐는데 예상 외 정보가 보인다

기본 시험 앱은 동의 전 SDK 다운로드·init·행동 queue를 시작하지 않습니다. 선택 SDK별로 consent 후 수집 허용, 철회 후 중지, 재동의의 새 정상 run을 확인합니다. **opt-out, identity storage 없음, unsent event storage 없음, autocapture off는 다른 옵션/경계**입니다. 실제 payload/저장/전송을 각각 검사합니다. [Browser consent 관리](https://amplitude.com/docs/sdks/analytics/browser/cookies-and-consent-management)

가짜 canary를 포함한 **시험 UI**만 사용합니다. 금지 값은 전송 전 차단된다는 기대를 먼저 만들고, 허가 없는 외부 송신으로 누출을 실증하지 않습니다. remote config, plugin, tag manager, manual/autocapture 중복 publisher, Replay/network tracking 여부를 확인합니다. 기본 LAB에 포함되지 않은 신호는 검사 완료로 표기하지 않습니다.

예상 외 송신이 보이면 발생기/SDK 호출부터 중단하고 저장된 synthetic 증거만 최소 보존합니다. 차트에서 숨기는 것을 외부 수집 중단이나 개인정보 삭제로 취급하지 않습니다. 실제 사고의 credential rotation·삭제·법무/보안 통지는 사용자/조직의 별도 승인 절차입니다.

## 거버넌스의 정상 운영

각 event에 owner·업무 정의·schema version·배포 source·소비 chart·retention/수신 목적지를 연결합니다. 바뀐 필드는 publisher와 chart consumer의 호환성 표를 거쳐 승인합니다. cohort activation, 외부 destination, 이메일 경보는 다른 사람/시스템에 영향을 줄 수 있어 이 LAB에서는 연결하지 않습니다.

event 숨김, 미래 수집 차단, event 관리 삭제, user privacy 삭제는 범위와 복구 가능성이 서로 다릅니다. “삭제”라는 UI 문구만 보고 목적을 달성했다고 판정하지 않습니다. 이번 과정은 해당 기능을 실행하지 않고 영향·권한·증거·보존 계획을 설명하는 것으로 시작합니다. [공식 governance FAQ](https://amplitude.com/docs/data/troubleshooting/instrumentation-issues)

## 회복 oracle와 제출

원래 승인된 계측/consent 설정으로 **새 run**을 실행하고 허용 event ID/업무 값 일치, 금지 marker 외부 송신 0, 중복 publisher 없음, 해당 창의 품질/가시성 회복을 확인합니다. 실제 사용자 데이터가 섞이면 실습을 계속하지 않습니다.

제출은 source별 정상/증상 창, 비율 분모, 품질 상태·관측 사각, 설정 diff, 제한 조치, 남은 누락/unknown, 새 run oracle입니다. SaaS 내부 backlog·DB health는 제공되지 않으면 unknown입니다. 기술적 음성 검사 통과를 개인정보 법률 준수 인증으로 주장하지 않습니다.
