"""The acquisition proxy exposes one closed MCP tool surface over its private port."""

from __future__ import annotations

import importlib
import json
import re
import runpy
import sys
import types
from pathlib import Path
from typing import Protocol, cast

import pytest

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


class _ExecutableExchange(Protocol):
    def __call__(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]: ...


class _ExecutableExchangeFactory(Protocol):
    def __call__(self, *, channel: object, frame_for: object) -> _ExecutableExchange: ...


class _ExecutableBoundaryChannel:
    """Drive one executable exchange through the framed service synchronously."""

    def __init__(self, *, service: object) -> None:
        self.service = service
        self.pending = bytearray()
        self.service_channel: _Channel | None = None
        self.outcome: object | None = None
        self.closed = False

    def sendall(self, frame: bytes) -> None:
        service_channel = _Channel(frames=[frame, None])
        self.service_channel = service_channel
        self.outcome = self.service.run(channel=service_channel, deadline=float("inf"))
        for response in service_channel.responses:
            self.pending.extend(response)

    def recv(self, size: int) -> bytes:
        received = bytes(self.pending[:size])
        del self.pending[:size]
        return received

    def close(self) -> None:
        self.closed = True


class _DescriptorChannel:
    def __init__(self, *, family: int, channel_type: int) -> None:
        self.family = family
        self.type = channel_type
        self.closed = False
        self.peer_reads = 0

    def getpeername(self) -> str:
        self.peer_reads += 1
        return "private-peer"

    def close(self) -> None:
        self.closed = True


class _SocketModule:
    AF_UNIX = 1
    SOCK_STREAM = 1

    def __init__(self, *, channel: _DescriptorChannel) -> None:
        self.channel = channel

    def socket(self, *, fileno: int) -> _DescriptorChannel:
        assert fileno == 3
        return self.channel


class _FakeOS:
    def __init__(self, *, environ: dict[str, str], close_fails: bool = False) -> None:
        self.environ = environ
        self.close_fails = close_fails
        self.closed: list[int] = []

    def close(self, descriptor: int) -> None:
        self.closed.append(descriptor)
        if self.close_fails:
            raise OSError("already closed")


class _Stdin:
    def __init__(self, *, lines: list[bytes]) -> None:
        self.buffer = lines


class _CloseFailingChannel(_Channel):
    def close(self) -> None:
        super().close()
        raise OSError("channel close failed")


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


def test_executable_boundary_accepts_sanitized_canonical_text_and_closes_on_bad_result() -> None:
    root = Path(__file__).parents[1]
    executable = root / ".claude-plugin" / "bin" / "lpm-acquisition-proxy"
    executable_members = runpy.run_path(str(executable), run_name="lpm_acquisition_proxy_test")
    exchange_factory = cast("_ExecutableExchangeFactory", executable_members["_ChannelExchange"])
    service_module = importlib.import_module("_lpm_acquisition_service")
    control_module = importlib.import_module("_lpm_browser_control")
    proxy_module = importlib.import_module("_lpm_acquisition_proxy")

    observation_performer = _RawPerformer(
        result={
            "running": False,
            "exit_status": 0,
            "stdout": "line one\nDéjà vu",
            "stderr": "",
        }
    )
    observation_service = service_module.AcquisitionProxyService(
        step_limit=1,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=observation_performer,
    )
    observation_channel = _ExecutableBoundaryChannel(service=observation_service)
    observation_proxy = proxy_module.AcquisitionProxy(
        exchange=exchange_factory(
            channel=observation_channel,
            frame_for=control_module.frame_for,
        )
    )

    observed = observation_proxy.handle(
        message={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "observe-terminal", "arguments": {}},
        }
    )
    content = cast("list[dict[str, object]]", observed["result"]["content"])
    assert json.loads(cast("str", content[0]["text"])) == {
        "version": 1,
        "status": "ok",
        "running": False,
        "exit_status": 0,
        "stdout": "line one\nDéjà vu",
        "stderr": "",
    }
    assert observation_performer.stop_calls == 1

    secret = "must-not-cross-the-proxy"
    malformed_performer = _RawPerformer(
        result={"version": 1, "status": "ok", "leaked_token": secret}
    )
    malformed_service = service_module.AcquisitionProxyService(
        step_limit=1,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset({secret}),
        perform=malformed_performer,
    )
    malformed_channel = _ExecutableBoundaryChannel(service=malformed_service)
    malformed_proxy = proxy_module.AcquisitionProxy(
        exchange=exchange_factory(
            channel=malformed_channel,
            frame_for=control_module.frame_for,
        )
    )

    with pytest.raises(ConnectionError):
        malformed_proxy.handle(
            message={
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "start-terminal", "arguments": {}},
            }
        )
    assert malformed_channel.service_channel is not None
    assert malformed_channel.service_channel.responses == []
    assert malformed_channel.outcome == service_module.ServiceOutcome(
        status="failed", failure_reason="flow-unavailable"
    )
    assert secret not in repr(malformed_channel.service_channel.responses)
    assert malformed_performer.stop_calls == 1


