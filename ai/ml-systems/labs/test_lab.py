"""Pure oracles plus REAL, bounded loopback HTTP integration tests.

Running this test file opts into local socket bind/connect. No remote destination
is allowed. Use lab.py --plan when no local service execution is desired.
"""

from __future__ import annotations

import contextlib
from copy import deepcopy
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import socket
import threading
import unittest
from unittest.mock import MagicMock, patch


SPEC = importlib.util.spec_from_file_location("ml_systems_lab_under_test", Path(__file__).with_name("lab.py"))
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("ML systems lab could not be loaded")
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)


class PureTests(unittest.TestCase):
    def test_literal_inference_and_candidate_regression(self):
        self.assertEqual(lab.probability(lab.BASELINE, [0.0, 0.0]), 0.5)
        self.assertAlmostEqual(lab.probability(lab.BASELINE, [1.0, 1.0]), 0.8807970779778823, places=14)
        self.assertAlmostEqual(lab.probability(lab.CANDIDATE, [1.0, 1.0]), 0.11920292202211755, places=14)
        self.assertAlmostEqual(lab.probability(lab.BASELINE, [-1.0, 0.0]),
                               1 - lab.probability(lab.BASELINE, [1.0, 0.0]), places=14)

    def test_stable_logistic_and_bad_artifact(self):
        self.assertEqual(lab.probability(lab.BASELINE, [1000.0, 0.0]), 1.0)
        self.assertEqual(lab.probability(lab.BASELINE, [-1000.0, 0.0]), 0.0)
        bad = lab.Artifact("bad", (math.nan, 0.0), 0.0)
        with self.assertRaisesRegex(lab.LabError, "invalid_model_artifact"):
            lab.probability(bad, [1.0, 0.0])

    def test_payload_factories_are_independent(self):
        first, second = lab.valid_payload(), lab.valid_payload()
        first["features"][0] = -5.0
        self.assertEqual(second["features"], [1.0, 0.0])

    def test_controller_is_local_versioned_pointer(self):
        controller = lab.Controller()
        self.assertEqual(controller.current(), lab.BASELINE)
        controller.select(lab.CANDIDATE.version)
        self.assertEqual(controller.current(), lab.CANDIDATE)
        controller.select(lab.BASELINE.version)
        self.assertEqual(controller.history, ["baseline-v1", "candidate-v2", "baseline-v1"])
        with self.assertRaisesRegex(lab.LabError, "unknown_artifact"):
            controller.select("external-deployment")

    def test_aggregate_can_pass_while_slice_gate_rejects(self):
        rows = lab.evaluation_rows()
        baseline = lab.quality(rows, [{"prediction": row["label"]} for row in rows])
        candidate_replies = [{"prediction": row["label"]} for row in rows]
        candidate_replies[-1]["prediction"] = 0
        candidate = lab.quality(rows, candidate_replies)
        self.assertEqual(baseline["accuracy"], 1)
        self.assertEqual(candidate["accuracy"], 11 / 12)
        self.assertEqual(candidate["slices"]["edge"]["accuracy"], 0.5)
        gate = lab.rollout_gate(baseline, candidate)
        self.assertFalse(gate["promote"])
        self.assertEqual(gate["reasons"], ["slice_regression:edge"])

    def test_identical_quality_gate_accepts(self):
        rows = lab.evaluation_rows()
        report = lab.quality(rows, [{"prediction": row["label"]} for row in rows])
        self.assertTrue(lab.rollout_gate(report, report)["promote"])

    def test_missing_slice_cannot_silently_pass(self):
        rows = lab.evaluation_rows()
        baseline = lab.quality(rows, [{"prediction": row["label"]} for row in rows])
        candidate = lab.quality(rows[:10], [{"prediction": row["label"]} for row in rows[:10]])
        gate = lab.rollout_gate(baseline, candidate)
        self.assertFalse(gate["promote"])
        self.assertIn("slice_coverage_mismatch", gate["reasons"])
        self.assertIn("sample_coverage_mismatch", gate["reasons"])

    def test_nonfinite_or_inconsistent_metric_cannot_promote(self):
        rows = lab.evaluation_rows()
        report = lab.quality(rows, [{"prediction": row["label"]} for row in rows])
        for invalid_value in [math.nan, math.inf, 0.95]:
            invalid = deepcopy(report)
            invalid["accuracy"] = invalid_value
            with self.assertRaisesRegex(lab.LabError, "invalid_quality_report"):
                lab.rollout_gate(report, invalid)

    def test_quality_requires_real_labels_predictions_and_denominator(self):
        for rows, replies in [([], []), ([{"label": True, "slice": "a"}], [{"prediction": 1}]),
                              ([{"label": 1, "slice": "a"}], [{"prediction": True}]),
                              ([{"label": 1, "slice": "a"}], [])]:
            with self.assertRaises(lab.LabError):
                lab.quality(rows, replies)

    def test_pit_late_arrival_and_future_event_oracle(self):
        records = [{"entity": "a", "event_time": 90, "available_time": 92, "value": 1.0},
                   {"entity": "a", "event_time": 95, "available_time": 105, "value": 99.0},
                   {"entity": "a", "event_time": 110, "available_time": 110, "value": 5.0}]
        original = deepcopy(records)
        self.assertEqual(lab.point_in_time(records, "a", 100)["value"], 1.0)
        self.assertEqual(lab.point_in_time(records, "a", 105)["value"], 99.0)
        self.assertEqual(lab.point_in_time(records, "a", 110)["value"], 5.0)
        self.assertIsNone(lab.point_in_time(records, "a", 91))
        self.assertIsNone(lab.point_in_time(records, "missing", 200))
        self.assertEqual(records, original)

    def test_pit_duplicate_version_is_not_order_dependent(self):
        first = {"entity": "a", "event_time": 1, "available_time": 2, "value": 3.0}
        second = dict(first, value=8.0)
        with self.assertRaisesRegex(lab.LabError, "duplicate_feature_version"):
            lab.point_in_time([first, second], "a", 10)

    def test_pit_rejects_bad_times_or_features(self):
        for record in [{"entity": "a", "event_time": 2, "available_time": 1, "value": 3.0},
                       {"entity": "a", "event_time": 1, "available_time": 2, "value": math.nan},
                       {"entity": "a", "event_time": True, "available_time": 2, "value": 1.0}, {}]:
            with self.assertRaises(lab.LabError):
                lab.point_in_time([record], "a", 10)

    def test_label_delay_coverage_is_not_negative_label(self):
        predictions = [{"id": "a", "prediction": 1}, {"id": "b", "prediction": 0}]
        labels = [{"id": "a", "label": 1, "available_time": 10},
                  {"id": "b", "label": 1, "available_time": 20}]
        early = lab.delayed_label_metrics(predictions, labels, 10)
        complete = lab.delayed_label_metrics(predictions, labels, 20)
        self.assertEqual(early, {"prediction_count": 2, "labeled_count": 1, "label_coverage": 0.5,
                                 "accuracy_on_available_labels": 1.0})
        self.assertEqual(complete["accuracy_on_available_labels"], 0.5)

    def test_no_labels_has_undefined_accuracy(self):
        report = lab.delayed_label_metrics([{"id": "a", "prediction": 1}], [], 10)
        self.assertEqual(report["label_coverage"], 0)
        self.assertIsNone(report["accuracy_on_available_labels"])

    def test_duplicate_or_invalid_label_is_rejected(self):
        predictions = [{"id": "a", "prediction": 1}]
        label = {"id": "a", "label": 1, "available_time": 2}
        with self.assertRaisesRegex(lab.LabError, "duplicate_label_id"):
            lab.delayed_label_metrics(predictions, [label, label], 10)
        with self.assertRaisesRegex(lab.LabError, "duplicate_prediction_id"):
            lab.delayed_label_metrics(predictions * 2, [label], 10)
        with self.assertRaises(lab.LabError):
            lab.delayed_label_metrics(predictions, [dict(label, label=True)], 10)

    def test_independent_drift_counterexamples(self):
        report = lab.drift_experiment()
        self.assertEqual(report["mean_absolute_feature_before"], 1.5)
        self.assertEqual(report["mean_absolute_feature_shifted"], 3.5)
        self.assertEqual(report["accuracy_after_covariate_shift"], 1)
        self.assertEqual(report["accuracy_after_label_rule_change"], 0)
        self.assertTrue(report["identical_feature_marginal_after_label_rule_change"])

    def test_feature_label_counts_separate(self):
        report = lab.feature_and_label_experiment()
        self.assertEqual(report["feature_valid_fraction"], 3 / 4)
        self.assertEqual(report["early_labels"]["label_coverage"], 2 / 4)
        self.assertEqual(report["early_labels"]["accuracy_on_available_labels"], 1)
        self.assertEqual(report["complete_labels"]["accuracy_on_available_labels"], 0.5)


