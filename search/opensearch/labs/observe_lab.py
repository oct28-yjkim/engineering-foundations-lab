"""Opt-in real OpenSearch query-cost comparison; not a CPU simulation or load test.

Fresh synthetic index only; fixed loopback endpoint, no deletion/global changes.
JSON stdout is evidence, not a promise that a slowdown or rejection was reproduced.
"""
from __future__ import annotations

import argparse
import http.client
import json
import math
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

from engine_lab import (ENDPOINT, NODE, LabFailure, RejectRedirects, integer,
                        require, verify_identity, verify_shards)

MAX_REQUESTS = 300
MAX_BYTES = 5 * 1024 * 1024
TIME_BUDGET_SECONDS = 120
INDEX_PATTERN = re.compile(r"efl-os-observe-[0-9a-f]{32}\Z")


def valid_options(documents: int, samples: int) -> None:
    require(type(documents) is int and 100 <= documents <= 10000, "documents_must_be_100_to_10000")
    require(type(samples) is int and 10 <= samples <= 100, "samples_must_be_10_to_100")


def fixture(number: int) -> dict:
    return {"doc_id": f"d{number:06d}", "group_no": number % 10, "value": number * 3}


def definition() -> dict:
    return {"settings": {"number_of_shards": 1, "number_of_replicas": 0, "refresh_interval": "-1"},
            "mappings": {"dynamic": "strict", "_meta": {"lab": "efl-observation-v1"},
                         "properties": {"doc_id": {"type": "keyword"}, "group_no": {"type": "integer"},
                                        "value": {"type": "integer"}}}}


def query(variant: str, *, rows: bool = False, profile: bool = False) -> dict:
    require(variant in ("script", "indexed"), "unknown_query_variant")
    clause = ({"script": {"script": {"source": "doc['group_no'].value == params.target",
                                     "params": {"target": 3}}}}
              if variant == "script" else {"term": {"group_no": 3}})
    body = {"query": {"bool": {"filter": [clause]}}, "track_total_hits": True,
            "size": 1000 if rows else 0, "timeout": "5s"}
    if rows:
        body["sort"] = [{"doc_id": "asc"}]
    if profile:
        body["profile"] = True
    return body


class Client:
    def __init__(self) -> None:
        self.index = "efl-os-observe-" + uuid.uuid4().hex
        self.created = False
        self.requests = 0
        self.stage = "preflight"
        self.started = time.monotonic()
        self.last_http_status = None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), RejectRedirects())

    def request(self, action: str, body: dict | bytes | None = None) -> dict:
        require(INDEX_PATTERN.fullmatch(self.index) is not None, "invalid_generated_index")
        base = "/" + self.index
        routes = {
            "root": ("GET", "/"),
            "create": ("PUT", base + "?wait_for_active_shards=1&timeout=10s"),
            "bulk": ("POST", base + "/_bulk?refresh=false&timeout=10s"),
            "refresh": ("POST", base + "/_refresh"),
            "search": ("POST", base + "/_search?allow_partial_search_results=false&request_cache=false"),
            "nodes": ("GET", "/_nodes/stats/jvm,process,fs,thread_pool,indices,breaker"),
            "stats": ("GET", base + "/_stats/search,indexing,merge,refresh"),
        }
        require(action in routes, "route_refused")
        require(action in ("root", "create") or self.created, "index_not_created")
        require(action != "create" or not self.created, "index_already_created")
        require(self.requests < MAX_REQUESTS, "request_budget_exceeded")
        require(time.monotonic() - self.started < TIME_BUDGET_SECONDS, "time_budget_exceeded")
        method, path = routes[action]
        require(body is None or isinstance(body, (dict, bytes)), "invalid_body")
        require(method != "GET" or body is None, "get_body_refused")
        payload = body if isinstance(body, bytes) else (
            json.dumps(body, allow_nan=False).encode() if body is not None else None)
        require(payload is None or len(payload) <= 1024 * 1024, "request_too_large")
        headers = {"Content-Type": "application/x-ndjson" if action == "bulk" else "application/json",
                   "Accept": "application/json", "Accept-Encoding": "identity"}
        request = urllib.request.Request(ENDPOINT + path, data=payload, method=method, headers=headers)
        self.requests += 1
        self.last_http_status = None
        try:
            try:
                response = self.opener.open(request, timeout=10)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                self.last_http_status = response.status
                require(not 300 <= response.status < 400, "redirect_refused")
                require(response.status == 200, "unexpected_http_status")
                require(response.headers.get("Content-Encoding", "identity").strip().lower() in ("", "identity"),
                        "encoded_response_refused")
                require(response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                        in ("application/json", "application/vnd.opensearch+json"), "response_not_json")
                length = response.headers.get("Content-Length")
                require(length is None or (length.isdigit() and int(length) <= MAX_BYTES), "response_too_large")
                raw = response.read(MAX_BYTES + 1)
                require(len(raw) <= MAX_BYTES, "response_too_large")
                result = json.loads(raw.decode("utf-8"))
                require(isinstance(result, dict), "response_not_object")
                return result
        except LabFailure:
            raise
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError, RecursionError):
            raise LabFailure("transport_or_json_failure") from None


