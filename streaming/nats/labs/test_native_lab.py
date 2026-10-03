"""Offline contract tests; no installed SDK, process, network, or fixture writes."""

import asyncio
import io
import json
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import urlparse

import native_lab as lab


RUN = "NATS_LAB_" + "a" * 32
STREAM = RUN + "_STREAM"
DURABLE = RUN + "_WORKER"
PASSWORD = "synthetic-test-only-" + "a" * 32


class NoResponders(Exception):
    pass


def sdk_fixture():
    return NS(
        NoRespondersError=NoResponders,
        StreamConfig=lambda **values: NS(**values),
        ConsumerConfig=lambda **values: NS(**values),
        StorageType=NS(FILE="file"), RetentionPolicy=NS(LIMITS="limits"),
        AckPolicy=NS(EXPLICIT="explicit"), DeliverPolicy=NS(ALL="all"),
        ReplayPolicy=NS(INSTANT="instant"),
    )


def delivery(count):
    return NS(data=lab.FIRST_BODY, metadata=NS(sequence=NS(stream=1, consumer=count),
                                             num_delivered=count),
              nak=AsyncMock(), ack_sync=AsyncMock())


def client_fixture():
    first, second = delivery(1), delivery(2)
    pull = NS(fetch=AsyncMock(side_effect=[[first], [second]]), unsubscribe=AsyncMock())
    core = NS(next_msg=AsyncMock(return_value=NS(subject=RUN + ".core", data=b"synthetic-core")),
              unsubscribe=AsyncMock())
    initial = NS(config=NS(name=STREAM, storage="file"), state=NS(messages=0))
    ack_one = NS(stream=STREAM, seq=1, duplicate=None)
    ack_two = NS(stream=STREAM, seq=1, duplicate=True)
    pending = NS(num_ack_pending=1, config=NS(max_ack_pending=1))
    final = NS(num_ack_pending=0, num_pending=0)
    js = NS(
        add_stream=AsyncMock(return_value=initial),
        publish=AsyncMock(side_effect=[ack_one, ack_two]),
        get_msg=AsyncMock(return_value=NS(data=lab.FIRST_BODY)),
        pull_subscribe=AsyncMock(return_value=pull),
        consumer_info=AsyncMock(side_effect=[pending, final]),
        stream_info=AsyncMock(return_value=NS(state=NS(messages=1))),
    )
    client = NS(
        subscribe=AsyncMock(return_value=core), flush=AsyncMock(), publish=AsyncMock(),
        request=AsyncMock(side_effect=NoResponders), jetstream=Mock(return_value=js),
        close=AsyncMock(), connect=AsyncMock(),
        _server_info={"version": lab.SERVER_VERSION, "server_name": RUN,
                      "jetstream": True, "server_id": "synthetic-server"},
        connected_url=urlparse("nats://127.0.0.1:12345"),
    )
    return NS(client=client, core=core, js=js, first=first, second=second, pull=pull,
              initial=initial, ack_one=ack_one, ack_two=ack_two, pending=pending, final=final)


