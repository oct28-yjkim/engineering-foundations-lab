"""Independent literal oracles for the synthetic models; no tool/cloud execution."""
from __future__ import annotations

from contextlib import redirect_stdout
import copy
from dataclasses import FrozenInstanceError
import io
import json
import unittest

from offline_lab import (
    LABS, LockToken, MemoryStateStore, StateSnapshot, evaluate_plan, main,
    normalize_graph, plan_scope, simulate_run, topological_layers,
)


def resource(address="demo.a", actions=None, after=None, unknown=None, sensitive=None):
    """Test fixture constructed independently, not with the production helper."""
    return {"address": address, "change": {
        "actions": ["create"] if actions is None else actions,
        "after": {"env": "lab", "region": "local"} if after is None else after,
        "after_unknown": {} if unknown is None else unknown,
        "after_sensitive": {} if sensitive is None else sensitive,
    }}


def envelope(*resources):
    return {"resource_changes": list(resources)}


class GraphTests(unittest.TestCase):
    def test_empty_graph(self):
        self.assertEqual(topological_layers({}), ())

    def test_diamond_layers(self):
        graph = {"d": ["b", "c"], "c": ["a"], "a": [], "b": ["a"]}
        self.assertEqual(topological_layers(graph), (("a",), ("b", "c"), ("d",)))

    def test_input_order_does_not_change_layers(self):
        self.assertEqual(topological_layers({"z": [], "b": [], "a": []}), (("a", "b", "z"),))

    def test_missing_dependency(self):
        with self.assertRaisesRegex(ValueError, "missing unit"):
            topological_layers({"a": ["absent"]})

    def test_self_cycle(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            topological_layers({"a": ["a"]})

    def test_long_cycle_with_independent_root(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            topological_layers({"a": ["c"], "b": ["a"], "c": ["b"], "ok": []})

    def test_reject_graph_as_list(self):
        with self.assertRaises(ValueError):
            topological_layers([])

    def test_reject_string_dependencies(self):
        with self.assertRaises(ValueError):
            topological_layers({"a": "a"})

    def test_reject_duplicate_dependencies(self):
        with self.assertRaisesRegex(ValueError, "duplicates"):
            topological_layers({"a": [], "b": ["a", "a"]})

    def test_reject_bad_unit_names(self):
        for name in ("", " a", 4, None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                topological_layers({name: []})

    def test_reject_bad_dependency_names(self):
        with self.assertRaises(ValueError):
            topological_layers({"a": [7]})

    def test_normalization_does_not_mutate_original(self):
        graph = {"a": [], "b": ["a"]}
        saved = copy.deepcopy(graph)
        normalized = normalize_graph(graph)
        graph["b"].clear()
        self.assertEqual(normalized, {"a": frozenset(), "b": frozenset({"a"})})
        self.assertEqual(saved, {"a": [], "b": ["a"]})

    def test_failure_blocks_transitive_descendants_only(self):
        graph = {"a": [], "b": ["a"], "c": ["b"], "x": [], "y": ["x"]}
        self.assertEqual(simulate_run(graph, ["a"]),
                         {"a": "FAILED", "x": "SUCCEEDED", "b": "BLOCKED", "y": "SUCCEEDED", "c": "BLOCKED"})

    def test_blocked_unit_does_not_execute_injected_failure(self):
        self.assertEqual(simulate_run({"a": [], "b": ["a"]}, ["a", "b"]),
                         {"a": "FAILED", "b": "BLOCKED"})

    def test_no_failures_all_succeed_and_preserve_graph(self):
        graph = {"a": [], "b": ["a"]}
        saved = copy.deepcopy(graph)
        self.assertEqual(simulate_run(graph), {"a": "SUCCEEDED", "b": "SUCCEEDED"})
        self.assertEqual(graph, saved)

    def test_unknown_failure_unit(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            simulate_run({"a": []}, ["not-a-unit"])

    def test_string_failure_collection_rejected(self):
        with self.assertRaises(ValueError):
            simulate_run({"a": []}, "a")


class PlanPolicyTests(unittest.TestCase):
    def test_empty_change_list_is_allowed_not_live_verification(self):
        decision = evaluate_plan(envelope())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reasons, ())

    def test_supported_non_destructive_actions(self):
        for action in ("no-op", "read", "create", "update"):
            with self.subTest(action=action):
                self.assertTrue(evaluate_plan(envelope(resource(actions=[action]))).allowed)

    def test_delete_and_both_replacements_are_detected(self):
        deletion = resource("demo.delete", ["delete"])
        deletion["change"]["after"] = None
        plan = envelope(resource("demo.before", ["delete", "create"]), deletion,
                        resource("demo.after", ["create", "delete"]))
        result = evaluate_plan(plan)
        self.assertFalse(result.allowed)
        self.assertEqual(result.destructive_addresses, ("demo.after", "demo.before", "demo.delete"))
        self.assertEqual(result.reasons, (
            "demo.after: delete/replacement denied", "demo.before: delete/replacement denied",
            "demo.delete: delete/replacement denied"))

    def test_unknown_identity_denied_even_with_plausible_value(self):
        result = evaluate_plan(envelope(resource(unknown={"region": True})))
        self.assertFalse(result.allowed)
        self.assertEqual(result.reasons, ("demo.a: region is unknown",))

    def test_unknown_entire_after_object_denies_both_identities(self):
        item = resource(unknown=True)
        item["change"]["after"] = None
        self.assertEqual(evaluate_plan(envelope(item)).reasons,
                         ("demo.a: env is unknown", "demo.a: region is unknown"))

    def test_missing_and_nonstring_identity_denied(self):
        self.assertEqual(evaluate_plan(envelope(resource(after={"env": 42}))).reasons,
                         ("demo.a: env is missing or not a string", "demo.a: region is missing or not a string"))

    def test_wrong_environment_or_region_denied(self):
        result = evaluate_plan(envelope(resource(after={"env": "production", "region": "elsewhere"})))
        self.assertEqual(result.reasons, ("demo.a: env is outside the permitted scope",
                                         "demo.a: region is outside the permitted scope"))

    def test_custom_allowlist(self):
        plan = envelope(resource(after={"env": "sandbox", "region": "region-b"}))
        self.assertTrue(evaluate_plan(plan, allowed_env="sandbox", allowed_regions=["region-a", "region-b"]).allowed)

    def test_empty_allowlist_or_string_rejected(self):
        for regions in ([], "local", [True]):
            with self.subTest(regions=regions), self.assertRaises(ValueError):
                evaluate_plan(envelope(), allowed_regions=regions)

    def test_sensitive_is_marker_not_encryption_or_approval_bypass(self):
        item = resource(after={"env": "production", "region": "local", "password": "demo-not-a-secret"},
                        sensitive={"password": True})
        decision = evaluate_plan(envelope(item))
        self.assertEqual(decision.sensitive_addresses, ("demo.a",))
        self.assertFalse(decision.allowed)
        self.assertEqual(item["change"]["after"]["password"], "demo-not-a-secret")

    def test_nested_sensitivity_is_reported(self):
        self.assertEqual(evaluate_plan(envelope(resource(sensitive={"nested": [{"token": True}]}))).sensitive_addresses,
                         ("demo.a",))

    def test_unknown_nonidentity_does_not_deny_this_narrow_policy(self):
        decision = evaluate_plan(envelope(resource(unknown={"generated_id": True})))
        self.assertTrue(decision.allowed)

    def test_boolean_false_markers(self):
        self.assertTrue(evaluate_plan(envelope(resource(unknown=False, sensitive=False))).allowed)

    def test_malformed_or_unknown_actions_rejected(self):
        for actions in ([], "create", [1], ["destroy"], ["forget"], ["update", "delete"],
                        ["create", "delete", "create"], ["create", "create"]):
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                evaluate_plan(envelope(resource(actions=actions)))

    def test_actual_full_plan_envelope_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "synthetic"):
            evaluate_plan({"format_version": "1.2", "resource_changes": []})

    def test_missing_envelope_or_nonlist_changes_rejected(self):
        for value in ({}, [], None, {"resource_changes": {}}, {"resource_changes": None}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluate_plan(value)

    def test_duplicate_addresses_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate_plan(envelope(resource(), resource()))

    def test_missing_unknown_or_sensitive_marker_rejected(self):
        for marker in ("after_unknown", "after_sensitive"):
            item = resource()
            del item["change"][marker]
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                evaluate_plan(envelope(item))

    def test_extra_resource_and_change_fields_rejected(self):
        for location in ("resource", "change"):
            item = resource()
            target = item if location == "resource" else item["change"]
            target["unsupported"] = True
            with self.subTest(location=location), self.assertRaises(ValueError):
                evaluate_plan(envelope(item))

    def test_bad_marker_types_rejected(self):
        for marker in (None, [], "true", 1, {"region": {"nested": True}}, {"x": "true"}, {1: True}):
            item = resource()
            item["change"]["after_unknown"] = marker
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                evaluate_plan(envelope(item))

    def test_non_json_after_and_nonfinite_values_rejected(self):
        for after in ([], "value", {"x": float("nan")}, {"x": float("inf")}, {"x": (1, 2)}, {1: "value"}):
            item = resource()
            item["change"]["after"] = after
            with self.subTest(after=after), self.assertRaises(ValueError):
                evaluate_plan(envelope(item))

    def test_delete_nonnull_after_rejected(self):
        with self.assertRaisesRegex(ValueError, "after=null"):
            evaluate_plan(envelope(resource(actions=["delete"])))

    def test_recursive_json_rejected_by_depth_bound(self):
        after = {"env": "lab", "region": "local"}
        after["cycle"] = after
        with self.assertRaisesRegex(ValueError, "depth"):
            evaluate_plan(envelope(resource(after=after)))

    def test_recursive_marker_rejected_by_depth_bound(self):
        marker = {}
        marker["cycle"] = marker
        with self.assertRaisesRegex(ValueError, "depth"):
            evaluate_plan(envelope(resource(unknown=marker)))

    def test_policy_does_not_mutate_input(self):
        plan = envelope(resource(sensitive={"nested": [{"password": True}]}))
        saved = copy.deepcopy(plan)
        evaluate_plan(plan)
        self.assertEqual(plan, saved)

    def test_reason_order_is_deterministic(self):
        items = [resource("z", unknown=True), resource("a", unknown=True)]
        self.assertEqual(evaluate_plan(envelope(*items)), evaluate_plan(envelope(*reversed(items))))


class StateCASTests(unittest.TestCase):
    def setUp(self):
        self.initial = StateSnapshot("lineage-a", 0, (("network", "before"),))
        self.store = MemoryStateStore({"state-a": self.initial, "state-b": StateSnapshot("lineage-b", 0)})

    def test_success_increments_exactly_one(self):
        token = self.store.acquire("state-a", "owner-a")
        new = StateSnapshot("lineage-a", 1, (("network", "after"),))
        self.assertEqual(self.store.compare_and_swap("state-a", self.initial, new, token), new)
        self.assertEqual(self.store.read("state-a"), new)
        self.store.release(token)

    def test_snapshot_and_nested_payload_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.initial.serial = 1
        with self.assertRaises(TypeError):
            self.initial.resources[0] = ("network", "after")

    def test_invalid_snapshot_serials(self):
        for serial in (-1, True, 0.5, "0"):
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                StateSnapshot("lineage", serial)

    def test_invalid_snapshot_lineage(self):
        for lineage in ("", " trailing ", None):
            with self.subTest(lineage=lineage), self.assertRaises(ValueError):
                StateSnapshot(lineage, 0)

    def test_mutable_or_malformed_resource_payload_rejected(self):
        for resources in ([('a', '1')], (["a", "1"],), (("a", 1),), (("a",),), (("", "x"),),
                          (("a", "1"), ("a", "2"))):
            with self.subTest(resources=resources), self.assertRaises(ValueError):
                StateSnapshot("lineage", 0, resources)

    def test_store_copies_initial_mapping(self):
        mapping = {"a": self.initial}
        store = MemoryStateStore(mapping)
        mapping["a"] = StateSnapshot("other", 5)
        self.assertEqual(store.read("a"), self.initial)

    def test_unknown_state_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown state"):
            self.store.read("missing")

    def test_competing_owner_and_reentrant_lock_rejected(self):
        self.store.acquire("state-a", "owner-a")
        for owner in ("owner-a", "owner-b"):
            with self.subTest(owner=owner), self.assertRaisesRegex(ValueError, "already locked"):
                self.store.acquire("state-a", owner)

    def test_wrong_owner_cannot_release(self):
        token = self.store.acquire("state-a", "owner-a")
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.store.release(LockToken("state-a", "owner-b", token.generation))
        self.store.release(token)

    def test_old_lock_generation_cannot_release_new_lock(self):
        old = self.store.acquire("state-a", "same-owner")
        self.store.release(old)
        current = self.store.acquire("state-a", "same-owner")
        self.assertEqual((old.generation, current.generation), (1, 2))
        with self.assertRaisesRegex(ValueError, "generation"):
            self.store.release(old)
        self.store.release(current)

    def test_release_twice_rejected(self):
        token = self.store.acquire("state-a", "owner-a")
        self.store.release(token)
        with self.assertRaises(ValueError):
            self.store.release(token)

    def test_token_for_another_state_cannot_write(self):
        token = self.store.acquire("state-b", "owner-a")
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.store.compare_and_swap("state-a", self.initial, StateSnapshot("lineage-a", 1), token)
        self.assertEqual(self.store.read("state-a"), self.initial)

    def test_released_token_cannot_write(self):
        token = self.store.acquire("state-a", "owner-a")
        self.store.release(token)
        with self.assertRaises(ValueError):
            self.store.compare_and_swap("state-a", self.initial, StateSnapshot("lineage-a", 1), token)

    def test_stale_snapshot_rejected_without_mutation(self):
        token = self.store.acquire("state-a", "owner-a")
        new = StateSnapshot("lineage-a", 1, (("network", "after"),))
        self.store.compare_and_swap("state-a", self.initial, new, token)
        with self.assertRaisesRegex(ValueError, "stale"):
            self.store.compare_and_swap("state-a", self.initial, StateSnapshot("lineage-a", 2), token)
        self.assertEqual(self.store.read("state-a"), new)

    def test_wrong_expected_lineage_rejected(self):
        token = self.store.acquire("state-a", "owner-a")
        with self.assertRaisesRegex(ValueError, "expected lineage"):
            self.store.compare_and_swap("state-a", StateSnapshot("other", 0), StateSnapshot("lineage-a", 1), token)
        self.assertEqual(self.store.read("state-a"), self.initial)

    def test_replacement_lineage_change_rejected(self):
        token = self.store.acquire("state-a", "owner-a")
        with self.assertRaisesRegex(ValueError, "change lineage"):
            self.store.compare_and_swap("state-a", self.initial, StateSnapshot("other", 1), token)

    def test_serial_skips_and_rewinds_rejected(self):
        token = self.store.acquire("state-a", "owner-a")
        for serial in (0, 2, 100):
            with self.subTest(serial=serial), self.assertRaisesRegex(ValueError, "increment"):
                self.store.compare_and_swap("state-a", self.initial, StateSnapshot("lineage-a", serial), token)
        self.assertEqual(self.store.read("state-a"), self.initial)

    def test_cas_identity_is_lineage_serial_not_payload_comparison(self):
        token = self.store.acquire("state-a", "owner-a")
        expected_with_other_payload = StateSnapshot("lineage-a", 0)
        self.store.compare_and_swap("state-a", expected_with_other_payload, StateSnapshot("lineage-a", 1), token)
        self.assertEqual(self.store.read("state-a").serial, 1)

    def test_independent_state_locks_can_coexist(self):
        first = self.store.acquire("state-a", "owner-a")
        second = self.store.acquire("state-b", "owner-b")
        self.store.release(first)
        self.store.release(second)

    def test_partial_multi_state_apply_does_not_roll_back_first_state(self):
        first = self.store.acquire("state-a", "owner-a")
        self.store.compare_and_swap("state-a", self.initial, StateSnapshot("lineage-a", 1), first)
        self.store.release(first)
        second = self.store.acquire("state-b", "owner-a")
        with self.assertRaises(ValueError):
            self.store.compare_and_swap("state-b", self.store.read("state-b"), StateSnapshot("lineage-b", 3), second)
        self.store.release(second)
        self.assertEqual((self.store.read("state-a").serial, self.store.read("state-b").serial), (1, 0))
        self.assertEqual(self.initial, StateSnapshot("lineage-a", 0, (("network", "before"),)))

    def test_same_lineage_serial_does_not_conflate_distinct_state_ids(self):
        store = MemoryStateStore({"a": self.initial, "b": self.initial})
        token = store.acquire("a", "runner")
        store.compare_and_swap("a", self.initial, StateSnapshot("lineage-a", 1), token)
        self.assertEqual((store.read("a").serial, store.read("b").serial), (1, 0))

    def test_invalid_store_or_owner_or_token_rejected(self):
        with self.assertRaises(ValueError):
            MemoryStateStore({"a": {"serial": 0}})
        with self.assertRaises(ValueError):
            self.store.acquire("state-a", "")
        with self.assertRaises(ValueError):
            self.store.release("not-a-token")

    def test_malformed_lock_token_fields_rejected(self):
        for fields in (([], "owner", 1), ("state", "", 1), ("state", "owner", True),
                       ("state", "owner", 0), ("state", "owner", -1), ("state", "owner", 1.0)):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                LockToken(*fields)


class BlastRadiusTests(unittest.TestCase):
    def setUp(self):
        self.graph = {"network": [], "identity": [], "database": ["network"],
                      "api": ["database", "identity"], "worker": ["database"], "docs": []}

    def test_changed_only_misses_dependents(self):
        scope = plan_scope(self.graph, ["database"], external_decision="include")
        self.assertEqual(scope.changed, frozenset({"database"}))
        self.assertEqual(scope.affected, frozenset({"database", "api", "worker"}))

    def test_unchanged_ancestors_enter_execution_closure(self):
        scope = plan_scope(self.graph, ["database"], external_decision="include")
        self.assertEqual(scope.external_dependencies, frozenset({"network", "identity"}))
        self.assertEqual(scope.dependency_closure, frozenset({"network", "identity", "database", "api", "worker"}))
        self.assertEqual(scope.selected_for_execution, scope.dependency_closure)
        self.assertEqual(scope.assumed_ready, frozenset())

    def test_external_dependencies_require_explicit_decision(self):
        with self.assertRaisesRegex(ValueError, "explicit decision"):
            plan_scope(self.graph, ["database"])

    def test_assume_ready_records_omitted_dependencies(self):
        scope = plan_scope(self.graph, ["database"], external_decision="assume-ready")
        self.assertEqual(scope.selected_for_execution, frozenset({"database", "api", "worker"}))
        self.assertEqual(scope.assumed_ready, frozenset({"network", "identity"}))
        self.assertEqual(scope.dependency_closure, frozenset({"network", "identity", "database", "api", "worker"}))

    def test_independent_change_needs_no_external_decision(self):
        scope = plan_scope(self.graph, ["docs"])
        self.assertEqual(scope.affected, frozenset({"docs"}))
        self.assertEqual(scope.selected_for_execution, frozenset({"docs"}))

    def test_empty_selection(self):
        scope = plan_scope(self.graph, [])
        self.assertEqual(scope.affected, frozenset())
        self.assertEqual(scope.dependency_closure, frozenset())

    def test_multiple_changed_roots(self):
        scope = plan_scope(self.graph, ["network", "identity"])
        self.assertEqual(scope.affected, frozenset({"network", "identity", "database", "api", "worker"}))
        self.assertEqual(scope.external_dependencies, frozenset())

    def test_unknown_changed_unit(self):
        with self.assertRaisesRegex(ValueError, "unknown changed"):
            plan_scope(self.graph, ["typo"])

    def test_invalid_external_decision(self):
        with self.assertRaises(ValueError):
            plan_scope(self.graph, [], external_decision="silently-ignore")

    def test_cycles_rejected_even_with_empty_selection(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            plan_scope({"a": ["b"], "b": ["a"]}, [])

    def test_scope_does_not_mutate_graph_or_changed_input(self):
        saved = copy.deepcopy(self.graph)
        changed = ["database"]
        plan_scope(self.graph, changed, external_decision="include")
        self.assertEqual(self.graph, saved)
        self.assertEqual(changed, ["database"])

    def test_unchanged_ancestor_other_consumers_are_not_automatically_affected(self):
        # The ancestor is selected as a prerequisite, not asserted to have changed.
        graph = {"root": [], "a": ["root"], "b": ["root"]}
        scope = plan_scope(graph, ["a"], external_decision="include")
        self.assertEqual(scope.affected, frozenset({"a"}))
        self.assertEqual(scope.selected_for_execution, frozenset({"root", "a"}))


class LabContractTests(unittest.TestCase):
    def test_all_four_literal_oracles_pass(self):
        self.assertEqual(set(LABS), {"graph", "plan-policy", "state-cas", "blast-radius"})
        for name, lab in LABS.items():
            with self.subTest(lab=name):
                self.assertEqual(lab()["status"], "PASS")

    def test_repeat_execution_is_deterministic(self):
        for name, lab in LABS.items():
            with self.subTest(lab=name):
                self.assertEqual(lab(), lab())

    def test_cli_all_outputs_four_json_lines(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--lab", "all"]), 0)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([row["lab"] for row in rows], ["graph", "plan-policy", "state-cas", "blast-radius"])
        self.assertEqual([row["status"] for row in rows], ["PASS"] * 4)

    def test_cli_single_lab(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--lab", "state-cas"]), 0)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(json.loads(output.getvalue())["state_serials"], {"network": 1, "database": 0})


if __name__ == "__main__":
    unittest.main()
