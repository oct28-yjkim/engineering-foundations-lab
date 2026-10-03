"""Static/mock contracts only. A passing suite does NOT mean Spark executed.

Small fixture-writing tests use Python TemporaryDirectory, restricted to files
created by these tests. No dependency, cloud connection or existing run is used.
"""
import ast
import contextlib
import importlib.metadata
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import spark_runner as runner


def test_directory():
    root = runner.DEFAULT_WORK_ROOT.parent / "spark-contract-tests"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="test-", dir=root)


class RunnerContractTests(unittest.TestCase):
    def test_help_without_pyspark(self):
        with patch.object(runner, "prerequisites", side_effect=AssertionError("must not inspect runtime")):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
                runner.main(["--help"])
        self.assertEqual(caught.exception.code, 0)

    def test_missing_dependency_is_error_without_writes(self):
        with patch.object(runner.importlib.metadata, "version", side_effect=importlib.metadata.PackageNotFoundError):
            with patch.object(runner, "create_run_directory") as create, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(["--lab", "batch"]), 1)
                create.assert_not_called()

    def test_wrong_pyspark_version_rejected(self):
        with patch.object(runner.importlib.metadata, "version", return_value="3.5.0"):
            with self.assertRaisesRegex(RuntimeError, "4.0.4"):
                runner.prerequisites()

    def test_java_17_and_21_parsed(self):
        self.assertEqual(runner.java_major('openjdk version "17.0.12" 2024-07-16'), 17)
        self.assertEqual(runner.java_major('java version "21.0.4" 2024-07-16'), 21)
        self.assertEqual(runner.java_major('openjdk 21.0.4 2024-07-16'), 21)

    def test_invalid_java_output(self):
        with self.assertRaises(RuntimeError):
            runner.java_major("java unavailable")

    def test_timeout_invalid_before_prerequisites(self):
        for seconds in [0, 4, 301]:
            with self.subTest(seconds=seconds), patch.object(runner, "prerequisites") as check:
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(runner.main(["--timeout-seconds", str(seconds)]), 1)
                check.assert_not_called()

    def test_default_root_is_repository_lab_workspace(self):
        self.assertEqual(runner.DEFAULT_WORK_ROOT.parts[-2:], ("lab-workspaces", "spark"))

    def test_refuse_filesystem_root(self):
        with self.assertRaises(RuntimeError):
            runner.validate_work_root(Path.cwd().anchor)

    def test_refuse_home(self):
        with self.assertRaises(RuntimeError):
            runner.validate_work_root(Path.home())

    def test_refuse_repository_root(self):
        with self.assertRaises(RuntimeError):
            runner.validate_work_root(Path(runner.__file__).resolve().parents[3])

    def test_reparse_point_rejected_without_isjunction_api(self):
        metadata = SimpleNamespace(st_mode=0o040755, st_file_attributes=0x400)
        with patch.object(Path, "lstat", return_value=metadata), \
                patch.object(runner.os.path, "isjunction", None, create=True):
            with self.assertRaisesRegex(RuntimeError, "reparse point"):
                runner.validate_work_root(runner.DEFAULT_WORK_ROOT / "synthetic-junction")

    def test_missing_suffix_still_checks_reparse_ancestor(self):
        candidate = runner.DEFAULT_WORK_ROOT / "synthetic-junction" / "new-child"
        def inspect(component):
            if component == candidate:
                raise FileNotFoundError(str(component))
            return SimpleNamespace(st_mode=0o040755, st_file_attributes=0x400)
        with patch.object(Path, "lstat", autospec=True, side_effect=inspect):
            with self.assertRaisesRegex(RuntimeError, "reparse point"):
                runner.validate_work_root(candidate)

    def test_missing_output_suffix_allowed(self):
        candidate = runner.DEFAULT_WORK_ROOT / "contract-not-created" / "child"
        original_lstat = Path.lstat
        def inspect(component):
            if component in (candidate, candidate.parent):
                raise FileNotFoundError(str(component))
            return original_lstat(component)
        with patch.object(Path, "lstat", autospec=True, side_effect=inspect):
            self.assertEqual(runner.validate_work_root(candidate), candidate.resolve())

    def test_unreadable_component_rejected(self):
        with patch.object(Path, "lstat", side_effect=PermissionError("synthetic ACL denial")):
            with self.assertRaisesRegex(RuntimeError, "Cannot inspect"):
                runner.validate_work_root(runner.DEFAULT_WORK_ROOT / "unreadable")

    def test_posix_symlink_mode_rejected_without_windows_attributes(self):
        with patch.object(Path, "lstat", return_value=SimpleNamespace(st_mode=0o120777)):
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                runner.validate_work_root(runner.DEFAULT_WORK_ROOT / "synthetic-link")

    def test_fresh_directories_preserve_existing(self):
        with test_directory() as temporary:
            root = Path(temporary)
            existing = root / "existing.txt"
            existing.write_text("keep", encoding="utf-8")
            first, second = runner.create_run_directory(root), runner.create_run_directory(root)
            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, root.resolve())
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")

    def test_refuse_file_as_root(self):
        with test_directory() as temporary:
            target = Path(temporary) / "not-a-directory"
            target.write_text("keep", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                runner.validate_work_root(target)

    def test_json_writer_never_overwrites(self):
        with test_directory() as temporary:
            target = Path(temporary) / "manifest.json"
            runner.write_json_new(target, {"first": True})
            with self.assertRaises(FileExistsError):
                runner.write_json_new(target, {"second": True})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"first": True})

    def test_input_writer_exact_schema_and_exclusive_create(self):
        with test_directory() as temporary:
            root = Path(temporary)
            runner.write_input_file(root, 1, runner.STREAM_PHASES[0])
            actual = [json.loads(line) for line in (root / "batch-01.json").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["row_id"] for row in actual], [1, 2, 3])
            self.assertIsNone(actual[1]["amount"])
            with self.assertRaises(FileExistsError):
                runner.write_input_file(root, 1, [])

    def test_python_oracle_matches_fixture_independently(self):
        result = {}
        for _, key, amount in runner.BATCH_ROWS:
            rows, nonnull, total = result.get(key, (0, 0, 0))
            result[key] = rows + 1, nonnull + (amount is not None), total + (amount or 0)
        self.assertEqual(result, runner.EXPECTED_GROUPS)

    def test_nullsafe_join_fixture(self):
        self.assertEqual([row[0] for row in runner.BATCH_ROWS if row[1] is not None], runner.EXPECTED_ORDINARY_JOIN_IDS)
        self.assertEqual([row[0] for row in runner.BATCH_ROWS], runner.EXPECTED_NULL_SAFE_JOIN_IDS)

    def test_stream_phases_exactly_cover_oracle(self):
        self.assertEqual([row for phase in runner.STREAM_PHASES for row in phase], runner.BATCH_ROWS)

    def test_module_imports_no_pyspark_at_top_level(self):
        tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
        imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        for node in imports:
            module = getattr(node, "module", "") or ""
            names = [alias.name for alias in node.names]
            self.assertFalse(module.startswith("pyspark") or any(name.startswith("pyspark") for name in names))

    def test_only_local_master_literal(self):
        source = Path(runner.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        masters = [node.args[0].value for node in ast.walk(tree)
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == "master" and node.args and isinstance(node.args[0], ast.Constant)]
        self.assertEqual(masters, ["local[2]"])
        self.assertNotIn("dbutils", source)

    def test_remote_environment_refused_before_import(self):
        with patch.dict(runner.os.environ, {"SPARK_REMOTE": "sc://example.invalid"}):
            with self.assertRaisesRegex(RuntimeError, "SPARK_REMOTE"):
                runner.prerequisites()

    def test_custom_package_submission_refused(self):
        clean = {"SPARK_REMOTE": "", "SPARK_CONNECT_MODE_ENABLED": "", "SPARK_HOME": "",
                 "PYSPARK_SUBMIT_ARGS": "--packages forbidden:package:1 pyspark-shell"}
        with patch.dict(runner.os.environ, clean):
            with self.assertRaisesRegex(RuntimeError, "PYSPARK_SUBMIT_ARGS"):
                runner.prerequisites()

    def test_inherited_gateway_refused(self):
        for name in ("PYSPARK_GATEWAY_PORT", "PYSPARK_GATEWAY_SECRET"):
            with self.subTest(name=name), patch.dict(runner.os.environ, {name: "synthetic-value"}):
                with self.assertRaisesRegex(RuntimeError, name):
                    runner.prerequisites()

    def test_streaming_timeout_stops_only_own_query(self):
        spark, builder, query = MagicMock(), MagicMock(), MagicMock()
        source = spark.readStream.schema.return_value.json.return_value
        source.select.return_value.writeStream = builder
        for name in ("format", "outputMode", "option", "trigger"):
            getattr(builder, name).return_value = builder
        builder.start.return_value = query
        query.awaitTermination.return_value = False
        query.isActive = True
        with test_directory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "exceeded 7s"):
                runner.streaming_experiment(spark, Path(temporary), 7)
        query.awaitTermination.assert_called_once_with(7)
        query.stop.assert_called_once_with()
        spark.read.parquet.assert_not_called()

    def test_streaming_mock_oracle_and_checkpoint_identity(self):
        spark, builder = MagicMock(), MagicMock()
        source = spark.readStream.schema.return_value.json.return_value
        source.select.return_value.writeStream = builder
        for name in ("format", "outputMode", "option", "trigger"):
            getattr(builder, name).return_value = builder
        queries = []
        for phase in (1, 2):
            query = MagicMock()
            query.awaitTermination.return_value = True
            query.exception.return_value = None
            query.isActive, query.id, query.runId = False, "same-query", f"run-{phase}"
            queries.append(query)
        builder.start.side_effect = queries
        rows = [SimpleNamespace(row_id=r[0], key=r[1], amount=r[2]) for r in runner.BATCH_ROWS]
        spark.read.parquet.return_value.collect.side_effect = [rows[:3], rows]
        with test_directory() as temporary:
            result = runner.streaming_experiment(spark, Path(temporary), 7)
        self.assertEqual(result["phases"][1]["sink_row_ids"], [1, 2, 3, 4, 5, 6])
        checkpoints = [call.args[1] for call in builder.option.call_args_list
                       if call.args[0] == "checkpointLocation"]
        self.assertEqual(len(checkpoints), 2)
        self.assertEqual(checkpoints[0], checkpoints[1])

    def test_environment_restored_even_if_spark_cleanup_fails(self):
        spark, session, builder = MagicMock(), MagicMock(), MagicMock()
        session.builder = builder
        builder.master.return_value = builder
        builder.appName.return_value = builder
        builder.config.return_value = builder
        builder.getOrCreate.return_value = spark
        spark.version = "incorrect-runtime"
        spark.stop.side_effect = RuntimeError("synthetic cleanup failure")
        old_tempdir = runner.tempfile.tempdir
        with test_directory() as temporary:
            run = Path(temporary) / "run"
            run.mkdir()
            with patch.object(runner, "prerequisites", return_value={}), \
                    patch.object(runner, "create_run_directory", return_value=run), \
                    patch.dict("sys.modules", {"pyspark": MagicMock(),
                                             "pyspark.sql": SimpleNamespace(SparkSession=session)}), \
                    patch.dict(runner.os.environ, {"SPARK_LOCAL_IP": "before-test"}), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(["--lab", "batch"]), 1)
                self.assertEqual(runner.os.environ["SPARK_LOCAL_IP"], "before-test")
                self.assertEqual(runner.tempfile.tempdir, old_tempdir)


if __name__ == "__main__":
    unittest.main()
