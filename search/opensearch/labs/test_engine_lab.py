"""Socket-free contracts only: these tests do not validate OpenSearch itself."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
import urllib.error
from copy import deepcopy
from unittest.mock import Mock, patch

import engine_lab as lab


SHARDS = {"total": 1, "successful": 1, "failed": 0}
INDEX = "efl-os-" + "a" * 32


class FakeResponse:
    def __init__(self, data=None, *, raw=None, status=200, headers=None):
        self.raw = raw if raw is not None else json.dumps(data).encode("utf-8")
        self.status = status
        self.headers = headers if headers is not None else {"Content-Type": "application/json; charset=UTF-8"}
        self.read_sizes = []
        self.closed = False

    def read(self, size):
        self.read_sizes.append(size)
        return self.raw[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


def identity():
    return {"name": lab.NODE, "cluster_name": lab.CLUSTER,
            "version": {"number": lab.VERSION, "distribution": "opensearch"}}


def hits(ids, *, updated=False):
    source = {document["doc_id"]: deepcopy(document) for document in lab.FIXTURES}
    if updated:
        source["a1"]["price"] = 11
    return {
        "_shards": deepcopy(SHARDS), "timed_out": False,
        "hits": {"total": {"value": len(ids), "relation": "eq"},
                 "hits": [{"_index": INDEX, "_id": doc_id, "_source": source[doc_id]} for doc_id in ids]},
    }


def aggregate(*, updated=False):
    response = hits(["a1", "a2", "a3", "b1", "b2", "b3"], updated=updated)
    response["aggregations"] = {"tenants": {
        "doc_count_error_upper_bound": 0, "sum_other_doc_count": 0,
        "buckets": [{"key": "alpha", "doc_count": 3}, {"key": "beta", "doc_count": 3}],
    }}
    return response


def bulk_ok():
    return {"errors": False, "items": [{"create": {
        "_index": INDEX, "_id": row["doc_id"], "status": 201, "result": "created", "_shards": deepcopy(SHARDS),
    }} for row in lab.FIXTURES]}


def bulk_negative():
    return {"errors": True, "items": [
        {"create": {"_index": INDEX, "_id": "a1", "status": 409,
                    "error": {"type": "version_conflict_engine_exception"}}},
        {"create": {"_index": INDEX, "_id": "invalid", "status": 400,
                    "error": {"type": "mapper_parsing_exception"}}},
    ]}


def responses_for_success():
    realtime = {"found": True, "_index": INDEX, "_id": "a1", "_source": deepcopy(lab.FIXTURES[0]),
                "_seq_no": 0, "_primary_term": 1}
    updated = {"_index": INDEX, "_id": "a1", "result": "updated", "_seq_no": 6,
               "_primary_term": 1, "_shards": deepcopy(SHARDS)}
    first = [identity(), {"acknowledged": True, "shards_acknowledged": True, "index": INDEX},
             bulk_ok(), hits([]), realtime, {"_shards": deepcopy(SHARDS)},
             hits(["a1", "a2", "a3", "b1", "b2", "b3"])]
    # Independent literals: do not generate fixture responses from query_cases().
    queries = [hits(["a1", "a2", "a3"]), hits(["a1", "b1"]), hits(["a1", "b1", "b3"]),
               hits(["a1", "b1"]), hits(["a1", "a2", "b1"]), hits(["b2", "a1", "b1", "a2", "b3", "a3"])]
    responses = [FakeResponse(value) for value in first + queries + [aggregate(), updated]]
    responses.append(FakeResponse({"error": {"type": "version_conflict_engine_exception"}, "status": 409}, status=409))
    responses.extend(FakeResponse(value) for value in [bulk_negative(), {"_shards": deepcopy(SHARDS)}, aggregate(updated=True)])
    return responses


def make_client(responses=None):
    with patch.object(lab.uuid, "uuid4", return_value=Mock(hex="a" * 32)):
        client = lab.LocalClient()
    client.opener = Mock()
    if responses is not None:
        client.opener.open.side_effect = responses
    return client


class LocalTransportTests(unittest.TestCase):
    def test_uuid_index_and_closed_opener_setup(self):
        with patch.object(lab.urllib.request, "build_opener") as build:
            client = lab.LocalClient()
        self.assertRegex(client.index, r"^efl-os-[0-9a-f]{32}$")
        proxy_handler, redirect_handler = build.call_args.args
        self.assertEqual(proxy_handler.proxies, {})
        self.assertIsInstance(redirect_handler, lab.RejectRedirects)

    def test_get_root_only_fixed_loopback_without_credentials(self):
        response = FakeResponse(identity())
        client = make_client([response])
        self.assertEqual(client.request("root"), identity())
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:19200/")
        self.assertEqual(request.method, "GET")
        self.assertIsNone(request.data)
        self.assertEqual(client.opener.open.call_args.kwargs, {"timeout": 10})
        self.assertNotIn("Authorization", dict(request.header_items()))
        self.assertEqual(response.read_sizes, [lab.MAX_RESPONSE_BYTES + 1])
        self.assertTrue(response.closed)

    def test_help_has_no_client_or_http(self):
        with patch.object(lab, "LocalClient") as client, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                lab.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        client.assert_not_called()

    def test_missing_opt_in_has_no_http(self):
        with patch.object(lab, "LocalClient") as client, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                lab.main([])
        self.assertEqual(raised.exception.code, 2)
        client.assert_not_called()

    def test_arbitrary_url_cli_is_not_supported(self):
        with patch.object(lab, "LocalClient") as client, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                lab.main(["--run-local", "--url", "http://example.com"])
        client.assert_not_called()

    def test_route_scope_rejects_user_paths(self):
        client = make_client()
        for route in ("/_all", "../other", "http://example.com", "delete", "_cluster/settings"):
            with self.subTest(route=route), self.assertRaisesRegex(lab.LabFailure, "route_refused"):
                client.request(route)
        client.opener.open.assert_not_called()

    def test_malformed_index_refused_before_dispatch(self):
        client = make_client()
        for index in ("_all", "*", "efl-os-" + "a" * 32 + "/../old", INDEX + "\n"):
            client.index = index
            with self.subTest(index=index), self.assertRaisesRegex(lab.LabFailure, "invalid_generated_index"):
                client.request("index")
        client.opener.open.assert_not_called()

    def test_index_scope_requires_confirmed_creation(self):
        client = make_client()
        with self.assertRaisesRegex(lab.LabFailure, "index_not_created"):
            client.request("bulk", b"{}\n")
        client.opener.open.assert_not_called()

    def test_request_budget_fails_before_dispatch(self):
        client = make_client()
        client.requests = lab.MAX_REQUESTS
        with self.assertRaisesRegex(lab.LabFailure, "request_budget_exceeded"):
            client.request("root")
        client.opener.open.assert_not_called()

    def test_redirect_handler_never_follows_location(self):
        with self.assertRaisesRegex(lab.LabFailure, "redirect_refused"):
            lab.RejectRedirects().redirect_request(None, None, 302, "redirect", {}, "https://example.com")

    def test_redirect_status_refused_without_read(self):
        response = FakeResponse({}, status=307)
        client = make_client([response])
        with self.assertRaisesRegex(lab.LabFailure, "redirect_refused"):
            client.request("root")
        self.assertEqual(response.read_sizes, [])

    def test_unexpected_status_does_not_expose_body(self):
        response = FakeResponse({"password": "secret"}, status=401)
        client = make_client([response])
        with self.assertRaisesRegex(lab.LabFailure, "^unexpected_http_status$"):
            client.request("root")
        self.assertEqual(response.read_sizes, [])

    def test_http_error_409_is_parsed_when_expected(self):
        raw = json.dumps({"error": {"type": "version_conflict_engine_exception"}, "status": 409}).encode()
        error = urllib.error.HTTPError(lab.ENDPOINT, 409, "conflict", {"Content-Type": "application/json"}, io.BytesIO(raw))
        client = make_client([error])
        client.index_created = True
        response = client.request("update_a1", {"doc": {"price": 11}}, seq_no=0, primary_term=1, expected_status=409)
        self.assertEqual(response["status"], 409)
        self.assertTrue(error.fp.closed)

    def test_oversize_content_length_refused_without_read(self):
        response = FakeResponse({}, headers={"Content-Type": "application/json", "Content-Length": str(lab.MAX_RESPONSE_BYTES + 1)})
        client = make_client([response])
        with self.assertRaisesRegex(lab.LabFailure, "response_too_large"):
            client.request("root")
        self.assertEqual(response.read_sizes, [])

    def test_oversize_body_refused_even_without_length(self):
        response = FakeResponse(raw=b"x" * (lab.MAX_RESPONSE_BYTES + 1))
        client = make_client([response])
        with self.assertRaisesRegex(lab.LabFailure, "response_too_large"):
            client.request("root")

    def test_non_json_and_compressed_responses_refused(self):
        cases = [({"Content-Type": "text/html"}, "response_not_json"),
                 ({"Content-Type": "application/json", "Content-Encoding": "gzip"}, "response_encoding_refused")]
        for headers, code in cases:
            with self.subTest(code=code):
                client = make_client([FakeResponse({}, headers=headers)])
                with self.assertRaisesRegex(lab.LabFailure, code):
                    client.request("root")

    def test_json_array_and_malformed_json_refused(self):
        for raw, code in ((b"[]", "response_not_object"), (b"not json", "transport_or_json_failure"),
                          (b"\xff", "transport_or_json_failure")):
            with self.subTest(raw=raw):
                client = make_client([FakeResponse(raw=raw)])
                with self.assertRaisesRegex(lab.LabFailure, code):
                    client.request("root")

    def test_connection_failure_is_redacted(self):
        client = make_client([urllib.error.URLError("private detail")])
        with self.assertRaisesRegex(lab.LabFailure, "^transport_or_json_failure$"):
            client.request("root")

    def test_incomplete_http_response_is_redacted(self):
        client = make_client([lab.http.client.IncompleteRead(b"private partial body", 100)])
        with self.assertRaisesRegex(lab.LabFailure, "^transport_or_json_failure$"):
            client.request("root")

    def test_occ_tokens_are_non_boolean_nonnegative_integers(self):
        client = make_client()
        client.index_created = True
        for seq_no, term in ((-1, 1), (0, 0), (True, 1), (0, False), ("0", 1), (0, None)):
            with self.subTest(seq_no=seq_no, term=term), self.assertRaisesRegex(lab.LabFailure, "invalid_occ_token"):
                client.request("update_a1", {}, seq_no=seq_no, primary_term=term)
        client.opener.open.assert_not_called()

    def test_get_body_and_unexpected_tokens_refused(self):
        client = make_client()
        with self.assertRaisesRegex(lab.LabFailure, "get_body_refused"):
            client.request("root", {})
        with self.assertRaisesRegex(lab.LabFailure, "unexpected_occ_token"):
            client.request("root", seq_no=0)
        client.opener.open.assert_not_called()


class OracleTests(unittest.TestCase):
    def test_identity_requires_all_pinned_fields(self):
        lab.verify_identity(identity())
        for path in ("number", "distribution", "cluster_name", "name"):
            modified = identity()
            if path in ("number", "distribution"):
                modified["version"][path] = "wrong"
            else:
                modified[path] = "wrong"
            with self.subTest(path=path), self.assertRaises(lab.LabFailure):
                lab.verify_identity(modified)

    def test_mapping_disables_refresh_and_implicit_fields(self):
        definition = lab.index_definition()
        self.assertEqual(definition["settings"], {"number_of_shards": 1, "number_of_replicas": 0, "refresh_interval": "-1"})
        self.assertEqual(definition["mappings"]["dynamic"], "strict")
        self.assertEqual(definition["mappings"]["properties"]["price"], {"type": "integer", "coerce": False})
        self.assertEqual(definition["mappings"]["properties"]["title"]["analyzer"], "standard")

    def test_bulk_only_create_and_no_index_override(self):
        payload = lab.bulk_create(lab.FIXTURES)
        self.assertTrue(payload.endswith(b"\n"))
        lines = [json.loads(line) for line in payload.splitlines()]
        self.assertEqual(len(lines), 12)
        self.assertEqual([lines[i] for i in range(0, 12, 2)],
                         [{"create": {"_id": doc_id}} for doc_id in ("a1", "a2", "a3", "b1", "b2", "b3")])
        self.assertEqual([lines[i] for i in range(1, 12, 2)], list(lab.FIXTURES))

    def test_bulk_rejects_unsafe_document_id(self):
        for doc_id in ("../old", "a\ncreate", 123, ""):
            with self.subTest(doc_id=doc_id), self.assertRaises(lab.LabFailure):
                lab.bulk_create([{"doc_id": doc_id}])

    def test_bulk_http_200_does_not_imply_item_success(self):
        response = bulk_ok()
        response["items"][2]["create"]["status"] = 429
        with self.assertRaisesRegex(lab.LabFailure, "bulk_status_mismatch"):
            lab.verify_bulk(response, INDEX, [(row["doc_id"], 201, None) for row in lab.FIXTURES])

    def test_bulk_negative_expected_item_contract(self):
        lab.verify_bulk(bulk_negative(), INDEX,
                        [("a1", 409, "version_conflict_engine_exception"), ("invalid", 400, "mapper_parsing_exception")])
        response = bulk_negative()
        response["items"][1]["create"]["error"]["type"] = "different_error"
        with self.assertRaisesRegex(lab.LabFailure, "bulk_error_mismatch"):
            lab.verify_bulk(response, INDEX,
                            [("a1", 409, "version_conflict_engine_exception"), ("invalid", 400, "mapper_parsing_exception")])

    def test_bulk_missing_items_and_error_flag_refused(self):
        expected = [(row["doc_id"], 201, None) for row in lab.FIXTURES]
        short = bulk_ok()
        short["items"].pop()
        wrong_flag = bulk_ok()
        wrong_flag["errors"] = True
        for response in (short, wrong_flag):
            with self.subTest(response=response), self.assertRaises(lab.LabFailure):
                lab.verify_bulk(response, INDEX, expected)

    def test_search_exact_ids_order_and_count(self):
        self.assertEqual(len(lab.verify_search(hits(["a1", "b1"]), INDEX, ["a1", "b1"])), 2)
        for ids in (["b1", "a1"], ["a1", "a1"], ["a1"], ["a1", "b1", "b3"]):
            with self.subTest(ids=ids), self.assertRaises(lab.LabFailure):
                lab.verify_search(hits(ids), INDEX, ["a1", "b1"])

    def test_search_inexact_total_is_failure(self):
        response = hits(["a1"])
        response["hits"]["total"]["relation"] = "gte"
        with self.assertRaisesRegex(lab.LabFailure, "inexact_total"):
            lab.verify_search(response, INDEX, ["a1"])

    def test_search_timeout_early_termination_and_shard_failures(self):
        modifications = [("timed_out", True), ("terminated_early", True),
                         ("_shards", {"total": 2, "successful": 1, "failed": 1})]
        for key, value in modifications:
            response = hits(["a1"])
            response[key] = value
            with self.subTest(key=key), self.assertRaises(lab.LabFailure):
                lab.verify_search(response, INDEX, ["a1"])

    def test_search_foreign_index_is_failure(self):
        response = hits(["a1"])
        response["hits"]["hits"][0]["_index"] = "not-our-index"
        with self.assertRaisesRegex(lab.LabFailure, "unexpected_hit_index"):
            lab.verify_search(response, INDEX, ["a1"])

    def test_incomplete_or_missing_shard_metadata_fails(self):
        for shards in (None, {}, {"total": 1, "successful": 0, "failed": 0},
                       {"total": 0, "successful": 0, "failed": 0}, {"total": 1, "successful": 1, "failed": False},
                       {"total": 1, "successful": True, "failed": 0}):
            with self.subTest(shards=shards), self.assertRaises(lab.LabFailure):
                lab.verify_shards({"_shards": shards})

    def test_query_cases_have_literal_independent_oracles(self):
        cases = lab.query_cases()
        self.assertEqual([case[0] for case in cases], ["keyword", "raw_keyword", "match_and", "phrase", "range", "sort"])
        self.assertEqual(cases[2][2], ["a1", "b1", "b3"])
        self.assertEqual(cases[3][2], ["a1", "b1"])
        self.assertEqual(cases[-1][2], ["b2", "a1", "b1", "a2", "b3", "a3"])
        for _, body, _ in cases:
            self.assertTrue(body["track_total_hits"])
            self.assertEqual(body["size"], 10)
            self.assertEqual(body["timeout"], "5s")

    def test_aggregation_rejects_truncation_and_wrong_counts(self):
        lab.verify_aggregation(aggregate(), INDEX)
        for key in ("doc_count_error_upper_bound", "sum_other_doc_count"):
            response = aggregate()
            response["aggregations"]["tenants"][key] = 1
            with self.subTest(key=key), self.assertRaisesRegex(lab.LabFailure, "incomplete_aggregation"):
                lab.verify_aggregation(response, INDEX)
        response = aggregate()
        response["aggregations"]["tenants"]["buckets"][0]["doc_count"] = 2
        with self.assertRaisesRegex(lab.LabFailure, "wrong_aggregation_buckets"):
            lab.verify_aggregation(response, INDEX)


class WorkflowTests(unittest.TestCase):
    def test_complete_mock_workflow_has_no_cleanup_and_exact_scoped_requests(self):
        client = make_client(responses_for_success())
        result = lab.run_lab(client)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(client.requests, 19)
        self.assertEqual(client.stage, "complete")
        requests = [call.args[0] for call in client.opener.open.call_args_list]
        self.assertEqual([request.method for request in requests].count("PUT"), 1)
        self.assertNotIn("DELETE", [request.method for request in requests])
        self.assertEqual(requests[0].full_url, lab.ENDPOINT + "/")
        self.assertTrue(all(request.full_url.startswith(lab.ENDPOINT + "/" + INDEX) for request in requests[1:]))
        self.assertTrue(all("_cluster" not in request.full_url and "_all" not in request.full_url for request in requests))
        self.assertIn("if_seq_no=0", requests[14].full_url)
        self.assertEqual(requests[14].full_url, requests[15].full_url)
        self.assertEqual(json.loads(requests[14].data), {"doc": {"price": 11}})
        self.assertEqual(json.loads(requests[15].data), {"doc": {"price": 999}})
        self.assertEqual(lab.FIXTURES[0]["price"], 10)

    def test_wrong_preflight_stops_before_any_write(self):
        bad = identity()
        bad["cluster_name"] = "production"
        client = make_client([FakeResponse(bad)])
        with self.assertRaisesRegex(lab.LabFailure, "unexpected_cluster_or_node"):
            lab.run_lab(client)
        self.assertEqual(client.requests, 1)
        self.assertFalse(client.index_created)

    def test_existing_index_conflict_never_retries_or_overwrites(self):
        client = make_client([FakeResponse(identity()), FakeResponse({}, status=400)])
        with self.assertRaisesRegex(lab.LabFailure, "unexpected_http_status"):
            lab.run_lab(client)
        self.assertEqual(client.requests, 2)
        self.assertFalse(client.index_created)

    def test_creation_without_shard_acknowledgement_is_not_pass(self):
        client = make_client([FakeResponse(identity()), FakeResponse({"acknowledged": True, "shards_acknowledged": False, "index": INDEX})])
        with self.assertRaisesRegex(lab.LabFailure, "index_creation_unconfirmed"):
            lab.run_lab(client)
        self.assertEqual(client.requests, 2)

    def test_premature_search_visibility_fails(self):
        responses = responses_for_success()
        responses[3] = FakeResponse(hits(["a1"]))
        client = make_client(responses)
        with self.assertRaisesRegex(lab.LabFailure, "wrong_total"):
            lab.run_lab(client)
        self.assertEqual(client.stage, "pre_refresh_search")

    def test_final_exact_row_oracle_rejects_wrong_value_even_with_right_counts(self):
        responses = responses_for_success()
        wrong = aggregate(updated=True)
        wrong["hits"]["hits"][0]["_source"]["price"] = 999
        responses[-1] = FakeResponse(wrong)
        client = make_client(responses)
        with self.assertRaisesRegex(lab.LabFailure, "wrong_final_rows"):
            lab.run_lab(client)

    def test_main_failure_reports_stage_without_server_body_or_cleanup(self):
        client = make_client([urllib.error.URLError("do-not-print-this")])
        output = io.StringIO()
        with patch.object(lab, "LocalClient", return_value=client), contextlib.redirect_stdout(output):
            code = lab.main(["--run-local"])
        self.assertEqual(code, 1)
        data = json.loads(output.getvalue())
        self.assertEqual(data["status"], "ERROR")
        self.assertEqual(data["stage"], "preflight")
        self.assertEqual(data["index"], INDEX)
        self.assertFalse(data["cleanup_performed"])
        self.assertNotIn("do-not-print-this", output.getvalue())

    def test_main_mock_success_reports_only_completed_oracles(self):
        client = make_client(responses_for_success())
        output = io.StringIO()
        with patch.object(lab, "LocalClient", return_value=client), contextlib.redirect_stdout(output):
            self.assertEqual(lab.main(["--run-local"]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["oracles"]["final_search_count"], 6)
        self.assertIn("security isolation", result["not_verified"])


if __name__ == "__main__":
    unittest.main()
