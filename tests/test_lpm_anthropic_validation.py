"""The Anthropic setup-token probe: the exact wire request, and the three-outcome mapping.

SPECIFICATION/contracts.md states the validation request literally — one HTTPS `POST` to
`https://api.anthropic.com/v1/messages` with four named headers and one exact UTF-8 JSON body
— and states the response mapping as a table whose unmatched default is `inconclusive`.
SPECIFICATION/spec.md then closes the outcome vocabulary at definitive success, definitive
credential rejection and inconclusive, and requires rate limiting, provider outage, transport
failure and timeout to be INCONCLUSIVE rather than credential rejection.

That last requirement is the one worth pinning hardest, because getting it wrong is silent
and expensive: a `529` read as rejection walks a perfectly good credential toward `dead`
every time Anthropic has a bad minute. So the inconclusive rows are enumerated here
individually rather than sampled.

The probe is INJECTED, and the test asserts that too. A module that could reach the network
on its own would be one import away from also being able to relay inference traffic, which
spec.md forbids outright.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_MESSAGE_BODY = {
    "id": "msg_01",
    "type": "message",
    "role": "assistant",
    "usage": {"input_tokens": 8, "output_tokens": 1},
}


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_anthropic.py"
    assert module_path.is_file(), "overseer/_lpm_anthropic.py must exist"
    return (
        importlib.import_module("_lpm_anthropic"),
        importlib.import_module("_lpm_registry"),
    )


def _outcome(anthropic, **changes) -> str:
    fields = {"reached": True, "status": 200, "body": dict(_MESSAGE_BODY)}
    fields.update(changes)
    return anthropic.validation_outcome(response=anthropic.ProbeResponse(**fields))


def _body(**changes) -> dict[str, object]:
    body = dict(_MESSAGE_BODY)
    body.update(changes)
    return body


def test_the_probe_request_is_the_one_wire_form_the_contract_states_literally():
    anthropic, registry = _modules()

    request = anthropic.probe_request(credential="sk-ant-oat0-example")

    assert request.method == "POST"
    assert request.url == "https://api.anthropic.com/v1/messages"
    assert dict(request.headers) == {
        "Authorization": "Bearer sk-ant-oat0-example",
        "anthropic-beta": "oauth-2025-04-20",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    assert request.body == (
        '{"model":"claude-haiku-4-5-20251001","max_tokens":1,'
        '"messages":[{"role":"user","content":"hi"}]}'
    )
    assert anthropic.VALIDATION_MODEL == "claude-haiku-4-5-20251001"
    row = registry.provider_row(provider="anthropic", kind="claude-code-oauth")
    assert row is not None and row.validation_adapter == anthropic.VALIDATION_ADAPTER


def test_a_well_formed_two_hundred_is_the_only_definitive_success():
    anthropic, _ = _modules()

    assert _outcome(anthropic) == anthropic.DEFINITIVE_SUCCESS
    assert anthropic.INFERENCE_CAPABLE_OUTCOME == anthropic.DEFINITIVE_SUCCESS
    assert anthropic.VALIDATION_OUTCOMES == (
        anthropic.DEFINITIVE_SUCCESS,
        anthropic.DEFINITIVE_REJECTION,
        anthropic.INCONCLUSIVE,
    )


def test_only_four_oh_one_and_four_oh_three_are_definitive_credential_rejection():
    anthropic, _ = _modules()

    for status in (401, 403):
        assert _outcome(anthropic, status=status) == anthropic.DEFINITIVE_REJECTION


def test_rate_limiting_outage_transport_failure_and_every_other_status_are_inconclusive():
    anthropic, _ = _modules()

    for status in (429, 500, 529, 599, 404, 302):
        assert _outcome(anthropic, status=status) == anthropic.INCONCLUSIVE
    # A transport failure or an expired probe deadline never reached a status at all.
    assert _outcome(anthropic, reached=False, status=0, body=None) == anthropic.INCONCLUSIVE


def test_a_two_hundred_whose_body_is_not_a_conforming_message_is_inconclusive():
    anthropic, _ = _modules()

    malformed: tuple[object, ...] = (
        ["not", "an", "object"],
        _body(id=""),
        _body(id=7),
        _body(type="error"),
        _body(role="user"),
        _body(usage="not-an-object"),
        _body(usage={"input_tokens": 8}),
        _body(usage={"input_tokens": True, "output_tokens": 1}),
        _body(usage={"input_tokens": -1, "output_tokens": 1}),
    )
    for body in malformed:
        assert _outcome(anthropic, body=body) == anthropic.INCONCLUSIVE, body


def test_validation_runs_exactly_one_injected_probe_and_reports_its_outcome():
    anthropic, _ = _modules()
    seen: list[object] = []

    def probe(*, request):
        seen.append(request)
        return anthropic.ProbeResponse(reached=True, status=401)

    outcome = anthropic.validate_credential(credential="sk-ant-oat0-dead", probe=probe)

    assert outcome == anthropic.DEFINITIVE_REJECTION
    assert len(seen) == 1


def test_no_manager_component_can_proxy_or_relay_inference_traffic():
    anthropic, _ = _modules()
    ast = importlib.import_module("ast")
    package = pathlib.Path(anthropic.__file__).parent

    # spec.md: the manager MUST NOT proxy, relay or rewrite inference traffic, enter the
    # inference request path, or pool subscription credentials behind a shared network
    # endpoint. No manager module imports a transport at all — the one outbound call this
    # operation is permitted to make is performed by an INJECTED probe, so the whole family
    # is structurally incapable of speaking to a provider on its own.
    transports = {"socket", "ssl", "urllib", "http", "requests", "httpx", "asyncio", "select"}
    for module_path in sorted(package.glob("_lpm_*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(transports), (module_path.name, sorted(imported & transports))

    # And the endpoint itself appears exactly once in the family: in the adapter that
    # DESCRIBES the request, never in one that could send it.
    naming = [
        path.name
        for path in sorted(package.glob("_lpm_*.py"))
        if "api.anthropic.com" in path.read_text(encoding="utf-8")
    ]
    assert naming == ["_lpm_anthropic.py"]
