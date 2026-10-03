"""Bounded security teaching models, NOT an OpenBao/Vault/Raft implementation.

Python 3.10+ standard library only. No files, network, subprocess, credentials,
cryptography or clocks are used. Callers supply explicit immutable model state.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import json
import re
from typing import Sequence


MAX_NUMBER = 2**63 - 1  # Teaching input bound, not a product's storage format.
CAPABILITIES = frozenset({"create", "read", "update", "patch", "delete", "list", "deny"})
PATH = re.compile(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/?", re.ASCII)
NODE_ID = re.compile(r"[a-z][a-z0-9-]*", re.ASCII)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def integer(value: int, name: str, minimum: int = 0) -> None:
    require(isinstance(value, int) and not isinstance(value, bool)
            and minimum <= value <= MAX_NUMBER,
            f"{name} must be an integer in [{minimum}, {MAX_NUMBER}]")


def exact_path(value: str) -> None:
    require(isinstance(value, str) and PATH.fullmatch(value) is not None,
            "path must be an explicit ASCII API path; no glob, template or normalization")


@dataclass(frozen=True)
class PolicyRule:
    path: str
    capabilities: frozenset[str]

    def __post_init__(self) -> None:
        exact_path(self.path)
        require(isinstance(self.capabilities, frozenset) and bool(self.capabilities),
                "capabilities must be a nonempty frozenset")
        require(self.capabilities <= CAPABILITIES, "unsupported capability")


@dataclass(frozen=True)
class ACLDecision:
    allowed: bool
    matched_rules: int
    effective_capabilities: tuple[str, ...]
    reason: str


def authorize(rules: Sequence[PolicyRule], path: str, capability: str) -> ACLDecision:
    """Union ONLY rules for the identical explicit path; deny wins in that union.

    Request paths must already be canonical API paths, including any LIST slash.
    No glob priority, path canonicalization, authn, root bypass, sudo, namespace,
    parameter constraints, identity templates or HTTP-to-capability inference.
    """
    require(isinstance(rules, (tuple, list)), "rules must be a tuple or list")
    require(all(isinstance(rule, PolicyRule) for rule in rules), "expected PolicyRule")
    exact_path(path)
    require(isinstance(capability, str) and capability in CAPABILITIES - {"deny"},
            "request must name one supported operation capability")
    matched = [rule for rule in rules if rule.path == path]
    caps = frozenset().union(*(rule.capabilities for rule in matched))
    if "deny" in caps:
        return ACLDecision(False, len(matched), ("deny",), "explicit-deny")
    allowed = capability in caps
    return ACLDecision(allowed, len(matched), tuple(sorted(caps)),
                       "granted" if allowed else "default-deny")


class CASMismatch(ValueError):
    """The model's mandatory check-and-set precondition failed."""


@dataclass(frozen=True)
class KVVersion:
    number: int
    value: str | None
    deleted: bool = False
    destroyed: bool = False

    def __post_init__(self) -> None:
        integer(self.number, "version", 1)
        require(isinstance(self.deleted, bool) and isinstance(self.destroyed, bool),
                "version flags must be boolean")
        require((self.destroyed and self.value is None and not self.deleted)
                or (not self.destroyed and isinstance(self.value, str)),
                "destroyed means no payload; nondestroyed payload must be text")


@dataclass(frozen=True)
class KVState:
    versions: tuple[KVVersion, ...] = ()

    def __post_init__(self) -> None:
        require(isinstance(self.versions, tuple), "history must be an immutable tuple")
        for number, version in enumerate(self.versions, 1):
            require(isinstance(version, KVVersion) and version.number == number,
                    "history must contain consecutive versions starting at 1")

    @property
    def current_version(self) -> int:
        return len(self.versions)


def kv_write(state: KVState, value: str, cas: int) -> KVState:
    """Mandatory CAS; zero creates only an absent key, positive matches metadata."""
    require(isinstance(state, KVState), "expected KVState")
    require(isinstance(value, str), "payload must be public synthetic text")
    integer(cas, "cas")
    if cas != state.current_version:
        raise CASMismatch("CAS does not match current metadata version")
    next_version = state.current_version + 1
    integer(next_version, "next version", 1)
    return KVState(state.versions + (KVVersion(next_version, value),))


