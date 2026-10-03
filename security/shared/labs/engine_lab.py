"""Opt-in, synthetic OpenBao/Vault dev-engine smoke lab (Python 3.10+).

Never starts/stops a container or initializes, unseals, rotates, or deletes an
existing server object. New mount/policy artifacts remain in the in-memory
fixture. Mock tests validate this runner, not either actual server.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from typing import Any


SECURITY_DIRECTORY = Path(__file__).resolve().parents[2]
PRODUCTS = {
    "openbao": {"version": "2.7.1", "image": "openbao/openbao:2.7.1", "cli": "bao", "prefix": "BAO"},
    "vault": {"version": "2.1.1", "image": "hashicorp/vault:2.1.1", "cli": "vault", "prefix": "VAULT"},
}
ADDRESS = "http://127.0.0.1:8200"
NAME_PATTERN = re.compile(r"efl-[0-9a-f]{32}\Z")
CONTAINER_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
LOCAL_PIPES = frozenset({"npipe:////./pipe/docker_engine", "npipe:////./pipe/dockerDesktopLinuxEngine"})
MAX_COMMANDS = 24
MAX_OUTPUT_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 30


class LabFailure(Exception):
    """Only fixed error labels; server output and tokens are never printed."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise LabFailure(code)


def safe_environment(source: dict[str, str]) -> dict[str, str]:
    # Read the context saved in the default Docker configuration, not a shell
    # DOCKER_HOST/CONTEXT/CONFIG override. Do not modify os.environ or context.
    result = {key: value for key, value in source.items()
              if not key.upper().startswith(("DOCKER_", "COMPOSE_", "BAO_", "VAULT_"))}
    result["COMPOSE_DISABLE_ENV_FILE"] = "true"
    return result


def parse_json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError, AttributeError):
        raise LabFailure("invalid_json_output") from None


def local_docker_host(contexts: Any) -> str:
    require(isinstance(contexts, list) and len(contexts) == 1, "invalid_docker_context")
    context = contexts[0]
    require(isinstance(context, dict), "invalid_docker_context")
    endpoints = context.get("Endpoints")
    require(isinstance(endpoints, dict) and isinstance(endpoints.get("docker"), dict), "invalid_docker_context")
    host = endpoints["docker"].get("Host")
    require(isinstance(host, str), "invalid_docker_context")
    require(re.fullmatch(r"unix:///[^\x00-\x20\\?#]+", host) is not None or host in LOCAL_PIPES,
            "remote_docker_endpoint_refused")
    return host


def root_token(product: str) -> str:
    require(product in PRODUCTS, "unknown_product")
    return f"efl-local-{product}-root-not-for-production"


def verify_container(items: Any, product: str, container: str) -> None:
    """Accidental-target guard, not authentication against a malicious host."""
    require(product in PRODUCTS, "unknown_product")
    require(CONTAINER_PATTERN.fullmatch(container) is not None, "invalid_container_id")
    require(isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict), "invalid_container_inspect")
    item = items[0]
    require(item.get("Id") == container, "unexpected_container_id")
    config, host, network, state = (item.get(key) for key in ("Config", "HostConfig", "NetworkSettings", "State"))
    require(all(isinstance(value, dict) for value in (config, host, network, state)), "invalid_container_shape")
    require(state.get("Running") is True, "container_not_running")
    spec = PRODUCTS[product]
    require(config.get("Image") == spec["image"], "unexpected_container_image")
    labels = config.get("Labels")
    require(isinstance(labels, dict) and labels.get("com.docker.compose.project") == f"engineering-foundations-{product}-lab"
            and labels.get("com.docker.compose.service") == product, "unexpected_compose_identity")
    expected_command = ["server", "-dev", "-dev-no-store-token", f"-dev-root-token-id={root_token(product)}",
                        "-dev-listen-address=127.0.0.1:8200"]
    require(config.get("Cmd") == expected_command, "unexpected_server_command")
    require(host.get("NetworkMode") == "none", "network_isolation_required")
    require(host.get("Privileged") is False and not host.get("CapAdd"), "privileged_container_refused")
    require(not host.get("Binds") and not host.get("VolumesFrom"), "host_or_external_mount_refused")
    require(not host.get("PublishAllPorts") and not host.get("PortBindings"), "published_ports_refused")
    ports = network.get("Ports")
    require(ports is None or (isinstance(ports, dict) and all(value is None for value in ports.values())), "published_ports_refused")
    allowed_tmpfs = {"/vault/file", "/vault/logs"} if product == "vault" else set()
    tmpfs = host.get("Tmpfs") or {}
    require(isinstance(tmpfs, dict) and set(tmpfs) == allowed_tmpfs, "unexpected_tmpfs_configuration")
    for options in tmpfs.values():
        require(isinstance(options, str) and set(options.split(",")) == {"rw", "noexec", "nosuid", "size=16m"},
                "unexpected_tmpfs_options")
    mounts = item.get("Mounts")
    require(isinstance(mounts, list), "invalid_mount_inspection")
    # Docker versions may represent --tmpfs only in HostConfig.Tmpfs, or also
    # in Mounts. Anonymous image-declared volumes must NOT appear here.
    require(all(isinstance(mount, dict) and mount.get("Type") == "tmpfs"
                and mount.get("Destination") in allowed_tmpfs for mount in mounts), "persistent_mount_refused")
    entries = config.get("Env")
    require(isinstance(entries, list) and all(isinstance(entry, str) and "=" in entry for entry in entries), "invalid_container_environment")
    relevant = [entry.split("=", 1) for entry in entries if entry.upper().startswith(("BAO_", "VAULT_"))]
    expected_env = {f"{spec['prefix']}_ADDR": ADDRESS, f"{spec['prefix']}_TOKEN": root_token(product)}
    require(len(relevant) == 2 and dict(relevant) == expected_env, "unexpected_container_environment")


