"""Prepare a synthetic event ledger; optionally send ONE batch to a test project.

Python 3.10+ standard library. Default/--plan never reads keys or uses a network.
--help only prints help. No retries, deletes, exports, SDK installs or real-user
payloads. A successful HTTP upload is NOT a verified chart/funnel/dedup result.
Official API contract: https://amplitude.com/docs/apis/analytics/http-v2
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENDPOINTS = {"us": "https://api2.amplitude.com/2/httpapi",
             "eu": "https://api.eu.amplitude.com/2/httpapi"}
API_KEY_ENV = "AMPLITUDE_LAB_API_KEY"
PROJECT_LABEL_ENV = "AMPLITUDE_LAB_PROJECT_LABEL"
FIXTURE_ID = "efl-amplitude-basic-v1"
SOURCE = "efl-http-v2"
MAX_FIXTURE_BYTES = 32 * 1024
MAX_REQUEST_BYTES = 32 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
SOCKET_TIMEOUT_SECONDS = 10
RECENT_WINDOW_MS = 7 * 24 * 60 * 60 * 1000
RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
MIN_EPOCH_MS = 1_000_000_000_000
MAX_EPOCH_MS = 4_102_444_800_000
EVENT_SPEC = (
    ("a", "Product Viewed", 0), ("a", "Product Viewed", 1000),
    ("a", "Checkout Started", 2000), ("a", "Purchase Completed", 3000),
    ("b", "Product Viewed", 4000), ("b", "Checkout Started", 5000),
    ("b", "Purchase Completed", 6000), ("c", "Product Viewed", 7000),
    ("c", "Checkout Started", 8000), ("d", "Product Viewed", 9000),
)
EXPECTED = {
    "total_events": 10, "unique_users": 4,
    "event_counts": {"Product Viewed": 5, "Checkout Started": 3, "Purchase Completed": 2},
    "unique_users_by_event": {"Product Viewed": 4, "Checkout Started": 3, "Purchase Completed": 2},
    "ordered_funnel_users": [4, 3, 2], "ordered_funnel_conversion": 0.5,
    "converted_user_aliases": ["a", "b"],
}


class LabFailure(Exception):
    """Terse constant error codes only; never attach raw responses or key values."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise LabFailure(code)


def integer(value: Any) -> bool:
    return type(value) is int and value >= 0


def parse_epoch_ms(value: str) -> int:
    if re.fullmatch(r"[0-9]{13}", value) is None:
        raise argparse.ArgumentTypeError("epoch_milliseconds_required")
    parsed = int(value)
    if not MIN_EPOCH_MS <= parsed <= MAX_EPOCH_MS - EVENT_SPEC[-1][2]:
        raise argparse.ArgumentTypeError("epoch_outside_lab_range")
    return parsed


def load_fixture() -> dict[str, Any]:
    try:
        with Path(__file__).with_name("fixture.json").open("rb") as stream:
            raw = stream.read(MAX_FIXTURE_BYTES + 1)
        require(len(raw) <= MAX_FIXTURE_BYTES, "fixture_too_large")
        result = json.loads(raw.decode("utf-8"))
    except LabFailure:
        raise
    except (OSError, ValueError, RecursionError):
        raise LabFailure("fixture_read_or_json_failure") from None
    expected_rows = [{"user": user, "event_type": event, "offset_ms": offset}
                     for user, event, offset in EVENT_SPEC]
    # Closed fixture schema: editing this JSON cannot add PII/custom properties
    # or change the destination payload to arbitrary real customer events.
    require(isinstance(result, dict) and set(result) == {
        "schema_version", "fixture_id", "source", "events", "expected"}, "fixture_schema_mismatch")
    require(type(result["schema_version"]) is int and result["schema_version"] == 1 and
            result["fixture_id"] == FIXTURE_ID and result["source"] == SOURCE and
            result["events"] == expected_rows and result["expected"] == EXPECTED,
            "fixture_contract_mismatch")
    require(all(type(row["offset_ms"]) is int for row in result["events"]), "fixture_offset_type_mismatch")
    return result


def utc_string(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000, timezone.utc).isoformat(timespec="milliseconds")


