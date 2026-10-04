"""Socket-free contracts; no claim of real query performance or engine execution."""
import contextlib
import io
import json
import math
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

import observe_lab as lab
from test_engine_lab import FakeResponse, identity

INDEX = "efl-os-observe-" + "a" * 32
SHARDS = {"total": 1, "successful": 1, "failed": 0}


def search_result(rows=False, profile=False):
    # Independent fixture oracle for exactly 100 input documents.
    numbers = [3, 13, 23, 33, 43, 53, 63, 73, 83, 93]
    result = {"_shards": deepcopy(SHARDS), "timed_out": False, "took": 2,
              "hits": {"total": {"value": 10, "relation": "eq"}, "hits": []}}
    if rows:
        result["hits"]["hits"] = [{"_index": INDEX, "_id": f"d{n:06d}",
                                    "_source": {"doc_id": f"d{n:06d}", "group_no": 3, "value": n * 3}}
                                   for n in numbers]
    if profile:
        result["profile"] = {"shards": [{"searches": [{"query": [{"type": "BooleanQuery", "time_in_nanos": 123}]}]}]}
    return result


def node_stats():
    return {"_nodes": {"total": 1, "successful": 1, "failed": 0},
            "nodes": {"node-a": {"name": "opensearch-lab", "jvm": {"uptime_in_millis": 1234,
                                    "mem": {"heap_used_percent": 10}},
                                   "thread_pool": {"search": {"rejected": 0, "queue": 0}}}}}


def index_stats():
    return {"_shards": deepcopy(SHARDS), "indices": {INDEX: {"total": {"search": {"query_total": 3}}}}}


class WorkflowDouble:
    """Returns protocol fixtures, never opens a socket or runs a search engine."""
    def __init__(self):
        self.index, self.created, self.stage, self.requests = INDEX, False, "preflight", 0
        self.calls = []
        self.last_http_status = None

    def request(self, action, body=None):
        self.requests += 1
        self.calls.append((action, body))
        if action == "root":
            return identity()
        if action == "create":
            return {"acknowledged": True, "shards_acknowledged": True, "index": INDEX}
        if action == "bulk":
            return {"errors": False, "items": [{"create": {"_index": INDEX, "_id": f"d{n:06d}",
                    "status": 201, "_shards": deepcopy(SHARDS)}} for n in range(100)]}
        if action == "refresh":
            return {"_shards": deepcopy(SHARDS)}
        if action == "search":
            return search_result(rows=body.get("size", 0) > 0, profile=body.get("profile", False))
        if action == "nodes":
            return node_stats()
        if action == "stats":
            return index_stats()
        raise AssertionError("unexpected route")


def client(response=None):
    with patch.object(lab.uuid, "uuid4", return_value=Mock(hex="a" * 32)):
        value = lab.Client()
    value.opener = Mock()
    value.opener.open.return_value = response or FakeResponse({})
    return value


class OptionsTests(unittest.TestCase):
    def test_bounds(self):
        for docs, samples in ((100, 10), (10000, 100)):
            lab.valid_options(docs, samples)
        for docs, samples in ((99, 10), (10001, 10), (100, 9), (100, 101), (True, 10), (100, True)):
            with self.subTest(docs=docs, samples=samples), self.assertRaises(lab.LabFailure):
                lab.valid_options(docs, samples)

    def test_plan_and_default_never_create_client(self):
        for args in ([], ["--plan"], ["--plan", "--documents", "10000", "--samples", "100"]):
            with patch.object(lab, "Client") as factory, contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(lab.main(args), 0)
                self.assertEqual(json.loads(output.getvalue())["network_calls"], 0)
                factory.assert_not_called()

    def test_invalid_or_override_arguments_rejected_before_io(self):
        for args in (["--url", "http://example.invalid"], ["--documents", "0"], ["--samples", "101"],
                     ["--plan", "--run-local"], ["--index", "real"]):
            with patch.object(lab, "Client") as factory, contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                lab.main(args)
            factory.assert_not_called()

    def test_help_no_io(self):
        with patch.object(lab, "Client") as factory, contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
            lab.main(["--help"])
        self.assertEqual(error.exception.code, 0)
        factory.assert_not_called()


