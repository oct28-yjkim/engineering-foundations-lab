"""CPU-only teaching models, not Terraform/Terragrunt or a backend implementation.

Python 3.10+; standard library only; no filesystem, network or subprocess access.
The synthetic plan format is deliberately smaller than Terraform's JSON schema.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from typing import Mapping


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def identifier(value: object, label: str) -> None:
    require(isinstance(value, str) and bool(value) and value == value.strip(),
            f"{label} must be a nonempty, trimmed string")


def name_set(values: object, label: str) -> frozenset[str]:
    require(isinstance(values, (list, tuple, set, frozenset)),
            f"{label} must be a collection, not a string")
    for value in values:
        identifier(value, label)
    require(len(values) == len(set(values)), f"{label} contains duplicates")
    return frozenset(values)


def normalize_graph(graph: Mapping[str, object]) -> dict[str, frozenset[str]]:
    require(isinstance(graph, Mapping), "graph must be a mapping")
    result = {}
    for unit, dependencies in graph.items():
        identifier(unit, "unit")
        result[unit] = name_set(dependencies, f"dependencies of {unit}")
    for unit, dependencies in result.items():
        require(dependencies <= result.keys(), f"{unit} references a missing unit")
    return result


def topological_layers(graph: Mapping[str, object]) -> tuple[tuple[str, ...], ...]:
    """Edges are unit -> prerequisite. Layers express eligibility, not timing."""
    dependencies = normalize_graph(graph)
    remaining, complete, layers = set(dependencies), set(), []
    while remaining:
        ready = tuple(sorted(unit for unit in remaining if dependencies[unit] <= complete))
        require(bool(ready), "dependency cycle detected")
        layers.append(ready)
        complete.update(ready)
        remaining.difference_update(ready)
    return tuple(layers)


def simulate_run(graph: Mapping[str, object], failures: object = ()) -> dict[str, str]:
    """An injected failure applies only if the unit is eligible to execute."""
    dependencies = normalize_graph(graph)
    failed = name_set(failures, "failures")
    require(failed <= dependencies.keys(), "unknown failure unit")
    status = {}
    for layer in topological_layers(dependencies):
        for unit in layer:
            if any(status[parent] != "SUCCEEDED" for parent in dependencies[unit]):
                status[unit] = "BLOCKED"
            else:
                status[unit] = "FAILED" if unit in failed else "SUCCEEDED"
    return status


def validate_json(value: object, depth: int = 0) -> None:
    require(depth <= 30, "synthetic JSON exceeds the supported nesting depth")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        require(math.isfinite(value), "JSON numbers must be finite")
        return
    if isinstance(value, list):
        for child in value:
            validate_json(child, depth + 1)
        return
    require(isinstance(value, dict), "unsupported JSON value")
    for key, child in value.items():
        require(isinstance(key, str), "JSON keys must be strings")
        validate_json(child, depth + 1)


def validate_marker(value: object, depth: int = 0) -> None:
    require(depth <= 30, "marker exceeds the supported nesting depth")
    if isinstance(value, bool):
        return
    require(isinstance(value, (dict, list)), "markers must contain booleans, maps or lists")
    if isinstance(value, dict):
        require(all(isinstance(key, str) for key in value), "marker keys must be strings")
        children = value.values()
    else:
        children = value
    for child in children:
        validate_marker(child, depth + 1)


def marker_has_true(value: object) -> bool:
    if isinstance(value, bool):
        return value
    children = value.values() if isinstance(value, dict) else value
    return any(marker_has_true(child) for child in children)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reasons: tuple[str, ...]
    destructive_addresses: tuple[str, ...]
    sensitive_addresses: tuple[str, ...]


SUPPORTED_ACTIONS = frozenset({
    ("no-op",), ("read",), ("create",), ("update",), ("delete",),
    ("delete", "create"), ("create", "delete"),
})


def evaluate_plan(plan: object, *, allowed_env: str = "lab",
                  allowed_regions: object = ("local",)) -> PolicyDecision:
    """Fail closed for this *synthetic subset*, not a production plan parser.

    Required identity fields are flat, scalar `env` and `region` on `after`.
    Delete/replacement always violates this teaching policy. Malformed or
    unsupported input raises ValueError, and must never be treated as approval.
    """
    identifier(allowed_env, "allowed_env")
    regions = name_set(allowed_regions, "allowed_regions")
    require(bool(regions), "at least one allowed region is required")
    require(isinstance(plan, dict) and set(plan) == {"resource_changes"},
            "only the synthetic resource_changes envelope is supported")
    changes = plan["resource_changes"]
    require(isinstance(changes, list), "resource_changes must be a list")
    seen, validated = set(), []
    for resource in changes:
        require(isinstance(resource, dict) and set(resource) == {"address", "change"},
                "each synthetic resource needs exactly address and change")
        address = resource["address"]
        identifier(address, "address")
        require(address not in seen, "duplicate resource address")
        seen.add(address)
        change = resource["change"]
        require(isinstance(change, dict) and set(change) == {
            "actions", "after", "after_unknown", "after_sensitive"},
            "synthetic change requires actions, after, after_unknown and after_sensitive")
        actions = change["actions"]
        require(isinstance(actions, list) and all(isinstance(item, str) for item in actions),
                "actions must be a list of strings")
        require(tuple(actions) in SUPPORTED_ACTIONS, "unsupported action sequence")
        after = change["after"]
        require(after is None or isinstance(after, dict), "after must be an object or null")
        validate_json(after)
        for field in ("after_unknown", "after_sensitive"):
            marker = change[field]
            require(isinstance(marker, (bool, dict)), f"{field} must be a boolean or map")
            validate_marker(marker)
            if isinstance(marker, dict):
                for identity in ("env", "region"):
                    require(isinstance(marker.get(identity, False), bool),
                            f"{field}.{identity} must be a scalar boolean")
        if actions == ["delete"]:
            require(after is None, "pure delete must have after=null in this subset")
        validated.append((address, change))

    reasons, destructive, sensitive = [], [], []
    for address, change in sorted(validated, key=lambda row: row[0]):
        if "delete" in change["actions"]:
            destructive.append(address)
            reasons.append(f"{address}: delete/replacement denied")
        if marker_has_true(change["after_sensitive"]):
            sensitive.append(address)
        if change["actions"] == ["delete"]:
            continue
        after, unknown = change["after"] or {}, change["after_unknown"]
        for identity in ("env", "region"):
            is_unknown = unknown if isinstance(unknown, bool) else unknown.get(identity, False)
            if is_unknown:
                reasons.append(f"{address}: {identity} is unknown")
                continue
            value = after.get(identity)
            if not isinstance(value, str) or not value:
                reasons.append(f"{address}: {identity} is missing or not a string")
            elif (identity == "env" and value != allowed_env) or (
                    identity == "region" and value not in regions):
                reasons.append(f"{address}: {identity} is outside the permitted scope")
    return PolicyDecision(not reasons, tuple(reasons), tuple(destructive), tuple(sensitive))


@dataclass(frozen=True)
class StateSnapshot:
    lineage: str
    serial: int
    resources: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        identifier(self.lineage, "lineage")
        require(isinstance(self.serial, int) and not isinstance(self.serial, bool)
                and self.serial >= 0, "serial must be a nonnegative integer")
        require(isinstance(self.resources, tuple), "resources must be an immutable tuple")
        seen = set()
        for pair in self.resources:
            require(isinstance(pair, tuple) and len(pair) == 2,
                    "resource entries must be immutable key/value pairs")
            key, value = pair
            identifier(key, "resource key")
            require(isinstance(value, str), "resource values must be strings in this model")
            require(key not in seen, "duplicate resource key")
            seen.add(key)


@dataclass(frozen=True)
class LockToken:
    state_id: str
    owner: str
    generation: int

    def __post_init__(self) -> None:
        identifier(self.state_id, "lock state_id")
        identifier(self.owner, "lock owner")
        require(isinstance(self.generation, int) and not isinstance(self.generation, bool)
                and self.generation > 0, "lock generation must be a positive integer")


class MemoryStateStore:
    """Single-process illustrative CAS. No authentication, persistence or leases.

    A state_id models explicit state identity, not a directory or an IAM boundary.
    Expected lineage + serial are the CAS token; resource payload is not compared.
    """

    def __init__(self, snapshots: Mapping[str, StateSnapshot]):
        require(isinstance(snapshots, Mapping), "snapshots must be a mapping")
        for state_id, snapshot in snapshots.items():
            identifier(state_id, "state_id")
            require(isinstance(snapshot, StateSnapshot), "snapshot type is required")
        self._snapshots = dict(snapshots)
        self._locks: dict[str, LockToken] = {}
        self._generations = {state_id: 0 for state_id in snapshots}

    def read(self, state_id: str) -> StateSnapshot:
        identifier(state_id, "state_id")
        require(state_id in self._snapshots, "unknown state_id")
        return self._snapshots[state_id]

    def acquire(self, state_id: str, owner: str) -> LockToken:
        self.read(state_id)
        identifier(owner, "owner")
        require(state_id not in self._locks, "state already locked")
        self._generations[state_id] += 1
        token = LockToken(state_id, owner, self._generations[state_id])
        self._locks[state_id] = token
        return token

    def _require_lock(self, state_id: str, token: LockToken) -> None:
        require(isinstance(token, LockToken), "lock token is required")
        require(token.state_id == state_id and self._locks.get(state_id) == token,
                "lock ownership/generation mismatch")

    def release(self, token: LockToken) -> None:
        require(isinstance(token, LockToken), "lock token is required")
        self._require_lock(token.state_id, token)
        del self._locks[token.state_id]

    def compare_and_swap(self, state_id: str, expected: StateSnapshot,
                         replacement: StateSnapshot, token: LockToken) -> StateSnapshot:
        current = self.read(state_id)
        self._require_lock(state_id, token)
        require(isinstance(expected, StateSnapshot) and isinstance(replacement, StateSnapshot),
                "expected and replacement must be immutable snapshots")
        require(expected.lineage == current.lineage, "expected lineage mismatch")
        require(expected.serial == current.serial, "stale expected serial")
        require(replacement.lineage == current.lineage, "replacement cannot change lineage")
        require(replacement.serial == current.serial + 1, "replacement must increment serial by one")
        self._snapshots[state_id] = replacement
        return replacement


@dataclass(frozen=True)
class ScopePlan:
    changed: frozenset[str]
    affected: frozenset[str]
    dependency_closure: frozenset[str]
    external_dependencies: frozenset[str]
    selected_for_execution: frozenset[str]
    assumed_ready: frozenset[str]


def plan_scope(graph: Mapping[str, object], changed: object,
               *, external_decision: str | None = None) -> ScopePlan:
    """Model-only selection; assume-ready requires evidence outside this model."""
    dependencies = normalize_graph(graph)
    topological_layers(dependencies)
    selected = name_set(changed, "changed units")
    require(selected <= dependencies.keys(), "unknown changed unit")
    require(external_decision in (None, "include", "assume-ready"),
            "external_decision must be include or assume-ready")
    affected = set(selected)
    while True:
        additions = {unit for unit, parents in dependencies.items() if parents & affected}
        if additions <= affected:
            break
        affected.update(additions)
    closure = set(affected)
    while True:
        additions = set().union(*(dependencies[unit] for unit in closure)) if closure else set()
        if additions <= closure:
            break
        closure.update(additions)
    external = closure - affected
    require(not external or external_decision is not None,
            "unchanged external dependencies need an explicit decision")
    assumed = external if external_decision == "assume-ready" else set()
    execution = affected if assumed else closure
    return ScopePlan(selected, frozenset(affected), frozenset(closure), frozenset(external),
                     frozenset(execution), frozenset(assumed))


def graph_lab() -> dict:
    graph = {"network": [], "database": ["network"], "api": ["database"],
             "telemetry": [], "dashboard": ["telemetry"]}
    layers = topological_layers(graph)
    status = simulate_run(graph, ["database"])
    require(layers == (("network", "telemetry"), ("dashboard", "database"), ("api",)),
            "unexpected eligibility layers")
    require(status == {"network": "SUCCEEDED", "telemetry": "SUCCEEDED",
                       "dashboard": "SUCCEEDED", "database": "FAILED", "api": "BLOCKED"},
            "failure propagation differs from the literal oracle")
    return {"status": "PASS", "layers": layers, "outcomes": status,
            "scope": "dependency teaching model, not the Terragrunt run queue"}


def synthetic_change(address: str, actions: list[str], *, env: str = "lab",
                     region: str = "local", unknown: bool = False, sensitive: bool = False) -> dict:
    return {"address": address, "change": {
        "actions": list(actions),
        "after": None if actions == ["delete"] else {"env": env, "region": region},
        "after_unknown": {"region": unknown}, "after_sensitive": {"env": sensitive}}}


def plan_policy_lab() -> dict:
    safe = evaluate_plan({"resource_changes": [synthetic_change("demo.safe", ["create"], sensitive=True)]})
    unsafe = evaluate_plan({"resource_changes": [
        synthetic_change("demo.replace_a", ["delete", "create"]),
        synthetic_change("demo.replace_b", ["create", "delete"]),
        synthetic_change("demo.unknown", ["create"], unknown=True),
    ]})
    require(safe.allowed and safe.sensitive_addresses == ("demo.safe",), "safe policy oracle failed")
    require(not unsafe.allowed and unsafe.destructive_addresses == ("demo.replace_a", "demo.replace_b"),
            "both replacement orderings must be detected")
    require(unsafe.reasons == ("demo.replace_a: delete/replacement denied",
                               "demo.replace_b: delete/replacement denied",
                               "demo.unknown: region is unknown"), "policy reason oracle failed")
    return {"status": "PASS", "known_scoped_create": "ALLOW", "unsafe_plan": "DENY",
            "reasons": unsafe.reasons, "sensitive_marker_is_encryption": False,
            "scope": "synthetic subset; ALLOW is not approval or live-infrastructure proof"}


def state_cas_lab() -> dict:
    original = StateSnapshot("lineage-network", 0, (("network", "before"),))
    database = StateSnapshot("lineage-database", 0)
    store = MemoryStateStore({"tenant-a/network": original, "tenant-a/database": database})
    token = store.acquire("tenant-a/network", "runner-a")
    updated = StateSnapshot("lineage-network", 1, (("network", "after"),))
    store.compare_and_swap("tenant-a/network", original, updated, token)
    rejected = []
    for label, expected in (("stale", original), ("wrong-lineage", StateSnapshot("other", 1))):
        try:
            store.compare_and_swap("tenant-a/network", expected,
                                   StateSnapshot("lineage-network", 2), token)
        except ValueError:
            rejected.append(label)
    store.release(token)
    db_token = store.acquire("tenant-a/database", "runner-a")
    try:
        store.compare_and_swap("tenant-a/database", database,
                               StateSnapshot("lineage-database", 2), db_token)
    except ValueError:
        rejected.append("second-state-apply")
    finally:
        store.release(db_token)
    require(rejected == ["stale", "wrong-lineage", "second-state-apply"], "CAS rejection oracle failed")
    require(store.read("tenant-a/network") == updated and store.read("tenant-a/database") == database,
            "partial multi-state outcome oracle failed")
    require(original.resources == (("network", "before"),) and original.serial == 0,
            "input snapshot was mutated")
    return {"status": "PASS", "rejected": rejected, "state_serials": {"network": 1, "database": 0},
            "multi_state_atomic": False, "scope": "single-process model, not a backend protocol"}


def blast_radius_lab() -> dict:
    graph = {"network": [], "identity": [], "database": ["network"],
             "api": ["database", "identity"], "worker": ["database"], "docs": []}
    scope = plan_scope(graph, ["database"], external_decision="include")
    require(scope.affected == frozenset({"database", "api", "worker"}), "dependent closure oracle failed")
    require(scope.external_dependencies == frozenset({"network", "identity"}), "ancestor closure oracle failed")
    require(scope.selected_for_execution == frozenset({"database", "api", "worker", "network", "identity"}),
            "execution selection oracle failed")
    return {"status": "PASS", "naive_changed_only": ["database"], "affected": sorted(scope.affected),
            "external_dependencies": sorted(scope.external_dependencies),
            "selected_for_execution": sorted(scope.selected_for_execution), "external_decision": "include",
            "scope": "declared edges only; directories are not state identity or security boundaries"}


LABS = {"graph": graph_lab, "plan-policy": plan_policy_lab,
        "state-cas": state_cas_lab, "blast-radius": blast_radius_lab}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab", choices=[*LABS, "all"], default="all")
    args = parser.parse_args(argv)
    names = list(LABS) if args.lab == "all" else [args.lab]
    for name in names:
        print(json.dumps({"lab": name, **LABS[name]()}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
