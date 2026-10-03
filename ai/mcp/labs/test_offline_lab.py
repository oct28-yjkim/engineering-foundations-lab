"""Literal-oracle tests for deliberately bounded MCP CPU models."""

import contextlib
import copy
from dataclasses import FrozenInstanceError, replace
import io
import json
import unittest

import offline_lab as lab


class RevisionTests(unittest.TestCase):
    def assert_code(self, code, message, required=()):
        with self.assertRaises(lab.ProtocolFailure) as caught:
            lab.modern_gate(message, required)
        self.assertEqual(caught.exception.code, code)

    def test_modern_direct_first_request(self):
        self.assertEqual(lab.modern_gate(lab.modern_request()), {
            "id": 1, "method": "tools/list", "revision": "2026-07-28", "prior_session_required": False})

    def test_requests_do_not_remember_capabilities(self):
        request = lab.modern_request()
        request["params"]["_meta"][lab.CAPABILITIES_KEY] = {"elicitation": {}}
        lab.modern_gate(request, ("elicitation",))
        self.assert_code(-32021, lab.modern_request(2), ("elicitation",))

    def test_missing_capability_error_uses_capabilities_object(self):
        with self.assertRaises(lab.ProtocolFailure) as caught:
            lab.modern_gate(lab.modern_request(), ("elicitation",))
        self.assertEqual(caught.exception.data, {"requiredCapabilities": {"elicitation": {}}})

    def test_missing_meta(self):
        self.assert_code(-32602, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    def test_missing_capabilities(self):
        request = lab.modern_request()
        del request["params"]["_meta"][lab.CAPABILITIES_KEY]
        self.assert_code(-32602, request)

    def test_missing_version(self):
        request = lab.modern_request()
        del request["params"]["_meta"][lab.VERSION_KEY]
        self.assert_code(-32602, request)

    def test_wrong_version(self):
        request = lab.modern_request()
        request["params"]["_meta"][lab.VERSION_KEY] = "2025-11-25"
        with self.assertRaises(lab.ProtocolFailure) as caught:
            lab.modern_gate(request)
        self.assertEqual(caught.exception.code, -32022)
        self.assertEqual(caught.exception.data, {"supported": ["2026-07-28"], "requested": "2025-11-25"})

    def test_null_bool_float_ids(self):
        for identifier in (None, True, False, 1.0, float("nan")):
            with self.subTest(identifier=identifier):
                self.assert_code(-32600, lab.modern_request(identifier))

    def test_string_empty_and_negative_ids(self):
        for identifier in ("1", "", -3):
            self.assertEqual(lab.modern_gate(lab.modern_request(identifier))["id"], identifier)

    def test_batch_is_outside_profile(self):
        self.assert_code(-32600, [lab.modern_request()])

    def test_modern_initialize_rejected(self):
        self.assert_code(-32601, lab.modern_request(method="initialize"))

    def test_mutable_inputs_unchanged(self):
        request = lab.modern_request()
        before = copy.deepcopy(request)
        lab.modern_gate(request)
        self.assertEqual(request, before)

    def test_classic_full_path(self):
        original = lab.ClassicState()
        waiting = lab.classic_step(original, self.initialize())
        ready = lab.classic_step(waiting, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual((original.phase, waiting.phase, ready.phase), ("new", "await-initialized", "ready"))
        self.assertEqual(lab.classic_step(ready, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}), ready)

    @staticmethod
    def initialize():
        return {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}

    def test_classic_request_before_init(self):
        with self.assertRaises(lab.ModelError):
            lab.classic_step(lab.ClassicState(), {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    def test_classic_initialized_cannot_have_id(self):
        with self.assertRaises(lab.ModelError):
            lab.classic_step(lab.ClassicState("await-initialized"), {
                "jsonrpc": "2.0", "id": 2, "method": "notifications/initialized"})

    def test_classic_rejects_modern_metadata(self):
        with self.assertRaises(lab.ModelError):
            lab.classic_step(lab.ClassicState("ready"), lab.modern_request())

    def test_classic_bad_meta_and_version(self):
        for value in (None, True, []):
            request = self.initialize()
            request["params"]["_meta"] = value
            with self.assertRaises(lab.ModelError):
                lab.classic_step(lab.ClassicState(), request)
        request = self.initialize()
        request["params"]["protocolVersion"] = "2026-07-28"
        with self.assertRaises(lab.ModelError):
            lab.classic_step(lab.ClassicState(), request)

    def test_classic_client_identity_required_but_not_authenticated(self):
        request = self.initialize()
        request["params"]["clientInfo"] = {"name": "unverified"}
        with self.assertRaises(lab.ModelError):
            lab.classic_step(lab.ClassicState(), request)

    def test_classic_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            lab.ClassicState().phase = "ready"


class SchemaTests(unittest.TestCase):
    def test_valid_ratio_and_literal_output(self):
        response = lab.invoke_ratio("r1", "ratio", {"numerator": 9, "denominator": 3})
        self.assertEqual(response["result"]["structuredContent"], {"quotient": 3.0})
        self.assertEqual(lab.classify_ratio_response(response, "r1"), "success")

    def test_zero_divisor_tool_error(self):
        response = lab.invoke_ratio(1, "ratio", {"numerator": 9, "denominator": 0})
        self.assertEqual(lab.classify_ratio_response(response, 1), "tool-error")
        self.assertNotIn("error", response)

    def test_unknown_tool_protocol_error(self):
        response = lab.invoke_ratio(1, "typo", {})
        self.assertEqual(response["error"]["code"], -32602)
        self.assertEqual(lab.classify_ratio_response(response, 1), "protocol-error")

    def test_malformed_argument_envelope_protocol_error(self):
        self.assertEqual(lab.classify_ratio_response(lab.invoke_ratio(1, "ratio", []), 1), "protocol-error")

    def test_argument_schema_failure_is_tool_error(self):
        self.assertEqual(lab.classify_ratio_response(lab.invoke_ratio(1, "ratio", {"numerator": "9"}), 1), "tool-error")

    def test_bool_is_not_numeric(self):
        for kind in ("integer", "number"):
            with self.assertRaises(lab.ModelError):
                lab.validate_value(lab.compile_schema({"type": kind}), True)

    def test_integer_valued_float_is_json_schema_integer(self):
        lab.validate_value(lab.compile_schema({"type": "integer"}), 3.0)
        with self.assertRaises(lab.ModelError):
            lab.validate_value(lab.compile_schema({"type": "integer"}), 3.1)

    def test_nonfinite_json_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(lab.ModelError):
                lab.validate_value(lab.compile_schema({"type": "number"}), value)

    def test_bounds_inclusive(self):
        schema = lab.compile_schema({"type": "number", "minimum": -1, "maximum": 1})
        for value in (-1, 0, 1):
            lab.validate_value(schema, value)
        for value in (-1.1, 1.1):
            with self.assertRaises(lab.ModelError):
                lab.validate_value(schema, value)

    def test_bad_bounds_rejected(self):
        for change in ({"minimum": True}, {"minimum": None}, {"maximum": float("nan")}, {"minimum": 2, "maximum": 1}):
            with self.assertRaises(lab.ModelError):
                lab.compile_schema({"type": "number", **change})

    def test_unknown_keywords_fail_closed(self):
        for keyword in ("$ref", "oneOf", "pattern", "format", "enum", "unevaluatedProperties"):
            with self.assertRaises(lab.ModelError):
                lab.compile_schema({"type": "string", keyword: "unsupported"})

    def test_boolean_schema_and_union_unsupported(self):
        for schema in (True, False, {"type": ["string", "null"]}, {}):
            with self.assertRaises(lab.ModelError):
                lab.compile_schema(schema)

    def test_explicit_dialect(self):
        lab.compile_schema({"type": "null", "$schema": "https://json-schema.org/draft/2020-12/schema"})
        with self.assertRaises(lab.ModelError):
            lab.compile_schema({"type": "null", "$schema": "http://json-schema.org/draft-07/schema#"})

    def test_required_and_extra_property(self):
        schema = lab.compile_schema({"type": "object", "properties": {"x": {"type": "string"}},
                                     "required": ["x"], "additionalProperties": False})
        for value in ({}, {"x": "ok", "y": 1}):
            with self.assertRaises(lab.ModelError):
                lab.validate_value(schema, value)

    def test_bad_required_list(self):
        for required in (["x", "x"], [True], ["undefined"], "x"):
            with self.assertRaises(lab.ModelError):
                lab.compile_schema({"type": "object", "properties": {"x": {"type": "string"}}, "required": required})

    def test_schema_valued_additional_properties_unsupported(self):
        with self.assertRaises(lab.ModelError):
            lab.compile_schema({"type": "object", "additionalProperties": {"type": "string"}})

    def test_arrays_and_scalar_structured_values(self):
        for raw, value in (({"type": "array", "items": {"type": "string"}}, ["a", "b"]),
                           ({"type": "null"}, None), ({"type": "boolean"}, False), ({"type": "string"}, "ok")):
            lab.validate_value(lab.compile_schema(raw), value)

    def test_array_child_mismatch(self):
        with self.assertRaises(lab.ModelError):
            lab.validate_value(lab.compile_schema({"type": "array", "items": {"type": "string"}}), ["a", 1])

    def test_schema_source_mutation_cannot_change_compiled_rule(self):
        raw = {"type": "object", "properties": {"x": {"type": "string"}}}
        schema = lab.compile_schema(raw)
        raw["properties"]["x"]["type"] = "number"
        lab.validate_value(schema, {"x": "still a string"})

    def test_bad_output_rejected(self):
        response = lab.invoke_ratio(1, "ratio", {"numerator": 1, "denominator": 2})
        response["result"]["structuredContent"]["quotient"] = "0.5"
        with self.assertRaises(lab.ModelError):
            lab.classify_ratio_response(response, 1)

    def test_missing_structured_output_rejected(self):
        response = lab.invoke_ratio(1, "ratio", {"numerator": 1, "denominator": 2})
        del response["result"]["structuredContent"]
        with self.assertRaises(lab.ModelError):
            lab.classify_ratio_response(response, 1)

    def test_id_type_correlation(self):
        response = lab.invoke_ratio(1, "ratio", {"numerator": 1, "denominator": 2})
        for expected in ("1", True, 1.0):
            with self.assertRaises(lab.ModelError):
                lab.classify_ratio_response(response, expected)

    def test_result_and_error_exclusive(self):
        response = lab.invoke_ratio(1, "ratio", {"numerator": 1, "denominator": 2})
        response["error"] = {"code": -32602, "message": "no"}
        with self.assertRaises(lab.ModelError):
            lab.classify_ratio_response(response, 1)

    def test_modern_result_type_required(self):
        response = lab.invoke_ratio(1, "ratio", {"numerator": 1, "denominator": 2})
        del response["result"]["resultType"]
        with self.assertRaises(lab.ModelError):
            lab.classify_ratio_response(response, 1)

    def test_mrtr_outside_complete_only_profile(self):
        response = {"jsonrpc": "2.0", "id": 1, "result": {"resultType": "input_required"}}
        with self.assertRaises(lab.ModelError):
            lab.classify_ratio_response(response, 1)

    def test_is_error_not_truthiness(self):
        response = lab.invoke_ratio(1, "ratio", {"numerator": 1, "denominator": 2})
        response["result"]["isError"] = "false"
        with self.assertRaises(lab.ModelError):
            lab.classify_ratio_response(response, 1)

    def test_overflow_becomes_tool_error(self):
        self.assertEqual(lab.classify_ratio_response(lab.invoke_ratio(1, "ratio", {
            "numerator": 1000, "denominator": 1e-320}), 1), "tool-error")

    def test_json_limits_and_non_json_values(self):
        for value in ({1: "key"}, (1, 2), {"bad": object()}, list(range(4097))):
            with self.assertRaises(lab.ModelError):
                lab.json_snapshot(value)
        recursive = []
        recursive.append(recursive)
        with self.assertRaises(lab.ModelError):
            lab.json_snapshot(recursive)


class LedgerTests(unittest.TestCase):
    def test_new_request_does_not_mutate_old_ledger(self):
        original = lab.Ledger()
        updated = lab.open_request(original, "a", 2, 10)
        self.assertEqual(original.requests, ())
        self.assertEqual((updated.clock, updated.requests[0].deadline), (2, 12))

    def test_duplicate_request_id(self):
        ledger = lab.open_request(lab.Ledger(), 1, 0, 10)
        with self.assertRaises(lab.ModelError):
            lab.open_request(ledger, 1, 1, 10)

    def test_string_and_integer_ids_distinct(self):
        ledger = lab.open_request(lab.open_request(lab.Ledger(), 1, 0, 10), "1", 1, 10)
        ledger, delivered = lab.receive_response(ledger, "1", {}, 2)
        self.assertTrue(delivered)
        self.assertEqual([item.state for item in ledger.requests], ["waiting", "completed"])

    def test_invalid_clock_and_timeout(self):
        for now, timeout in ((True, 1), (-1, 1), (0, False), (0, 0), (0, 1.0), (float("nan"), 2)):
            with self.assertRaises(lab.ModelError):
                lab.open_request(lab.Ledger(), 1, now, timeout)

    def test_clock_regression(self):
        ledger = lab.open_request(lab.Ledger(), 1, 5, 10)
        with self.assertRaises(lab.ModelError):
            lab.expire_requests(ledger, 4)

    def test_deadline_boundary(self):
        ledger = lab.open_request(lab.Ledger(), 1, 0, 10)
        self.assertEqual(lab.expire_requests(ledger, 9).requests[0].state, "waiting")
        self.assertEqual(lab.expire_requests(ledger, 10).requests[0].state, "unknown")

    def test_cancel_is_unknown_not_rollback(self):
        ledger = lab.open_request(lab.Ledger(), 1, 0, 10)
        store, _ = lab.business_effect(lab.BusinessStore(), "a", "t", None, "add", {})
        ledger = lab.abandon_request(ledger, 1, 1, "cancel-requested")
        self.assertEqual((ledger.requests[0].state, store.effect_count), ("unknown", 1))

    def test_broken_stream_requires_new_trace_id(self):
        ledger = lab.abandon_request(lab.open_request(lab.Ledger(), 1, 0, 10), 1, 1, "broken-stream")
        with self.assertRaises(lab.ModelError):
            lab.open_request(ledger, 1, 2, 10)
        self.assertEqual(len(lab.open_request(ledger, 2, 2, 10).requests), 2)

    def test_late_response_not_delivered(self):
        ledger, delivered = lab.receive_response(lab.open_request(lab.Ledger(), 1, 0, 10), 1, {"ok": True}, 10)
        self.assertFalse(delivered)
        self.assertEqual((ledger.requests[0].state, ledger.requests[0].reason), ("late-result", "deadline"))

    def test_unknown_response_id(self):
        with self.assertRaises(lab.ModelError):
            lab.receive_response(lab.Ledger(), 999, {}, 0)

    def test_duplicate_response(self):
        ledger, _ = lab.receive_response(lab.open_request(lab.Ledger(), 1, 0, 10), 1, {}, 1)
        with self.assertRaises(lab.ModelError):
            lab.receive_response(ledger, 1, {}, 2)

    def test_response_snapshot_immutable(self):
        result = {"count": [1]}
        ledger, _ = lab.receive_response(lab.open_request(lab.Ledger(), 1, 0, 10), 1, result, 1)
        result["count"].append(2)
        self.assertEqual(ledger.requests[0].response_json, '{"count":[1]}')

    def test_repeated_business_without_key_duplicates(self):
        store, _ = lab.business_effect(lab.BusinessStore(), "a", "t", None, "add", {})
        store, _ = lab.business_effect(store, "a", "t", None, "add", {})
        self.assertEqual(store.effect_count, 2)

    def test_business_key_deduplicates_same_intent(self):
        store, receipt = lab.business_effect(lab.BusinessStore(), "a", "t", "key", "add", {"x": 1})
        updated, retried = lab.business_effect(store, "a", "t", "key", "add", {"x": 1})
        self.assertEqual((updated.effect_count, receipt, retried), (1, 1, 1))
        self.assertIs(updated, store)

    def test_business_key_cannot_change_intent(self):
        store, _ = lab.business_effect(lab.BusinessStore(), "a", "t", "key", "add", {"x": 1})
        with self.assertRaises(lab.ModelError):
            lab.business_effect(store, "a", "t", "key", "add", {"x": 2})

    def test_business_key_scoped_to_identity(self):
        store, _ = lab.business_effect(lab.BusinessStore(), "a", "t", "key", "add", {})
        store, _ = lab.business_effect(store, "b", "t", "key", "add", {})
        store, _ = lab.business_effect(store, "a", "u", "key", "add", {})
        self.assertEqual(store.effect_count, 3)

    def test_business_key_empty_rejected(self):
        with self.assertRaises(lab.ModelError):
            lab.business_effect(lab.BusinessStore(), "a", "t", "", "add", {})

    def test_immutable_store_rejects_mutable_constructor(self):
        with self.assertRaises(lab.ModelError):
            lab.Ledger(requests=[])
        with self.assertRaises(lab.ModelError):
            lab.BusinessStore(records=[])


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.key = lab.make_cache_key("s", "2026-07-28", "alice", "t", "tools/list", {}, "p1", "c1", "auth-a1")
        self.entries = lab.cache_put((), self.key, {"tools": ["safe"]}, 0, 10, True)

    def test_same_identity_hit(self):
        self.assertEqual(lab.cache_get(self.entries, self.key, 1, True), {"tools": ["safe"]})

    def test_principal_partition(self):
        self.assertIsNone(lab.cache_get(self.entries, replace(self.key, principal="bob"), 1, True))

    def test_same_principal_different_authorization_context_partition(self):
        self.assertIsNone(lab.cache_get(self.entries, replace(self.key, authorization_context="auth-a2"), 1, True))

    def test_tenant_partition(self):
        self.assertIsNone(lab.cache_get(self.entries, replace(self.key, tenant="u"), 1, True))

    def test_policy_revision_partition(self):
        self.assertIsNone(lab.cache_get(self.entries, replace(self.key, policy_revision="p2"), 1, True))

    def test_catalog_revision_partition(self):
        self.assertIsNone(lab.cache_get(self.entries, replace(self.key, catalog_revision="c2"), 1, True))

    def test_server_and_protocol_partition(self):
        for changes in ({"server": "s2"}, {"revision": "2025-11-25"}):
            self.assertIsNone(lab.cache_get(self.entries, replace(self.key, **changes), 1, True))

    def test_method_and_arguments_partition(self):
        for changes in ({"method": "resources/read"}, {"arguments_json": '{"cursor":"next"}'}):
            self.assertIsNone(lab.cache_get(self.entries, replace(self.key, **changes), 1, True))

    def test_argument_key_order_canonicalized(self):
        first = lab.make_cache_key("s", lab.MODERN, "a", "t", "resources/read", {"a": 1, "b": 2}, "p", "c", "auth-1")
        second = lab.make_cache_key("s", lab.MODERN, "a", "t", "resources/read", {"b": 2, "a": 1}, "p", "c", "auth-1")
        self.assertEqual(first, second)

    def test_input_argument_snapshot(self):
        arguments = {"ids": [1]}
        key = lab.make_cache_key("s", lab.MODERN, "a", "t", "resources/read", arguments, "p", "c", "auth-1")
        arguments["ids"].append(2)
        self.assertEqual(key.arguments_json, '{"ids":[1]}')

    def test_read_and_write_payload_copy(self):
        payload = {"tools": ["one"]}
        entries = lab.cache_put((), self.key, payload, 0, 10, True)
        payload["tools"].append("two")
        result = lab.cache_get(entries, self.key, 1, True)
        result["tools"].append("three")
        self.assertEqual(lab.cache_get(entries, self.key, 2, True), {"tools": ["one"]})

    def test_auth_recheck_on_hit(self):
        self.assertIsNone(lab.cache_get(self.entries, self.key, 1, False))

    def test_expiry_boundary_and_zero_ttl(self):
        self.assertIsNotNone(lab.cache_get(self.entries, self.key, 9, True))
        self.assertIsNone(lab.cache_get(self.entries, self.key, 10, True))
        zero = lab.cache_put((), self.key, {}, 1, 0, True)
        self.assertIsNone(lab.cache_get(zero, self.key, 1, True))

    def test_public_scope_outside_private_model(self):
        with self.assertRaises(lab.ModelError):
            lab.cache_put((), self.key, {}, 0, 10, True, "public")

    def test_invalid_auth_type_and_unauthorized_put(self):
        with self.assertRaises(lab.ModelError):
            lab.cache_put((), self.key, {}, 0, 10, False)
        with self.assertRaises(lab.ModelError):
            lab.cache_get(self.entries, self.key, 1, 1)

    def test_bad_ttl_and_backwards_clock(self):
        for ttl in (True, -1, 1.5, float("nan")):
            with self.assertRaises(lab.ModelError):
                lab.cache_put((), self.key, {}, 0, ttl, True)
        entries = lab.cache_put((), self.key, {}, 5, 10, True)
        with self.assertRaises(lab.ModelError):
            lab.cache_get(entries, self.key, 4, True)

    def test_new_policy_cache_does_not_reuse_old_data(self):
        new_key = replace(self.key, policy_revision="p2")
        entries = lab.cache_put(self.entries, new_key, {"tools": []}, 1, 10, True)
        self.assertEqual(lab.cache_get(entries, new_key, 2, True), {"tools": []})

    def test_writes_not_cacheable_in_model(self):
        with self.assertRaises(lab.ModelError):
            lab.make_cache_key("s", lab.MODERN, "a", "t", "tools/call", {}, "p", "c", "auth-1")

    def test_mrtr_retries_not_cacheable(self):
        for arguments in ({"inputResponses": {}}, {"requestState": "opaque"}, []):
            with self.assertRaises(lab.ModelError):
                lab.make_cache_key("s", lab.MODERN, "a", "t", "resources/read", arguments, "p", "c", "auth-1")

    def test_cache_key_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            self.key.principal = "bob"


class CliTests(unittest.TestCase):
    def capture(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(lab.main(argv), 0)
        return output.getvalue()

    def test_list_literal(self):
        self.assertEqual(self.capture(["--list"]), "revision-gate\ntool-contract\nrequest-ledger\nprincipal-cache\n")

    def test_help_is_safe_default(self):
        self.assertIn("--lab", self.capture([]))

    def test_all_literal_oracles(self):
        result = json.loads(self.capture(["--lab", "all"]))
        self.assertEqual(result["revision-gate"], {"classic_phase": "ready", "classic_revision": "2025-11-25",
                         "modern_prior_session_required": False, "modern_revision": "2026-07-28"})
        self.assertEqual(result["tool-contract"], {"valid": "success", "zero_divisor": "tool-error", "unknown_tool": "protocol-error"})
        self.assertEqual(result["request-ledger"], {"business_effects": 1, "first_request_state": "unknown",
                         "retry_delivered": True, "retry_new_rpc_id": "rpc-2", "same_receipt": True})
        self.assertEqual(result["principal-cache"], {"same_principal_hit": True, "other_principal_hit": False,
                         "revoked_permission_hit": False, "at_expiry_hit": False})

    def test_each_lab_deterministic(self):
        for name in lab.LAB_NAMES:
            self.assertEqual(self.capture(["--lab", name]), self.capture(["--lab", name]))


if __name__ == "__main__":
    unittest.main()
