"""The private browser boundary fails malformed input closed and bounds valid calls."""

from __future__ import annotations

import importlib
from pathlib import Path


def _assert_malformed_frames(*, control, perform):
    malformed = (
        b"",
        b"\x00\x00\x00\x00",
        b"\x00\x00\x00\x05{}",
        b'\x00\x00\x00;{"version": 1,"tool":"wait-browser","arguments":{"seconds":1}}',
        control.frame_for(tool="unregistered", arguments={}),
        control.frame_for(tool="wait-browser", arguments={"seconds": 1, "extra": 2}),
    )
    for frame in malformed:
        boundary = control.BrowserControl(
            remaining_steps=6,
            allowed_origins=frozenset({"https://claude.com"}),
            tainted_values=frozenset({"concealed"}),
            perform=perform,
        )
        outcome = boundary.dispatch(frame=frame)
        assert outcome.close_channel is True
        assert outcome.response is None
        assert outcome.stop_reason == "flow-unavailable"
        assert boundary.consumed_steps == 0


def _assert_semantic_refusals(*, control, perform):
    invalid_calls = (
        ("navigate-browser", {"url": "http://claude.com"}),
        ("navigate-browser", {"url": "https://example.com"}),
        ("type-browser-text", {"text": "", "element_handle": "element:1"}),
        ("select-browser", {"value": "concealed", "element_handle": "element:1"}),
        ("scroll-browser", {"direction": "sideways", "pixels": 1}),
        ("scroll-browser", {"direction": "down", "pixels": 10001}),
        ("wait-browser", {"seconds": 0}),
        ("send-terminal-line", {"text": "concealed"}),
        ("wait-terminal", {"seconds": 31}),
        ("type-login-material", {"field": "password", "element_handle": "element:1"}),
    )
    boundary = control.BrowserControl(
        remaining_steps=len(invalid_calls),
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset({"concealed"}),
        perform=perform,
    )
    for tool, arguments in invalid_calls:
        outcome = boundary.dispatch(frame=control.frame_for(tool=tool, arguments=arguments))
        assert outcome.response == {"version": 1, "status": "refused"}
        assert outcome.close_channel is False
    assert boundary.consumed_steps == len(invalid_calls)
    assert perform.actions == []


def _assert_repetition_and_exhaustion(*, control, perform):
    boundary = control.BrowserControl(
        remaining_steps=5,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=perform,
    )
    mutation = control.frame_for(
        tool="navigate-browser", arguments={"url": "https://claude.com/settings"}
    )
    for _ in range(3):
        outcome = boundary.dispatch(frame=mutation)
        assert outcome.response == {"version": 1, "status": "ok"}
        assert outcome.stop_reason is None
    repeated = boundary.dispatch(frame=mutation)
    assert repeated.response == {"version": 1, "status": "refused"}
    assert repeated.stop_reason == "step-limit"
    assert boundary.consumed_steps == 4
    assert len(perform.actions) == 3

    exhausted = control.BrowserControl(
        remaining_steps=0,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=perform,
    )
    stopped = exhausted.dispatch(
        frame=control.frame_for(tool="wait-browser", arguments={"seconds": 1})
    )
    assert stopped.response == {"version": 1, "status": "refused"}
    assert stopped.stop_reason == "step-limit"
    assert exhausted.consumed_steps == 0


class _Performer:
    def __init__(self):
        self.actions: list[tuple[str, dict[str, object]]] = []

    def __call__(self, *, tool, arguments):
        self.actions.append((tool, arguments))
        return {"version": 1, "status": "ok"}


def test_browser_control_rejects_frames_and_enforces_cumulative_guards():
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_browser_control.py"
    assert module_path.is_file(), "the private browser-control boundary must be implemented"
    control = importlib.import_module("_lpm_browser_control")
    perform = _Performer()

    _assert_malformed_frames(control=control, perform=perform)
    _assert_semantic_refusals(control=control, perform=perform)
    _assert_repetition_and_exhaustion(control=control, perform=perform)
