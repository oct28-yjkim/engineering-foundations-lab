# MCP 실습 — CPU 기본, 공식 SDK stdio 선택

[트랙](../README.md) · [환경·설치](../environment.md) · [호환성](../compatibility.md) · [검증 기록](validation.md)

모든 명령은 저장소 루트에서 실행합니다. 기본은 Python 3.10+ 표준 라이브러리이며 패키지·모델·API 키·Docker·외부 계정이 필요 없습니다.

## 1. 네트워크 없는 작은 모형

```text
python -B ai/mcp/labs/offline_lab.py --list
python -B ai/mcp/labs/offline_lab.py --lab all
python -B -m unittest discover -s ai/mcp/labs -p "test_*.py" -v
python -B -O -m unittest discover -s ai/mcp/labs -p "test_*.py" -v
```

| 모형 | 질문 | 경계 |
| --- | --- | --- |
| `revision-gate` | modern 요청별 metadata와 classic handshake를 섞으면 어디서 거부해야 하는가? | 두 revision의 제한된 판정, 전체 negotiation/transport 구현 아님 |
| `tool-contract` | schema 오류·tool error·RPC error·structured result가 어떻게 다른가? | 명시한 JSON Schema 부분집합, 일반 schema validator 아님 |
| `request-ledger` | 응답 순서·timeout·취소·RPC ID와 업무 key를 어떻게 분리하는가? | explicit clock·합성 원장, 실제 동시 실행·transaction·network 아님 |
| `principal-cache` | principal·authorization context·tenant·policy/catalog 변경 후 cache가 새면 어떻게 찾는가? | 신뢰된 synthetic identity 입력, 실제 OAuth/서명 검증 아님 |

[offline.md](offline.md)에 독립 정답과 반례가 있습니다. runtime oracle은 Python `-O`에서도 제거되지 않는 예외를 사용합니다. 테스트의 SDK 부분은 외부 의존성 없이 mock과 합성 함수로 검사하며, 실제 SDK 실행은 다음 단계입니다.

## 2. 선택: 공식 SDK로 실제 stdio 실행

[환경 안내](../environment.md)에 따라 **별도 venv**에 `requirements-sdk.txt`를 설치합니다. 전역 설치·host/앱 설정·현재 연결된 MCP 서버는 변경하지 않습니다. 네트워크가 필요한 것은 패키지 설치이며 fixture 자체는 외부 서버/API/모델을 호출하지 않습니다.

Windows에서 이미 해당 환경을 준비했다면:

```text
./lab-workspaces/mcp-sdk-2.3.0/Scripts/python.exe -B ai/mcp/labs/sdk_lab.py --check
./lab-workspaces/mcp-sdk-2.3.0/Scripts/python.exe -B ai/mcp/labs/sdk_lab.py --run-local
```

macOS/Linux는 같은 venv의 `bin/python`을 사용합니다. `--check`는 dependency metadata만 읽고 서버를 시작하지 않습니다. 인자 없는 실행·`--help`도 안내만 출력합니다. 실제 실행은 `--run-local`로 명시하며 고정 sibling `sdk_server.py`를 현재 Python의 child process로 시작합니다. 임의 URL·실행 파일·서버 경로를 받지 않습니다.

기준은 **SDK 2.3.0 / protocol 2026-07-28 / stdio**입니다. 자동 fallback 모드가 아니라 명시한 revision으로 실행하며 예전 `initialize` 예제를 섞지 않습니다. SDK와 `mcp-types`의 정확한 버전이 준비돼야 합니다. interpreter/OS/전이 의존성은 [검증 기록](validation.md)과 비교합니다.

## 3. 합성 fixture와 실제 정답

| 검사 | 실제 기대값 |
| --- | --- |
| tools/list | `lookup_inventory` 한 개, required `sku`, enum `widget-a`/`widget-b`, output schema와 hints |
| tools/call A | SKU `widget-a`, quantity **7**, warehouse `synthetic-east` |
| tools/call B | SKU `widget-b`, quantity **0**, warehouse `synthetic-west` |
| 필수 인자 누락 | `is_error=True`, `sku` 관련 tool error, 성공 structured content 없음 |
| enum 밖 인자 | `is_error=True`, `sku` 관련 tool error |
| unknown tool | 고정 SDK 구현의 `is_error=True`, `Unknown tool` 오류 |
| resource | URI `inventory://lab/catalog`, JSON `{"synthetic":true,"skus":["widget-a","widget-b"]}` |
| 없는 resource | SDK `MCPError`, RPC code **-32602** |
| prompt | `review_inventory` template 한 개, user message; 모델 호출 없음 |
| 오류 뒤 정상 호출 | A의 7개 재고를 다시 정확하게 읽음 |

구조화된 tool 결과와 JSON text fallback은 각각 literal 정답에 대조합니다. resource URI는 파일 경로나 외부 주소가 아니라 fixture 내부의 이름입니다. read-only hint를 믿어 안전한 것이 아니라, handler 구현이 오직 고정 합성 데이터를 읽기 때문에 이 실습의 쓰기 효과가 없습니다.

**unknown tool 오류는 구현 차이의 학습 사례입니다.** 현행 [tools 명세](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)는 unknown tool 같은 protocol 오류와 실행/입력 오류의 tool result를 구별합니다. 이 fixture가 사용하는 SDK 2.3.0 `MCPServer` 경로는 unknown tool을 tool error로 반환합니다. 이 관측을 명세의 일반 규칙으로 바꾸지 않고, 공식 conformance PASS라고 부르지 않습니다. wire·SDK 객체·호스트 UI가 같은 오류 표현을 쓰는지도 별도로 확인해야 합니다.

성공 출력은 `sdk`, `protocol`, `transport:"stdio"`와 **10개 `checks`**를 포함하고 exit code 0입니다. 하나라도 정답이 다르면 nonzero로 종료합니다. 임의 오류·timeout을 “거부 테스트 성공”으로 집계하지 않습니다.

## 4. 안전·장애·제한

runner는 child를 `-I -B -u`로 시작하고 환경을 allowlist로 제한합니다. 외부 OTel exporter를 구성하지 않으며 해당 자동 설정도 끕니다. stdout은 SDK가 관리하는 JSON-RPC 전용이고 사용자 payload나 비밀을 로그로 내보내지 않습니다. 최종 실패는 exception 종류만 출력하며 원문 peer 오류·환경·token은 출력하지 않습니다.

요청 timeout과 전체 실험 budget을 두고 context manager로 stdio를 닫습니다. SDK의 cleanup도 별도 유예/종료 시간이 있으므로 전체 wall-clock을 정확히 같은 초로 보장하지 않습니다. terminal 강제 종료·OS 강제 kill·malicious process의 완전한 격리는 이 fixture가 검증하지 않습니다. stdio는 OS sandbox가 아닙니다.

Windows에서 제한된 실행 환경이 로컬 pipe/subprocess를 막으면 `PermissionError`로 실패할 수 있습니다. 사용자가 통제하는 일반 터미널이나 승인된 동일 로컬 실행에서 검증하고, 이를 schema/권한 oracle의 성공으로 세지 않습니다. 보안 도구를 끄거나 임의 서버를 실행하는 방식으로 우회하지 않습니다.

HTTP/SSE·TLS·OAuth·issuer discovery·SSRF 방어·Origin·proxy·MRTR 사용자 승인·Tasks/Apps·cross-SDK/host·실제 LLM 판단·운영 성능은 기본 smoke 범위 밖입니다. [강의](../curriculum.md)와 [8주 연구](../../../capstones/mcp-tool-boundary-recovery.md)에서 별도 환경을 준비합니다.
