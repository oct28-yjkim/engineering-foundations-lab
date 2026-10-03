"""Opt-in, synthetic OpenSearch 3.9.0 REST lab; Python 3.10+ standard library.

Only http://127.0.0.1:19200 is used. Each run creates and retains one new index.
No cleanup, cloud access, credentials, arbitrary URLs, or existing-index writes.
Mock tests validate client contracts, not an actual OpenSearch implementation.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from copy import deepcopy
from typing import Any


ENDPOINT = "http://127.0.0.1:19200"
VERSION = "3.9.0"
CLUSTER = "engineering-foundations-opensearch-lab"
NODE = "opensearch-lab"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REQUESTS = 32
SOCKET_TIMEOUT_SECONDS = 10
INDEX_PATTERN = re.compile(r"efl-os-[0-9a-f]{32}\Z")

FIXTURES = (
    {"doc_id": "a1", "tenant": "alpha", "title": "Quick brown fox", "price": 10},
    {"doc_id": "a2", "tenant": "alpha", "title": "Quick blue fox", "price": 20},
    {"doc_id": "a3", "tenant": "alpha", "title": "Brown fox handbook", "price": 30},
    {"doc_id": "b1", "tenant": "beta", "title": "Quick brown fox", "price": 15},
    {"doc_id": "b2", "tenant": "beta", "title": "Slow green turtle", "price": 5},
    {"doc_id": "b3", "tenant": "beta", "title": "Brown fox quick guide", "price": 25},
)


class LabFailure(Exception):
    """An intentionally terse error code; never include server bodies or secrets."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise LabFailure(code)


def integer(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def index_definition() -> dict[str, Any]:
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "-1",
        },
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "doc_id": {"type": "keyword"},
                "tenant": {"type": "keyword"},
                "title": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {"raw": {"type": "keyword"}},
                },
                "price": {"type": "integer", "coerce": False},
            },
        },
    }