def test_channel_close_failure_still_reaps_the_performer() -> None:
    service_module = importlib.import_module("_lpm_acquisition_service")
    control_module = importlib.import_module("_lpm_browser_control")
    performer = _Exchange()
    service = service_module.AcquisitionProxyService(
        step_limit=1,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=performer,
    )
    channel = _CloseFailingChannel(
        frames=[control_module.frame_for(tool="start-terminal", arguments={}), None]
    )

    with pytest.raises(OSError, match="channel close failed"):
        service.run(channel=channel, deadline=float("inf"))

    assert channel.closed is True
    assert performer.running is False
    assert performer.stop_calls == 1


@pytest.mark.parametrize(
    ("tool", "arguments", "result", "expected"),
    [
        ("start-terminal", {}, {"version": 2, "status": "ok"}, None),
        ("start-terminal", {}, {"version": True, "status": "ok"}, None),
        ("start-terminal", {}, {"version": 1, "status": 1}, None),
        (
            "start-terminal",
            {},
            {"version": 1, "status": "refused"},
            {"version": 1, "status": "refused"},
        ),
        (
            "start-terminal",
            {},
            {"version": 1, "status": "unavailable"},
            {"version": 1, "status": "unavailable"},
        ),
        ("start-terminal", {}, {"version": 1, "status": "captured"}, None),
        (
            "apply-mailbox-verification",
            {"element_handle": "element:1"},
            {"version": 1, "status": "applied"},
            {"version": 1, "status": "applied"},
        ),
        (
            "apply-mailbox-verification",
            {"element_handle": "element:1"},
            {"version": 1, "status": "not-found"},
            {"version": 1, "status": "not-found"},
        ),
        (
            "apply-mailbox-verification",
            {"element_handle": "element:1"},
            {"version": 1, "status": "ok"},
            None,
        ),
        (
            "capture-token",
            {"source_handle": "browser:123e4567-e89b-42d3-a456-426614174000"},
            {"version": 1, "status": "captured", "capture_handle": "capture:opaque"},
            {"version": 1, "status": "captured", "capture_handle": "capture:opaque"},
        ),
        (
            "capture-token",
            {"source_handle": "browser:123e4567-e89b-42d3-a456-426614174000"},
            {"version": 1, "status": "captured", "capture_handle": ""},
            None,
        ),
    ],
)
def test_non_observation_results_have_exact_per_tool_shapes(
    *,
    tool: str,
    arguments: dict[str, object],
    result: dict[str, object],
    expected: dict[str, object] | None,
) -> None:
    service_module = importlib.import_module("_lpm_acquisition_service")
    control_module = importlib.import_module("_lpm_browser_control")
    performer = _RawPerformer(result=result)
    service = service_module.AcquisitionProxyService(
        step_limit=1,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=performer,
    )
    channel = _Channel(frames=[control_module.frame_for(tool=tool, arguments=arguments), None])

    outcome = service.run(channel=channel, deadline=float("inf"))

    if expected is None:
        assert channel.responses == []
        assert outcome == service_module.ServiceOutcome(
            status="failed", failure_reason="flow-unavailable"
        )
    else:
        assert json.loads(channel.responses[0][4:]) == expected
    assert performer.calls == [(tool, arguments)]
    assert performer.stop_calls == 1


def _executable_function(*, name: str, run_name: str) -> types.FunctionType:
    executable = Path(__file__).parents[1] / ".claude-plugin" / "bin" / "lpm-acquisition-proxy"
    members = runpy.run_path(str(executable), run_name=run_name)
    return cast(types.FunctionType, members[name])


