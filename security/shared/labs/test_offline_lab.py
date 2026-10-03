"""Independent literal oracles for bounded models; no engines or credentials."""
import contextlib
from dataclasses import FrozenInstanceError
import io
import itertools
import json
import unittest
from unittest.mock import patch

from offline_lab import (LABS, MAX_NUMBER, ACLDecision, CASMismatch, KVState,
                         KVVersion, Lease, Member, PolicyRule, advance_lease,
                         attempt_revocation, authorize, backend_credential_usable,
                         change_versions, exact_acl_lab, issue_lease, kv_cas_lab,
                         kv_read, kv_write, lease_clock_lab, lease_usable, main,
                         partition_quorums, quorum, raft_quorum_lab, renew_lease,
                         require, revoke_lease)


class ExactACLTests(unittest.TestCase):
    def setUp(self):
        self.read = PolicyRule("secret/data/app", frozenset({"read"}))

    def test_empty_policy_denies(self):
        self.assertEqual(authorize((), "secret/data/app", "read"),
                         ACLDecision(False, 0, (), "default-deny"))

    def test_exact_read_is_granted(self):
        self.assertEqual(authorize([self.read], "secret/data/app", "read"),
                         ACLDecision(True, 1, ("read",), "granted"))

    def test_different_capability_is_denied(self):
        self.assertFalse(authorize([self.read], "secret/data/app", "update").allowed)

    def test_exact_path_is_not_prefix(self):
        for path in ("secret/data/apps", "secret/data/app/child", "secret/data/app/"):
            with self.subTest(path=path):
                self.assertEqual(authorize([self.read], path, "read").matched_rules, 0)

    def test_case_is_not_normalized(self):
        self.assertFalse(authorize([self.read], "secret/data/App", "read").allowed)

    def test_same_path_capabilities_union(self):
        update = PolicyRule("secret/data/app", frozenset({"update", "create"}))
        result = authorize([self.read, update], "secret/data/app", "create")
        self.assertEqual((result.allowed, result.matched_rules, result.effective_capabilities),
                         (True, 2, ("create", "read", "update")))

    def test_deny_wins_at_identical_path(self):
        deny = PolicyRule("secret/data/app", frozenset({"deny", "update"}))
        self.assertEqual(authorize([self.read, deny], "secret/data/app", "read"),
                         ACLDecision(False, 2, ("deny",), "explicit-deny"))

    def test_unrelated_deny_does_not_spread(self):
        deny = PolicyRule("secret/data/other", frozenset({"deny"}))
        self.assertTrue(authorize([self.read, deny], "secret/data/app", "read").allowed)

    def test_rule_order_does_not_change_decision(self):
        rules = (self.read, PolicyRule("secret/data/app", frozenset({"update"})),
                 PolicyRule("secret/data/app", frozenset({"deny"})))
        for permutation in itertools.permutations(rules):
            self.assertEqual(authorize(permutation, "secret/data/app", "update").reason, "explicit-deny")

    def test_data_and_metadata_capabilities_are_distinct(self):
        self.assertFalse(authorize([self.read], "secret/metadata/app", "read").allowed)
        self.assertFalse(authorize([self.read], "secret/metadata/", "list").allowed)

    def test_list_uses_explicit_canonical_prefix_path(self):
        rule = PolicyRule("secret/metadata/apps/", frozenset({"list"}))
        self.assertTrue(authorize([rule], "secret/metadata/apps/", "list").allowed)
        self.assertFalse(authorize([rule], "secret/metadata/apps", "list").allowed)
        self.assertFalse(authorize([rule], "secret/metadata/apps/payments", "read").allowed)

    def test_unsupported_paths_rejected_not_approximated(self):
        for path in ("", "/secret/x", "secret//x", "secret/../x", "secret/./x", "secret/*",
                     "secret/+", "secret/{{id}}", "secret/%2f", "secret/x?query=1", "secret/한글",
                     "secret/x\n", None, 1, True):
            with self.subTest(path=path), self.assertRaises(ValueError):
                PolicyRule(path, frozenset({"read"}))

    def test_invalid_capabilities_rejected(self):
        for caps in (set(), {"read"}, [], (), frozenset(), frozenset({"sudo"}),
                     frozenset({True}), frozenset({"read", "unknown"}), None):
            with self.subTest(caps=caps), self.assertRaises(ValueError):
                PolicyRule("secret/data/app", caps)

    def test_invalid_requests_and_rules_rejected(self):
        for operation in ("deny", "sudo", "GET", "", None, True, []):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                authorize([self.read], "secret/data/app", operation)
        for rules in (None, "rule", [None], {self.read}):
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                authorize(rules, "secret/data/app", "read")

    def test_inputs_unchanged_and_results_frozen(self):
        rules = [self.read]
        result = authorize(rules, "secret/data/app", "read")
        self.assertEqual(rules, [PolicyRule("secret/data/app", frozenset({"read"}))])
        with self.assertRaises(FrozenInstanceError):
            self.read.path = "changed"
        with self.assertRaises(FrozenInstanceError):
            result.allowed = False

    def test_lab_literal_decisions(self):
        result = exact_acl_lab()
        self.assertEqual(result["allowed_in_request_order"], [True, True, False, True, False, False, False])
        self.assertEqual(result["admin_reason"], "explicit-deny")


