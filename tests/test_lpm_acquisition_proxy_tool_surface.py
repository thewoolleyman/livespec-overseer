"""The private acquisition proxy serves exactly the seventeen private execution tools.

The private channel and the browser and terminal performers are injected ports, so
this exercises the service loop against doubles for both; the concrete performers
and the real channel adapter are separate work items.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

_EXPECTED_TOOLS = (
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
_VALID_CALLS: tuple[tuple[str, dict[str, object]], ...] = (
    ("observe-browser", {}),
    ("navigate-browser", {"url": "https://claude.com/settings"}),
    ("click-browser", {"element_handle": "element:1"}),
    ("type-browser-text", {"text": "visible", "element_handle": "element:1"}),
    ("select-browser", {"value": "choice", "element_handle": "element:1"}),
    ("scroll-browser", {"direction": "down", "pixels": 120}),
    ("wait-browser", {"seconds": 1}),
    ("start-terminal", {}),
    ("observe-terminal", {}),
    ("send-terminal-line", {"text": "visible"}),
    ("send-terminal-handle", {"source_handle": "browser:123e4567-e89b-12d3-a456-426614174000"}),
    ("wait-terminal", {"seconds": 1}),
    ("terminate-terminal", {}),
    ("type-login-material", {"field": "login_identifier", "element_handle": "element:1"}),
    ("apply-mailbox-verification", {"element_handle": "element:1"}),
    ("capture-token", {"source_handle": "terminal:123e4567-e89b-12d3-a456-426614174000"}),
    ("discard-capture", {"capture_handle": "capture:1"}),
)


class _Channel:
    def __init__(self, *, inbound: bytes) -> None:
        self.inbound = inbound
        self.offset = 0
        self.sent: list[bytes] = []
        self.timeouts: list[float] = []
        self.closed = False

    def receive(self, *, count: int, timeout_seconds: float) -> bytes | None:
        self.timeouts.append(timeout_seconds)
        chunk = self.inbound[self.offset : self.offset + count]
        if len(chunk) != count:
            return None
        self.offset += count
        return chunk

    def send(self, *, frame: bytes) -> bool:
        self.sent.append(frame)
        return True

    def close(self) -> None:
        self.closed = True


class _Performers:
    def __init__(self) -> None:
        self.actions: list[tuple[str, dict[str, object]]] = []

    def perform(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        self.actions.append((tool, arguments))
        return {"version": 1, "status": "ok"}

    def shutdown(self) -> None:
        return None


def _results(*, channel: _Channel) -> list[dict[str, object]]:
    decoded: list[dict[str, object]] = []
    for frame in channel.sent:
        declared = int.from_bytes(frame[:4], "big")
        assert declared == len(frame[4:])
        parsed: dict[str, object] = json.loads(frame[4:].decode("utf-8"))
        decoded.append(parsed)
    return decoded


def _proxy_over(
    *,
    proxy_module: ModuleType,
    channel: _Channel,
    performers: _Performers,
    clock: object = None,
) -> object:
    return proxy_module.private_acquisition_proxy(
        channel=channel,
        performers=performers,
        bounds=proxy_module.ExecutionBounds(
            step_limit=len(_VALID_CALLS) + 1,
            allowed_origins=frozenset({"https://claude.com"}),
            tainted_values=frozenset({"concealed"}),
        ),
        worker_deadline=1_000.0,
        clock=clock if clock is not None else (lambda: 0.0),
    )


def _assert_every_registered_tool_reaches_its_performer(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    channel = _Channel(
        inbound=b"".join(
            requests.frame_for(tool=tool, arguments=arguments) for tool, arguments in _VALID_CALLS
        )
    )
    performers = _Performers()
    outcome = _proxy_over(proxy_module=proxy_module, channel=channel, performers=performers).serve()

    assert performers.actions == list(_VALID_CALLS)
    assert _results(channel=channel) == [{"version": 1, "status": "ok"}] * len(_VALID_CALLS)
    assert outcome.stop_reason == "flow-unavailable"
    assert outcome.consumed_steps == len(_VALID_CALLS)
    assert channel.timeouts == [1_000.0] * (2 * len(_VALID_CALLS) + 1)


def _assert_an_unregistered_tool_name_never_reaches_a_performer(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    channel = _Channel(inbound=requests.frame_for(tool="evaluate-javascript", arguments={}))
    performers = _Performers()
    outcome = _proxy_over(proxy_module=proxy_module, channel=channel, performers=performers).serve()

    assert performers.actions == []
    assert channel.sent == []
    assert outcome.stop_reason == "flow-unavailable"
    assert outcome.consumed_steps == 0


def _assert_a_truncated_frame_ends_the_loop(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    channel = _Channel(
        inbound=requests.frame_for(tool="wait-browser", arguments={"seconds": 1})[:-1]
    )
    performers = _Performers()
    outcome = _proxy_over(proxy_module=proxy_module, channel=channel, performers=performers).serve()

    assert performers.actions == []
    assert channel.sent == []
    assert outcome.stop_reason == "flow-unavailable"


def _assert_a_spent_worker_deadline_reads_no_frame(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    channel = _Channel(inbound=requests.frame_for(tool="wait-browser", arguments={"seconds": 1}))
    performers = _Performers()
    outcome = _proxy_over(
        proxy_module=proxy_module,
        channel=channel,
        performers=performers,
        clock=lambda: 1_000.0,
    ).serve()

    assert channel.timeouts == []
    assert performers.actions == []
    assert outcome.stop_reason == "flow-unavailable"


def test_the_private_proxy_exposes_exactly_the_seventeen_private_execution_tools() -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_proxy.py"
    assert module_path.is_file(), "the private acquisition proxy service loop must be implemented"
    proxy_module = importlib.import_module("_lpm_acquisition_proxy")
    requests = importlib.import_module("_lpm_browser_requests")

    assert len(_EXPECTED_TOOLS) == 17
    assert proxy_module.PRIVATE_EXECUTION_TOOLS == _EXPECTED_TOOLS

    _assert_every_registered_tool_reaches_its_performer(
        proxy_module=proxy_module, requests=requests
    )
    _assert_an_unregistered_tool_name_never_reaches_a_performer(
        proxy_module=proxy_module, requests=requests
    )
    _assert_a_truncated_frame_ends_the_loop(proxy_module=proxy_module, requests=requests)
    _assert_a_spent_worker_deadline_reads_no_frame(proxy_module=proxy_module, requests=requests)