def bulk_create(documents: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> bytes:
    """No _index metadata: every operation stays in the request's fresh index."""
    lines = []
    for document in documents:
        require(isinstance(document, dict), "invalid_fixture")
        doc_id = document.get("doc_id")
        require(isinstance(doc_id, str) and re.fullmatch(r"[a-z][a-z0-9]{0,31}", doc_id) is not None,
                "invalid_fixture_id")
        lines.extend((json.dumps({"create": {"_id": doc_id}}), json.dumps(document)))
    return ("\n".join(lines) + "\n").encode("utf-8")


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LabFailure("redirect_refused")


class LocalClient:
    """A closed set of routes, all scoped to a generated index except GET /."""

    def __init__(self) -> None:
        self.index = "efl-os-" + uuid.uuid4().hex
        require(INDEX_PATTERN.fullmatch(self.index) is not None, "invalid_generated_index")
        self.requests = 0
        self.stage = "preflight"
        self.index_created = False
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), RejectRedirects()
        )

    def request(
        self,
        resource: str,
        body: dict[str, Any] | bytes | None = None,
        *,
        seq_no: int | None = None,
        primary_term: int | None = None,
        expected_status: int = 200,
    ) -> dict[str, Any]:
        require(INDEX_PATTERN.fullmatch(self.index) is not None, "invalid_generated_index")
        index_path = "/" + urllib.parse.quote(self.index, safe="")
        routes = {
            "root": ("GET", "/", {}),
            "index": ("PUT", index_path, {"wait_for_active_shards": "1", "timeout": "10s"}),
            "bulk": ("POST", index_path + "/_bulk", {"refresh": "false", "timeout": "10s"}),
            "refresh": ("POST", index_path + "/_refresh", {}),
            "search": ("POST", index_path + "/_search", {"allow_partial_search_results": "false"}),
            "get_a1": ("GET", index_path + "/_doc/a1", {"realtime": "true"}),
            "update_a1": ("POST", index_path + "/_update/a1", {"refresh": "false", "timeout": "10s"}),
        }
        require(resource in routes, "route_refused")
        require((resource == "root") or self.index_created or resource == "index", "index_not_created")
        if resource == "update_a1":
            require(integer(seq_no) and integer(primary_term, 1), "invalid_occ_token")
        else:
            require(seq_no is None and primary_term is None, "unexpected_occ_token")
        method, path, query = routes[resource]
        if resource == "update_a1":
            query.update(if_seq_no=str(seq_no), if_primary_term=str(primary_term))
        url = ENDPOINT + path + ("?" + urllib.parse.urlencode(query) if query else "")
        require(body is None or isinstance(body, (dict, bytes)), "invalid_request_body")
        require(method != "GET" or body is None, "get_body_refused")
        payload = body if isinstance(body, bytes) else (
            json.dumps(body, allow_nan=False).encode("utf-8") if body is not None else None
        )
        content_type = "application/x-ndjson" if resource == "bulk" else "application/json"
        request = urllib.request.Request(
            url, data=payload, method=method,
            headers={"Content-Type": content_type, "Accept": "application/json", "Accept-Encoding": "identity"},
        )
        require(self.requests < MAX_REQUESTS, "request_budget_exceeded")
        self.requests += 1
        try:
            try:
                response = self.opener.open(request, timeout=SOCKET_TIMEOUT_SECONDS)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.status
                # No redirect following, compressed data, arbitrary response output,
                # or unbounded reads. Timeout is per socket operation, not wall time.
                require(not 300 <= status < 400, "redirect_refused")
                require(status == expected_status, "unexpected_http_status")
                content_encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
                require(content_encoding in ("", "identity"), "response_encoding_refused")
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                require(content_type in ("application/json", "application/vnd.opensearch+json"),
                        "response_not_json")
                length = response.headers.get("Content-Length")
                if length is not None:
                    require(length.isdigit() and int(length) <= MAX_RESPONSE_BYTES, "response_too_large")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                require(len(raw) <= MAX_RESPONSE_BYTES, "response_too_large")
                data = json.loads(raw.decode("utf-8"))
                require(isinstance(data, dict), "response_not_object")
                return data
        except LabFailure:
            raise
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError, RecursionError):
            raise LabFailure("transport_or_json_failure") from None


def verify_identity(data: dict[str, Any]) -> None:
    """Accidental-target guard only; a hostile local server can spoof these fields."""
    version = data.get("version")
    require(isinstance(version, dict), "unexpected_server")
    require(version.get("number") == VERSION and version.get("distribution") == "opensearch",
            "unexpected_version")
    require(data.get("cluster_name") == CLUSTER and data.get("name") == NODE,
            "unexpected_cluster_or_node")


def verify_shards(data: dict[str, Any]) -> None:
    shards = data.get("_shards")
    require(isinstance(shards, dict), "missing_shards")
    require(shards.get("failed") == 0 and integer(shards.get("failed")), "shard_failure")
    require(integer(shards.get("total"), 1) and integer(shards.get("successful"), 1)
            and shards["successful"] == shards["total"],
            "incomplete_shards")
    require(not shards.get("failures"), "shard_failure")


def verify_search(data: dict[str, Any], index: str, expected_ids: list[str]) -> list[dict[str, Any]]:
    verify_shards(data)
    require(data.get("timed_out") is False, "search_timeout")
    require(data.get("terminated_early") in (None, False), "search_terminated_early")
    hits = data.get("hits")
    require(isinstance(hits, dict), "missing_hits")
    total = hits.get("total")
    require(isinstance(total, dict) and total.get("relation") == "eq", "inexact_total")
    require(integer(total.get("value")) and total["value"] == len(expected_ids), "wrong_total")
    rows = hits.get("hits")
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), "invalid_hits")
    require([row.get("_id") for row in rows] == expected_ids, "wrong_ids_or_order")
    require(all(row.get("_index") == index for row in rows), "unexpected_hit_index")
    require(len({row.get("_id") for row in rows}) == len(rows), "duplicate_hits")
    return rows


