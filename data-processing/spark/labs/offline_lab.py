"""Deterministic CPU models, NOT Spark, Delta Lake or Databricks execution.

Python 3.10+; standard library only; no file writes, network or credentials.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Iterable


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def positive_int(value: int, name: str) -> None:
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"{name} must be a positive integer")


def finite_nonnegative(value: float, name: str) -> None:
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0, f"{name} must be finite and nonnegative")


def partition(key: str, partitions: int) -> int:
    """Our stable SHA-256 rule, not Spark's Murmur3 partitioning rule."""
    positive_int(partitions, "partitions")
    require(isinstance(key, str), "key must be a string")
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") % partitions


def weighted_mean(partials: Iterable[tuple[float, int]]) -> float:
    total, count = 0.0, 0
    for partial_sum, partial_count in partials:
        require(isinstance(partial_sum, (int, float)) and not isinstance(partial_sum, bool)
                and math.isfinite(partial_sum), "partial sum must be finite")
        positive_int(partial_count, "partial count")
        total += partial_sum
        require(math.isfinite(total), "partial sums overflowed")
        count += partial_count
    require(count > 0, "at least one partial is required")
    return total / count


def partition_skew_lab() -> dict:
    rows = [(i, "hot", float(i % 7)) for i in range(201)]
    rows += [(201 + i, f"cold-{i}", float(i % 3)) for i in range(39)]
    plain, salted = [0] * 4, [0] * 4
    partials: dict[tuple[str, int], tuple[float, int]] = {}
    reference: dict[str, tuple[float, int]] = {}
    for row_id, key, amount in rows:
        salt = row_id % 8 if key == "hot" else 0
        plain[partition(key, 4)] += 1
        salted[partition(f"{key}|{salt}", 4)] += 1
        part_sum, part_count = partials.get((key, salt), (0.0, 0))
        partials[key, salt] = part_sum + amount, part_count + 1
        ref_sum, ref_count = reference.get(key, (0.0, 0))
        reference[key] = ref_sum + amount, ref_count + 1
    for key, (ref_sum, ref_count) in reference.items():
        result = weighted_mean(value for (group, _), value in partials.items() if group == key)
        require(math.isclose(result, ref_sum / ref_count), "two-stage mean changed the answer")
    unequal = [(100.0, 1), (0.0, 9)]
    weighted, naive = weighted_mean(unequal), sum(s / n for s, n in unequal) / len(unequal)
    require(weighted == 10.0 and naive == 50.0, "counterexample changed")
    return {"scope": "synthetic hash and row load; NOT measured Spark speed",
            "rows": len(rows), "plain_partition_rows": plain, "salted_partition_rows": salted,
            "two_stage_means_equal_reference": True,
            "unequal_partial_weighted_mean": weighted, "wrong_mean_of_means": naive}


@dataclass(frozen=True)
class VersionedRow:
    key: str
    version: int
    value: str | None
    deleted: bool = False


def validate_row(row: VersionedRow) -> None:
    require(isinstance(row, VersionedRow), "expected VersionedRow")
    require(isinstance(row.key, str) and bool(row.key), "key must be nonempty")
    positive_int(row.version, "version")
    require(isinstance(row.deleted, bool), "deleted must be boolean")
    require((row.deleted and row.value is None) or
            (not row.deleted and isinstance(row.value, str)), "invalid payload/tombstone")


def merge_versions(current: dict[str, VersionedRow], incoming: Iterable[VersionedRow]) -> dict[str, VersionedRow]:
    """Chosen business contract: ties must agree, highest version wins, retain tombstones.

    Validation is atomic in this in-memory model. It is not Delta MERGE syntax or a
    database transaction implementation. Ordering is an upstream business version.
    Conflicts are detectable only among this batch and the retained latest rows;
    detecting disagreements with discarded older history requires another ledger.
    """
    for key, row in current.items():
        validate_row(row)
        require(key == row.key, "state key differs from row key")
    seen = {(r.key, r.version): r for r in current.values()}
    batch = list(incoming)
    for row in batch:
        validate_row(row)
        identity = row.key, row.version
        require(identity not in seen or seen[identity] == row, "conflicting equal-version rows")
        seen[identity] = row
    result = dict(current)
    for row in batch:
        if row.key not in result or row.version > result[row.key].version:
            result[row.key] = row
    return result


