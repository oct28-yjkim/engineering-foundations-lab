"""Opt-in, staged OpenSearch incident practice against the existing local lab.

Python 3.10+ standard library. --list and --help do not access the network.
Five small, retained fixtures; no global settings, deletes, service starts, disk
filling, cloud access, credentials, or arbitrary URLs. This is not a load test.
Ownership and identity checks prevent accidental targeting, not a hostile local
server or concurrent administrator. Mock tests do not prove engine behavior.
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
from typing import Any

from engine_lab import (
    CLUSTER, ENDPOINT, NODE, VERSION, LabFailure, RejectRedirects, bulk_create,
    integer, require, verify_bulk, verify_identity, verify_shards,
)


SCENARIOS = ("refresh", "bulk-errors", "write-block", "allocation", "pagination")
STEPS = ("prepare", "observe", "recover", "verify")
MARKER = "engineering-foundations-opensearch-incident-v1"
MAX_REQUESTS = 96
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PAYLOAD_BYTES = 32 * 1024
SOCKET_TIMEOUT_SECONDS = 5
RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
DOCS = ({"doc_id": "a1", "value": 1}, {"doc_id": "a2", "value": 2})
PAGE_DOCS = tuple({"doc_id": f"p{number:02d}", "value": number} for number in range(20))


def search_body(size: int = 5, *, after: str | None = None, deep: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "size": size, "track_total_hits": True, "timeout": "3s",
        "query": {"match_all": {}}, "sort": [{"doc_id": "asc"}],
    }
    if after is not None:
        result["search_after"] = [after]
    if deep:
        result["from"] = 5
    return result


def index_definition(scenario: str, run_id: str) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "number_of_shards": 1, "number_of_replicas": 0, "refresh_interval": "-1",
    }
    if scenario == "pagination":
        settings["max_result_window"] = 5
    return {
        "settings": settings,
        "mappings": {
            "_meta": {"lab": MARKER, "scenario": scenario, "run_id": run_id},
            "dynamic": "strict",
            "properties": {"doc_id": {"type": "keyword"},
                           "value": {"type": "integer", "coerce": False}},
        },
    }


class LocalClient:
    """Closed routes and bodies; every existing-index mutation rechecks _meta."""

    def __init__(self, scenario: str, step: str, run_id: str | None = None) -> None:
        require(scenario in SCENARIOS and step in STEPS, "invalid_scenario_or_step")
        require((step == "prepare" and run_id is None) or
                (step != "prepare" and isinstance(run_id, str) and RUN_ID.fullmatch(run_id) is not None),
                "invalid_run_id_contract")
        self.scenario, self.step = scenario, step
        self.run_id = uuid.uuid4().hex if run_id is None else run_id
        require(RUN_ID.fullmatch(self.run_id) is not None, "invalid_generated_run_id")
        self.index = f"efl-os-incident-{scenario}-{self.run_id}"
        self.requests = 0
        self.stage = "preflight"
        self.created = False
        self.last_status = 0
        self.identity_verified = False
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), RejectRedirects())

    def check_ownership(self) -> None:
        data = self.request("mapping")
        require(set(data) == {self.index} and isinstance(data[self.index], dict), "foreign_mapping")
        mappings = data[self.index].get("mappings")
        require(isinstance(mappings, dict) and mappings.get("_meta") == {
            "lab": MARKER, "scenario": self.scenario, "run_id": self.run_id,
        }, "ownership_mismatch")

    def validate_body(self, resource: str, body: Any) -> None:
        if resource == "index":
            require(body == index_definition(self.scenario, self.run_id), "index_body_refused")
        elif resource == "settings_update":
            allowed = {
                "allocation": [{"index": {"number_of_replicas": value}} for value in (0, 1)],
                "write-block": [{"index": {"blocks.read_only_allow_delete": value}} for value in (True, False)],
            }.get(self.scenario, [])
            require(body in allowed, "settings_body_refused")
        elif resource == "bulk":
            bad = {"doc_id": "a2", "value": "not-an-integer"}
            allowed = {
                "refresh": [bulk_create(DOCS)],
                "bulk-errors": [bulk_create([DOCS[0], bad, DOCS[0]]), bulk_create([DOCS[1]])],
                "write-block": [bulk_create([DOCS[0]])],
                "allocation": [bulk_create(DOCS)],
                "pagination": [bulk_create(PAGE_DOCS)],
            }[self.scenario]
            require(isinstance(body, bytes) and body in allowed, "bulk_body_refused")
        elif resource == "write_probe":
            require(self.scenario == "write-block" and body == DOCS[1], "write_body_refused")
        elif resource == "search":
            allowed_searches = [search_body(), search_body(deep=True)]
            allowed_searches += [search_body(after=document["doc_id"]) for document in PAGE_DOCS]
            require(body in allowed_searches, "search_body_refused")
        else:
            require(body is None, "unexpected_request_body")

    def request(self, resource: str, body: Any = None, *, expected: tuple[int, ...] = (200,)) -> dict[str, Any]:
        require(self.index == f"efl-os-incident-{self.scenario}-{self.run_id}" and
                RUN_ID.fullmatch(self.run_id) is not None, "invalid_index")
        path = "/" + urllib.parse.quote(self.index, safe="")
        routes = {
            "root": ("GET", "/", {}),
            "index": ("PUT", path, {"wait_for_active_shards": "1", "timeout": "3s"}),
            "mapping": ("GET", path + "/_mapping", {}),
            "settings": ("GET", path + "/_settings", {"flat_settings": "true", "include_defaults": "false"}),
            "settings_update": ("PUT", path + "/_settings", {"timeout": "3s"}),
            "bulk": ("POST", path + "/_bulk", {"refresh": "false", "timeout": "3s"}),
            "refresh": ("POST", path + "/_refresh", {}),
            "get_a1": ("GET", path + "/_doc/a1", {"realtime": "true"}),
            "get_a2": ("GET", path + "/_doc/a2", {"realtime": "true"}),
            "write_probe": ("PUT", path + "/_create/a2", {"refresh": "false", "timeout": "3s"}),
            "search": ("POST", path + "/_search", {"allow_partial_search_results": "false"}),
            "stats": ("GET", path + "/_stats/docs,indexing,search,refresh,store", {}),
            "health": ("GET", "/_cluster/health/" + self.index,
                       {"level": "indices", "wait_for_status": "yellow", "timeout": "3s"}),
            "allocation": ("POST", "/_cluster/allocation/explain", {}),
        }
        require(resource in routes, "route_refused")
        require(resource == "root" or self.identity_verified, "identity_not_verified")
        self.validate_body(resource, body)
        mutations = {"index", "settings_update", "bulk", "refresh", "write_probe"}
        if resource in mutations:
            require(self.step in ("prepare", "recover"), "read_only_step")
            if resource == "index":
                require(self.step == "prepare" and not self.created, "index_creation_refused")
            else:
                self.check_ownership()
        method, route, query = routes[resource]
        if resource == "allocation":
            require(self.scenario == "allocation", "allocation_route_refused")
            body = {"index": self.index, "shard": 0, "primary": False}
        payload = body if isinstance(body, bytes) else (
            json.dumps(body, allow_nan=False).encode("utf-8") if body is not None else None
        )
        require(payload is None or len(payload) <= MAX_PAYLOAD_BYTES, "payload_too_large")
        require(self.requests < MAX_REQUESTS, "request_budget_exceeded")
        self.requests += 1
        request = urllib.request.Request(
            ENDPOINT + route + ("?" + urllib.parse.urlencode(query) if query else ""),
            data=payload, method=method,
            headers={"Content-Type": "application/x-ndjson" if resource == "bulk" else "application/json",
                     "Accept": "application/json", "Accept-Encoding": "identity"},
        )
        try:
            try:
                response = self.opener.open(request, timeout=SOCKET_TIMEOUT_SECONDS)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                self.last_status = response.status
                require(not 300 <= response.status < 400, "redirect_refused")
                require(response.status in expected, "unexpected_http_status")
                require(response.headers.get("Content-Encoding", "identity").strip().lower() in ("", "identity"),
                        "response_encoding_refused")
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                require(content_type in ("application/json", "application/vnd.opensearch+json"), "response_not_json")
                length = response.headers.get("Content-Length")
                if length is not None:
                    require(length.isdigit() and int(length) <= MAX_RESPONSE_BYTES, "response_too_large")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                require(len(raw) <= MAX_RESPONSE_BYTES, "response_too_large")
                result = json.loads(raw.decode("utf-8"))
                require(isinstance(result, dict), "response_not_object")
                return result
        except LabFailure:
            raise
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError, RecursionError):
            raise LabFailure("transport_or_json_failure") from None


def settings(client: LocalClient) -> dict[str, Any]:
    data = client.request("settings")
    require(set(data) == {client.index} and isinstance(data[client.index], dict), "settings_target_mismatch")
    values = data[client.index].get("settings")
    require(isinstance(values, dict), "invalid_settings")
    keys = ("index.number_of_shards", "index.number_of_replicas", "index.refresh_interval",
            "index.blocks.read_only_allow_delete", "index.max_result_window")
    result = {key: values[key] for key in keys if key in values}
    require(all(isinstance(value, (str, bool, int)) for value in result.values()), "invalid_setting_value")
    return result


def update_settings(client: LocalClient, values: dict[str, Any]) -> None:
    require(client.request("settings_update", {"index": values}).get("acknowledged") is True,
            "settings_not_acknowledged")


def verify_get(client: LocalClient, document: dict[str, Any], *, found: bool) -> None:
    data = client.request("get_" + document["doc_id"], expected=(200,) if found else (404,))
    require(data.get("_index") == client.index and data.get("_id") == document["doc_id"] and
            data.get("found") is found, "get_result_mismatch")
    if found:
        require(data.get("_source") == document, "get_source_mismatch")


def verify_rows(data: dict[str, Any], client: LocalClient, expected_docs: list[dict[str, Any]], total: int) -> None:
    verify_shards(data)
    require(data.get("timed_out") is False and data.get("terminated_early") in (None, False), "search_incomplete")
    hits = data.get("hits")
    require(isinstance(hits, dict) and hits.get("total") == {"value": total, "relation": "eq"}, "wrong_total")
    rows = hits.get("hits")
    require(isinstance(rows, list) and len(rows) == len(expected_docs), "wrong_hit_count")
    for row, document in zip(rows, expected_docs):
        require(isinstance(row, dict) and row.get("_index") == client.index and
                row.get("_id") == document["doc_id"] and row.get("_source") == document and
                row.get("sort") == [document["doc_id"]], "wrong_hit_value_or_order")


def read_rows(client: LocalClient, documents: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> None:
    verify_rows(client.request("search", search_body()), client, list(documents), len(documents))


def verify_error(data: dict[str, Any], status: int, error_type: str, *, cause: str | None = None) -> None:
    error = data.get("error")
    require(data.get("status") == status and isinstance(error, dict) and error.get("type") == error_type,
            "expected_error_not_reproduced")
    if cause is not None:
        causes = error.get("root_cause")
        require(isinstance(causes, list) and any(isinstance(item, dict) and item.get("type") == cause
                                               for item in causes), "wrong_error_cause")


def stats(client: LocalClient) -> dict[str, Any]:
    data = client.request("stats")
    # An intentionally unassigned replica may not answer a stats broadcast.
    # Preserve the actual coverage rather than treating yellow as a failed API.
    shards = data.get("_shards")
    require(isinstance(shards, dict) and integer(shards.get("total"), 1) and
            integer(shards.get("successful"), 1) and shards["successful"] <= shards["total"] and
            shards.get("failed") == 0 and not shards.get("failures"), "stats_shard_failure")
    indices = data.get("indices")
    require(isinstance(indices, dict) and set(indices) == {client.index}, "stats_target_mismatch")
    require(isinstance(indices[client.index], dict), "invalid_index_stats")
    primaries = indices[client.index].get("primaries")
    require(isinstance(primaries, dict), "missing_primary_stats")
    fields = {"docs": ("count", "deleted"), "store": ("size_in_bytes",),
              "indexing": ("index_total", "index_failed", "index_time_in_millis"),
              "search": ("query_total", "query_time_in_millis"),
              "refresh": ("total", "total_time_in_millis")}
    result = {"shards.total": shards["total"], "shards.successful": shards["successful"], "shards.failed": 0}
    for group, names in fields.items():
        source = primaries.get(group)
        require(isinstance(source, dict), "missing_stats_group")
        for name in names:
            if name in source:
                require(integer(source[name]), "invalid_stats_value")
                result[group + "." + name] = source[name]
    return result


def allocation_evidence(client: LocalClient, *, recovered: bool) -> dict[str, Any]:
    health = client.request("health")
    require(health.get("timed_out") is False and health.get("number_of_nodes") == 1, "not_ready_single_node")
    indices = health.get("indices")
    require(isinstance(indices, dict) and set(indices) == {client.index}, "health_target_mismatch")
    target = indices[client.index]
    require(isinstance(target, dict) and target.get("active_primary_shards") == 1 and
            target.get("number_of_shards") == 1, "primary_not_ready")
    wanted = "green" if recovered else "yellow"
    require(target.get("status") == wanted and target.get("number_of_replicas") == (0 if recovered else 1)
            and target.get("unassigned_shards") == (0 if recovered else 1), "allocation_state_mismatch")
    result = {"index_status": wanted, "active_primary_shards": 1,
              "unassigned_shards": target["unassigned_shards"], "number_of_nodes": 1}
    if not recovered:
        explanation = client.request("allocation")
        require(explanation.get("index") == client.index and explanation.get("shard") == 0 and
                explanation.get("primary") is False and explanation.get("current_state") == "unassigned"
                and explanation.get("can_allocate") == "no", "allocation_explanation_mismatch")
        nodes = explanation.get("node_allocation_decisions")
        require(isinstance(nodes, list) and any(isinstance(node, dict) and
                isinstance(node.get("deciders"), list) and any(isinstance(decider, dict) and
                decider.get("decider") == "same_shard" and decider.get("decision") == "NO"
                for decider in node["deciders"]) for node in nodes), "same_shard_cause_not_found")
        result["blocking_decider"] = "same_shard"
    return result


def pagination_error(client: LocalClient) -> dict[str, Any]:
    data = client.request("search", search_body(deep=True), expected=(400,))
    verify_error(data, 400, "search_phase_execution_exception", cause="illegal_argument_exception")
    return {"http_status": 400, "error_type": "search_phase_execution_exception",
            "root_cause": "illegal_argument_exception", "from_plus_size": 10, "max_result_window": 5}


def paginate(client: LocalClient) -> dict[str, Any]:
    ids = []
    after = None
    for start in range(0, 20, 5):
        data = client.request("search", search_body(after=after))
        expected = list(PAGE_DOCS[start:start + 5])
        verify_rows(data, client, expected, 20)
        ids += [row["_id"] for row in data["hits"]["hits"]]
        after = data["hits"]["hits"][-1]["sort"][0]
    verify_rows(client.request("search", search_body(after=after)), client, [], 20)
    require(ids == [document["doc_id"] for document in PAGE_DOCS] and len(set(ids)) == 20,
            "pagination_missing_or_duplicate")
    return {"query_pattern": "search_after", "pages": 4, "unique_documents": 20,
            "ids": ids, "snapshot_isolation": False, "fixture_is_immutable": True}


def prepare(client: LocalClient) -> dict[str, Any]:
    created = client.request("index", index_definition(client.scenario, client.run_id))
    require(created.get("index") == client.index and created.get("acknowledged") is True and
            created.get("shards_acknowledged") is True, "index_creation_unconfirmed")
    client.created = True
    client.stage = "prepare_seed"
    if client.scenario == "bulk-errors":
        bad = {"doc_id": "a2", "value": "not-an-integer"}
        data = client.request("bulk", bulk_create([DOCS[0], bad, DOCS[0]]))
        verify_bulk(data, client.index, [("a1", 201, None), ("a2", 400, "mapper_parsing_exception"),
                                        ("a1", 409, "version_conflict_engine_exception")])
        verify_shards(client.request("refresh"))
        verify_get(client, DOCS[0], found=True)
        verify_get(client, DOCS[1], found=False)
        return {"bulk_http_status": 200, "bulk_errors": True, "item_statuses": [201, 400, 409],
                "error_types": ["mapper_parsing_exception", "version_conflict_engine_exception"],
                "successful_id": "a1", "missing_id": "a2"}
    documents = PAGE_DOCS if client.scenario == "pagination" else (
        (DOCS[0],) if client.scenario == "write-block" else DOCS
    )
    verify_bulk(client.request("bulk", bulk_create(documents)), client.index,
                [(document["doc_id"], 201, None) for document in documents])
    if client.scenario == "refresh":
        verify_get(client, DOCS[0], found=True)
        verify_get(client, DOCS[1], found=True)
        read_rows(client, [])
        require(settings(client).get("index.refresh_interval") == "-1", "refresh_interval_changed")
        return {"realtime_found": ["a1", "a2"], "search_count": 0, "refresh_interval": "-1"}
    verify_shards(client.request("refresh"))
    client.stage = "prepare_symptom"
    if client.scenario == "write-block":
        read_rows(client, [DOCS[0]])
        update_settings(client, {"blocks.read_only_allow_delete": True})
        data = client.request("write_probe", DOCS[1], expected=(403, 429))
        status = client.last_status
        verify_error(data, status, "cluster_block_exception")
        verify_get(client, DOCS[1], found=False)
        return {"http_status": status, "error_type": "cluster_block_exception",
                "block_injected": True, "physical_disk_full_reproduced": False}
    if client.scenario == "allocation":
        update_settings(client, {"number_of_replicas": 1})
        return allocation_evidence(client, recovered=False)
    return pagination_error(client)


def observe(client: LocalClient) -> dict[str, Any]:
    result: dict[str, Any] = {"settings": settings(client), "primary_stats": stats(client),
                              "stats_are_cumulative_or_point_in_time_not_rates": True}
    if client.scenario == "refresh":
        verify_get(client, DOCS[0], found=True)
        verify_get(client, DOCS[1], found=True)
        read_rows(client, [])
        result.update(realtime_found=["a1", "a2"], search_count=0)
    elif client.scenario == "bulk-errors":
        verify_get(client, DOCS[0], found=True)
        verify_get(client, DOCS[1], found=False)
        read_rows(client, [DOCS[0]])
        result.update(successful_id="a1", missing_id="a2", rejection_details="see prepare JSON; no bulk replay")
    elif client.scenario == "write-block":
        require(result["settings"].get("index.blocks.read_only_allow_delete") in ("true", True),
                "write_block_not_present")
        read_rows(client, [DOCS[0]])
        verify_get(client, DOCS[1], found=False)
        result.update(reads_work=True, missing_id="a2", rejection_details="see prepare JSON; no write probe")
    elif client.scenario == "allocation":
        result.update(allocation_evidence(client, recovered=False))
    else:
        require(str(result["settings"].get("index.max_result_window")) == "5", "result_window_changed")
        result.update(pagination_error(client))
    return result


def recover(client: LocalClient) -> dict[str, Any]:
    if client.scenario == "refresh":
        verify_shards(client.request("refresh"))
        return {"action": "explicit_index_refresh", "automatic_refresh_still_disabled": True}
    if client.scenario == "bulk-errors":
        verify_get(client, DOCS[0], found=True)
        verify_get(client, DOCS[1], found=False)
        verify_bulk(client.request("bulk", bulk_create([DOCS[1]])), client.index, [("a2", 201, None)])
        verify_shards(client.request("refresh"))
        return {"action": "retry_only_corrected_failed_document", "retried_ids": ["a2"]}
    if client.scenario == "write-block":
        update_settings(client, {"blocks.read_only_allow_delete": False})
        data = client.request("write_probe", DOCS[1], expected=(201,))
        require(data.get("_index") == client.index and data.get("_id") == "a2" and
                data.get("result") == "created", "write_not_recovered")
        verify_shards(data)
        verify_shards(client.request("refresh"))
        return {"action": "clear_only_fixture_block_and_retry", "written_id": "a2",
                "not_a_production_disk_pressure_remedy": True}
    if client.scenario == "allocation":
        update_settings(client, {"number_of_replicas": 0})
        return {"action": "restore_single_node_fixture_replica_count", "production_ha_restored": False}
    require(str(settings(client).get("index.max_result_window")) == "5", "result_window_changed")
    return paginate(client)


def verify(client: LocalClient) -> dict[str, Any]:
    values = settings(client)
    if client.scenario == "pagination":
        require(str(values.get("index.max_result_window")) == "5", "result_window_changed")
        pagination_error(client)
        return paginate(client)
    read_rows(client, DOCS)
    verify_get(client, DOCS[0], found=True)
    verify_get(client, DOCS[1], found=True)
    result: dict[str, Any] = {"exact_documents": list(DOCS), "search_count": 2}
    if client.scenario == "refresh":
        require(values.get("index.refresh_interval") == "-1", "refresh_interval_changed")
        result["automatic_refresh_still_disabled"] = True
    if client.scenario == "write-block":
        require(values.get("index.blocks.read_only_allow_delete") in ("false", False), "write_block_still_set")
        result["write_block"] = False
    if client.scenario == "allocation":
        result.update(allocation_evidence(client, recovered=True))
    return result


def run_step(client: LocalClient) -> dict[str, Any]:
    verify_identity(client.request("root"))
    client.identity_verified = True
    if client.step != "prepare":
        client.check_ownership()
    client.stage = client.step
    evidence = {"prepare": prepare, "observe": observe, "recover": recover, "verify": verify}[client.step](client)
    client.stage = "complete"
    return {
        "status": {"prepare": "PREPARED", "observe": "OBSERVED", "recover": "RECOVERED", "verify": "VERIFIED"}[client.step],
        "mode": "real_local_engine", "scenario": client.scenario, "step": client.step,
        "run_id": client.run_id, "index": client.index, "index_retained": True,
        "endpoint": ENDPOINT, "version": VERSION, "requests": client.requests,
        "evidence": evidence, "cleanup_performed": False,
        "not_verified": ["production throughput", "HA or failover", "physical disk pressure",
                         "security isolation", "concurrent-update pagination consistency"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List scenarios without network or file I/O.")
    parser.add_argument("--run-local", action="store_true", help="Explicitly opt in to local REST requests.")
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--step", choices=STEPS)
    parser.add_argument("--run-id", help="32 lowercase hex characters from prepare; forbidden for prepare.")
    args = parser.parse_args(argv)
    if args.list:
        if args.run_local or args.scenario or args.step or args.run_id:
            parser.error("--list cannot be combined with execution arguments. No HTTP request was sent.")
        print(json.dumps({"scenarios": list(SCENARIOS), "steps": list(STEPS), "network_access": False}, sort_keys=True))
        return 0
    if not args.run_local or not args.scenario or not args.step:
        parser.error("Provide --run-local, --scenario and --step. No HTTP request was sent.")
    if (args.step == "prepare" and args.run_id is not None) or (args.step != "prepare" and
            (args.run_id is None or RUN_ID.fullmatch(args.run_id) is None)):
        parser.error("prepare generates its ID; later steps require its 32-hex --run-id. No HTTP request was sent.")
    if sys.version_info < (3, 10):
        print(json.dumps({"status": "ERROR", "error": "python_3_10_required"}))
        return 1
    client = LocalClient(args.scenario, args.step, args.run_id)
    try:
        print(json.dumps(run_step(client), sort_keys=True))
        return 0
    except LabFailure as error:
        print(json.dumps({"status": "ERROR", "stage": client.stage, "error": str(error),
                          "scenario": client.scenario, "step": client.step,
                          "run_id": client.run_id, "index": client.index,
                          "index_creation_confirmed_this_process": client.created,
                          "requests": client.requests, "cleanup_performed": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
