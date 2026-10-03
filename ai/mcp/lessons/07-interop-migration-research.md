# 07. 상호 운용·마이그레이션·2주 미니 연구

[커리큘럼](../curriculum.md) · [평가표](../assessment.md) · [실습](../labs/README.md) · [소스 지도](../source-reading.md)

<a id="mc13"></a>
## MC13: 서로 다른 세대와 구현을 연결한다

선수 조건: MC01–12. 호환성은 “MCP 지원”이라는 한 칸이 아닙니다. client와 server 각각의 revision·transport·capability·extension·인증·schema 계약을 연결하는 관계입니다. 아래는 실제 실행 전에 작성할 연구 행렬입니다. 빈칸은 성공이 아니라 미검증으로 둡니다.

| 비교 축 | baseline | 비교 대상 | 판정 증거 |
| --- | --- | --- | --- |
| protocol era | modern 2026-07-28 | legacy 2025-11-25 / dual-era | discovery·metadata·handshake trace |
| SDK | 공식 Python 2.3.0 | 별도 고정 구현 1개 | wire shape·오류·cancel cleanup |
| transport | 로컬 stdio | 전용 HTTP fixture | framing·headers·JSON/SSE·종료 |
| host | 모델 없는 test client | 선택 LLM host 1개 | 권한·schema·동의·결과 표시 |
| 기능 | tool/resource/prompt | MRTR 또는 extension 1개 | capability·result shape·fallback |
| 인증 | credential 없는 합성 fixture | 전용 HTTP auth lab | issuer/audience/scope/tenant 거부 |

modern 규격과 earlier initialization 기반 revision은 명시적으로 구별합니다. dual-era가 아닌 현대 전용 client가 legacy server에 붙었다고 자동으로 호환되는 것은 아닙니다. transport별 probe와 fallback은 [공식 versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)을 기준으로 구현하고, 권한 실패를 protocol fallback 성공으로 덮지 않습니다.

### 실험

1. [LOCAL-SDK 검증 기록](../labs/validation.md)을 baseline으로 고정합니다. 다른 SDK나 host는 실제 버전과 설치 출처를 확인한 뒤 별도 환경에서 하나씩 추가합니다.
2. 동일한 synthetic tool에 정상 입력·잘못된 type·unknown name·empty/null output·거절·timeout을 보냅니다. server와 client 양쪽의 결과 해석을 비교합니다.
3. 기능을 일부 제거한 server, capability를 일부 줄인 client를 만듭니다. 지원하지 않는 확장을 조용히 실행하거나 오류를 성공으로 축약하지 않습니다.
4. 이전 spec의 `initialize`, server-initiated request, session ID, GET stream, Tasks 실험 기능을 현대 계약에 각각 대응시킵니다. 이름 변경만으로 변환할 수 없는 상태·취소·재시도 의미를 찾아냅니다.
5. SDK v1 API와 v2 API의 소스/배포 변경을 wire revision 변경과 별개로 계획합니다. dependency bump만 한 배포와 protocol mode를 바꾼 배포를 분리하여 롤백 가능성을 점검합니다.
6. 발견된 불일치를 최소 fixture로 줄입니다. 규격 조항·정확한 소스 revision·request/result·환경·실행 여부를 제출하고, 근거 없이 특정 client 전체를 “미지원”이라 하지 않습니다.

제출물: 실제 행렬, 실패 원인 분류, 보존해야 할 업무 불변식, migration 순서, 롤백/중단 조건. 확장 지원은 [공식 extension 설명](https://modelcontextprotocol.io/extensions/overview)과 해당 구현의 고정 source를 각각 확인합니다.

<a id="mc14"></a>
## MC14: 결론 하나를 반증 가능한 연구로 만든다

기간은 **2주·24시간**, 새 환경을 넓히지 않고 앞선 fixture를 재사용합니다. 주제 하나·개선 하나·실패 조건 둘·독립 oracle 하나를 선택합니다.

| 후보 | 가설 | 실패 조건 둘 | 독립 oracle |
| --- | --- | --- | --- |
| private cache | auth context와 정책 revision을 분리하면 누출을 막는다 | token 교체·scope 축소 | principal별 허용 결과 집합 |
| 업무 재시도 | durable key를 사용하면 특정 중복 부작용을 줄인다 | 응답 유실·동시 재전송 | 독립 업무 원장 count+payload |
| schema 갱신 | stale tool contract를 감지하면 잘못된 dispatch를 막는다 | header/body 차이·구버전 목록 | handler 진입/거부 기록 |
| MRTR state | 주체·인자·시간 결합이 잘못된 state 재사용을 막는다 | 다른 사용자·만료 재전송 | 정책 판정+side effect 원장 |
| stdio 종료 | bounded cleanup이 orphan process를 줄인다 | handler 실패·client timeout | 소유 PID·대기 queue·종료 결과 |

### 2주 진행

- 1–2일: 업무 불변식·위협·규격 범위·예상 결과를 확정합니다. 결과를 보기 전에 성공/실패 기준을 씁니다.
- 3–5일: baseline·독립 oracle·최소 실패 재현을 완성합니다. 구현과 같은 함수를 oracle로 다시 부르지 않습니다.
- 6–8일: 수정 하나만 적용하고 반복합니다. 권한 범위·fixture·부하·시계 조건을 고정합니다.
- 9–10일: 음성 대조군·자원 상한·회귀·다른 실행 순서를 검증합니다.
- 마지막: 동료 재현·구술·한계·후속 실험을 정리합니다. 실제 작업일 기준으로 시간 배분을 조정하되 총 24시간의 범위를 넘으면 과제를 축소합니다.

성능 보고서는 동일한 업무 결과와 권한 검사를 유지해야 합니다. 안전성 보고서는 모든 가능한 공격 방어가 아니라 선언한 합성 실패 모델에 대한 결과입니다. 표본 수, 반복 횟수, cold/warm cache, p50/p95/p99, 실패/거부율, 메모리/queue 상한, 재시도 횟수를 같이 적습니다.

최종 산출물은 한 페이지 문제 정의, 재현 fixture, 증거표, 소스 근거, 반례, 미검증 범위입니다. OFFLINE만 실행했으면 프로토콜 모델 연구로, LOCAL-SDK까지 실행했으면 그 구현/transport까지 검증한 것으로 표시합니다. 운영 보안이나 모든 host의 호환성으로 확대하지 않습니다.

추가 issuer·다중 tenant·proxy·durable 업무 저장소·실제 모델 평가까지 통합하려면 별도 [8주 MCP 경계·복구 캡스톤](../../../capstones/mcp-tool-boundary-recovery.md)을 진행합니다. 인증서·토큰·실제 고객 데이터·운영 API를 연구 편의를 위해 끌어오지 않습니다.