class DryPlanTests(unittest.TestCase):
    def test_default_has_no_side_effects(self):
        with patch.object(lab, "run_local") as run, patch.object(lab, "load_sdk") as sdk, \
                patch.object(lab.subprocess, "run") as process, patch.object(lab, "storage_parent") as storage, \
                patch.object(lab, "reserve_port") as port, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(lab.main([]), 0)
        for operation in (run, sdk, process, storage, port):
            operation.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertFalse(result["server_started"])
        self.assertFalse(result["network_used"])
        self.assertFalse(result["files_written"])

    def test_binary_alone_does_not_opt_in(self):
        with patch.object(lab, "run_local") as run, redirect_stdout(io.StringIO()):
            self.assertEqual(lab.main(["--server-binary", "unused"]), 0)
        run.assert_not_called()

    def test_missing_binary_is_usage_error(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            lab.main(["--run-local"])
        self.assertEqual(caught.exception.code, 2)

    def test_unknown_url_argument_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            lab.main(["--url", "nats://foreign.example"])

    def test_failure_redacts_external_exception(self):
        with patch.object(lab, "run_local", side_effect=ValueError("secret:password")), \
                redirect_stderr(io.StringIO()) as output:
            self.assertEqual(lab.main(["--run-local", "--server-binary", "x"]), 1)
        self.assertNotIn("password", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["error"], "ValueError")

    def test_success_json(self):
        with patch.object(lab, "run_local", return_value={"check_count": 10}), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(lab.main(["--run-local", "--server-binary", "x"]), 0)
        self.assertEqual(json.loads(output.getvalue()), {"check_count": 10})


class GateTests(unittest.TestCase):
    def test_require_survives_optimization(self):
        with self.assertRaises(lab.LabFailure):
            lab.require(False, "must fail")

    def test_environment_allowlist(self):
        environment = lab.safe_environment({"Path": "bin", "SYSTEMROOT": "windows", "NATS_URL": "remote",
                                           "NATS_TOKEN": "secret", "HTTP_PROXY": "proxy", "AWS_SECRET": "secret"})
        self.assertEqual(environment, {"PATH": "bin", "SYSTEMROOT": "windows"})

    def test_environment_rejects_nul_and_shell_function(self):
        self.assertEqual(lab.safe_environment({"PATH": "a\x00b", "LANG": "() evil", "TEMP": None}), {})

    def test_missing_sdk(self):
        with patch.object(lab.metadata, "version", side_effect=metadata.PackageNotFoundError), \
                self.assertRaises(lab.LabFailure):
            lab.load_sdk()

    def test_wrong_sdk(self):
        with patch.object(lab.metadata, "version", return_value="2.15.0"), self.assertRaises(lab.LabFailure):
            lab.load_sdk()

    def test_relative_binary_refused(self):
        with patch.object(lab.subprocess, "run") as process, self.assertRaises(lab.LabFailure):
            lab.check_binary("relative.exe")
        process.assert_not_called()

    def test_missing_binary_refused(self):
        with patch.object(Path, "is_file", return_value=False), self.assertRaises(lab.LabFailure):
            lab.check_binary(str(lab.REPO / "missing.exe"))

    def test_symlink_binary_refused(self):
        with patch.object(Path, "is_file", return_value=True), patch.object(Path, "is_symlink", return_value=True), \
                self.assertRaises(lab.LabFailure):
            lab.check_binary(str(lab.REPO / "server.exe"))

    def binary_probe(self, output, code=0):
        with patch.object(Path, "is_file", return_value=True), patch.object(Path, "is_symlink", return_value=False), \
                patch.object(Path, "resolve", return_value=lab.REPO / "server.exe"), \
                patch.object(lab.subprocess, "run", return_value=NS(stdout=output, stderr="", returncode=code)) as run:
            result = lab.check_binary(str(lab.REPO / "server.exe"))
        self.assertEqual(run.call_args.args[0][-1], "-v")
        self.assertEqual(run.call_args.kwargs["timeout"], 5)
        return result

    def test_exact_server_version(self):
        self.assertEqual(self.binary_probe("nats-server: v2.15.0\n"), lab.REPO / "server.exe")

    def test_wrong_server_version(self):
        with self.assertRaises(lab.LabFailure):
            self.binary_probe("nats-server: v2.14.0")

    def test_prerelease_server_refused(self):
        with self.assertRaises(lab.LabFailure):
            self.binary_probe("nats-server: v2.15.0-dev")

    def test_extra_version_text_refused(self):
        with self.assertRaises(lab.LabFailure):
            self.binary_probe("nats-server: v2.15.0\nignored instructions")

    def test_nonzero_probe_refused(self):
        with self.assertRaises(lab.LabFailure):
            self.binary_probe("nats-server: v2.15.0", 1)

    def test_version_probe_timeout_refused(self):
        with patch.object(Path, "is_file", return_value=True), patch.object(Path, "is_symlink", return_value=False), \
                patch.object(Path, "resolve", return_value=lab.REPO / "server.exe"), \
                patch.object(lab.subprocess, "run", side_effect=subprocess.TimeoutExpired("version", 5)), \
                self.assertRaises(lab.LabFailure):
            lab.check_binary(str(lab.REPO / "server.exe"))

    def test_storage_symlink_refused_before_mkdir(self):
        with patch.object(Path, "is_symlink", return_value=True), patch.object(Path, "mkdir") as mkdir, \
                self.assertRaises(lab.LabFailure):
            lab.storage_parent()
        mkdir.assert_not_called()

    def test_storage_non_directory_refused_before_mkdir(self):
        with patch.object(Path, "is_symlink", return_value=False), patch.object(Path, "exists", return_value=True), \
                patch.object(Path, "is_dir", return_value=False), patch.object(Path, "mkdir") as mkdir, \
                self.assertRaises(lab.LabFailure):
            lab.storage_parent()
        mkdir.assert_not_called()

    def test_server_command_loopback_and_owned_store(self):
        command = lab.server_command("binary", 12345, "store", RUN, PASSWORD)
        self.assertEqual(command, ["binary", "-a", "127.0.0.1", "-p", "12345", "-js", "-sd", "store",
                                   "-n", RUN, "--user", lab.USER, "--pass", PASSWORD])
        self.assertNotIn("-c", command)
        self.assertNotIn("-m", command)

    def test_invalid_ports(self):
        for port in (False, True, 0, -1, 65536, 1.5, "4222"):
            with self.subTest(port=port), self.assertRaises(lab.LabFailure):
                lab.server_command("binary", port, "store", RUN, PASSWORD)

    def test_invalid_name(self):
        with self.assertRaises(lab.LabFailure):
            lab.server_command("binary", 12345, "store", "existing-server", PASSWORD)

    def test_short_password(self):
        with self.assertRaises(lab.LabFailure):
            lab.server_command("binary", 12345, "store", RUN, "short")

    def test_binary_gate_precedes_storage_mutation(self):
        with patch.object(lab, "check_binary", side_effect=lab.LabFailure("version")), \
                patch.object(lab, "storage_parent") as storage, patch.object(lab, "load_sdk") as sdk, \
                self.assertRaises(lab.LabFailure):
            lab.run_local("binary")
        storage.assert_not_called()
        sdk.assert_not_called()

    def test_sdk_gate_precedes_storage_mutation(self):
        with patch.object(lab, "check_binary", return_value=Path("binary")), \
                patch.object(lab, "load_sdk", side_effect=lab.LabFailure("SDK")), \
                patch.object(lab, "storage_parent") as storage, self.assertRaises(lab.LabFailure):
            lab.run_local("binary")
        storage.assert_not_called()


class IdentityTests(unittest.TestCase):
    def test_owned_identity(self):
        lab.check_identity(client_fixture().client, RUN, 12345)

    def test_identity_mismatches(self):
        for key, value in (("version", "2.14.0"), ("server_name", "foreign"), ("jetstream", False),
                           ("jetstream", 1), ("server_id", ""), ("server_id", None)):
            fixture = client_fixture()
            fixture.client._server_info[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(lab.LabFailure):
                lab.check_identity(fixture.client, RUN, 12345)

    def test_foreign_urls(self):
        for url in ("nats://localhost:12345", "nats://127.0.0.1:4222", "nats://example.com:12345"):
            fixture = client_fixture()
            fixture.client.connected_url = urlparse(url)
            with self.subTest(url=url), self.assertRaises(lab.LabFailure):
                lab.check_identity(fixture.client, RUN, 12345)

    def test_missing_url(self):
        fixture = client_fixture()
        fixture.client.connected_url = None
        with self.assertRaises(lab.LabFailure):
            lab.check_identity(fixture.client, RUN, 12345)


class AsyncContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_literal_oracles(self):
        fixture = client_fixture()
        result = await lab.exercise(fixture.client, sdk_fixture(), RUN)
        self.assertEqual(result["check_count"], 10)
        self.assertEqual(result["business"], {"deliveries": 2, "naive_total": 14,
                         "idempotent_total": 7, "applied_business_keys": 1, "transactional_database": False})
        fixture.first.nak.assert_awaited_once_with()
        fixture.second.ack_sync.assert_awaited_once_with(timeout=2)
        fixture.pull.unsubscribe.assert_awaited_once_with()
        config = fixture.js.add_stream.call_args.kwargs["config"]
        self.assertEqual(config.num_replicas, 1)
        self.assertEqual(config.duplicate_window, 30)
        self.assertEqual(config.max_age, 60)

    async def test_core_wrong_payload_refused(self):
        fixture = client_fixture()
        fixture.core.next_msg.return_value.data = b"wrong"
        with self.assertRaises(lab.LabFailure):
            await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_request_unexpected_success_refused(self):
        fixture = client_fixture()
        fixture.client.request.side_effect = None
        with self.assertRaises(lab.LabFailure):
            await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_request_timeout_is_not_no_responder_success(self):
        fixture = client_fixture()
        fixture.client.request.side_effect = asyncio.TimeoutError
        with self.assertRaises(asyncio.TimeoutError):
            await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_dirty_stream_refused(self):
        fixture = client_fixture()
        fixture.initial.state.messages = 1
        with self.assertRaises(lab.LabFailure):
            await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_memory_stream_refused(self):
        fixture = client_fixture()
        fixture.initial.config.storage = "memory"
        with self.assertRaises(lab.LabFailure):
            await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_publish_ack_corruptions(self):
        for target, key, value in (("ack_one", "seq", 2), ("ack_one", "duplicate", True),
                                   ("ack_one", "stream", "foreign"), ("ack_two", "seq", 2),
                                   ("ack_two", "duplicate", False), ("ack_two", "stream", "foreign")):
            fixture = client_fixture()
            setattr(getattr(fixture, target), key, value)
            with self.subTest(target=target, key=key), self.assertRaises(lab.LabFailure):
                await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_changed_stored_body_refused(self):
        fixture = client_fixture()
        fixture.js.get_msg.return_value.data = lab.OTHER_BODY
        with self.assertRaises(lab.LabFailure):
            await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_empty_delivery_refused(self):
        fixture = client_fixture()
        fixture.pull.fetch.side_effect = [[]]
        with self.assertRaises(lab.LabFailure):
            await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_redelivery_metadata_corruptions(self):
        for target, value in (("stream", 2), ("consumer", 1), ("num_delivered", 1)):
            fixture = client_fixture()
            if target == "num_delivered":
                fixture.second.metadata.num_delivered = value
            else:
                setattr(fixture.second.metadata.sequence, target, value)
            with self.subTest(target=target), self.assertRaises(lab.LabFailure):
                await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_initial_pending_must_be_one(self):
        fixture = client_fixture()
        fixture.pending.num_ack_pending = 0
        with self.assertRaises(lab.LabFailure):
            await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_final_pending_must_be_zero(self):
        for key in ("num_ack_pending", "num_pending"):
            fixture = client_fixture()
            setattr(fixture.final, key, 1)
            with self.subTest(key=key), self.assertRaises(lab.LabFailure):
                await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_limits_retention_must_keep_message(self):
        fixture = client_fixture()
        fixture.js.stream_info.return_value.state.messages = 0
        with self.assertRaises(lab.LabFailure):
            await lab.exercise(fixture.client, sdk_fixture(), RUN)

    async def test_connect_uses_only_owned_endpoint_without_reconnect(self):
        fixture = client_fixture()
        sdk = NS(Client=Mock(return_value=fixture.client))
        process = Mock(poll=Mock(return_value=None))
        result = await lab.connect_owned(sdk, process, 12345, RUN, PASSWORD)
        self.assertIs(result, fixture.client)
        options = fixture.client.connect.call_args.kwargs
        self.assertEqual(options["servers"], ["nats://127.0.0.1:12345"])
        self.assertFalse(options["allow_reconnect"])
        self.assertEqual(options["max_reconnect_attempts"], 0)
        self.assertEqual(options["password"], PASSWORD)

    async def test_exited_server_never_connects(self):
        sdk = NS(Client=Mock())
        with self.assertRaises(lab.LabFailure):
            await lab.connect_owned(sdk, Mock(poll=Mock(return_value=1)), 12345, RUN, PASSWORD)
        sdk.Client.assert_not_called()

    async def test_identity_failure_closes_client(self):
        fixture = client_fixture()
        fixture.client._server_info["server_name"] = "foreign"
        with self.assertRaises(lab.LabFailure):
            await lab.connect_owned(NS(Client=lambda: fixture.client), Mock(poll=lambda: None), 12345, RUN, PASSWORD)
        fixture.client.close.assert_awaited_once_with()

    async def test_readiness_deadline(self):
        with patch.object(lab.time, "monotonic", side_effect=[0, 6]), self.assertRaises(lab.LabFailure):
            await lab.connect_owned(NS(Client=Mock()), Mock(poll=lambda: None), 12345, RUN, PASSWORD)

    async def test_refusal_retry_closes_failed_client(self):
        fixture = client_fixture()
        fixture.client.connect.side_effect = [OSError(), None]
        with patch.object(lab.asyncio, "sleep", new=AsyncMock()):
            result = await lab.connect_owned(NS(Client=lambda: fixture.client), Mock(poll=lambda: None),
                                             12345, RUN, PASSWORD)
        self.assertIs(result, fixture.client)
        fixture.client.close.assert_awaited_once_with()

    async def test_authentication_error_closes_client_without_retry(self):
        fixture = client_fixture()
        fixture.client.connect.side_effect = ValueError("synthetic authentication failure")
        sdk = NS(Client=Mock(return_value=fixture.client))
        with self.assertRaises(ValueError):
            await lab.connect_owned(sdk, Mock(poll=lambda: None), 12345, RUN, PASSWORD)
        fixture.client.close.assert_awaited_once_with()
        self.assertEqual(sdk.Client.call_count, 1)

    async def test_session_failure_closes_client(self):
        fixture = client_fixture()
        with patch.object(lab, "connect_owned", new=AsyncMock(return_value=fixture.client)), \
                patch.object(lab, "exercise", new=AsyncMock(side_effect=lab.LabFailure("oracle"))), \
                self.assertRaises(lab.LabFailure):
            await lab.run_session(sdk_fixture(), Mock(), 12345, RUN, PASSWORD)
        fixture.client.close.assert_awaited_once_with()


class CleanupAndBusinessTests(unittest.TestCase):
    def local_run_context(self, session_error=None, stop_error=None):
        parent = lab.REPO / "lab-workspaces" / "nats-native"
        temporary = Mock(name=str(parent / "owned-test"))
        temporary.name = str(parent / "owned-test")
        process = Mock()
        patches = [
            patch.object(lab, "check_binary", return_value=Path("binary")),
            patch.object(lab, "load_sdk", return_value=sdk_fixture()),
            patch.object(lab, "storage_parent", return_value=parent),
            patch.object(lab.tempfile, "TemporaryDirectory", return_value=temporary),
            patch.object(Path, "resolve", lambda path, **kwargs: path),
            patch.object(lab, "reserve_port", return_value=12345),
            patch.object(lab.subprocess, "Popen", return_value=process),
            patch.object(lab, "run_session", new=AsyncMock(side_effect=session_error,
                                                           return_value={"check_count": 10})),
            patch.object(lab, "stop_owned", side_effect=stop_error),
        ]
        return temporary, process, patches

    def test_full_lifecycle_cleans_after_success(self):
        temporary, process, patches = self.local_run_context()
        from contextlib import ExitStack
        with ExitStack() as stack:
            active = [stack.enter_context(item) for item in patches]
            result = lab.run_local("binary")
        active[-1].assert_called_once_with(process)
        temporary.cleanup.assert_called_once_with()
        temporary._finalizer.detach.assert_not_called()
        self.assertTrue(result["owned_server_stopped"])
        self.assertTrue(result["owned_storage_removed"])

    def test_full_lifecycle_stops_and_cleans_after_oracle_failure(self):
        temporary, process, patches = self.local_run_context(session_error=lab.LabFailure("oracle"))
        from contextlib import ExitStack
        with ExitStack() as stack:
            active = [stack.enter_context(item) for item in patches]
            with self.assertRaises(lab.LabFailure):
                lab.run_local("binary")
        active[-1].assert_called_once_with(process)
        temporary.cleanup.assert_called_once_with()

    def test_full_lifecycle_preserves_storage_if_process_cannot_stop(self):
        temporary, process, patches = self.local_run_context(stop_error=lab.LabFailure("still running"))
        from contextlib import ExitStack
        with ExitStack() as stack:
            active = [stack.enter_context(item) for item in patches]
            with self.assertRaises(lab.LabFailure):
                lab.run_local("binary")
        active[-1].assert_called_once_with(process)
        temporary.cleanup.assert_not_called()
        temporary._finalizer.detach.assert_called_once_with()

    def test_failed_launch_still_cleans_new_storage(self):
        temporary, process, patches = self.local_run_context()
        from contextlib import ExitStack
        with ExitStack() as stack:
            active = [stack.enter_context(item) for item in patches]
            active[6].side_effect = OSError("cannot start")
            with self.assertRaises(OSError):
                lab.run_local("binary")
        active[-1].assert_not_called()
        temporary.cleanup.assert_called_once_with()

    def test_owned_process_already_exited(self):
        process = Mock(poll=Mock(return_value=0))
        lab.stop_owned(process)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_owned_process_terminates_then_waits(self):
        process = Mock(poll=Mock(return_value=None))
        lab.stop_owned(process)
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=3)
        process.kill.assert_not_called()

    def test_timeout_kills_only_owned_process(self):
        process = Mock(poll=Mock(return_value=None), wait=Mock(side_effect=[subprocess.TimeoutExpired("owned", 3), 0]))
        lab.stop_owned(process)
        process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_count, 2)

    def test_failed_kill_withholds_cleanup(self):
        process = Mock(poll=Mock(return_value=None), wait=Mock(side_effect=subprocess.TimeoutExpired("owned", 3)))
        with self.assertRaises(lab.LabFailure):
            lab.stop_owned(process)

    def test_business_expected_duplicate(self):
        result = lab.verify_business_ledger([delivery(1), delivery(2)])
        self.assertEqual(result["naive_total"], 14)
        self.assertEqual(result["idempotent_total"], 7)

    def test_business_bad_count_refused(self):
        for messages in ([], [delivery(1)], [delivery(1), delivery(2), delivery(3)]):
            with self.subTest(count=len(messages)), self.assertRaises(lab.LabFailure):
                lab.verify_business_ledger(messages)

    def test_business_changed_payload_refused(self):
        second = delivery(2)
        second.data = lab.OTHER_BODY
        with self.assertRaises(lab.LabFailure):
            lab.verify_business_ledger([delivery(1), second])


if __name__ == "__main__":
    unittest.main()