def build_plan(fixture: dict[str, Any], run_id: str, start_time_ms: int) -> dict[str, Any]:
    require(isinstance(run_id, str) and RUN_ID.fullmatch(run_id) is not None, "invalid_run_id")
    require(type(start_time_ms) is int and MIN_EPOCH_MS <= start_time_ms <= MAX_EPOCH_MS - 9000,
            "invalid_start_time_ms")
    # Read only the validated event ledger. All emitted identity/properties are
    # generated from bounded, synthetic aliases, never environment data.
    require(fixture.get("fixture_id") == FIXTURE_ID and fixture.get("events") == [
        {"user": user, "event_type": event, "offset_ms": offset} for user, event, offset in EVENT_SPEC],
        "fixture_contract_mismatch")
    namespace = uuid.UUID(hex=run_id)
    sessions: dict[str, int] = {}
    events = []
    for index, row in enumerate(fixture["events"]):
        alias = row["user"]
        event_time = start_time_ms + row["offset_ms"]
        sessions.setdefault(alias, event_time)
        properties = {"lab_run_id": run_id, "source": SOURCE}
        if row["event_type"] in ("Checkout Started", "Purchase Completed"):
            properties["order_id"] = f"efl-order-{run_id}-{alias}"
        events.append({
            "user_id": f"efl-amp-{run_id}-user-{alias}",
            "device_id": f"efl-amp-{run_id}-device-{alias}",
            "event_type": row["event_type"], "time": event_time,
            "session_id": sessions[alias], "event_id": index + 1,
            "insert_id": str(uuid.uuid5(namespace, f"{FIXTURE_ID}:event-{index + 1:02d}")),
            "event_properties": properties,
        })
    require(len(events) == 10 and len({event["insert_id"] for event in events}) == 10, "invalid_generated_events")
    return {
        "status": "PLAN", "network_calls": 0, "fixture_id": FIXTURE_ID,
        "run_id": run_id, "start_time_ms": start_time_ms,
        "first_event_utc": utc_string(start_time_ms), "last_event_utc": utc_string(start_time_ms + 9000),
        "events": events, "expected": EXPECTED,
        "comparison_contract": {
            "filter": {"event_property": "lab_run_id", "equals": run_id},
            "timezone": "UTC", "date_window": "include first_event_utc through last_event_utc",
            "funnel": "Product Viewed -> Checkout Started -> Purchase Completed",
            "funnel_order": "this order", "conversion_window": "at least 10 seconds",
            "unit": "unique users", "verified_in_amplitude": False,
        },
        "replay_contract": "reuse BOTH run_id and start_time_ms; inspect receipt/UI first; no automatic retry",
    }


def check_send_window(plan: dict[str, Any], now_ms: int) -> None:
    require(integer(now_ms), "invalid_clock")
    times = [event["time"] for event in plan["events"]]
    require(max(times) <= now_ms, "future_events_refused")
    require(min(times) >= now_ms - RECENT_WINDOW_MS, "backfill_outside_recent_seven_days")


def validate_generated_events(events: Any) -> None:
    require(isinstance(events, list) and len(events) == 10 and isinstance(events[0], dict), "fixed_batch_required")
    properties = events[0].get("event_properties")
    require(isinstance(properties, dict), "synthetic_events_required")
    run_id = properties.get("lab_run_id")
    fixture = {"fixture_id": FIXTURE_ID, "events": [
        {"user": user, "event_type": event, "offset_ms": offset} for user, event, offset in EVENT_SPEC]}
    expected = build_plan(fixture, run_id, events[0].get("time"))["events"]
    require(events == expected and all(type(event.get(field)) is int for event in events
                                      for field in ("time", "session_id", "event_id")), "synthetic_events_required")


def credentials(confirmed_label: str) -> str:
    require(isinstance(confirmed_label, str) and 1 <= len(confirmed_label) <= 100 and
            confirmed_label == confirmed_label.strip() and all(char.isprintable() for char in confirmed_label),
            "invalid_project_label")
    label = os.environ.get(PROJECT_LABEL_ENV)
    require(label == confirmed_label, "project_label_not_confirmed")
    key = os.environ.get(API_KEY_ENV)
    require(isinstance(key, str) and 1 <= len(key) <= 256 and key.isascii() and
            all(33 <= ord(char) <= 126 for char in key), "lab_api_key_missing_or_invalid")
    return key


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LabFailure("redirect_refused_upload_state_unknown")


