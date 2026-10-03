"""Literal-oracle tests for the bounded NATS models, not server conformance."""

import contextlib
import copy
from dataclasses import FrozenInstanceError
import io
import json
import unittest
from unittest import mock

import offline_lab as lab


BAD_NUMBERS = (True, False, 1.0, "1", None, [], {}, float("nan"), float("inf"), -1)


class SubjectTests(unittest.TestCase):
    def test_literal_case_sensitive(self):
        self.assertTrue(lab.matches("orders.created", "orders.created"))
        self.assertFalse(lab.matches("orders.created", "Orders.created"))

    def test_star_is_exactly_one_token(self):
        self.assertTrue(lab.matches("orders.*", "orders.created"))
        self.assertFalse(lab.matches("orders.*", "orders"))
        self.assertFalse(lab.matches("orders.*", "orders.us.created"))

    def test_tail_requires_one_or_more(self):
        self.assertFalse(lab.matches("orders.>", "orders"))
        self.assertTrue(lab.matches("orders.>", "orders.created"))
        self.assertTrue(lab.matches("orders.>", "orders.us.created"))

    def test_root_tail_and_star(self):
        self.assertTrue(lab.matches(">", "orders"))
        self.assertTrue(lab.matches(">", "orders.us.created"))
        self.assertTrue(lab.matches("*", "orders"))
        self.assertFalse(lab.matches("*", "orders.created"))

    def test_mixed_wildcards(self):
        self.assertTrue(lab.matches("orders.*.>", "orders.us.created"))
        self.assertFalse(lab.matches("orders.*.>", "orders.us"))
        self.assertFalse(lab.matches("orders.*.created", "orders.us.cancelled"))

    def test_unicode_literals_are_not_normalized(self):
        self.assertTrue(lab.matches("주문.*", "주문.생성"))
        self.assertFalse(lab.matches("é", "e\u0301"))

    def test_publish_rejects_wildcards(self):
        for subject in ("*", ">", "orders.*", "order*", "orders.>"):
            with self.subTest(subject=subject), self.assertRaises(lab.ModelError):
                lab.subject_tokens(subject)

    def test_bad_pattern_grammar(self):
        for pattern in ("a.>.b", "a.*b", "a.b>", "a.>>", "a.**"):
            with self.subTest(pattern=pattern), self.assertRaises(lab.ModelError):
                lab.subject_tokens(pattern, pattern=True)

    def test_empty_whitespace_control_and_empty_token_rejected(self):
        for subject in ("", ".a", "a.", "a..b", "a b", "a\tb", "a\nb", "a\0b", "a\x7fb"):
            with self.subTest(subject=subject), self.assertRaises(lab.ModelError):
                lab.subject_tokens(subject)

    def test_subject_type_and_profile_limits(self):
        for subject in (None, True, 123, [], {}, "a" * 257, ".".join(["a"] * 33)):
            with self.subTest(subject=subject), self.assertRaises(lab.ModelError):
                lab.subject_tokens(subject)

    def test_pattern_switch_is_boolean(self):
        with self.assertRaises(lab.ModelError):
            lab.subject_tokens("a", pattern="false")

    def test_independent_overlap_oracles(self):
        cases = (("a", "a", True), ("a", "b", False), ("a.>", "a", False),
                 ("a.>", "a.*", True), ("a.*.c", "a.b.*", True),
                 ("a.*.c", "a.b.d", False), (">", "a.b.c", True),
                 ("a.*", "a.*.*", False), ("a.>", "b.>", False),
                 ("a.*.>", "a.b", False), ("a.*.>", "a.b.c.d", True))
        for left, right, expected in cases:
            with self.subTest(left=left, right=right):
                self.assertIs(lab.patterns_overlap(left, right), expected)
                self.assertIs(lab.patterns_overlap(right, left), expected)

    def test_normal_fanout_preserves_distinct_subscriptions(self):
        members = (lab.Subscription("s1", "a.>"), lab.Subscription("s2", "a.*"))
        self.assertEqual(lab.route("a.b", members), ("s1", "s2"))

    def test_one_per_matching_queue_plus_normals(self):
        members = (lab.Subscription("audit", "a.>"), lab.Subscription("w1", "a.*", "q"),
                   lab.Subscription("w2", "a.*", "q"), lab.Subscription("other", "a.*", "r"))
        self.assertEqual(lab.route("a.b", members), ("audit", "other", "w1"))
        self.assertEqual(lab.route("a.b", members, 1), ("audit", "other", "w2"))
        self.assertEqual(lab.route("a.b", members, 2), ("audit", "other", "w1"))

    def test_queue_selection_excludes_nonmatching_members(self):
        members = (lab.Subscription("w1", "a.*", "q"), lab.Subscription("w2", "b.*", "q"))
        self.assertEqual(lab.route("a.x", members, 1), ("w1",))

    def test_no_interest_means_no_delivery(self):
        self.assertEqual(lab.route("a.b", (lab.Subscription("s", "b.>"),)), ())
        self.assertEqual(lab.route("a.b", ()), ())

    def test_bad_subscription_names_and_queues(self):
        for name in (None, [], {}, "", "a b", "*", "a" * 65):
            with self.subTest(name=name), self.assertRaises(lab.ModelError):
                lab.Subscription(name, "a")
            with self.subTest(queue=name), self.assertRaises(lab.ModelError):
                lab.Subscription("ok", "a", "" if name is None else name)

    def test_subscription_collection_validation(self):
        sub = lab.Subscription("s", "a")
        for members in ([sub], (None,), (sub, sub), (sub,) * 257):
            with self.subTest(members=members), self.assertRaises(lab.ModelError):
                lab.route("a", members)

    def test_turn_validation(self):
        for value in BAD_NUMBERS:
            with self.subTest(value=value), self.assertRaises(lab.ModelError):
                lab.route("a", (), value)

    def test_subscriptions_immutable(self):
        member = lab.Subscription("s", "a")
        with self.assertRaises(FrozenInstanceError):
            member.pattern = ">"


