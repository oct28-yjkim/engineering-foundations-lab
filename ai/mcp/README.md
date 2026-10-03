# MCP: Zero to Hero → Protocol, Trust & Tool Execution Engineering

Model Context Protocol을 함수 연결법에서 출발하여 **프로토콜 계약·권한 경계·장애 후 실행 결과·구현 검증**까지 연구하는 28주·14모듈·7강 과정입니다. “연결 성공”을 “안전한 agent”와 같은 뜻으로 쓰지 않습니다. 기본은 실제 client/server 실행·요청 관측·오류 진단이며 GPU·모델 API·외부 계정은 필수가 아닙니다.

기준일은 **2026-10-04**, 프로토콜은 **2026-07-28**, 선택 Python SDK는 **2.3.0**입니다. SDK 버전과 프로토콜 revision은 서로 다른 축입니다. 이 revision의 core는 요청별 metadata를 사용하는 stateless 방식이며, 2025-11-25 및 그 이전의 `initialize` 중심 흐름은 별도 비교 대상으로 다룹니다. [공식 버전 규칙](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning), [SDK 릴리스](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)를 함께 확인합니다.

## 시작 순서

1. [환경·안전 범위](environment.md)와 [커리큘럼](curriculum.md)을 읽습니다. Python async·프로세스·JSON Schema·HTTP/TLS·OAuth·분산 시스템 기초가 부족하면 별도 보충합니다.
2. [실제 SDK 실습](labs/README.md)으로 정상/거부 기준선을 확인하고 [운영·트러블슈팅](operations.md)에서 지연·오류 층·timeout·종료를 진단합니다. 원리 모형 4개는 선택 보조자료입니다.
3. 관측한 실패를 강의·[소스 지도](source-reading.md)의 규격·구현·시험에 연결합니다. [호환성 지도](compatibility.md)로 현대/이전 규격과 구현별 차이를 대조합니다.
4. [평가표](assessment.md)에 실행한 범위, 설계만 한 범위, 미검증 환경을 구분하여 제출합니다.

| 모듈 | 강의 | 핵심 질문 |
| --- | --- | --- |
| MC01–02 | [아키텍처·신뢰·revision·JSON-RPC](lessons/01-architecture-revisions.md) | 모델의 요청과 실행 권한, 현대/이전 규격을 어떻게 분리하는가? |
| MC03–04 | [tool 계약·resource·prompt·캐시](lessons/02-contracts-context-cache.md) | 잘 정의된 schema가 실제 업무 결과와 사용자 격리를 보장하는가? |
| MC05–06 | [stdio·Streamable HTTP·프레이밍·라우팅](lessons/03-transports-routing.md) | 메시지가 도착했다는 것과 올바른 주체에게 처리됐다는 것은 같은가? |
| MC07–08 | [OAuth·동의·tenant·prompt injection](lessons/04-authorization-trust.md) | 인증된 호출에서도 어떤 데이터와 작업을 거부해야 하는가? |
| MC09–10 | [MRTR·elicitation·취소·재시도·extensions](lessons/05-mrtr-recovery-extensions.md) | 추가 입력과 응답 유실 이후 중복 실행을 어떻게 통제하는가? |
| MC11–12 | [SDK 내부·conformance·관측·배포](lessons/06-sdk-observability-operations.md) | SDK의 편의 기능 뒤에 있는 실제 요청·상태·실패 경로는 무엇인가? |
| MC13–14 | [상호 운용·이전·2주 미니 연구](lessons/07-interop-migration-research.md) | 한 구현의 성공을 다른 host·revision까지 일반화할 수 있는가? |

권장 시간은 **28주 × 주 12시간 = 336시간**입니다. MC14는 기존 자산을 사용하는 2주 연구이며, [8주 MCP 경계·복구 캡스톤](../../capstones/mcp-tool-boundary-recovery.md)은 별도 확장 과정입니다. 기간이나 테스트 수 자체를 숙련도의 보장으로 사용하지 않습니다.

## 제공물과 증거 경계

| 범위 | 제공 또는 추가 과제 | 증명하지 않는 것 |
| --- | --- | --- |
| OFFLINE | `revision-gate`, `tool-contract`, `request-ledger`, `principal-cache` CPU 모형 | MCP 전체 conformance, OAuth 보안, JSON Schema 전체, 실제 네트워크 장애 |
| LOCAL-SDK | 고정 SDK 기반 선택 stdio client/server fixture | HTTP·TLS·OAuth·다중 tenant·특정 LLM host와의 호환성 |
| HTTP-LAB | 합성 자산으로 별도 HTTP/SSE·proxy·Origin·metadata 실험 | 배포 환경 전체의 공격 방어·확장성 |
| AUTH-LAB | 전용 issuer·resource·scope·동의·tenant 음성 대조군 | 모델의 자연어 판단만으로 권한 보장 |
| RECOVERY-LAB | 업무 원장·deadline·재시도·MRTR·선택 tasks 확장 | JSON-RPC ID만으로 exactly-once 실행 |
| BUILD/INTEROP | 고정 소스 시험·다른 구현과 feature matrix | 미실행 SDK·host·확장 지원 |

실행 상태와 테스트 수는 [검증 기록](labs/validation.md)에 적습니다. 가벼운 모형이 다루지 않는 부분을 강의의 수동 실험과 구술 질문으로 명확히 남깁니다.

## 학습 중 반드시 지킬 경계

tool 설명·annotations·resource 내용·prompt template은 권한을 주는 명령이 아닙니다. roots도 OS sandbox가 아닙니다. MCP 연결 인증과 앱의 작업 승인, downstream 데이터 접근 권한은 각각 확인합니다. 실제 토큰·DB 암호·클라우드 키를 모델 prompt·tool 결과·trace에 싣지 않습니다. secret 사용 설계는 [OpenBao](../../security/openbao/README.md)와 [Vault](../../security/vault/README.md) 트랙으로 확장하되, 기본 실습에는 자격 증명을 넣지 않습니다.

현재 규격에서 Roots·Sampling·Logging은 Deprecated이고 Tasks는 선택 extension입니다. 새 구현에 deprecated 기능을 추가하는 대신 이전 시스템 분석·마이그레이션 과제로 다룹니다. 모든 기능이 모든 client에 지원된다고 가정하지 않습니다. [공식 변경 사항](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