def check_search(data: dict, index: str, documents: int, *, rows: bool = False) -> int:
    verify_shards(data)
    require(data.get("timed_out") is False and data.get("terminated_early") in (None, False), "partial_search")
    expected = list(range(3, documents, 10))
    hits = data.get("hits", {})
    total = hits.get("total", {}) if isinstance(hits, dict) else {}
    require(isinstance(total, dict) and total.get("relation") == "eq" and integer(total.get("value"))
            and total["value"] == len(expected), "wrong_match_count")
    require(integer(data.get("took")), "invalid_took")
    if rows:
        actual = hits.get("hits")
        require(isinstance(actual, list) and len(actual) == len(expected), "missing_rows")
        for hit, number in zip(actual, expected):
            require(isinstance(hit, dict) and hit.get("_index") == index
                    and hit.get("_id") == f"d{number:06d}", "wrong_row_identity")
            require(hit.get("_source") == {"doc_id": f"d{number:06d}", "group_no": 3, "value": number * 3},
                    "wrong_row_values")
    return data["took"]


def read_number(data: dict, path: str):
    value = data
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def snapshot(client: Client) -> dict:
    raw = client.request("nodes")
    summary = raw.get("_nodes", {})
    nodes = raw.get("nodes", {})
    require(isinstance(summary, dict) and all(type(summary.get(k)) is int for k in ("total", "failed", "successful"))
            and summary.get("total") == 1 and summary.get("failed") == 0 and summary.get("successful") == 1
            and isinstance(nodes, dict) and len(nodes) == 1, "unexpected_node_stats_scope")
    node_id, node = next(iter(nodes.items()))
    require(isinstance(node, dict) and node.get("name") == NODE, "unexpected_node_stats_identity")
    gauge_paths = ("jvm.mem.heap_used_percent", "process.cpu.percent", "fs.total.available_in_bytes",
                   "thread_pool.search.queue", "thread_pool.search.active", "thread_pool.write.queue")
    counter_paths = ("jvm.gc.collectors.young.collection_count", "jvm.gc.collectors.young.collection_time_in_millis",
                     "jvm.gc.collectors.old.collection_count", "jvm.gc.collectors.old.collection_time_in_millis",
                     "thread_pool.search.rejected", "thread_pool.write.rejected",
                     "indices.merges.total", "indices.merges.total_time_in_millis")
    own = client.request("stats")
    verify_shards(own)
    indices = own.get("indices", {})
    require(isinstance(indices, dict) and set(indices) == {client.index}, "unexpected_index_stats_scope")
    require(isinstance(indices[client.index], dict), "invalid_index_stats")
    totals = indices[client.index].get("total", {})
    require(isinstance(totals, dict), "invalid_index_totals")
    gauges = {path: read_number(node, path) for path in gauge_paths}
    counters = {path: read_number(node, path) for path in counter_paths}
    for path in ("search.query_total", "search.query_time_in_millis", "indexing.index_total",
                 "indexing.index_time_in_millis", "merges.total", "merges.total_time_in_millis",
                 "refresh.total", "refresh.total_time_in_millis"):
        counters["owned_index." + path] = read_number(totals, path)
    return {"sampled_at_utc": datetime.now(timezone.utc).isoformat(), "monotonic_seconds": time.monotonic(),
            "node_id": node_id, "jvm_uptime_ms": read_number(node, "jvm.uptime_in_millis"),
            "gauges": gauges, "counters": counters}


def counter_changes(before: dict, after: dict) -> dict:
    first, last = before.get("jvm_uptime_ms"), after.get("jvm_uptime_ms")
    stable = (before.get("node_id") == after.get("node_id") and first is not None
              and last is not None and last >= first)
    result = {}
    for key, prior in before["counters"].items():
        current = after["counters"].get(key)
        if prior is None or current is None:
            result[key] = {"delta": None, "state": "unavailable"}
        elif not stable or current < prior:
            result[key] = {"delta": None, "state": "reset_or_restart"}
        else:
            result[key] = {"delta": current - prior, "state": "observed"}
    return result


def latency_summary(values: list[float]) -> dict:
    require(bool(values) and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values),
            "invalid_latency_samples")
    ordered = sorted(values)
    def nearest(percent):
        return ordered[max(0, math.ceil(len(ordered) * percent) - 1)]
    return {"count": len(ordered), "p50_ms": nearest(0.5), "p95_ms": nearest(0.95),
            "min_ms": ordered[0], "max_ms": ordered[-1], "method": "nearest_rank"}


def profile_summary(data: dict) -> list:
    profile = data.get("profile", {})
    require(isinstance(profile, dict), "profile_invalid")
    profiles = profile.get("shards", [])
    require(isinstance(profiles, list) and bool(profiles), "profile_missing")
    result = []
    for shard in profiles:
        require(isinstance(shard, dict) and isinstance(shard.get("searches"), list), "profile_searches_invalid")
        for search in shard["searches"]:
            require(isinstance(search, dict) and isinstance(search.get("query"), list), "profile_query_invalid")
            for item in search["query"]:
                require(isinstance(item, dict) and isinstance(item.get("type"), str)
                        and integer(item.get("time_in_nanos")), "profile_item_invalid")
                result.append({"type": item.get("type"), "time_in_nanos": item.get("time_in_nanos")})
    require(bool(result), "profile_queries_missing")
    return result


