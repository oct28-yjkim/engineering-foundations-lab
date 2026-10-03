"""Optional Apache Spark 4.0.4 local[2] experiment; no cloud/Databricks connection.

Requires Python 3.10+, PySpark == 4.0.4, Java 17 or 21 already installed.
No install/download is performed. --help works without PySpark or Java.
Controlled outputs are created in a fresh run directory; nothing is deleted.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


EXPECTED_SPARK = "4.0.4"
DEFAULT_WORK_ROOT = Path(__file__).resolve().parents[3] / "lab-workspaces" / "spark"
BATCH_ROWS = [(1, "a", 10), (2, "a", None), (3, "b", 5),
              (4, None, 7), (5, "a", 10), (6, None, None)]
EXPECTED_GROUPS = {"a": (3, 2, 20), "b": (1, 1, 5), None: (2, 1, 7)}
EXPECTED_ORDINARY_JOIN_IDS = [1, 2, 3, 5]
EXPECTED_NULL_SAFE_JOIN_IDS = [1, 2, 3, 4, 5, 6]
STREAM_PHASES = [BATCH_ROWS[:3], BATCH_ROWS[3:]]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def java_major(version_output: str) -> int:
    match = re.search(r'(?:openjdk|java)\s+version\s+"(?P<major>\d+)', version_output)
    if not match:
        # Some OpenJDK distributions print `openjdk 21.0.2 ...` without "version".
        match = re.search(r'\bopenjdk\s+(?P<major>\d+)(?:\.|\s)', version_output)
    check(match is not None, "Cannot parse Java version; expected Java 17 or 21")
    return int(match.group("major"))


def prerequisites() -> dict:
    check(sys.version_info >= (3, 10), "Python 3.10+ is required")
    for name in ("SPARK_REMOTE", "SPARK_CONNECT_MODE_ENABLED", "SPARK_HOME",
                 "PYSPARK_GATEWAY_PORT", "PYSPARK_GATEWAY_SECRET"):
        check(not os.environ.get(name), f"Use a clean local environment without {name}")
    check(os.environ.get("PYSPARK_SUBMIT_ARGS", "pyspark-shell") == "pyspark-shell",
          "Remove custom PYSPARK_SUBMIT_ARGS; this lab must not fetch packages or contact a cluster")
    try:
        installed = importlib.metadata.version("pyspark")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("PySpark is not installed. Follow labs/README.md; nothing was run.") from exc
    check(installed == EXPECTED_SPARK, f"Expected pyspark=={EXPECTED_SPARK}; found {installed}")
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")) if java_home else shutil.which("java")
    check(bool(java) and Path(java).is_file(), "Java not found. Set a valid JAVA_HOME or PATH for Java 17/21.")
    try:
        result = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Unable to inspect Java; no Spark experiment started") from exc
    check(result.returncode == 0, "java -version failed")
    major = java_major(result.stdout + result.stderr)
    check(major in (17, 21), f"Expected Java 17 or 21; found major {major}")
    # Do not expose full environment paths or other configuration in the manifest.
    return {"python": sys.version.split()[0], "pyspark": installed, "java_major": major}


def validate_work_root(value: str | Path) -> Path:
    import stat

    candidate = Path(value).expanduser().absolute()
    for component in [candidate, *candidate.parents]:
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            # The fresh output suffix may not exist; existing ancestors still must be checked.
            continue
        except OSError as exc:
            raise RuntimeError(f"Cannot inspect work-root component: {component}") from exc
        # st_file_attributes is available on Windows before os.path.isjunction (3.12).
        # Reject every existing reparse point, including directory junctions, without following it.
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        check(not stat.S_ISLNK(metadata.st_mode) and not (attributes & reparse_flag),
              f"Work root must not traverse a symlink/junction/reparse point: {component}")
    resolved = candidate.resolve()
    forbidden = {Path(resolved.anchor), Path.home().resolve(), Path(__file__).resolve().parents[3]}
    check(resolved not in forbidden, "Use a dedicated lab directory, not a filesystem/home/repository root")
    check(not resolved.exists() or resolved.is_dir(), "Work root is not a directory")
    return resolved


def create_run_directory(work_root: str | Path) -> Path:
    root = validate_work_root(work_root)
    root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=root)).resolve()
    check(run.parent == root and run.is_dir(), "Fresh run escaped the work root")
    return run


def write_json_new(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def batch_experiment(spark, explain: bool = False) -> dict:
    from pyspark.sql import functions as F
    frame = spark.createDataFrame(BATCH_ROWS, "row_id long, key string, amount long")
    groups = frame.groupBy("key").agg(F.count("*").alias("rows"),
               F.count("amount").alias("nonnull"), F.sum("amount").alias("total"))
    # The fixture is six rows, the group oracle is three keys; never collect user data.
    actual = {row["key"]: (row["rows"], row["nonnull"], row["total"]) for row in groups.collect()}
    check(actual == EXPECTED_GROUPS, f"Group/null/duplicate oracle mismatch: {actual}")
    dimension = spark.createDataFrame([("a", "A"), ("b", "B"), (None, "UNKNOWN")],
                                     "dim_key string, label string")
    ordinary = frame.join(dimension, frame.key == dimension.dim_key, "inner")
    null_safe = frame.join(dimension, frame.key.eqNullSafe(dimension.dim_key), "inner")
    ordinary_ids = sorted(row.row_id for row in ordinary.select("row_id").collect())
    null_safe_ids = sorted(row.row_id for row in null_safe.select("row_id").collect())
    check(ordinary_ids == EXPECTED_ORDINARY_JOIN_IDS, "Ordinary equality join oracle mismatch")
    check(null_safe_ids == EXPECTED_NULL_SAFE_JOIN_IDS, "Null-safe equality join oracle mismatch")
    if explain:
        groups.explain(mode="formatted")
    return {"status": "PASS", "scope": "actual local Spark batch on six synthetic rows",
            "group_oracle_keys": 3, "ordinary_join_ids": ordinary_ids,
            "null_safe_join_ids": null_safe_ids, "aqe_enabled": spark.conf.get("spark.sql.adaptive.enabled"),
            "performance_claim": False}


def write_input_file(input_dir: Path, phase: int, rows: list[tuple]) -> None:
    # The query is stopped while each file is written; Spark never sees a half-written fixture.
    path = input_dir / f"batch-{phase:02d}.json"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row_id, key, amount in rows:
            handle.write(json.dumps({"row_id": row_id, "key": key, "amount": amount}) + "\n")


def streaming_experiment(spark, run: Path, timeout_seconds: int) -> dict:
    input_dir, checkpoint, sink = run / "input", run / "checkpoint", run / "sink"
    input_dir.mkdir()
    phase_results = []
    for phase, rows in enumerate(STREAM_PHASES, start=1):
        write_input_file(input_dir, phase, rows)
        source = spark.readStream.schema("row_id long, key string, amount long").json(str(input_dir))
        query = None
        try:
            query = (source.select("row_id", "key", "amount").writeStream.format("parquet")
                     .outputMode("append").option("path", str(sink))
                     .option("checkpointLocation", str(checkpoint))
                     .trigger(availableNow=True).start())
            check(query.awaitTermination(timeout_seconds),
                  f"Streaming phase {phase} exceeded {timeout_seconds}s; results are incomplete, not PASS")
            check(query.exception() is None, f"Streaming phase {phase} failed")
            actual = sorted((row.row_id, row.key, row.amount) for row in spark.read.parquet(str(sink)).collect())
            expected = sorted(row for part in STREAM_PHASES[:phase] for row in part)
            check(actual == expected, f"Streaming phase {phase} sink differs from the exact row oracle")
            phase_results.append({"phase": phase, "sink_row_ids": [row[0] for row in actual],
                                  "query_id": str(query.id), "run_id": str(query.runId)})
        finally:
            if query is not None and query.isActive:
                query.stop()
    check(phase_results[0]["query_id"] == phase_results[1]["query_id"], "Checkpoint identity changed on restart")
    check(phase_results[0]["run_id"] != phase_results[1]["run_id"], "Expected a new query run after restart")
    return {"status": "PASS", "scope": "local file source + parquet sink, normal stop/restart, same checkpoint",
            "phases": phase_results, "proves": "exact six-row result across this normal restart",
            "does_not_prove": ["crash recovery", "Kafka offsets", "Delta transactions",
                               "external side-effect exactly once", "cloud/Databricks behavior"]}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--lab", choices=["batch", "streaming", "all"], default="all")
    result.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT,
                        help="Dedicated parent for a NEW run-* directory; existing runs are not reused/deleted")
    result.add_argument("--timeout-seconds", type=int, default=120,
                        help="Per streaming query wait, 5..300 seconds (default: 120)")
    result.add_argument("--explain", action="store_true", help="Print the tiny batch aggregate physical plan")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    spark, run, previous_tempdir = None, None, tempfile.tempdir
    changed_environment: dict[str, str | None] = {}
    try:
        check(5 <= args.timeout_seconds <= 300, "timeout-seconds must be between 5 and 300")
        versions = prerequisites()
        run = create_run_directory(args.work_root)
        for dirname in ("tmp", "scratch", "warehouse", "conf"):
            (run / dirname).mkdir()
        for name, value in {"TMPDIR": str(run / "tmp"), "TMP": str(run / "tmp"),
                            "TEMP": str(run / "tmp"), "SPARK_LOCAL_DIRS": str(run / "scratch"),
                            "SPARK_CONF_DIR": str(run / "conf"),
                            "PYSPARK_PYTHON": sys.executable, "SPARK_LOCAL_IP": "127.0.0.1"}.items():
            changed_environment[name] = os.environ.get(name)
            os.environ[name] = value
        tempfile.tempdir = str(run / "tmp")
        from pyspark.sql import SparkSession
        spark = (SparkSession.builder.master("local[2]").appName("engineering-foundations-spark-lab")
                 .config("spark.ui.enabled", "false").config("spark.driver.bindAddress", "127.0.0.1")
                 .config("spark.driver.host", "127.0.0.1").config("spark.sql.shuffle.partitions", "4")
                 .config("spark.sql.adaptive.enabled", "true")
                 .config("spark.sql.streaming.stopTimeout", "30000")
                 .config("spark.sql.warehouse.dir", (run / "warehouse").as_uri())
                 .config("spark.driver.extraJavaOptions", f'-Djava.io.tmpdir="{(run / "tmp").as_posix()}"')
                 .getOrCreate())
        check(spark.version == EXPECTED_SPARK, f"Spark runtime mismatch: {spark.version}")
        check(spark.sparkContext.master == "local[2]", "Refusing a non-local Spark context")
        spark.sparkContext.setLogLevel("WARN")
        manifest = {"versions": versions, "spark": spark.version,
                    "application_id": spark.sparkContext.applicationId,
                    "run_directory": str(run), "synthetic_only": True, "labs": {}}
        if args.lab in ("batch", "all"):
            manifest["labs"]["batch"] = batch_experiment(spark, args.explain)
        if args.lab in ("streaming", "all"):
            manifest["labs"]["streaming"] = streaming_experiment(spark, run, args.timeout_seconds)
        stopping, spark = spark, None
        stopping.stop()
        manifest["status"] = "PASS"
        write_json_new(run / "manifest.json", manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        error = {"status": "ERROR", "message": str(exc), "run_directory": str(run) if run else None,
                 "note": "No passing result is claimed. Any partial run is retained; nothing is deleted."}
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        try:
            if spark is not None:
                spark.stop()
        except Exception as exc:
            print(json.dumps({"status": "CLEANUP_ERROR", "message": str(exc),
                              "note": "Inspect only the local process started by this run."}), file=sys.stderr)
        finally:
            tempfile.tempdir = previous_tempdir
            for name, previous in changed_environment.items():
                if previous is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = previous


if __name__ == "__main__":
    raise SystemExit(main())
