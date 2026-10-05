"""Opt-in loopback model serving and bounded ML-system diagnostic experiments.

Python 3.10+ standard library only. Default/--plan prints a plan without binding
or connecting sockets. --run starts one disposable 127.0.0.1 HTTP server. No file
I/O, package installation, cloud/API credentials, downloads, or production load.
"""

from __future__ import annotations

import argparse
from contextlib import AbstractContextManager
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import socket
import threading
import time
from typing import NamedTuple, Sequence


LOOPBACK = "127.0.0.1"
MAX_BODY_BYTES = 2048
MAX_RESPONSE_BYTES = 4096
MAX_REQUESTS = 64
MAX_ROWS = 128
IO_TIMEOUT_SECONDS = 1.0
SESSION_BUDGET_SECONDS = 20.0
PREDICTION_TIME = 100  # Logical fixture time, not the machine clock.
MAX_FEATURE_AGE = 30
FEATURE_VERSION = "signals-v1"
PREPROCESSING_VERSION = "identity-v1"


class LabError(Exception):
    """Stable diagnostic code; never includes raw request features."""


class ContractError(LabError):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise LabError(code)


def is_number(value) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        # JSON integers can exceed binary64 even within the body-size budget.
        return False


class Artifact(NamedTuple):
    version: str
    weights: tuple[float, float]
    bias: float
    feature_version: str = FEATURE_VERSION
    preprocessing_version: str = PREPROCESSING_VERSION


# Hand-specified synthetic artefacts, NOT trained/pretrained model downloads.
BASELINE = Artifact("baseline-v1", (2.0, 0.0), 0.0)
CANDIDATE = Artifact("candidate-v2", (2.0, -4.0), 0.0)
ARTIFACTS = {BASELINE.version: BASELINE, CANDIDATE.version: CANDIDATE}


def probability(artifact: Artifact, features: Sequence[float]) -> float:
    require(len(artifact.weights) == 2 and all(is_number(w) for w in artifact.weights)
            and is_number(artifact.bias), "invalid_model_artifact")
    require(len(features) == 2 and all(is_number(x) for x in features), "invalid_model_input")
    logit = sum(weight * feature for weight, feature in zip(artifact.weights, features)) + artifact.bias
    require(is_number(logit), "nonfinite_logit")
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp_value = math.exp(logit)
    return exp_value / (1.0 + exp_value)


def valid_payload(features: Sequence[float] = (1.0, 0.0)) -> dict:
    return {"features": list(features), "feature_version": FEATURE_VERSION,
            "preprocessing_version": PREPROCESSING_VERSION, "feature_time": 95}


def validate_payload(payload, artifact: Artifact) -> list[float]:
    expected = {"features", "feature_version", "preprocessing_version", "feature_time"}
    if type(payload) is not dict or set(payload) != expected:
        raise ContractError(400, "schema_mismatch")
    if (type(payload["features"]) is not list
            or type(payload["feature_time"]) is not int
            or type(payload["feature_version"]) is not str
            or type(payload["preprocessing_version"]) is not str):
        raise ContractError(422, "type_mismatch")
    if len(payload["features"]) != 2:
        raise ContractError(422, "dimension_mismatch")
    if not all(is_number(x) for x in payload["features"]):
        raise ContractError(422, "type_mismatch")
    if not all(abs(x) <= 8 for x in payload["features"]):
        raise ContractError(422, "feature_range")
    if payload["feature_version"] != artifact.feature_version:
        raise ContractError(409, "feature_version_mismatch")
    if payload["preprocessing_version"] != artifact.preprocessing_version:
        raise ContractError(409, "preprocessing_version_mismatch")
    age = PREDICTION_TIME - payload["feature_time"]
    if age < 0:
        raise ContractError(409, "future_feature")
    if age > MAX_FEATURE_AGE:
        raise ContractError(409, "stale_feature")
    return list(payload["features"])


def _reject_constant(_value):
    raise ContractError(400, "invalid_json")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(400, "duplicate_json_key")
        result[key] = value
    return result


