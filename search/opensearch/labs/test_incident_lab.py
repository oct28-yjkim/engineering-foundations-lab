"""Offline HTTP contracts/oracles only: these do not prove OpenSearch behavior."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

import incident_lab as lab


SHARDS = {"total": 1, "successful": 1, "failed": 0}
IDENTITY = {"version": {"number": "3.9.0", "distribution": "opensearch"},
            "cluster_name": "engineering-foundations-opensearch-lab", "name": "opensearch-lab"}
RUN = "a" * 32


class Response:
    def __init__(self, data, status=200, *, headers=None, raw=None):
        self.status = status
        self.headers = {"Content-Type": "application/json"} if headers is None else headers
        self.raw = json.dumps(data).encode() if raw is None else raw
        self.read_limit = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        self.read_limit = limit
        return self.raw[:limit]


class Scripted:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FixtureServer:
    """Small fake solely for client stage ordering and expected-result checks."""

    def __init__(self):
        self.index = None
        self.mapping = None
        self.values = {}
        self.docs = {}
        self.visible = {}
        self.calls = []

    def open(self, request, timeout):
        url = urllib.parse.urlsplit(request.full_url)
        path, method = url.path, request.get_method()
        body = json.loads(request.data) if request.data and not path.endswith("/_bulk") else None
        self.calls.append((method, path, body))
        if path == "/":
            return Response(IDENTITY)
        if method == "PUT" and "/" not in path[1:]:
            if self.index is not None:
                return Response({}, 400)
            self.index = path[1:]
            self.mapping = body["mappings"]
            self.values = {"index." + key: str(value).lower() for key, value in body["settings"].items()}
            return Response({"index": self.index, "acknowledged": True, "shards_acknowledged": True})
        if path.endswith("/_mapping"):
            return Response({self.index: {"mappings": self.mapping}})
        if path.endswith("/_settings"):
            if method == "PUT":
                self.values.update({"index." + key: str(value).lower() for key, value in body["index"].items()})
                return Response({"acknowledged": True})
            return Response({self.index: {"settings": self.values}})
        if path.endswith("/_bulk"):
            lines = [json.loads(line) for line in request.data.decode().splitlines()]
            items = []
            for action, document in zip(lines[::2], lines[1::2]):
                doc_id = action["create"]["_id"]
                result = {"_index": self.index, "_id": doc_id}
                if doc_id in self.docs:
                    result.update(status=409, error={"type": "version_conflict_engine_exception"})
                elif type(document["value"]) is not int:
                    result.update(status=400, error={"type": "mapper_parsing_exception"})
                else:
                    self.docs[doc_id] = document
                    result.update(status=201, result="created", _shards=SHARDS)
                items.append({"create": result})
            return Response({"items": items, "errors": any(item["create"]["status"] >= 400 for item in items)})
        if path.endswith("/_refresh"):
            self.visible = copy.deepcopy(self.docs)
            return Response({"_shards": SHARDS})
        if "/_doc/" in path:
            doc_id = path.rsplit("/", 1)[1]
            result = {"_index": self.index, "_id": doc_id, "found": doc_id in self.docs}
            if doc_id in self.docs:
                result["_source"] = self.docs[doc_id]
            return Response(result, 200 if result["found"] else 404)
        if path.endswith("/_create/a2"):
            if self.values.get("index.blocks.read_only_allow_delete") == "true":
                return Response({"status": 429, "error": {"type": "cluster_block_exception"}}, 429)
            if "a2" in self.docs:
                return Response({"status": 409, "error": {"type": "version_conflict_engine_exception"}}, 409)
            self.docs["a2"] = body
            return Response({"_index": self.index, "_id": "a2", "result": "created", "_shards": SHARDS}, 201)
        if path.endswith("/_search"):
            if body.get("from", 0) + body["size"] > int(self.values.get("index.max_result_window", "10000")):
                return Response({"status": 400, "error": {"type": "search_phase_execution_exception",
                    "root_cause": [{"type": "illegal_argument_exception"}]}}, 400)
            ids = sorted(self.visible)
            after = body.get("search_after", [""])[0]
            hits = [{"_index": self.index, "_id": key, "_source": self.visible[key], "sort": [key]}
                    for key in ids if key > after][:body["size"]]
            return Response({"_shards": SHARDS, "timed_out": False,
                "hits": {"total": {"value": len(ids), "relation": "eq"}, "hits": hits}})
        if "/_stats/" in path:
            primaries = {"docs": {"count": len(self.visible), "deleted": 0}, "store": {"size_in_bytes": 100},
                "indexing": {"index_total": len(self.docs), "index_failed": 0, "index_time_in_millis": 1},
                "search": {"query_total": 2, "query_time_in_millis": 1},
                "refresh": {"total": 1, "total_time_in_millis": 1}}
            replica = int(self.values["index.number_of_replicas"])
            return Response({"_shards": {"total": 1 + replica, "successful": 1, "failed": 0},
                "indices": {self.index: {"primaries": primaries}}})
        if path.startswith("/_cluster/health/"):
            replica = int(self.values["index.number_of_replicas"])
            return Response({"timed_out": False, "number_of_nodes": 1, "indices": {self.index: {
                "status": "yellow" if replica else "green", "active_primary_shards": 1,
                "number_of_shards": 1, "number_of_replicas": replica, "unassigned_shards": replica}}})
        if path == "/_cluster/allocation/explain":
            return Response({"index": self.index, "shard": 0, "primary": False, "current_state": "unassigned",
                "can_allocate": "no", "node_allocation_decisions": [{"deciders": [
                    {"decider": "same_shard", "decision": "NO"}]}]})
        raise AssertionError("unimplemented fake route")


def client(scenario="refresh", step="observe"):
    result = lab.LocalClient(scenario, step, None if step == "prepare" else RUN)
    result.identity_verified = True
    return result


def ownership(result):
    return Response({result.index: {"mappings": {"_meta": {
        "lab": lab.MARKER, "scenario": result.scenario, "run_id": result.run_id}}}})


class StageTests(unittest.TestCase):
    def test_all_five_staged_flows(self):
        for scenario in lab.SCENARIOS:
            with self.subTest(scenario=scenario):
                server = FixtureServer()
                run_id = None
                for step, status in zip(lab.STEPS, ("PREPARED", "OBSERVED", "RECOVERED", "VERIFIED")):
                    current = lab.LocalClient(scenario, step, run_id)
                    current.opener = server
                    before = len(server.calls)
                    output = lab.run_step(current)
                    self.assertEqual(output["status"], status)
                    self.assertEqual(output["index"], server.index)
                    self.assertLess(current.requests, lab.MAX_REQUESTS)
                    self.assertFalse(output["cleanup_performed"])
                    self.assertTrue(output["index_retained"])
                    run_id = output["run_id"]
                    if step in ("observe", "verify"):
                        # Search and allocation explain are read-only POST endpoints.
                        for method, path, _ in server.calls[before:]:
                            self.assertTrue(method == "GET" or path.endswith("/_search") or
                                            path == "/_cluster/allocation/explain")
                    if step == "prepare":
                        self.assertNotEqual(output["status"], "VERIFIED")
                    if scenario == "pagination" and step == "verify":
                        self.assertEqual(output["evidence"]["ids"], [f"p{i:02d}" for i in range(20)])
                        self.assertEqual(server.values["index.max_result_window"], "5")
                self.assertEqual(len(server.docs), 20 if scenario == "pagination" else 2)

    def test_every_existing_index_mutation_has_immediate_ownership_read(self):
        for scenario in lab.SCENARIOS:
            server = FixtureServer()
            prepare = lab.LocalClient(scenario, "prepare")
            prepare.opener = server
            lab.run_step(prepare)
            recovery = lab.LocalClient(scenario, "recover", prepare.run_id)
            recovery.opener = server
            lab.run_step(recovery)
            for i, (method, path, _) in enumerate(server.calls):
                mutation = method == "PUT" or path.endswith("/_bulk") or path.endswith("/_refresh")
                creation = method == "PUT" and path == "/" + server.index
                if mutation and not creation:
                    self.assertEqual(server.calls[i - 1][:2], ("GET", "/" + server.index + "/_mapping"))

    def test_verify_before_recovery_fails(self):
        for scenario in ("refresh", "bulk-errors", "write-block", "allocation"):
            with self.subTest(scenario=scenario):
                server = FixtureServer()
                prepared = lab.LocalClient(scenario, "prepare")
                prepared.opener = server
                lab.run_step(prepared)
                verification = lab.LocalClient(scenario, "verify", prepared.run_id)
                verification.opener = server
                with self.assertRaises(lab.LabFailure):
                    lab.run_step(verification)

    def test_bulk_recover_retries_only_failed_document(self):
        server = FixtureServer()
        prepared = lab.LocalClient("bulk-errors", "prepare")
        prepared.opener = server
        lab.run_step(prepared)
        recovery = lab.LocalClient("bulk-errors", "recover", prepared.run_id)
        recovery.opener = server
        self.assertEqual(lab.run_step(recovery)["evidence"]["retried_ids"], ["a2"])
        with self.assertRaisesRegex(lab.LabFailure, "unexpected_http_status"):
            lab.run_step(recovery)

    def test_refresh_does_not_restore_automatic_refresh(self):
        server = FixtureServer()
        prepared = lab.LocalClient("refresh", "prepare")
        prepared.opener = server
        lab.run_step(prepared)
        recovery = lab.LocalClient("refresh", "recover", prepared.run_id)
        recovery.opener = server
        self.assertTrue(lab.run_step(recovery)["evidence"]["automatic_refresh_still_disabled"])
        self.assertEqual(server.values["index.refresh_interval"], "-1")


class SafetyTests(unittest.TestCase):
    def test_id_contract(self):
        for scenario, step, run_id in [("refresh", "prepare", RUN), ("refresh", "observe", None),
                ("refresh", "observe", "../foreign"), ("refresh", "observe", "A" * 32),
                ("unknown", "prepare", None), ("refresh", "destroy", RUN)]:
            with self.subTest(scenario=scenario, step=step, run_id=run_id), self.assertRaises(lab.LabFailure):
                lab.LocalClient(scenario, step, run_id)

    def test_unknown_route_and_tampered_index_do_not_send(self):
        current = client()
        current.opener = Scripted()
        for route in ("delete", "_all", "http://example.com", "../foreign"):
            with self.assertRaisesRegex(lab.LabFailure, "route_refused"):
                current.request(route)
        current.index = "foreign"
        with self.assertRaisesRegex(lab.LabFailure, "invalid_index"):
            current.request("root")
        self.assertEqual(current.opener.calls, [])

    def test_identity_required_before_nonroot(self):
        current = lab.LocalClient("refresh", "observe", RUN)
        current.opener = Scripted()
        with self.assertRaisesRegex(lab.LabFailure, "identity_not_verified"):
            current.request("mapping")
        self.assertEqual(current.opener.calls, [])

    def test_wrong_server_identity_stops_before_index(self):
        for field in ("name", "cluster_name", "version"):
            identity = copy.deepcopy(IDENTITY)
            identity[field] = "foreign"
            current = client(step="prepare")
            current.opener = Scripted(Response(identity))
            with self.assertRaises(lab.LabFailure):
                lab.run_step(current)
            self.assertEqual(len(current.opener.calls), 1)

    def test_foreign_metadata_blocks_every_mutation(self):
        cases = [("refresh", "refresh", None), ("allocation", "settings_update", {"index": {"number_of_replicas": 0}}),
                 ("bulk-errors", "bulk", lab.bulk_create([lab.DOCS[1]])),
                 ("write-block", "write_probe", lab.DOCS[1])]
        for scenario, route, body in cases:
            with self.subTest(scenario=scenario):
                current = client(scenario, "recover")
                current.opener = Scripted(Response({current.index: {"mappings": {"_meta": {"lab": "foreign"}}}}))
                with self.assertRaisesRegex(lab.LabFailure, "ownership_mismatch"):
                    current.request(route, body)
                self.assertEqual(len(current.opener.calls), 1)
                self.assertEqual(current.opener.calls[0][0].get_method(), "GET")

    def test_read_only_steps_refuse_mutation(self):
        for step in ("observe", "verify"):
            current = client(step=step)
            current.opener = Scripted()
            with self.assertRaisesRegex(lab.LabFailure, "read_only_step"):
                current.request("refresh")
            self.assertEqual(current.opener.calls, [])

    def test_foreign_bulk_target_and_unapproved_settings_refused(self):
        for scenario, resource, body in [
            ("bulk-errors", "bulk", b'{"create":{"_index":"foreign","_id":"a2"}}\n{"value":2}\n'),
            ("allocation", "settings_update", {"index": {"routing.allocation.enable": "none"}}),
            ("pagination", "settings_update", {"index": {"max_result_window": 1000000}}),
            ("refresh", "search", {"size": 10000000})]:
            current = client(scenario, "recover")
            current.opener = Scripted()
            with self.assertRaises(lab.LabFailure):
                current.request(resource, body)
            self.assertEqual(current.opener.calls, [])

    def test_allocation_request_is_explicitly_own_index(self):
        current = client("allocation")
        current.opener = Scripted(Response({}))
        current.request("allocation")
        request, timeout = current.opener.calls[0]
        self.assertEqual(json.loads(request.data), {"index": current.index, "shard": 0, "primary": False})
        self.assertEqual(timeout, 5)
        self.assertEqual(request.full_url, "http://127.0.0.1:19200/_cluster/allocation/explain")

    def test_proxy_and_redirect_handlers_are_installed(self):
        with patch.object(lab.urllib.request, "build_opener") as build:
            client()
            handlers = build.call_args.args
            self.assertEqual(handlers[0].proxies, {})
            self.assertIsInstance(handlers[1], lab.RejectRedirects)
        with self.assertRaisesRegex(lab.LabFailure, "redirect_refused"):
            lab.RejectRedirects().redirect_request(None, None, 302, None, None, "https://example.com")

    def test_request_budget(self):
        current = client()
        current.requests = lab.MAX_REQUESTS
        current.opener = Scripted()
        with self.assertRaisesRegex(lab.LabFailure, "request_budget_exceeded"):
            current.request("root")
        self.assertEqual(current.opener.calls, [])


class TransportTests(unittest.TestCase):
    def test_rejects_bad_status_encoding_type_length_and_json(self):
        cases = [(Response({}, 302), "redirect_refused"), (Response({}, 500), "unexpected_http_status"),
            (Response({}, headers={"Content-Encoding": "gzip"}), "response_encoding_refused"),
            (Response({}, headers={"Content-Type": "text/html"}), "response_not_json"),
            (Response({}, headers={"Content-Type": "application/json", "Content-Length": "99999999"}), "response_too_large"),
            (Response({}, raw=b"{"), "transport_or_json_failure"), (Response([]), "response_not_object"),
            (Response({}, raw=b"x" * (lab.MAX_RESPONSE_BYTES + 1)), "response_too_large")]
        for response, error in cases:
            with self.subTest(error=error):
                current = client()
                current.opener = Scripted(response)
                with self.assertRaisesRegex(lab.LabFailure, error):
                    current.request("root")

    def test_bounded_read(self):
        response = Response({})
        current = client()
        current.opener = Scripted(response)
        current.request("root")
        self.assertEqual(response.read_limit, lab.MAX_RESPONSE_BYTES + 1)

    def test_http_error_is_parsed_but_raw_body_not_printed(self):
        error = urllib.error.HTTPError("http://127.0.0.1:19200", 400, "SECRET", {"Content-Type": "application/json"},
                                      io.BytesIO(b'{"status":400,"error":{"type":"expected"}}'))
        current = client()
        current.opener = Scripted(error)
        self.assertEqual(current.request("root", expected=(400,))["status"], 400)

    def test_network_error_is_sanitized(self):
        current = client()
        current.opener = Scripted(urllib.error.URLError("SECRET CREDENTIAL"))
        with self.assertRaisesRegex(lab.LabFailure, "^transport_or_json_failure$"):
            current.request("root")


class OracleTests(unittest.TestCase):
    def test_wrong_sources_ids_sort_counts_timeouts_and_shards_fail(self):
        current = client()
        valid = {"_shards": SHARDS, "timed_out": False, "hits": {"total": {"value": 1, "relation": "eq"},
            "hits": [{"_index": current.index, "_id": "a1", "_source": {"doc_id": "a1", "value": 1}, "sort": ["a1"]}]}}
        lab.verify_rows(valid, current, [lab.DOCS[0]], 1)
        changes = [("_source", {"doc_id": "a1", "value": 999}), ("_id", "other"),
                   ("_index", "foreign"), ("sort", ["wrong"])]
        for key, value in changes:
            data = copy.deepcopy(valid)
            data["hits"]["hits"][0][key] = value
            with self.assertRaises(lab.LabFailure):
                lab.verify_rows(data, current, [lab.DOCS[0]], 1)
        for key, value in [("timed_out", True), ("_shards", {"total": 1, "successful": 0, "failed": 1}),
                           ("terminated_early", True)]:
            data = copy.deepcopy(valid)
            data[key] = value
            with self.assertRaises(lab.LabFailure):
                lab.verify_rows(data, current, [lab.DOCS[0]], 1)
        data = copy.deepcopy(valid)
        data["hits"]["total"]["relation"] = "gte"
        with self.assertRaises(lab.LabFailure):
            lab.verify_rows(data, current, [lab.DOCS[0]], 1)

    def test_expected_failure_must_be_real_correct_classification(self):
        for data in [{"status": 200, "error": {"type": "cluster_block_exception"}},
                     {"status": 429, "error": {"type": "es_rejected_execution_exception"}},
                     {"status": 429, "error": "secret raw message"}]:
            with self.assertRaises(lab.LabFailure):
                lab.verify_error(data, 429, "cluster_block_exception")
        with self.assertRaisesRegex(lab.LabFailure, "wrong_error_cause"):
            lab.verify_error({"status": 400, "error": {"type": "search_phase_execution_exception",
                "root_cause": [{"type": "different_failure"}]}}, 400,
                "search_phase_execution_exception", cause="illegal_argument_exception")

    def test_foreign_stats_and_failed_shards_rejected(self):
        for data in [{"_shards": SHARDS, "indices": {"foreign": {}}},
                     {"_shards": {"total": 2, "successful": 1, "failed": 1}, "indices": {}}]:
            current = client()
            current.opener = Scripted(Response(data))
            with self.assertRaises(lab.LabFailure):
                lab.stats(current)


class CliTests(unittest.TestCase):
    def test_list_and_help_do_not_construct_client(self):
        with patch.object(lab, "LocalClient") as constructor:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(lab.main(["--list"]), 0)
            self.assertFalse(json.loads(stdout.getvalue())["network_access"])
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
                lab.main(["--help"])
            self.assertEqual(caught.exception.code, 0)
            constructor.assert_not_called()

    def test_bad_cli_has_no_io(self):
        cases = [[], ["--scenario", "refresh", "--step", "prepare"],
            ["--list", "--run-local"], ["--run-local", "--scenario", "refresh", "--step", "observe"],
            ["--run-local", "--scenario", "refresh", "--step", "prepare", "--run-id", RUN],
            ["--run-local", "--scenario", "refresh", "--step", "verify", "--run-id", "../foreign"]]
        for args in cases:
            with self.subTest(args=args), patch.object(lab, "LocalClient") as constructor:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    lab.main(args)
                constructor.assert_not_called()

    def test_error_output_is_sanitized_and_retains_recovery_id(self):
        current = client(step="prepare")
        current.opener = Scripted(urllib.error.URLError("SECRET"))
        with patch.object(lab, "LocalClient", return_value=current):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                result = lab.main(["--run-local", "--scenario", "refresh", "--step", "prepare"])
        self.assertEqual(result, 1)
        text = stdout.getvalue()
        self.assertNotIn("SECRET", text)
        output = json.loads(text)
        self.assertEqual(output["status"], "ERROR")
        self.assertEqual(output["run_id"], current.run_id)
        self.assertFalse(output["cleanup_performed"])


if __name__ == "__main__":
    unittest.main()
