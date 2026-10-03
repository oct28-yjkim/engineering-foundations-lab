"""Subprocess-free MySQL client contracts; no server behavior is verified here."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import Mock, patch

import engine_lab as lab


DATABASE = "efl_mysql_" + "a" * 32
SOCKET = "unix:///var/run/docker.sock"
IDENTITY = "8.4.11\tefl-mysql-lab\t8411\tInnoDB\t1\t1\tROW\tON\tON\n"


def context(host=SOCKET):
    return [{"Name": "default", "Endpoints": {"docker": {"Host": host}}}]


def result(stdout=b"", stderr=b"", returncode=0):
    if isinstance(stdout, str):
        stdout = stdout.encode("utf-8")
    if isinstance(stderr, str):
        stderr = stderr.encode("utf-8")
    return subprocess.CompletedProcess(["docker"], returncode, stdout, stderr)


def rows_text(stage):
    return "\n".join("\t".join(row) for row in lab.EXPECTED_ROWS[stage]) + "\n"


def successful_results():
    return [
        result(json.dumps(context())), result(IDENTITY), result("created\n"),
        result("fixture\t2\t4\n"),
        result("counts\t4\t3\t2\t3100\nnot_in_null\t0\nanti_join\t102,104\n"
               "groups\t<NULL>\t1\ngroups\tx\t2\ngroups\ty\t1\n"
               "join\talpha\t1500\njoin\tbeta\t1600\n"
               "index\towner_code,balance_cents\ncovering_result\t1\t10000\n"),
        result('{"query_block": {"select_id": 1, "table": {"access_type": "ALL"}}}'),
        result("commit\t1:8750,2:6250\t15000\n"),
        result("before_rollback\t1:8250,2:6750\t15000\nafter_rollback\t1:8750,2:6250\t15000\n"),
        result(stderr="ERROR 1062 (23000) at line 8: duplicate fixture key\n", returncode=1),
        result(stderr="ERROR 1452 (23000) at line 8: fixture foreign key\n", returncode=1),
        result(stderr="ERROR 3819 (HY000) at line 8: fixture check constraint\n", returncode=1),
        result("accounts\t1:alpha:8750,2:beta:6250\t2\t15000\n"
               "orders\t101:1:1200:USD:x,102:1:300:<NULL>:x,103:2:700:USD:<NULL>,104:2:900:EUR:y\t4\n"
               "engines\taccounts:InnoDB,orders:InnoDB\n"),
    ]


def client_ready(*, identity=True, created=True):
    with patch.object(lab.uuid, "uuid4", return_value=Mock(hex="a" * 32)), patch.object(lab.shutil, "which", return_value="docker"):
        client = lab.LocalClient()
    client.host = SOCKET
    client.identity_verified = identity
    client.database_created = created
    return client


class EndpointTests(unittest.TestCase):
    def test_unix_default_is_allowed(self):
        self.assertEqual(lab.local_docker_host(context()), SOCKET)

    def test_unix_rootless_socket_is_allowed(self):
        self.assertEqual(lab.local_docker_host(context("unix:///run/user/1000/docker.sock")),
                         "unix:///run/user/1000/docker.sock")

    def test_desktop_local_sockets_are_allowed(self):
        for host in ("unix:///Users/learner/.docker/run/docker.sock",
                     "unix:///home/learner/.docker/desktop/docker.sock", *lab.LOCAL_PIPES):
            with self.subTest(host=host):
                self.assertEqual(lab.local_docker_host(context(host)), host)

    def test_tcp_loopback_is_deliberately_not_allowed(self):
        with self.assertRaisesRegex(lab.LabFailure, "remote_docker_endpoint_refused"):
            lab.local_docker_host(context("tcp://127.0.0.1:2375"))

    def test_remote_tcp_ssh_and_named_pipe_are_refused(self):
        for host in ("tcp://production:2376", "ssh://root@production", "npipe:////server/pipe/docker_engine"):
            with self.subTest(host=host), self.assertRaises(lab.LabFailure):
                lab.local_docker_host(context(host))

    def test_malformed_unix_and_control_characters_are_refused(self):
        for host in ("unix://relative.sock", "unix:///", "unix:///tmp/socket\n", "unix:///tmp/sock?override=tcp",
                     "unix:///tmp/sock\x00", "unix:///tmp/my socket", "unix:///tmp\\socket"):
            with self.subTest(host=host), self.assertRaises(lab.LabFailure):
                lab.local_docker_host(context(host))

    def test_missing_context_shapes_are_refused(self):
        for data in (None, {}, [], [None], [{"Endpoints": []}], [{"Endpoints": {"docker": {}}}]):
            with self.subTest(data=data), self.assertRaises(lab.LabFailure):
                lab.local_docker_host(data)

    def test_multiple_contexts_are_not_guessed(self):
        with self.assertRaisesRegex(lab.LabFailure, "invalid_docker_context"):
            lab.local_docker_host(context() + context())

    def test_environment_overrides_are_removed_case_insensitively(self):
        original = {"PATH": "system", "HOME": "/user", "DOCKER_HOST": "ssh://production", "docker_context": "production",
                    "DOCKER_TLS_VERIFY": "1", "DOCKER_CONFIG": "/private", "COMPOSE_FILE": "other.yml",
                    "COMPOSE_PROJECT_NAME": "production", "MYSQL_PWD": "private", "custom": "preserved"}
        sanitized = lab.safe_environment(original)
        self.assertEqual(sanitized, {"PATH": "system", "HOME": "/user", "custom": "preserved",
                                     "COMPOSE_DISABLE_ENV_FILE": "true"})
        self.assertEqual(original["DOCKER_HOST"], "ssh://production")


class TransportTests(unittest.TestCase):
    def test_client_constructor_has_no_subprocess(self):
        with patch.object(lab.subprocess, "run") as run:
            client = lab.LocalClient()
        run.assert_not_called()
        self.assertRegex(client.database, r"^efl_mysql_[0-9a-f]{32}$")
        self.assertEqual(client.commands, 0)

    def test_context_inspection_is_read_only_and_pins_socket(self):
        client = client_ready()
        client.host = None
        with patch.object(lab.subprocess, "run", return_value=result(json.dumps(context()))) as run:
            client.connect()
        self.assertEqual(run.call_args.args[0], ["docker", "context", "inspect"])
        self.assertEqual(client.host, SOCKET)

    def test_context_failure_does_not_expose_stderr(self):
        client = client_ready()
        client.host = None
        with patch.object(lab.subprocess, "run", return_value=result(stderr="private credentials", returncode=1)):
            with self.assertRaisesRegex(lab.LabFailure, "^docker_context_inspection_failed$"):
                client.connect()

    def test_context_json_parse_failure_is_redacted(self):
        client = client_ready()
        client.host = None
        with patch.object(lab.subprocess, "run", return_value=result("private non-json")):
            with self.assertRaisesRegex(lab.LabFailure, "^invalid_docker_context_json$"):
                client.connect()

    def test_context_is_not_reinspected_after_pinning(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run") as run, self.assertRaisesRegex(lab.LabFailure, "context_already_inspected"):
            client.connect()
        run.assert_not_called()

    def test_command_is_fixed_compose_local_socket_without_host_password(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run", return_value=result(IDENTITY)) as run:
            client.execute("preflight")
        arguments = run.call_args.args[0]
        self.assertEqual(arguments[:6], ["docker", "--host", SOCKET, "compose", "--project-name", lab.PROJECT])
        self.assertEqual(arguments[6:10], ["--project-directory", str(lab.TRACK_DIRECTORY), "-f", str(lab.COMPOSE_FILE)])
        self.assertEqual(arguments[10:], ["exec", "-T", "mysql", "sh", "-c", lab.MYSQL_COMMAND])
        self.assertNotIn("local_mysql_root_not_for_production", " ".join(arguments))
        self.assertNotIn("--force", lab.MYSQL_COMMAND)
        self.assertIn("--no-defaults --no-login-paths", lab.MYSQL_COMMAND)
        self.assertIn("--skip-reconnect", lab.MYSQL_COMMAND)

    def test_sql_is_stdin_not_interpolated_shell_command(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run", return_value=result("fixture\t2\t4\n")) as run:
            client.execute("schema")
        self.assertIn(f"USE `{DATABASE}`;", run.call_args.kwargs["input"].decode())
        self.assertNotIn(DATABASE, " ".join(run.call_args.args[0]))
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_timeout_and_no_check_are_explicit(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run", return_value=result(IDENTITY)) as run:
            client.execute("preflight")
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertFalse(run.call_args.kwargs["check"])
        self.assertEqual(run.call_args.kwargs["cwd"], str(lab.TRACK_DIRECTORY))

    def test_timeout_reports_uncertain_server_state_without_partial_output(self):
        client = client_ready()
        error = subprocess.TimeoutExpired(["private"], 30, output=b"private partial SQL", stderr=b"private password")
        with patch.object(lab.subprocess, "run", side_effect=error):
            with self.assertRaisesRegex(lab.LabFailure, "^command_timeout_server_state_unknown$"):
                client.execute("preflight")

    def test_os_error_is_redacted(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run", side_effect=OSError("private path")):
            with self.assertRaisesRegex(lab.LabFailure, "^docker_command_failed$"):
                client.execute("preflight")

    def test_missing_docker_cli_stops_before_dispatch(self):
        client = client_ready()
        client.docker = None
        with patch.object(lab.subprocess, "run") as run, self.assertRaisesRegex(lab.LabFailure, "docker_cli_not_found"):
            client.execute("preflight")
        run.assert_not_called()

    def test_command_budget_stops_before_dispatch(self):
        client = client_ready()
        client.commands = lab.MAX_COMMANDS
        with patch.object(lab.subprocess, "run") as run, self.assertRaisesRegex(lab.LabFailure, "command_budget_exceeded"):
            client.execute("preflight")
        run.assert_not_called()

    def test_oversized_captured_output_is_not_accepted_or_printed(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run", return_value=result(b"x" * (lab.MAX_OUTPUT_BYTES + 1))):
            with self.assertRaisesRegex(lab.LabFailure, "output_too_large"):
                client.execute("preflight")

    def test_stdout_and_stderr_share_post_capture_size_budget(self):
        client = client_ready()
        half = lab.MAX_OUTPUT_BYTES // 2
        with patch.object(lab.subprocess, "run", return_value=result(b"x" * half, b"y" * (half + 1))):
            with self.assertRaisesRegex(lab.LabFailure, "output_too_large"):
                client.execute("preflight")

    def test_invalid_output_encoding_is_redacted(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run", return_value=result(b"\xff")):
            with self.assertRaisesRegex(lab.LabFailure, "invalid_output_encoding"):
                client.execute("preflight")

    def test_arbitrary_sql_stage_is_refused(self):
        client = client_ready()
        for stage in ("DROP DATABASE mysql", "../old", "cleanup", "sql", "restart"):
            with self.subTest(stage=stage), patch.object(lab.subprocess, "run") as run, self.assertRaisesRegex(lab.LabFailure, "sql_stage_refused"):
                client.execute(stage)
            run.assert_not_called()

    def test_unsafe_generated_namespace_is_refused(self):
        client = client_ready()
        for database in ("mysql", "efl_mysql_" + "a" * 32 + "\n", "a`; DROP DATABASE mysql; --"):
            client.database = database
            with self.subTest(database=database), patch.object(lab.subprocess, "run") as run, self.assertRaises(lab.LabFailure):
                client.execute("schema")
            run.assert_not_called()

    def test_context_guard_cannot_be_bypassed_before_execute(self):
        client = client_ready()
        client.host = "ssh://production"
        with patch.object(lab.subprocess, "run") as run, self.assertRaisesRegex(lab.LabFailure, "remote_docker_endpoint_refused"):
            client.execute("schema")
        run.assert_not_called()

    def test_no_context_stops_before_execute(self):
        client = client_ready()
        client.host = None
        with patch.object(lab.subprocess, "run") as run, self.assertRaisesRegex(lab.LabFailure, "docker_context_not_inspected"):
            client.execute("preflight")
        run.assert_not_called()

    def test_unverified_identity_cannot_write(self):
        client = client_ready(identity=False, created=False)
        with patch.object(lab.subprocess, "run") as run, self.assertRaisesRegex(lab.LabFailure, "server_identity_not_verified"):
            client.execute("create")
        run.assert_not_called()

    def test_unconfirmed_creation_cannot_write_fixtures(self):
        client = client_ready(created=False)
        with patch.object(lab.subprocess, "run") as run, self.assertRaisesRegex(lab.LabFailure, "database_creation_not_confirmed"):
            client.execute("schema")
        run.assert_not_called()

    def test_create_is_never_if_not_exists_or_retry(self):
        client = client_ready(created=False)
        with patch.object(lab.subprocess, "run", return_value=result("created\n")) as run:
            client.execute("create")
            with self.assertRaisesRegex(lab.LabFailure, "database_creation_already_attempted"):
                client.execute("create")
        self.assertEqual(run.call_count, 1)
        sql = run.call_args.kwargs["input"].decode()
        self.assertNotIn("IF NOT EXISTS", sql)
        self.assertIn(f"CREATE DATABASE `{DATABASE}`", sql)


class OracleTests(unittest.TestCase):
    def test_identity_is_exact_pinned_configuration(self):
        lab.verify_identity(IDENTITY)
        for before, after in (("8.4.11", "8.4.10"), ("efl-mysql-lab", "production"), ("8411", "1"),
                              ("InnoDB", "MyISAM"), ("ROW", "STATEMENT"), ("ON", "OFF")):
            with self.subTest(before=before), self.assertRaises(lab.LabFailure):
                lab.verify_identity(IDENTITY.replace(before, after))

    def test_identity_extra_row_is_rejected(self):
        with self.assertRaises(lab.LabFailure):
            lab.verify_identity(IDENTITY + IDENTITY)

    def test_mysql_tab_output_and_crlf_are_parsed(self):
        self.assertEqual(lab.parse_rows("a\tb\r\nc\td\r\n"), [["a", "b"], ["c", "d"]])

    def test_nul_output_is_rejected(self):
        with self.assertRaisesRegex(lab.LabFailure, "invalid_output"):
            lab.parse_rows("a\x00b\n")

    def test_all_expected_rows_are_literal_and_correct(self):
        self.assertEqual(lab.EXPECTED_ROWS["commit"], [["commit", "1:8750,2:6250", "15000"]])
        self.assertEqual(lab.EXPECTED_ROWS["semantics"][0:3], [
            ["counts", "4", "3", "2", "3100"], ["not_in_null", "0"], ["anti_join", "102,104"]])
        self.assertEqual(lab.EXPECTED_ROWS["rollback"][0], ["before_rollback", "1:8250,2:6750", "15000"])

    def test_wrong_balance_fails_even_when_total_is_correct(self):
        with self.assertRaisesRegex(lab.LabFailure, "row_oracle_failed"):
            lab.verify_rows("commit", "commit\t1:8000,2:7000\t15000\n")

    def test_missing_extra_or_reordered_rows_fail(self):
        good = rows_text("semantics").splitlines()
        for lines in (good[:-1], good + [good[0]], list(reversed(good))):
            with self.subTest(lines=lines), self.assertRaises(lab.LabFailure):
                lab.verify_rows("semantics", "\n".join(lines) + "\n")

    def test_wrong_final_fixture_fails_even_when_counts_match(self):
        wrong = rows_text("final").replace("102:1:300:<NULL>:x", "102:1:300:USD:x")
        with self.assertRaises(lab.LabFailure):
            lab.verify_rows("final", wrong)

    def test_explain_accepts_valid_alternative_access_paths(self):
        for access in ("ALL", "range", "ref", "const", "index"):
            with self.subTest(access=access):
                lab.verify_explain(json.dumps({"query_block": {"table": {"access_type": access}}}))

    def test_invalid_explain_json_and_shapes_fail(self):
        for value in ("not-json", "[]", "{}", '{"query_block": null}', '{"query_block": []}'):
            with self.subTest(value=value), self.assertRaises(lab.LabFailure):
                lab.verify_explain(value)

    def test_schema_uses_explicit_innodb_and_integrity_constraints(self):
        self.assertEqual(lab.SCHEMA_SQL.count("ENGINE=InnoDB"), 2)
        self.assertIn("balance_cents BIGINT NOT NULL", lab.SCHEMA_SQL)
        self.assertIn("CHECK (balance_cents >= 0)", lab.SCHEMA_SQL)
        self.assertIn("FOREIGN KEY (account_id) REFERENCES accounts(account_id)", lab.SCHEMA_SQL)
        self.assertIn("owner_code VARCHAR(16) NOT NULL UNIQUE", lab.SCHEMA_SQL)

    def test_transaction_boundaries_share_one_sql_invocation(self):
        self.assertTrue(lab.COMMIT_SQL.startswith("START TRANSACTION;"))
        self.assertIn("COMMIT;\nSELECT", lab.COMMIT_SQL)
        self.assertTrue(lab.ROLLBACK_SQL.startswith("START TRANSACTION;"))
        self.assertIn("ROLLBACK;\nSELECT", lab.ROLLBACK_SQL)
        self.assertEqual(lab.COMMIT_SQL.count("UPDATE accounts"), 2)
        self.assertEqual(lab.ROLLBACK_SQL.count("UPDATE accounts"), 2)

    def test_sql_never_drops_database_or_changes_global_settings(self):
        combined = "\n".join([lab.PREFLIGHT_SQL, lab.SESSION_SQL, *lab.STAGES.values()]).upper()
        for forbidden in ("DROP ", "TRUNCATE ", "SET GLOBAL", "SET PERSIST", "GRANT ", "CREATE USER", "SHUTDOWN"):
            self.assertNotIn(forbidden, combined)

    def test_expected_constraint_errors_are_observed_not_asserted_success(self):
        client = client_ready()
        for stage, (errno, sqlstate) in lab.NEGATIVE_ERRORS.items():
            with self.subTest(stage=stage), patch.object(lab.subprocess, "run", return_value=result(
                    stderr=f"ERROR {errno} ({sqlstate}) at line 8: expected fixture rejection\n", returncode=1)):
                self.assertEqual(client.execute(stage), "")

    def test_constraint_success_is_failure(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run", return_value=result()):
            with self.assertRaisesRegex(lab.LabFailure, "expected_constraint_rejection_missing"):
                client.execute("negative_check")

    def test_unrelated_error_is_not_mistaken_for_expected_constraint(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run", return_value=result(stderr="ERROR 1045 (28000): password detail\n", returncode=1)):
            with self.assertRaisesRegex(lab.LabFailure, "^wrong_constraint_error$"):
                client.execute("negative_fk")

    def test_wrong_sqlstate_is_failure_even_when_errno_matches(self):
        client = client_ready()
        with patch.object(lab.subprocess, "run", return_value=result(stderr="ERROR 3819 (23000): wrong state\n", returncode=1)):
            with self.assertRaisesRegex(lab.LabFailure, "wrong_constraint_error"):
                client.execute("negative_check")

    def test_multiple_errors_and_unexpected_stdout_are_refused(self):
        client = client_ready()
        for output in (result("unexpected\n", "ERROR 1062 (23000): duplicate\n", 1),
                       result(stderr="ERROR 1062 (23000): duplicate\nERROR 1062 (23000): second\n", returncode=1)):
            with self.subTest(output=output), patch.object(lab.subprocess, "run", return_value=output), self.assertRaises(lab.LabFailure):
                client.execute("negative_duplicate")


class WorkflowTests(unittest.TestCase):
    def test_full_mock_run_preserves_database_and_reports_boundaries(self):
        client = client_ready(identity=False, created=False)
        client.host = None
        with patch.object(lab.subprocess, "run", side_effect=successful_results()) as run:
            outcome = lab.run_lab(client)
        self.assertEqual(outcome["status"], "PASS")
        self.assertEqual(outcome["commands"], 12)
        self.assertEqual(client.stage, "complete")
        self.assertTrue(outcome["database_retained"])
        self.assertEqual(outcome["oracles"]["balances_cents"], [8750, 6250])
        self.assertIn("multi-session isolation or locking", outcome["not_verified"])
        self.assertEqual(run.call_count, 12)
        for call in run.call_args_list[1:]:
            self.assertEqual(call.args[0][1:3], ["--host", SOCKET])
            self.assertEqual(call.args[0][-1], lab.MYSQL_COMMAND)

    def test_remote_context_stops_before_any_mysql_command(self):
        client = client_ready(identity=False, created=False)
        client.host = None
        with patch.object(lab.subprocess, "run", return_value=result(json.dumps(context("ssh://production")))) as run:
            with self.assertRaisesRegex(lab.LabFailure, "remote_docker_endpoint_refused"):
                lab.run_lab(client)
        self.assertEqual(run.call_count, 1)
        self.assertFalse(client.database_creation_attempted)

    def test_wrong_server_stops_before_create_database(self):
        responses = successful_results()
        responses[1] = result(IDENTITY.replace("efl-mysql-lab", "production"))
        client = client_ready(identity=False, created=False)
        client.host = None
        with patch.object(lab.subprocess, "run", side_effect=responses) as run:
            with self.assertRaisesRegex(lab.LabFailure, "unexpected_server_identity_or_settings"):
                lab.run_lab(client)
        self.assertEqual(run.call_count, 2)
        self.assertFalse(client.database_creation_attempted)

    def test_collision_never_retries_or_overwrites(self):
        responses = successful_results()
        responses[2] = result(stderr="ERROR 1007 (HY000): database exists\n", returncode=1)
        client = client_ready(identity=False, created=False)
        client.host = None
        with patch.object(lab.subprocess, "run", side_effect=responses) as run:
            with self.assertRaisesRegex(lab.LabFailure, "mysql_statement_failed"):
                lab.run_lab(client)
        self.assertEqual(run.call_count, 3)
        self.assertTrue(client.database_creation_attempted)
        self.assertFalse(client.database_created)

    def test_incomplete_create_confirmation_stops_before_fixture(self):
        responses = successful_results()
        responses[2] = result("")
        client = client_ready(identity=False, created=False)
        client.host = None
        with patch.object(lab.subprocess, "run", side_effect=responses) as run:
            with self.assertRaisesRegex(lab.LabFailure, "row_oracle_failed"):
                lab.run_lab(client)
        self.assertEqual(run.call_count, 3)
        self.assertFalse(client.database_created)

    def test_bad_final_rows_never_report_pass(self):
        responses = successful_results()
        responses[-1] = result(rows_text("final").replace("8750", "0"))
        client = client_ready(identity=False, created=False)
        client.host = None
        with patch.object(lab.subprocess, "run", side_effect=responses):
            with self.assertRaisesRegex(lab.LabFailure, "row_oracle_failed"):
                lab.run_lab(client)
        self.assertEqual(client.stage, "final")

    def test_help_never_constructs_client_or_starts_subprocess(self):
        with patch.object(lab, "LocalClient") as constructor, patch.object(lab.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                lab.main(["--help"])
        self.assertEqual(error.exception.code, 0)
        constructor.assert_not_called()
        run.assert_not_called()

    def test_missing_opt_in_starts_nothing(self):
        with patch.object(lab, "LocalClient") as constructor, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                lab.main([])
        self.assertEqual(error.exception.code, 2)
        constructor.assert_not_called()

    def test_arbitrary_host_database_and_sql_cli_are_not_supported(self):
        for option in ("--host", "--database", "--sql", "--context", "--password"):
            with self.subTest(option=option), patch.object(lab, "LocalClient") as constructor, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    lab.main(["--run-local", option, "private"])
            constructor.assert_not_called()

    def test_main_failure_redacts_stderr_sql_and_host_environment(self):
        client = client_ready(identity=False, created=False)
        client.host = None
        output = io.StringIO()
        with patch.object(lab, "LocalClient", return_value=client), patch.object(lab.subprocess, "run", return_value=result(
                stderr="private password and sql", returncode=1)), contextlib.redirect_stdout(output):
            self.assertEqual(lab.main(["--run-local"]), 1)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "ERROR")
        self.assertEqual(payload["stage"], "docker_context")
        self.assertEqual(payload["database"], DATABASE)
        self.assertFalse(payload["cleanup_performed"])
        self.assertNotIn("private", output.getvalue())

    def test_main_mock_success_reports_completed_oracles_only(self):
        client = client_ready(identity=False, created=False)
        client.host = None
        output = io.StringIO()
        with patch.object(lab, "LocalClient", return_value=client), patch.object(lab.subprocess, "run", side_effect=successful_results()), contextlib.redirect_stdout(output):
            self.assertEqual(lab.main(["--run-local"]), 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["oracles"]["constraint_errors"], [1062, 1452, 3819])
        self.assertTrue(payload["oracles"]["rollback_restored_rows"])


if __name__ == "__main__":
    unittest.main()
