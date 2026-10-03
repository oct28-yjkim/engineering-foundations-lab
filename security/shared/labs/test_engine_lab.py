"""Mock-only native-runner tests. No Docker/server subprocess is executed."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import patch

import engine_lab as lab


CID = "a" * 64
NAME = "efl-" + "b" * 32
CHILD = "hvs.MockOnlyChildTokenNeverUseInProduction"
HOST = "unix:///var/run/docker.sock"


def result(value=None, code=0, stderr=b"", raw=None):
    stdout = (json.dumps(value).encode() if raw is None else raw)
    return subprocess.CompletedProcess([], code, stdout, stderr)


def context(host=HOST):
    return [{"Endpoints": {"docker": {"Host": host}}}]


def fixture(product="openbao"):
    prefix = "BAO" if product == "openbao" else "VAULT"
    version = "2.7.1" if product == "openbao" else "2.1.1"
    image = f"openbao/openbao:{version}" if product == "openbao" else f"hashicorp/vault:{version}"
    tmpfs = {"/vault/file": "rw,noexec,nosuid,size=16m", "/vault/logs": "rw,noexec,nosuid,size=16m"} if product == "vault" else {}
    return [{"Id": CID, "State": {"Running": True},
             "Config": {"Image": image,
                        "Labels": {"com.docker.compose.project": f"engineering-foundations-{product}-lab",
                                   "com.docker.compose.service": product},
                        "Cmd": ["server", "-dev", "-dev-no-store-token",
                                f"-dev-root-token-id=efl-local-{product}-root-not-for-production",
                                "-dev-listen-address=127.0.0.1:8200"],
                        "Env": ["PATH=/bin:/usr/bin", f"{prefix}_ADDR=http://127.0.0.1:8200",
                                f"{prefix}_TOKEN=efl-local-{product}-root-not-for-production"]},
             "HostConfig": {"NetworkMode": "none", "Privileged": False, "CapAdd": None,
                            "PublishAllPorts": False, "PortBindings": {}, "Binds": None,
                            "VolumesFrom": None, "Tmpfs": tmpfs},
             "NetworkSettings": {"Ports": {"8200/tcp": None}}, "Mounts": []}]


def status(product="openbao"):
    return {"initialized": True, "sealed": False, "storage_type": "inmem",
            "version": "2.7.1" if product == "openbao" else "2.1.1"}


def root(product="openbao"):
    return {"data": {"id": f"efl-local-{product}-root-not-for-production", "policies": ["root"]}}


def token():
    return {"auth": {"client_token": CHILD, "policies": [NAME], "lease_duration": 300, "renewable": False}}


def value():
    return {"data": {"data": {"message": "public-synthetic-v2"}, "metadata": {"version": 2}}}


def denied(code=403, detail="permission denied"):
    return result(code=2, raw=b"", stderr=f"Error making API request.\nURL: PUT http://127.0.0.1:8200/v1/mock\nCode: {code}. Errors:\n\n* {detail}\n".encode())


def responses(product="openbao"):
    return [result(context()), result(raw=(CID + "\n").encode()), result(fixture(product)),
            result(status(product)), result(root(product)), result(["default", "root"]),
            result(raw=b"Success! Enabled kv secrets engine.\n"),
            result({"data": {"version": 1}}), result({"data": {"version": 2}}),
            denied(400, "check-and-set parameter did not match the current version"),
            result(value()), result(raw=b"Success! Uploaded policy.\n"), result(token()),
            result(value()), denied(), denied(), result(raw=b"Success! Revoked token.\n"), denied(), result(value())]


class GuardTests(unittest.TestCase):
    def fail_fixture(self, section, key, value, product="openbao"):
        data = fixture(product)
        data[0][section][key] = value
        with self.assertRaises(lab.LabFailure):
            lab.verify_container(data, product, CID)

    def test_local_unix_and_windows_endpoints(self):
        for host in [HOST, "npipe:////./pipe/docker_engine", "npipe:////./pipe/dockerDesktopLinuxEngine"]:
            with self.subTest(host=host):
                self.assertEqual(lab.local_docker_host(context(host)), host)

    def test_remote_and_malformed_endpoints_rejected(self):
        for host in ["tcp://127.0.0.1:2375", "ssh://host", "http://localhost", "unix://remote/path", "unix:///path with space", "unix:///path?x", "npipe:////remote/pipe/docker_engine", "", None]:
            with self.subTest(host=host), self.assertRaises(lab.LabFailure):
                lab.local_docker_host(context(host))

    def test_context_shapes_rejected(self):
        for data in [None, {}, [], [1], [{"Endpoints": None}], context() * 2]:
            with self.subTest(data=data), self.assertRaises(lab.LabFailure):
                lab.local_docker_host(data)

    def test_environment_sanitization_case_insensitive_nonmutating(self):
        source = {"PATH": "/bin", "DOCKER_HOST": "ssh://host", "docker_config": "elsewhere",
                  "COMPOSE_FILE": "wrong", "BAO_TOKEN": "private", "vault_addr": "https://prod"}
        original = source.copy()
        self.assertEqual(lab.safe_environment(source), {"PATH": "/bin", "COMPOSE_DISABLE_ENV_FILE": "true"})
        self.assertEqual(source, original)

    def test_both_fixture_shapes_valid(self):
        for product in ("openbao", "vault"):
            lab.verify_container(fixture(product), product, CID)

    def test_vault_tmpfs_mount_representations_allowed(self):
        data = fixture("vault")
        data[0]["Mounts"] = [{"Type": "tmpfs", "Destination": "/vault/file"}, {"Type": "tmpfs", "Destination": "/vault/logs"}]
        data[0]["Config"]["Volumes"] = {"/vault/file": {}, "/vault/logs": {}}
        lab.verify_container(data, "vault", CID)

    def test_wrong_container_id_rejected(self):
        with self.assertRaises(lab.LabFailure):
            lab.verify_container(fixture(), "openbao", "c" * 64)

    def test_invalid_inspect_shape_rejected(self):
        for data in [[], {}, [None], fixture() * 2]:
            with self.subTest(data=data), self.assertRaises(lab.LabFailure):
                lab.verify_container(data, "openbao", CID)

    def test_running_state_required(self):
        self.fail_fixture("State", "Running", False)

    def test_exact_pinned_image_required(self):
        self.fail_fixture("Config", "Image", "openbao/openbao:latest")

    def test_compose_project_required(self):
        self.fail_fixture("Config", "Labels", {"com.docker.compose.project": "production", "com.docker.compose.service": "openbao"})

    def test_compose_service_required(self):
        self.fail_fixture("Config", "Labels", {"com.docker.compose.project": "engineering-foundations-openbao-lab", "com.docker.compose.service": "other"})

    def test_exact_dev_command_required(self):
        self.fail_fixture("Config", "Cmd", ["server", "-config=/prod/config.hcl"])

    def test_network_none_required(self):
        self.fail_fixture("HostConfig", "NetworkMode", "bridge")

    def test_privilege_and_capabilities_refused(self):
        self.fail_fixture("HostConfig", "Privileged", True)
        self.fail_fixture("HostConfig", "CapAdd", ["SYS_ADMIN"])

    def test_host_binds_and_volumes_from_refused(self):
        self.fail_fixture("HostConfig", "Binds", ["/secret:/config"])
        self.fail_fixture("HostConfig", "VolumesFrom", ["production"])

    def test_host_port_bindings_refused(self):
        self.fail_fixture("HostConfig", "PortBindings", {"8200/tcp": [{"HostPort": "8200"}]})
        self.fail_fixture("HostConfig", "PublishAllPorts", True)

    def test_runtime_published_ports_refused(self):
        self.fail_fixture("NetworkSettings", "Ports", {"8200/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8200"}]})

    def test_persistent_image_volume_refused(self):
        data = fixture("vault")
        data[0]["Mounts"] = [{"Type": "volume", "Destination": "/vault/file", "Name": "anonymous"}]
        with self.assertRaises(lab.LabFailure):
            lab.verify_container(data, "vault", CID)

    def test_tmpfs_exact_destinations_required(self):
        self.fail_fixture("HostConfig", "Tmpfs", {}, "vault")
        self.fail_fixture("HostConfig", "Tmpfs", {"/other": "rw,noexec,nosuid,size=16m"})

    def test_tmpfs_options_required(self):
        self.fail_fixture("HostConfig", "Tmpfs", {"/vault/file": "rw", "/vault/logs": "rw"}, "vault")

    def test_environment_exact_address_and_root_required(self):
        self.fail_fixture("Config", "Env", ["BAO_ADDR=https://prod", "BAO_TOKEN=private"])

    def test_namespace_or_duplicate_environment_refused(self):
        for extra in ["BAO_NAMESPACE=other", "VAULT_TOKEN=other", "BAO_TOKEN=duplicate"]:
            self.fail_fixture("Config", "Env", fixture()[0]["Config"]["Env"] + [extra])

    def test_status_version_storage_and_seal_required(self):
        for key, replacement in [("initialized", False), ("sealed", True), ("version", "2.7.0"), ("storage_type", "raft")]:
            data = status()
            data[key] = replacement
            with self.subTest(key=key), self.assertRaises(lab.LabFailure):
                lab.verify_status(data, "openbao")

    def test_root_identity_and_policy_required(self):
        for data in [{}, {"data": {"id": "private", "policies": ["root"]}}, {"data": {"id": lab.root_token("openbao"), "policies": ["default"]}}]:
            with self.subTest(data=data), self.assertRaises(lab.LabFailure):
                lab.verify_root(data, "openbao")


class OracleTests(unittest.TestCase):
    def test_json_invalid_encoding_and_shape(self):
        for raw in [b"invalid", b"\xff", b"{", None]:
            with self.subTest(raw=raw), self.assertRaises(lab.LabFailure):
                lab.parse_json(raw)

    def test_version_exact_integer_required(self):
        lab.verify_version({"data": {"version": 1}}, 1)
        for replacement in [True, "1", 2, None]:
            with self.subTest(replacement=replacement), self.assertRaises(lab.LabFailure):
                lab.verify_version({"data": {"version": replacement}}, 1)

    def test_read_value_and_version_required(self):
        lab.verify_value(value())
        for data in [{}, {"data": {"data": {"message": "wrong"}, "metadata": {"version": 2}}}, {"data": {"data": {"message": "public-synthetic-v2"}, "metadata": {"version": 3}}}]:
            with self.subTest(data=data), self.assertRaises(lab.LabFailure):
                lab.verify_value(data)

    def test_child_token_scope_bounded(self):
        self.assertEqual(lab.child_token(token(), NAME), CHILD)
        for key, replacement in [("policies", [NAME, "default"]), ("lease_duration", 301), ("lease_duration", 0), ("lease_duration", True), ("renewable", True)]:
            data = token()
            data["auth"][key] = replacement
            with self.subTest(key=key, value=replacement), self.assertRaises(lab.LabFailure):
                lab.child_token(data, NAME)

    def test_child_token_control_chars_and_length_refused(self):
        for candidate in [CHILD + "\n", "short", "x" * 4097, None]:
            data = token()
            data["auth"]["client_token"] = candidate
            with self.subTest(candidate=candidate), self.assertRaises(lab.LabFailure):
                lab.child_token(data, NAME)

    def test_http_403_oracle_accepts_only_specific_denial(self):
        lab.verify_http_error(denied(), 403)
        for response in [result(raw=b"", code=0), denied(500), result(raw=b"", code=2, stderr=b"connection refused"), result(raw=b"secret", code=2, stderr=b"Code: 403. Errors:\n")]:
            with self.subTest(response=response), self.assertRaises(lab.LabFailure):
                lab.verify_http_error(response, 403)

    def test_multiple_error_codes_rejected(self):
        response = denied()
        response.stderr += b"Code: 403. Errors:\n"
        with self.assertRaises(lab.LabFailure):
            lab.verify_http_error(response, 403)

    def test_cas_400_requires_specific_semantics(self):
        lab.verify_http_error(denied(400, "check-and-set parameter did not match the current version"), 400, cas=True)
        with self.assertRaises(lab.LabFailure):
            lab.verify_http_error(denied(400, "invalid request body"), 400, cas=True)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.locator = patch.object(lab.shutil, "which", return_value="docker")
        self.locator.start()
        self.addCleanup(self.locator.stop)
        self.client = lab.LocalClient("openbao")
        self.client.name = NAME

    def ready(self):
        self.client.host = HOST
        self.client.container = CID
        self.client.fixture_verified = True
        self.client.identity_verified = True

    def test_complete_mock_run_both_products(self):
        for product in ("openbao", "vault"):
            client = lab.LocalClient(product)
            client.name = NAME
            with self.subTest(product=product), patch.object(lab.subprocess, "run", side_effect=responses(product)) as run:
                report = lab.run_lab(client)
                self.assertEqual(report["status"], "PASS")
                self.assertEqual(report["commands"], 19)
                self.assertTrue(report["child_token_revoked"])
                self.assertTrue(report["artifacts_retained"])
                self.assertEqual(len(report["oracles"]), 8)
                self.assertEqual(run.call_count, 19)

    def test_subprocess_has_pinned_host_stdin_only_token_and_no_shell(self):
        with patch.object(lab.subprocess, "run", side_effect=responses()) as run:
            lab.run_lab(self.client)
        for index, call in enumerate(run.call_args_list):
            argv = call.args[0]
            kwargs = call.kwargs
            self.assertNotIn(CHILD, " ".join(argv))
            self.assertNotIn(CHILD, str(kwargs["env"]))
            self.assertFalse(kwargs["shell"])
            self.assertEqual(kwargs["timeout"], 30)
            self.assertEqual(kwargs["env"]["COMPOSE_DISABLE_ENV_FILE"], "true")
            if index:
                self.assertEqual(argv[1:3], ["--host", HOST])
        child_calls = run.call_args_list[13:18]
        self.assertTrue(all(call.kwargs["input"].startswith((CHILD + "\n").encode()) for call in child_calls))
        verbs = [call.args[0][3] for call in run.call_args_list[1:]]
        self.assertFalse(set(verbs) & {"run", "start", "stop", "rm", "restart"})

    def test_default_and_product_only_are_inert(self):
        for argv in [[], ["--product", "openbao"], ["--run-local"]]:
            with self.subTest(argv=argv), patch.object(lab.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    lab.main(argv)
                self.assertEqual(error.exception.code, 2)
                run.assert_not_called()

    def test_help_is_inert(self):
        with patch.object(lab.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                lab.main(["--help"])
            self.assertEqual(error.exception.code, 0)
            run.assert_not_called()

    def test_unknown_product_refused(self):
        with self.assertRaises(lab.LabFailure):
            lab.LocalClient("production")

    def test_missing_docker_no_subprocess(self):
        self.client.docker = None
        with patch.object(lab.subprocess, "run") as run, self.assertRaises(lab.LabFailure):
            self.client.connect()
        run.assert_not_called()

    def test_remote_context_stops_before_container_lookup(self):
        with patch.object(lab.subprocess, "run", return_value=result(context("ssh://prod"))) as run, self.assertRaises(lab.LabFailure):
            self.client.connect()
        self.assertEqual(run.call_count, 1)
        self.assertFalse(self.client.mutation_attempted)

    def test_wrong_fixture_stops_before_any_cli(self):
        replies = responses()
        changed = fixture()
        changed[0]["HostConfig"]["NetworkMode"] = "bridge"
        replies[2] = result(changed)
        with patch.object(lab.subprocess, "run", side_effect=replies) as run, self.assertRaises(lab.LabFailure):
            lab.run_lab(self.client)
        self.assertEqual(run.call_count, 3)
        self.assertFalse(self.client.mutation_attempted)

    def test_wrong_status_stops_before_writes(self):
        replies = responses()
        data = status()
        data["storage_type"] = "raft"
        replies[3] = result(data)
        with patch.object(lab.subprocess, "run", side_effect=replies) as run, self.assertRaises(lab.LabFailure):
            lab.run_lab(self.client)
        self.assertEqual(run.call_count, 4)
        self.assertFalse(self.client.mutation_attempted)

    def test_wrong_root_stops_before_writes(self):
        replies = responses()
        replies[4] = result({"data": {"id": "private", "policies": ["root"]}})
        with patch.object(lab.subprocess, "run", side_effect=replies) as run, self.assertRaises(lab.LabFailure):
            lab.run_lab(self.client)
        self.assertEqual(run.call_count, 5)
        self.assertFalse(self.client.mutation_attempted)

    def test_policy_collision_stops_before_writes(self):
        replies = responses()
        replies[5] = result(["default", "root", NAME])
        with patch.object(lab.subprocess, "run", side_effect=replies) as run, self.assertRaises(lab.LabFailure):
            lab.run_lab(self.client)
        self.assertEqual(run.call_count, 6)
        self.assertFalse(self.client.mutation_attempted)

    def test_write_requires_verified_fixture_and_identity(self):
        with patch.object(lab.subprocess, "run") as run:
            with self.assertRaises(lab.LabFailure):
                self.client.execute("mount")
            self.ready()
            self.client.identity_verified = False
            with self.assertRaises(lab.LabFailure):
                self.client.execute("mount")
            run.assert_not_called()

    def test_invalid_namespace_and_unknown_stage_refused(self):
        self.ready()
        with patch.object(lab.subprocess, "run") as run:
            with self.assertRaises(lab.LabFailure):
                self.client.execute("delete_mount")
            self.client.name = "../production"
            with self.assertRaises(lab.LabFailure):
                self.client.execute("mount")
            run.assert_not_called()

    def test_child_stage_cannot_use_root_or_missing_token(self):
        self.ready()
        with patch.object(lab.subprocess, "run") as run:
            for stage, token_value in [("allowed_read", None), ("allowed_read", lab.root_token("openbao")), ("policy", CHILD)]:
                with self.subTest(stage=stage, token=token_value), self.assertRaises(lab.LabFailure):
                    self.client.execute(stage, token_value)
            run.assert_not_called()

    def test_context_cannot_be_reinspected_or_mutated_to_remote(self):
        self.ready()
        with patch.object(lab.subprocess, "run") as run:
            with self.assertRaises(lab.LabFailure):
                self.client.connect()
            self.client.host = "tcp://localhost:2375"
            with self.assertRaises(lab.LabFailure):
                self.client.execute("status")
            run.assert_not_called()

    def test_command_budget_and_timeout_are_fixed_errors(self):
        self.client.commands = lab.MAX_COMMANDS
        with patch.object(lab.subprocess, "run") as run, self.assertRaisesRegex(lab.LabFailure, "command_budget_exceeded"):
            self.client.invoke([])
        run.assert_not_called()
        self.client.commands = 0
        with patch.object(lab.subprocess, "run", side_effect=subprocess.TimeoutExpired("secret command", 30)), self.assertRaisesRegex(lab.LabFailure, "command_timeout_server_state_unknown"):
            self.client.invoke([])

    def test_process_os_failure_and_output_limit(self):
        with patch.object(lab.subprocess, "run", side_effect=OSError("private")), self.assertRaisesRegex(lab.LabFailure, "docker_command_failed"):
            self.client.invoke([])
        with patch.object(lab.subprocess, "run", return_value=result(raw=b"x" * (lab.MAX_OUTPUT_BYTES + 1))), self.assertRaisesRegex(lab.LabFailure, "output_too_large"):
            self.client.invoke([])

    def test_error_output_is_redacted_and_no_cleanup_is_attempted(self):
        replies = responses()
        replies[14] = result(raw=b"", code=2, stderr=("connection failed " + CHILD).encode())
        output = io.StringIO()
        with patch.object(lab, "LocalClient", return_value=self.client), patch.object(lab.subprocess, "run", side_effect=replies) as run, contextlib.redirect_stdout(output):
            self.assertEqual(lab.main(["--product", "openbao", "--run-local"]), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["error"], "expected_http_rejection_missing")
        self.assertTrue(report["mutation_attempted"])
        self.assertFalse(report["cleanup_performed"])
        self.assertNotIn(CHILD, output.getvalue())
        self.assertEqual(run.call_count, 15)

    def test_success_output_has_no_token(self):
        output = io.StringIO()
        with patch.object(lab, "LocalClient", return_value=self.client), patch.object(lab.subprocess, "run", side_effect=responses()), contextlib.redirect_stdout(output):
            self.assertEqual(lab.main(["--product", "openbao", "--run-local"]), 0)
        self.assertNotIn(CHILD, output.getvalue())
        self.assertNotIn(lab.root_token("openbao"), output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
