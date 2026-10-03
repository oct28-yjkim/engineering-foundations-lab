# MCP 환경·권한·실행 범위

[실습 안내](labs/README.md) · [호환성](compatibility.md) · [검증 기록](labs/validation.md)

## 기본과 선택 환경

| 수준 | 제공 환경 | 확인하는 것 | 확인하지 않는 것 |
| --- | --- | --- | --- |
| CPU-MODEL | Python 3.10+ 표준 라이브러리 | revision·도구 계약·요청 원장·principal cache의 작은 모형 | 완전한 JSON Schema/MCP·OAuth·실제 네트워크 |
| SDK-STDIO | 고정 Python SDK, 별도 가상환경, owned child server | 실제 로컬 client/server의 도구·resource·prompt·오류 | HTTP/TLS/OAuth·외부 host·LLM 판단·conformance 전체 |
| HTTP-AUTH | 학습자가 별도 격리 endpoint/issuer 구성 | header/body·Origin·audience·권한·proxy·재시도 | 전역 cloud/운영 보안 자동 보장 |
| INTEROP/RESEARCH | 별도 고정 SDK/host·지원 matrix | 실제 교차 구현과 실패·마이그레이션 | 시험하지 않은 revision/extension/host |

기본 CPU는 추가 패키지·Docker·모델·GPU·API 키·네트워크가 필요 없습니다. MCP는 모델 자체나 특정 모델 제공자의 tool-calling API가 아닙니다. 로컬 fixture에서 MCP client/server만 검증하며 LLM 없이도 실행합니다.

## 선택 SDK 설치

공식 배포 `mcp==2.3.0`, `mcp-types==2.3.0`을 고정합니다. SDK 자체는 Python 3.10+을 요구하며 이 저장소의 실측 환경은 검증 기록에 적습니다. `requirements-sdk.txt`는 직접 의존성 pin이지 모든 전이 의존성·OS·wheel hash를 고정한 universal lockfile은 아닙니다. 실제 보고서에 `pip freeze`, Python/OS/architecture를 함께 보존합니다.

아래는 **사용자가 선택 실행하는** 설치입니다. 전역 Python·현재 앱의 MCP 서버 설정은 바꾸지 않습니다. 저장소 루트에서 시작하며 `lab-workspaces/mcp-sdk-2.3.0`은 Git ignore된 실습 전용 위치입니다. 같은 이름의 기존 환경이 있으면 내용을 확인하고 다른 새 이름을 사용하거나 의도적으로 재사용합니다. venv를 덮어쓰거나 자동 삭제하지 않습니다.

```text
python -m venv lab-workspaces/mcp-sdk-2.3.0
```

Windows PowerShell:

```text
./lab-workspaces/mcp-sdk-2.3.0/Scripts/python.exe -m pip --isolated --disable-pip-version-check install --index-url https://pypi.org/simple --only-binary=:all: -r ai/mcp/labs/requirements-sdk.txt
./lab-workspaces/mcp-sdk-2.3.0/Scripts/python.exe -B ai/mcp/labs/sdk_lab.py --check
./lab-workspaces/mcp-sdk-2.3.0/Scripts/python.exe -B ai/mcp/labs/sdk_lab.py --run-local
```

macOS/Linux:

```text
./lab-workspaces/mcp-sdk-2.3.0/bin/python -m pip --isolated --disable-pip-version-check install --index-url https://pypi.org/simple --only-binary=:all: -r ai/mcp/labs/requirements-sdk.txt
./lab-workspaces/mcp-sdk-2.3.0/bin/python -B ai/mcp/labs/sdk_lab.py --check
./lab-workspaces/mcp-sdk-2.3.0/bin/python -B ai/mcp/labs/sdk_lab.py --run-local
```

설치는 PyPI에서 코드와 의존성을 내려받는 네트워크 작업입니다. `--only-binary` 대상 wheel이 없는 플랫폼에서는 실패할 수 있으며, 자동으로 source build·전역 설치로 전환하지 않습니다. runtime fixture는 외부 요청·OAuth 로그인·모델 호출·유료 자원을 사용하지 않습니다. `--check`는 의존성 상태만 점검하고 `--run-local`만 owned 서버 프로세스를 시작합니다.

## 권한 경계

- stdio server는 host가 실행하는 **일반 로컬 프로세스**입니다. stdio나 MCP Roots가 OS sandbox를 만들어 주지 않습니다. 이 fixture의 데이터는 소스에 들어 있는 공개 합성 값이며 임의 path/URL/command를 도구 인자로 받지 않습니다.
- SDK runner는 같은 Python으로 고정 `sdk_server.py`만 실행합니다. 비밀·proxy·외부 telemetry 설정을 물려주지 않도록 환경을 제한하지만, OS 수준 네트워크/파일 차단 보장은 아닙니다. 알 수 없는 외부 MCP server를 이 launcher에 넣지 않습니다.
- OTel instrumentation과 외부 exporter 전송은 다릅니다. 기본 lab은 외부 exporter를 구성하지 않고 관련 자동 설정을 차단합니다. prompt·token·tool payload 원문을 trace/log에 넣지 않습니다.
- 실제 HTTP 실험은 별도 localhost/TLS 계획·Origin 검증·인증·승인·egress/SSRF 방어·요청/결과 크기·deadline을 준비합니다. 무인증 `0.0.0.0` 배포 예제를 기본 환경으로 제공하지 않습니다.
- token audience·issuer·tenant·scope는 실제 verifier가 확인한 신원에서 얻습니다. `clientInfo`, 요청 JSON의 tenant 주장, tool annotation, cache hint는 그 대체물이 아닙니다.
- [OpenBao/Vault](../../security/README.md)에서 받은 credential도 LLM prompt·resource·tool 결과로 반환하지 않습니다. 필요한 도구의 신뢰된 실행 경계에서만 제한적으로 사용합니다.

실제 auth server·cloud resource·DB·Sentry·ChatGPT/IDE 연결 설정은 자동 생성하지 않습니다. Git에는 비식별 결과·코드·명세 revision만 남기고 실제 JWT·refresh token·인증 코드·DB credential·사용자 payload는 저장하지 않습니다.
