"""Opt-in MySQL 8.4.11 local-engine lab; Python 3.10+ standard library.

Uses the checked-in Compose service through a verified local Docker socket.
Creates and retains one fresh database. Never starts Docker, changes context,
connects to a TCP/SSH Docker endpoint, or drops an existing object.
Tests with mocked subprocesses validate this client, not MySQL itself.
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


VERSION = "8.4.11"
HOSTNAME = "efl-mysql-lab"
PROJECT = "engineering-foundations-mysql-lab"
SERVER_ID = "8411"
TRACK_DIRECTORY = Path(__file__).resolve().parents[1]
COMPOSE_FILE = TRACK_DIRECTORY / "compose.yaml"
DATABASE_PATTERN = re.compile(r"efl_mysql_[0-9a-f]{32}\Z")
TIMEOUT_SECONDS = 30
MAX_COMMANDS = 16
MAX_OUTPUT_BYTES = 1024 * 1024
LOCAL_PIPES = frozenset({"npipe:////./pipe/docker_engine", "npipe:////./pipe/dockerDesktopLinuxEngine"})

# This is fixed source, not an interpolated shell command. SQL arrives only on
# stdin. The public dummy password stays inside the local container environment.
MYSQL_COMMAND = (
    ': "${MYSQL_ROOT_PASSWORD:?local lab password missing}"; '
    'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; '
    'exec mysql --no-defaults --no-login-paths --protocol=socket '
    '--socket=/var/run/mysqld/mysqld.sock --user=root --batch --raw '
    '--skip-column-names --skip-reconnect --connect-timeout=5 '
    '--local-infile=0 --skip-system-command --commands=OFF'
)

SESSION_SQL = """SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY';
SET SESSION autocommit = 1;
SET SESSION foreign_key_checks = 1;
SET SESSION max_execution_time = 5000;
SET SESSION innodb_lock_wait_timeout = 5;
SET SESSION lock_wait_timeout = 5;
"""

PREFLIGHT_SQL = """SELECT VERSION(), @@hostname, @@server_id, @@default_storage_engine,
@@global.innodb_flush_log_at_trx_commit, @@global.sync_binlog,
@@global.binlog_format, @@global.gtid_mode, @@global.enforce_gtid_consistency;
"""

SCHEMA_SQL = """CREATE TABLE accounts (
  account_id INT NOT NULL PRIMARY KEY,
  owner_code VARCHAR(16) NOT NULL UNIQUE,
  balance_cents BIGINT NOT NULL,
  CONSTRAINT ck_accounts_nonnegative CHECK (balance_cents >= 0),
  INDEX idx_owner_balance (owner_code, balance_cents)
) ENGINE=InnoDB;
CREATE TABLE orders (
  order_id INT NOT NULL PRIMARY KEY,
  account_id INT NOT NULL,
  amount_cents INT NOT NULL,
  currency CHAR(3) NULL,
  tag VARCHAR(16) NULL,
  CONSTRAINT fk_orders_account FOREIGN KEY (account_id) REFERENCES accounts(account_id),
  CONSTRAINT ck_orders_positive CHECK (amount_cents > 0)
) ENGINE=InnoDB;
INSERT INTO accounts VALUES (1, 'alpha', 10000), (2, 'beta', 5000);
INSERT INTO orders VALUES
  (101, 1, 1200, 'USD', 'x'), (102, 1, 300, NULL, 'x'),
  (103, 2, 700, 'USD', NULL), (104, 2, 900, 'EUR', 'y');