def parse_json(data: bytes):
    try:
        return json.loads(data.decode("utf-8"), parse_constant=_reject_constant,
                          object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ContractError(400, "invalid_json") from exc


class Controller:
    """In-process model pointer only; no deployment API or traffic splitting."""

    def __init__(self):
        self._artifact = BASELINE
        self._lock = threading.Lock()
        self.history = [BASELINE.version]

    def current(self) -> Artifact:
        with self._lock:
            return self._artifact

    def select(self, version: str) -> None:
        require(version in ARTIFACTS, "unknown_artifact")
        with self._lock:
            self._artifact = ARTIFACTS[version]
            self.history.append(version)


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = 0
        self.responses = 0
        self.failures = 0
        self.reasons: dict[str, int] = {}
        self.models: dict[str, int] = {}
        self.handler_seconds: list[float] = []

    def begin(self) -> int:
        with self.lock:
            self.requests += 1
            return self.requests

    def finish(self, status: int, reason: str, version: str, seconds: float) -> None:
        with self.lock:
            self.responses += 1
            self.failures += int(status >= 400)
            self.reasons[reason] = self.reasons.get(reason, 0) + 1
            self.models[version] = self.models.get(version, 0) + 1
            if len(self.handler_seconds) < MAX_REQUESTS:
                self.handler_seconds.append(seconds)

    def snapshot(self) -> dict:
        with self.lock:
            samples = sorted(self.handler_seconds)
            p95 = samples[math.ceil(0.95 * len(samples)) - 1] if samples else None
            return {"requests_seen": self.requests, "responses_prepared": self.responses,
                    "error_responses": self.failures,
                    "response_error_rate": self.failures / self.responses if self.responses else None,
                    "by_reason": dict(self.reasons), "by_model_version": dict(self.models),
                    "handler_latency_sample_count": len(samples), "handler_p95_seconds": p95}


class LocalHTTPServer(HTTPServer):
    allow_reuse_address = False
    request_queue_size = 4

    def __init__(self, controller: Controller, request_limit: int = MAX_REQUESTS):
        require(type(request_limit) is int and 1 <= request_limit <= MAX_REQUESTS, "invalid_request_limit")
        self.controller, self.metrics, self.request_limit = controller, Metrics(), request_limit
        super().__init__((LOOPBACK, 0), Handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(IO_TIMEOUT_SECONDS)
        return connection, address

    def handle_error(self, request, client_address):
        # No traceback, client address, headers, payload, or model features in logs.
        pass


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "SyntheticLab"
    sys_version = ""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self._handle(allow_post=False)

    def do_POST(self):
        self._handle(allow_post=True)

    def _handle(self, allow_post: bool) -> None:
        start = time.perf_counter()
        request_number = self.server.metrics.begin()
        artifact = self.server.controller.current()
        status, reason = 200, "ok"
        try:
            if request_number > self.server.request_limit:
                raise ContractError(429, "request_budget_exceeded")
            if not allow_post:
                raise ContractError(405, "method_not_allowed")
            if self.path != "/predict":
                raise ContractError(404, "route_not_found")
            if self.headers.get("Transfer-Encoding") is not None:
                raise ContractError(400, "transfer_encoding_not_supported")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                raise ContractError(400, "invalid_content_length")
            if len(lengths[0]) > 6 or int(lengths[0]) > MAX_BODY_BYTES:
                raise ContractError(413, "body_too_large")
            length = int(lengths[0])
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ContractError(415, "unsupported_media_type")
            body = self.rfile.read(length)
            if len(body) != length:
                raise ContractError(400, "incomplete_body")
            features = validate_payload(parse_json(body), artifact)
            value = probability(artifact, features)
            response = {"model_version": artifact.version, "feature_version": artifact.feature_version,
                        "preprocessing_version": artifact.preprocessing_version,
                        "probability": value, "prediction": int(value >= 0.5)}
        except ContractError as exc:
            status, reason = exc.status, exc.code
            response = {"error": reason, "model_version": artifact.version}
        except (TimeoutError, socket.timeout):
            status, reason = 408, "request_timeout"
            response = {"error": reason, "model_version": artifact.version}
        except Exception:
            status, reason = 500, "internal_error"
            response = {"error": reason, "model_version": artifact.version}
        # Latency is request-handler entry -> response construction, not wire/client latency.
        self.server.metrics.finish(status, reason, artifact.version, time.perf_counter() - start)
        try:
            encoded = json.dumps(response, allow_nan=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(encoded)
        except (OSError, ValueError):
            # A response prepared is not proof that the client received it.
            pass
        finally:
            self.close_connection = True


class Service(AbstractContextManager):
    def __init__(self, request_limit: int = MAX_REQUESTS):
        self.controller = Controller()
        self.request_limit = request_limit
        self.server: LocalHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.client_requests = 0
        self.active = False
        self.closed = False
        self.started_at = 0.0

    def __enter__(self):
        require(not self.active and not self.closed, "service_not_reusable")
        self.server = LocalHTTPServer(self.controller, self.request_limit)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, name="ml-systems-loopback")
        try:
            self.thread.start()
            self.active = True
            self.started_at = time.perf_counter()
            return self
        except Exception:
            self.server.server_close()
            self.closed = True
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if self.active and self.server is not None:
                self.server.shutdown()
        finally:
            if self.server is not None:
                self.server.server_close()
            if self.thread is not None:
                self.thread.join(timeout=IO_TIMEOUT_SECONDS + 2.0)
            self.active, self.closed = False, True
        require(self.thread is None or not self.thread.is_alive(), "server_thread_not_stopped")
        return False


def checked_destination(host, port) -> None:
    # No DNS resolution, localhost aliases, URLs, redirects, or arbitrary remote hosts.
    require(host == LOOPBACK and type(port) is int and 1 <= port <= 65535, "nonlocal_destination")


def request(service: Service, payload=None, *, raw: bytes | None = None,
            method: str = "POST", path: str = "/predict", content_type: str = "application/json") -> tuple[int, dict]:
    require(service.active and service.server is not None, "service_not_running")
    host, port = service.server.server_address
    checked_destination(host, port)
    require(service.client_requests < MAX_REQUESTS, "client_request_budget_exceeded")
    remaining = SESSION_BUDGET_SECONDS - (time.perf_counter() - service.started_at)
    require(remaining > 0, "client_session_budget_exceeded")
    require(method in ("POST", "GET") and path.startswith("/") and not path.startswith("//"),
            "invalid_local_request")
    try:
        body = json.dumps(payload, allow_nan=False).encode("utf-8") if raw is None else raw
    except (ValueError, TypeError, OverflowError) as exc:
        raise LabError("client_invalid_json") from exc
    require(type(body) is bytes and len(body) <= MAX_BODY_BYTES + 1, "client_body_budget_exceeded")
    connection = HTTPConnection(host, port, timeout=min(IO_TIMEOUT_SECONDS + 1, remaining))
    service.client_requests += 1
    try:
        connection.request(method, path, body=body, headers={"Content-Type": content_type})
        response = connection.getresponse()
        data = response.read(MAX_RESPONSE_BYTES + 1)
        require(len(data) <= MAX_RESPONSE_BYTES, "response_body_budget_exceeded")
        # http.client does not follow redirects and does not consume proxy environment variables.
        require(not 300 <= response.status < 400, "redirect_refused")
        parsed = parse_json(data)
        require(type(parsed) is dict, "invalid_response_schema")
        return response.status, parsed
    except (OSError, HTTPException) as exc:
        raise LabError("local_transport_error") from exc
    finally:
        connection.close()


def quality(rows: Sequence[dict], replies: Sequence[dict]) -> dict:
    require(0 < len(rows) == len(replies) <= MAX_ROWS, "invalid_evaluation_size")
    slices: dict[str, dict] = {}
    for row, reply in zip(rows, replies):
        require(type(row) is dict and type(reply) is dict
                and type(row.get("label")) is int and row["label"] in (0, 1)
                and type(row.get("slice")) is str and bool(row["slice"]), "invalid_evaluation_row")
        require(type(reply.get("prediction")) is int and reply["prediction"] in (0, 1), "invalid_prediction")
        correct = int(reply["prediction"] == row["label"])
        item = slices.setdefault(row["slice"], {"correct": 0, "total": 0})
        item["correct"] += correct
        item["total"] += 1
    for item in slices.values():
        item["accuracy"] = item["correct"] / item["total"]
    correct = sum(item["correct"] for item in slices.values())
    return {"correct": correct, "total": len(rows), "accuracy": correct / len(rows), "slices": slices}


def validate_quality_report(report: dict) -> None:
    require(type(report) is dict and type(report.get("slices")) is dict and bool(report["slices"]),
            "invalid_quality_report")
    for item in [report, *report["slices"].values()]:
        require(type(item) is dict and type(item.get("total")) is int and 0 < item["total"] <= MAX_ROWS
                and type(item.get("correct")) is int and 0 <= item["correct"] <= item["total"]
                and is_number(item.get("accuracy"))
                and abs(item["accuracy"] - item["correct"] / item["total"]) < 1e-12,
                "invalid_quality_report")
    require(all(type(name) is str and name for name in report["slices"])
            and sum(item["total"] for item in report["slices"].values()) == report["total"]
            and sum(item["correct"] for item in report["slices"].values()) == report["correct"],
            "invalid_quality_report")


def rollout_gate(baseline: dict, candidate: dict) -> dict:
    validate_quality_report(baseline)
    validate_quality_report(candidate)
    reasons = []
    if candidate["accuracy"] < 0.9:
        reasons.append("aggregate_accuracy_below_0.9")
    if set(baseline["slices"]) != set(candidate["slices"]):
        reasons.append("slice_coverage_mismatch")
    if baseline["total"] != candidate["total"]:
        reasons.append("sample_coverage_mismatch")
    for name, reference in baseline["slices"].items():
        observed = candidate["slices"].get(name)
        if observed is not None and observed["total"] != reference["total"]:
            reasons.append("slice_sample_mismatch:" + name)
        if observed is not None and observed["accuracy"] < reference["accuracy"] - 0.05:
            reasons.append("slice_regression:" + name)
    return {"promote": not reasons, "reasons": reasons,
            "policy": {"minimum_aggregate_accuracy": 0.9, "maximum_slice_accuracy_drop": 0.05}}


def evaluation_rows() -> list[dict]:
    return ([{"features": [float(x), 0.0], "label": int(x > 0), "slice": "core"}
             for x in [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]]
            + [{"features": [-1.0, 1.0], "label": 0, "slice": "edge"},
               {"features": [1.0, 1.0], "label": 1, "slice": "edge"}])


def evaluate_http(service: Service, rows: Sequence[dict], version: str) -> tuple[dict, list[dict]]:
    replies = []
    for row in rows:
        status, reply = request(service, valid_payload(row["features"]))
        require(status == 200 and reply.get("model_version") == version, "inference_or_version_failed")
        replies.append(reply)
    return quality(rows, replies), replies


def contract_experiments(service: Service) -> list[dict]:
    cases = []
    extra = valid_payload()
    extra["extra"] = "synthetic"
    cases.append((extra, 400, "schema_mismatch"))
    cases.append((valid_payload([True, 0.0]), 422, "type_mismatch"))
    cases.append((valid_payload([1.0]), 422, "dimension_mismatch"))
    for key, value, code in [("feature_time", 60, "stale_feature"),
                             ("feature_version", "signals-v0", "feature_version_mismatch"),
                             ("preprocessing_version", "scale-v0", "preprocessing_version_mismatch")]:
        payload = valid_payload()
        payload[key] = value
        cases.append((payload, 409, code))
    results = []
    for payload, expected_status, expected_code in cases:
        status, reply = request(service, payload)
        require(status == expected_status and reply.get("error") == expected_code, "contract_rejection_failed")
        recovered_status, recovered = request(service, valid_payload())
        require(recovered_status == 200 and recovered.get("model_version") == BASELINE.version
                and abs(recovered["probability"] - 0.8807970779778823) < 1e-12,
                "contract_recovery_failed")
        results.append({"reason": expected_code, "rejected_status": status,
                        "repaired_status": recovered_status, "recovery_probability": recovered["probability"]})
    return results


def point_in_time(records: Sequence[dict], entity: str, prediction_time: int):
    require(0 < len(records) <= MAX_ROWS and type(prediction_time) is int and type(entity) is str,
            "invalid_pit_input")
    eligible = []
    keys = set()
    for record in records:
        require(type(record) is dict and set(record) == {"entity", "event_time", "available_time", "value"}
                and type(record["entity"]) is str
                and type(record["event_time"]) is int and type(record["available_time"]) is int
                and record["available_time"] >= record["event_time"] and is_number(record["value"]),
                "invalid_feature_record")
        key = (record["entity"], record["event_time"], record["available_time"])
        require(key not in keys, "duplicate_feature_version")
        keys.add(key)
        if (record["entity"] == entity and record["event_time"] <= prediction_time
                and record["available_time"] <= prediction_time):
            eligible.append(record)
    return max(eligible, key=lambda r: (r["event_time"], r["available_time"])) if eligible else None


def delayed_label_metrics(predictions: Sequence[dict], labels: Sequence[dict], as_of: int) -> dict:
    require(0 < len(predictions) <= MAX_ROWS and len(labels) <= MAX_ROWS and type(as_of) is int,
            "invalid_label_input")
    require(all(type(row) is dict and set(row) == {"id", "label", "available_time"}
                and type(row["id"]) is str and type(row["label"]) is int and row["label"] in (0, 1)
                and type(row["available_time"]) is int for row in labels), "invalid_label")
    require(all(type(row) is dict and set(row) == {"id", "prediction"}
                and type(row["id"]) is str and type(row["prediction"]) is int and row["prediction"] in (0, 1)
                for row in predictions), "invalid_prediction")
    require(len({row["id"] for row in predictions}) == len(predictions), "duplicate_prediction_id")
    require(len({row["id"] for row in labels}) == len(labels), "duplicate_label_id")
    available = {row["id"]: row["label"] for row in labels if row["available_time"] <= as_of}
    evaluated = [row for row in predictions if row["id"] in available]
    correct = sum(row["prediction"] == available[row["id"]] for row in evaluated)
    return {"prediction_count": len(predictions), "labeled_count": len(evaluated),
            "label_coverage": len(evaluated) / len(predictions),
            "accuracy_on_available_labels": correct / len(evaluated) if evaluated else None}


def feature_and_label_experiment() -> dict:
    records = [{"entity": "a", "event_time": 90, "available_time": 92, "value": 1.0},
               {"entity": "a", "event_time": 95, "available_time": 105, "value": 99.0},
               {"entity": "a", "event_time": 110, "available_time": 110, "value": 5.0}]
    selected = point_in_time(records, "a", 100)
    leaked = max((r for r in records if r["event_time"] <= 100), key=lambda r: r["event_time"])
    require(selected["value"] == 1.0 and leaked["value"] == 99.0, "pit_oracle_failed")
    predictions = [{"id": key, "prediction": value} for key, value in zip("abcd", [1, 0, 1, 0])]
    labels = [{"id": key, "label": value, "available_time": timestamp}
              for key, value, timestamp in zip("abcd", [1, 0, 0, 1], [110, 120, 130, 200])]
    early = delayed_label_metrics(predictions, labels, 125)
    complete = delayed_label_metrics(predictions, labels, 200)
    valid_count = sum(is_number(value) for value in [1.0, 2.0, None, 3.0])
    require(early["label_coverage"] == 0.5 and early["accuracy_on_available_labels"] == 1.0
            and complete["accuracy_on_available_labels"] == 0.5 and valid_count == 3, "delayed_label_oracle_failed")
    return {"point_in_time_value": selected["value"], "event_time_only_leaked_value": leaked["value"],
            "feature_valid_fraction": valid_count / 4, "early_labels": early, "complete_labels": complete,
            "scope": "Pure PIT/availability fixture, not a feature store. Quality, label coverage, model quality and HTTP failures have different denominators."}


def drift_experiment() -> dict:
    before, shifted = [-2.0, -1.0, 1.0, 2.0], [-4.0, -3.0, 3.0, 4.0]
    expected = [0, 0, 1, 1]
    classify = lambda xs: [int(probability(BASELINE, [x, 0.0]) >= 0.5) for x in xs]
    before_predictions, after_predictions = classify(before), classify(shifted)
    accuracy = lambda p, y: sum(a == b for a, b in zip(p, y)) / len(y)
    before_accuracy, shifted_accuracy = accuracy(before_predictions, expected), accuracy(after_predictions, expected)
    flipped_accuracy = accuracy(before_predictions, [1, 1, 0, 0])
    before_magnitude = sum(abs(x) for x in before) / len(before)
    shifted_magnitude = sum(abs(x) for x in shifted) / len(shifted)
    require(before_accuracy == shifted_accuracy == 1.0 and flipped_accuracy == 0.0, "drift_oracle_failed")
    require(before_magnitude == 1.5 and shifted_magnitude == 3.5, "drift_magnitude_oracle_failed")
    return {"mean_absolute_feature_before": before_magnitude, "mean_absolute_feature_shifted": shifted_magnitude,
            "accuracy_before": before_accuracy, "accuracy_after_covariate_shift": shifted_accuracy,
            "identical_feature_marginal_after_label_rule_change": True,
            "accuracy_after_label_rule_change": flipped_accuracy,
            "scope": "Literal finite counterexamples, not a production drift detector, significance test or retraining trigger."}


def plan() -> dict:
    return {"mode": "PLAN", "sockets_started": 0, "network_requests": 0, "file_writes": 0,
            "opt_in": "--run", "bind": "127.0.0.1:ephemeral", "max_requests": MAX_REQUESTS,
            "max_request_body_bytes": MAX_BODY_BYTES, "session_budget_seconds": SESSION_BUDGET_SECONDS,
            "scenarios": ["normal inference and six contract failures/recovery", "slice rollout gate and rollback",
                          "point-in-time availability and delayed labels", "drift versus performance counterexamples"],
            "artifacts": "Two fixed synthetic logistic artefacts, not trained here or downloaded.",
            "limitations": "No production deployment, feature store, TLS/auth, durable metrics, workload benchmark or automatic retraining."}


def run() -> dict:
    rows = evaluation_rows()
    service = Service()
    with service:
        baseline_metrics, baseline_replies = evaluate_http(service, rows, BASELINE.version)
        require(baseline_metrics == {"correct": 12, "total": 12, "accuracy": 1.0,
                                     "slices": {"core": {"correct": 10, "total": 10, "accuracy": 1.0},
                                                "edge": {"correct": 2, "total": 2, "accuracy": 1.0}}},
                "baseline_quality_oracle_failed")
        contracts = contract_experiments(service)
        service.controller.select(CANDIDATE.version)
        candidate_metrics, _ = evaluate_http(service, rows, CANDIDATE.version)
        require(candidate_metrics == {"correct": 11, "total": 12, "accuracy": 11 / 12,
                                      "slices": {"core": {"correct": 10, "total": 10, "accuracy": 1.0},
                                                 "edge": {"correct": 1, "total": 2, "accuracy": 0.5}}},
                "candidate_quality_oracle_failed")
        gate = rollout_gate(baseline_metrics, candidate_metrics)
        require(candidate_metrics["accuracy"] == 11 / 12 and gate["reasons"] == ["slice_regression:edge"]
                and not gate["promote"], "candidate_gate_oracle_failed")
        service.controller.select(BASELINE.version)
        recovered_metrics, recovered_replies = evaluate_http(service, rows, BASELINE.version)
        require(recovered_replies == baseline_replies and recovered_metrics == baseline_metrics, "rollback_verification_failed")
        metrics = service.server.metrics.snapshot()
        require(metrics["requests_seen"] == metrics["responses_prepared"] == 48
                and metrics["error_responses"] == 6, "http_accounting_failed")
        http_result = {"actual_loopback_http_requests": service.client_requests, "contract_cases": contracts,
                       "metrics": metrics, "baseline_quality": baseline_metrics, "candidate_quality": candidate_metrics,
                       "rollout_gate": gate, "controller_history": list(service.controller.history),
                       "rollback_predictions_equal": recovered_replies == baseline_replies,
                       "scope": "Sequential synthetic HTTP service. Rollout/rollback changes one in-process pointer, not infrastructure."}
    require(service.closed and not service.thread.is_alive(), "cleanup_failed")
    return {"mode": "ACTUAL_LOOPBACK_HTTP", "status": "PASS", "server_closed": service.closed,
            "http": http_result, "feature_and_label": feature_and_label_experiment(), "drift": drift_experiment(),
            "file_writes": 0, "external_network_requests": 0,
            "latency_scope": "Handler response-construction p95 from 48 small requests; not client latency, SLO proof or throughput benchmark."}


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise LabError("invalid_arguments")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = SafeParser(description=__doc__)
        choice = parser.add_mutually_exclusive_group()
        choice.add_argument("--plan", action="store_true")
        choice.add_argument("--run", action="store_true")
        args = parser.parse_args(argv)
        output = run() if args.run else plan()
        print(json.dumps(output, ensure_ascii=False, allow_nan=False, sort_keys=True))
        return 0
    except LabError as exc:
        print(json.dumps({"status": "ERROR", "code": str(exc)}))
        return 1
    except (OSError, HTTPException):
        print(json.dumps({"status": "ERROR", "code": "loopback_environment_unavailable"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
