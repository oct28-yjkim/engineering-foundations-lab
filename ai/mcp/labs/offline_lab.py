"""Bounded, deterministic MCP teaching models; not an MCP SDK or wire server.

Only Python stdlib, explicit logical clocks, and synthetic in-memory values.
No network, subprocess, filesystem access, OAuth, or real tool side effects.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import json
import math
from typing import Any


MODERN = "2026-07-28"
CLASSIC = "2025-11-25"
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
LAB_NAMES = ("revision-gate", "tool-contract", "request-ledger", "principal-cache")


class ModelError(ValueError):
    """An explicitly rejected model input, not a remote protocol response."""


class ProtocolFailure(ModelError):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


def text_value(value: Any, name: str) -> str:
    if type(value) is not str or not value or len(value) > 256:
        raise ModelError(f"{name}: expected a nonempty string of at most 256 characters")
    return value


def integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ModelError(f"{name}: expected integer >= {minimum}, not bool")
    return value


def rpc_id(value: Any) -> str | int:
    # Unlike integer clocks, JSON-RPC IDs may be negative or empty strings.
    if type(value) not in (str, int):
        raise ModelError("request ID must be a string or integer, not null/bool/float")
    return value


def json_snapshot(value: Any) -> str:
    """Small JSON-only input boundary; immutable canonical snapshot, not RFC 8785."""
    budget = [4096]

    def inspect(item: Any, depth: int) -> None:
        budget[0] -= 1
        if depth > 16 or budget[0] < 0:
            raise ModelError("JSON model limit exceeded")
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise ModelError("non-finite numbers are not JSON")
            return
        if type(item) is list:
            for child in item:
                inspect(child, depth + 1)
            return
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise ModelError("JSON object keys must be strings")
                inspect(child, depth + 1)
            return
        raise ModelError("unsupported non-JSON value")

    inspect(value, 0)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _request(message: Any) -> tuple[str | int, str, dict]:
    if type(message) is not dict or message.get("jsonrpc") != "2.0":
        raise ProtocolFailure(-32600, "single JSON-RPC request required")
    try:
        identifier = rpc_id(message.get("id"))
        method = text_value(message.get("method"), "method")
    except ModelError as error:
        raise ProtocolFailure(-32600, str(error)) from error
    params = message.get("params", {})
    if type(params) is not dict:
        raise ProtocolFailure(-32602, "object params required by this model")
    try:
        json_snapshot(params)
    except ModelError as error:
        raise ProtocolFailure(-32602, str(error)) from error
    return identifier, method, params


def modern_gate(message: Any, required_capabilities: tuple[str, ...] = ()) -> dict:
    """One request, no prior session. Capability checks are top-level only."""
    identifier, method, params = _request(message)
    meta = params.get("_meta")
    if type(meta) is not dict or type(meta.get(VERSION_KEY)) is not str:
        raise ProtocolFailure(-32602, "missing protocol version metadata")
    capabilities = meta.get(CAPABILITIES_KEY)
    if type(capabilities) is not dict:
        raise ProtocolFailure(-32602, "missing client capabilities metadata")
    if meta[VERSION_KEY] != MODERN:
        raise ProtocolFailure(-32022, "unsupported protocol revision", {"supported": [MODERN], "requested": meta[VERSION_KEY]})
    if type(required_capabilities) is not tuple:
        raise ModelError("required_capabilities must be a tuple")
    missing = []
    for name in required_capabilities:
        text_value(name, "capability name")
        if type(capabilities.get(name)) is not dict:
            missing.append(name)
    if missing:
        raise ProtocolFailure(-32021, "required client capability absent", {
            "requiredCapabilities": {name: {} for name in missing}})
    if method not in ("server/discover", "tools/list", "tools/call", "resources/read"):
        raise ProtocolFailure(-32601, "method outside modern teaching profile")
    return {"id": identifier, "method": method, "revision": MODERN, "prior_session_required": False}


@dataclass(frozen=True)
class ClassicState:
    phase: str = "new"

    def __post_init__(self) -> None:
        if self.phase not in ("new", "await-initialized", "ready"):
            raise ModelError("unknown classic phase")


def classic_step(state: ClassicState, message: Any) -> ClassicState:
    """Successful classic handshake path; excludes ping/logging/negotiation fallback."""
    if not isinstance(state, ClassicState):
        raise ModelError("ClassicState required")
    if state.phase == "await-initialized":
        if (type(message) is not dict or message.get("jsonrpc") != "2.0"
                or message.get("method") != "notifications/initialized" or "id" in message):
            raise ModelError("classic profile waits for initialized notification without ID")
        return ClassicState("ready")
    _, method, params = _request(message)
    if "_meta" in params:
        if type(params["_meta"]) is not dict:
            raise ModelError("metadata must be an object")
        if VERSION_KEY in params["_meta"] or CAPABILITIES_KEY in params["_meta"]:
            raise ModelError("do not mix modern metadata into this classic model")
    if state.phase == "new":
        if method != "initialize" or params.get("protocolVersion") != CLASSIC:
            raise ModelError("classic profile requires matching initialize first")
        if type(params.get("capabilities")) is not dict or type(params.get("clientInfo")) is not dict:
            raise ModelError("classic initialize requires capabilities and clientInfo")
        text_value(params["clientInfo"].get("name"), "clientInfo.name")
        text_value(params["clientInfo"].get("version"), "clientInfo.version")
        return ClassicState("await-initialized")
    if method not in ("tools/list", "tools/call", "resources/read"):
        raise ModelError("method outside ready classic profile")
    return state


@dataclass(frozen=True)
class TinySchema:
    kind: str
    properties: tuple[tuple[str, "TinySchema"], ...] = ()
    required: tuple[str, ...] = ()
    additional: bool = True
    items: "TinySchema | None" = None
    minimum: int | float | None = None
    maximum: int | float | None = None


def compile_schema(schema: Any, depth: int = 0) -> TinySchema:
    """Fail closed on keywords outside this small JSON Schema 2020-12 subset."""
    integer(depth, "depth")
    if depth > 16 or type(schema) is not dict:
        raise ModelError("schema must be a bounded object; boolean schemas unsupported")
    kind = schema.get("type")
    if kind not in ("object", "array", "string", "number", "integer", "boolean", "null"):
        raise ModelError("explicit single type required")
    allowed = {"type", "$schema", "description"}
    allowed |= {"object": {"properties", "required", "additionalProperties"},
                "array": {"items"}, "number": {"minimum", "maximum"},
                "integer": {"minimum", "maximum"}}.get(kind, set())
    if set(schema) - allowed:
        raise ModelError("unsupported schema keyword")
    if "$schema" in schema and schema["$schema"] != "https://json-schema.org/draft/2020-12/schema":
        raise ModelError("only the teaching 2020-12 profile is supported")
    if "description" in schema and type(schema["description"]) is not str:
        raise ModelError("description must be text")
    props: tuple[tuple[str, TinySchema], ...] = ()
    required: tuple[str, ...] = ()
    additional = True
    items = None
    if kind == "object":
        raw_props = schema.get("properties", {})
        raw_required = schema.get("required", [])
        if type(raw_props) is not dict or len(raw_props) > 64:
            raise ModelError("properties must be a bounded object")
        if any(type(key) is not str for key in raw_props):
            raise ModelError("property names must be strings")
        if type(raw_required) is not list or any(type(key) is not str for key in raw_required):
            raise ModelError("required must be a list of property names")
        if len(set(raw_required)) != len(raw_required) or set(raw_required) - set(raw_props):
            raise ModelError("required must be unique and defined in properties in this subset")
        additional = schema.get("additionalProperties", True)
        if type(additional) is not bool:
            raise ModelError("schema-valued additionalProperties unsupported")
        props = tuple((key, compile_schema(child, depth + 1)) for key, child in sorted(raw_props.items()))
        required = tuple(raw_required)
    elif kind == "array":
        if "items" not in schema:
            raise ModelError("array items required in this subset")
        items = compile_schema(schema["items"], depth + 1)
    bounds = [schema.get("minimum"), schema.get("maximum")]
    if any(name in schema and schema[name] is None for name in ("minimum", "maximum")):
        raise ModelError("explicit null is not a numeric bound")
    for bound in bounds:
        if bound is not None and (type(bound) not in (int, float)
                                  or (type(bound) is float and not math.isfinite(bound))):
            raise ModelError("bounds must be finite numbers, not bool")
    if bounds[0] is not None and bounds[1] is not None and bounds[0] > bounds[1]:
        raise ModelError("minimum exceeds maximum")
    return TinySchema(kind, props, required, additional, items, *bounds)


def validate_value(schema: TinySchema, value: Any) -> None:
    if not isinstance(schema, TinySchema):
        raise ModelError("compile schema before validation")
    json_snapshot(value)

    def check(rule: TinySchema, item: Any, path: str) -> None:
        valid = {"object": type(item) is dict, "array": type(item) is list,
                 "string": type(item) is str, "boolean": type(item) is bool,
                 "null": item is None, "number": type(item) in (int, float),
                 "integer": type(item) is int or (type(item) is float and item.is_integer())}[rule.kind]
        if not valid:
            raise ModelError(f"{path}: expected {rule.kind}")
        if rule.kind == "object":
            props = dict(rule.properties)
            if set(rule.required) - set(item):
                raise ModelError(f"{path}: required property missing")
            if not rule.additional and set(item) - set(props):
                raise ModelError(f"{path}: additional property rejected")
            for key, child in item.items():
                if key in props:
                    check(props[key], child, f"{path}.{key}")
        elif rule.kind == "array":
            if rule.items is None:
                raise ModelError("invalid compiled array schema")
            for index, child in enumerate(item):
                check(rule.items, child, f"{path}[{index}]")
        elif rule.kind in ("number", "integer"):
            if rule.minimum is not None and item < rule.minimum:
                raise ModelError(f"{path}: below minimum")
            if rule.maximum is not None and item > rule.maximum:
                raise ModelError(f"{path}: above maximum")

    check(schema, value, "$")


RATIO_INPUT = compile_schema({"type": "object", "properties": {
    "numerator": {"type": "number", "minimum": -1000, "maximum": 1000},
    "denominator": {"type": "number", "minimum": -1000, "maximum": 1000}},
    "required": ["numerator", "denominator"], "additionalProperties": False})
RATIO_OUTPUT = compile_schema({"type": "object", "properties": {"quotient": {"type": "number"}},
                               "required": ["quotient"], "additionalProperties": False})


def _tool_error(identifier: str | int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": identifier, "result": {"resultType": "complete",
            "content": [{"type": "text", "text": message}], "isError": True}}


def invoke_ratio(identifier: Any, name: Any, arguments: Any) -> dict:
    identifier = rpc_id(identifier)
    if type(name) is not str or type(arguments) is not dict:
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": -32602, "message": "Malformed call parameters"}}
    if name != "ratio":
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": -32602, "message": "Unknown tool"}}
    try:
        validate_value(RATIO_INPUT, arguments)
    except ModelError:
        return _tool_error(identifier, "Arguments violate the ratio input contract")
    if arguments["denominator"] == 0:
        return _tool_error(identifier, "Denominator must be nonzero")
    quotient = arguments["numerator"] / arguments["denominator"]
    if not math.isfinite(quotient):
        return _tool_error(identifier, "Quotient exceeds the teaching numeric range")
    output = {"quotient": quotient}
    validate_value(RATIO_OUTPUT, output)
    return {"jsonrpc": "2.0", "id": identifier, "result": {"resultType": "complete",
            "content": [{"type": "text", "text": json_snapshot(output)}],
            "structuredContent": output, "isError": False}}


def classify_ratio_response(response: Any, expected_id: Any) -> str:
    rpc_id(expected_id)
    if type(response) is not dict or response.get("jsonrpc") != "2.0":
        raise ModelError("invalid response envelope")
    identifier = rpc_id(response.get("id"))
    if type(identifier) is not type(expected_id) or identifier != expected_id:
        raise ModelError("response ID does not correlate")
    if ("result" in response) == ("error" in response):
        raise ModelError("exactly one of result/error required")
    if "error" in response:
        error = response["error"]
        if type(error) is not dict or type(error.get("code")) is not int or type(error.get("message")) is not str:
            raise ModelError("invalid JSON-RPC error")
        return "protocol-error"
    result = response["result"]
    if type(result) is not dict or result.get("resultType") != "complete":
        raise ModelError("this modern profile accepts complete results only")
    if type(result.get("isError", False)) is not bool:
        raise ModelError("isError must be boolean")
    content = result.get("content")
    if type(content) is not list or any(type(item) is not dict or item.get("type") != "text"
                                       or type(item.get("text")) is not str for item in content):
        raise ModelError("this model accepts text content blocks only")
    if result.get("isError", False):
        return "tool-error"
    if "structuredContent" not in result:
        raise ModelError("ratio success requires structuredContent")
    validate_value(RATIO_OUTPUT, result["structuredContent"])
    return "success"


@dataclass(frozen=True)
class PendingRequest:
    identifier: str | int
    deadline: int
    state: str = "waiting"
    reason: str = ""
    response_json: str | None = None

    def __post_init__(self) -> None:
        rpc_id(self.identifier)
        integer(self.deadline, "deadline")
        if self.state not in ("waiting", "unknown", "completed", "late-result"):
            raise ModelError("unknown request state")


@dataclass(frozen=True)
class Ledger:
    clock: int = 0
    requests: tuple[PendingRequest, ...] = ()

    def __post_init__(self) -> None:
        integer(self.clock, "ledger clock")
        if type(self.requests) is not tuple or any(not isinstance(item, PendingRequest) for item in self.requests):
            raise ModelError("requests must be an immutable tuple of PendingRequest")
        identifiers = [(type(item.identifier), item.identifier) for item in self.requests]
        if len(set(identifiers)) != len(identifiers):
            raise ModelError("duplicate ledger request IDs")


def _advance(ledger: Ledger, now: Any) -> Ledger:
    integer(now, "clock")
    if now < ledger.clock:
        raise ModelError("logical clock cannot move backwards")
    return replace(ledger, clock=now, requests=tuple(
        replace(item, state="unknown", reason="deadline")
        if item.state == "waiting" and now >= item.deadline else item for item in ledger.requests))


def _index(ledger: Ledger, identifier: Any) -> int:
    rpc_id(identifier)
    for index, item in enumerate(ledger.requests):
        if type(item.identifier) is type(identifier) and item.identifier == identifier:
            return index
    raise ModelError("unknown request ID")


def _update(ledger: Ledger, index: int, request: PendingRequest) -> Ledger:
    return replace(ledger, requests=ledger.requests[:index] + (request,) + ledger.requests[index + 1:])


def open_request(ledger: Ledger, identifier: Any, now: Any, timeout: Any) -> Ledger:
    rpc_id(identifier)
    integer(timeout, "timeout", 1)
    ledger = _advance(ledger, now)
    # Deliberately stronger than protocol uniqueness: never reuse within one model trace.
    if any(type(item.identifier) is type(identifier) and item.identifier == identifier for item in ledger.requests):
        raise ModelError("this trace never reuses request IDs")
    return replace(ledger, requests=ledger.requests + (PendingRequest(identifier, now + timeout),))


def abandon_request(ledger: Ledger, identifier: Any, now: Any, reason: str) -> Ledger:
    if reason not in ("cancel-requested", "broken-stream"):
        raise ModelError("unsupported abandonment reason")
    ledger = _advance(ledger, now)
    index = _index(ledger, identifier)
    request = ledger.requests[index]
    if request.state != "waiting":
        raise ModelError("only a waiting request can be abandoned")
    return _update(ledger, index, replace(request, state="unknown", reason=reason))


def expire_requests(ledger: Ledger, now: Any) -> Ledger:
    return _advance(ledger, now)


def receive_response(ledger: Ledger, identifier: Any, response: Any, now: Any) -> tuple[Ledger, bool]:
    ledger = _advance(ledger, now)
    index = _index(ledger, identifier)
    request = ledger.requests[index]
    if request.state not in ("waiting", "unknown"):
        raise ModelError("duplicate terminal response")
    payload = json_snapshot(response)
    delivered = request.state == "waiting"
    updated = replace(request, state="completed" if delivered else "late-result", response_json=payload)
    return _update(ledger, index, updated), delivered


@dataclass(frozen=True)
class BusinessRecord:
    principal: str
    tenant: str
    key: str
    fingerprint: str
    result: int


@dataclass(frozen=True)
class BusinessStore:
    effect_count: int = 0
    records: tuple[BusinessRecord, ...] = ()

    def __post_init__(self) -> None:
        integer(self.effect_count, "effect count")
        if type(self.records) is not tuple or any(not isinstance(item, BusinessRecord) for item in self.records):
            raise ModelError("business records must be an immutable tuple")


def business_effect(store: BusinessStore, principal: str, tenant: str,
                    key: str | None, operation: str, arguments: Any) -> tuple[BusinessStore, int]:
    """Atomic *toy* deduplication; RPC IDs never participate in business identity."""
    for name, value in (("principal", principal), ("tenant", tenant), ("operation", operation)):
        text_value(value, name)
    if key is not None:
        text_value(key, "business key")
    fingerprint = json_snapshot({"operation": operation, "arguments": arguments})
    for record in store.records:
        if key is not None and (record.principal, record.tenant, record.key) == (principal, tenant, key):
            if record.fingerprint != fingerprint:
                raise ModelError("business key reused with different operation or arguments")
            return store, record.result
    result = store.effect_count + 1
    records = store.records
    if key is not None:
        records += (BusinessRecord(principal, tenant, key, fingerprint, result),)
    return BusinessStore(result, records), result


@dataclass(frozen=True)
class CacheKey:
    server: str
    revision: str
    principal: str
    tenant: str
    method: str
    arguments_json: str
    policy_revision: str
    catalog_revision: str
    authorization_context: str

    def __post_init__(self) -> None:
        for name in ("server", "principal", "tenant", "policy_revision", "catalog_revision", "authorization_context"):
            text_value(getattr(self, name), name)
        if self.revision not in (MODERN, CLASSIC) or self.method not in ("tools/list", "resources/read"):
            raise ModelError("cache key outside teaching profile")
        if type(self.arguments_json) is not str:
            raise ModelError("immutable arguments snapshot required")


def make_cache_key(server: str, revision: str, principal: str, tenant: str, method: str,
                   arguments: Any, policy_revision: str, catalog_revision: str, authorization_context: str) -> CacheKey:
    for name, value in (("server", server), ("principal", principal), ("tenant", tenant),
                        ("policy_revision", policy_revision), ("catalog_revision", catalog_revision),
                        ("authorization_context", authorization_context)):
        text_value(value, name)
    if revision not in (MODERN, CLASSIC) or method not in ("tools/list", "resources/read"):
        raise ModelError("cache profile only models selected read methods and explicit revisions")
    if type(arguments) is not dict or "inputResponses" in arguments or "requestState" in arguments:
        raise ModelError("only ordinary object params are cached; MRTR retries are excluded")
    return CacheKey(server, revision, principal, tenant, method, json_snapshot(arguments),
                    policy_revision, catalog_revision, authorization_context)


@dataclass(frozen=True)
class CacheEntry:
    key: CacheKey
    payload_json: str
    created_at: int
    expires_at: int


def cache_put(entries: tuple[CacheEntry, ...], key: CacheKey, payload: Any,
              now: Any, ttl_ms: Any, authorized: bool, cache_scope: str = "private") -> tuple[CacheEntry, ...]:
    integer(now, "clock")
    integer(ttl_ms, "ttlMs")
    if type(entries) is not tuple or not isinstance(key, CacheKey):
        raise ModelError("immutable entries and CacheKey required")
    if authorized is not True or cache_scope != "private":
        raise ModelError("only already-authorized private entries are modeled")
    entry = CacheEntry(key, json_snapshot(payload), now, now + ttl_ms)
    return tuple(item for item in entries if item.key != key) + (entry,)


def cache_get(entries: tuple[CacheEntry, ...], key: CacheKey, now: Any, authorized: bool) -> Any:
    integer(now, "clock")
    if type(entries) is not tuple or not isinstance(key, CacheKey):
        raise ModelError("immutable entries and CacheKey required")
    if type(authorized) is not bool:
        raise ModelError("authorization must be an explicit boolean")
    if not authorized:
        return None
    for entry in entries:
        if entry.key == key:
            if now < entry.created_at:
                raise ModelError("lookup predates insertion")
            return json.loads(entry.payload_json) if now < entry.expires_at else None
    return None


def modern_request(identifier: str | int = 1, method: str = "tools/list") -> dict:
    return {"jsonrpc": "2.0", "id": identifier, "method": method, "params": {"_meta": {
        VERSION_KEY: MODERN, CAPABILITIES_KEY: {}}}}


def demo_revision() -> dict:
    modern = modern_gate(modern_request())
    old = classic_step(ClassicState(), {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": CLASSIC, "capabilities": {}, "clientInfo": {"name": "cpu-lab", "version": "1"}}})
    old = classic_step(old, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    return {"modern_revision": modern["revision"], "modern_prior_session_required": False,
            "classic_revision": CLASSIC, "classic_phase": old.phase}


def demo_contract() -> dict:
    return {"valid": classify_ratio_response(invoke_ratio(1, "ratio", {"numerator": 6, "denominator": 2}), 1),
            "zero_divisor": classify_ratio_response(invoke_ratio(2, "ratio", {"numerator": 6, "denominator": 0}), 2),
            "unknown_tool": classify_ratio_response(invoke_ratio(3, "missing", {}), 3)}


def demo_ledger() -> dict:
    ledger = open_request(Ledger(), "rpc-1", 0, 10)
    store, first = business_effect(BusinessStore(), "alice", "tenant-a", "order-7", "increment", {})
    ledger = abandon_request(ledger, "rpc-1", 5, "broken-stream")
    ledger = open_request(ledger, "rpc-2", 6, 10)
    store, retry = business_effect(store, "alice", "tenant-a", "order-7", "increment", {})
    ledger, delivered = receive_response(ledger, "rpc-2", {"receipt": retry}, 7)
    return {"first_request_state": ledger.requests[0].state, "retry_new_rpc_id": "rpc-2",
            "business_effects": store.effect_count, "same_receipt": first == retry, "retry_delivered": delivered}


def demo_cache() -> dict:
    key = make_cache_key("server-a", MODERN, "alice", "tenant-a", "tools/list", {}, "p1", "c1", "auth-a1")
    entries = cache_put((), key, {"tools": ["read_public_fixture"]}, 0, 10, True)
    return {"same_principal_hit": cache_get(entries, key, 1, True) is not None,
            "other_principal_hit": cache_get(entries, replace(key, principal="bob"), 1, True) is not None,
            "revoked_permission_hit": cache_get(entries, key, 1, False) is not None,
            "at_expiry_hit": cache_get(entries, key, 10, True) is not None}


DEMOS = dict(zip(LAB_NAMES, (demo_revision, demo_contract, demo_ledger, demo_cache)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true", help="list bounded teaching models")
    group.add_argument("--lab", choices=(*LAB_NAMES, "all"), help="run deterministic synthetic examples")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(LAB_NAMES))
    elif args.lab:
        selected = LAB_NAMES if args.lab == "all" else (args.lab,)
        print(json.dumps({name: DEMOS[name]() for name in selected}, indent=2, sort_keys=True))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
