"""Opt-in Qdrant 1.19.1 REST lab; Python 3.10+ standard library.

Default --plan performs no network/file I/O. --run creates one fresh collection
on a fixed loopback endpoint, retains it, and never accepts an existing name.
Six synthetic vectors are NOT an HNSW, relevance, performance, or HA benchmark.
Mock tests check this client contract, not the actual database implementation.
"""
from __future__ import annotations

import argparse
import http.client
import json
import math
import re
import sys
import time
import uuid
from copy import deepcopy

ENDPOINT = "http://127.0.0.1:16333"
VERSION = "1.19.1"
MAX_REQUESTS = 64
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REQUEST_BYTES = 32 * 1024
SOCKET_TIMEOUT = 10
RUN_DEADLINE = 180
NAME_PATTERN = re.compile(r"efl_qdrant_[0-9a-f]{32}\Z")
SCENARIOS = ("basics", "features", "incidents", "all")
DENSE_QUERY = [1, 0, 0, 0]
SPARSE_QUERY = {"indices": [0], "values": [1]}
DENSE_IDS = [1, 2, 3, 4, 5, 6]
DENSE_SCORES = [1, 0.8, 0.6, 0, -0.6, -1]
SPARSE_IDS = [2, 4, 1, 3, 5, 6]
RRF_IDS = [2, 1, 4, 3]
RRF_SCORES = [5 / 6, 3 / 4, 1 / 3, 1 / 4]
# Mirrored in fixture.json for independent inspection; no runtime file input.
POINTS = [
    {"id": 1, "vector": {"dense": [1, 0, 0, 0], "lexical": {"indices": [0], "values": [4]}}, "payload": {"tenant": "alpha", "doc": "a1", "rating": 5}},
    {"id": 2, "vector": {"dense": [0.8, 0.6, 0, 0], "lexical": {"indices": [0], "values": [6]}}, "payload": {"tenant": "alpha", "doc": "a2", "rating": 4}},
    {"id": 3, "vector": {"dense": [0.6, 0.8, 0, 0], "lexical": {"indices": [0], "values": [3]}}, "payload": {"tenant": "beta", "doc": "b1", "rating": 3}},
    {"id": 4, "vector": {"dense": [0, 1, 0, 0], "lexical": {"indices": [0], "values": [5]}}, "payload": {"tenant": "alpha", "doc": "a3", "rating": 2}},
    {"id": 5, "vector": {"dense": [-0.6, 0.8, 0, 0], "lexical": {"indices": [0], "values": [2]}}, "payload": {"tenant": "beta", "doc": "b2", "rating": 1}},
    {"id": 6, "vector": {"dense": [-1, 0, 0, 0], "lexical": {"indices": [0], "values": [1]}}, "payload": {"tenant": "beta", "doc": "b3", "rating": 0}},
]


class LabFailure(Exception):
    """Only constant codes: server bodies, credentials and URLs are not echoed."""


def require(condition, code):
    if not condition:
        raise LabFailure(code)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def emit(**record):
    print(json.dumps(record, ensure_ascii=False, allow_nan=False))


def check(stage, observed, expected):
    emit(stage=stage, observed=observed, expected=expected,
         result="PASS" if observed == expected else "FAIL")
    require(observed == expected, "oracle_mismatch_" + stage)


def query_body(using="dense", limit=6, filter_value=None):
    body = {"query": deepcopy(DENSE_QUERY if using == "dense" else SPARSE_QUERY),
            "using": using, "limit": limit, "with_payload": True,
            "with_vector": False, "params": {"exact": True}}
    if filter_value is not None:
        body["filter"] = filter_value
    return body


def field_match(field, value):
    return {"must": [{"key": field, "match": {"value": value}}]}


