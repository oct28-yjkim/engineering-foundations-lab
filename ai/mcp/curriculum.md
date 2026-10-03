# MCP 28주 심화 커리큘럼

14모듈 × 2주 × 주 12시간 = **336시간**입니다. 모듈당 원리·공식 자료 6시간, 실험 10시간, 소스 추적 4시간, 분석·구술 4시간을 권장합니다. 외부 issuer·proxy·별도 SDK 빌드·다중 host 환경 구축 시간은 추가입니다.

## 모듈 지도

기본 실험은 [실제 SDK 실행·운영 진단](operations.md)입니다. 실험 10시간은 요청 기준선·오류 층·지연/종료·회복 관측에 우선 사용하고 원리 모형은 선택 보충으로 둡니다. MC01–02 process/revision, 03–04 schema/cache, 05–06 transport, 07–08 auth, 09–10 timeout/retry, 11–12 계측/운영, 13–14 호환성/source 결과를 실제 증거와 연결합니다. 학습자가 추가할 계측·HTTP 환경은 제공 SDK smoke와 구분합니다.

| 모듈 / 주 | 선수 조건 | 핵심 질문 | 최소 제출물 |
| --- | --- | --- | --- |
| MC01 / 1–2 | Python·HTTP·프로세스 기초 | [host/client/server·신뢰 경계](lessons/01-architecture-revisions.md#mc01) | 자산·주체·데이터 이동·실행 권한 지도 |
| MC02 / 3–4 | 01, JSON-RPC | [revision·metadata·오류 계약](lessons/01-architecture-revisions.md#mc02) | modern/legacy/dual-era 행렬·메시지별 독립 oracle |
| MC03 / 5–6 | 02, JSON Schema | [tool 입력·결과·오류·부작용](lessons/02-contracts-context-cache.md#mc03) | schema/업무 규칙 분리·양성/음성 fixture |
| MC04 / 7–8 | 03, 캐시·URI | [resource·prompt·pagination·cache](lessons/02-contracts-context-cache.md#mc04) | 주체별 결과·TTL 경계·cursor 변경 원장 |
| MC05 / 9–10 | 02, OS·async | [stdio·프레이밍·프로세스 수명](lessons/03-transports-routing.md#mc05) | 분할 입력·stdout 오염·EOF·종료 결과 |
| MC06 / 11–12 | 05, HTTP/TLS | [HTTP/SSE·metadata·proxy](lessons/03-transports-routing.md#mc06) | header/body 일치·잘못된 Origin·끊김 검산 |
| MC07 / 13–14 | 06, OAuth·JWT 기초 | [issuer·audience·scope·동의](lessons/04-authorization-trust.md#mc07) | token 목적지·issuer 변경·scope 부족 거부 |
| MC08 / 15–16 | 03–07, 접근 제어 | [tenant·prompt injection·비밀](lessons/04-authorization-trust.md#mc08) | 합성 악성 데이터 대조군·자산별 권한 판정 |
| MC09 / 17–18 | 02, 07–08 | [MRTR·elicitation·입력 검증](lessons/05-mrtr-recovery-extensions.md#mc09) | 추가 입력·거절·재시도·state tampering 결과 |
| MC10 / 19–20 | 05–09, 재시도·트랜잭션 | [취소·deadline·중복·extensions](lessons/05-mrtr-recovery-extensions.md#mc10) | 요청/업무 원장·불확실 결과·확장 fallback |
| MC11 / 21–22 | 01–10, Python async | [SDK source·schema·conformance](lessons/06-sdk-observability-operations.md#mc11) | 5symbol·2자료구조·1실제 test·누락 범위 |
| MC12 / 23–24 | 06–11, 운영·관측 | [trace·backpressure·배포·회복](lessons/06-sdk-observability-operations.md#mc12) | 지연 분해·자원 상한·redaction·장애 원장 |
| MC13 / 25–26 | 01–12 | [상호 운용·revision·SDK 이전](lessons/07-interop-migration-research.md#mc13) | client/server/revision/기능별 호환 행렬 |
| MC14 / 27–28 | 13, 앞선 fixture | [2주 최소 연구](lessons/07-interop-migration-research.md#mc14) | 한 경로·한 개선·실패 2개·독립 검산·한계 |

## 공통 실험 계약

업무 질문 → 신뢰/자산 → 규격 revision → 불변식 → 실패 모델 → 수작업 기대값 → 실행 → 관측 → 경쟁 가설 → 구현 근거 → 한계 순으로 제출합니다. [공통 실험 방법](../../databases/shared/experiment-method.md)을 재사용합니다.

```text
run_id / protocol revision / SDK version+source revision / transport / host version
feature and extension identifiers / claimed support / observed support
principal alias / tenant alias / issuer alias / audience / scope / policy revision
JSON-RPC request ID / method / tool or URI alias / schema revision
business operation key / payload digest / expected effects / observed effects
deadline / clock basis / attempt / completion or unknown-outcome reason
cache authorization context / TTL / cursor alias / invalidation reason
MRTR input IDs / consent outcome / state-verification result (not state contents)
HTTP and RPC status / tool isError / schema validation / business oracle
latency phases / resource limits / sanitized trace references / untested boundaries
```

출력 원문이나 access token을 그대로 transcript에 남기지 않습니다. JSON-RPC ID는 응답 상관용, 업무 operation key는 중복 방지용이며 서로 대체하지 않습니다. 같은 실패를 HTTP 오류·RPC 오류·tool 실행 오류·업무 불일치 중 어디에서 관측했는지 분리합니다. deadline 초과나 취소 요청만으로 외부 부작용이 없었다고 결론 내리지 않습니다.

## 기준 revision과 자료 읽기

현대 규격은 2026-07-28, 이전 방식 비교는 2025-11-25입니다. [공식 revision 규칙](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)을 먼저 읽고, 각 강의에서 해당 기능의 공식 페이지와 고정 [소스 지도](source-reading.md)를 대조합니다. 블로그의 발행일이나 SDK major version만으로 wire protocol을 추측하지 않습니다.

각 규정은 MUST/SHOULD/MAY·이 revision의 요구·구현 선택·우리 실험의 추가 정책으로 분류합니다. 예컨대 우리 fixture의 입력 길이 제한을 MCP 전체가 강제하는 값으로 설명하지 않습니다. 규격과 SDK가 어긋나는 결과는 규격 조항·최소 재현·실제 revision을 함께 기록하고 임의로 일반화하지 않습니다.

## Gate

- G1, MC01–04: 실행 권한·revision·계약·캐시. tool annotation을 권한으로 사용하거나 권한 context를 건너뛴 private cache를 허용하면 미통과입니다.
- G2, MC05–08: transport·인증·tenant. stdout 오염, 잘못된 audience, 다른 tenant 데이터, token passthrough를 놓치면 미통과입니다.
- G3, MC09–12: 추가 입력·중복·운영. 취소를 rollback으로 보거나 stateless protocol을 무상태 업무 처리로 오해하면 미통과입니다.
- G4, MC13–14: 상호 운용·증거. mock/CPU/한 SDK의 성공을 전체 conformance나 모든 host 지원으로 표시하면 미통과입니다.

[평가표](assessment.md)의 정확성·원리/소스·실험/반증·운영/재현성은 각 25점입니다. **80/100 이상, 각 15/25 이상, 필수 gate 전체 통과**가 선언 범위의 완료 조건입니다. OFFLINE만 실행해도 학습 결과는 제출할 수 있지만 AUTH·HTTP·RECOVERY·BUILD/INTEROP까지 실행 완료로 표시하지 않습니다.

MC14는 이미 만든 fixture에서 결론 하나를 검증하는 2주 연구입니다. 새로운 issuer, 다중 지역 배포, 모델 비교 평가, 여러 DB까지 한꺼번에 추가하지 않습니다. 넓은 운영 통합은 [8주 캡스톤](../../capstones/mcp-tool-boundary-recovery.md)으로 분리합니다.