def verify_bulk(data: dict[str, Any], index: str, expected: list[tuple[str, int, str | None]]) -> None:
    items = data.get("items")
    require(isinstance(items, list) and len(items) == len(expected), "bulk_item_count")
    require(data.get("errors") is any(status >= 400 for _, status, _ in expected), "bulk_errors_flag")
    for item, (doc_id, status, error_type) in zip(items, expected):
        require(isinstance(item, dict) and set(item) == {"create"}, "bulk_action_mismatch")
        result = item["create"]
        require(isinstance(result, dict), "bulk_invalid_item")
        require(result.get("_id") == doc_id and result.get("_index") == index, "bulk_target_mismatch")
        require(result.get("status") == status, "bulk_status_mismatch")
        if error_type is None:
            require("error" not in result and result.get("result") == "created", "bulk_create_failed")
            verify_shards(result)
        else:
            error = result.get("error")
            require(isinstance(error, dict) and error.get("type") == error_type, "bulk_error_mismatch")


def search_body(query: dict[str, Any] | None = None, sort: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "size": 10,
        "track_total_hits": True,
        "timeout": "5s",
        "query": query if query is not None else {"match_all": {}},
        "sort": sort if sort is not None else [{"doc_id": "asc"}],
    }


def query_cases() -> list[tuple[str, dict[str, Any], list[str]]]:
    """Literal expected IDs: no expected values derived from server ranking."""
    return [
        ("keyword", search_body({"terms": {"tenant": ["alpha"]}}), ["a1", "a2", "a3"]),
        ("raw_keyword", search_body({"term": {"title.raw": "Quick brown fox"}}), ["a1", "b1"]),
        ("match_and", search_body({"match": {"title": {"query": "quick brown", "operator": "and"}}}),
         ["a1", "b1", "b3"]),
        ("phrase", search_body({"match_phrase": {"title": {"query": "quick brown", "slop": 0}}}),
         ["a1", "b1"]),
        ("range", search_body({"range": {"price": {"gte": 10, "lte": 20}}}), ["a1", "a2", "b1"]),
        ("sort", search_body(sort=[{"price": "asc"}, {"doc_id": "asc"}]),
         ["b2", "a1", "b1", "a2", "b3", "a3"]),
    ]


def verify_aggregation(data: dict[str, Any], index: str) -> None:
    verify_search(data, index, ["a1", "a2", "a3", "b1", "b2", "b3"])
    aggregations = data.get("aggregations")
    require(isinstance(aggregations, dict), "missing_aggregation")
    tenants = aggregations.get("tenants")
    require(isinstance(tenants, dict), "missing_tenant_aggregation")
    require(tenants.get("doc_count_error_upper_bound") == 0 and tenants.get("sum_other_doc_count") == 0,
            "incomplete_aggregation")
    require(tenants.get("buckets") == [{"key": "alpha", "doc_count": 3}, {"key": "beta", "doc_count": 3}],
            "wrong_aggregation_buckets")