class DedupTests(unittest.TestCase):
    def test_first_publish_and_duplicate_receipts(self):
        publisher = lab.DedupPublisher(10)
        self.assertEqual(publisher.publish("a", b"one", 0, "id"), lab.PublishReceipt(1, False))
        self.assertEqual(publisher.publish("a", b"one", 9, "id"), lab.PublishReceipt(1, True))
        self.assertEqual(len(publisher.messages), 1)

    def test_changed_body_does_not_replace_original(self):
        publisher = lab.DedupPublisher(10)
        publisher.publish("a", b"original", 0, "id")
        publisher.publish("a", b"changed", 1, "id")
        self.assertEqual(publisher.messages[0].payload, b"original")

    def test_dedup_is_stream_scope_not_subject_scope(self):
        publisher = lab.DedupPublisher(10)
        publisher.publish("a", b"original", 0, "id")
        self.assertEqual(publisher.publish("b", b"changed", 1, "id"), lab.PublishReceipt(1, True))
        self.assertEqual(publisher.messages[0].subject, "a")

    def test_model_window_boundary_is_half_open(self):
        publisher = lab.DedupPublisher(10)
        publisher.publish("a", b"one", 0, "id")
        self.assertEqual(publisher.publish("a", b"two", 10, "id"), lab.PublishReceipt(2, False))

    def test_retries_do_not_extend_original_window(self):
        publisher = lab.DedupPublisher(10)
        publisher.publish("a", b"one", 0, "id")
        publisher.publish("a", b"one", 9, "id")
        self.assertFalse(publisher.publish("a", b"one", 10, "id").duplicate)
        self.assertTrue(publisher.publish("a", b"one", 19, "id").duplicate)
        self.assertFalse(publisher.publish("a", b"one", 20, "id").duplicate)

    def test_without_id_same_body_is_not_deduplicated(self):
        publisher = lab.DedupPublisher()
        self.assertEqual(publisher.publish("a", b"same", 0), lab.PublishReceipt(1, False))
        self.assertEqual(publisher.publish("a", b"same", 0), lab.PublishReceipt(2, False))

    def test_different_ids_are_independent(self):
        publisher = lab.DedupPublisher()
        publisher.publish("a", b"same", 0, "first")
        self.assertEqual(publisher.publish("a", b"same", 0, "second"), lab.PublishReceipt(2, False))

    def test_empty_payload_is_valid(self):
        publisher = lab.DedupPublisher()
        publisher.publish("a", b"", 0)
        self.assertEqual(publisher.messages[0].payload, b"")

    def test_invalid_window(self):
        for value in (*BAD_NUMBERS, 0):
            with self.subTest(value=value), self.assertRaises(lab.ModelError):
                lab.DedupPublisher(value)

    def test_invalid_payload_and_id_do_not_mutate(self):
        publisher = lab.DedupPublisher()
        for payload in ("body", bytearray(b"body"), None, [], {}, b"x" * 4097):
            with self.subTest(payload=type(payload)), self.assertRaises(lab.ModelError):
                publisher.publish("a", payload, 10)
        for identifier in (True, [], {}, "", "bad key"):
            with self.subTest(identifier=identifier), self.assertRaises(lab.ModelError):
                publisher.publish("a", b"body", 10, identifier)
        self.assertEqual((publisher.clock, publisher.messages), (0, ()))

    def test_bad_and_backward_clock_do_not_mutate(self):
        publisher = lab.DedupPublisher()
        publisher.publish("a", b"one", 5)
        for now in (*BAD_NUMBERS, 4):
            with self.subTest(now=now), self.assertRaises(lab.ModelError):
                publisher.publish("a", b"two", now)
        self.assertEqual((publisher.clock, len(publisher.messages)), (5, 1))

    def test_message_snapshot_is_immutable(self):
        publisher = lab.DedupPublisher()
        publisher.publish("a", b"one", 0)
        snapshot = publisher.messages
        publisher.publish("a", b"two", 1)
        self.assertEqual(len(snapshot), 1)
        with self.assertRaises(FrozenInstanceError):
            snapshot[0].payload = b"changed"

    def test_business_same_key_same_intent_once(self):
        business = lab.BusinessCounter()
        self.assertTrue(business.apply("tenant", "order", b"charge-1"))
        self.assertFalse(business.apply("tenant", "order", b"charge-1"))
        self.assertEqual(business.count, 1)

    def test_business_same_key_conflicting_intent_fails_closed(self):
        business = lab.BusinessCounter()
        business.apply("tenant", "order", b"charge-1")
        with self.assertRaises(lab.ModelError):
            business.apply("tenant", "order", b"charge-2")
        self.assertEqual(business.count, 1)

    def test_business_key_is_tenant_scoped(self):
        business = lab.BusinessCounter()
        business.apply("one", "order", b"charge-1")
        business.apply("two", "order", b"charge-1")
        self.assertEqual(business.count, 2)

    def test_business_invalid_keys_not_hash_errors(self):
        business = lab.BusinessCounter()
        for value in (None, [], {}, True, ""):
            with self.subTest(value=value), self.assertRaises(lab.ModelError):
                business.apply(value, "key", b"x")
            with self.subTest(value=value), self.assertRaises(lab.ModelError):
                business.apply("tenant", value, b"x")
        self.assertEqual(business.count, 0)


