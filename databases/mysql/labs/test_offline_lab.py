"""CPU model contracts; these tests do NOT execute MySQL or test persistence."""
import contextlib
from dataclasses import FrozenInstanceError
import io
import itertools
import json
import unittest
from unittest.mock import patch

from offline_lab import (LABS, MAX_ID, CommitEvidence, ReadView, RecordLock, Row,
                         Version, changes_visible, commit_recovery_lab, commit_trace,
                         compatible, deadlock_lab, find_cycle, index_lookup,
                         index_lookup_lab, main, make_read_view, read_value,
                         read_view_lab, recover_after_volatile_loss, require,
                         statement_view, visible_version, wait_for_graph)


class IndexLookupTests(unittest.TestCase):
    def setUp(self):
        self.rows = [Row(4, "A", 20, "four"), Row(1, "A", 10, "one"),
                     Row(3, "B", 15, "three"), Row(2, "A", 20, "two"), Row(5, "A", 30, "five")]

    def test_covering_literal_rows_and_zero_fetches(self):
        result = index_lookup(self.rows, "A", 10, 20, ("pk", "score"))
        self.assertEqual(result.rows, ((1, 10), (2, 20), (4, 20)))
        self.assertEqual((result.secondary_entries, result.clustered_lookups, result.covering), (3, 0, True))

    def test_payload_projection_fetches_clustered_records(self):
        result = index_lookup(self.rows, "A", 10, 20, ("pk", "payload"))
        self.assertEqual(result.rows, ((1, "one"), (2, "two"), (4, "four")))
        self.assertEqual((result.secondary_entries, result.clustered_lookups, result.covering), (3, 3, False))

    def test_inclusive_range_and_pk_tie_order(self):
        self.assertEqual(index_lookup(self.rows, "A", 20, 20, ["pk"]).rows, ((2,), (4,)))

    def test_leading_tenant_predicate(self):
        self.assertEqual(index_lookup(self.rows, "B", 0, 100, ["tenant", "pk"]).rows, (("B", 3),))

    def test_projection_order_and_repeated_values(self):
        self.assertEqual(index_lookup(self.rows, "A", 20, 20, ["score", "tenant"]).rows,
                         ((20, "A"), (20, "A")))

    def test_no_match_has_no_record_fetches(self):
        for tenant, low, high in (("C", 0, 100), ("A", 11, 19), ("A", 31, 99)):
            with self.subTest(tenant=tenant, low=low):
                result = index_lookup(self.rows, tenant, low, high, ["payload"])
                self.assertEqual((result.rows, result.secondary_entries, result.clustered_lookups), ((), 0, 0))

    def test_empty_table(self):
        self.assertEqual(index_lookup([], "A", 0, 0, ["pk"]).rows, ())

    def test_signed_score_and_maximum_pk_bounds(self):
        rows = [Row(MAX_ID, "A", MAX_ID, ""), Row(1, "A", -MAX_ID, "")]
        self.assertEqual(index_lookup(rows, "A", -MAX_ID, MAX_ID, ["pk"]).rows, ((1,), (MAX_ID,)))

    def test_matches_independent_full_scan_reference(self):
        # Full scan fixture and sort, not bisect or the implementation's tuple path.
        for tenant, low, high in itertools.product(("A", "B", "C"), (0, 10, 20), (20, 30)):
            expected = tuple((row.pk, row.payload) for row in sorted(self.rows, key=lambda row: (row.score, row.pk))
                             if row.tenant == tenant and low <= row.score <= high)
            with self.subTest(tenant=tenant, low=low, high=high):
                self.assertEqual(index_lookup(self.rows, tenant, low, high, ["pk", "payload"]).rows, expected)

    def test_input_order_does_not_change_output(self):
        self.assertEqual(index_lookup(self.rows, "A", 0, 100, ["pk"]),
                         index_lookup(list(reversed(self.rows)), "A", 0, 100, ["pk"]))

    def test_inputs_not_mutated_and_result_frozen(self):
        original = self.rows.copy()
        projection = ["pk", "payload"]
        result = index_lookup(self.rows, "A", 0, 100, projection)
        self.assertEqual(self.rows, original)
        self.assertEqual(projection, ["pk", "payload"])
        with self.assertRaises(FrozenInstanceError):
            result.clustered_lookups = 0

    def test_duplicate_primary_key_rejected(self):
        with self.assertRaises(ValueError):
            index_lookup([Row(1, "A", 1, ""), Row(1, "B", 2, "")], "A", 0, 2, ["pk"])

    def test_invalid_rows_rejected(self):
        for rows in (None, [None], [Row(0, "A", 1, "")], [Row(True, "A", 1, "")],
                     [Row(1, "", 1, "")], [Row(1, "A", float("nan"), "")], [Row(1, "A", 1, None)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                index_lookup(rows, "A", 0, 10, ["pk"])

    def test_invalid_range_rejected(self):
        for low, high in ((2, 1), (True, 5), (0.5, 5), (0, float("inf")), (-MAX_ID - 1, 0), (0, MAX_ID + 1)):
            with self.subTest(low=low, high=high), self.assertRaises(ValueError):
                index_lookup(self.rows, "A", low, high, ["pk"])

    def test_invalid_projection_and_tenant(self):
        for projection in (None, [], "pk", ["unknown"], ["pk", "pk"], [None]):
            with self.subTest(projection=projection), self.assertRaises(ValueError):
                index_lookup(self.rows, "A", 0, 10, projection)
        with self.assertRaises(ValueError):
            index_lookup(self.rows, "", 0, 10, ["pk"])

    def test_lab_literal_work_counts(self):
        result = index_lookup_lab()
        self.assertEqual(result["covering"]["clustered_lookups"], 0)
        self.assertEqual(result["noncovering"]["clustered_lookups"], 3)


class ReadViewTests(unittest.TestCase):
    def setUp(self):
        self.view = make_read_view(20, 30, [12, 20, 25])
        self.history = (Version(25, "new"), Version(8, "old"))

    def test_named_boundaries_exclude_creator(self):
        self.assertEqual(self.view, ReadView(20, 12, 30, frozenset({12, 25})))

    def test_visibility_boundary_matrix(self):
        # Explicit expected set over an entire small allocation interval.
        invisible = {12, 25, 30, 31}
        self.assertEqual([trx for trx in range(1, 32) if not changes_visible(self.view, trx)], sorted(invisible))

    def test_own_transaction_visible_even_when_newer_than_up_limit(self):
        self.assertTrue(changes_visible(self.view, 20))

    def test_unassigned_read_only_creator_zero(self):
        view = make_read_view(0, 10, [])
        self.assertTrue(changes_visible(view, 9))
        self.assertFalse(changes_visible(view, 10))

    def test_empty_active_ids_collapse_boundaries(self):
        self.assertEqual(make_read_view(2, 10, {2}), ReadView(2, 10, 10, frozenset()))

    def test_active_collection_is_captured_not_referenced(self):
        active = [12, 20, 25]
        view = make_read_view(20, 30, active)
        active.clear()
        self.assertEqual(view.active_ids, frozenset({12, 25}))
        with self.assertRaises(FrozenInstanceError):
            view.low_limit_id = 31

    def test_skips_invisible_head_to_older_version(self):
        self.assertEqual(visible_version(self.view, self.history), Version(8, "old"))

    def test_visible_tombstone_stops_traversal(self):
        history = (Version(15, None, True), Version(8, "old"))
        self.assertEqual(visible_version(self.view, history), Version(15, None, True))
        self.assertIsNone(read_value(self.view, history))

    def test_invisible_tombstone_keeps_older_row(self):
        self.assertEqual(read_value(self.view, (Version(25, None, True), Version(8, "old"))), "old")

    def test_own_delete_visible(self):
        self.assertIsNone(read_value(self.view, (Version(20, None, True), Version(8, "old"))))

    def test_own_write_overrides_old_snapshot(self):
        self.assertEqual(read_value(self.view, (Version(20, "own"), *self.history)), "own")

    def test_no_visible_version_or_empty_history(self):
        self.assertIsNone(visible_version(self.view, [Version(30, "future")]))
        self.assertIsNone(visible_version(self.view, []))

    def test_physical_history_is_not_sorted_by_transaction_id(self):
        # An older-started transaction can produce a later physical version.
        self.assertEqual(read_value(self.view, (Version(8, "latest"), Version(15, "earlier"))), "latest")

    def test_latest_of_multiple_own_versions(self):
        self.assertEqual(read_value(self.view, (Version(20, "second"), Version(20, "first"))), "second")

    def test_rc_statement_refresh_exposes_committed_writer(self):
        new_view = statement_view("RC", 20, 31, {20}, self.view)
        self.assertEqual(read_value(new_view, self.history), "new")
        self.assertEqual(read_value(self.view, self.history), "old")

    def test_rr_holds_first_consistent_read_view(self):
        next_view = statement_view("RR", 20, 31, {20}, self.view)
        self.assertIs(next_view, self.view)
        self.assertEqual(read_value(next_view, self.history), "old")

    def test_first_statement_captures_view_for_both_levels(self):
        self.assertEqual(statement_view("RC", 20, 30, [12, 20, 25]), self.view)
        self.assertEqual(statement_view("RR", 20, 30, [12, 20, 25]), self.view)

    def test_old_invisible_insert_can_become_visible_in_rc(self):
        history = (Version(30, "inserted"),)
        self.assertIsNone(read_value(self.view, history))
        self.assertEqual(read_value(statement_view("RC", 20, 31, [20], self.view), history), "inserted")

    def test_invalid_view_inputs(self):
        for creator, next_id, active in ((True, 30, []), (30, 30, []), (0, 0, []), (0, 30, [30]),
                                         (0, 30, [1, 1]), (0, 30, [False]), (0, 30, "12"), (0, float("inf"), [])):
            with self.subTest(creator=creator, next_id=next_id, active=active), self.assertRaises(ValueError):
                make_read_view(creator, next_id, active)

    def test_manually_corrupt_view_rejected(self):
        for view in (None, ReadView(20, 10, 30, frozenset({12})), ReadView(20, 20, 30, frozenset({20})),
                     ReadView(0, 30, 30, set()), ReadView(0, 30, 30, frozenset({31}))):
            with self.subTest(view=view), self.assertRaises(ValueError):
                changes_visible(view, 1)

    def test_invalid_version_and_history_rejected_even_after_visible_head(self):
        for bad in (None, Version(0, "x"), Version(True, "x"), Version(1, None),
                    Version(1, "x", True), Version(1, "x", 1)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                read_value(self.view, [Version(8, "valid"), bad])
        with self.assertRaises(ValueError):
            read_value(self.view, None)

    def test_invalid_visibility_id_rejected(self):
        for trx_id in (0, True, -1, float("nan"), MAX_ID + 1):
            with self.subTest(trx_id=trx_id), self.assertRaises(ValueError):
                changes_visible(self.view, trx_id)

    def test_cross_transaction_or_time_reversal_view_reuse_rejected(self):
        for isolation, creator, next_id in (("RR", 21, 31), ("RR", 20, 29), ("SERIALIZABLE", 20, 31)):
            with self.subTest(isolation=isolation, creator=creator, next_id=next_id), self.assertRaises(ValueError):
                statement_view(isolation, creator, next_id, [], self.view)

    def test_history_input_not_mutated(self):
        history = list(self.history)
        read_value(self.view, history)
        self.assertEqual(history, list(self.history))

    def test_lab_expected_values(self):
        self.assertEqual(read_view_lab()["first_RR_RC_values"], ["old", "old", "new"])


class DeadlockTests(unittest.TestCase):
    def test_sx_compatibility_matrix(self):
        self.assertEqual([[compatible(a, b) for b in ("S", "X")] for a in ("S", "X")],
                         [[True, False], [False, False]])

    def test_waiter_to_holder_direction(self):
        self.assertEqual(wait_for_graph([RecordLock("T1", "r", "X")], [RecordLock("T2", "r", "S")]),
                         {"T1": frozenset(), "T2": frozenset({"T1"})})

    def test_shared_holders_block_exclusive_request(self):
        graph = wait_for_graph([RecordLock("T1", "r", "S"), RecordLock("T2", "r", "S")],
                               [RecordLock("T3", "r", "X")])
        self.assertEqual(graph["T3"], frozenset({"T1", "T2"}))

    def test_shared_request_is_compatible_with_shared_holder(self):
        self.assertEqual(wait_for_graph([RecordLock("T1", "r", "S")], [RecordLock("T2", "r", "S")])["T2"],
                         frozenset())

    def test_different_resources_do_not_conflict(self):
        self.assertEqual(wait_for_graph([RecordLock("T1", "r1", "X")], [RecordLock("T2", "r2", "X")])["T2"],
                         frozenset())

    def test_own_lock_does_not_create_self_wait(self):
        self.assertEqual(wait_for_graph([RecordLock("T1", "r", "S")], [RecordLock("T1", "r", "X")]),
                         {"T1": frozenset()})

    def test_two_way_record_cycle(self):
        self.assertEqual(deadlock_lab()["cycle"], ("T1", "T2", "T1"))

    def test_three_way_cycle_with_tail(self):
        graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}, "tail": {"a"}}
        self.assertEqual(find_cycle(graph), ("a", "b", "c", "a"))

    def test_acyclic_diamond_has_waits_but_no_deadlock(self):
        self.assertEqual(find_cycle({"a": {"b", "c"}, "b": {"d"}, "c": {"d"}, "d": set()}), ())

    def test_empty_and_isolated_graph(self):
        self.assertEqual(find_cycle({}), ())
        self.assertEqual(find_cycle({"a": set()}), ())

    def test_generic_graph_self_cycle(self):
        # Generic graph API can accept self-edges; the record model never creates one.
        self.assertEqual(find_cycle({"a": {"a"}}), ("a", "a"))

    def test_all_three_node_directed_graphs_against_transitive_closure(self):
        vertices = ("a", "b", "c")
        possible_edges = [(a, b) for a in vertices for b in vertices if a != b]
        for mask in range(1 << len(possible_edges)):
            graph = {node: set() for node in vertices}
            for offset, (a, b) in enumerate(possible_edges):
                if mask & (1 << offset):
                    graph[a].add(b)
            reachable = {(a, b) for a in vertices for b in graph[a]}
            for middle in vertices:
                for left in vertices:
                    for right in vertices:
                        if (left, middle) in reachable and (middle, right) in reachable:
                            reachable.add((left, right))
            expected = any((node, node) in reachable for node in vertices)
            cycle = find_cycle(graph)
            with self.subTest(mask=mask):
                self.assertEqual(bool(cycle), expected)
                if cycle:
                    self.assertEqual(cycle[0], cycle[-1])
                    self.assertTrue(all(b in graph[a] for a, b in zip(cycle, cycle[1:])))

    def test_long_acyclic_graph_avoids_recursive_stack_limit(self):
        graph = {str(index): {str(index + 1)} for index in range(1500)}
        graph["1500"] = set()
        self.assertEqual(find_cycle(graph), ())

    def test_invalid_granted_conflicts_rejected(self):
        with self.assertRaises(ValueError):
            wait_for_graph([RecordLock("a", "r", "X"), RecordLock("b", "r", "S")], [])

    def test_duplicate_grant_and_multiple_pending_requests_rejected(self):
        lock = RecordLock("a", "r", "S")
        with self.assertRaises(ValueError):
            wait_for_graph([lock, lock], [])
        with self.assertRaises(ValueError):
            wait_for_graph([], [lock, RecordLock("a", "other", "X")])

    def test_invalid_lock_modes_and_resources_rejected(self):
        for lock in (None, RecordLock("", "r", "S"), RecordLock("a", "", "S"), RecordLock("a", "r", "GAP")):
            with self.subTest(lock=lock), self.assertRaises(ValueError):
                wait_for_graph([lock], [])
        with self.assertRaises(ValueError):
            compatible("S", "IS")

    def test_invalid_graph_rejected(self):
        for graph in (None, {"a": {"missing"}}, {"a": ["a"]}, {"": set()}, {"a": {None}}):
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                find_cycle(graph)

    def test_inputs_unchanged_and_edges_immutable(self):
        holders = [RecordLock("a", "r", "X")]
        requests = [RecordLock("b", "r", "S")]
        result = wait_for_graph(holders, requests)
        find_cycle(result)
        self.assertEqual(holders, [RecordLock("a", "r", "X")])
        self.assertEqual(requests, [RecordLock("b", "r", "S")])
        self.assertIsInstance(result["b"], frozenset)


class CommitEvidenceTests(unittest.TestCase):
    def test_entire_evidence_truth_table_literal_oracle(self):
        expected = {"absent": ["ABSENT", "ABSENT", "INCONSISTENT"],
                    "prepared": ["ROLLBACK", "ROLLBACK", "COMMIT"],
                    "committed": ["INCONSISTENT", "INCONSISTENT", "COMMIT"]}
        for redo, outcomes in expected.items():
            self.assertEqual([recover_after_volatile_loss(CommitEvidence(redo, binlog))
                              for binlog in ("absent", "written", "durable")], outcomes)

    def test_prepare_and_complete_durable_xid_commit_without_engine_commit_record(self):
        self.assertEqual(recover_after_volatile_loss(CommitEvidence("prepared", "durable")), "COMMIT")

    def test_written_but_unsynced_binlog_can_be_lost(self):
        self.assertEqual(recover_after_volatile_loss(CommitEvidence("prepared", "written")), "ROLLBACK")

    def test_durable_commit_without_binlog_is_not_rolled_back(self):
        self.assertEqual(recover_after_volatile_loss(CommitEvidence("committed", "written")), "INCONSISTENT")

    def test_binlog_without_engine_prepare_is_not_called_recoverable_commit(self):
        self.assertEqual(recover_after_volatile_loss(CommitEvidence("absent", "durable")), "INCONSISTENT")

    def test_ack_does_not_change_durable_evidence_decision(self):
        for redo, binlog in itertools.product(("absent", "prepared", "committed"), ("absent", "written", "durable")):
            with self.subTest(redo=redo, binlog=binlog):
                self.assertEqual(recover_after_volatile_loss(CommitEvidence(redo, binlog, True)),
                                 recover_after_volatile_loss(CommitEvidence(redo, binlog, False)))

    def test_strict_trace_all_crash_cuts(self):
        trace = commit_trace()
        self.assertEqual([stage for stage, _ in trace],
                         ["initial", "prepare", "binlog-write", "binlog-sync", "engine-commit", "ack-received"])
        self.assertEqual([recover_after_volatile_loss(evidence) for _, evidence in trace],
                         ["ABSENT", "ROLLBACK", "ROLLBACK", "COMMIT", "COMMIT", "COMMIT"])

    def test_lost_ack_does_not_prove_rollback(self):
        evidence = commit_trace()[-2][1]
        self.assertFalse(evidence.ack_received)
        self.assertEqual(recover_after_volatile_loss(evidence), "COMMIT")

    def test_relaxed_both_acknowledged_change_can_disappear(self):
        evidence = commit_trace(False, False)[-1][1]
        self.assertTrue(evidence.ack_received)
        self.assertEqual(recover_after_volatile_loss(evidence), "ABSENT")

    def test_relaxed_binlog_can_diverge_from_durable_engine_commit(self):
        trace = commit_trace(True, False)
        self.assertNotIn("binlog-sync", [stage for stage, _ in trace])
        self.assertEqual(recover_after_volatile_loss(trace[-1][1]), "INCONSISTENT")

    def test_relaxed_redo_can_leave_only_durable_binlog(self):
        self.assertEqual(recover_after_volatile_loss(commit_trace(False, True)[-1][1]), "INCONSISTENT")

    def test_evidence_and_trace_immutable(self):
        trace = commit_trace()
        self.assertIsInstance(trace, tuple)
        with self.assertRaises(FrozenInstanceError):
            trace[-1][1].ack_received = False

    def test_invalid_state_or_policy_rejected(self):
        for evidence in (None, CommitEvidence("written", "durable"), CommitEvidence("prepared", "partial"),
                         CommitEvidence("absent", "absent", 1)):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                recover_after_volatile_loss(evidence)
        for redo, binlog in ((1, True), (True, 0), (None, True)):
            with self.subTest(redo=redo, binlog=binlog), self.assertRaises(ValueError):
                commit_trace(redo, binlog)

    def test_lab_counterexamples(self):
        result = commit_recovery_lab()
        self.assertTrue(result["no_ACK_can_still_commit"])
        self.assertEqual(result["relaxed_both_after_ACK"], "ABSENT")
        self.assertEqual(result["relaxed_binlog_after_ACK"], "INCONSISTENT")


class CLITests(unittest.TestCase):
    def test_all_labs_json_and_stable_names(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(["--lab", "all"]), 0)
        result = json.loads(stream.getvalue())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(list(result["labs"]), ["index-lookup", "read-view", "deadlock", "commit-recovery"])

    def test_each_lab_selection(self):
        for name in LABS:
            stream = io.StringIO()
            with self.subTest(name=name), contextlib.redirect_stdout(stream):
                self.assertEqual(main(["--lab", name]), 0)
            self.assertEqual(list(json.loads(stream.getvalue())["labs"]), [name])

    def test_default_all(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            main([])
        self.assertEqual(len(json.loads(stream.getvalue())["labs"]), 4)

    def test_bad_selection_exits_two(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--lab", "mysql-server"])
        self.assertEqual(caught.exception.code, 2)

    def test_help_does_not_execute_labs(self):
        with patch.dict(LABS, {"index-lookup": lambda: self.fail("help executed a lab")}):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(["--help"])
        self.assertEqual(caught.exception.code, 0)

    def test_explicit_contract_checks_survive_optimized_python(self):
        with self.assertRaisesRegex(ValueError, "oracle"):
            require(False, "oracle")


if __name__ == "__main__":
    unittest.main()
