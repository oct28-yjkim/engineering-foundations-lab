# Amplitude LAB 검증 기록

검증일 **2026-10-04**. 이 기록은 제공 코드·문서의 검증 범위이며 Amplitude 운영 검증 완료 보고서가 아닙니다. 회사 계정·API key·실제 사용자 데이터에는 접근하지 않았고 수집 endpoint로 이벤트를 전송하지 않았습니다.

## 수행한 검사

| 대상 | 결과 | 이 결과가 증명하지 않는 것 |
| --- | --- | --- |
| HTTP fixture·계약·안전장치 | Python 3.12.14에서 단위 테스트 22개 통과; `-O`에서도 같은 22개 통과 | 실제 HTTP 수집·dedup·identity·차트 결과 |
| 웹 controller·설정·입력 검증 | Node.js 24.19.0에서 테스트 11개 통과 | 실제 브라우저 SDK·Network·SaaS 동작 |
| JavaScript 구문 | `app.mjs`, `core.mjs`의 `node --check` 통과 | DOM 렌더링·CSP 적용·CDN 로딩 성공 |
| 공개 SDK 식별 | 공식 registry의 Browser SDK 2.47.2, CDN HTTP 200, tag의 peeled SHA 확인 | upstream suite 전체 실행·SDK 런타임 검증 |
| 고정 소스 검토 | init/identity/track/flush API, remote config·diagnostics·storage 설정과 queue/opt-out 경계 확인 | SaaS 서버 구현·모바일 SDK의 동일한 보장 |
| 공식 문서·소스 URL | Amplitude 트랙의 공식 URL 38개 HTTP 200; 의심 경로의 본문 추가 확인 | 모든 문서의 실행 시점 최신성·회사 plan에서 기능 제공 |
| 저장소 문서 연결 | Markdown 285개·내부 링크 1,995개의 대상/앵커와 fence 검사 오류 0개 | 외부 페이지 내용·실제 화면 렌더링 |
| 실행 안내 구문 | Amplitude의 PowerShell 코드 블록 1개 parse 오류 없음; `git diff --check` 통과 | 예제의 실제 외부 전송 실행 |

HTTP 테스트는 환경과 전송을 mock하고 socket 연결도 차단합니다. 웹 테스트는 fake SDK를 사용하는 controller 검사입니다. 둘 다 실제 제품의 장애 재현·복구 증거로 제출하지 않습니다. sandbox의 `node --test` 자식 process 생성이 거부되어 동일 테스트 파일을 Node에서 직접 실행했습니다.

소스 기준은 [Browser SDK 2.47.2의 고정 commit](https://github.com/amplitude/Amplitude-TypeScript/tree/21b55e2576a33ca7b64d0136bc83e0389a9098ad)입니다. 자동 수집·원격 설정·진단을 끄고 저장소를 메모리로 제한한 것은 이 LAB의 설정이며 제품 기본값이라는 뜻이 아닙니다.

특히 `setOptOut(true)`와 LAB 중지는 **이미 queue에 들어간 이벤트·진행 중 요청의 취소나 서버 데이터 삭제를 보장하지 않습니다.** 5분 제한은 새 LAB 동작의 허용 시간이지 모든 네트워크 요청의 종료 시한이 아닙니다. 소스 검토에서 확인한 이 한계를 앱 안내와 운영 지침에 반영했습니다.

## 재실행 명령

저장소 루트에서 실행합니다. 아래 검사는 key 없이 실행하며 실제 전송을 하지 않습니다. Python 3.10+와 현재 Node.js 런타임을 별도로 준비합니다.

```text
python -B -m unittest discover -s observability/amplitude/labs -p test_http_lab.py -v
python -B -O -m unittest discover -s observability/amplitude/labs -p test_http_lab.py -v
node observability/amplitude/labs/browser/test_core.mjs
node --check observability/amplitude/labs/browser/app.mjs
node --check observability/amplitude/labs/browser/core.mjs
python -B observability/amplitude/labs/http_lab.py --plan
```

`--plan`은 합성 원장과 기대 결과를 만드는 준비 단계입니다. HTTP 10-event fixture의 `4 → 3 → 2`와 웹 정상 3-event 실습의 `1 → 1 → 1`, [4강](../lessons/04-analysis-semantics.md)의 별도 분석 예제는 다른 입력 집합이며 결과를 섞지 않습니다.

## 아직 수행하지 않은 것

- 브라우저에서 페이지 렌더링·실제 SDK 초기화·CSP/네트워크/queue·전송 callback 관측
- Amplitude 테스트 프로젝트의 수집, 사용자 병합·session, dedup, funnel/retention·cohort 계산 검산
- 웹 offline/reconnect·중복 계측·로그아웃·consent 사건의 실제 재현과 회복 확인
- iOS/Android 앱 build·실기기/simulator·background/offline/lifecycle 실험
- 실제 quota/429·backfill·다운스트림 audience/알림·대규모 비용/확장 시험

실제 제품 검증은 [환경 준비](../environment.md) 후 [기본 LAB](README.md)과 [모바일 LAB](mobile-lab.md)에서 수동 수행합니다. 별도 시험 프로젝트·합성 ID·작은 입력으로 시작하고 [기록 양식](../../../operations/incident-report-template.md)에 source/SDK version·region·chart 정의·입력·관측·회복 결과를 남깁니다. 기존 검증 기록을 덮어쓰지 않고 자신의 실행 일시와 환경을 분리해 기록합니다.