def verify_status(data: Any, product: str) -> None:
    require(isinstance(data, dict) and data.get("initialized") is True and data.get("sealed") is False
            and data.get("storage_type") == "inmem" and data.get("version") == PRODUCTS[product]["version"],
            "unexpected_server_status")


def verify_root(data: Any, product: str) -> None:
    require(isinstance(data, dict) and isinstance(data.get("data"), dict), "invalid_root_lookup")
    token = data["data"]
    require(token.get("id") == root_token(product) and token.get("policies") == ["root"], "unexpected_root_identity")


def verify_version(data: Any, expected: int) -> None:
    require(isinstance(data, dict) and isinstance(data.get("data"), dict)
            and type(data["data"].get("version")) is int and data["data"]["version"] == expected,
            "unexpected_kv_version")


def verify_value(data: Any) -> None:
    require(isinstance(data, dict) and isinstance(data.get("data"), dict), "invalid_kv_read")
    value = data["data"]
    require(value.get("data") == {"message": "public-synthetic-v2"} and isinstance(value.get("metadata"), dict)
            and type(value["metadata"].get("version")) is int and value["metadata"]["version"] == 2,
            "unexpected_kv_value")


def child_token(data: Any, policy: str) -> str:
    require(isinstance(data, dict) and isinstance(data.get("auth"), dict), "invalid_token_response")
    auth = data["auth"]
    token = auth.get("client_token")
    # Token grammar deliberately broad enough for both pinned products, but
    # forbids newlines/control characters and unbounded stdin payloads.
    require(isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) is not None,
            "invalid_child_token")
    require(auth.get("policies") == [policy] and type(auth.get("lease_duration")) is int
            and 0 < auth["lease_duration"] <= 300 and auth.get("renewable") is False,
            "unexpected_child_token_scope")
    return token


def verify_http_error(result: subprocess.CompletedProcess, status: int, cas: bool = False) -> None:
    # CLI errors include an HTTP "Code:" line. A timeout, exit 1, or arbitrary
    # error text does not prove ACL denial or CAS rejection.
    codes = re.findall(rb"(?m)^Code: ([0-9]{3})\.(?:\s|$)", result.stderr)
    require(result.returncode != 0 and result.stdout == b"" and codes == [str(status).encode("ascii")],
            "expected_http_rejection_missing")
    if cas:
        require(b"check-and-set parameter did not match the current version" in result.stderr.lower(),
                "expected_cas_rejection_missing")