def run(client: Client, documents: int, samples: int) -> dict:
    valid_options(documents, samples)
    verify_identity(client.request("root"))
    client.stage = "create_index"
    created = client.request("create", definition())
    require(created.get("acknowledged") is True and created.get("shards_acknowledged") is True
            and created.get("index") == client.index, "index_creation_unconfirmed")
    client.created = True
    client.stage = "seed"
    for start in range(0, documents, 500):
        lines = []
        numbers = list(range(start, min(documents, start + 500)))
        for number in numbers:
            lines.extend((json.dumps({"create": {"_id": f"d{number:06d}"}}), json.dumps(fixture(number))))
        result = client.request("bulk", ("\n".join(lines) + "\n").encode())
        items = result.get("items", [])
        require(result.get("errors") is False and isinstance(items, list) and len(items) == len(numbers), "bulk_failure")
        for item, number in zip(items, numbers):
            require(isinstance(item, dict), "bulk_item_invalid")
            row = item.get("create", {})
            require(isinstance(row, dict) and type(row.get("status")) is int and row.get("status") == 201 and row.get("_index") == client.index
                    and row.get("_id") == f"d{number:06d}" and "error" not in row, "bulk_item_failure")
            verify_shards(row)
    verify_shards(client.request("refresh"))
    client.stage = "correctness_and_warmup"
    for variant in ("script", "indexed"):
        check_search(client.request("search", query(variant, rows=True)), client.index, documents, rows=True)
        for _ in range(2):
            check_search(client.request("search", query(variant)), client.index, documents)
    client.stage = "measure"
    before = snapshot(client)
    schedule = ["script", "indexed"] * samples
    random.Random(28).shuffle(schedule)
    measurements = []
    for variant in schedule:
        started = time.monotonic()
        result = client.request("search", query(variant))
        elapsed = (time.monotonic() - started) * 1000
        took = check_search(result, client.index, documents)
        measurements.append({"variant": variant, "client_ms": elapsed, "server_took_ms": took})
    after = snapshot(client)
    client.stage = "profile_outside_timing"
    profiles = {}
    for variant in ("script", "indexed"):
        result = client.request("search", query(variant, profile=True))
        check_search(result, client.index, documents)
        profiles[variant] = profile_summary(result)
        check_search(client.request("search", query(variant, rows=True)), client.index, documents, rows=True)
    client.stage = "complete"
    summary = {variant: {"client": latency_summary([m["client_ms"] for m in measurements if m["variant"] == variant]),
                         "server_took": latency_summary([m["server_took_ms"] for m in measurements if m["variant"] == variant])}
               for variant in ("script", "indexed")}
    difference = summary["script"]["client"]["p50_ms"] - summary["indexed"]["client"]["p50_ms"]
    return {"status": "MEASURED", "index": client.index, "index_retained": True,
            "documents": documents, "matching_documents": len(range(3, documents, 10)), "requests": client.requests,
            "samples_per_variant": samples, "concurrency": 1, "observed_errors": 0,
            "summary": summary, "samples": measurements, "before": before, "after": after,
            "counter_changes": counter_changes(before, after), "profile": profiles,
            "script_minus_indexed_p50_ms": difference,
            "slowdown_conclusion": "unconfirmed_repeat_with_controlled_workload",
            "pressure_incident": "not_reproduced_by_design",
            "limitations": ["sequential query-cost comparison, not capacity/429/OOM test",
                            "query/OS caches remain; request cache disabled; warmup before sampling",
                            "node metrics include other activity; two snapshots do not show peaks",
                            "small-sample p95 is descriptive, no production p99/SLO claim",
                            "profile collected after timed requests; profile is not client latency"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run-local", action="store_true")
    mode.add_argument("--plan", action="store_true")
    parser.add_argument("--documents", type=int, default=2000)
    parser.add_argument("--samples", type=int, default=20, help="requests per variant, 10..100")
    args = parser.parse_args(argv)
    try:
        valid_options(args.documents, args.samples)
    except LabFailure as error:
        parser.error(str(error))
    if not args.run_local:
        print(json.dumps({"status": "PLAN", "network_calls": 0, "endpoint": ENDPOINT,
                          "documents": args.documents, "samples_per_variant": args.samples,
                          "maximum_requests": MAX_REQUESTS, "budget_seconds": TIME_BUDGET_SECONDS,
                          "writes": "fresh UUID synthetic index; retained, never deleted"}))
        return 0
    client = Client()
    try:
        print(json.dumps(run(client, args.documents, args.samples), ensure_ascii=False, sort_keys=True))
        return 0
    except LabFailure as error:
        print(json.dumps({"status": "ERROR", "stage": client.stage, "error": str(error),
                          "http_status": client.last_http_status, "index": client.index,
                          "index_creation_confirmed": client.created, "requests": client.requests,
                          "cleanup_performed": False, "completed_comparison": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