class EvidenceTests(unittest.TestCase):
    def test_query_definition_and_fixture(self):
        self.assertEqual(lab.fixture(13), {"doc_id": "d000013", "group_no": 3, "value": 39})
        self.assertEqual(lab.definition()["settings"]["number_of_replicas"], 0)
        self.assertEqual(lab.query("indexed")["query"]["bool"]["filter"], [{"term": {"group_no": 3}}])
        self.assertIn("script", lab.query("script")["query"]["bool"]["filter"][0])
        self.assertNotIn("profile", lab.query("script"))
        self.assertEqual(lab.query("indexed", rows=True)["sort"], [{"doc_id": "asc"}])

    def test_independent_rows(self):
        self.assertEqual(lab.check_search(search_result(True), INDEX, 100, rows=True), 2)
        for field in ("_id", "_index", "_source"):
            value = search_result(True)
            value["hits"]["hits"][0][field] = "wrong"
            with self.subTest(field=field), self.assertRaises(lab.LabFailure):
                lab.check_search(value, INDEX, 100, rows=True)

    def test_search_failures(self):
        changes = [("timed_out", True), ("terminated_early", True), ("took", True),
                   ("_shards", {"total": 1, "successful": 0, "failed": 1}),
                   ("hits", {"total": 10}), ("hits", {"total": {"value": 10, "relation": "gte"}})]
        for key, value in changes:
            response = search_result()
            response[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(lab.LabFailure):
                lab.check_search(response, INDEX, 100)

    def test_percentiles_and_rejected_samples(self):
        result = lab.latency_summary(list(range(1, 21)))
        self.assertEqual((result["count"], result["p50_ms"], result["p95_ms"]), (20, 10, 19))
        for values in ([], [math.nan], [math.inf], [-1], [True]):
            with self.subTest(values=values), self.assertRaises(lab.LabFailure):
                lab.latency_summary(values)

    def test_delta_reset_restart_and_missing(self):
        before = {"node_id": "a", "jvm_uptime_ms": 100, "counters": {"ok": 2, "reset": 20, "missing": None, "zero": 0}}
        after = {"node_id": "a", "jvm_uptime_ms": 200, "counters": {"ok": 5, "reset": 1, "missing": 0, "zero": 0}}
        delta = lab.counter_changes(before, after)
        self.assertEqual(delta["ok"]["delta"], 3)
        self.assertEqual(delta["zero"]["delta"], 0)
        self.assertEqual(delta["reset"]["state"], "reset_or_restart")
        self.assertEqual(delta["missing"]["state"], "unavailable")
        for key, value in (("node_id", "b"), ("jvm_uptime_ms", 50)):
            changed = dict(after, **{key: value})
            self.assertEqual(lab.counter_changes(before, changed)["ok"]["state"], "reset_or_restart")

    def test_snapshot_missing_is_not_zero(self):
        result = lab.snapshot(WorkflowDouble())
        self.assertEqual(result["gauges"]["thread_pool.search.queue"], 0)
        self.assertIsNone(result["gauges"]["process.cpu.percent"])
        self.assertEqual(result["counters"]["owned_index.search.query_total"], 3)

    def test_snapshot_scope_and_shape(self):
        for nodes in ({"_nodes": None}, {"_nodes": {"total": 2, "successful": 1, "failed": 0}, "nodes": {"a": {}}},
                      {"_nodes": {"total": 1, "successful": 1, "failed": 0}, "nodes": {"a": {"name": "other"}}}):
            double = WorkflowDouble()
            double.request = Mock(return_value=nodes)
            with self.subTest(nodes=nodes), self.assertRaises(lab.LabFailure):
                lab.snapshot(double)
        for indices in ({"foreign": {}}, {INDEX: None}, {INDEX: {"total": []}}):
            double = WorkflowDouble()
            double.request = Mock(side_effect=[node_stats(), {"_shards": SHARDS, "indices": indices}])
            with self.subTest(indices=indices), self.assertRaises(lab.LabFailure):
                lab.snapshot(double)

    def test_profile_shapes(self):
        self.assertEqual(lab.profile_summary(search_result(profile=True)), [{"type": "BooleanQuery", "time_in_nanos": 123}])
        for value in (None, {}, {"shards": []}, {"shards": [None]}, {"shards": [{"searches": [None]}]}):
            with self.subTest(value=value), self.assertRaises(lab.LabFailure):
                lab.profile_summary({"profile": value})


class TransportTests(unittest.TestCase):
    def test_no_proxy_or_redirect_and_uuid(self):
        with patch.object(lab.urllib.request, "build_opener") as build:
            result = lab.Client()
        self.assertRegex(result.index, r"^efl-os-observe-[0-9a-f]{32}$")
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], lab.RejectRedirects)

    def test_fixed_root_request(self):
        response = FakeResponse(identity())
        value = client(response)
        self.assertEqual(value.request("root"), identity())
        request = value.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:19200/")
        self.assertEqual(request.method, "GET")
        self.assertEqual(value.opener.open.call_args.kwargs["timeout"], 10)
        self.assertEqual(response.read_sizes, [lab.MAX_BYTES + 1])

    def test_closed_routes_and_ownership(self):
        for action in ("delete", "cluster_settings", "search", "nodes", "stats", "../_all"):
            value = client()
            with self.subTest(action=action), self.assertRaises(lab.LabFailure):
                value.request(action)
            value.opener.open.assert_not_called()
        value = client()
        value.created = True
        with self.assertRaises(lab.LabFailure):
            value.request("create", {})

    def test_invalid_index_get_body_and_budgets(self):
        for attr, setting, action, body in (("index", "_all", "root", None),
                                           ("requests", 300, "root", None),
                                           ("started", -1e30, "root", None),
                                           ("created", False, "root", {}),
                                           ("created", False, "create", b"a" * (1024 * 1024 + 1))):
            value = client()
            setattr(value, attr, setting)
            with self.subTest(attr=attr, action=action), self.assertRaises(lab.LabFailure):
                value.request(action, body)
            value.opener.open.assert_not_called()

    def test_http_and_response_errors(self):
        responses = [FakeResponse({}, status=429), FakeResponse({}, status=302), FakeResponse([]),
                     FakeResponse(raw=b"not-json"), FakeResponse({}, headers={"Content-Type": "text/html"}),
                     FakeResponse({}, headers={"Content-Type": "application/json", "Content-Encoding": "gzip"}),
                     FakeResponse({}, headers={"Content-Type": "application/json", "Content-Length": str(lab.MAX_BYTES + 1)}),
                     FakeResponse(raw=b" " * (lab.MAX_BYTES + 1))]
        for response in responses:
            with self.subTest(status=response.status, headers=response.headers), self.assertRaises(lab.LabFailure):
                client(response).request("root")

    def test_search_no_partial_results_or_request_cache(self):
        value = client(FakeResponse(search_result()))
        value.created = True
        value.request("search", lab.query("indexed"))
        request = value.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, f"http://127.0.0.1:19200/{INDEX}/_search?allow_partial_search_results=false&request_cache=false")