class ContractTests(unittest.TestCase):
    def test_normal_contract_and_exact_freshness_boundaries(self):
        self.assertEqual(lab.validate_payload(lab.valid_payload(), lab.BASELINE), [1.0, 0.0])
        for timestamp in [70, 100]:
            payload = lab.valid_payload()
            payload["feature_time"] = timestamp
            self.assertEqual(lab.validate_payload(payload, lab.BASELINE), [1.0, 0.0])

    def test_schema_type_dimension_and_ranges(self):
        cases = [(None, "schema_mismatch"), ({}, "schema_mismatch"),
                 (lab.valid_payload([True, 0]), "type_mismatch"),
                 (lab.valid_payload([math.nan, 0]), "type_mismatch"),
                 (lab.valid_payload([1]), "dimension_mismatch"),
                 (lab.valid_payload([9, 0]), "feature_range")]
        for payload, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(lab.ContractError, code):
                lab.validate_payload(payload, lab.BASELINE)

    def test_version_and_freshness_rejections(self):
        for key, value, code in [("feature_time", 69, "stale_feature"),
                                 ("feature_time", 101, "future_feature"),
                                 ("feature_version", "old", "feature_version_mismatch"),
                                 ("preprocessing_version", "old", "preprocessing_version_mismatch")]:
            payload = lab.valid_payload()
            payload[key] = value
            with self.assertRaisesRegex(lab.ContractError, code):
                lab.validate_payload(payload, lab.BASELINE)

    def test_strict_json_rejects_duplicate_nan_utf8(self):
        for data in [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b'{']:
            with self.assertRaises(lab.ContractError):
                lab.parse_json(data)

    def test_destination_rejects_external_aliases_and_invalid_ports(self):
        for host, port in [("example.com", 80), ("localhost", 8000), ("0.0.0.0", 8000),
                           ("::1", 8000), ("https://127.0.0.1", 8000), ("127.0.0.1", True),
                           ("127.0.0.1", 0), ("127.0.0.1", 65536)]:
            with self.assertRaisesRegex(lab.LabError, "nonlocal_destination"):
                lab.checked_destination(host, port)
        lab.checked_destination("127.0.0.1", 12345)

    def test_metrics_counts_units_and_no_samples(self):
        metrics = lab.Metrics()
        self.assertIsNone(metrics.snapshot()["handler_p95_seconds"])
        metrics.begin()
        metrics.finish(200, "ok", "baseline-v1", 0.001)
        metrics.begin()
        metrics.finish(422, "type_mismatch", "baseline-v1", 0.002)
        report = metrics.snapshot()
        self.assertEqual(report["response_error_rate"], 0.5)
        self.assertEqual(report["handler_p95_seconds"], 0.002)
        self.assertEqual(report["by_model_version"], {"baseline-v1": 2})