class LocalClient:
    """Direct HTTPConnection ignores proxy variables; never follows redirects."""

    def __init__(self, base_url):
        require(base_url == ENDPOINT, "target_refused")
        self.name = "efl_qdrant_" + uuid.uuid4().hex
        require(NAME_PATTERN.fullmatch(self.name) is not None, "name_refused")
        self.prefix = "/collections/" + self.name
        self.calls = 0
        self.started = time.monotonic()
        self.created = False
        self.create_attempted = False
        self.routes = {
            "identity": ("GET", "/"), "exists": ("GET", self.prefix + "/exists"),
            "create": ("PUT", self.prefix + "?timeout=10"),
            "info": ("GET", self.prefix), "metrics": ("GET", "/metrics"),
            "upsert": ("PUT", self.prefix + "/points?wait=true&timeout=10"),
            "retrieve": ("POST", self.prefix + "/points"),
            "count": ("POST", self.prefix + "/points/count"),
            "query": ("POST", self.prefix + "/points/query?timeout=10"),
            "index": ("PUT", self.prefix + "/index?wait=true&timeout=10"),
            "delete_point": ("POST", self.prefix + "/points/delete?wait=true&timeout=10"),
        }

    def call(self, route, body=None, expected_status=200):
        require(route in self.routes, "route_refused")
        require(route in ("identity", "exists", "create") or self.created,
                "collection_not_owned")
        require(expected_status in (200, 400), "status_contract_refused")
        require(self.calls < MAX_REQUESTS, "request_budget_exhausted")
        remaining = RUN_DEADLINE - (time.monotonic() - self.started)
        require(remaining > 0, "run_deadline_exhausted")
        encoded = None if body is None else json.dumps(body, allow_nan=False).encode()
        require(encoded is None or len(encoded) <= MAX_REQUEST_BYTES, "request_too_large")
        self.calls += 1
        method, path = self.routes[route]
        connection = http.client.HTTPConnection("127.0.0.1", 16333,
                                                timeout=min(SOCKET_TIMEOUT, remaining))
        try:
            connection.request(method, path, body=encoded,
                               headers={"Accept": "application/json" if route != "metrics" else "text/plain",
                                        "Content-Type": "application/json", "Connection": "close"})
            response = connection.getresponse()
            require(response.status == expected_status, "unexpected_http_status")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            require(len(raw) <= MAX_RESPONSE_BYTES, "response_too_large")
            if expected_status == 400:
                return {"http_status": 400}  # Never print service error text.
            if route == "metrics":
                return raw.decode("utf-8")
            require("application/json" in (response.getheader("Content-Type") or ""),
                    "invalid_content_type")
            value = json.loads(raw)
            require(isinstance(value, dict), "invalid_response")
            if route != "identity":
                require(value.get("status") == "ok" and "result" in value, "api_failure")
                return value["result"]
            return value
        except (OSError, http.client.HTTPException, ValueError, UnicodeError) as exc:
            raise LabFailure("transport_or_decode_failure_no_retry") from exc
        finally:
            connection.close()

    def create(self):
        identity = self.call("identity")
        require(isinstance(identity.get("version"), str) and
                re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", identity["version"]), "invalid_version")
        check("server_version", identity.get("version"), VERSION)
        absent = self.call("exists")
        require(isinstance(absent, dict) and absent.get("exists") is False,
                "existing_collection_refused")
        self.create_attempted = True
        result = self.call("create", {"vectors": {"dense": {"size": 4, "distance": "Cosine"}},
                                     "sparse_vectors": {"lexical": {}},
                                     "shard_number": 1, "replication_factor": 1,
                                     "metadata": {"lab": "engineering-foundations-qdrant", "run_id": self.name}})
        require(result is True, "create_not_confirmed")
        self.created = True


def completed(result):
    require(isinstance(result, dict) and result.get("status") == "completed",
            "write_not_completed")


def upsert(client, points):
    completed(client.call("upsert", {"points": deepcopy(points)}))


def exact_count(client, expected, stage):
    result = client.call("count", {"exact": True})
    require(isinstance(result, dict) and type(result.get("count")) is int, "invalid_count")
    check(stage, result["count"], expected)


def retrieve(client, expected, stage):
    ids = [point["id"] for point in expected]
    observed = client.call("retrieve", {"ids": ids, "with_payload": True, "with_vector": True})
    require(isinstance(observed, list), "invalid_retrieve")
    require(all(isinstance(point, dict) and type(point.get("id")) is int for point in observed),
            "invalid_retrieve_point")
    check(stage + "_ids", sorted(point["id"] for point in observed), sorted(ids))
    by_id = {point["id"]: point for point in observed}
    for point in expected:
        result = by_id[point["id"]]
        # Only a Boolean is logged; unexpected server payload is never echoed.
        check(stage + "_payload_" + str(point["id"]), result.get("payload") == point["payload"], True)
        vectors = result.get("vector", {})
        require(isinstance(vectors, dict), "invalid_vectors")
        values = vectors.get("dense", [])
        require(isinstance(values, list) and len(values) == 4 and all(number(v) for v in values),
                "invalid_dense_vector")
        check(stage + "_dense_" + str(point["id"]),
              all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(values, point["vector"]["dense"])), True)
        check(stage + "_sparse_" + str(point["id"]), vectors.get("lexical") == point["vector"]["lexical"], True)