class LocalClient:
    def __init__(self, product: str) -> None:
        require(product in PRODUCTS, "unknown_product")
        self.product = product
        self.spec = PRODUCTS[product]
        self.track = SECURITY_DIRECTORY / product
        self.name = "efl-" + uuid.uuid4().hex
        self.stage = "docker_context"
        self.commands = 0
        self.host: str | None = None
        self.container: str | None = None
        self.fixture_verified = False
        self.identity_verified = False
        self.mutation_attempted = False
        self.environment = safe_environment(dict(os.environ))
        self.docker = shutil.which("docker", path=self.environment.get("PATH"))

    def invoke(self, arguments: list[str], payload: str = "") -> subprocess.CompletedProcess:
        require(self.docker is not None, "docker_cli_not_found")
        require(self.commands < MAX_COMMANDS, "command_budget_exceeded")
        self.commands += 1
        try:
            result = subprocess.run([self.docker, *arguments], input=payload.encode("utf-8"), stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=TIMEOUT_SECONDS, check=False, shell=False,
                                    env=self.environment, cwd=str(self.track))
        except subprocess.TimeoutExpired:
            raise LabFailure("command_timeout_server_state_unknown") from None
        except (OSError, ValueError):
            raise LabFailure("docker_command_failed") from None
        require(isinstance(result.stdout, bytes) and isinstance(result.stderr, bytes), "invalid_process_output")
        # Post-capture validation limit, not a streaming memory-use bound.
        require(len(result.stdout) + len(result.stderr) <= MAX_OUTPUT_BYTES, "output_too_large")
        return result

    def connect(self) -> None:
        require(self.host is None, "context_already_inspected")
        result = self.invoke(["context", "inspect"])
        require(result.returncode == 0, "docker_context_inspection_failed")
        self.host = local_docker_host(parse_json(result.stdout))
        self.stage = "container_inspection"
        result = self.invoke(["--host", self.host, "compose", "--project-name", f"engineering-foundations-{self.product}-lab",
                              "--project-directory", str(self.track), "-f", str(self.track / "compose.yaml"),
                              "ps", "-q", self.product])
        require(result.returncode == 0, "compose_service_lookup_failed")
        try:
            container = result.stdout.decode("ascii").strip()
        except UnicodeDecodeError:
            raise LabFailure("invalid_container_id") from None
        require(CONTAINER_PATTERN.fullmatch(container) is not None, "expected_one_running_container")
        result = self.invoke(["--host", self.host, "inspect", container])
        require(result.returncode == 0, "container_inspection_failed")
        verify_container(parse_json(result.stdout), self.product, container)
        self.container = container
        self.fixture_verified = True

    def execute(self, stage: str, token: str | None = None) -> Any:
        require(NAME_PATTERN.fullmatch(self.name) is not None, "invalid_generated_name")
        require(self.host is not None and self.fixture_verified and self.container is not None, "fixture_not_verified")
        local_docker_host([{"Endpoints": {"docker": {"Host": self.host}}}])
        require(CONTAINER_PATTERN.fullmatch(self.container) is not None, "invalid_container_id")
        path = self.name + "/data/item"
        policy = (f'path "{path}" {{ capabilities = ["read"] }}\n'
                  'path "auth/token/revoke-self" { capabilities = ["update"] }\n')
        operations = {
            "status": (["status", "-format=json"], ""),
            "root_lookup": (["token", "lookup", "-format=json"], ""),
            "policy_inventory": (["policy", "list", "-format=json"], ""),
            "mount": (["secrets", "enable", f"-path={self.name}", "-version=2", "kv"], ""),
            "cas_create": (["write", "-format=json", path, "-"], json.dumps({"options": {"cas": 0}, "data": {"message": "public-synthetic-v1"}})),
            "cas_update": (["write", "-format=json", path, "-"], json.dumps({"options": {"cas": 1}, "data": {"message": "public-synthetic-v2"}})),
            "cas_stale": (["write", "-format=json", path, "-"], json.dumps({"options": {"cas": 1}, "data": {"message": "public-synthetic-rejected"}})),
            "root_read": (["read", "-format=json", path], ""),
            "policy": (["policy", "write", self.name, "-"], policy),
            "token_create": (["token", "create", "-format=json", f"-policy={self.name}", "-no-default-policy",
                              "-ttl=5m", "-explicit-max-ttl=10m", "-renewable=false", "-type=service"], ""),
            "allowed_read": (["read", "-format=json", path], ""),
            "denied_write": (["write", "-format=json", path, "-"], json.dumps({"options": {"cas": 2}, "data": {"message": "public-synthetic-rejected"}})),
            "denied_list": (["list", "-format=json", self.name + "/metadata"], ""),
            "revoke_self": (["token", "revoke", "-self"], ""),
            "revoked_read": (["read", "-format=json", path], ""),
        }
        require(stage in operations, "unknown_engine_stage")
        if stage not in {"status", "root_lookup"}:
            require(self.identity_verified, "server_identity_not_verified")
        child_stages = {"allowed_read", "denied_write", "denied_list", "revoke_self", "revoked_read"}
        require((token is not None) == (stage in child_stages), "unexpected_token_scope")
        if token is not None:
            require(re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) is not None and token != root_token(self.product),
                    "invalid_child_token")
        self.stage = stage
        if stage in {"mount", "cas_create", "cas_update", "cas_stale", "policy", "token_create", "denied_write", "revoke_self"}:
            self.mutation_attempted = True
        arguments, body = operations[stage]
        # Fixed shell source; only argv supplies validated paths. Token arrives
        # via stdin, never Docker argv, host environment, console or a file.
        prefix = self.spec["prefix"]
        wrapper = (f'IFS= read -r efl_token || exit 90; {prefix}_TOKEN="$efl_token"; export {prefix}_TOKEN; '
                   'unset efl_token HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy; '
                   f'exec {self.spec["cli"]} "$@"')
        result = self.invoke(["--host", self.host, "exec", "-i", self.container, "sh", "-c", wrapper, "efl-cli", *arguments],
                             (token if token is not None else root_token(self.product)) + "\n" + body)
        if stage in {"cas_stale", "denied_write", "denied_list", "revoked_read"}:
            verify_http_error(result, 400 if stage == "cas_stale" else 403, cas=stage == "cas_stale")
            return None
        require(result.returncode == 0, "engine_command_failed")
        if stage in {"mount", "policy", "revoke_self"}:
            return None
        return parse_json(result.stdout)