class ConsumerTests(unittest.TestCase):
    def test_first_delivery_has_two_sequence_axes(self):
        consumer = lab.ConsumerLedger((10, 20))
        self.assertEqual(consumer.pull(0), lab.Delivery(10, 1, 1, 5))
        self.assertEqual(consumer.pull(0), lab.Delivery(20, 2, 1, 5))

    def test_no_message_returns_none(self):
        self.assertIsNone(lab.ConsumerLedger(()).pull(0))

    def test_redelivery_increments_consumer_not_stream_sequence(self):
        consumer = lab.ConsumerLedger((7,), ack_wait=5)
        consumer.pull(0)
        self.assertIsNone(consumer.pull(4))
        self.assertEqual(consumer.pull(5), lab.Delivery(7, 2, 2, 10))

    def test_max_pending_blocks_new_not_redelivery(self):
        consumer = lab.ConsumerLedger((1, 2), max_pending=1)
        consumer.pull(0)
        self.assertIsNone(consumer.pull(1))
        self.assertEqual(consumer.pull(5), lab.Delivery(1, 2, 2, 10))
        self.assertEqual(consumer.pending, (1,))

    def test_ack_opens_pending_slot(self):
        consumer = lab.ConsumerLedger((1, 2), max_pending=1)
        consumer.pull(0)
        consumer.ack(1, 1)
        self.assertEqual(consumer.pull(1), lab.Delivery(2, 2, 1, 6))

    def test_out_of_order_ack_does_not_skip_unacked_prefix(self):
        consumer = lab.ConsumerLedger((10, 20))
        consumer.pull(0)
        consumer.pull(0)
        consumer.ack(2, 1)
        self.assertEqual((consumer.pending, consumer.settled_prefix), ((10,), 0))
        consumer.ack(1, 1)
        self.assertEqual((consumer.pending, consumer.settled_prefix), ((), 20))

    def test_old_attempt_ack_settles_same_message_after_redelivery(self):
        consumer = lab.ConsumerLedger((1,))
        consumer.pull(0)
        consumer.pull(5)
        self.assertTrue(consumer.ack(1, 6))
        self.assertEqual(consumer.pending, ())
        self.assertFalse(consumer.ack(2, 6))
        self.assertIsNone(consumer.pull(100))

    def test_duplicate_ack_idempotent(self):
        consumer = lab.ConsumerLedger((1,))
        consumer.pull(0)
        self.assertTrue(consumer.ack(1, 0))
        self.assertFalse(consumer.ack(1, 0))
        self.assertEqual(consumer.settled_prefix, 1)

    def test_max_deliver_not_stream_deletion_or_ack(self):
        consumer = lab.ConsumerLedger((1,), max_deliver=2)
        consumer.pull(0)
        consumer.pull(5)
        self.assertIsNone(consumer.pull(10))
        self.assertEqual((consumer.exhausted, consumer.pending, consumer.stream_sequences,
                          consumer.settled_prefix), ((1,), (), (1,), 0))

    def test_max_deliver_one_waits_for_deadline_then_frees_slot(self):
        consumer = lab.ConsumerLedger((1, 2), max_deliver=1, max_pending=1)
        consumer.pull(0)
        self.assertIsNone(consumer.pull(4))
        self.assertEqual(consumer.pull(5), lab.Delivery(2, 2, 1, 10))
        self.assertEqual(consumer.exhausted, (1,))

    def test_late_ack_can_settle_exhausted_message_in_model(self):
        consumer = lab.ConsumerLedger((1,), max_deliver=1)
        consumer.pull(0)
        consumer.pull(5)
        self.assertTrue(consumer.ack(1, 6))
        self.assertEqual((consumer.exhausted, consumer.settled_prefix), ((), 1))

    def test_backoff_replaces_ack_wait_and_reuses_last_entry(self):
        consumer = lab.ConsumerLedger((1,), ack_wait=100, max_deliver=4, backoff=(2, 7))
        self.assertEqual(consumer.pull(0), lab.Delivery(1, 1, 1, 2))
        self.assertEqual(consumer.pull(2), lab.Delivery(1, 2, 2, 9))
        self.assertEqual(consumer.pull(9), lab.Delivery(1, 3, 3, 16))
        self.assertEqual(consumer.pull(16), lab.Delivery(1, 4, 4, 23))
        self.assertIsNone(consumer.pull(23))

    def test_due_order_is_explicit_teaching_rule(self):
        consumer = lab.ConsumerLedger((1, 2, 3), max_pending=2)
        consumer.pull(0)
        consumer.pull(0)
        self.assertEqual(consumer.pull(5).stream_sequence, 1)
        self.assertEqual(consumer.pull(5).stream_sequence, 2)

    def test_sequences_validate_before_sort_or_hash(self):
        for sequences in ([1], (True,), (1.0,), ([],), ({},), (0,), (2, 1), (1, 1), tuple(range(1, 4098))):
            with self.subTest(sequences=type(sequences)), self.assertRaises(lab.ModelError):
                lab.ConsumerLedger(sequences)

    def test_numeric_configuration_is_strict_positive_integer(self):
        for keyword in ("ack_wait", "max_pending", "max_deliver"):
            for value in (*BAD_NUMBERS, 0):
                with self.subTest(keyword=keyword, value=value), self.assertRaises(lab.ModelError):
                    lab.ConsumerLedger((1,), **{keyword: value})

    def test_backoff_validation(self):
        for backoff in ([1], (True,), (1.0,), (0,), ([],), (1, 2, 3, 4)):
            with self.subTest(backoff=backoff), self.assertRaises(lab.ModelError):
                lab.ConsumerLedger((1,), backoff=backoff)

    def test_invalid_pull_clocks_do_not_add_deliveries(self):
        consumer = lab.ConsumerLedger((1, 2))
        consumer.pull(5)
        for now in (*BAD_NUMBERS, 4):
            with self.subTest(now=now), self.assertRaises(lab.ModelError):
                consumer.pull(now)
        self.assertEqual(consumer.deliveries, (lab.Delivery(1, 1, 1, 10),))

    def test_ack_unknown_invalid_and_backward_inputs(self):
        consumer = lab.ConsumerLedger((1,))
        consumer.pull(5)
        for sequence in (*BAD_NUMBERS, 0, 2):
            with self.subTest(sequence=sequence), self.assertRaises(lab.ModelError):
                consumer.ack(sequence, 5)
        with self.assertRaises(lab.ModelError):
            consumer.ack(1, 4)
        with self.assertRaises(lab.ModelError):
            consumer.ack(1, True)
        self.assertEqual(consumer.pending, (1,))

    def test_delivery_snapshot_immutable(self):
        consumer = lab.ConsumerLedger((1,))
        delivery = consumer.pull(0)
        snapshot = consumer.deliveries
        consumer.pull(5)
        self.assertEqual(len(snapshot), 1)
        with self.assertRaises(FrozenInstanceError):
            delivery.attempt = 50


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.consumers = (lab.Subscription("a", "orders.*"), lab.Subscription("b", "orders.>"))

    def test_limits_ack_does_not_delete(self):
        store = lab.RetentionStore("limits", self.consumers)
        store.publish("orders.created", b"x", 0)
        store.deliver(1, "a", 0)
        self.assertTrue(store.ack(1, "a", 1))
        self.assertEqual([message.sequence for message in store.messages], [1])
        self.assertEqual(store.removals, ())

    def test_interest_waits_for_all_matching_consumers(self):
        store = lab.RetentionStore("interest", self.consumers)
        store.publish("orders.created", b"x", 0)
        store.deliver(1, "a", 0)
        store.deliver(1, "b", 0)
        store.ack(1, "a", 1)
        self.assertEqual(len(store.messages), 1)
        store.ack(1, "b", 1)
        self.assertEqual(store.messages, ())
        self.assertEqual(store.removals, (lab.Removal(1, "all-interest-acked"),))

    def test_interest_only_matching_consumers_gate_deletion(self):
        store = lab.RetentionStore("interest", (lab.Subscription("a", "orders.*"),
                                                lab.Subscription("b", "payments.*")))
        store.publish("orders.created", b"x", 0)
        store.deliver(1, "a", 0)
        store.ack(1, "a", 1)
        self.assertEqual(store.messages, ())

    def test_interest_without_consumers_removes_immediately(self):
        store = lab.RetentionStore("interest")
        self.assertEqual(store.publish("orders.created", b"x", 0), 1)
        self.assertEqual(store.messages, ())
        self.assertEqual(store.removals, (lab.Removal(1, "no-interest"),))

    def test_interest_nonmatching_consumers_are_no_interest(self):
        store = lab.RetentionStore("interest", (lab.Subscription("a", "payments.*"),))
        store.publish("orders.created", b"x", 0)
        self.assertEqual(store.removals, (lab.Removal(1, "no-interest"),))

    def test_workqueue_without_consumer_keeps_work(self):
        store = lab.RetentionStore("workqueue")
        store.publish("orders.created", b"x", 0)
        self.assertEqual(len(store.messages), 1)

    def test_workqueue_ack_deletes_after_delivery(self):
        store = lab.RetentionStore("workqueue", (self.consumers[0],))
        store.publish("orders.created", b"x", 0)
        store.deliver(1, "a", 0)
        store.ack(1, "a", 1)
        self.assertEqual((store.messages, store.removals), ((), (lab.Removal(1, "workqueue-ack"),)))

    def test_workqueue_rejects_overlapping_filters(self):
        with self.assertRaises(lab.ModelError):
            lab.RetentionStore("workqueue", self.consumers)

    def test_workqueue_nonoverlapping_filters_supported(self):
        store = lab.RetentionStore("workqueue", (lab.Subscription("a", "orders.us"),
                                                 lab.Subscription("b", "orders.eu")))
        store.publish("orders.us", b"x", 0)
        store.publish("orders.eu", b"y", 0)
        store.deliver(1, "a", 0)
        store.ack(1, "a", 1)
        self.assertEqual([message.sequence for message in store.messages], [2])

    def test_all_policies_age_out_unacked_messages(self):
        for policy in ("limits", "interest", "workqueue"):
            with self.subTest(policy=policy):
                store = lab.RetentionStore(policy, (self.consumers[0],), max_age=5)
                store.publish("orders.created", b"x", 0)
                store.deliver(1, "a", 0)
                store.advance(4)
                self.assertEqual(len(store.messages), 1)
                store.advance(5)
                self.assertEqual((store.messages, store.removals), ((), (lab.Removal(1, "max-age"),)))

    def test_all_policies_discard_old_even_if_unacked(self):
        for policy in ("limits", "interest", "workqueue"):
            with self.subTest(policy=policy):
                store = lab.RetentionStore(policy, (self.consumers[0],), max_messages=1)
                store.publish("orders.created", b"x", 0)
                store.publish("orders.created", b"y", 1)
                self.assertEqual([message.sequence for message in store.messages], [2])
                self.assertEqual(store.removals, (lab.Removal(1, "max-messages-discard-old"),))

    def test_sequence_does_not_reset_after_removal(self):
        store = lab.RetentionStore("limits", max_age=1)
        self.assertEqual(store.publish("a", b"x", 0), 1)
        store.advance(1)
        self.assertEqual(store.publish("a", b"y", 1), 2)

    def test_duplicate_ack_does_not_repeat_removal(self):
        store = lab.RetentionStore("workqueue", (self.consumers[0],))
        store.publish("orders.created", b"x", 0)
        store.deliver(1, "a", 0)
        self.assertTrue(store.ack(1, "a", 1))
        self.assertFalse(store.ack(1, "a", 1))
        self.assertEqual(len(store.removals), 1)

    def test_ack_without_delivery_rejected(self):
        store = lab.RetentionStore("interest", self.consumers)
        store.publish("orders.created", b"x", 0)
        with self.assertRaises(lab.ModelError):
            store.ack(1, "a", 10)
        self.assertEqual(len(store.messages), 1)
        self.assertTrue(store.deliver(1, "a", 1))

    def test_ack_after_age_limit_cannot_resurrect(self):
        store = lab.RetentionStore("interest", self.consumers, max_age=5)
        store.publish("orders.created", b"x", 0)
        store.deliver(1, "a", 0)
        self.assertFalse(store.ack(1, "a", 5))
        self.assertEqual(store.removals, (lab.Removal(1, "max-age"),))

    def test_delivery_after_age_limit_is_absent(self):
        store = lab.RetentionStore("limits", self.consumers, max_age=5)
        store.publish("orders.created", b"x", 0)
        self.assertFalse(store.deliver(1, "a", 5))

    def test_age_removal_precedes_count_enforcement(self):
        store = lab.RetentionStore("limits", max_age=5, max_messages=1)
        store.publish("a", b"x", 0)
        store.publish("a", b"y", 5)
        self.assertEqual(store.removals, (lab.Removal(1, "max-age"),))

    def test_policy_and_numeric_configuration_rejected(self):
        for policy in (None, True, [], {}, "", "Interest", "other"):
            with self.subTest(policy=policy), self.assertRaises(lab.ModelError):
                lab.RetentionStore(policy)
        for keyword in ("max_messages", "max_age"):
            for value in (*BAD_NUMBERS, 0):
                with self.subTest(keyword=keyword, value=value), self.assertRaises(lab.ModelError):
                    lab.RetentionStore("limits", **{keyword: value})

    def test_core_queue_subscriptions_not_retention_consumers(self):
        with self.assertRaises(lab.ModelError):
            lab.RetentionStore("limits", (lab.Subscription("a", "a", "queue"),))

    def test_unknown_consumer_and_sequence_rejected(self):
        store = lab.RetentionStore("limits", self.consumers)
        store.publish("orders.created", b"x", 0)
        for method in (store.deliver, store.ack):
            with self.assertRaises(lab.ModelError):
                method(2, "a", 0)
            with self.assertRaises(lab.ModelError):
                method(1, "unknown", 0)
            for value in ([], {}, True, 1.0):
                with self.subTest(value=value), self.assertRaises(lab.ModelError):
                    method(value, "a", 0)

    def test_filter_mismatch_rejected(self):
        store = lab.RetentionStore("limits", self.consumers)
        store.publish("payments.created", b"x", 0)
        for method in (store.deliver, store.ack):
            with self.assertRaises(lab.ModelError):
                method(1, "a", 0)

    def test_invalid_publish_leaves_state_unchanged(self):
        store = lab.RetentionStore("limits")
        for subject, payload, now in (("a.*", b"x", 5), ("a", [], 5), ("a", b"x", True)):
            with self.assertRaises(lab.ModelError):
                store.publish(subject, payload, now)
        self.assertEqual(store.publish("a", b"x", 0), 1)

    def test_advance_rejects_backward_and_noninteger_clock(self):
        store = lab.RetentionStore("limits")
        store.advance(5)
        for value in (*BAD_NUMBERS, 4):
            with self.subTest(value=value), self.assertRaises(lab.ModelError):
                store.advance(value)

    def test_snapshots_and_removals_immutable(self):
        store = lab.RetentionStore("limits", max_age=1)
        store.publish("a", b"x", 0)
        messages = store.messages
        store.advance(1)
        self.assertEqual(len(messages), 1)
        with self.assertRaises(FrozenInstanceError):
            store.removals[0].reason = "changed"


