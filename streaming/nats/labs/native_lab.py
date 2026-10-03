"""Opt-in, owned-loopback NATS experiment. Default invocation is a dry plan.

No SDK import, server, socket, or filesystem write occurs without --run-local.
The executable is explicitly supplied; version checks are not authenticity checks.
"""

import argparse
import asyncio
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace


SERVER_VERSION = "2.15.0"
SDK_VERSION = "2.16.0"
HOST = "127.0.0.1"
USER = "synthetic_nats_lab"
REPO = Path(__file__).resolve().parents[3]
ENV_ALLOWLIST = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL",
})
FIRST_BODY = b'{"business_id":"synthetic-order-1","amount":7}'
OTHER_BODY = b'{"business_id":"synthetic-order-1","amount":999}'


class LabFailure(RuntimeError):
    """A dependency gate, owned process, or independent oracle failed."""


def require(condition, message):
    # Runtime checks deliberately survive python -O.
    if not condition:
        raise LabFailure(message)


def plan():
    return {
        "mode": "plan", "server_started": False, "network_used": False,
        "files_written": False, "required_server": SERVER_VERSION,
        "required_sdk": SDK_VERSION,
        "opt_in": "--run-local --server-binary ABSOLUTE_PATH",
        "scope": ["Core delivery", "no responders", "finite-window publish dedup",
                  "explicit ACK/NAK redelivery", "application idempotency ledger"],
        "not_proven": ["HA/Raft", "power-loss durability", "database transaction",
                       "end-to-end exactly-once", "dedup after window expiry"],
    }


def safe_environment(source):
    result = {}
    for key, value in source.items():
        if key.upper() in ENV_ALLOWLIST and isinstance(value, str):
            if "\x00" not in value and not value.startswith("()"):
                result[key.upper()] = value
    return result


def process_options():
    options = {"env": safe_environment(dict(os.environ)), "cwd": str(REPO)}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    return options


