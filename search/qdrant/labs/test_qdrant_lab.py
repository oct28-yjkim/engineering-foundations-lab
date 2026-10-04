"""Socket-free client-contract tests; these are NOT Qdrant engine tests."""
import contextlib
import io
import json
import math
from pathlib import Path
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

import qdrant_lab as lab


class FakeResponse:
    def __init__(self, value=None, status=200, raw=None, content_type="application/json"):
        self.status = status
        self.raw = json.dumps(value).encode() if raw is None else raw
        self.content_type = content_type
        self.read_sizes = []

    def getheader(self, name):
        return self.content_type

    def read(self, size):
        self.read_sizes.append(size)
        return self.raw[:size]


class FakeClient(lab.LocalClient):
    """Literal canned ranking responses, not an implementation of Qdrant."""
    def __init__(self):
        super().__init__(lab.ENDPOINT)
        self.records = []
        self.points = {}
        self.indexes = {}

    def call(self, route, body=None, expected_status=200):
        self.calls += 1
        self.records.append((route, deepcopy(body), expected_status))
        if route == "identity":
            return {"version": lab.VERSION}
        if route == "exists":
            return {"exists": False}
        if route == "create":
            return True
        if route == "upsert":
            if expected_status == 400:
                return {"http_status": 400}
            for point in body["points"]:
                self.points[point["id"]] = deepcopy(point)
            return {"status": "completed", "operation_id": 1}
        if route == "count":
            return {"count": len(self.points)}
        if route == "retrieve":
            return [deepcopy(self.points[p]) for p in body["ids"] if p in self.points]
        if route == "delete_point":
            for point_id in body["points"]:
                self.points.pop(point_id, None)
            return {"status": "completed"}
        if route == "index":
            self.indexes[body["field_name"]] = {"data_type": body["field_schema"]}
            return {"status": "completed"}
        if route == "info":
            return {"payload_schema": deepcopy(self.indexes), "status": "green",
                    "optimizer_status": "ok", "points_count": len(self.points),
                    "indexed_vectors_count": 0, "segments_count": 2}
        if route == "metrics":
            return 'collections_total 1\nprocess_resident_memory_bytes 123\nprivate_metric{secret="redact"} 7\n'
        if route == "query":
            if expected_status == 400:
                return {"http_status": 400}
            if "prefetch" in body:
                ids, scores = [2, 1, 4, 3], [5 / 6, .75, 1 / 3, .25]
            elif body.get("using") == "lexical":
                ids, scores = [2, 4, 1, 3, 5, 6], [6, 5, 4, 3, 2, 1]
            elif body.get("filter") == lab.field_match("tenant", "alpha"):
                ids, scores = [1, 2, 4], [1, .8, 0]
            elif body.get("filter") == lab.field_match("rating", "5"):
                ids, scores = [], []
            elif body.get("filter") == lab.field_match("rating", 5):
                ids, scores = [1], [1]
            else:
                ids, scores = [1, 2, 3, 4, 5, 6], [1, .8, .6, 0, -.6, -1]
            return {"points": [{"id": p, "score": s} for p, s in zip(ids, scores)]}
        raise AssertionError("unexpected fake route")


class GuardedTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch("socket.create_connection", side_effect=AssertionError("real socket forbidden")).start()
        patch("socket.socket", side_effect=AssertionError("real socket forbidden")).start()

    def quiet(self, function, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = function(*args)
        return result, out.getvalue()


class ContractTests(GuardedTest):
    def test_default_plan_no_file_or_network(self):
        with patch("builtins.open", side_effect=AssertionError("file read forbidden")), \
             patch.object(lab, "LocalClient", side_effect=AssertionError("client forbidden")):
            code, output = self.quiet(lab.main, [])
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertEqual(result["mode"], "PLAN_ONLY")
        self.assertEqual(result["network_calls"], 0)

    def test_invalid_targets_refused_without_echo(self):
        for target in ("https://127.0.0.1:16333", "http://localhost:16333", lab.ENDPOINT + "/",
                       "http://user:secret@example.com", lab.ENDPOINT + "/collections/prod"):
            with self.subTest(target=target):
                code, output = self.quiet(lab.main, ["--run", "--base-url", target])
                self.assertEqual(code, 1)
                self.assertNotIn(target, output)
                self.assertNotIn("secret", output)

    def test_argument_conflicts_and_unknown_options(self):
        for args in (["--run", "--plan"], ["--token", "secret"], ["--scenario", "bad"], ["--base-url"]):
            code, output = self.quiet(lab.main, args)
            self.assertEqual(code, 1)
            self.assertNotIn("secret", output)

    def test_fixture_file_and_literal_oracles(self):
        fixture = json.loads(Path(__file__).with_name("fixture.json").read_text(encoding="utf-8"))
        self.assertEqual(fixture["points"], lab.POINTS)
        self.assertEqual(fixture["expected"]["rrf_top3_prefetch_ids"], lab.RRF_IDS)
        self.assertEqual([p["id"] for p in lab.POINTS], list(range(1, 7)))
        for point in lab.POINTS:
            self.assertAlmostEqual(sum(v * v for v in point["vector"]["dense"]), 1)
            self.assertIs(type(point["payload"]["rating"]), int)

    def test_rrf_oracle_independently_from_literal_ranks(self):
        scores = {}
        for ranking in ([1, 2, 3], [2, 4, 1]):
            for rank, point in enumerate(ranking):
                scores[point] = scores.get(point, 0) + 1 / (rank + 2)
        self.assertEqual(sorted(scores, key=scores.get, reverse=True), [2, 1, 4, 3])
        for observed, expected in zip([scores[p] for p in lab.RRF_IDS], lab.RRF_SCORES):
            self.assertAlmostEqual(observed, expected)

    def test_all_scenarios_mock_only_restore_fixture(self):
        original = deepcopy(lab.POINTS)
        for scenario in lab.SCENARIOS:
            client = FakeClient()
            _, output = self.quiet(lab.execute, client, scenario)
            self.assertEqual(client.points, {p["id"]: p for p in original})
            self.assertLessEqual(client.calls, lab.MAX_REQUESTS)
            self.assertNotIn("redact", output)
            self.assertTrue(client.created)
        self.assertEqual(lab.POINTS, original)

    def test_query_requests_exact_and_hybrid_prefetch(self):
        client = FakeClient()
        self.quiet(lab.execute, client, "all")
        queries = [body for route, body, _ in client.records if route == "query"]
        hybrid = next(body for body in queries if "prefetch" in body)
        self.assertEqual(hybrid["query"], {"fusion": "rrf"})
        self.assertEqual([p["using"] for p in hybrid["prefetch"]], ["dense", "lexical"])
        self.assertTrue(all(p["limit"] == 3 and p["params"]["exact"] for p in hybrid["prefetch"]))

    def test_owned_point_deletes_only_two_or_seven(self):
        client = FakeClient()
        self.quiet(lab.execute, client, "all")
        deleted = [body["points"] for route, body, _ in client.records if route == "delete_point"]
        self.assertEqual(deleted, [[2], [7]])
        self.assertTrue(all(method != "DELETE" for method, _ in client.routes.values()))

    def test_existing_collection_stops_before_create(self):
        client = lab.LocalClient(lab.ENDPOINT)
        with patch.object(client, "call", side_effect=[{"version": lab.VERSION}, {"exists": True}]) as call:
            with self.assertRaisesRegex(lab.LabFailure, "existing_collection_refused"):
                self.quiet(client.create)
        self.assertEqual(call.call_count, 2)
        self.assertFalse(client.created)
        self.assertFalse(client.create_attempted)

    def test_wrong_version_stops_before_exists(self):
        client = lab.LocalClient(lab.ENDPOINT)
        with patch.object(client, "call", return_value={"version": "1.0.0"}) as call:
            with self.assertRaises(lab.LabFailure):
                self.quiet(client.create)
        self.assertEqual(call.call_count, 1)

    def test_bad_dimension_and_name_are_expected_400(self):
        client = FakeClient()
        self.quiet(lab.execute, client, "incidents")
        errors = [(route, body) for route, body, status in client.records if status == 400]
        self.assertEqual([route for route, _ in errors], ["upsert", "query"])
        self.assertEqual(len(errors[0][1]["points"][0]["vector"]["dense"]), 3)
        self.assertEqual(errors[1][1]["using"], "missing_dense")

    def test_oracle_fails_not_assert(self):
        with self.assertRaises(lab.LabFailure):
            self.quiet(lab.check, "deliberate", 1, 2)
        with self.assertRaises(lab.LabFailure):
            lab.completed({"status": "acknowledged"})

    def test_nan_score_and_boolean_count_rejected(self):
        client = Mock()
        client.call.return_value = {"points": [{"id": 1, "score": math.nan}]}
        with self.assertRaises(lab.LabFailure):
            lab.query(client, {}, [1], [1], "nan")
        client.call.return_value = {"count": True}
        with self.assertRaises(lab.LabFailure):
            lab.exact_count(client, 1, "bool")

    def test_final_cli_reports_retained_mock_collection(self):
        with patch.object(lab, "LocalClient", return_value=FakeClient()):
            code, output = self.quiet(lab.main, ["--run", "--scenario", "all"])
        self.assertEqual(code, 0)
        record = json.loads(output.splitlines()[-1])
        self.assertEqual(record["mode"], "LOCAL_ENGINE_PASS")
        self.assertTrue(record["retained"])
        self.assertFalse(record["performance_ha_production_security_verified"])


class TransportTests(GuardedTest):
    def run_response(self, response, route="identity", body=None, status=200):
        connection = Mock()
        connection.getresponse.return_value = response
        client = lab.LocalClient(lab.ENDPOINT)
        client.created = True
        with patch.object(lab.http.client, "HTTPConnection", return_value=connection) as constructor:
            result = client.call(route, body, status)
        self.assertEqual(constructor.call_args.args, ("127.0.0.1", 16333))
        self.assertLessEqual(constructor.call_args.kwargs["timeout"], 10)
        connection.close.assert_called_once()
        self.assertEqual(response.read_sizes, [lab.MAX_RESPONSE_BYTES + 1])
        return result, connection

    def test_fixed_host_no_proxy_headers(self):
        with patch.dict("os.environ", {"http_proxy": "http://secret@example.com:99"}):
            result, connection = self.run_response(FakeResponse({"version": lab.VERSION}))
        self.assertEqual(result["version"], lab.VERSION)
        self.assertEqual(connection.request.call_args.args[:2], ("GET", "/"))
        self.assertNotIn("Authorization", connection.request.call_args.kwargs["headers"])

    def test_redirects_and_unexpected_errors_rejected_no_retry(self):
        for status in (301, 302, 307, 308, 400, 401, 409, 429, 500):
            connection = Mock()
            connection.getresponse.return_value = FakeResponse({}, status=status)
            with patch.object(lab.http.client, "HTTPConnection", return_value=connection):
                with self.assertRaisesRegex(lab.LabFailure, "unexpected_http_status"):
                    lab.LocalClient(lab.ENDPOINT).call("identity")
            connection.request.assert_called_once()
            connection.close.assert_called_once()

    def test_expected_400_body_not_echoed_or_decoded(self):
        result, _ = self.run_response(FakeResponse(status=400, raw=b'secret'), "query", {}, 400)
        self.assertEqual(result, {"http_status": 400})

    def test_response_and_request_bounds(self):
        with self.assertRaisesRegex(lab.LabFailure, "response_too_large"):
            self.run_response(FakeResponse(raw=b'x' * (lab.MAX_RESPONSE_BYTES + 1)))
        client = lab.LocalClient(lab.ENDPOINT)
        client.created = True
        with self.assertRaisesRegex(lab.LabFailure, "request_too_large"):
            client.call("query", {"large": "x" * lab.MAX_REQUEST_BYTES})

    def test_bad_json_content_type_status_shape(self):
        for response in (FakeResponse(raw=b'not json'), FakeResponse([], content_type="text/html"),
                         FakeResponse([]), FakeResponse({"result": True, "status": "error"})):
            with self.assertRaises(lab.LabFailure):
                self.run_response(response, "info")

    def test_route_ownership_and_budgets(self):
        client = lab.LocalClient(lab.ENDPOINT)
        for route in ("/collections/prod", "delete_collection", "query"):
            with self.assertRaises(lab.LabFailure):
                client.call(route)
        client.calls = lab.MAX_REQUESTS
        with self.assertRaisesRegex(lab.LabFailure, "request_budget"):
            client.call("identity")
        client.calls = 0
        client.started -= lab.RUN_DEADLINE + 1
        with self.assertRaisesRegex(lab.LabFailure, "deadline"):
            client.call("identity")

    def test_transport_failure_retains_attempted_name_and_redacts(self):
        connection = Mock()
        connection.request.side_effect = OSError("secret transport details")
        with patch.object(lab.http.client, "HTTPConnection", return_value=connection):
            code, output = self.quiet(lab.main, ["--run"])
        self.assertEqual(code, 1)
        self.assertNotIn("secret", output)
        record = json.loads(output.splitlines()[-1])
        self.assertRegex(record["collection"], lab.NAME_PATTERN)
        self.assertEqual(record["code"], "transport_or_decode_failure_no_retry")
        connection.request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
