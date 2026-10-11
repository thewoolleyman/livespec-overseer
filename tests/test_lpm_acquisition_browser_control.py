"""The private browser boundary validates before action and bounds every valid call."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType


class _Performer:
    def __init__(self) -> None:
        self.actions: list[tuple[str, dict[str, object]]] = []

    def __call__(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        self.actions.append((tool, arguments))
        if tool == "observe-browser":
            return {"version": 1, "status": "ok", "state_fingerprint": "browser-2"}
        if tool == "observe-terminal":
            return {"version": 1, "status": "ok", "terminal_digest": "terminal-2"}
        return {"version": 1, "status": "ok"}


def _assert_malformed_frames(*, control: ModuleType, performed: _Performer) -> None:
    malformed_frames = (
        b"",
        b"\x00\x00\x00",
        b"\x00\x00\x00\x00",
        (16_777_217).to_bytes(4, "big") + b"{}",
        b"\x00\x00\x00\x05{}",
        b"\x00\x00\x00\x01\xff",
        b'\x00\x00\x00;{"version": 1,"tool":"wait-browser","arguments":{"seconds":1}}',
        control.frame_for(tool="unregistered", arguments={}),
        control.frame_for(tool="wait-browser", arguments={"seconds": True}),
        control.frame_for(tool="wait-browser", arguments={"seconds": 1, "extra": 2}),
    )
    for frame in malformed_frames:
        boundary = control.BrowserControl(
            step_limit=6,
            allowed_origins=frozenset({"https://claude.com"}),
            tainted_values=frozenset({"concealed"}),
            perform=performed,
        )
        outcome = boundary.dispatch(frame=frame)
        assert outcome.response is None
        assert outcome.close_channel is True
        assert outcome.stop_reason == "flow-unavailable"
        assert boundary.consumed_steps == 0
    assert performed.actions == []


def _assert_semantic_refusals(*, control: ModuleType, performed: _Performer) -> None:
    invalid_calls = (
        ("navigate-browser", {"url": "http://claude.com"}),
        ("navigate-browser", {"url": "https://claude.com.evil.test"}),
        ("navigate-browser", {"url": "https://user@claude.com"}),
        ("click-browser", {"element_handle": ""}),
        ("type-browser-text", {"text": "", "element_handle": "element:1"}),
        (
            "type-browser-text",
            {"text": "x" * 4097, "element_handle": "element:1"},
        ),
        (
            "type-browser-text",
            {"text": "prefix-concealed-suffix", "element_handle": "element:1"},
        ),
        (
            "select-browser",
            {"value": "sk-ant-oat01-secret", "element_handle": "element:1"},
        ),
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
    refusal_boundary = control.BrowserControl(
        step_limit=len(invalid_calls),
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset({"concealed"}),
        perform=performed,
    )
    for tool, arguments in invalid_calls:
        refused = refusal_boundary.dispatch(frame=control.frame_for(tool=tool, arguments=arguments))
        assert refused.response == {"version": 1, "status": "refused"}
        assert refused.close_channel is False
        assert refused.stop_reason is None
    assert refusal_boundary.consumed_steps == len(invalid_calls)
    assert performed.actions == []


def _assert_repetition_guard(*, control: ModuleType, performed: _Performer) -> None:
    boundary = control.BrowserControl(
        step_limit=10,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=performed,
    )
    mutation = control.frame_for(
        tool="navigate-browser", arguments={"url": "https://claude.com/settings"}
    )
    for _ in range(3):
        accepted = boundary.dispatch(frame=mutation)
        assert accepted.response == {"version": 1, "status": "ok"}
    observed_without_change = boundary.dispatch(
        frame=control.frame_for(tool="wait-browser", arguments={"seconds": 1})
    )
    assert observed_without_change.stop_reason is None
    repeated = boundary.dispatch(frame=mutation)
    assert repeated.response == {"version": 1, "status": "refused"}
    assert repeated.stop_reason == "step-limit"
    assert len(performed.actions) == 4

    observed_change = boundary.dispatch(
        frame=control.frame_for(tool="observe-browser", arguments={})
    )
    assert observed_change.response["state_fingerprint"] == "browser-2"
    reset = boundary.dispatch(frame=mutation)
    assert reset.response == {"version": 1, "status": "ok"}
    terminal_change = boundary.dispatch(
        frame=control.frame_for(tool="observe-terminal", arguments={})
    )
    assert terminal_change.response["terminal_digest"] == "terminal-2"
    assert boundary.consumed_steps == 8


def _assert_cumulative_limit(*, control: ModuleType, performed: _Performer) -> None:
    exhausted = control.BrowserControl(
        step_limit=1,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=performed,
    )
    first = exhausted.dispatch(
        frame=control.frame_for(tool="wait-terminal", arguments={"seconds": 1})
    )
    stopped = exhausted.dispatch(
        frame=control.frame_for(tool="wait-terminal", arguments={"seconds": 1})
    )
    assert first.response == {"version": 1, "status": "ok"}
    assert stopped.response == {"version": 1, "status": "refused"}
    assert stopped.stop_reason == "step-limit"
    assert exhausted.consumed_steps == 1


def test_browser_control_validates_before_action_and_enforces_every_bound() -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_browser_control.py"
    assert module_path.is_file(), "the private browser-control boundary must be implemented"
    control = importlib.import_module("_lpm_browser_control")
    performed = _Performer()

    _assert_malformed_frames(control=control, performed=performed)
    _assert_semantic_refusals(control=control, performed=performed)
    _assert_repetition_guard(control=control, performed=performed)
    _assert_cumulative_limit(control=control, performed=performed)
