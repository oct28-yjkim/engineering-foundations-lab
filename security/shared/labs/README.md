# OpenBao / Vault 공통 실습

[보안 트랙](../../README.md) · [OpenBao](../../openbao/README.md) · [Vault](../../vault/README.md) · [환경 경계](../environment.md) · [검증 기록](validation.md)

기본은 Python 3.10+ 표준 라이브러리 CPU 실험입니다. 실제 제품 실행은 아래의 **선택 dev 단계**로 분리합니다. 모든 명령은 저장소 루트에서 한 줄씩 실행합니다.

## 1. 설치·과금 없는 CPU 모형

```text
python -B security/shared/labs/offline_lab.py --list
python -B security/shared/labs/offline_lab.py --lab all
python -B -m unittest discover -s security/shared/labs -p "test_*.py" -v
python -B -O -m unittest discover -s security/shared/labs -p "test_*.py" -v
```

| 모형 | 검산할 것 | 구현하지 않는 것 |
| --- | --- | --- |
| `exact-acl` | 동일 exact path capability 합집합·deny·data/metadata 분리 | 실제 wildcard selector 우선순위·auth·root·namespace |
| `kv-cas` | CAS 경쟁·version·soft delete/undelete/destroy | storage/HTTP·자동 pruning·실제 메모리 삭제 |
| `lease-clock` | 일반 lease 갱신 상한·만료·backend revoke 실패/재시도 | 실제 clock/scheduler·periodic/batch·DB session 종료 |
| `raft-quorum` | 고정 voter membership의 과반수·partition·nonvoter | leader 선출·log·read consistency·membership 변경 |

정답·반례·단계별 해설은 [offline.md](offline.md)에 있습니다. 이 모형은 암호 구현이나 OpenBao/Vault/Raft 서버가 아닙니다. 단위 테스트의 native 부분도 Docker subprocess **mock**이며 컨테이너를 시작하지 않습니다. 일반/`-O` 양쪽에서 같은 oracle이 유지되는지 확인합니다.

## 2. 선택: 실제 dev 엔진 준비

먼저 [환경 문서](../environment.md)를 읽습니다. 이 fixture는 공개 dummy root token, 자동 초기화/unseal, in-memory storage, 컨테이너 내부 HTTP를 사용하며 **운영용이 아닙니다**. 실제 키·계정·운영 데이터를 넣지 않습니다. 외부 통신·host port·bind mount·영속 volume은 없습니다. Docker 관리자/host 침해를 방어하는 sandbox는 아닙니다.

필요 조건은 개인 로컬 Docker Linux engine·Compose v2입니다. 원격 daemon이나 공유 cluster를 대상으로 실행하지 않습니다. 설치·engine 시작·image pull·container start는 Python runner가 자동 수행하지 않습니다. `up`은 최초 사용 시 이미지를 다운로드할 수 있습니다.

로컬 대상부터 확인합니다. `docker context inspect` 결과의 `Endpoints.docker.Host`가 개인 로컬 Unix socket 또는 Windows named pipe인지 확인하고, 임의 `DOCKER_HOST`/`DOCKER_CONTEXT` override와 혼동하지 않습니다. runner는 shell의 `DOCKER_*`, `COMPOSE_*`, `BAO_*`, `VAULT_*` override를 제거하고 **기본 Docker 설정에 저장된 context**를 읽은 뒤 로컬 endpoint를 고정합니다. context를 바꾸지 않으며 remote endpoint를 거절합니다.

```text
docker context inspect
docker compose -f security/openbao/compose.yaml config --quiet
docker compose -f security/vault/compose.yaml config --quiet
```

아래 시작/조회/종료 예시는 **Windows Docker Desktop Linux engine** 주소를 명시합니다. 다른 로컬 engine이라면 검증한 endpoint를 모든 `--host` 인자에 일관되게 넣습니다. 예를 들어 Linux 기본 socket은 `unix:///var/run/docker.sock`이며 rootless/custom socket은 실제 context 값을 확인해야 합니다. runner가 읽는 저장된 context와도 같은 engine이어야 합니다. 원격 주소로 치환하지 않습니다.

### OpenBao 선택

```text
docker --host npipe:////./pipe/dockerDesktopLinuxEngine compose -f security/openbao/compose.yaml up -d
docker --host npipe:////./pipe/dockerDesktopLinuxEngine compose -f security/openbao/compose.yaml exec -T openbao bao status -format=json
python -B security/shared/labs/engine_lab.py --product openbao --run-local
```

### Vault 선택

```text
docker --host npipe:////./pipe/dockerDesktopLinuxEngine compose -f security/vault/compose.yaml up -d
docker --host npipe:////./pipe/dockerDesktopLinuxEngine compose -f security/vault/compose.yaml exec -T vault vault status -format=json
python -B security/shared/labs/engine_lab.py --product vault --run-local
```

둘 다 실행할 필요는 없습니다. `up -d`는 readiness의 증거가 아닙니다. status가 `initialized:true`, `sealed:false`, `storage_type:"inmem"`이고 제품별 정확한 version을 반환한 뒤 runner를 실행합니다. 준비 중 connection failure면 잠시 뒤 status만 재확인합니다. image tag·서버 version이 달라졌다면 guard를 제거하지 말고 릴리스/보안 공지와 fixture를 다시 검토합니다.