class Sender:
    def __init__(self) -> None:
        self.requests = 0
        self.http_status: int | None = None
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), RejectRedirects(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )

    def send(self, region: str, api_key: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        require(region in ENDPOINTS, "region_required")
        require(self.requests == 0, "one_request_only_no_retry")
        validate_generated_events(events)
        payload = json.dumps({"api_key": api_key, "events": events}, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")
        require(len(payload) <= MAX_REQUEST_BYTES, "payload_too_large")
        request = urllib.request.Request(ENDPOINTS[region], data=payload, method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json", "Accept-Encoding": "identity"})
        self.requests += 1
        try:
            try:
                response = self.opener.open(request, timeout=SOCKET_TIMEOUT_SECONDS)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                self.http_status = response.status
                require(not 300 <= response.status < 400, "redirect_refused_upload_state_unknown")
                require(response.headers.get("Content-Encoding", "identity").strip().lower() in ("", "identity"),
                        "response_encoding_refused_upload_state_unknown")
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                require(content_type == "application/json", "non_json_receipt_upload_state_unknown")
                length = response.headers.get("Content-Length")
                require(length is None or (length.isdigit() and int(length) <= MAX_RESPONSE_BYTES),
                        "receipt_too_large_upload_state_unknown")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                require(len(raw) <= MAX_RESPONSE_BYTES, "receipt_too_large_upload_state_unknown")
                data = json.loads(raw.decode("utf-8"))
                require(isinstance(data, dict), "invalid_receipt_upload_state_unknown")
                return classify_receipt(response.status, data, len(events))
        except LabFailure:
            raise
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError, RecursionError):
            raise LabFailure("transport_or_receipt_failure_upload_state_unknown") from None


def classify_receipt(http_status: int, data: dict[str, Any], expected_events: int) -> dict[str, Any]:
    # Error strings, IDs, invalid-field maps and arbitrary keys are never echoed.
    allowed = {key: data[key] for key in ("code", "events_ingested", "payload_size_bytes", "server_upload_time")
               if integer(data.get(key))}
    exact = http_status == 200 and allowed.get("code") == 200 and allowed.get("events_ingested") == expected_events
    return {
        "status": "RECEIPT_ACCEPTED" if exact else "NEEDS_REVIEW",
        "http_status": http_status, "receipt": allowed, "expected_events": expected_events,
        "chart_funnel_dedup_verified": False, "automatic_retry_performed": False,
        "next_step": "inspect test-project receipt and UI using the same run_id; do not invent new insert_ids to retry",
    }


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes bad argument values, which may be a pasted key.
        self.print_usage(sys.stderr)
        self.exit(2, "Invalid arguments. Use --help; no request was sent.\n")


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="Print synthetic ledger; no key reads or network (default).")
    mode.add_argument("--send-to-test-project", action="store_true", help="Opt in to one irreversible event upload.")
    parser.add_argument("--run-id", help="32 lowercase hex characters; reuse on a deliberate replay.")
    parser.add_argument("--start-time-ms", type=parse_epoch_ms,
                        help="13-digit epoch milliseconds; default recent 9-second window ending one second ago.")
    parser.add_argument("--region", choices=tuple(ENDPOINTS), help="Explicit project residency; required only to send.")
    parser.add_argument("--confirm-project-label", help="Must exactly match AMPLITUDE_LAB_PROJECT_LABEL.")
    args = parser.parse_args(argv)
    if args.run_id is not None and RUN_ID.fullmatch(args.run_id) is None:
        parser.error("invalid_run_id")
    if args.send_to_test_project and (args.region is None or args.confirm_project_label is None):
        parser.error("region_and_confirmation_required")
    if not args.send_to_test_project and (args.region is not None or args.confirm_project_label is not None):
        parser.error("send_options_not_applicable_to_plan")
    sender = None
    run_id = args.run_id or uuid.uuid4().hex
    start_time_ms = args.start_time_ms if args.start_time_ms is not None else int(time.time() * 1000) - 10000
    try:
        plan = build_plan(load_fixture(), run_id, start_time_ms)
        if not args.send_to_test_project:
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
            return 0
        check_send_window(plan, int(time.time() * 1000))
        api_key = credentials(args.confirm_project_label)
        sender = Sender()
        result = sender.send(args.region, api_key, plan["events"])
        result.update(run_id=run_id, start_time_ms=start_time_ms, region=args.region,
                      project_label_confirmed=True, requests=sender.requests)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "RECEIPT_ACCEPTED" else 1
    except LabFailure as error:
        print(json.dumps({"status": "ERROR", "error": str(error), "run_id": run_id,
                          "start_time_ms": start_time_ms, "requests": sender.requests if sender else 0,
                          "http_status": sender.http_status if sender else None,
                          "chart_funnel_dedup_verified": False, "automatic_retry_performed": False,
                          "upload_state": "unknown_inspect_before_replay" if sender and sender.requests else "not_sent"},
                         sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