def kv_read(state: KVState, version: int | None = None) -> str | None:
    """None means no readable payload, not a simulated HTTP error/status code."""
    require(isinstance(state, KVState), "expected KVState")
    if version is None:
        version = state.current_version
    else:
        integer(version, "version", 1)
    if version == 0 or version > state.current_version:
        return None
    item = state.versions[version - 1]
    return None if item.deleted or item.destroyed else item.value


def change_versions(state: KVState, versions: Sequence[int], operation: str) -> KVState:
    """Strict teaching transition; no metadata deletion or automatic pruning.

    Unknown versions and undelete of destroyed versions are rejected deliberately;
    this validation contract does not reproduce product HTTP error/no-op behavior.
    """
    require(isinstance(state, KVState), "expected KVState")
    require(isinstance(versions, (tuple, list)) and bool(versions), "versions must be nonempty")
    require(isinstance(operation, str) and operation in {"delete", "undelete", "destroy"},
            "unsupported version operation")
    for number in versions:
        integer(number, "selected version", 1)
        require(number <= state.current_version, "unknown version")
    require(len(set(versions)) == len(versions), "duplicate selected version")
    selected = frozenset(versions)
    if operation == "undelete":
        require(all(not item.destroyed for item in state.versions if item.number in selected),
                "destroyed payload cannot be undeleted")
    changed = []
    for item in state.versions:
        if item.number in selected:
            if operation == "destroy":
                item = KVVersion(item.number, None, destroyed=True)
            elif not item.destroyed:
                item = replace(item, deleted=operation == "delete")
        changed.append(item)
    return KVState(tuple(changed))


@dataclass(frozen=True)
class Lease:
    issued_at: int
    now: int
    expires_at: int
    max_expires_at: int
    renewable: bool = True
    revocation: str = "active"
    attempts: int = 0

    def __post_init__(self) -> None:
        for name in ("issued_at", "now", "expires_at", "max_expires_at", "attempts"):
            integer(getattr(self, name), name)
        require(self.issued_at <= self.now and self.issued_at < self.expires_at <= self.max_expires_at,
                "inconsistent lease lifetime")
        require(isinstance(self.renewable, bool), "renewable must be boolean")
        require(isinstance(self.revocation, str) and self.revocation in {"active", "pending", "complete"},
                "invalid revocation state")
        require(self.revocation != "active" or (self.now < self.expires_at and self.attempts == 0),
                "active lease must be unexpired and have no revocation attempt")
        require(self.revocation != "complete" or self.attempts > 0,
                "complete revocation requires a successful attempt")


def issue_lease(now: int, ttl: int, max_ttl: int, renewable: bool = True) -> Lease:
    integer(now, "now")
    integer(ttl, "ttl", 1)
    integer(max_ttl, "max_ttl", 1)
    require(ttl <= max_ttl, "initial ttl must not exceed max_ttl")
    integer(now + max_ttl, "maximum expiry")
    return Lease(now, now, now + ttl, now + max_ttl, renewable)


def advance_lease(lease: Lease, now: int) -> Lease:
    require(isinstance(lease, Lease), "expected Lease")
    integer(now, "now")
    require(now >= lease.now, "model clock cannot move backward")
    pending = lease.revocation == "active" and now >= lease.expires_at
    return replace(lease, now=now, revocation="pending" if pending else lease.revocation)


def renew_lease(lease: Lease, increment: int) -> Lease:
    """Granted TTL starts at current model time, not at the previous expiry.

    The model fixes the maximum at issuance. Real grants additionally depend on
    current role/mount/system settings and backend responses; periodic/batch
    tokens, parent revocation, auth sessions and external clocks are not modeled.
    """
    require(isinstance(lease, Lease), "expected Lease")
    integer(increment, "increment", 1)
    require(lease.renewable and lease.revocation == "active", "lease cannot be renewed")
    return replace(lease, expires_at=min(lease.now + increment, lease.max_expires_at))


def revoke_lease(lease: Lease) -> Lease:
    require(isinstance(lease, Lease), "expected Lease")
    return replace(lease, revocation="pending") if lease.revocation == "active" else lease