SELECT 'fixture', (SELECT COUNT(*) FROM accounts), (SELECT COUNT(*) FROM orders);
"""

SEMANTICS_SQL = """SELECT 'counts', COUNT(*), COUNT(currency), COUNT(DISTINCT currency), SUM(amount_cents) FROM orders;
SELECT 'not_in_null', COUNT(*) FROM orders WHERE currency NOT IN ('USD', NULL);
SELECT 'anti_join', GROUP_CONCAT(order_id ORDER BY order_id) FROM orders AS o
WHERE NOT EXISTS (
  SELECT 1 FROM (SELECT 'USD' AS code UNION ALL SELECT NULL) AS blocked
  WHERE blocked.code = o.currency
);
SELECT 'groups', COALESCE(tag, '<NULL>'), COUNT(*) FROM orders GROUP BY tag ORDER BY tag;
SELECT 'join', a.owner_code, SUM(o.amount_cents) FROM accounts AS a
JOIN orders AS o ON o.account_id = a.account_id GROUP BY a.owner_code ORDER BY a.owner_code;
SELECT 'index', GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'accounts' AND INDEX_NAME = 'idx_owner_balance';
SELECT 'covering_result', account_id, balance_cents FROM accounts
WHERE owner_code = 'alpha' AND balance_cents >= 0 ORDER BY balance_cents, account_id;
"""

EXPLAIN_SQL = """EXPLAIN FORMAT=JSON SELECT account_id, balance_cents FROM accounts
WHERE owner_code = 'alpha' AND balance_cents >= 0 ORDER BY balance_cents, account_id;
"""

COMMIT_SQL = """START TRANSACTION;
UPDATE accounts SET balance_cents = balance_cents - 1250 WHERE account_id = 1;
UPDATE accounts SET balance_cents = balance_cents + 1250 WHERE account_id = 2;
COMMIT;
SELECT 'commit', GROUP_CONCAT(CONCAT(account_id, ':', balance_cents) ORDER BY account_id), SUM(balance_cents) FROM accounts;
"""

ROLLBACK_SQL = """START TRANSACTION;
UPDATE accounts SET balance_cents = balance_cents - 500 WHERE account_id = 1;
UPDATE accounts SET balance_cents = balance_cents + 500 WHERE account_id = 2;
SELECT 'before_rollback', GROUP_CONCAT(CONCAT(account_id, ':', balance_cents) ORDER BY account_id), SUM(balance_cents) FROM accounts;
ROLLBACK;
SELECT 'after_rollback', GROUP_CONCAT(CONCAT(account_id, ':', balance_cents) ORDER BY account_id), SUM(balance_cents) FROM accounts;
"""

FINAL_SQL = """SELECT 'accounts', GROUP_CONCAT(CONCAT(account_id, ':', owner_code, ':', balance_cents) ORDER BY account_id), COUNT(*), SUM(balance_cents) FROM accounts;
SELECT 'orders', GROUP_CONCAT(CONCAT(order_id, ':', account_id, ':', amount_cents, ':', COALESCE(currency, '<NULL>'), ':', COALESCE(tag, '<NULL>')) ORDER BY order_id SEPARATOR ','), COUNT(*) FROM orders;
SELECT 'engines', GROUP_CONCAT(CONCAT(TABLE_NAME, ':', ENGINE) ORDER BY TABLE_NAME)
FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE();
"""

STAGES = {
    "schema": SCHEMA_SQL,
    "semantics": SEMANTICS_SQL,
    "explain": EXPLAIN_SQL,
    "commit": COMMIT_SQL,
    "rollback": ROLLBACK_SQL,
    "negative_duplicate": "INSERT INTO accounts VALUES (1, 'gamma', 1);\n",
    "negative_fk": "INSERT INTO orders VALUES (999, 99, 1, 'USD', 'invalid');\n",
    "negative_check": "INSERT INTO accounts VALUES (3, 'gamma', -1);\n",
    "final": FINAL_SQL,
}
NEGATIVE_ERRORS = {
    "negative_duplicate": (1062, "23000"),
    "negative_fk": (1452, "23000"),
    "negative_check": (3819, "HY000"),
}
EXPECTED_ROWS = {
    "create": [["created"]],
    "schema": [["fixture", "2", "4"]],
    "semantics": [
        ["counts", "4", "3", "2", "3100"],
        ["not_in_null", "0"],
        ["anti_join", "102,104"],
        ["groups", "<NULL>", "1"], ["groups", "x", "2"], ["groups", "y", "1"],
        ["join", "alpha", "1500"], ["join", "beta", "1600"],
        ["index", "owner_code,balance_cents"], ["covering_result", "1", "10000"],
    ],
    "commit": [["commit", "1:8750,2:6250", "15000"]],
    "rollback": [["before_rollback", "1:8250,2:6750", "15000"],
                 ["after_rollback", "1:8750,2:6250", "15000"]],
    "final": [["accounts", "1:alpha:8750,2:beta:6250", "2", "15000"],
              ["orders", "101:1:1200:USD:x,102:1:300:<NULL>:x,103:2:700:USD:<NULL>,104:2:900:EUR:y", "4"],
              ["engines", "accounts:InnoDB,orders:InnoDB"]],
}


class LabFailure(Exception):
    """Only fixed error codes; subprocess stderr and SQL are never printed."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise LabFailure(code)


