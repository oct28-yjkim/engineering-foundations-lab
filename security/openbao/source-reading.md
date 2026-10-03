# OpenBao 소스 읽기 지도

[커리큘럼](curriculum.md) · [실습](../shared/labs/README.md) · [논문·제품 비교](../shared/comparison.md)

확인일 **2026-10-04**, tag [`v2.7.1`](https://github.com/openbao/openbao/releases/tag/v2.7.1), commit **`a5db72cef75c24b920ade02065b18dd8eb666bac`**. 아래 경로는 고정 Git tree에서 확인했고 core unseal·ACL·expiration·KV write 심볼을 원문과 대조했습니다. Go 빌드·upstream test·debugger 실행은 미수행입니다.

현재 core는 `internal/vault/`, KV는 `internal/builtin/logical/kv/`에 있습니다. 오래된 Vault의 경로를 그대로 가정하지 않습니다. 정적 호출 경로와 실제 실행한 경로를 구분합니다.

## 요청 하나를 끝까지 추적하기

| 모듈 | 고정 소스 | 추적할 조건·반례 |
| --- | --- | --- |
| OB01–02 | [core.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/core.go) | `Unseal`·`unsealFragment`·`postUnseal`·`SealWithRequest`, 상태 lock과 실패 경로. dev 자동 unseal과 정상 운영 절차 구별 |
| OB02 | [barrier/aes_gcm.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/barrier/aes_gcm.go) / [keyring.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/barrier/keyring.go) | storage write/read의 암호·인증·key version, sealed 접근 차단. 실제 key bytes를 출력하지 않기 |
| OB02·12 | [seal.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/seal.go) / [seal_manager.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/seal_manager.go) | seal 구현·key custody·namespace seal, barrier rotation과 rekey의 차이 |
| OB03–04 | [request_handling.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/request_handling.go) / [routing/router.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/routing/router.go) | 인증 예외·mount routing·namespace·ACL·audit·response의 실제 순서 |
| OB04 | [policy/acl.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/policy/acl.go) | `NewACL`·`AllowOperation`, selector ranking과 capability, 어느 규칙 집합에 deny가 적용되는가? |
| OB03–06 | [token_store.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/token_store.go) / [expiration.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/expiration.go) | parent·lookup·renew/revoke; `Renew`·`LazyRevoke`·`revokeEntry`와 backend 실패·재시도 |
| OB05 | [kv/path_data.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/builtin/logical/kv/path_data.go) / [path_metadata.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/builtin/logical/kv/path_metadata.go) | `pathDataWrite`의 CAS·version·동기화·metadata 업데이트; CLI shorthand와 API route 구별 |
| OB05 | [path_delete.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/builtin/logical/kv/path_delete.go) / [path_destroy.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/builtin/logical/kv/path_destroy.go) | soft delete·undelete·destroy 상태 전이. API destroy와 매체 전체 forensic erasure는 다름 |
| OB07 | [transit/path_rotate.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/builtin/logical/transit/path_rotate.go) / [path_rewrap.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/builtin/logical/transit/path_rewrap.go) | key version 생성·기존 ciphertext 재작성의 다른 경로, min decryption version과 rollback |
| OB08 | [pki/backend.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/builtin/logical/pki/backend.go) | issuer/role/issue/revoke route에서 구현으로 이동. serial·CRL·client 검증 분리 |
| OB09 | [vault/audit.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/audit.go) / [audit/audit.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/audit/audit.go) | request/response 기록·backend 실패 전파·HMAC 적용 대상과 예외 |
| OB10 | [agent/template/template.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/command/agent/template/template.go) / [lease_cache.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/command/agentproxyshared/cache/lease_cache.go) | renew/cache/render에서 앱 credential 사용까지의 시간·권한·reload 경계 |
| OB11–12 | [physical/raft/raft.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/physical/raft/raft.go) / [vault/raft.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/raft.go) | storage adapter·join/unseal·snapshot, library·core·seal key의 책임 분리 |

## upstream 테스트를 읽는 순서

1. [acl_test.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/policy/acl_test.go): 겹치는 selector의 우선순위와 literal 기대값을 손으로 계산합니다. CPU `exact-acl`은 전체 selector 의미를 구현하지 않습니다.
2. [path_data_test.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/builtin/logical/kv/path_data_test.go), [path_destroy_test.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/builtin/logical/kv/path_destroy_test.go): CAS conflict와 tombstone/destroyed metadata의 차이를 추적합니다.
3. [aes_gcm_test.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/vault/barrier/aes_gcm_test.go): tamper·key lifecycle·sealed 검사와 테스트 밖 공격자 가정을 적습니다.
4. [template_test.go](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/internal/command/agent/template/template_test.go): 파일 렌더링과 소비자 사용 완료가 같은 사건인지 반증합니다.

별도 고정 checkout에서 Go 버전·module/workspace·빌드 안내를 확인하고 한 package의 좁은 test부터 실행합니다. `go test ./...`는 dependency 다운로드·외부 서비스가 필요한 통합 테스트를 포함할 수 있어 검토 없이 실행하지 않습니다. Python PASS는 upstream Go test PASS가 아닙니다.

## dependency와 이미지

[go.mod](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/go.mod)의 Raft 의존성과 [Dockerfile](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/Dockerfile), [entrypoint](https://github.com/openbao/openbao/blob/a5db72cef75c24b920ade02065b18dd8eb666bac/.release/docker/docker-entrypoint.sh)을 함께 읽습니다. source 기능과 배포 이미지의 활성화 조건은 같지 않을 수 있습니다. 외부 plugin 목록·버전은 Vault와 동일하다고 가정하지 않습니다.

trace마다 입력·독립 정답·symbol 5개·자료구조 2개·동기화/오류 경계·기존 test oracle·본인 반례를 제출합니다. 키/토큰 대신 비식별 request ID·version·상태 전이를 사용합니다. [논문 지도](../shared/comparison.md)와 [8주 연구](../../capstones/secrets-identity-recovery.md)로 연결합니다.