def query(client, body, ids, scores, stage):
    result = client.call("query", body)
    require(isinstance(result, dict) and isinstance(result.get("points"), list), "invalid_query")
    points = result["points"]
    require(all(isinstance(p, dict) and type(p.get("id")) is int and number(p.get("score")) for p in points),
            "invalid_query_point")
    check(stage + "_ids", [p["id"] for p in points], ids)
    actual_scores = [p["score"] for p in points]
    matches = len(scores) == len(points) and all(
        math.isclose(a, b, abs_tol=1e-5) for a, b in zip(actual_scores, scores))
    emit(stage=stage + "_scores", observed=actual_scores, expected=scores,
         tolerance=1e-5, result="PASS" if matches else "FAIL")
    require(matches, "score_oracle_mismatch")


def basics(client):
    upsert(client, POINTS)
    exact_count(client, 6, "baseline_count")
    retrieve(client, POINTS, "baseline_retrieve")
    query(client, query_body(), DENSE_IDS, DENSE_SCORES, "dense_exact")
    query(client, query_body(filter_value=field_match("tenant", "alpha")),
          [1, 2, 4], [1, 0.8, 0], "tenant_alpha")


def features(client):
    for field, schema in (("tenant", "keyword"), ("rating", "integer")):
        completed(client.call("index", {"field_name": field, "field_schema": schema}))
    info = client.call("info")
    require(isinstance(info, dict) and isinstance(info.get("payload_schema"), dict), "invalid_index_info")
    schema = info["payload_schema"]
    require(all(isinstance(schema.get(field), dict) for field in ("tenant", "rating")), "invalid_index_schema")
    types = {field: schema[field].get("data_type") for field in ("tenant", "rating")}
    require(all(value in ("keyword", "integer") for value in types.values()), "unexpected_index_type")
    check("payload_index_types", types,
          {"tenant": "keyword", "rating": "integer"})
    query(client, query_body(filter_value=field_match("tenant", "alpha")),
          [1, 2, 4], [1, 0.8, 0], "indexed_filter_same_results")
    query(client, query_body("lexical"), SPARSE_IDS, [6, 5, 4, 3, 2, 1], "sparse_exact")
    prefetch = [query_body(limit=3), query_body("lexical", limit=3)]
    for item in prefetch:
        item.pop("with_payload")
        item.pop("with_vector")
    # v1.19.1 default RRF k=2; zero-based ranks; not k=60 from other systems.
    query(client, {"prefetch": prefetch, "query": {"fusion": "rrf"}, "limit": 4,
                   "with_payload": True}, RRF_IDS, RRF_SCORES, "hybrid_rrf")
    updated = deepcopy(POINTS[0])
    updated["payload"]["rating"] = 6
    upsert(client, [updated])
    exact_count(client, 6, "same_id_overwrite_count")
    retrieve(client, [updated], "same_id_updated")
    upsert(client, [POINTS[0]])
    retrieve(client, [POINTS[0]], "same_id_recovered")
    completed(client.call("delete_point", {"points": [2]}))
    exact_count(client, 5, "delete_count")
    check("deleted_id_absent", client.call("retrieve", {"ids": [2]}) == [], True)
    upsert(client, [POINTS[1]])
    exact_count(client, 6, "delete_reinsert_count")