class ScenarioAndCliTests(unittest.TestCase):
    def test_subject_scenario_literal_oracle_and_bad_control(self):
        result = lab.subject_routing_lab()
        self.assertEqual(result["ordinary_and_queues"], ("audit", "billing", "metrics", "worker-a"))
        self.assertEqual(result["next_example_turn"], ("audit", "billing", "metrics", "worker-b"))
        self.assertTrue(result["parent_does_not_match_tail"])
        self.assertTrue(result["bad_control_zero_token_tail_would_match"])
        self.assertEqual(result["no_interest_deliveries"], ())

    def test_dedup_scenario_literal_oracle(self):
        self.assertEqual(lab.publish_dedup_lab(), {
            "receipts": [{"sequence": 1, "duplicate": False}, {"sequence": 1, "duplicate": True},
                         {"sequence": 2, "duplicate": False}],
            "stored_payloads": ["order-1", "order-1"], "naive_external_effects": 2,
            "idempotent_external_effects": 1, "publisher_ack_is_external_commit": False})

    def test_consumer_scenario_literal_oracle(self):
        result = lab.ack_redelivery_lab()
        self.assertEqual(result["first"], {"stream_sequence": 1, "consumer_sequence": 1, "attempt": 1, "deadline": 5})
        self.assertEqual(result["redelivery"], {"stream_sequence": 1, "consumer_sequence": 2, "attempt": 2, "deadline": 10})
        self.assertEqual(result["next_message"]["stream_sequence"], 2)
        self.assertEqual(result["exhausted"], (2,))
        self.assertEqual(result["stream_still_contains"], (1, 2))
        self.assertEqual(result["settled_prefix_not_server_ack_floor"], 1)
        self.assertEqual(result["naive_effects_for_first_message"], 2)
        self.assertEqual(result["idempotent_effects_for_first_message"], 1)
        self.assertFalse(result["automatic_dlq_created"])

    def test_retention_scenario_literal_oracle(self):
        self.assertEqual(lab.retention_gates_lab(), {
            "limits_after_all_acks": 1, "interest_after_all_acks": 0, "interest_without_consumers": 0,
            "workqueue_removals": [{"sequence": 1, "reason": "workqueue-ack"}, {"sequence": 2, "reason": "max-age"}],
            "retention_is_automatic_business_exactly_once": False})

    def test_scenarios_do_not_share_mutable_state(self):
        for function in lab.LABS.values():
            self.assertEqual(function(), function())

    def test_runtime_oracle_accepts_all_good_scenarios(self):
        for name, function in lab.LABS.items():
            self.assertIsNone(lab.verify_result(name, function()))

    def test_runtime_oracle_detects_each_corrupted_top_level_field(self):
        for name, function in lab.LABS.items():
            original = function()
            for key in original:
                broken = copy.deepcopy(original)
                broken[key] = None
                with self.subTest(lab=name, field=key), self.assertRaises(lab.ModelError):
                    lab.verify_result(name, broken)

    def test_runtime_oracle_does_not_conflate_bool_int_and_float(self):
        for value in (True, 1.0, "1"):
            broken = lab.publish_dedup_lab()
            broken["receipts"][0]["sequence"] = value
            with self.subTest(value=value), self.assertRaises(lab.ModelError):
                lab.verify_result("publish-dedup", broken)

    def test_runtime_oracle_rejects_missing_and_extra_keys(self):
        broken = lab.subject_routing_lab()
        del broken["no_interest_deliveries"]
        with self.assertRaises(lab.ModelError):
            lab.verify_result("subject-routing", broken)
        broken = lab.subject_routing_lab()
        broken["invented_claim"] = True
        with self.assertRaises(lab.ModelError):
            lab.verify_result("subject-routing", broken)

    def test_runtime_oracle_rejects_invalid_name_and_result_shapes(self):
        for name in ("unknown", None, [], {}):
            with self.subTest(name=name), self.assertRaises(lab.ModelError):
                lab.verify_result(name, {})
        for value in (None, [], True, "ok"):
            with self.subTest(value=value), self.assertRaises(lab.ModelError):
                lab.verify_result("subject-routing", value)

    def test_cli_wrong_result_exits_nonzero_without_success_json(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        broken = lab.publish_dedup_lab()
        broken["idempotent_external_effects"] = 2
        with mock.patch.dict(lab.LABS, {"publish-dedup": lambda: broken}):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(lab.main(["--lab", "all"]), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("publish-dedup", stderr.getvalue())
        self.assertIn("independent literal oracle", stderr.getvalue())

    def test_cli_model_error_exits_nonzero(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(lab.LABS, {"subject-routing": mock.Mock(side_effect=lab.ModelError("injected failure"))}):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(lab.main(["--lab", "subject-routing"]), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("injected failure", stderr.getvalue())

    def test_cli_default_only_help(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(lab.main([]), 0)
        self.assertIn("usage:", stream.getvalue())
        self.assertNotIn('"receipts"', stream.getvalue())

    def test_cli_list(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            lab.main(["--list"])
        self.assertEqual(stream.getvalue().splitlines(), list(lab.LAB_NAMES))

    def test_cli_each_and_all_valid_json(self):
        for name in (*lab.LAB_NAMES, "all"):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(lab.main(["--lab", name]), 0)
            self.assertEqual(list(json.loads(stream.getvalue())), list(lab.LAB_NAMES) if name == "all" else [name])

    def test_cli_bad_selection_and_conflicting_flags(self):
        for argv in (["--lab", "unknown"], ["--list", "--lab", "all"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                lab.main(argv)
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
