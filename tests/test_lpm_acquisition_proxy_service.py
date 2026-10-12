"""The acquisition proxy exposes one closed MCP tool surface over its private port."""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import cast

_TOOLS = (
    "observe-browser",
    "navigate-browser",
    "click-browser",
    "type-browser-text",
    "select-browser",
    "scroll-browser",
    "wait-browser",
    "start-terminal",
    "observe-terminal",
    "send-terminal-line",
    "send-terminal-handle",
    "wait-terminal",
    "terminate-terminal",
    "type-login-material",
    "apply-mailbox-verification",
    "capture-token",
    "discard-capture",
)


class _Exchange:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.running = False
        self.stop_calls = 0

    def __call__(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((tool, arguments))
        if tool == "start-terminal":
            self.running = True
        return {"version": 1, "status": "ok"}

    def stop(self) -> None:
        self.running = False
        self.stop_calls += 1


class _RawPerformer:
    def __init__(self, *, result: dict[str, object]) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.stop_calls = 0

    def __call__(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((tool, arguments))
        return self.result

    def stop(self) -> None:
        self.stop_calls += 1


class _Clock:
    def __init__(self, *, value: float) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class _Channel:
    def __init__(self, *, frames: list[bytes | None]) -> None:
        self.frames = frames
        self.responses: list[bytes] = []
        self.closed = False

    def receive(self, *, deadline: float) -> bytes | None:
        assert deadline > 0
        return self.frames.pop(0)

    def send(self, *, frame: bytes, deadline: float) -> None:
        assert deadline > 0
        self.responses.append(frame)

    def close(self) -> None:
        self.closed = True


def _assert_redacted(*, result: dict[str, object], token: str, sensitive: str, source: str) -> None:
    assert token not in repr(result)
    assert sensitive not in repr(result)
    assert result["status"] == "ok"
    assert "[[redacted-sensitive]]" in repr(result)
    assert re.search(rf"\[\[redacted-token:{source}:[0-9a-f-]{{36}}\]\]", repr(result))


def test_private_proxy_executable_exposes_only_the_seventeen_registered_tools() -> None:
    root = Path(__file__).parents[1]
    module_path = root / "overseer" / "_lpm_acquisition_proxy.py"
    executable = root / ".claude-plugin" / "bin" / "lpm-acquisition-proxy"
    assert module_path.is_file(), "the private acquisition proxy service must exist"
    proxy = importlib.import_module("_lpm_acquisition_proxy")
    exchange = _Exchange()
    service = proxy.AcquisitionProxy(exchange=exchange)

    listed = service.handle(
        message={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    )
    assert tuple(tool["name"] for tool in listed["result"]["tools"]) == _TOOLS

    refused = service.handle(
        message={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "read-file", "arguments": {}},
        }
    )
    assert refused == {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [{"type": "text", "text": '{"status":"refused","version":1}'}],
            "isError": False,
        },
    }
    assert exchange.calls == []
    assert executable.is_file()
    assert executable.stat().st_mode & 0o111


def test_malformed_private_frame_closes_without_result_action_or_step() -> None:
    root = Path(__file__).parents[1]
    module_path = root / "overseer" / "_lpm_acquisition_service.py"
    assert module_path.is_file(), "the private framed service loop must exist"
    service_module = importlib.import_module("_lpm_acquisition_service")
    performer = _Exchange()
    service = service_module.AcquisitionProxyService(
        step_limit=5,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=performer,
    )
    channel = _Channel(frames=[b"\x00\x00\x00\x00"])

    outcome = service.run(channel=channel, deadline=float("inf"))

    assert outcome == service_module.ServiceOutcome(
        status="failed", failure_reason="flow-unavailable"
    )
    assert channel.responses == []
    assert channel.closed is True
    assert performer.calls == []
    assert service.consumed_steps == 0


def test_valid_out_of_bounds_requests_return_refused_without_performer_action() -> None:
    service_module = importlib.import_module("_lpm_acquisition_service")
    control_module = importlib.import_module("_lpm_browser_control")
    refused_payload = b'{"status":"refused","version":1}'
    refused_frame = len(refused_payload).to_bytes(4, "big") + refused_payload
    ok_payload = b'{"status":"ok","version":1}'
    ok_frame = len(ok_payload).to_bytes(4, "big") + ok_payload

    semantic_performer = _Exchange()
    semantic = service_module.AcquisitionProxyService(
        step_limit=5,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=semantic_performer,
    )
    semantic_channel = _Channel(
        frames=[
            control_module.frame_for(tool="wait-browser", arguments={"seconds": 31}),
            None,
        ]
    )
    assert semantic.run(channel=semantic_channel, deadline=float("inf")) == (
        service_module.ServiceOutcome(status="stopped", failure_reason=None)
    )
    assert semantic_channel.responses == [refused_frame]
    assert semantic_performer.calls == []
    assert semantic.consumed_steps == 1

    budget_performer = _Exchange()
    budget = service_module.AcquisitionProxyService(
        step_limit=0,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=budget_performer,
    )
    budget_channel = _Channel(
        frames=[control_module.frame_for(tool="wait-browser", arguments={"seconds": 1})]
    )
    assert budget.run(channel=budget_channel, deadline=float("inf")) == (
        service_module.ServiceOutcome(status="failed", failure_reason="step-limit")
    )
    assert budget_channel.responses == [refused_frame]
    assert budget_performer.calls == []
    assert budget.consumed_steps == 0

    repeated_performer = _Exchange()
    repeated = service_module.AcquisitionProxyService(
        step_limit=5,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=repeated_performer,
    )
    repeated_request = control_module.frame_for(
        tool="navigate-browser", arguments={"url": "https://claude.com/setup"}
    )
    repeated_channel = _Channel(frames=[repeated_request] * 4)
    assert repeated.run(channel=repeated_channel, deadline=float("inf")) == (
        service_module.ServiceOutcome(status="failed", failure_reason="step-limit")
    )
    assert repeated_channel.responses == [ok_frame, ok_frame, ok_frame, refused_frame]
    assert (
        repeated_performer.calls
        == [
            ("navigate-browser", {"url": "https://claude.com/setup"}),
        ]
        * 3
    )
    assert repeated.consumed_steps == 4


def test_performer_observations_are_sanitized_and_masking_failure_is_unavailable() -> None:
    service_module = importlib.import_module("_lpm_acquisition_service")
    control_module = importlib.import_module("_lpm_browser_control")
    token = "sk-ant-oat01-secret-token"
    sensitive = "person@example.com"

    terminal_performer = _RawPerformer(
        result={
            "running": False,
            "exit_status": 0,
            "stdout": f"captured {token}",
            "stderr": sensitive,
        }
    )
    terminal = service_module.AcquisitionProxyService(
        step_limit=5,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset({sensitive}),
        perform=terminal_performer,
    )
    terminal_channel = _Channel(
        frames=[control_module.frame_for(tool="observe-terminal", arguments={}), None]
    )
    assert terminal.run(channel=terminal_channel, deadline=float("inf")) == (
        service_module.ServiceOutcome(status="stopped", failure_reason=None)
    )
    terminal_result = cast("dict[str, object]", json.loads(terminal_channel.responses[0][4:]))
    _assert_redacted(result=terminal_result, token=token, sensitive=sensitive, source="terminal")

    browser_performer = _RawPerformer(
        result={
            "url": f"https://claude.com/{token}",
            "title": sensitive,
            "dom_text": f"token: {token}",
            "accessibility_tree": f"account: {sensitive}",
            "masked_screenshot_png": b"masked-png",
            "masking_established": True,
        }
    )
    browser = service_module.AcquisitionProxyService(
        step_limit=5,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset({sensitive}),
        perform=browser_performer,
    )
    browser_channel = _Channel(
        frames=[control_module.frame_for(tool="observe-browser", arguments={}), None]
    )
    assert browser.run(channel=browser_channel, deadline=float("inf")) == (
        service_module.ServiceOutcome(status="stopped", failure_reason=None)
    )
    browser_result = cast("dict[str, object]", json.loads(browser_channel.responses[0][4:]))
    _assert_redacted(result=browser_result, token=token, sensitive=sensitive, source="browser")
    assert browser_result["screenshot_png"] == "bWFza2VkLXBuZw=="
    assert re.fullmatch(r"[0-9a-f]{64}", cast("str", browser_result["state_fingerprint"]))

    unmasked_performer = _RawPerformer(
        result={
            "url": "https://claude.com",
            "title": "Login",
            "dom_text": "secret field",
            "accessibility_tree": "secret field",
            "masked_screenshot_png": b"untrusted",
            "masking_established": False,
        }
    )
    unmasked = service_module.AcquisitionProxyService(
        step_limit=5,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=unmasked_performer,
    )
    unmasked_channel = _Channel(
        frames=[control_module.frame_for(tool="observe-browser", arguments={})]
    )
    assert unmasked.run(channel=unmasked_channel, deadline=float("inf")) == (
        service_module.ServiceOutcome(status="failed", failure_reason="flow-unavailable")
    )
    unavailable_payload = b'{"status":"unavailable","version":1}'
    assert unmasked_channel.responses == [
        len(unavailable_payload).to_bytes(4, "big") + unavailable_payload
    ]


def test_service_stops_at_channel_or_deadline_and_reaps_started_performer() -> None:
    service_module = importlib.import_module("_lpm_acquisition_service")
    control_module = importlib.import_module("_lpm_browser_control")

    performer = _Exchange()
    service = service_module.AcquisitionProxyService(
        step_limit=5,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=performer,
    )
    channel = _Channel(frames=[control_module.frame_for(tool="start-terminal", arguments={}), None])
    assert service.run(channel=channel, deadline=float("inf")) == (
        service_module.ServiceOutcome(status="stopped", failure_reason=None)
    )
    assert performer.running is False
    assert performer.stop_calls == 1
    assert channel.closed is True

    deadline_performer = _Exchange()
    deadline_service = service_module.AcquisitionProxyService(
        step_limit=5,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=deadline_performer,
        now=_Clock(value=100.0),
    )
    deadline_channel = _Channel(frames=[None])
    assert deadline_service.run(channel=deadline_channel, deadline=100.0) == (
        service_module.ServiceOutcome(status="failed", failure_reason="flow-unavailable")
    )
    assert deadline_performer.calls == []
    assert deadline_performer.stop_calls == 1
    assert deadline_channel.closed is True

    proxy_module = importlib.import_module("_lpm_acquisition_proxy")
    proxy_exchange = _Exchange()
    proxy = proxy_module.AcquisitionProxy(exchange=proxy_exchange)
    forwarded = proxy.handle(
        message={
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "start-terminal", "arguments": {}},
        }
    )
    assert forwarded["result"] == {
        "content": [{"type": "text", "text": '{"status":"ok","version":1}'}],
        "isError": False,
    }
    assert proxy_exchange.calls == [("start-terminal", {})]