class ActualHTTPTests(unittest.TestCase):
    def setUp(self):
        # Test-level guard: real TCP sockets, but never a non-loopback destination/bind.
        original_connect = socket.socket.connect
        original_bind = socket.socket.bind

        def connect(sock, address):
            if not isinstance(address, tuple) or address[0] != "127.0.0.1":
                raise AssertionError("non-loopback connect forbidden")
            return original_connect(sock, address)

        def bind(sock, address):
            if not isinstance(address, tuple) or address != ("127.0.0.1", 0):
                raise AssertionError("non-ephemeral-loopback bind forbidden")
            return original_bind(sock, address)

        self.addCleanup(patch.stopall)
        patch.object(socket.socket, "connect", connect).start()
        patch.object(socket.socket, "bind", bind).start()
        patch("builtins.open", side_effect=AssertionError("application file I/O forbidden")).start()
        patch("os.open", side_effect=AssertionError("application file I/O forbidden")).start()

    def test_normal_real_http_and_cleanup(self):
        service = lab.Service()
        with service:
            self.assertEqual(service.server.server_address[0], "127.0.0.1")
            self.assertGreater(service.server.server_address[1], 0)
            status, body = lab.request(service, lab.valid_payload())
            self.assertEqual(status, 200)
            self.assertEqual(body["model_version"], "baseline-v1")
            self.assertAlmostEqual(body["probability"], 0.8807970779778823, places=14)
            self.assertEqual(service.server.metrics.snapshot()["requests_seen"], 1)
        self.assertTrue(service.closed)
        self.assertFalse(service.thread.is_alive())
        self.assertEqual(service.server.socket.fileno(), -1)
        with self.assertRaisesRegex(lab.LabError, "service_not_running"):
            lab.request(service, lab.valid_payload())

    def test_six_http_failures_each_repaired(self):
        with lab.Service() as service:
            outcomes = lab.contract_experiments(service)
            self.assertEqual([row["rejected_status"] for row in outcomes], [400, 422, 422, 409, 409, 409])
            self.assertTrue(all(row["repaired_status"] == 200 for row in outcomes))
            metrics = service.server.metrics.snapshot()
            self.assertEqual(metrics["requests_seen"], 12)
            self.assertEqual(metrics["error_responses"], 6)

    def test_out_of_numeric_range_integer_is_contract_failure_then_recovers(self):
        payload = lab.valid_payload([10 ** 400, 0])
        self.assertLess(len(json.dumps(payload).encode("utf-8")), lab.MAX_BODY_BYTES)
        self.assertFalse(lab.is_number(payload["features"][0]))
        with lab.Service() as service:
            status, body = lab.request(service, payload)
            self.assertEqual((status, body["error"]), (422, "type_mismatch"))
            self.assertEqual(lab.request(service, lab.valid_payload())[0], 200)
            self.assertNotIn("internal_error", service.server.metrics.snapshot()["by_reason"])

    def test_baseline_quality_mutation_fails_and_service_closes(self):
        original = lab.probability
        service = lab.Service()

        def changed(artifact, features):
            value = original(artifact, features)
            return 1 - value if artifact.version == "baseline-v1" and features == [5.0, 0.0] else value

        with patch.object(lab, "probability", changed), patch.object(lab, "Service", return_value=service):
            with self.assertRaisesRegex(lab.LabError, "baseline_quality_oracle_failed"):
                lab.run()
        self.assertTrue(service.closed)
        self.assertFalse(service.thread.is_alive())

    def test_candidate_slice_mutation_cannot_keep_same_aggregate_and_pass(self):
        original = lab.probability
        service = lab.Service()

        def changed(artifact, features):
            value = original(artifact, features)
            if artifact.version == "candidate-v2" and features in ([5.0, 0.0], [1.0, 1.0]):
                return 1 - value
            return value

        with patch.object(lab, "probability", changed), patch.object(lab, "Service", return_value=service):
            with self.assertRaisesRegex(lab.LabError, "candidate_quality_oracle_failed"):
                lab.run()
        self.assertTrue(service.closed)
        self.assertFalse(service.thread.is_alive())

    def test_full_actual_http_rollout_and_rollback(self):
        output = lab.run()
        self.assertEqual(output["status"], "PASS")
        self.assertTrue(output["server_closed"])
        self.assertEqual(output["http"]["actual_loopback_http_requests"], 48)
        self.assertEqual(output["http"]["metrics"]["by_reason"]["ok"], 42)
        self.assertEqual(output["http"]["metrics"]["error_responses"], 6)
        self.assertEqual(output["http"]["metrics"]["response_error_rate"], 0.125)
        self.assertEqual(output["http"]["controller_history"], ["baseline-v1", "candidate-v2", "baseline-v1"])
        self.assertFalse(output["http"]["rollout_gate"]["promote"])
        self.assertTrue(output["http"]["rollback_predictions_equal"])
        json.dumps(output, allow_nan=False)

    def test_invalid_json_and_no_raw_feature_logs(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured), contextlib.redirect_stdout(captured), lab.Service() as service:
            for raw, code in [(b'{"x":1,"x":2}', "duplicate_json_key"),
                              (b'{"features":[NaN,0]}', "invalid_json"),
                              (b'{"SYNTHETIC_SECRET":', "invalid_json"), (b'\xff', "invalid_json")]:
                status, body = lab.request(service, raw=raw)
                self.assertEqual(status, 400)
                self.assertEqual(body["error"], code)
            self.assertEqual(lab.request(service, lab.valid_payload())[0], 200)
        self.assertEqual(captured.getvalue(), "")

    def test_body_content_type_method_route_bounds(self):
        with lab.Service() as service:
            for kwargs, status, code in [({"raw": b"x" * (lab.MAX_BODY_BYTES + 1)}, 413, "body_too_large"),
                                         ({"content_type": "text/plain"}, 415, "unsupported_media_type"),
                                         ({"method": "GET"}, 405, "method_not_allowed"),
                                         ({"path": "/not-inference"}, 404, "route_not_found")]:
                actual, body = lab.request(service, lab.valid_payload(), **kwargs)
                self.assertEqual((actual, body["error"]), (status, code))
            self.assertEqual(lab.request(service, lab.valid_payload())[0], 200)

    def test_server_request_budget_is_enforced(self):
        with lab.Service(request_limit=1) as service:
            self.assertEqual(lab.request(service, lab.valid_payload())[0], 200)
            status, body = lab.request(service, lab.valid_payload())
            self.assertEqual((status, body["error"]), (429, "request_budget_exceeded"))

    def test_client_budget_and_expired_session_before_io(self):
        with lab.Service() as service:
            service.client_requests = lab.MAX_REQUESTS
            with self.assertRaisesRegex(lab.LabError, "client_request_budget_exceeded"):
                lab.request(service, lab.valid_payload())
            service.client_requests = 0
            service.started_at -= lab.SESSION_BUDGET_SECONDS + 1
            with self.assertRaisesRegex(lab.LabError, "client_session_budget_exceeded"):
                lab.request(service, lab.valid_payload())
            self.assertEqual(service.server.metrics.snapshot()["requests_seen"], 0)

    def test_endpoint_tampering_blocked_before_connect(self):
        with lab.Service() as service:
            with patch.object(service.server, "server_address", ("example.com", 80)), \
                 patch.object(lab, "HTTPConnection") as connection:
                with self.assertRaisesRegex(lab.LabError, "nonlocal_destination"):
                    lab.request(service, lab.valid_payload())
                connection.assert_not_called()

    def test_proxy_environment_is_not_used(self):
        with patch.dict(os.environ, {"HTTP_PROXY": "http://external.invalid:1234",
                                     "HTTPS_PROXY": "http://external.invalid:1234", "NO_PROXY": ""}), \
             lab.Service() as service:
            self.assertEqual(lab.request(service, lab.valid_payload())[0], 200)

    def test_inference_internal_error_and_repair(self):
        with lab.Service() as service:
            with patch.object(lab, "probability", side_effect=RuntimeError("SYNTHETIC_SECRET")):
                status, body = lab.request(service, lab.valid_payload())
            self.assertEqual((status, body["error"]), (500, "internal_error"))
            self.assertNotIn("SYNTHETIC_SECRET", json.dumps(body))
            self.assertEqual(lab.request(service, lab.valid_payload())[0], 200)

    def test_incomplete_request_body_times_out_then_recovers(self):
        with lab.Service() as service:
            host, port = service.server.server_address
            connection = lab.HTTPConnection(host, port, timeout=lab.IO_TIMEOUT_SECONDS + 2)
            try:
                connection.request("POST", "/predict", body=b"{}",
                                   headers={"Content-Type": "application/json", "Content-Length": "3"})
                response = connection.getresponse()
                self.assertEqual(response.status, 408)
                self.assertEqual(json.loads(response.read())["error"], "request_timeout")
            finally:
                connection.close()
            self.assertEqual(lab.request(service, lab.valid_payload())[0], 200)

    def test_exception_inside_context_still_closes(self):
        service = lab.Service()
        with self.assertRaisesRegex(RuntimeError, "deliberate"), service:
            self.assertEqual(lab.request(service, lab.valid_payload())[0], 200)
            raise RuntimeError("deliberate")
        self.assertTrue(service.closed)
        self.assertFalse(service.thread.is_alive())
        self.assertEqual(service.server.socket.fileno(), -1)

    def test_thread_start_error_closes_bound_socket(self):
        service = lab.Service()
        with patch.object(threading.Thread, "start", side_effect=RuntimeError("deliberate")):
            with self.assertRaisesRegex(RuntimeError, "deliberate"):
                service.__enter__()
        self.assertTrue(service.closed)
        self.assertEqual(service.server.socket.fileno(), -1)

    def test_client_invalid_json_and_body_size_before_io(self):
        with lab.Service() as service:
            with self.assertRaisesRegex(lab.LabError, "client_invalid_json"):
                lab.request(service, lab.valid_payload([math.nan, 0]))
            with self.assertRaisesRegex(lab.LabError, "client_body_budget_exceeded"):
                lab.request(service, raw=b"x" * (lab.MAX_BODY_BYTES + 2))
            self.assertEqual(service.client_requests, 0)

    def test_client_refuses_redirect_and_large_response_without_following(self):
        with lab.Service() as service:
            for status, body, expected in [(302, b"{}", "redirect_refused"),
                                           (200, b"x" * (lab.MAX_RESPONSE_BYTES + 1), "response_body_budget_exceeded")]:
                fake = MagicMock()
                fake.getresponse.return_value.status = status
                fake.getresponse.return_value.read.return_value = body
                with patch.object(lab, "HTTPConnection", return_value=fake) as constructor:
                    with self.assertRaisesRegex(lab.LabError, expected):
                        lab.request(service, lab.valid_payload())
                self.assertEqual(constructor.call_count, 1)
                fake.close.assert_called_once()
            self.assertEqual(service.server.metrics.snapshot()["requests_seen"], 0)