def attempt_revocation(lease: Lease, success: bool) -> Lease:
    require(isinstance(lease, Lease), "expected Lease")
    require(isinstance(success, bool), "success must be boolean")
    require(lease.revocation == "pending", "only a pending lease may retry revocation")
    return replace(lease, attempts=lease.attempts + 1,
                   revocation="complete" if success else "pending")


def lease_usable(lease: Lease) -> bool:
    """Whether a cooperative model client should keep using the lease.

    This does not enforce authorization at the external credential's backend.
    """
    require(isinstance(lease, Lease), "expected Lease")
    return lease.revocation == "active"


def backend_credential_usable(lease: Lease) -> bool:
    """Assume a backend credential with NO independent expiry until revocation.

    This is a counterexample assumption, not the behavior of every DB/cloud
    credential. Existing connections and permissions cached by clients are out
    of scope even after the model records successful credential revocation.
    """
    require(isinstance(lease, Lease), "expected Lease")
    return lease.revocation != "complete"


@dataclass(frozen=True)
class Member:
    node_id: str
    voting: bool = True

    def __post_init__(self) -> None:
        require(isinstance(self.node_id, str) and NODE_ID.fullmatch(self.node_id) is not None,
                "node ID must be a lowercase ASCII identifier")
        require(isinstance(self.voting, bool), "voting must be boolean")


@dataclass(frozen=True)
class Quorum:
    voters: int
    reachable_voters: int
    required_votes: int
    has_voting_majority: bool
    maximum_unavailable_voters: int


def validate_members(members: Sequence[Member]) -> None:
    require(isinstance(members, (tuple, list)) and bool(members), "membership must be nonempty")
    require(all(isinstance(member, Member) for member in members), "expected Member")
    require(len({member.node_id for member in members}) == len(members), "duplicate node ID")
    require(any(member.voting for member in members), "at least one voter is required")


def quorum(members: Sequence[Member], reachable: frozenset[str]) -> Quorum:
    """Count a fixed membership's votes in a mutually connected live component.

    A majority is a necessary numerical condition, NOT a proof that a leader
    exists, a write committed, a read is linearizable, or a snapshot is safe.
    """
    validate_members(members)
    require(isinstance(reachable, frozenset), "reachable IDs must be a frozenset")
    known = {member.node_id for member in members}
    require(reachable <= known, "unknown reachable member")
    voters = sum(member.voting for member in members)
    present = sum(member.voting and member.node_id in reachable for member in members)
    required = voters // 2 + 1
    return Quorum(voters, present, required, present >= required, voters - required)


def partition_quorums(members: Sequence[Member], components: Sequence[frozenset[str]]) -> tuple[Quorum, ...]:
    validate_members(members)
    require(isinstance(components, (tuple, list)) and bool(components), "components must be nonempty")
    seen: set[str] = set()
    results = []
    for component in components:
        require(isinstance(component, frozenset) and bool(component), "component must be a nonempty frozenset")
        require(not seen.intersection(component), "partition components must be disjoint")
        results.append(quorum(members, component))
        seen.update(component)
    require(seen == {member.node_id for member in members}, "partition must cover every member")
    return tuple(results)


def exact_acl_lab() -> dict:
    rules = (
        PolicyRule("secret/data/apps/payments", frozenset({"read"})),
        PolicyRule("secret/data/apps/payments", frozenset({"update"})),
        PolicyRule("secret/metadata/apps/", frozenset({"list"})),
        PolicyRule("secret/data/apps/admin", frozenset({"read"})),
        PolicyRule("secret/data/apps/admin", frozenset({"deny"})),
    )
    requests = (("secret/data/apps/payments", "read"), ("secret/data/apps/payments", "update"),
                ("secret/data/apps/payments", "delete"), ("secret/metadata/apps/", "list"),
                ("secret/metadata/apps/payments", "read"), ("secret/data/apps/admin", "read"),
                ("secret/data/apps/payments/child", "read"))
    allowed = [authorize(rules, path, capability).allowed for path, capability in requests]
    require(allowed == [True, True, False, True, False, False, False], "ACL oracle failed")
    return {"lab": "exact-acl", "status": "PASS", "allowed_in_request_order": allowed,
            "admin_reason": authorize(rules, "secret/data/apps/admin", "read").reason,
            "model": "exact paths only; no wildcard precedence or authentication"}


