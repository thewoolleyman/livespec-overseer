"""A structurally valid out-of-bound request is refused without reaching a performer.

The browser-control boundary owns every semantic, cumulative-step and repetition
bound. The proxy returns that boundary's exact refused result, keeps serving after
an ordinary refusal, and ends the invocation with step-limit once the boundary
imposes one.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

_REFUSED = {"version": 1, "status": "refused"}
_OK = {"version": 1, "status": "ok"}
_OUT_OF_BOUND_CALLS: tuple[tuple[str, dict[str, object]], ...] = (
    ("navigate-browser", {"url": "http://claude.com"}),
    ("navigate-browser", {"url": "https://claude.com.evil.test"}),
    ("navigate-browser", {"url": "https://user@claude.com"}),
    ("click-browser", {"element_handle": ""}),
    ("type-browser-text", {"text": "", "element_handle": "element:1"}),
    ("type-browser-text", {"text": "x" * 4097, "element_handle": "element:1"}),
    ("type-browser-text", {"text": "holds concealed inside", "element_handle": "element:1"}),
    ("select-browser", {"value": "sk-ant-oat01-secret", "element_handle": "element:1"}),
    ("scroll-browser", {"direction": "sideways", "pixels": 1}),
    ("scroll-browser", {"direction": "down", "pixels": 10_001}),
    ("wait-browser", {"seconds": 0}),
    ("send-terminal-line", {"text": "concealed"}),
    ("send-terminal-handle", {"source_handle": "[[redacted-sensitive]]"}),
    ("wait-terminal", {"seconds": 31}),
    ("type-login-material", {"field": "password", "element_handle": "element:1"}),
    ("capture-token", {"source_handle": "browser:not-a-uuid"}),
    ("discard-capture", {"capture_handle": ""}),
)


class _Channel:
    def __init__(self, *, inbound: bytes) -> None:
        self.inbound = inbound
        self.offset = 0
        self.sent: list[bytes] = []
        self.closed = False

    def receive(self, *, count: int, timeout_seconds: float) -> bytes | None:
        assert timeout_seconds > 0
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
        return dict(_OK)

    def shutdown(self) -> None:
        return None


def _results(*, channel: _Channel) -> list[dict[str, object]]:
    decoded: list[dict[str, object]] = []
    for frame in channel.sent:
        parsed: dict[str, object] = json.loads(frame[4:].decode("utf-8"))
        decoded.append(parsed)
    return decoded


def _served(
    *, proxy_module: ModuleType, inbound: bytes, step_limit: int
) -> tuple[object, _Channel, _Performers]:
    channel = _Channel(inbound=inbound)
    performers = _Performers()
    outcome = proxy_module.private_acquisition_proxy(
        channel=channel,
        performers=performers,
        bounds=proxy_module.ExecutionBounds(
            step_limit=step_limit,
            allowed_origins=frozenset({"https://claude.com"}),
            tainted_values=frozenset({"concealed"}),
        ),
        worker_deadline=1_000.0,
        clock=lambda: 0.0,
    ).serve()
    return outcome, channel, performers


def _inbound(*, requests: ModuleType, calls: tuple[tuple[str, dict[str, object]], ...]) -> bytes:
    return b"".join(requests.frame_for(tool=tool, arguments=arguments) for tool, arguments in calls)


def _assert_a_semantic_refusal_never_reaches_a_performer_and_keeps_serving(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    allowed = ("wait-browser", {"seconds": 1})
    outcome, channel, performers = _served(
        proxy_module=proxy_module,
        inbound=_inbound(requests=requests, calls=(*_OUT_OF_BOUND_CALLS, allowed)),
        step_limit=len(_OUT_OF_BOUND_CALLS) + 1,
    )

    assert performers.actions == [allowed], (
        "no out-of-bound request may reach a performer, and the loop must keep serving "
        f"after one, but the performer saw {performers.actions}"
    )
    assert _results(channel=channel) == [*([_REFUSED] * len(_OUT_OF_BOUND_CALLS)), _OK]
    assert outcome.consumed_steps == len(_OUT_OF_BOUND_CALLS) + 1
    assert outcome.stop_reason == "flow-unavailable"


def _assert_the_cumulative_step_bound_ends_the_invocation(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    outcome, channel, performers = _served(
        proxy_module=proxy_module,
        inbound=_inbound(
            requests=requests,
            calls=(
                ("wait-browser", {"seconds": 1}),
                ("wait-terminal", {"seconds": 1}),
                ("observe-browser", {}),
            ),
        ),
        step_limit=2,
    )

    assert len(performers.actions) == 2
    assert _results(channel=channel) == [_OK, _OK, _REFUSED]
    assert outcome.consumed_steps == 2, "a request arriving with no step left is not an invocation"
    assert outcome.stop_reason == "step-limit"


def _assert_the_repetition_bound_ends_the_invocation(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    repeated = ("navigate-browser", {"url": "https://claude.com/settings"})
    outcome, channel, performers = _served(
        proxy_module=proxy_module,
        inbound=_inbound(requests=requests, calls=(repeated,) * 5),
        step_limit=10,
    )

    assert performers.actions == [repeated] * 3, "the fourth identical mutation runs no action"
    assert _results(channel=channel) == [_OK, _OK, _OK, _REFUSED]
    assert outcome.consumed_steps == 4, "the refused fourth call still consumes its one step"
    assert outcome.stop_reason == "step-limit"
    assert channel.closed is True


def test_an_out_of_bound_request_is_refused_without_a_performer_call() -> None:
    proxy_module = importlib.import_module("_lpm_acquisition_proxy")
    requests = importlib.import_module("_lpm_browser_requests")
    assert (
        Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_proxy.py"
    ).is_file(), "the private acquisition proxy service loop must be implemented"

    _assert_a_semantic_refusal_never_reaches_a_performer_and_keeps_serving(
        proxy_module=proxy_module, requests=requests
    )
    _assert_the_cumulative_step_bound_ends_the_invocation(
        proxy_module=proxy_module, requests=requests
    )
    _assert_the_repetition_bound_ends_the_invocation(proxy_module=proxy_module, requests=requests)