def run_lab(client: LocalClient) -> dict[str, Any]:
    client.connect()
    verify_status(client.execute("status"), client.product)
    verify_root(client.execute("root_lookup"), client.product)
    client.identity_verified = True
    policies = client.execute("policy_inventory")
    require(isinstance(policies, list) and all(isinstance(policy, str) for policy in policies)
            and client.name not in policies, "policy_name_collision_or_invalid_inventory")
    # Enabling an already-mounted path fails on the server; we never tune,
    # disable, replace or reuse another mount. UUID minimizes concurrent races.
    client.execute("mount")
    verify_version(client.execute("cas_create"), 1)
    verify_version(client.execute("cas_update"), 2)
    client.execute("cas_stale")
    verify_value(client.execute("root_read"))
    client.execute("policy")
    token = child_token(client.execute("token_create"), client.name)
    verify_value(client.execute("allowed_read", token))
    client.execute("denied_write", token)
    client.execute("denied_list", token)
    client.execute("revoke_self", token)
    client.execute("revoked_read", token)
    verify_value(client.execute("root_read"))
    client.stage = "complete"
    return {"status": "PASS", "mode": "local_dev_engine", "product": client.product,
            "version": client.spec["version"], "mount_and_policy": client.name, "artifacts_retained": True,
            "child_token_revoked": True, "commands": client.commands,
            "oracles": ["CAS create version 1", "CAS update version 2", "stale CAS HTTP 400",
                        "exact ACL read", "write HTTP 403", "metadata list HTTP 403", "revoked token HTTP 403",
                        "final synthetic value unchanged"],
            "not_verified": ["seal/unseal or encryption at rest", "Raft/HA", "TLS", "audit devices",
                             "dynamic backend credentials", "durable restore", "production isolation"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", choices=tuple(PRODUCTS), help="Pinned local dev fixture to test.")
    parser.add_argument("--run-local", action="store_true", help="Opt in to new synthetic mount/policy writes; never starts Docker.")
    args = parser.parse_args(argv)
    if not args.run_local or args.product is None:
        parser.error("Both --product and --run-local are required. No subprocess was started.")
    if sys.version_info < (3, 10):
        print(json.dumps({"status": "ERROR", "error": "python_3_10_required"}))
        return 1
    client = LocalClient(args.product)
    try:
        print(json.dumps(run_lab(client), sort_keys=True))
        return 0
    except LabFailure as error:
        print(json.dumps({"status": "ERROR", "product": client.product, "stage": client.stage, "error": str(error),
                          "mount_and_policy": client.name, "mutation_attempted": client.mutation_attempted,
                          "cleanup_performed": False, "commands": client.commands}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