def kv_cas_lab() -> dict:
    first = kv_write(KVState(), "public-v1", 0)
    second = kv_write(first, "public-v2", 1)
    try:
        kv_write(second, "stale-writer", 1)
    except CASMismatch:
        stale_rejected = True
    else:
        stale_rejected = False
    deleted = change_versions(second, (2,), "delete")
    restored = change_versions(deleted, (2,), "undelete")
    destroyed = change_versions(restored, (1,), "destroy")
    third = kv_write(destroyed, "public-v3", 2)
    require(stale_rejected and kv_read(deleted) is None and kv_read(restored) == "public-v2"
            and kv_read(destroyed, 1) is None and third.current_version == 3
            and kv_read(first) == "public-v1", "KV oracle failed")
    return {"lab": "kv-cas", "status": "PASS", "stale_cas_rejected": stale_rejected,
            "current_versions": [first.current_version, second.current_version, deleted.current_version,
                                 restored.current_version, destroyed.current_version, third.current_version],
            "latest_after_soft_delete": kv_read(deleted), "latest_after_undelete": kv_read(restored),
            "version_1_after_destroy": kv_read(destroyed, 1), "latest_after_next_cas": kv_read(third),
            "model": "immutable synthetic history; no engine storage or payload erasure guarantee"}


def lease_clock_lab() -> dict:
    first = issue_lease(0, 10, 25)
    second = renew_lease(advance_lease(first, 6), 10)
    third = renew_lease(advance_lease(second, 15), 20)
    expired = advance_lease(third, 25)
    failed = attempt_revocation(expired, False)
    complete = attempt_revocation(failed, True)
    expiry_pair = [lease_usable(expired), backend_credential_usable(expired)]
    failed_pair = [lease_usable(failed), backend_credential_usable(failed)]
    complete_pair = [lease_usable(complete), backend_credential_usable(complete)]
    require([first.expires_at, second.expires_at, third.expires_at] == [10, 16, 25]
            and expiry_pair == [False, True] and failed_pair == [False, True]
            and complete_pair == [False, False] and complete.attempts == 2, "lease oracle failed")
    return {"lab": "lease-clock", "status": "PASS", "expiry_times": [10, 16, 25],
            "at_expiry_lease_and_backend_usable": expiry_pair,
            "after_failed_revoke_lease_and_backend_usable": failed_pair,
            "after_successful_revoke_lease_and_backend_usable": complete_pair,
            "revocation_attempts": complete.attempts,
            "model": "ordinary bounded lease; backend has no independent expiry"}


def raft_quorum_lab() -> dict:
    three = tuple(Member(node) for node in ("a", "b", "c"))
    five = tuple(Member(node) for node in ("a", "b", "c", "d", "e"))
    split_three = partition_quorums(three, (frozenset({"a", "b"}), frozenset({"c"})))
    split_five = partition_quorums(five, (frozenset({"a", "b", "c"}), frozenset({"d", "e"})))
    with_nonvoter = quorum(three + (Member("learner", False),), frozenset({"a", "learner"}))
    require([item.has_voting_majority for item in split_three] == [True, False]
            and [item.has_voting_majority for item in split_five] == [True, False]
            and not with_nonvoter.has_voting_majority, "quorum oracle failed")
    return {"lab": "raft-quorum", "status": "PASS", "required_votes_for_3_and_5": [2, 3],
            "maximum_unavailable_voters_for_3_and_5": [1, 2],
            "split_2_1_majorities": [item.has_voting_majority for item in split_three],
            "split_3_2_majorities": [item.has_voting_majority for item in split_five],
            "one_voter_plus_nonvoter_has_majority": with_nonvoter.has_voting_majority,
            "model": "static connected components; no election, log, reads or membership changes"}


LABS = {"exact-acl": exact_acl_lab, "kv-cas": kv_cas_lab,
        "lease-clock": lease_clock_lab, "raft-quorum": raft_quorum_lab}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--list", action="store_true", help="list model names")
    selection.add_argument("--lab", choices=[*LABS, "all"], help="run one or all deterministic models")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(LABS))
    elif args.lab:
        results = [function() for function in LABS.values()] if args.lab == "all" else [LABS[args.lab]()]
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