class WorkflowTests(unittest.TestCase):
    def test_full_protocol_workflow_and_separate_profile(self):
        value = WorkflowDouble()
        result = lab.run(value, 100, 10)
        self.assertEqual(result["status"], "MEASURED")
        self.assertTrue(result["index_retained"])
        self.assertEqual(result["requests"], 38)
        self.assertEqual(len(result["samples"]), 20)
        self.assertEqual(result["matching_documents"], 10)
        for variant in ("script", "indexed"):
            self.assertEqual(result["summary"][variant]["client"]["count"], 10)
        profiles = [i for i, (a, b) in enumerate(value.calls) if a == "search" and b.get("profile")]
        last_stats = max(i for i, (a, b) in enumerate(value.calls) if a == "stats")
        self.assertEqual(len(profiles), 2)
        self.assertTrue(all(i > last_stats for i in profiles))
        self.assertEqual(result["pressure_incident"], "not_reproduced_by_design")

    def test_wrong_identity_aborts_before_create(self):
        value = WorkflowDouble()
        value.request = Mock(return_value={})
        with self.assertRaises(lab.LabFailure):
            lab.run(value, 100, 10)
        self.assertEqual(value.request.call_args_list, [unittest.mock.call("root")])

    def test_cli_failure_is_not_partial_pass(self):
        value = WorkflowDouble()
        with patch.object(lab, "Client", return_value=value), patch.object(lab, "run", side_effect=lab.LabFailure("rejected")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(lab.main(["--run-local"]), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "ERROR")
        self.assertFalse(report["completed_comparison"])
        self.assertFalse(report["cleanup_performed"])


if __name__ == "__main__":
    unittest.main()
