"""Small deterministic NATS teaching models, NOT a server or conformance suite.

Python stdlib only; no sockets, files, subprocesses, wall clocks, or real effects.
See offline.md for deliberately narrower grammars and state-machine assumptions.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from typing import Any


LAB_NAMES = ("subject-routing", "publish-dedup", "ack-redelivery", "retention-gates")


class ModelError(ValueError):
    """Rejected teaching-model input; not a NATS protocol error."""


def integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ModelError(f"{name}: expected integer >= {minimum}, not bool")
    return value


def identifier(value: Any, name: str = "identifier") -> str:
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is None:
        raise ModelError(f"{name}: this profile requires 1..64 ASCII letters/digits/_/-")
    return value


def payload_bytes(value: Any) -> bytes:
    if type(value) is not bytes or len(value) > 4096:
        raise ModelError("payload: immutable bytes of at most 4096 bytes required")
    return value


def subject_tokens(value: Any, *, pattern: bool = False) -> tuple[str, ...]:
    if type(pattern) is not bool:
        raise ModelError("pattern must be bool")
    if type(value) is not str or not value or len(value) > 256:
        raise ModelError("subject: expected 1..256 characters in this profile")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        raise ModelError("subject: whitespace/control characters are outside this profile")
    tokens = tuple(value.split("."))
    if len(tokens) > 32 or any(not token for token in tokens):
        raise ModelError("subject: expected 1..32 nonempty tokens")
    for index, token in enumerate(tokens):
        if "*" not in token and ">" not in token:
            continue
        if not pattern or token not in ("*", ">"):
            raise ModelError("wildcards must occupy whole subscription tokens")
        if token == ">" and index != len(tokens) - 1:
            raise ModelError("> is allowed only as the final token")
    return tokens


def matches(pattern: str, subject: str) -> bool:
    wanted = subject_tokens(pattern, pattern=True)
    actual = subject_tokens(subject)
    for index, token in enumerate(wanted):
        if index >= len(actual):
            return False  # 'orders.>' MUST NOT match 'orders'.
        if token == ">":
            return True
        if token != "*" and token != actual[index]:
            return False
    return len(wanted) == len(actual)


def patterns_overlap(left: str, right: str) -> bool:
    """Existential intersection for this token grammar, not a sampled-subject test."""
    a = subject_tokens(left, pattern=True)
    b = subject_tokens(right, pattern=True)
    a_tail, b_tail = a[-1] == ">", b[-1] == ">"
    length = max(len(a), len(b))
    if (not a_tail and len(a) != length) or (not b_tail and len(b) != length):
        return False
    for index in range(length):
        x = "*" if a_tail and index >= len(a) - 1 else a[index]
        y = "*" if b_tail and index >= len(b) - 1 else b[index]
        if x != "*" and y != "*" and x != y:
            return False
    return True


@dataclass(frozen=True)
class Subscription:
    name: str
    pattern: str
    queue: str | None = None

    def __post_init__(self) -> None:
        identifier(self.name, "subscription name")
        subject_tokens(self.pattern, pattern=True)
        if self.queue is not None:
            identifier(self.queue, "queue group")


def subscriptions(value: Any) -> tuple[Subscription, ...]:
    if type(value) is not tuple or len(value) > 256:
        raise ModelError("subscriptions: tuple of at most 256 subscriptions required")
    if any(type(item) is not Subscription for item in value):
        raise ModelError("subscriptions: Subscription objects required")
    if len({item.name for item in value}) != len(value):
        raise ModelError("subscription names must be unique in this model")
    return value


def route(subject: str, members: tuple[Subscription, ...], turn: int = 0) -> tuple[str, ...]:
    """All ordinary matching subscriptions + one per matching queue group.

    turn selects a deterministic example member. It is NOT NATS fairness/order.
    """
    subject_tokens(subject)
    subscriptions(members)
    integer(turn, "turn")
    ordinary: list[str] = []
    queues: dict[str, list[str]] = {}
    for member in members:
        if matches(member.pattern, subject):
            if member.queue is None:
                ordinary.append(member.name)
            else:
                queues.setdefault(member.queue, []).append(member.name)
    for names in queues.values():
        ordinary.append(names[turn % len(names)])
    return tuple(sorted(ordinary))


@dataclass(frozen=True)
class StoredMessage:
    sequence: int
    subject: str
    payload: bytes
    accepted_at: int
    message_id: str | None = None


@dataclass(frozen=True)
class PublishReceipt:
    sequence: int
    duplicate: bool


class DedupPublisher:
    """One stream, finite ID window, no storage limits or failed commit path."""

    def __init__(self, window: int = 10):
        self._window = integer(window, "window", 1)
        self._clock = 0
        self._messages: list[StoredMessage] = []
        self._ids: dict[str, tuple[int, int]] = {}

    @property
    def messages(self) -> tuple[StoredMessage, ...]:
        return tuple(self._messages)

    @property
    def clock(self) -> int:
        return self._clock

    def publish(self, subject: str, payload: bytes, now: int,
                message_id: str | None = None) -> PublishReceipt:
        subject_tokens(subject)
        payload_bytes(payload)
        integer(now, "now", self._clock)
        if message_id is not None:
            identifier(message_id, "message ID")
        active = {key: value for key, value in self._ids.items() if now - value[1] < self._window}
        self._clock = now
        self._ids = active
        if message_id is not None and message_id in active:
            # A duplicate does not compare/replace the body, nor refresh first-seen time.
            return PublishReceipt(active[message_id][0], True)
        sequence = len(self._messages) + 1
        self._messages.append(StoredMessage(sequence, subject, payload, now, message_id))
        if message_id is not None:
            self._ids[message_id] = (sequence, now)
        return PublishReceipt(sequence, False)


class BusinessCounter:
    """Assumed atomic in-memory effect+key recording; not a DB implementation."""

    def __init__(self):
        self._effects: dict[tuple[str, str], bytes] = {}

    @property
    def count(self) -> int:
        return len(self._effects)

    def apply(self, tenant: str, key: str, intent: bytes) -> bool:
        identifier(tenant, "tenant")
        identifier(key, "business key")
        payload_bytes(intent)
        composite = (tenant, key)
        if composite in self._effects:
            if self._effects[composite] != intent:
                raise ModelError("same business key was reused for a different intent")
            return False
        self._effects[composite] = intent
        return True


@dataclass(frozen=True)
class Delivery:
    stream_sequence: int
    consumer_sequence: int
    attempt: int
    deadline: int


class ConsumerLedger:
    """Explicit ACK, one fixed input sequence, synchronous pull and logical time.

    No NAK, TERM, progress ACK, AckAll, filters, deletion, replication, or real
    server AckFloor algorithm. settled_prefix is a separately named teaching value.
    """

    def __init__(self, stream_sequences: tuple[int, ...], *, ack_wait: int = 5,
                 max_pending: int = 2, max_deliver: int = 3,
                 backoff: tuple[int, ...] = ()):
        if type(stream_sequences) is not tuple or len(stream_sequences) > 4096:
            raise ModelError("stream_sequences: tuple of at most 4096 integers required")
        for sequence in stream_sequences:
            integer(sequence, "stream sequence", 1)
        if tuple(sorted(set(stream_sequences))) != stream_sequences:
            raise ModelError("stream sequences must be strictly increasing")
        self._ack_wait = integer(ack_wait, "ack_wait", 1)
        self._max_pending = integer(max_pending, "max_pending", 1)
        self._max_deliver = integer(max_deliver, "max_deliver", 1)
        if type(backoff) is not tuple or len(backoff) > max_deliver:
            raise ModelError("backoff: tuple no longer than max_deliver required")
        for wait in backoff:
            integer(wait, "backoff entry", 1)
        self._backoff = backoff
        self._sequences = stream_sequences
        self._clock = 0
        self._deliveries: list[Delivery] = []
        self._pending: dict[int, Delivery] = {}
        self._acked: set[int] = set()
        self._exhausted: set[int] = set()
        self._seen: set[int] = set()

    @property
    def deliveries(self) -> tuple[Delivery, ...]:
        return tuple(self._deliveries)

    @property
    def pending(self) -> tuple[int, ...]:
        return tuple(sorted(self._pending))

    @property
    def exhausted(self) -> tuple[int, ...]:
        return tuple(sorted(self._exhausted))

    @property
    def stream_sequences(self) -> tuple[int, ...]:
        return self._sequences

    @property
    def settled_prefix(self) -> int:
        """Last ACKed supplied sequence before a gap; NOT server AckFloor."""
        result = 0
        for sequence in self._sequences:
            if sequence not in self._acked:
                break
            result = sequence
        return result

    def _wait(self, attempt: int) -> int:
        if self._backoff:
            return self._backoff[min(attempt - 1, len(self._backoff) - 1)]
        return self._ack_wait

    def pull(self, now: int) -> Delivery | None:
        integer(now, "now", self._clock)
        self._clock = now
        # Timer processing only happens when the learner calls pull, not in a thread.
        for sequence, delivery in tuple(self._pending.items()):
            if now >= delivery.deadline and delivery.attempt >= self._max_deliver:
                self._exhausted.add(sequence)
                del self._pending[sequence]
        due = sorted(sequence for sequence, delivery in self._pending.items()
                     if now >= delivery.deadline)
        if due:
            sequence = due[0]
            attempt = self._pending[sequence].attempt + 1
        else:
            if len(self._pending) >= self._max_pending:
                return None
            unseen = [sequence for sequence in self._sequences if sequence not in self._seen]
            if not unseen:
                return None
            sequence, attempt = unseen[0], 1
        delivery = Delivery(sequence, len(self._deliveries) + 1, attempt, now + self._wait(attempt))
        self._seen.add(sequence)
        self._pending[sequence] = delivery
        self._deliveries.append(delivery)
        return delivery

    def ack(self, consumer_sequence: int, now: int) -> bool:
        integer(consumer_sequence, "consumer sequence", 1)
        integer(now, "now", self._clock)
        if consumer_sequence > len(self._deliveries):
            raise ModelError("cannot ACK a delivery that never happened")
        sequence = self._deliveries[consumer_sequence - 1].stream_sequence
        self._clock = now
        if sequence in self._acked:
            return False
        # This model accepts an old attempt's ACK for the same stream message.
        # It does not revoke an already dispatched worker's external side effects.
        self._acked.add(sequence)
        self._pending.pop(sequence, None)
        self._exhausted.discard(sequence)
        return True


@dataclass(frozen=True)
class Removal:
    sequence: int
    reason: str


class RetentionStore:
    """Static consumers + explicit delivery/ACK; MaxMsgs/MaxAge, DiscardOld only.

    No consumer creation/deletion after publish, MaxBytes, purge, mirrors,
    subject transforms, rollup, per-message TTL, or consumer-ledger coupling.
    """

    def __init__(self, policy: str, consumers: tuple[Subscription, ...] = (),
                 *, max_messages: int = 100, max_age: int = 100):
        if type(policy) is not str or policy not in ("limits", "interest", "workqueue"):
            raise ModelError("policy must be limits, interest, or workqueue")
        subscriptions(consumers)
        if any(consumer.queue is not None for consumer in consumers):
            raise ModelError("retention consumers are not Core queue subscriptions")
        if policy == "workqueue":
            for index, left in enumerate(consumers):
                if any(patterns_overlap(left.pattern, right.pattern) for right in consumers[index + 1:]):
                    raise ModelError("WorkQueue consumer filters must not overlap")
        self._policy = policy
        self._consumers = consumers
        self._max_messages = integer(max_messages, "max_messages", 1)
        self._max_age = integer(max_age, "max_age", 1)
        self._clock = 0
        self._last_sequence = 0
        self._messages: dict[int, StoredMessage] = {}
        self._delivered: set[tuple[int, str]] = set()
        self._acked: set[tuple[int, str]] = set()
        self._removals: list[Removal] = []

    @property
    def messages(self) -> tuple[StoredMessage, ...]:
        return tuple(self._messages.values())

    @property
    def removals(self) -> tuple[Removal, ...]:
        return tuple(self._removals)

    def _remove(self, sequence: int, reason: str) -> None:
        del self._messages[sequence]
        self._removals.append(Removal(sequence, reason))

    def advance(self, now: int) -> None:
        integer(now, "now", self._clock)
        self._clock = now
        for sequence, message in tuple(self._messages.items()):
            if now - message.accepted_at >= self._max_age:
                self._remove(sequence, "max-age")
        while len(self._messages) > self._max_messages:
            self._remove(next(iter(self._messages)), "max-messages-discard-old")

    def publish(self, subject: str, payload: bytes, now: int) -> int:
        subject_tokens(subject)
        payload_bytes(payload)
        integer(now, "now", self._clock)
        self.advance(now)
        self._last_sequence += 1
        sequence = self._last_sequence
        self._messages[sequence] = StoredMessage(sequence, subject, payload, now)
        if self._policy == "interest" and not any(matches(c.pattern, subject) for c in self._consumers):
            self._remove(sequence, "no-interest")
        self.advance(now)
        return sequence

    def _target(self, sequence: int, consumer: str, now: int) -> StoredMessage | None:
        integer(sequence, "stream sequence", 1)
        identifier(consumer, "consumer")
        integer(now, "now", self._clock)
        if sequence > self._last_sequence:
            raise ModelError("unknown stream sequence")
        member = next((c for c in self._consumers if c.name == consumer), None)
        if member is None:
            raise ModelError("unknown consumer")
        message = self._messages.get(sequence)
        if message is not None and not matches(member.pattern, message.subject):
            raise ModelError("consumer filter does not cover this message")
        return message

    def deliver(self, sequence: int, consumer: str, now: int) -> bool:
        self._target(sequence, consumer, now)
        self.advance(now)
        if sequence not in self._messages:
            return False
        self._delivered.add((sequence, consumer))
        return True

    def ack(self, sequence: int, consumer: str, now: int) -> bool:
        message = self._target(sequence, consumer, now)
        if message is not None and (sequence, consumer) not in self._delivered:
            raise ModelError("ACK requires a prior matching delivery in this model")
        self.advance(now)
        if sequence not in self._messages or (sequence, consumer) in self._acked:
            return False
        self._acked.add((sequence, consumer))
        if self._policy == "workqueue":
            self._remove(sequence, "workqueue-ack")
        elif self._policy == "interest":
            interested = (c.name for c in self._consumers if matches(c.pattern, message.subject))
            if all((sequence, name) in self._acked for name in interested):
                self._remove(sequence, "all-interest-acked")
        return True


def subject_routing_lab() -> dict:
    members = (Subscription("audit", "orders.>"), Subscription("billing", "orders.*"),
               Subscription("worker-a", "orders.*", "workers"),
               Subscription("worker-b", "orders.*", "workers"),
               Subscription("metrics", "orders.*", "metrics"))
    return {"ordinary_and_queues": route("orders.created", members),
            "next_example_turn": route("orders.created", members, 1),
            "parent_does_not_match_tail": not matches("orders.>", "orders"),
            "no_interest_deliveries": route("payments.created", members),
            "bad_control_zero_token_tail_would_match": "orders".startswith("orders.>"[:-2])}


def publish_dedup_lab() -> dict:
    publisher = DedupPublisher(window=10)
    receipts = [publisher.publish("orders.created", b"order-1", 0, "id-1"),
                publisher.publish("orders.created", b"changed-body", 9, "id-1"),
                publisher.publish("orders.created", b"order-1", 10, "id-1")]
    business = BusinessCounter()
    for message in publisher.messages:
        business.apply("tenant-a", "order-1", message.payload)
    return {"receipts": [asdict(receipt) for receipt in receipts],
            "stored_payloads": [message.payload.decode() for message in publisher.messages],
            "naive_external_effects": len(publisher.messages),
            "idempotent_external_effects": business.count,
            "publisher_ack_is_external_commit": False}


def ack_redelivery_lab() -> dict:
    consumer = ConsumerLedger((1, 2), ack_wait=5, max_pending=1, max_deliver=2)
    first = consumer.pull(0)
    blocked = consumer.pull(1)
    again = consumer.pull(5)
    business = BusinessCounter()
    business.apply("tenant-a", "order-1", b"charge-100")
    business.apply("tenant-a", "order-1", b"charge-100")
    consumer.ack(first.consumer_sequence, 6)
    second = consumer.pull(6)
    consumer.pull(11)
    consumer.pull(16)
    return {"first": asdict(first), "blocked_by_max_pending": blocked is None,
            "redelivery": asdict(again), "next_message": asdict(second),
            "exhausted": consumer.exhausted, "stream_still_contains": consumer.stream_sequences,
            "settled_prefix_not_server_ack_floor": consumer.settled_prefix,
            "naive_effects_for_first_message": 2, "idempotent_effects_for_first_message": business.count,
            "automatic_dlq_created": False}


def retention_gates_lab() -> dict:
    members = (Subscription("billing", "orders.*"), Subscription("audit", "orders.>"))
    limits = RetentionStore("limits", members)
    interest = RetentionStore("interest", members)
    for store in (limits, interest):
        store.publish("orders.created", b"1", 0)
        for name in ("billing", "audit"):
            store.deliver(1, name, 1)
            store.ack(1, name, 1)
    no_interest = RetentionStore("interest")
    no_interest.publish("orders.created", b"1", 0)
    work = RetentionStore("workqueue", (Subscription("workers", "orders.>"),), max_age=5)
    work.publish("orders.created", b"1", 0)
    work.deliver(1, "workers", 0)
    work.ack(1, "workers", 1)
    work.publish("orders.created", b"unacked", 1)
    work.advance(6)
    return {"limits_after_all_acks": len(limits.messages), "interest_after_all_acks": len(interest.messages),
            "interest_without_consumers": len(no_interest.messages),
            "workqueue_removals": [asdict(removal) for removal in work.removals],
            "retention_is_automatic_business_exactly_once": False}


LABS = dict(zip(LAB_NAMES, (subject_routing_lab, publish_dedup_lab, ack_redelivery_lab, retention_gates_lab)))


_EXPECTED = {
    "subject-routing": {
        "ordinary_and_queues": ("audit", "billing", "metrics", "worker-a"),
        "next_example_turn": ("audit", "billing", "metrics", "worker-b"),
        "parent_does_not_match_tail": True, "no_interest_deliveries": (),
        "bad_control_zero_token_tail_would_match": True},
    "publish-dedup": {
        "receipts": [{"sequence": 1, "duplicate": False}, {"sequence": 1, "duplicate": True},
                     {"sequence": 2, "duplicate": False}],
        "stored_payloads": ["order-1", "order-1"], "naive_external_effects": 2,
        "idempotent_external_effects": 1, "publisher_ack_is_external_commit": False},
    "ack-redelivery": {
        "first": {"stream_sequence": 1, "consumer_sequence": 1, "attempt": 1, "deadline": 5},
        "blocked_by_max_pending": True,
        "redelivery": {"stream_sequence": 1, "consumer_sequence": 2, "attempt": 2, "deadline": 10},
        "next_message": {"stream_sequence": 2, "consumer_sequence": 3, "attempt": 1, "deadline": 11},
        "exhausted": (2,), "stream_still_contains": (1, 2),
        "settled_prefix_not_server_ack_floor": 1,
        "naive_effects_for_first_message": 2, "idempotent_effects_for_first_message": 1,
        "automatic_dlq_created": False},
    "retention-gates": {
        "limits_after_all_acks": 1, "interest_after_all_acks": 0, "interest_without_consumers": 0,
        "workqueue_removals": [{"sequence": 1, "reason": "workqueue-ack"},
                               {"sequence": 2, "reason": "max-age"}],
        "retention_is_automatic_business_exactly_once": False},
}


def _same_result(actual: Any, expected: Any) -> bool:
    # Python's ordinary equality treats True == 1; the oracle must not do that.
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return (actual.keys() == expected.keys()
                and all(_same_result(actual[key], value) for key, value in expected.items()))
    if type(expected) in (tuple, list):
        return len(actual) == len(expected) and all(_same_result(a, e) for a, e in zip(actual, expected))
    return actual == expected


def verify_result(name: str, result: Any) -> None:
    """Runtime check against hand-calculated literals, independent of lab execution."""
    if type(name) is not str or name not in _EXPECTED:
        raise ModelError("unknown experiment oracle")
    if not _same_result(result, _EXPECTED[name]):
        raise ModelError(f"{name}: output disagrees with the independent literal oracle")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true", help="list bounded model names")
    group.add_argument("--lab", choices=(*LAB_NAMES, "all"), help="run one model or all")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(LAB_NAMES))
    elif args.lab:
        names = LAB_NAMES if args.lab == "all" else (args.lab,)
        results = {}
        try:
            for name in names:
                result = LABS[name]()
                verify_result(name, result)
                results[name] = result
        except ModelError as error:
            print(f"model verification failed: {error}", file=sys.stderr)
            return 1
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