def check_binary(binary):
    path = Path(binary).expanduser()
    require(path.is_absolute(), "--server-binary must be an absolute path")
    require(path.is_file() and not path.is_symlink(), "server binary must be an existing regular file")
    path = path.resolve(strict=True)
    try:
        result = subprocess.run(
            [str(path), "-v"], capture_output=True, text=True, timeout=5,
            check=False, **process_options(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LabFailure("server version probe failed") from exc
    output = (result.stdout + result.stderr).strip()
    require(result.returncode == 0, "server version probe returned nonzero status")
    require(re.fullmatch(r"nats-server:\s+v" + re.escape(SERVER_VERSION), output) is not None,
            "server version must be exactly " + SERVER_VERSION)
    return path


def load_sdk():
    try:
        installed = metadata.version("nats-py")
    except metadata.PackageNotFoundError as exc:
        raise LabFailure("optional nats-py dependency is not installed") from exc
    require(installed == SDK_VERSION, "nats-py version must be exactly " + SDK_VERSION)
    # Import only after explicit opt-in and a package version gate.
    from nats.aio.client import Client
    from nats.errors import NoRespondersError
    from nats.js.api import (
        AckPolicy, ConsumerConfig, DeliverPolicy, ReplayPolicy,
        RetentionPolicy, StorageType, StreamConfig,
    )
    return SimpleNamespace(
        Client=Client, NoRespondersError=NoRespondersError, AckPolicy=AckPolicy,
        ConsumerConfig=ConsumerConfig, DeliverPolicy=DeliverPolicy,
        ReplayPolicy=ReplayPolicy, RetentionPolicy=RetentionPolicy,
        StorageType=StorageType, StreamConfig=StreamConfig,
    )


def storage_parent():
    root = REPO.resolve(strict=True)
    path = root
    for part in ("lab-workspaces", "nats-native"):
        path = path / part
        require(not path.is_symlink(), "storage parent must not be a symlink")
        if path.exists():
            require(path.is_dir(), "storage parent must be a directory")
        require(path.resolve().is_relative_to(root), "storage parent escaped repository")
        path.mkdir(exist_ok=True)
        require(path.resolve(strict=True).is_relative_to(root), "resolved storage parent escaped repository")
    return path


def reserve_port():
    # The port is not held across Popen. Authentication and fresh server_name
    # identity checks prevent an unrelated listener from becoming a fixture.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def server_command(binary, port, store, server_name, password):
    require(type(port) is int and 1 <= port <= 65535, "invalid local port")
    require(re.fullmatch(r"NATS_LAB_[a-f0-9]{32}", server_name) is not None, "invalid fixture name")
    require(isinstance(password, str) and len(password) >= 24, "invalid ephemeral password")
    return [str(binary), "-a", HOST, "-p", str(port), "-js", "-sd", str(store),
            "-n", server_name, "--user", USER, "--pass", password]


def check_identity(client, server_name, port):
    # _server_info is deliberately a pinned SDK-internal inspection point.
    info = client._server_info
    require(isinstance(info, dict), "missing server INFO")
    require(info.get("version") == SERVER_VERSION, "connected server version mismatch")
    require(info.get("server_name") == server_name, "connected server identity mismatch")
    require(info.get("jetstream") is True, "owned server has no JetStream")
    require(isinstance(info.get("server_id"), str) and bool(info["server_id"]), "missing server id")
    connected = client.connected_url
    require(connected is not None and connected.hostname == HOST and connected.port == port,
            "connection is not the owned loopback endpoint")


async def connect_owned(sdk, process, port, server_name, password):
    async def quiet_error_callback(error):
        # Startup retries are expected. The final error and every result oracle
        # still fail closed; do not log SDK exception text containing endpoints.
        return None

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        require(process.poll() is None, "owned server exited before readiness")
        client = sdk.Client()
        try:
            # This SDK can retry initial TCP selection inside connect even when
            # allow_reconnect=False. The outer timeout bounds that initial loop.
            await asyncio.wait_for(client.connect(
                servers=[f"nats://{HOST}:{port}"], user=USER, password=password,
                allow_reconnect=False, max_reconnect_attempts=0, connect_timeout=0.4,
                error_cb=quiet_error_callback,
            ), timeout=0.7)
        except (OSError, asyncio.TimeoutError):
            await asyncio.wait_for(client.close(), timeout=1)
            await asyncio.sleep(0.05)
            continue
        except BaseException:
            await asyncio.wait_for(client.close(), timeout=1)
            raise
        try:
            check_identity(client, server_name, port)
            require(process.poll() is None, "owned server exited during readiness")
            return client
        except BaseException:
            await asyncio.wait_for(client.close(), timeout=1)
            raise
    raise LabFailure("owned server did not become ready within five seconds")


def verify_business_ledger(messages):
    require(len(messages) == 2, "business oracle expects exactly two deliveries")
    ledger = {}
    naive_total = 0
    for message in messages:
        require(message.data == FIRST_BODY, "dedup changed the originally stored body")
        record = json.loads(message.data)
        require(record == {"business_id": "synthetic-order-1", "amount": 7}, "business fixture mismatch")
        naive_total += record["amount"]
        ledger.setdefault(record["business_id"], record["amount"])
    require(naive_total == 14 and len(ledger) == 1 and sum(ledger.values()) == 7,
            "application idempotency oracle failed")
    return {"deliveries": 2, "naive_total": 14, "idempotent_total": 7,
            "applied_business_keys": 1, "transactional_database": False}


async def exercise(client, sdk, run_name):
    checks = []
    core_subject = run_name + ".core"
    subscription = await client.subscribe(core_subject)
    await client.flush(timeout=2)
    await client.publish(core_subject, b"synthetic-core")
    await client.flush(timeout=2)
    message = await subscription.next_msg(timeout=2)
    require(message.subject == core_subject and message.data == b"synthetic-core", "Core delivery oracle failed")
    await subscription.unsubscribe()
    checks.append("core_subscription_flush_publish")

    try:
        await client.request(run_name + ".no_responder", b"synthetic-request", timeout=2)
    except sdk.NoRespondersError:
        checks.append("request_no_responders_is_error")
    else:
        raise LabFailure("request unexpectedly found a responder")

    js = client.jetstream(timeout=2)
    subject = run_name + ".events"
    stream_name = run_name + "_STREAM"
    durable_name = run_name + "_WORKER"
    stream = await js.add_stream(config=sdk.StreamConfig(
        name=stream_name, subjects=[subject], storage=sdk.StorageType.FILE,
        retention=sdk.RetentionPolicy.LIMITS, num_replicas=1,
        max_msgs=16, max_bytes=1048576, max_age=60, duplicate_window=30,
    ))
    require(stream.config.name == stream_name and stream.config.storage == sdk.StorageType.FILE,
            "fresh file stream was not configured")
    require(stream.state.messages == 0, "new owned stream is not empty")
    checks.append("fresh_file_stream")
    headers = {"Nats-Msg-Id": "synthetic-message-1"}
    first = await js.publish(subject, FIRST_BODY, headers=headers, timeout=2)
    duplicate = await js.publish(subject, OTHER_BODY, headers=headers, timeout=2)
    require(first.stream == stream_name and first.seq == 1 and not first.duplicate,
            "first publish acknowledgment mismatch")
    require(duplicate.stream == stream_name and duplicate.seq == 1 and duplicate.duplicate is True,
            "duplicate publish did not acknowledge the original sequence")
    checks.append("publish_id_dedup_same_sequence")
    stored = await js.get_msg(stream_name, seq=1)
    require(stored.data == FIRST_BODY, "duplicate publish overwrote the first body")
    checks.append("publish_dedup_first_body_wins")

    pull = await js.pull_subscribe(
        subject, durable=durable_name, stream=stream_name,
        config=sdk.ConsumerConfig(
            ack_policy=sdk.AckPolicy.EXPLICIT, ack_wait=2, max_ack_pending=1,
            max_deliver=3, deliver_policy=sdk.DeliverPolicy.ALL,
            replay_policy=sdk.ReplayPolicy.INSTANT,
        ),
    )
    first_batch = await pull.fetch(1, timeout=2)
    require(len(first_batch) == 1, "first pull batch size mismatch")
    delivery_one = first_batch[0]
    require(delivery_one.metadata.sequence.stream == 1 and delivery_one.metadata.sequence.consumer == 1
            and delivery_one.metadata.num_delivered == 1 and delivery_one.data == FIRST_BODY,
            "initial delivery metadata mismatch")
    pending = await js.consumer_info(stream_name, durable_name)
    require(pending.num_ack_pending == 1 and pending.config.max_ack_pending == 1,
            "explicit ACK pending state mismatch")
    checks.append("explicit_ack_pending")
    await delivery_one.nak()
    await client.flush(timeout=2)
    second_batch = await pull.fetch(1, timeout=2)
    require(len(second_batch) == 1, "redelivery pull batch size mismatch")
    delivery_two = second_batch[0]
    require(delivery_two.metadata.sequence.stream == 1 and delivery_two.metadata.sequence.consumer == 2
            and delivery_two.metadata.num_delivered == 2 and delivery_two.data == FIRST_BODY,
            "redelivery metadata mismatch")
    checks.append("nak_redelivery_preserves_stream_sequence")
    business = verify_business_ledger([delivery_one, delivery_two])
    checks.append("business_ledger_independent_of_delivery")
    await delivery_two.ack_sync(timeout=2)
    final = await js.consumer_info(stream_name, durable_name)
    require(final.num_ack_pending == 0 and final.num_pending == 0,
            "ACK confirmation did not clear pending delivery")
    checks.append("double_ack_pending_zero")
    final_stream = await js.stream_info(stream_name)
    require(final_stream.state.messages == 1, "Limits retention unexpectedly removed the acknowledged message")
    checks.append("limits_retention_keeps_acked_message")
    await pull.unsubscribe()
    return {"mode": "verified-local", "server_version": SERVER_VERSION,
            "sdk_version": SDK_VERSION, "checks": checks, "check_count": len(checks),
            "business": business, "not_proven": plan()["not_proven"]}


def stop_owned(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired as exc:
            raise LabFailure("owned server could not be stopped; storage cleanup withheld") from exc


async def run_session(sdk, process, port, run_name, password):
    client = await connect_owned(sdk, process, port, run_name, password)
    try:
        return await asyncio.wait_for(exercise(client, sdk, run_name), timeout=25)
    finally:
        await asyncio.wait_for(client.close(), timeout=3)


def run_local(binary):
    checked = check_binary(binary)
    sdk = load_sdk()
    parent = storage_parent()
    temporary = tempfile.TemporaryDirectory(prefix="owned-", dir=parent)
    process = None
    safe_to_clean = True
    try:
        store = Path(temporary.name).resolve(strict=True)
        require(store.is_relative_to(parent.resolve(strict=True)) and store != parent,
                "temporary storage escaped owned parent")
        run_name = "NATS_LAB_" + uuid.uuid4().hex
        password = secrets.token_urlsafe(32)
        port = reserve_port()
        process = subprocess.Popen(
            server_command(checked, port, store, run_name, password),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **process_options(),
        )
        result = asyncio.run(run_session(sdk, process, port, run_name, password))
        result["owned_server_stopped"] = False
    finally:
        try:
            if process is not None:
                stop_owned(process)
        except BaseException:
            safe_to_clean = False
            # Do not let TemporaryDirectory's finalizer delete live storage.
            temporary._finalizer.detach()
            raise
        finally:
            if safe_to_clean:
                temporary.cleanup()
    result["owned_server_stopped"] = True
    result["owned_storage_removed"] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-local", action="store_true", help="start only an owned loopback server")
    parser.add_argument("--server-binary", help="absolute path to a verified official nats-server binary")
    args = parser.parse_args(argv)
    if not args.run_local:
        print(json.dumps(plan(), indent=2))
        return 0
    if not args.server_binary:
        parser.error("--run-local requires --server-binary")
    try:
        result = run_local(args.server_binary)
    except Exception as exc:
        # Do not print external exception messages: those may contain credentials.
        message = str(exc) if isinstance(exc, LabFailure) else type(exc).__name__
        print(json.dumps({"mode": "failed", "error": message}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