def merge_lab() -> dict:
    batch = [VersionedRow("a", 1, "old"), VersionedRow("a", 2, "new"),
             VersionedRow("a", 2, "new"), VersionedRow("b", 1, "temporary"),
             VersionedRow("b", 3, None, True)]
    state = merge_versions({}, batch)
    require(merge_versions(state, batch) == state, "replay is not idempotent")
    require(merge_versions(state, [VersionedRow("b", 2, "late")]) == state,
            "late update resurrected a tombstone")
    conflict_rejected = False
    try:
        merge_versions(state, [VersionedRow("a", 2, "conflict")])
    except ValueError:
        conflict_rejected = True
    require(conflict_rejected, "conflicting tie accepted")
    return {"scope": "in-memory business-version contract; NOT Delta MERGE",
            "retained_state": [asdict(state[k]) for k in sorted(state)],
            "visible_keys": [k for k in sorted(state) if not state[k].deleted],
            "replay_unchanged": True, "conflicting_tie_rejected": conflict_rejected,
            "limitation": "discarded older-version payloads are not a historical conflict ledger"}


class WatermarkModel:
    """Single-input toy model with an explicit previous-batch watermark.

    At batch entry W = previous max event time - delay. Drop t < W, accept
    t == W; count fixed [start,end) windows; emit end <= W. Then advance max.
    Empty batches may emit against W but never advance event time themselves.
    There is no deduplication. Spark operator/trigger/version semantics differ.
    """
    def __init__(self, window: int = 10, delay: int = 5) -> None:
        positive_int(window, "window")
        positive_int(delay, "delay")
        self.window, self.delay = window, delay
        self.max_time: int | None = None
        self.pending: dict[int, int] = {}

    def batch(self, events: Iterable[tuple[str, int]]) -> dict:
        events = list(events)
        for identity, timestamp in events:
            require(isinstance(identity, str) and bool(identity), "event ID must be nonempty")
            require(isinstance(timestamp, int) and not isinstance(timestamp, bool) and timestamp >= 0,
                    "event time must be a nonnegative integer")
        watermark = None if self.max_time is None else self.max_time - self.delay
        dropped, accepted = [], []
        for identity, timestamp in events:
            if watermark is not None and timestamp < watermark:
                dropped.append(identity)
                continue
            accepted.append(identity)
            start = timestamp // self.window * self.window
            self.pending[start] = self.pending.get(start, 0) + 1
        emitted = []
        for start in sorted(list(self.pending)):
            if watermark is not None and start + self.window <= watermark:
                emitted.append({"start": start, "end": start + self.window,
                                "count": self.pending.pop(start)})
        if events:
            self.max_time = max([t for _, t in events] + ([] if self.max_time is None else [self.max_time]))
        return {"entry_watermark": watermark, "accepted_ids": accepted,
                "dropped_ids": dropped, "emitted": emitted, "pending": dict(self.pending)}


def watermark_lab() -> dict:
    model = WatermarkModel()
    trace = [model.batch([("e1", 2), ("e2", 12)]),
             model.batch([("late", 3), ("boundary", 7), ("future", 25)]), model.batch([])]
    require(trace[1]["dropped_ids"] == ["late"], "late fixture changed")
    require(trace[2]["emitted"] == [{"start": 0, "end": 10, "count": 2},
                                    {"start": 10, "end": 20, "count": 1}], "window fixture changed")
    require(model.batch([])["pending"] == {20: 1}, "idle batch advanced event time")
    return {"scope": "one explicit event-time model; NOT a Spark watermark guarantee", "trace": trace,
            "idle_does_not_advance_event_time": True, "deduplication_enabled": False}


def budget_plan(workers: int, hours: float, attempts: int, cap_units: float,
                worker_units_per_hour: float = 2.0, driver_units_per_hour: float = 1.0) -> dict:
    positive_int(workers, "workers")
    positive_int(attempts, "attempts")
    for name, value in [("hours", hours), ("cap_units", cap_units),
                        ("worker_units_per_hour", worker_units_per_hour),
                        ("driver_units_per_hour", driver_units_per_hour)]:
        finite_nonnegative(value, name)
    units = (workers * worker_units_per_hour + driver_units_per_hour) * hours * attempts
    require(math.isfinite(units), "resource units overflowed")
    return {"modeled_resource_units": units, "cap_units": cap_units,
            "within_cap": units <= cap_units,
            "assumption": "every attempt uses all workers and driver for full hours"}


def budget_lab() -> dict:
    first = budget_plan(2, 0.5, 1, 4)
    retry = budget_plan(2, 0.5, 2, 4)
    require(first["within_cap"] and not retry["within_cap"], "budget fixture changed")
    return {"scope": "fictional resource units; NOT DBUs, prices, quota or enforced cloud stop",
            "first_attempt": first, "one_full_retry": retry,
            "excluded": ["storage", "network", "idle startup", "cloud-specific billing granularity"]}


LABS = {"partition-skew": partition_skew_lab, "merge": merge_lab,
        "watermark": watermark_lab, "budget": budget_lab}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab", choices=[*LABS, "all"], default="all")
    args = parser.parse_args(argv)
    names = list(LABS) if args.lab == "all" else [args.lab]
    print(json.dumps({"status": "PASS", "runtime": "Python standard library only",
                      "labs": {name: LABS[name]() for name in names}}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
