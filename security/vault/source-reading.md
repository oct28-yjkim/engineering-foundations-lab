# HashiCorp Vault 소스 읽기 지도

[커리큘럼](curriculum.md) · [실습](../shared/labs/README.md) · [논문·제품 비교](../shared/comparison.md)

확인일 **2026-10-04**, tag [`v2.1.1`](https://github.com/hashicorp/vault/releases/tag/v2.1.1), commit **`d78bbbe2d2f3d289c1ec29d431071beb23668212`**. 아래 core 경로는 고정 Git tree에서 확인했고 ACL·expiration 심볼과 dependency pin을 대조했습니다. Go 빌드·upstream test·실제 서버 실행은 미수행입니다. 공개 경로가 있다는 것과 Enterprise 기능이 Community fixture에서 지원된다는 것은 다릅니다.

## core에서 backend까지

| 모듈 | 고정 소스 | 추적할 질문 |
| --- | --- | --- |
| VL01–02 | [core.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/core.go) / [seal.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/seal.go) | sealed·초기화·unseal·post-unseal component 시작과 실패 rollback |
| VL02 | [barrier_aes_gcm.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/barrier_aes_gcm.go) / [seal_autoseal.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/seal_autoseal.go) | data encryption·root key·seal/recovery 조건, rekey·rotate·KMS 교체의 차이 |
| VL03–04 | [request_handling.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/request_handling.go) / [router.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/router.go) | 인증 예외·token validation·ACL·audit·plugin routing의 조건과 순서 |
| VL04 | [acl.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/acl.go) / [acl_ce.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/acl_ce.go) | `NewACL`·`AllowOperation`, selector ranking·capability와 edition boundary |
| VL03–06 | [token_store.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/token_store.go) | parent·orphan·service/batch·정책 분기; 문자열 형식으로 인증을 대신하지 않기 |
| VL06 | [expiration.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/expiration.go) | `Renew`·`RenewToken`·`LazyRevoke`·`revokeEntry`·backoff·irrevocable lease, 외부 backend 실패 |
| VL07 | [transit/backend.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/builtin/logical/transit/backend.go) | encrypt/decrypt/rotate/rewrap route를 따라가 key version·권한·오류 비교 |
| VL08 | [pki/backend.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/builtin/logical/pki/backend.go) | role·issuer·issue·revoke·CRL 전달과 client 검증 경계 |
| VL09 | [audit.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/audit.go) | setup·device 실패·request 처리, 실제 serialization/HMAC 구현으로 이동 |
| VL10 | [agent/template/template.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/command/agent/template/template.go) / [lease_cache.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/command/agentproxyshared/cache/lease_cache.go) | renew·render·cache 수명·앱 reload, 파일·process env 노출 |
| VL11–12 | [physical/raft/raft.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/physical/raft/raft.go) / [vault/raft.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/raft.go) | storage·Raft apply·snapshot restore와 core seal·peer join의 연결 |

## KV는 별도 plugin pin을 따라가기

[go.mod](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/go.mod)는 `github.com/hashicorp/vault-plugin-secrets-kv v0.26.3-0.20260626165612-824fb96aa7a8`을 참조합니다. server tag를 고정하고 plugin의 `main`을 읽으면 다른 코드일 수 있습니다.

| VL05 경로 | 읽기 과제 |
| --- | --- |
| [path_data.go](https://github.com/hashicorp/vault-plugin-secrets-kv/blob/824fb96aa7a8/path_data.go) / [path_data_test.go](https://github.com/hashicorp/vault-plugin-secrets-kv/blob/824fb96aa7a8/path_data_test.go) | `options.cas`·`data` envelope, current version 확인·write·lock·error |
| [path_delete.go](https://github.com/hashicorp/vault-plugin-secrets-kv/blob/824fb96aa7a8/path_delete.go) / [path_destroy.go](https://github.com/hashicorp/vault-plugin-secrets-kv/blob/824fb96aa7a8/path_destroy.go) | 논리 delete·version destroy의 다른 데이터/metadata 변화 |
| [path_metadata.go](https://github.com/hashicorp/vault-plugin-secrets-kv/blob/824fb96aa7a8/path_metadata.go) / [path_metadata_test.go](https://github.com/hashicorp/vault-plugin-secrets-kv/blob/824fb96aa7a8/path_metadata_test.go) | metadata read/list/delete 권한, retention·version counter와 CAS |

JWT auth도 별도 dependency `vault-plugin-auth-jwt v0.26.4`를 사용합니다. role/claim 검증과 core identity/token 발급을 분리합니다. 다른 plugin 버전을 이 값에서 유추하지 않습니다.

## upstream test와 최소 반례

- [acl_test.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/acl_test.go): exact/prefix/segment wildcard 선택 우선순위. 넓은 deny가 모든 구체적 allow를 무조건 덮는다는 잘못된 모델을 반증합니다.
- [token_store_test.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/token_store_test.go): 발급/회수·parent/lease, root 예외를 업무 정책에 일반화하지 않습니다.
- [expiration_test.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/expiration_test.go): clock·retry·backend mock, 실제 외부 DB 회수와 구분합니다.
- [raft_test.go](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/vault/raft_test.go): peer/snapshot·seal 의존성·복원 oracle. dev restart는 Raft restore가 아닙니다.

별도 고정 checkout에서 module·Go 버전·build tag·테스트 dependency를 확인하고 좁은 package/test를 선택합니다. 외부 서비스가 필요한 통합 테스트를 검토 없이 실행하지 않습니다. 공개 CE에서 찾지 못한 Enterprise 경로는 미확인으로 남깁니다.

[Dockerfile](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/Dockerfile)의 default stage와 [entrypoint](https://github.com/hashicorp/vault/blob/d78bbbe2d2f3d289c1ec29d431071beb23668212/.release/docker/docker-entrypoint.sh)를 함께 읽습니다. `/vault/file`, `/vault/logs` VOLUME 선언 때문에 dev Compose는 tmpfs를 명시합니다. build helper stage와 runtime image를 혼동하지 않습니다.

trace에는 입력·독립 정답·symbol 5개·자료구조 2개·동기화/오류 경계·기존 test oracle·본인 반례를 담습니다. raw key/token 대신 request ID·version·상태를 사용합니다. [논문](../shared/comparison.md)과 [8주 연구](../../capstones/secrets-identity-recovery.md)에서 실제 운영 증거와 연결합니다.