class CLITests(unittest.TestCase):
    def test_default_and_plan_are_socket_and_file_free(self):
        for args in [[], ["--plan"]]:
            output = io.StringIO()
            with patch("socket.socket", side_effect=AssertionError("plan socket forbidden")), \
                 patch("builtins.open", side_effect=AssertionError("plan file forbidden")), \
                 patch.object(lab, "Service", side_effect=AssertionError("plan service forbidden")), \
                 contextlib.redirect_stdout(output):
                self.assertEqual(lab.main(args), 0)
            plan = json.loads(output.getvalue())
            self.assertEqual(plan["mode"], "PLAN")
            self.assertEqual(plan["network_requests"], 0)

    def test_unknown_arguments_are_explicit_and_do_not_echo_input(self):
        for args in [["--endpoint", "https://external.invalid/secret"], ["--plan", "--run"]]:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(lab.main(args), 1)
            self.assertEqual(json.loads(output.getvalue()), {"status": "ERROR", "code": "invalid_arguments"})
            self.assertNotIn("external", output.getvalue())

    def test_bind_failure_is_error_not_mock_pass(self):
        output = io.StringIO()
        with patch.object(lab, "LocalHTTPServer", side_effect=OSError("bind denied")), \
             contextlib.redirect_stdout(output):
            self.assertEqual(lab.main(["--run"]), 1)
        self.assertEqual(json.loads(output.getvalue())["code"], "loopback_environment_unavailable")

    def test_explicit_runtime_oracle_remains_enabled(self):
        with self.assertRaisesRegex(lab.LabError, "deliberate"):
            lab.require(False, "deliberate")


if __name__ == "__main__":
    unittest.main()