def local_docker_host(contexts: Any) -> str:
    """Local transport guard, not authentication of a privileged local daemon."""
    require(isinstance(contexts, list) and len(contexts) == 1, "invalid_docker_context")
    context = contexts[0]
    require(isinstance(context, dict), "invalid_docker_context")
    endpoints = context.get("Endpoints")
    require(isinstance(endpoints, dict) and isinstance(endpoints.get("docker"), dict), "invalid_docker_context")
    host = endpoints["docker"].get("Host")
    require(isinstance(host, str), "invalid_docker_context")
    local_unix = re.fullmatch(r"unix:///[^\x00-\x20\\?#]+", host) is not None
    require(local_unix or host in LOCAL_PIPES, "remote_docker_endpoint_refused")
    return host


def safe_environment(source: dict[str, str]) -> dict[str, str]:
    # Ignore environment-selected endpoints/config directories. Inspection uses
    # the context saved in the DEFAULT Docker configuration, not necessarily the
    # shell's effective context. Pin its endpoint with --host later. Do not mutate
    # os.environ or saved context. Disable Compose .env loading as an extra guard.
    result = {key: value for key, value in source.items()
              if not key.upper().startswith(("DOCKER_", "COMPOSE_", "MYSQL_"))}
    result["COMPOSE_DISABLE_ENV_FILE"] = "true"
    return result


def verify_identity(stdout: str) -> None:
    expected = [[VERSION, HOSTNAME, SERVER_ID, "InnoDB", "1", "1", "ROW", "ON", "ON"]]
    require(parse_rows(stdout) == expected, "unexpected_server_identity_or_settings")


def parse_rows(stdout: str) -> list[list[str]]:
    require(isinstance(stdout, str) and "\x00" not in stdout, "invalid_output")
    return [line.split("\t") for line in stdout.splitlines()]


def verify_rows(stage: str, stdout: str) -> None:
    require(stage in EXPECTED_ROWS, "unknown_row_oracle")
    require(parse_rows(stdout) == EXPECTED_ROWS[stage], "row_oracle_failed")


def verify_explain(stdout: str) -> None:
    try:
        data = json.loads(stdout)
    except (ValueError, RecursionError):
        raise LabFailure("invalid_explain_json") from None
    require(isinstance(data, dict) and isinstance(data.get("query_block"), dict), "invalid_explain_shape")
    # Small fixtures legitimately produce different access paths. The lab does
    # not equate JSON parsing, index existence, or EXPLAIN estimates with speed.


