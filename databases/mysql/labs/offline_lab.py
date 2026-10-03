"""Four deterministic MySQL-inspired teaching models, NOT a database engine.

Python 3.10+ standard library; no files, network, subprocess or credentials.
Logical work, visibility, record wait graphs and durable evidence are separate
models. They do not measure InnoDB pages, locks, fsync or actual crash recovery.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from dataclasses import asdict, dataclass
import json
from typing import Mapping, Sequence


MAX_ID = 2**63 - 1  # An explicit teaching input bound, NOT InnoDB's ID format.


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def integer(value: int, name: str, minimum: int = 0) -> None:
    require(isinstance(value, int) and not isinstance(value, bool)
            and minimum <= value <= MAX_ID, f"{name} must be an integer in [{minimum}, {MAX_ID}]")


def text(value: str, name: str) -> None:
    require(isinstance(value, str) and bool(value), f"{name} must be nonempty text")


def sequence(value: object, name: str) -> None:
    require(isinstance(value, (tuple, list)), f"{name} must be a list or tuple")


@dataclass(frozen=True)
class Row:
    pk: int
    tenant: str
    score: int
    payload: str


@dataclass(frozen=True)
class LookupResult:
    rows: tuple[tuple[object, ...], ...]
    secondary_entries: int
    clustered_lookups: int
    covering: bool


def index_lookup(rows: Sequence[Row], tenant: str, low: int, high: int,
                 projection: Sequence[str]) -> LookupResult:
    """Model a (tenant, score, PK) secondary index and optional PK lookups.

    Counts exclude validation, index construction and range-bound search. They
    count only matching leaf tuples and logical clustered record fetches, NOT
    Python operations, B+tree levels, pages, buffer misses or physical I/O.
    """
    sequence(rows, "rows")
    text(tenant, "tenant")
    integer(low, "low", -MAX_ID)
    integer(high, "high", -MAX_ID)
    require(low <= high, "low must not exceed high")
    sequence(projection, "projection")
    require(bool(projection), "projection must not be empty")
    for column in projection:
        require(isinstance(column, str) and column in {"pk", "tenant", "score", "payload"},
                "unsupported projection column")
    require(len(set(projection)) == len(projection), "duplicate projection column")
    primary = {}
    for row in rows:
        require(isinstance(row, Row), "expected Row")
        integer(row.pk, "pk", 1)
        text(row.tenant, "row tenant")
        integer(row.score, "score", -MAX_ID)
        require(isinstance(row.payload, str), "payload must be text")
        require(row.pk not in primary, "duplicate primary key")
        primary[row.pk] = row
    secondary = sorted((row.tenant, row.score, row.pk) for row in rows)
    left = bisect_left(secondary, (tenant, low, 0))
    right = bisect_right(secondary, (tenant, high, MAX_ID))
    covering = "payload" not in projection
    results = []
    for owner, score, pk in secondary[left:right]:
        values = {"pk": pk, "tenant": owner, "score": score}
        if not covering:
            values["payload"] = primary[pk].payload
        results.append(tuple(values[column] for column in projection))
    count = right - left
    return LookupResult(tuple(results), count, 0 if covering else count, covering)


@dataclass(frozen=True)
class ReadView:
    creator_id: int
    up_limit_id: int
    low_limit_id: int
    active_ids: frozenset[int]


def validate_view(view: ReadView) -> None:
    require(isinstance(view, ReadView), "expected ReadView")
    integer(view.creator_id, "creator_id")
    integer(view.low_limit_id, "low_limit_id", 1)
    integer(view.up_limit_id, "up_limit_id", 1)
    require(view.creator_id < view.low_limit_id, "creator must precede next unallocated ID")
    require(isinstance(view.active_ids, frozenset), "active_ids must be immutable")
    for trx_id in view.active_ids:
        integer(trx_id, "active transaction ID", 1)
        require(trx_id < view.low_limit_id and trx_id != view.creator_id,
                "active IDs must precede low_limit and exclude creator")
    expected_up = min(view.active_ids, default=view.low_limit_id)
    require(view.up_limit_id == expected_up, "up_limit must be minimum active ID or low_limit")


def make_read_view(creator_id: int, next_id: int,
                   active_ids: Sequence[int] | set[int] | frozenset[int]) -> ReadView:
    """Capture active read-write IDs, excluding the creator; 0=unassigned reader.

    This model does not assign an ID later to an existing read-only transaction.
    Its next_id is a teaching allocation boundary, not an InnoDB trx_no counter.
    """
    integer(creator_id, "creator_id")
    integer(next_id, "next_id", 1)
    require(creator_id < next_id, "creator must be allocated before next_id")
    require(isinstance(active_ids, (tuple, list, set, frozenset)), "invalid active IDs collection")
    for trx_id in active_ids:
        integer(trx_id, "active transaction ID", 1)
        require(trx_id < next_id, "active transaction must be allocated before next_id")
    require(len(set(active_ids)) == len(active_ids), "duplicate active transaction ID")
    captured = frozenset(trx_id for trx_id in active_ids if trx_id != creator_id)
    result = ReadView(creator_id, min(captured, default=next_id), next_id, captured)
    validate_view(result)
    return result


def changes_visible(view: ReadView, trx_id: int) -> bool:
    validate_view(view)
    integer(trx_id, "trx_id", 1)
    if trx_id < view.up_limit_id or trx_id == view.creator_id:
        return True
    if trx_id >= view.low_limit_id:
        return False
    return trx_id not in view.active_ids


@dataclass(frozen=True)
class Version:
    trx_id: int
    value: str | None
    deleted: bool = False


def visible_version(view: ReadView, newest_first: Sequence[Version]) -> Version | None:
    """Choose first visible physical version; transaction IDs are NOT timestamps.

    A visible tombstone ends traversal. An invisible tombstone permits reading
    an older version. Caller supplies a valid history, including undo versions;
    this code has no undo allocator, purge, rollback or concurrent writer.
    """
    validate_view(view)
    sequence(newest_first, "version history")
    for version in newest_first:
        require(isinstance(version, Version), "expected Version")
        integer(version.trx_id, "version trx_id", 1)
        require(isinstance(version.deleted, bool), "deleted must be boolean")
        require((version.deleted and version.value is None)
                or (not version.deleted and isinstance(version.value, str)),
                "tombstone needs None; live version needs text")
    return next((version for version in newest_first if changes_visible(view, version.trx_id)), None)


def read_value(view: ReadView, newest_first: Sequence[Version]) -> str | None:
    version = visible_version(view, newest_first)
    return None if version is None or version.deleted else version.value


def statement_view(isolation: str, creator_id: int, next_id: int,
                   active_ids: Sequence[int] | set[int] | frozenset[int],
                   previous: ReadView | None = None) -> ReadView:
    """Only ordinary consistent SELECT: RC refreshes; RR reuses its first view.

    Not transaction begin, DML/locking reads, SERIALIZABLE or full isolation.
    Explicit consistent-snapshot transaction startup is outside this model.
    """
    require(isolation in ("RC", "RR"), "isolation must be RC or RR")
    fresh = make_read_view(creator_id, next_id, active_ids)
    if previous is not None:
        validate_view(previous)
        require(previous.creator_id == creator_id, "cannot reuse another transaction's view")
        require(previous.low_limit_id <= next_id, "allocation boundary cannot go backwards")
    return previous if isolation == "RR" and previous is not None else fresh


@dataclass(frozen=True)
class RecordLock:
    transaction: str
    resource: str
    mode: str


def validate_lock(lock: RecordLock) -> None:
    require(isinstance(lock, RecordLock), "expected RecordLock")
    text(lock.transaction, "transaction")
    text(lock.resource, "resource")
    require(lock.mode in ("S", "X"), "lock mode must be S or X")


def compatible(left: str, right: str) -> bool:
    require(left in ("S", "X") and right in ("S", "X"), "lock mode must be S or X")
    return left == right == "S"


def wait_for_graph(holders: Sequence[RecordLock], requests: Sequence[RecordLock]) -> dict[str, frozenset[str]]:
    """Edges waiter -> incompatible granted holder on the same record resource.

    Static graph: no queue fairness, next-key/gap/insert intention/table locks,
    metadata locks, latches, lock acquisition, scheduler or victim selection.
    """
    sequence(holders, "holders")
    sequence(requests, "requests")
    for lock in (*holders, *requests):
        validate_lock(lock)
    require(len({(lock.transaction, lock.resource) for lock in holders}) == len(holders),
            "one granted lock per transaction/resource is required")
    require(len({lock.transaction for lock in requests}) == len(requests),
            "at most one pending request per transaction")
    for offset, left in enumerate(holders):
        for right in holders[offset + 1:]:
            if left.resource == right.resource and left.transaction != right.transaction:
                require(compatible(left.mode, right.mode), "incompatible granted holders")
    graph: dict[str, set[str]] = {lock.transaction: set() for lock in (*holders, *requests)}
    for request in requests:
        for holder in holders:
            if (request.resource == holder.resource and request.transaction != holder.transaction
                    and not compatible(request.mode, holder.mode)):
                graph[request.transaction].add(holder.transaction)
    return {node: frozenset(graph[node]) for node in sorted(graph)}


def find_cycle(graph: Mapping[str, set[str] | frozenset[str]]) -> tuple[str, ...]:
    """Deterministic iterative DFS; returns a closed cycle, or an empty tuple."""
    require(isinstance(graph, Mapping), "graph must be a mapping")
    for node, neighbors in graph.items():
        text(node, "graph node")
        require(isinstance(neighbors, (set, frozenset)), "neighbors must be a set")
        for neighbor in neighbors:
            text(neighbor, "neighbor")
            require(neighbor in graph, "every neighbor must have a graph node")
    color = {node: 0 for node in graph}
    for root in sorted(graph):
        if color[root]:
            continue
        path = [root]
        positions = {root: 0}
        color[root] = 1
        stack = [(root, iter(sorted(graph[root])))]
        while stack:
            node, neighbors = stack[-1]
            neighbor = next(neighbors, None)
            if neighbor is None:
                stack.pop()
                path.pop()
                positions.pop(node)
                color[node] = 2
            elif color[neighbor] == 1:
                return tuple(path[positions[neighbor]:] + [neighbor])
            elif color[neighbor] == 0:
                positions[neighbor] = len(path)
                path.append(neighbor)
                color[neighbor] = 1
                stack.append((neighbor, iter(sorted(graph[neighbor]))))
    return ()


@dataclass(frozen=True)
class CommitEvidence:
    """One internal transaction; redo state describes DURABLE evidence only.

    binlog='durable' means an entire valid transaction including XID survived.
    binlog='written' is unsynced and is discarded in our chosen loss scenario.
    ack_received is a separate client observation, not a recovery instruction.
    """
    redo: str = "absent"
    binlog: str = "absent"
    ack_received: bool = False


def validate_evidence(evidence: CommitEvidence) -> None:
    require(isinstance(evidence, CommitEvidence), "expected CommitEvidence")
    require(evidence.redo in ("absent", "prepared", "committed"), "invalid durable redo state")
    require(evidence.binlog in ("absent", "written", "durable"), "invalid binlog state")
    require(isinstance(evidence.ack_received, bool), "ack_received must be boolean")


def recover_after_volatile_loss(evidence: CommitEvidence) -> str:
    """Abstract truth table, NOT real recovery or a claim every unsynced write is lost.

    Assumptions: internal 2PC with binlog enabled, one InnoDB transaction,
    trustworthy durable media, valid complete XID, no external XA/DDL/mixed
    engines, and ALL non-durable evidence lost by the modeled power failure.
    Impossible states under our strict ordering are reported INCONSISTENT,
    never repaired by silently rolling back a durable committed transaction.
    """
    validate_evidence(evidence)
    logged = evidence.binlog == "durable"
    if evidence.redo == "absent":
        return "INCONSISTENT" if logged else "ABSENT"
    if evidence.redo == "prepared":
        return "COMMIT" if logged else "ROLLBACK"
    return "COMMIT" if logged else "INCONSISTENT"


def commit_trace(durable_redo: bool = True, sync_binlog: bool = True) -> tuple[tuple[str, CommitEvidence], ...]:
    """Policy thought experiment: not a trace of MySQL group-commit internals.

    With both switches true, durable prepare precedes durable binlog, then
    durable engine commit and observed ACK. False means required persistence
    is deliberately omitted in this model; these are NOT server variables.
    """
    require(isinstance(durable_redo, bool) and isinstance(sync_binlog, bool), "policy switches must be boolean")
    prepared = "prepared" if durable_redo else "absent"
    committed = "committed" if durable_redo else "absent"
    logged = "durable" if sync_binlog else "written"
    stages = [("initial", CommitEvidence()),
              ("prepare", CommitEvidence(prepared)),
              ("binlog-write", CommitEvidence(prepared, "written"))]
    if sync_binlog:
        stages.append(("binlog-sync", CommitEvidence(prepared, "durable")))
    stages.extend([("engine-commit", CommitEvidence(committed, logged)),
                   ("ack-received", CommitEvidence(committed, logged, True))])
    return tuple(stages)


def index_lookup_lab() -> dict:
    rows = [Row(40, "A", 20, "p40"), Row(10, "A", 10, "p10"), Row(30, "B", 15, "p30"),
            Row(20, "A", 20, "p20"), Row(50, "A", 30, "p50")]
    covering = index_lookup(rows, "A", 10, 20, ("pk", "score"))
    fetching = index_lookup(rows, "A", 10, 20, ("pk", "score", "payload"))
    require(covering.rows == ((10, 10), (20, 20), (40, 20)), "covering row oracle failed")
    require(fetching.rows == ((10, 10, "p10"), (20, 20, "p20"), (40, 20, "p40")),
            "clustered lookup oracle failed")
    require((covering.secondary_entries, covering.clustered_lookups) == (3, 0)
            and (fetching.secondary_entries, fetching.clustered_lookups) == (3, 3), "logical work oracle failed")
    return {"scope": "sorted secondary tuples and logical PK fetches; NOT physical I/O or MVCC index-only guarantee",
            "covering": asdict(covering), "noncovering": asdict(fetching)}


def read_view_lab() -> dict:
    first = statement_view("RR", 20, 30, {12, 20, 25})
    history = (Version(25, "new"), Version(8, "old"))
    rr_later = statement_view("RR", 20, 31, {20}, first)
    rc_later = statement_view("RC", 20, 31, {20}, first)
    own_history = (Version(20, "own-write"), *history)
    deletion = (Version(25, None, True), Version(8, "old"))
    require(first.active_ids == frozenset({12, 25}) and first.up_limit_id == 12
            and first.low_limit_id == 30, "view boundary oracle failed")
    require([changes_visible(first, trx) for trx in (8, 12, 15, 20, 25, 30)]
            == [True, False, True, True, False, False], "visibility matrix failed")
    values = [read_value(view, history) for view in (first, rr_later, rc_later)]
    require(values == ["old", "old", "new"], "RC/RR oracle failed")
    require(read_value(first, own_history) == "own-write", "own-write oracle failed")
    require(read_value(first, deletion) == "old" and read_value(rc_later, deletion) is None,
            "tombstone oracle failed")
    return {"scope": "consistent-read version selection only; NOT locking reads, DML, purge or full isolation",
            "view": {"creator_id": 20, "up_limit_id": 12, "low_limit_id": 30, "active_ids": [12, 25]},
            "first_RR_RC_values": values, "own_write": "own-write",
            "delete_before_after_visibility": ["old", None]}


def deadlock_lab() -> dict:
    holders = [RecordLock("T1", "account:1", "X"), RecordLock("T2", "account:2", "X")]
    requests = [RecordLock("T1", "account:2", "X"), RecordLock("T2", "account:1", "X")]
    graph = wait_for_graph(holders, requests)
    cycle = find_cycle(graph)
    require(graph == {"T1": frozenset({"T2"}), "T2": frozenset({"T1"})}
            and cycle == ("T1", "T2", "T1"), "wait graph oracle failed")
    no_cycle = wait_for_graph(holders, requests[:1])
    require(find_cycle(no_cycle) == (), "waiting alone is not a deadlock")
    upgrades = wait_for_graph([RecordLock("T1", "r", "S"), RecordLock("T2", "r", "S")],
                             [RecordLock("T1", "r", "X"), RecordLock("T2", "r", "X")])
    require(find_cycle(upgrades) == ("T1", "T2", "T1"), "shared-lock upgrade oracle failed")
    return {"scope": "static record S/X graph only; NOT next-key/gap locks, wait queues, latches or victim selection",
            "edges": {node: sorted(edges) for node, edges in graph.items()}, "cycle": cycle,
            "one_wait_cycle": find_cycle(no_cycle), "upgrade_cycle": find_cycle(upgrades)}


def commit_recovery_lab() -> dict:
    strict = commit_trace()
    outcomes = [recover_after_volatile_loss(evidence) for _, evidence in strict]
    require(outcomes == ["ABSENT", "ROLLBACK", "ROLLBACK", "COMMIT", "COMMIT", "COMMIT"],
            "strict crash-cut oracle failed")
    lost_ack = strict[-2][1]
    require(not lost_ack.ack_received and recover_after_volatile_loss(lost_ack) == "COMMIT",
            "ACK absence must not imply rollback")
    relaxed_all = commit_trace(False, False)[-1][1]
    relaxed_binlog = commit_trace(True, False)[-1][1]
    require(relaxed_all.ack_received and recover_after_volatile_loss(relaxed_all) == "ABSENT",
            "relaxed persistence loss counterexample failed")
    require(recover_after_volatile_loss(relaxed_binlog) == "INCONSISTENT",
            "durable engine commit without durable binlog must not be called rollback")
    return {"scope": "assumption-based internal 2PC evidence table; all volatile writes lost; NOT real fsync/recovery",
            "strict_crash_cuts": [{"stage": stage, **asdict(evidence), "recovery": outcome}
                                  for (stage, evidence), outcome in zip(strict, outcomes)],
            "no_ACK_can_still_commit": True,
            "relaxed_both_after_ACK": recover_after_volatile_loss(relaxed_all),
            "relaxed_binlog_after_ACK": recover_after_volatile_loss(relaxed_binlog),
            "warning": "unsynced writes are not guaranteed lost in reality; this is one permitted loss scenario"}


LABS = {"index-lookup": index_lookup_lab, "read-view": read_view_lab,
        "deadlock": deadlock_lab, "commit-recovery": commit_recovery_lab}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab", choices=[*LABS, "all"], default="all")
    args = parser.parse_args(argv)
    names = list(LABS) if args.lab == "all" else [args.lab]
    results = {name: LABS[name]() for name in names}
    print(json.dumps({"status": "PASS", "runtime": "Python standard library only", "labs": results},
                     ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
