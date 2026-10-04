"""Offline contracts only. No actual key reads, sockets or Amplitude UI checks."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import ssl
import unittest
import urllib.error
from unittest.mock import patch

import http_lab as lab


RUN = "a" * 32
START = 1_800_000_000_000
NOW = START + 10000
SECRET = "never-print-this-test-key"
LABEL = "isolated-amplitude-test"
SOCKET_GUARD = patch("socket.create_connection", side_effect=AssertionError("Tests must never open a socket"))


def setUpModule():
    SOCKET_GUARD.start()


def tearDownModule():
    SOCKET_GUARD.stop()


class PoisonEnvironment:
    def __getitem__(self, key):
        if self.get(key) is None:
            raise KeyError(key)

    def get(self, key, default=None):
        # argparse/gettext may inspect non-secret terminal/locale settings.
        if key in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG", "COLUMNS", "LINES"):
            return default
        raise AssertionError("Plan or rejected input attempted to read a key/project environment value")


class Response:
    def __init__(self, data=None, status=200, *, raw=None, headers=None):
        self.status = status
        self.headers = {"Content-Type": "application/json"} if headers is None else headers
        self.raw = json.dumps(data if data is not None else {}).encode() if raw is None else raw
        self.read_limit = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        self.read_limit = limit
        return self.raw[:limit]


class Opener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_plan():
    return lab.build_plan(lab.load_fixture(), RUN, START)


def sender_for(response):
    opener = Opener(response)
    with patch.object(lab.urllib.request, "build_opener", return_value=opener):
        sender = lab.Sender()
    return sender, opener


def send_args(*extra):
    return ["--send-to-test-project", "--region", "us", "--confirm-project-label", LABEL,
            "--run-id", RUN, "--start-time-ms", str(START), *extra]


class FixtureTests(unittest.TestCase):
    def test_literal_counts_and_conversion(self):
        plan = make_plan()
        events = plan["events"]
        self.assertEqual(len(events), 10)
        self.assertEqual(len({event["user_id"] for event in events}), 4)
        self.assertEqual([event["event_type"] for event in events], [
            "Product Viewed", "Product Viewed", "Checkout Started", "Purchase Completed",
            "Product Viewed", "Checkout Started", "Purchase Completed", "Product Viewed",
            "Checkout Started", "Product Viewed"])
        for event_type, count, unique in [("Product Viewed", 5, 4), ("Checkout Started", 3, 3),
                                          ("Purchase Completed", 2, 2)]:
            actual = [event for event in events if event["event_type"] == event_type]
            self.assertEqual(len(actual), count)
            self.assertEqual(len({event["user_id"] for event in actual}), unique)
            self.assertEqual(plan["expected"]["event_counts"][event_type], count)
        self.assertEqual(plan["expected"]["ordered_funnel_users"], [4, 3, 2])
        self.assertEqual(plan["expected"]["ordered_funnel_conversion"], 0.5)
        self.assertFalse(plan["comparison_contract"]["verified_in_amplitude"])

    def test_timestamps_sessions_order_and_ids(self):
        events = make_plan()["events"]
        self.assertEqual([event["time"] for event in events], [START + number * 1000 for number in range(10)])
        self.assertEqual([event["event_id"] for event in events], list(range(1, 11)))
        self.assertEqual([event["session_id"] for event in events],
                         [START] * 4 + [START + 4000] * 3 + [START + 7000] * 2 + [START + 9000])
        self.assertEqual(len({event["insert_id"] for event in events}), 10)
        for event in events:
            self.assertTrue(event["user_id"].startswith("efl-amp-" + RUN + "-user-"))
            self.assertTrue(event["device_id"].startswith("efl-amp-" + RUN + "-device-"))
            self.assertEqual(event["event_properties"]["source"], "efl-http-v2")
            self.assertEqual(event["event_properties"]["lab_run_id"], RUN)
            self.assertNotIn("user_properties", event)
            self.assertNotIn("ip", event)
        self.assertEqual(events[2]["event_properties"]["order_id"], events[3]["event_properties"]["order_id"])

    def test_replay_and_new_run_identity_contract(self):
        first = make_plan()
        second = make_plan()
        self.assertEqual(first, second)
        shifted = lab.build_plan(lab.load_fixture(), RUN, START + 100000)
        self.assertEqual([event["insert_id"] for event in first["events"]],
                         [event["insert_id"] for event in shifted["events"]])
        self.assertNotEqual(first["events"][0]["time"], shifted["events"][0]["time"])
        fresh = lab.build_plan(lab.load_fixture(), "b" * 32, START)
        for field in ("insert_id", "user_id", "device_id"):
            self.assertTrue({event[field] for event in first["events"]}.isdisjoint(
                            {event[field] for event in fresh["events"]}))

    def test_closed_fixture_rejects_custom_data(self):
        fixture = lab.load_fixture()
        mutations = []
        custom = copy.deepcopy(fixture)
        custom["events"][0]["email"] = "real-user@example.invalid"
        mutations.append(custom)
        custom = copy.deepcopy(fixture)
        custom["events"][0]["user"] = "real-user@example.invalid"
        mutations.append(custom)
        custom = copy.deepcopy(fixture)
        custom["expected"]["ordered_funnel_conversion"] = 1.0
        mutations.append(custom)
        for custom in mutations:
            with self.subTest(custom=custom), patch.object(lab.Path, "open", return_value=io.BytesIO(json.dumps(custom).encode())):
                with self.assertRaises(lab.LabFailure):
                    lab.load_fixture()

    def test_fixture_read_is_bounded_and_errors_sanitized(self):
        for stream in (io.BytesIO(b"x" * (lab.MAX_FIXTURE_BYTES + 1)), io.BytesIO(b"["), io.BytesIO(b"[]")):
            with patch.object(lab.Path, "open", return_value=stream), self.assertRaises(lab.LabFailure):
                lab.load_fixture()
        with patch.object(lab.Path, "open", side_effect=OSError(SECRET)), self.assertRaisesRegex(
                lab.LabFailure, "^fixture_read_or_json_failure$"):
            lab.load_fixture()

    def test_bad_run_and_epoch_rejected(self):
        for run_id in ("A" * 32, "../foreign", "a" * 31, "a" * 33, None):
            with self.assertRaises(lab.LabFailure):
                lab.build_plan(lab.load_fixture(), run_id, START)
        for value in (True, 123, "1800000000000", lab.MAX_EPOCH_MS):
            with self.assertRaises(lab.LabFailure):
                lab.build_plan(lab.load_fixture(), RUN, value)
        for value in ("1.8e12", "1800000000", "+1800000000000", " 1800000000000", "9999999999999"):
            with self.assertRaises(Exception):
                lab.parse_epoch_ms(value)

    def test_recent_window_and_future_guard(self):
        plan = make_plan()
        lab.check_send_window(plan, NOW)
        lab.check_send_window(plan, START + lab.RECENT_WINDOW_MS)
        with self.assertRaisesRegex(lab.LabFailure, "future_events_refused"):
            lab.check_send_window(plan, START + 8999)
        with self.assertRaisesRegex(lab.LabFailure, "backfill_outside_recent_seven_days"):
            lab.check_send_window(plan, START + lab.RECENT_WINDOW_MS + 1)


class CredentialTests(unittest.TestCase):
    def test_only_dedicated_environment_and_exact_label(self):
        cases = [{}, {"AMPLITUDE_API_KEY": SECRET, lab.PROJECT_LABEL_ENV: LABEL},
                 {lab.API_KEY_ENV: SECRET, lab.PROJECT_LABEL_ENV: LABEL.upper()},
                 {lab.API_KEY_ENV: "bad\nkey", lab.PROJECT_LABEL_ENV: LABEL}]
        for environment in cases:
            with patch.object(lab.os, "environ", environment), self.assertRaises(lab.LabFailure):
                lab.credentials(LABEL)
        with patch.object(lab.os, "environ", {lab.API_KEY_ENV: SECRET, lab.PROJECT_LABEL_ENV: LABEL}):
            self.assertEqual(lab.credentials(LABEL), SECRET)

    def test_unconfirmed_label_does_not_read_key(self):
        class RecordingEnvironment:
            calls = []
            def get(self, key):
                self.calls.append(key)
                return "different-project"
        env = RecordingEnvironment()
        with patch.object(lab.os, "environ", env), self.assertRaises(lab.LabFailure):
            lab.credentials(LABEL)
        self.assertEqual(env.calls, [lab.PROJECT_LABEL_ENV])


class SenderTests(unittest.TestCase):
    def test_official_region_endpoints_one_post_fixed_payload(self):
        for region, endpoint in [("us", "https://api2.amplitude.com/2/httpapi"),
                                 ("eu", "https://api.eu.amplitude.com/2/httpapi")]:
            with self.subTest(region=region):
                response = Response({"code": 200, "events_ingested": 10, "api_key": SECRET, "error": SECRET})
                sender, opener = sender_for(response)
                output = sender.send(region, SECRET, make_plan()["events"])
                self.assertEqual(output["status"], "RECEIPT_ACCEPTED")
                self.assertFalse(output["chart_funnel_dedup_verified"])
                self.assertNotIn(SECRET, json.dumps(output))
                request, timeout = opener.calls[0]
                self.assertEqual(request.full_url, endpoint)
                self.assertEqual(request.get_method(), "POST")
                self.assertEqual(timeout, 10)
                payload = json.loads(request.data)
                self.assertEqual(payload["api_key"], SECRET)
                self.assertEqual(payload["events"], make_plan()["events"])
                self.assertLess(len(request.data), lab.MAX_REQUEST_BYTES)
                self.assertEqual(response.read_limit, lab.MAX_RESPONSE_BYTES + 1)
                with self.assertRaisesRegex(lab.LabFailure, "one_request_only_no_retry"):
                    sender.send(region, SECRET, make_plan()["events"])
                self.assertEqual(len(opener.calls), 1)

    def test_unknown_region_and_custom_payload_have_no_request(self):
        events = make_plan()["events"]
        sender, opener = sender_for(Response())
        with self.assertRaises(lab.LabFailure):
            sender.send("https://example.com", SECRET, events)
        for altered in (events[:9], copy.deepcopy(events), copy.deepcopy(events)):
            if len(altered) == 10:
                altered[0]["user_id"] = "real-user@example.invalid"
            with self.assertRaises(lab.LabFailure):
                sender.send("us", SECRET, altered)
        self.assertEqual(opener.calls, [])

    def test_request_size_bound(self):
        sender, opener = sender_for(Response())
        with self.assertRaisesRegex(lab.LabFailure, "payload_too_large"):
            sender.send("us", "x" * lab.MAX_REQUEST_BYTES, make_plan()["events"])
        self.assertEqual(opener.calls, [])

    def test_proxy_redirect_and_default_verified_tls(self):
        with patch.object(lab.urllib.request, "build_opener") as build:
            lab.Sender()
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], lab.RejectRedirects)
        self.assertIsInstance(handlers[2], lab.urllib.request.HTTPSHandler)
        self.assertEqual(handlers[2]._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(handlers[2]._context.check_hostname)
        with self.assertRaisesRegex(lab.LabFailure, "redirect_refused_upload_state_unknown"):
            handlers[1].redirect_request(None, None, 302, None, None, "https://example.com")

    def test_429_partial_and_ambiguous_receipts_never_pass_or_retry(self):
        cases = [(429, {"code": 429, "error": SECRET, "throttled_users": {SECRET: 9}}),
                 (400, {"code": 400, "error": SECRET}), (403, {"code": 403}), (413, {"code": 413}),
                 (500, {"code": 500}), (200, {"code": 200, "events_ingested": 9}),
                 (200, {"events_ingested": 10}), (200, {"code": 200, "events_ingested": "10"})]
        for status, data in cases:
            with self.subTest(status=status, data=data):
                sender, opener = sender_for(Response(data, status))
                result = sender.send("us", SECRET, make_plan()["events"])
                self.assertEqual(result["status"], "NEEDS_REVIEW")
                self.assertFalse(result["automatic_retry_performed"])
                self.assertNotIn(SECRET, json.dumps(result))
                self.assertEqual(len(opener.calls), 1)

    def test_http_error_receipt_is_safely_classified(self):
        error = urllib.error.HTTPError("https://api2.amplitude.com", 429, SECRET,
            {"Content-Type": "application/json"}, io.BytesIO(json.dumps({"code": 429, "error": SECRET}).encode()))
        sender, opener = sender_for(error)
        result = sender.send("us", SECRET, make_plan()["events"])
        self.assertEqual(result["http_status"], 429)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(len(opener.calls), 1)

    def test_malformed_transport_is_sanitized_and_not_retried(self):
        cases = [Response({}, 302), Response({}, raw=b"{"), Response([]),
            Response({}, headers={"Content-Encoding": "gzip"}),
            Response({}, headers={"Content-Type": "text/html"}),
            Response({}, headers={"Content-Type": "application/json", "Content-Length": "999999999"}),
            Response({}, raw=b"x" * (lab.MAX_RESPONSE_BYTES + 1)), urllib.error.URLError(SECRET)]
        for response in cases:
            with self.subTest(response=response):
                sender, opener = sender_for(response)
                with self.assertRaises(lab.LabFailure) as caught:
                    sender.send("us", SECRET, make_plan()["events"])
                self.assertNotIn(SECRET, str(caught.exception))
                self.assertEqual(len(opener.calls), 1)


class CliTests(unittest.TestCase):
    def test_default_plan_and_help_have_no_key_reads_or_network(self):
        with patch.object(lab.os, "environ", PoisonEnvironment()), patch.object(lab, "Sender") as constructor:
            with patch.object(lab.time, "time", return_value=NOW / 1000):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(lab.main([]), 0)
            output = json.loads(stdout.getvalue())
            self.assertEqual(output["status"], "PLAN")
            self.assertEqual(output["network_calls"], 0)
            self.assertEqual(output["start_time_ms"], START)
            self.assertEqual(output["events"][-1]["time"], NOW - 1000)
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
                lab.main(["--help"])
            self.assertEqual(caught.exception.code, 0)
            constructor.assert_not_called()

    def test_fixed_old_plan_allowed_without_send(self):
        with patch.object(lab.os, "environ", PoisonEnvironment()), patch.object(lab, "Sender") as constructor:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(lab.main(["--plan", "--run-id", RUN, "--start-time-ms", "1600000000000"]), 0)
            self.assertEqual(json.loads(stdout.getvalue())["start_time_ms"], 1600000000000)
            constructor.assert_not_called()

    def test_missing_region_confirmation_and_invalid_arguments_no_io_or_echo(self):
        cases = [["--send-to-test-project"], ["--send-to-test-project", "--confirm-project-label", LABEL],
            ["--send-to-test-project", "--region", "us"], ["--plan", "--region", "us"],
            ["--plan", "--send-to-test-project"], ["--region", SECRET], ["--run-id", SECRET],
            ["--api-key", SECRET], ["--start-time-ms", SECRET]]
        for args in cases:
            with self.subTest(args=args), patch.object(lab.os, "environ", PoisonEnvironment()), patch.object(lab, "Sender") as constructor:
                with contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit) as caught:
                    lab.main(args)
                self.assertEqual(caught.exception.code, 2)
                self.assertNotIn(SECRET, stderr.getvalue())
                constructor.assert_not_called()

    def test_future_and_old_send_refused_before_key_access(self):
        for now in (START, START + lab.RECENT_WINDOW_MS + 1):
            with patch.object(lab.time, "time", return_value=now / 1000), patch.object(lab.os, "environ", PoisonEnvironment()), patch.object(lab, "Sender") as constructor:
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(lab.main(send_args()), 1)
                output = json.loads(stdout.getvalue())
                self.assertEqual(output["requests"], 0)
                self.assertEqual(output["upload_state"], "not_sent")
                constructor.assert_not_called()

    def test_bad_environment_no_sender(self):
        for environment in ({}, {lab.PROJECT_LABEL_ENV: LABEL, "AMPLITUDE_API_KEY": SECRET},
                            {lab.PROJECT_LABEL_ENV: "wrong", lab.API_KEY_ENV: SECRET}):
            with patch.object(lab.time, "time", return_value=NOW / 1000), patch.object(lab.os, "environ", environment), patch.object(lab, "Sender") as constructor:
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(lab.main(send_args()), 1)
                self.assertNotIn(SECRET, stdout.getvalue())
                constructor.assert_not_called()

    def test_send_output_receipt_only_no_key_payload_or_raw_response(self):
        for response, expected_status, exit_code in [
            (Response({"code": 200, "events_ingested": 10, "error": SECRET}), "RECEIPT_ACCEPTED", 0),
            (Response({"code": 200, "events_ingested": 5, "error": SECRET}), "NEEDS_REVIEW", 1),
            (urllib.error.URLError(SECRET), "ERROR", 1)]:
            with self.subTest(expected_status=expected_status):
                opener = Opener(response)
                with patch.object(lab.time, "time", return_value=NOW / 1000), patch.object(lab.os, "environ", {
                        lab.PROJECT_LABEL_ENV: LABEL, lab.API_KEY_ENV: SECRET}), patch.object(lab.urllib.request, "build_opener", return_value=opener):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        self.assertEqual(lab.main(send_args()), exit_code)
                text = stdout.getvalue()
                output = json.loads(text)
                self.assertEqual(output["status"], expected_status)
                self.assertFalse(output["chart_funnel_dedup_verified"])
                self.assertNotIn(SECRET, text)
                self.assertNotIn("Product Viewed", text)
                self.assertNotIn("api_key", output)
                self.assertEqual(len(opener.calls), 1)


if __name__ == "__main__":
    unittest.main()