class LocalClient:
    def __init__(self) -> None:
        self.database = "efl_mysql_" + uuid.uuid4().hex
        require(DATABASE_PATTERN.fullmatch(self.database) is not None, "invalid_generated_database")
        self.stage = "docker_context"
        self.commands = 0
        self.host: str | None = None
        self.identity_verified = False
        self.database_created = False
        self.database_creation_attempted = False
        self.environment = safe_environment(dict(os.environ))
        self.docker = shutil.which("docker")

    def invoke(self, arguments: list[str], sql: str = "") -> subprocess.CompletedProcess:
        require(self.docker is not None, "docker_cli_not_found")
        require(self.commands < MAX_COMMANDS, "command_budget_exceeded")
        self.commands += 1
        try:
            result = subprocess.run(
                [self.docker, *arguments], input=sql.encode("utf-8"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT_SECONDS,
                check=False, shell=False, env=self.environment, cwd=str(TRACK_DIRECTORY),
            )
        except subprocess.TimeoutExpired:
            # Killing the Docker client does not prove that server execution
            # stopped or rolled back. Retain namespace and report uncertainty.
            raise LabFailure("command_timeout_server_state_unknown") from None
        except (OSError, ValueError):
            raise LabFailure("docker_command_failed") from None
        require(isinstance(result.stdout, bytes) and isinstance(result.stderr, bytes), "invalid_process_output")
        # A post-capture validation limit, not a streaming memory-use bound.
        require(len(result.stdout) + len(result.stderr) <= MAX_OUTPUT_BYTES, "output_too_large")
        return result

    def connect(self) -> None:
        require(self.host is None, "context_already_inspected")
        result = self.invoke(["context", "inspect"])
        require(result.returncode == 0, "docker_context_inspection_failed")
        try:
            context = json.loads(result.stdout.decode("utf-8"))
        except (ValueError, RecursionError):
            raise LabFailure("invalid_docker_context_json") from None
        self.host = local_docker_host(context)

    def execute(self, stage: str) -> str:
        require(stage in {"preflight", "create", *STAGES}, "sql_stage_refused")
        require(DATABASE_PATTERN.fullmatch(self.database) is not None, "invalid_generated_database")
        require(self.host is not None, "docker_context_not_inspected")
        # Recheck before dispatch; no TCP/SSH endpoint can enter this path.
        local_docker_host([{"Endpoints": {"docker": {"Host": self.host}}}])
        if stage == "preflight":
            sql = PREFLIGHT_SQL
        else:
            require(self.identity_verified, "server_identity_not_verified")
            if stage == "create":
                require(not self.database_creation_attempted, "database_creation_already_attempted")
                self.database_creation_attempted = True
                sql = f"CREATE DATABASE `{self.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;\nSELECT 'created';\n"
            else:
                require(self.database_created, "database_creation_not_confirmed")
                sql = SESSION_SQL + f"USE `{self.database}`;\n" + STAGES[stage]
        self.stage = stage
        result = self.invoke([
            "--host", self.host, "compose", "--project-name", PROJECT,
            "--project-directory", str(TRACK_DIRECTORY), "-f", str(COMPOSE_FILE),
            "exec", "-T", "mysql", "sh", "-c", MYSQL_COMMAND,
        ], sql)
        if stage in NEGATIVE_ERRORS:
            expected_errno, expected_state = NEGATIVE_ERRORS[stage]
            match = re.search(rb"(?m)^ERROR ([0-9]+) \(([0-9A-Z]{5})\)(?: at line [0-9]+)?:", result.stderr)
            require(result.returncode != 0 and result.stdout == b"" and match is not None,
                    "expected_constraint_rejection_missing")
            require((int(match[1]), match[2].decode("ascii")) == (expected_errno, expected_state),
                    "wrong_constraint_error")
            require(len(re.findall(rb"(?m)^ERROR ", result.stderr)) == 1, "multiple_sql_errors")
            return ""
        require(result.returncode == 0, "mysql_statement_failed")
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            raise LabFailure("invalid_output_encoding") from None


def run_lab(client: LocalClient) -> dict[str, Any]:
    client.connect()
    verify_identity(client.execute("preflight"))
    client.identity_verified = True
    verify_rows("create", client.execute("create"))
    client.database_created = True
    for stage in ("schema", "semantics"):
        verify_rows(stage, client.execute(stage))
    verify_explain(client.execute("explain"))
    for stage in ("commit", "rollback"):
        verify_rows(stage, client.execute(stage))
    for stage in NEGATIVE_ERRORS:
        client.execute(stage)
    verify_rows("final", client.execute("final"))
    client.stage = "complete"
    return {
        "status": "PASS", "mode": "local_engine", "version": VERSION,
        "database": client.database, "database_retained": True, "commands": client.commands,
        "oracles": {"accounts": 2, "orders": 4, "total_balance_cents": 15000,
                    "balances_cents": [8750, 6250], "null_not_in_count": 0,
                    "anti_join_ids": [102, 104], "constraint_errors": [1062, 1452, 3819],
                    "explain_json_parsed": True, "rollback_restored_rows": True},
        "not_verified": ["multi-session isolation or locking", "crash durability", "replication or failover",
                         "backup restore", "production performance", "security isolation"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-local", action="store_true",
                        help="Opt in to writes to one new local MySQL database, retained without cleanup.")
    args = parser.parse_args(argv)
    if not args.run_local:
        parser.error("Pass --run-local to opt in. No subprocess was started.")
    if sys.version_info < (3, 10):
        print(json.dumps({"status": "ERROR", "stage": "preflight", "error": "python_3_10_required"}))
        return 1
    client = LocalClient()
    try:
        print(json.dumps(run_lab(client), ensure_ascii=False, sort_keys=True))
        return 0
    except LabFailure as error:
        print(json.dumps({"status": "ERROR", "stage": client.stage, "error": str(error),
                          "database": client.database,
                          "database_creation_attempted": client.database_creation_attempted,
                          "database_creation_confirmed": client.database_created,
                          "cleanup_performed": False, "commands": client.commands}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