def incidents(client):
    malformed = deepcopy(POINTS[0])
    malformed["id"] = 7
    malformed["vector"]["dense"] = [1, 0, 0]
    check("wrong_dimension", client.call("upsert", {"points": [malformed]}, 400), {"http_status": 400})
    exact_count(client, 6, "wrong_dimension_unchanged_count")
    check("rejected_id_absent", client.call("retrieve", {"ids": [7]}) == [], True)
    # Repair the same attempted point, verify it, then remove only that owned point.
    repaired = deepcopy(POINTS[0])
    repaired["id"] = 7
    upsert(client, [repaired])
    retrieve(client, [repaired], "dimension_repaired")
    exact_count(client, 7, "dimension_repaired_count")
    completed(client.call("delete_point", {"points": [7]}))
    exact_count(client, 6, "dimension_recovery_count")
    query(client, query_body(filter_value=field_match("rating", "5")), [], [], "wrong_payload_type")
    query(client, query_body(filter_value=field_match("rating", 5)), [1], [1], "payload_type_recovered")
    mismatch = query_body()
    mismatch["using"] = "missing_dense"
    check("wrong_vector_name", client.call("query", mismatch, 400), {"http_status": 400})
    query(client, query_body(), DENSE_IDS, DENSE_SCORES, "vector_name_recovered")


def observe(client):
    info = client.call("info")
    require(isinstance(info, dict), "invalid_collection_info")
    summary = {key: info[key] for key in ("points_count", "indexed_vectors_count", "segments_count")
               if type(info.get(key)) is int and info[key] >= 0}
    summary["status"] = info.get("status") if info.get("status") in ("green", "yellow", "grey", "red") else "unknown"
    summary["optimizer_ok"] = info.get("optimizer_status") == "ok"
    emit(stage="collection_observation", observed=summary,
         note="counts_may_be_approximate_indexed_count_not_an_HNSW_or_HA_proof")
    metrics = client.call("metrics")
    selected = {}
    for line in metrics.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in ("collections_total", "collections_vector_total", "process_resident_memory_bytes"):
            try:
                value = float(parts[1])
                if math.isfinite(value):
                    selected[parts[0]] = value
            except ValueError:
                pass
    emit(stage="metrics_observation", observed=selected,
         note="allowlisted_unlabelled_instance_metrics_only_missing_is_not_zero")


def execute(client, scenario):
    require(scenario in SCENARIOS, "scenario_refused")
    client.create()
    basics(client)
    if scenario in ("features", "all"):
        features(client)
    if scenario in ("incidents", "all"):
        incidents(client)
    exact_count(client, 6, "final_count")
    retrieve(client, POINTS, "final_recovery")
    query(client, query_body(), DENSE_IDS, DENSE_SCORES, "final_dense")
    observe(client)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise LabFailure("invalid_arguments")  # Do not echo pasted secrets/URLs.


def main(argv=None):
    client = None
    try:
        parser = SafeParser(description=__doc__)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--plan", action="store_true")
        mode.add_argument("--run", action="store_true")
        parser.add_argument("--base-url", default=ENDPOINT)
        parser.add_argument("--scenario", choices=SCENARIOS, default="all")
        args = parser.parse_args(argv)
        require(args.base_url == ENDPOINT, "target_refused")
        if not args.run:
            emit(mode="PLAN_ONLY", scenario=args.scenario, endpoint=ENDPOINT, network_calls=0,
                 fixture_points=6, maximum_live_points=7, maximum_requests=MAX_REQUESTS,
                 created_collection="fresh efl_qdrant_<32hex>; never reuse", automatic_cleanup=False,
                 expected_dense_ids=DENSE_IDS, expected_alpha_ids=[1, 2, 4],
                 expected_sparse_ids=SPARSE_IDS, expected_rrf_ids=RRF_IDS,
                 limits="local correctness only; no embedding API, ANN/scale/HA/security proof")
            return 0
        client = LocalClient(args.base_url)
        emit(mode="RUN_START", collection=client.name, scenario=args.scenario,
             note="explicit_local_writes_no_auto_cleanup_no_retries")
        execute(client, args.scenario)
        emit(mode="LOCAL_ENGINE_PASS", collection=client.name, requests=client.calls,
             retained=True, performance_ha_production_security_verified=False)
        return 0
    except LabFailure as exc:
        emit(mode="STOPPED", code=str(exc), collection=client.name if client else None,
             create_attempted=bool(client and client.create_attempted),
             created_confirmed=bool(client and client.created),
             note="no_retry_no_cleanup_check_retained_collection_if_creation_was_attempted")
        return 1
    except KeyboardInterrupt:
        emit(mode="INTERRUPTED", collection=client.name if client else None,
             note="outcome_may_be_unknown_no_cleanup")
        return 130


if __name__ == "__main__":
    sys.exit(main())