def run_lab(client: LocalClient) -> dict[str, Any]:
    client.stage = "preflight"
    verify_identity(client.request("root"))
    client.stage = "create_index"
    created = client.request("index", index_definition())
    require(created.get("acknowledged") is True and created.get("shards_acknowledged") is True
            and created.get("index") == client.index, "index_creation_unconfirmed")
    client.index_created = True
    client.stage = "bulk_create"
    verify_bulk(client.request("bulk", bulk_create(FIXTURES)), client.index,
                [(document["doc_id"], 201, None) for document in FIXTURES])
    client.stage = "pre_refresh_search"
    verify_search(client.request("search", search_body()), client.index, [])
    client.stage = "realtime_get"
    realtime = client.request("get_a1")
    require(realtime.get("found") is True and realtime.get("_id") == "a1"
            and realtime.get("_index") == client.index and realtime.get("_source") == FIXTURES[0],
            "wrong_realtime_document")
    seq_no, primary_term = realtime.get("_seq_no"), realtime.get("_primary_term")
    require(integer(seq_no) and integer(primary_term, 1), "invalid_server_occ_token")
    client.stage = "refresh"
    verify_shards(client.request("refresh"))
    client.stage = "post_refresh_search"
    verify_search(client.request("search", search_body()), client.index,
                  ["a1", "a2", "a3", "b1", "b2", "b3"])
    for name, query, expected_ids in query_cases():
        client.stage = "query_" + name
        verify_search(client.request("search", query), client.index, expected_ids)
    aggregation_query = search_body()
    aggregation_query["aggs"] = {"tenants": {"terms": {"field": "tenant", "size": 10, "order": {"_key": "asc"}}}}
    client.stage = "aggregation"
    verify_aggregation(client.request("search", aggregation_query), client.index)
    client.stage = "occ_update"
    updated = client.request("update_a1", {"doc": {"price": 11}}, seq_no=seq_no, primary_term=primary_term)
    require(updated.get("_index") == client.index and updated.get("_id") == "a1"
            and updated.get("result") == "updated", "update_unconfirmed")
    verify_shards(updated)
    require(integer(updated.get("_seq_no")) and updated["_seq_no"] > seq_no, "unchanged_seq_no")
    client.stage = "occ_stale_conflict"
    stale = client.request("update_a1", {"doc": {"price": 999}}, seq_no=seq_no, primary_term=primary_term,
                           expected_status=409)
    require(isinstance(stale.get("error"), dict)
            and stale["error"].get("type") == "version_conflict_engine_exception"
            and stale.get("status") == 409, "stale_update_not_rejected")
    client.stage = "negative_bulk"
    bad_price = {"doc_id": "invalid", "tenant": "alpha", "title": "Invalid price", "price": "not-an-integer"}
    verify_bulk(client.request("bulk", bulk_create([FIXTURES[0], bad_price])), client.index,
                [("a1", 409, "version_conflict_engine_exception"), ("invalid", 400, "mapper_parsing_exception")])
    client.stage = "final_refresh"
    verify_shards(client.request("refresh"))
    client.stage = "final_rows"
    final_response = client.request("search", aggregation_query)
    verify_aggregation(final_response, client.index)
    expected_rows = deepcopy(list(FIXTURES))
    expected_rows[0]["price"] = 11
    require([row.get("_source") for row in final_response["hits"]["hits"]] == expected_rows,
            "wrong_final_rows")
    client.stage = "complete"
    return {
        "status": "PASS", "mode": "local_engine", "version": VERSION, "endpoint": ENDPOINT,
        "index": client.index, "index_retained": True, "requests": client.requests,
        "oracles": {
            "pre_refresh_search_count": 0, "realtime_get_found": True, "final_search_count": 6,
            "query_cases": 6, "tenant_counts": {"alpha": 3, "beta": 3},
            "updated_a1_price": 11, "stale_update_status": 409, "negative_bulk_statuses": [409, 400],
        },
        "not_verified": ["security isolation", "replication or failover", "durability after crash",
                         "BM25 score equivalence", "vector search", "production performance"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-local", action="store_true",
                        help="Opt in to synthetic writes to one fresh local index; retain it without cleanup.")
    args = parser.parse_args(argv)
    if not args.run_local:
        parser.error("Pass --run-local to opt in. No HTTP request was sent.")
    if sys.version_info < (3, 10):
        print(json.dumps({"status": "ERROR", "stage": "preflight", "error": "python_3_10_required"}))
        return 1
    client = LocalClient()
    try:
        print(json.dumps(run_lab(client), ensure_ascii=False, sort_keys=True))
        return 0
    except LabFailure as error:
        print(json.dumps({"status": "ERROR", "stage": client.stage, "error": str(error),
                          "index": client.index, "index_creation_confirmed": client.index_created,
                          "cleanup_performed": False, "requests": client.requests}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
