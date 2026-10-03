# MCP 검증 기록

확인일 **2026-10-04**. Windows·CPython **3.12.14**에서 검사했습니다. Python 3.10+을 대상으로 하지만 모든 minor/OS 조합에서 실행한 것은 아닙니다.

## 실행한 검사

| 검사 | 결과 | 증거 범위 |
| --- | --- | --- |
| CPU `--lab all` | 4개 oracle 통과, 일반/`-O` 각각 | revision·tool 계약·요청 원장·principal cache의 제한된 모형 |
| `test_offline_lab.py` | 89개 PASS, 일반/`-O` 각각 | 독립 literal 기대값·schema 경계·불변성·인가 context·재시도 |
| `test_sdk_lab.py` | 62개 PASS, 일반/`-O` 각각 | mock SDK·순수 합성 handler·결과 검사·환경/opt-in·이중 version guard |
| 신규 전체 | 151개 PASS, 일반/`-O` 각각 | 같은 테스트 151개를 두 모드로 실행; 실제 SDK 결과와 구분 |
| 실제 SDK stdio | **10개 검사 통과**, 일반 및 `-O` runner 각각 | SDK/type 2.3.0, protocol 2026-07-28, owned child server와 실제 통신 |
| 격리 venv `pip check` | PASS | 설치된 의존성 요구사항 충돌 없음, 전체 supply-chain 보안 검증 아님 |
| 프로세스 종료 | 실행 후 해당 `sdk_server.py` process 0개 | 정상 종료 경로의 잔존 프로세스 확인, 강제 kill 모든 경우의 증명 아님 |
| 기존 security·LLM·IaC 회귀 | 각각 132·50·82개 PASS | 기존 CPU/mock 실습 유지 |
| 소스 링크 | 고정 파일 참조 35개 확인 | spec/SDK Git tree의 파일 존재; upstream test 실행 아님 |
| Markdown·내부 링크 | 225문서·1,357링크, 오류 0 | 파일/anchor·code fence, MCP 7강·14 module anchor 확인 |

`-O` native 검사는 runner를 최적화 모드로 실행한 것입니다. child는 고정 launcher의 `-I -B -u`로 실행하며 이 검사에서 child까지 `-O`로 실행했다고 주장하지 않습니다. 핵심 CPU/runner oracle은 `assert` 대신 예외를 사용합니다.

## 실제 SDK 환경과 결과

전역 Python에는 `mcp`가 없었습니다. 기존 환경을 바꾸지 않고 Git ignore된 `lab-workspaces/mcp-sdk-2.3.0` venv를 생성한 뒤 공식 PyPI의 binary wheel로 `mcp==2.3.0`을 설치했습니다. 설치는 네트워크를 사용했으며 실제 lab은 모델·외부 API·HTTP endpoint·OAuth 계정·업무 데이터에 접속하지 않았습니다. 가상환경은 재실험을 위해 로컬에 남겨 두었고 Git에 포함하지 않았습니다.

첫 제한 환경 실행은 Windows 로컬 pipe/subprocess 권한 문제로 `PermissionError`가 발생했습니다. 동일한 고정 합성 서버/클라이언트만 승인된 로컬 실행으로 재검증하여 통과했습니다. 실패한 첫 시도를 protocol 거부 oracle의 성공으로 집계하지 않았고, host 보안 설정이나 현재 앱 MCP 설정을 변경하지 않았습니다.

실측 정답은 tool `widget-a` 수량 7·`widget-b` 수량 0, JSON resource의 SKU 목록, 고정 prompt, 필수 인자/enum 오류, unknown tool의 SDK tool-error, missing resource의 RPC **-32602**, 오류 후 정상 호출입니다. unknown tool은 명세의 일반 규칙과 구별해야 하는 SDK 구현 관측이며 [실습 안내](README.md)에 차이를 기록했습니다.

다음은 이 실행 시점의 주요 의존성입니다. 직접 pin 외 의존성은 미래 설치 때 달라질 수 있으며 universal lockfile이나 보안 승인 목록이 아닙니다.

| 패키지 | 관측 버전 |
| --- | --- |
| mcp / mcp-types | 2.3.0 / 2.3.0 |
| anyio | 4.15.1 |
| pydantic / pydantic-core | 2.13.5 / 2.46.5 |
| jsonschema | 4.26.0 |
| httpx2 / httpcore2 | 2.13.1 / 2.13.1 |
| opentelemetry-api | 1.45.0 |
| starlette / sse-starlette | 1.7.0 / 3.5.0 |
| pywin32 | 312 |

자신의 환경에서는 [설치 지침](../environment.md)과 함께 `python -m pip freeze`로 전체 전이 의존성을 기록합니다. `mcp`와 `mcp-types` 중 하나라도 지정 버전과 다르면 runner/server guard가 거부합니다.

## 검증하지 않은 것

실제 Streamable HTTP/SSE·TLS·proxy·Origin/Host·OAuth login/token/audience·SSRF 방어·MRTR 승인·Tasks/Apps·cross-SDK/host·classic 실제 wire·실제 모델 tool 선택·운영 부하/성능·crash durability·모든 OS cleanup·upstream 전체 tests·공식 conformance harness는 실행하지 않았습니다.

stdio 동일 SDK 양끝의 10개 검사로 이 항목들을 대신하지 않습니다. CPU·mock·실제 fixture·심화 과제·설계만 완료한 항목을 별도 표시합니다. [호환성 표](../compatibility.md)와 [소스 지도](../source-reading.md)의 기대/연구 질문을 실측 결과로 간주하지 않습니다.