제품 image에 노출 port 메타데이터가 있어도 host에 publish되지는 않습니다. native runner는 실제 binding·network mode·mount·command·project label·root identity를 검사합니다. 이 검사는 우발적 오대상 방지이며 악의적인 Docker host를 인증하는 기능은 아닙니다. Vault의 image-declared 두 volume은 tmpfs로 덮어야 guard를 통과합니다.

## 3. 실제 runner의 검증 계약

`--product`와 `--run-local`을 모두 지정해야 subprocess를 실행합니다. 도움말이나 인자 없는 실행은 mutation 없이 종료합니다.

| 순서 | 실제 작업 | 독립 기대값 |
| --- | --- | --- |
| 사전 확인 | local context → 단일 container → 격리 config → status → dummy root → 기존 policy 이름 | 하나라도 불일치하면 write 전 중단 |
| 새 mount | 새 `efl-<UUID>` KV v2 mount | 기존 mount를 tune/disable/reuse하지 않음 |
| CAS | `cas=0` v1 → `cas=1` v2 → stale `cas=1` | version 1/2, stale write HTTP 400 + CAS 오류문구 |
| 최소 권한 | 새 exact read + self-revoke policy, nonrenewable 5분 child service token | default/root policy 없이 해당 policy만 포함 |
| 허용/거부 | child로 item read, item write, metadata list | v2 합성 값 일치, write/list는 각각 HTTP 403 |
| 자기 폐기 | child로 revoke-self → 같은 token read | HTTP 403, root 재조회한 최종 값은 v2 그대로 |

`write`는 API JSON을 stdin으로 받습니다. 정책은 `data/item`의 read와 자기 token 폐기만 허용하며 KV CLI의 metadata preflight에 의존하지 않습니다. timeout·exit code만으로 권한 거부를 판정하지 않습니다. 참고: [Vault write](https://developer.hashicorp.com/vault/docs/commands/write), [token create](https://developer.hashicorp.com/vault/docs/commands/token/create), [OpenBao write](https://openbao.org/docs/commands/write/), [token create](https://openbao.org/docs/commands/token/create/).

성공 시 JSON의 `mode:"local_dev_engine"`, `status:"PASS"`, 제품/version, 새 mount/policy 식별자, 8개 oracle, `child_token_revoked:true`를 확인합니다. child token은 출력/파일/host argv에 넣지 않고 stdin→컨테이너 프로세스 환경으로만 전달합니다. process memory/env를 읽는 host 관리자까지 차단하는 것은 아닙니다.

실패 시 고정 stage/error label만 출력하며 원문 서버 오류를 출력하지 않습니다. timeout 이후 상태는 불명확할 수 있으므로 성공으로 간주하거나 기존 객체에 재시도하지 않습니다. child token 발급 뒤 실패하면 최대 5분 동안 남을 수 있습니다. 명시적 max TTL은 10분이지만 이 child는 갱신 불가이며 initial TTL은 5분 이하입니다. mount·policy는 성공/실패 모두 memory에 남습니다.

fixture는 audit·transit·PKI·auth provider·외부 DB를 구성하지 않습니다. 실제 seal, 키 보관, Raft, TLS, 복원, dynamic credential, 운영 격리는 **미검증**입니다. 다음 단계는 제품별 강의와 [선택 8주 연구](../../../capstones/secrets-identity-recovery.md)의 별도 허가된 환경입니다.

## 4. 학습 종료와 폐기

실측 결과에서 비밀을 제거하고 image digest/version·stage·기대값·실제값·미검증 경계만 남깁니다. image digest 조회는 원문 secret을 포함하지 않는 다음 명령을 사용합니다.

```text
docker --host npipe:////./pipe/dockerDesktopLinuxEngine image inspect openbao/openbao:2.7.1 --format '{{json .RepoDigests}}'
docker --host npipe:////./pipe/dockerDesktopLinuxEngine image inspect hashicorp/vault:2.1.1 --format '{{json .RepoDigests}}'
```

다음은 해당 제품 실습 컨테이너를 제거하는 **선택 폐기 명령**입니다. 실행한 제품에 대해서만 사용하며, memory의 모든 실습 데이터를 잃습니다. `stop/start`나 `restart`도 이 dev 데이터는 보존하지 않습니다. 운영 backup이나 credential을 이 fixture에 넣지 않습니다.

```text
docker --host npipe:////./pipe/dockerDesktopLinuxEngine compose -f security/openbao/compose.yaml down
docker --host npipe:////./pipe/dockerDesktopLinuxEngine compose -f security/vault/compose.yaml down
```

logging driver `none`은 dev bootstrap 키가 console log로 보존되는 것을 줄이기 위한 선택입니다. `docker logs`를 감사 증거로 사용할 수 없습니다. 실제 audit logging·장애 대응은 S2에서 비밀 비노출·retention·가용성을 함께 설계합니다.