def test_executable_main_scrubs_startup_and_handles_cli_modes(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    main = _executable_function(name="main", run_name="lpm_proxy_cli_test")
    members = main.__globals__

    inherited = {
        "PATH": "/usr/bin",
        "CLAUDECODE": "secret",
        "anthropic_api_key": "secret",
        "op_service_account_token": "secret",
        "lpm_value_reader_op_service_account_token": "secret",
    }
    refused_os = _FakeOS(environ=inherited, close_fails=True)
    members["os"] = refused_os
    monkeypatch.setattr(sys, "argv", ["lpm-acquisition-proxy"])
    assert main() == 1
    assert inherited == {"PATH": "/usr/bin"}
    assert refused_os.closed == [3]

    members["os"] = _FakeOS(environ={})
    monkeypatch.setattr(sys, "argv", ["lpm-acquisition-proxy", "--help"])
    assert main() == 0
    assert capsys.readouterr().out == "usage: lpm-acquisition-proxy\n"

    monkeypatch.setattr(sys, "argv", ["lpm-acquisition-proxy", "unexpected"])
    assert main() == 2


def test_executable_main_serves_initialization_notification_and_tool_call(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    main = _executable_function(name="main", run_name="lpm_proxy_serving_test")
    members = main.__globals__
    members["os"] = _FakeOS(environ={})
    service_module = importlib.import_module("_lpm_acquisition_service")
    performer = _RawPerformer(
        result={
            "running": False,
            "exit_status": 0,
            "stdout": "safe",
            "stderr": "",
        }
    )
    service = service_module.AcquisitionProxyService(
        step_limit=1,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=performer,
    )
    channel = _ExecutableBoundaryChannel(service=service)
    members["_open_channel"] = lambda: channel
    monkeypatch.setattr(
        sys,
        "stdin",
        _Stdin(
            lines=[
                b'{"jsonrpc":"2.0","id":1,"method":"initialize",'
                b'"params":{"protocolVersion":"test-version"}}\n',
                b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n',
                b'{"jsonrpc":"2.0","id":2,"method":"tools/call",'
                b'"params":{"name":"observe-terminal","arguments":{}}}\n',
            ]
        ),
    )
    monkeypatch.setattr(sys, "argv", ["lpm-acquisition-proxy"])
    monkeypatch.setattr(sys, "path", [*sys.path])
    assert main() == 0
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert output[0]["result"]["protocolVersion"] == "test-version"
    assert json.loads(output[1]["result"]["content"][0]["text"])["stdout"] == "safe"
    assert channel.closed is True


@pytest.mark.parametrize("line", [b"{\n", b"[]\n"])
def test_executable_main_fails_closed_on_invalid_input(
    *, line: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    main = _executable_function(name="main", run_name="lpm_proxy_invalid_input_test")
    members = main.__globals__
    members["os"] = _FakeOS(environ={})
    malformed_channel = _Channel(frames=[])
    members["_open_channel"] = lambda: malformed_channel
    monkeypatch.setattr(sys, "stdin", _Stdin(lines=[line]))
    monkeypatch.setattr(sys, "argv", ["lpm-acquisition-proxy"])
    monkeypatch.setattr(sys, "path", [*sys.path])
    assert main() == 1
    assert malformed_channel.closed is True


def test_executable_descriptor_and_frame_guards() -> None:
    open_channel = _executable_function(name="_open_channel", run_name="lpm_proxy_guards_test")
    read_result = cast(types.FunctionType, open_channel.__globals__["_read_result"])
    members = open_channel.__globals__

    valid = _DescriptorChannel(family=_SocketModule.AF_UNIX, channel_type=_SocketModule.SOCK_STREAM)
    members["socket"] = _SocketModule(channel=valid)
    assert open_channel() is valid
    assert valid.peer_reads == 1

    invalid = _DescriptorChannel(family=999, channel_type=_SocketModule.SOCK_STREAM)
    members["socket"] = _SocketModule(channel=invalid)
    with pytest.raises(ValueError, match="private channel"):
        open_channel()
    assert invalid.closed is True

    invalid_frame = _ExecutableBoundaryChannel(service=object())
    invalid_frame.pending.extend(b"\x00\x00\x00\x00")
    with pytest.raises(ValueError, match="result frame"):
        read_result(channel=invalid_frame)

    noncanonical_payload = b'{"status":"ok", "version":1}'
    noncanonical = _ExecutableBoundaryChannel(service=object())
    noncanonical.pending.extend(len(noncanonical_payload).to_bytes(4, "big") + noncanonical_payload)
    with pytest.raises(ValueError, match="result frame"):
        read_result(channel=noncanonical)