class KVCasTests(unittest.TestCase):
    def setUp(self):
        self.empty = KVState()
        self.first = kv_write(self.empty, "one", 0)
        self.second = kv_write(self.first, "two", 1)

    def test_empty_state_and_create(self):
        self.assertEqual((self.empty.current_version, kv_read(self.empty)), (0, None))
        self.assertEqual(self.first.versions, (KVVersion(1, "one"),))

    def test_cas_zero_rejects_existing_metadata(self):
        with self.assertRaises(CASMismatch):
            kv_write(self.first, "overwrite", 0)

    def test_positive_cas_rejects_absent_key(self):
        with self.assertRaises(CASMismatch):
            kv_write(self.empty, "one", 1)

    def test_current_cas_appends_and_preserves_history(self):
        self.assertEqual(self.second.versions, (KVVersion(1, "one"), KVVersion(2, "two")))
        self.assertEqual(kv_read(self.second, 1), "one")
        self.assertEqual(kv_read(self.second), "two")

    def test_two_writers_same_cas_only_first_can_follow_current_state(self):
        written = kv_write(self.second, "writer-a", 2)
        with self.assertRaises(CASMismatch):
            kv_write(written, "writer-b", 2)
        self.assertEqual((written.current_version, kv_read(written)), (3, "writer-a"))

    def test_soft_delete_hides_but_keeps_value(self):
        deleted = change_versions(self.second, [2], "delete")
        self.assertIsNone(kv_read(deleted))
        self.assertEqual(deleted.versions[1], KVVersion(2, "two", deleted=True))
        self.assertEqual(kv_read(deleted, 1), "one")

    def test_undelete_restores_soft_deleted_version(self):
        deleted = change_versions(self.second, (2,), "delete")
        self.assertEqual(change_versions(deleted, (2,), "undelete"), self.second)

    def test_destroy_removes_payload_only_from_new_model_state(self):
        destroyed = change_versions(self.second, (1,), "destroy")
        self.assertEqual(destroyed.versions, (KVVersion(1, None, destroyed=True), KVVersion(2, "two")))
        self.assertIsNone(kv_read(destroyed, 1))
        self.assertEqual(kv_read(self.second, 1), "one")  # No real memory-erasure claim.

    def test_destroyed_version_cannot_be_undeleted(self):
        destroyed = change_versions(self.second, (1,), "destroy")
        with self.assertRaisesRegex(ValueError, "cannot be undeleted"):
            change_versions(destroyed, (1,), "undelete")

    def test_delete_and_destroy_keep_current_metadata_for_cas(self):
        for operation in ("delete", "destroy"):
            state = change_versions(self.second, (1, 2), operation)
            with self.subTest(operation=operation):
                self.assertEqual(state.current_version, 2)
                with self.assertRaises(CASMismatch):
                    kv_write(state, "new", 0)
                self.assertEqual(kv_write(state, "new", 2).versions[-1], KVVersion(3, "new"))

    def test_delete_and_destroy_are_idempotent(self):
        for operation in ("delete", "destroy"):
            once = change_versions(self.second, (1,), operation)
            self.assertEqual(change_versions(once, (1,), operation), once)
        destroyed = change_versions(self.second, (1,), "destroy")
        self.assertEqual(change_versions(destroyed, (1,), "delete"), destroyed)

    def test_undelete_live_is_idempotent_and_selection_order_irrelevant(self):
        self.assertEqual(change_versions(self.second, (2, 1), "undelete"), self.second)
        self.assertEqual(change_versions(self.second, (1, 2), "delete"),
                         change_versions(self.second, (2, 1), "delete"))

    def test_missing_version_and_empty_payload_are_distinct(self):
        state = kv_write(self.empty, "", 0)
        self.assertEqual(kv_read(state), "")
        self.assertIsNone(kv_read(state, 2))

    def test_inputs_and_old_states_are_immutable(self):
        selected = [1]
        changed = change_versions(self.second, selected, "delete")
        self.assertEqual(selected, [1])
        self.assertEqual(self.second, KVState((KVVersion(1, "one"), KVVersion(2, "two"))))
        self.assertNotEqual(changed, self.second)
        with self.assertRaises(FrozenInstanceError):
            self.first.versions = ()
        with self.assertRaises(FrozenInstanceError):
            self.first.versions[0].value = "other"

    def test_invalid_history_is_rejected(self):
        for versions in ([], [KVVersion(1, "x")], (None,), (KVVersion(2, "x"),),
                         (KVVersion(1, "x"), KVVersion(1, "y")), "", None):
            with self.subTest(versions=versions), self.assertRaises(ValueError):
                KVState(versions)

    def test_invalid_version_payload_and_flags_rejected(self):
        for args in ((0, "x"), (True, "x"), (1.0, "x"), (1, None), (1, "x", 1),
                     (1, "x", False, 1), (1, "x", False, True), (1, None, True, True)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                KVVersion(*args)

    def test_invalid_cas_and_payload_rejected(self):
        for cas in (True, -1, 1.0, None, float("nan"), MAX_NUMBER + 1):
            with self.subTest(cas=cas), self.assertRaises(ValueError):
                kv_write(self.first, "two", cas)
        for value in (None, True, 1, {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                kv_write(self.first, value, 1)

    def test_invalid_selections_reads_and_operations_rejected(self):
        for selection in ((), None, "1", (0,), (True,), (1.0,), (3,), (1, 1)):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                change_versions(self.second, selection, "delete")
        for version in (0, True, -1, 1.0, MAX_NUMBER + 1):
            with self.subTest(version=version), self.assertRaises(ValueError):
                kv_read(self.second, version)
        for operation in ("erase", None, []):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                change_versions(self.second, (1,), operation)

    def test_invalid_state_rejected_by_operations(self):
        for operation in (lambda: kv_write(None, "x", 0), lambda: kv_read(None),
                          lambda: change_versions(None, (1,), "delete")):
            with self.assertRaises(ValueError):
                operation()

    def test_lab_literal_version_trace(self):
        result = kv_cas_lab()
        self.assertEqual(result["current_versions"], [1, 2, 2, 2, 2, 3])
        self.assertTrue(result["stale_cas_rejected"])
        self.assertIsNone(result["latest_after_soft_delete"])
        self.assertEqual(result["latest_after_undelete"], "public-v2")
        self.assertIsNone(result["version_1_after_destroy"])
        self.assertEqual(result["latest_after_next_cas"], "public-v3")


class LeaseClockTests(unittest.TestCase):
    def setUp(self):
        self.lease = issue_lease(100, 10, 25)

    def test_issuance_has_literal_fixed_deadlines(self):
        self.assertEqual(self.lease, Lease(100, 100, 110, 125))
        self.assertTrue(lease_usable(self.lease))
        self.assertTrue(backend_credential_usable(self.lease))

    def test_one_tick_before_expiry_is_active(self):
        state = advance_lease(self.lease, 109)
        self.assertEqual((state.revocation, lease_usable(state)), ("active", True))

    def test_exact_expiry_queues_revocation_without_backend_completion(self):
        state = advance_lease(self.lease, 110)
        self.assertEqual((state.revocation, state.attempts), ("pending", 0))
        self.assertFalse(lease_usable(state))
        self.assertTrue(backend_credential_usable(state))

    def test_clock_can_jump_beyond_expiry(self):
        state = advance_lease(self.lease, 1000)
        self.assertEqual((state.now, state.expires_at, state.revocation), (1000, 110, "pending"))

    def test_renewal_increment_counts_from_now_not_old_expiry(self):
        state = renew_lease(advance_lease(self.lease, 106), 10)
        self.assertEqual((state.issued_at, state.expires_at, state.max_expires_at), (100, 116, 125))

    def test_renewal_clamped_to_issuance_maximum(self):
        state = renew_lease(advance_lease(self.lease, 109), 100)
        self.assertEqual(state.expires_at, 125)
        state = renew_lease(advance_lease(state, 124), MAX_NUMBER)
        self.assertEqual(state.expires_at, 125)

    def test_shorter_requested_increment_can_shorten_model_lease(self):
        state = renew_lease(advance_lease(self.lease, 102), 1)
        self.assertEqual(state.expires_at, 103)

    def test_renewal_at_expiry_is_rejected(self):
        with self.assertRaises(ValueError):
            renew_lease(advance_lease(self.lease, 110), 5)

    def test_nonrenewable_lease_remains_usable_until_expiry(self):
        state = issue_lease(0, 5, 10, renewable=False)
        self.assertTrue(lease_usable(state))
        with self.assertRaises(ValueError):
            renew_lease(state, 1)
        self.assertFalse(lease_usable(advance_lease(state, 5)))

    def test_manual_revocation_can_precede_expiry(self):
        pending = revoke_lease(advance_lease(self.lease, 101))
        self.assertEqual((pending.now, pending.expires_at, pending.revocation), (101, 110, "pending"))
        self.assertFalse(lease_usable(pending))
        self.assertTrue(backend_credential_usable(pending))
        with self.assertRaises(ValueError):
            renew_lease(pending, 10)

    def test_failed_revocation_retains_counterexample_backend_access(self):
        state = attempt_revocation(revoke_lease(self.lease), False)
        self.assertEqual((state.revocation, state.attempts), ("pending", 1))
        self.assertEqual((lease_usable(state), backend_credential_usable(state)), (False, True))

    def test_retry_success_records_backend_revocation(self):
        state = revoke_lease(self.lease)
        for success in (False, False, True):
            state = attempt_revocation(state, success)
        self.assertEqual((state.revocation, state.attempts), ("complete", 3))
        self.assertEqual((lease_usable(state), backend_credential_usable(state)), (False, False))

    def test_revoke_is_idempotent_for_pending_and_complete(self):
        pending = revoke_lease(self.lease)
        complete = attempt_revocation(pending, True)
        self.assertEqual(revoke_lease(pending), pending)
        self.assertEqual(revoke_lease(complete), complete)
        self.assertEqual(advance_lease(complete, 200).revocation, "complete")

    def test_retry_requires_pending_and_boolean_outcome(self):
        pending = revoke_lease(self.lease)
        complete = attempt_revocation(pending, True)
        for state in (self.lease, complete):
            with self.assertRaises(ValueError):
                attempt_revocation(state, True)
        for success in (1, 0, None, "true", []):
            with self.subTest(success=success), self.assertRaises(ValueError):
                attempt_revocation(pending, success)

    def test_clock_must_be_monotonic_integer(self):
        for now in (99, True, 101.0, -1, None, float("nan"), MAX_NUMBER + 1):
            with self.subTest(now=now), self.assertRaises(ValueError):
                advance_lease(self.lease, now)
        self.assertEqual(advance_lease(self.lease, 100), self.lease)

    def test_invalid_issuance_and_increment_rejected(self):
        for args in ((True, 1, 2), (0, 0, 1), (0, 1, 0), (0, 3, 2), (0, 1.0, 2),
                     (0, 1, True), (-1, 1, 2), (MAX_NUMBER, 1, 1), (0, 1, 2, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                issue_lease(*args)
        for increment in (0, -1, True, 1.0, float("inf"), MAX_NUMBER + 1):
            with self.subTest(increment=increment), self.assertRaises(ValueError):
                renew_lease(self.lease, increment)

    def test_inconsistent_manual_states_rejected(self):
        for args in ((10, 9, 15, 20), (10, 10, 10, 20), (10, 10, 30, 20),
                     (10, 15, 15, 20), (10, 10, 15, 20, True, "unknown"),
                     (10, 10, 15, 20, True, "active", 1),
                     (10, 10, 15, 20, True, "complete", 0),
                     (10, 10, 15, 20, True, "pending", True)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Lease(*args)

    def test_invalid_state_inputs_rejected(self):
        for operation in (lambda: advance_lease(None, 1), lambda: renew_lease(None, 1),
                          lambda: revoke_lease(None), lambda: attempt_revocation(None, False),
                          lambda: lease_usable(None), lambda: backend_credential_usable(None)):
            with self.assertRaises(ValueError):
                operation()

    def test_immutable_input_and_upper_clock_boundary(self):
        state = issue_lease(MAX_NUMBER - 1, 1, 1)
        expired = advance_lease(state, MAX_NUMBER)
        self.assertFalse(lease_usable(expired))
        self.assertTrue(lease_usable(state))
        with self.assertRaises(FrozenInstanceError):
            state.now = 0
        self.assertEqual(self.lease, Lease(100, 100, 110, 125))

    def test_lab_literal_expiry_and_revocation_trace(self):
        result = lease_clock_lab()
        self.assertEqual(result["expiry_times"], [10, 16, 25])
        self.assertEqual(result["at_expiry_lease_and_backend_usable"], [False, True])
        self.assertEqual(result["after_failed_revoke_lease_and_backend_usable"], [False, True])
        self.assertEqual(result["after_successful_revoke_lease_and_backend_usable"], [False, False])
        self.assertEqual(result["revocation_attempts"], 2)


class QuorumTests(unittest.TestCase):
    def setUp(self):
        self.three = tuple(Member(node) for node in ("a", "b", "c"))
        self.five = self.three + (Member("d"), Member("e"))

    def test_three_voters_need_two(self):
        result = quorum(self.three, frozenset({"a", "b"}))
        self.assertEqual((result.voters, result.reachable_voters, result.required_votes,
                          result.has_voting_majority, result.maximum_unavailable_voters), (3, 2, 2, True, 1))

    def test_five_voters_need_three(self):
        result = quorum(self.five, frozenset({"a", "b", "c"}))
        self.assertEqual((result.voters, result.reachable_voters, result.required_votes,
                          result.has_voting_majority, result.maximum_unavailable_voters), (5, 3, 3, True, 2))

    def test_minority_has_no_majority(self):
        self.assertFalse(quorum(self.three, frozenset({"a"})).has_voting_majority)
        self.assertFalse(quorum(self.five, frozenset({"a", "b"})).has_voting_majority)

    def test_zero_reachable_voters_has_no_majority(self):
        self.assertEqual(quorum(self.three, frozenset()).reachable_voters, 0)
        self.assertFalse(quorum(self.three, frozenset()).has_voting_majority)

    def test_single_voter_requires_itself_and_has_no_fault_budget(self):
        result = quorum((Member("a"),), frozenset({"a"}))
        self.assertEqual((result.required_votes, result.has_voting_majority,
                          result.maximum_unavailable_voters), (1, True, 0))

    def test_even_membership_does_not_gain_same_failure_budget_as_next_odd(self):
        four = self.three + (Member("d"),)
        result = quorum(four, frozenset({"a", "b"}))
        self.assertEqual((result.required_votes, result.maximum_unavailable_voters,
                          result.has_voting_majority), (3, 1, False))

    def test_nonvoter_does_not_supply_a_vote(self):
        members = self.three + (Member("learner", False),)
        result = quorum(members, frozenset({"a", "learner"}))
        self.assertEqual((result.voters, result.reachable_voters, result.required_votes,
                          result.has_voting_majority), (3, 1, 2, False))

    def test_many_nonvoters_do_not_change_required_majority(self):
        members = self.three + tuple(Member(f"observer-{number}", False) for number in range(10))
        reachable = frozenset(member.node_id for member in members if member.node_id != "c")
        result = quorum(members, reachable)
        self.assertEqual((result.voters, result.reachable_voters, result.required_votes), (3, 2, 2))

    def test_three_and_five_partition_literal_results(self):
        three = partition_quorums(self.three, (frozenset({"a", "b"}), frozenset({"c"})))
        five = partition_quorums(self.five, (frozenset({"a", "b", "c"}), frozenset({"d", "e"})))
        self.assertEqual(tuple(item.has_voting_majority for item in three), (True, False))
        self.assertEqual(tuple(item.has_voting_majority for item in five), (True, False))

    def test_two_two_split_has_no_majority(self):
        result = partition_quorums(self.three + (Member("d"),),
                                  (frozenset({"a", "b"}), frozenset({"c", "d"})))
        self.assertEqual(tuple(item.has_voting_majority for item in result), (False, False))

    def test_disjoint_majorities_impossible_for_all_three_and_five_bipartitions(self):
        for members in (self.three, self.five):
            all_ids = frozenset(member.node_id for member in members)
            for size in range(1, len(members)):
                for selection in itertools.combinations(sorted(all_ids), size):
                    left = frozenset(selection)
                    result = partition_quorums(members, (left, all_ids - left))
                    self.assertEqual(sum(item.has_voting_majority for item in result), 1)

    def test_invalid_memberships_rejected(self):
        for members in ((), None, "a", (None,), (Member("a"), Member("a")), (Member("a", False),)):
            with self.subTest(members=members), self.assertRaises(ValueError):
                quorum(members, frozenset())
        for args in (("",), ("A",), ("a/b",), (True,), ("a", 1), ("한글",)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Member(*args)

    def test_invalid_reachable_members_rejected(self):
        for reachable in ({"a"}, ["a"], "a", None, frozenset({"unknown"}), frozenset({True})):
            with self.subTest(reachable=reachable), self.assertRaises(ValueError):
                quorum(self.three, reachable)

    def test_invalid_partitions_rejected(self):
        for components in (None, (), (frozenset(),), (frozenset({"a", "b"}),),
                           (frozenset({"a", "b"}), frozenset({"b", "c"})),
                           (frozenset({"a", "b", "c", "d"}),), ({"a", "b", "c"},)):
            with self.subTest(components=components), self.assertRaises(ValueError):
                partition_quorums(self.three, components)

    def test_order_immutability_and_frozen_results(self):
        members = list(self.three)
        result = quorum(members, frozenset({"b", "a"}))
        self.assertEqual(result, quorum(tuple(reversed(members)), frozenset({"a", "b"})))
        self.assertEqual(members, [Member("a"), Member("b"), Member("c")])
        with self.assertRaises(FrozenInstanceError):
            result.required_votes = 1
        with self.assertRaises(FrozenInstanceError):
            members[0].voting = False

    def test_lab_literal_quorum_report(self):
        result = raft_quorum_lab()
        self.assertEqual(result["required_votes_for_3_and_5"], [2, 3])
        self.assertEqual(result["maximum_unavailable_voters_for_3_and_5"], [1, 2])
        self.assertEqual(result["split_2_1_majorities"], [True, False])
        self.assertEqual(result["split_3_2_majorities"], [True, False])
        self.assertFalse(result["one_voter_plus_nonvoter_has_majority"])


class CLITests(unittest.TestCase):
    def capture(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(argv)
        return result, output.getvalue()

    def test_list_exact_names(self):
        result, output = self.capture(["--list"])
        self.assertEqual(result, 0)
        self.assertEqual(output, "exact-acl\nkv-cas\nlease-clock\nraft-quorum\n")

    def test_all_has_four_successful_reports(self):
        result, output = self.capture(["--lab", "all"])
        reports = json.loads(output)
        self.assertEqual(result, 0)
        self.assertEqual([report["lab"] for report in reports],
                         ["exact-acl", "kv-cas", "lease-clock", "raft-quorum"])
        self.assertEqual([report["status"] for report in reports], ["PASS"] * 4)

    def test_individual_reports_are_single_element_lists(self):
        for name in LABS:
            with self.subTest(name=name):
                result, output = self.capture(["--lab", name])
                reports = json.loads(output)
                self.assertEqual(result, 0)
                self.assertEqual(len(reports), 1)
                self.assertEqual((reports[0]["lab"], reports[0]["status"]), (name, "PASS"))

    def test_no_argument_shows_help_without_running_models(self):
        with patch.dict(LABS, {"exact-acl": lambda: self.fail("must not run")}, clear=True):
            result, output = self.capture([])
        self.assertEqual(result, 0)
        self.assertIn("usage:", output)
        self.assertNotIn('"status"', output)

    def test_invalid_cli_and_conflicting_flags_fail(self):
        for argv in (["--lab", "unknown"], ["--list", "--lab", "all"], ["--lab"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(argv)
            self.assertEqual(error.exception.code, 2)

    def test_help_exits_successfully(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["--help"])
        self.assertEqual(error.exception.code, 0)

    def test_output_is_deterministic(self):
        self.assertEqual(self.capture(["--lab", "all"]), self.capture(["--lab", "all"]))

    def test_require_is_not_an_optimizable_assert(self):
        with self.assertRaisesRegex(ValueError, "oracle failed"):
            require(False, "oracle failed")
        require(True, "valid")


if __name__ == "__main__":
    unittest.main()
