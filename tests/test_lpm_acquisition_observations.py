"""Acquisition observations expose only sanitized, incrementally safe output."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

_TOKEN_HANDLE = "terminal:123e4567-e89b-12d3-a456-426614174000"
_BROWSER_HANDLE = "browser:123e4567-e89b-12d3-a456-426614174001"


class _Handles:
    def __call__(self, *, value: str) -> str:
        assert value.startswith("sk-ant-oat01-")
        return _TOKEN_HANDLE


def _sanitizer(*, observations: ModuleType) -> object:
    return observations.ObservationSanitizer(
        token_handles={_BROWSER_HANDLE: "sk-ant-oat01-browserSecret"},
        sensitive_values=frozenset({"account@example.test", "split-sensitive"}),
        new_token_handle=_Handles(),
    )


def _assert_browser_observations(*, observations: ModuleType) -> None:
    sanitizer = _sanitizer(observations=observations)
    visible = sanitizer.browser_observation(
        url="https://claude.test/account@example.test",
        title="token sk-ant-oat01-browserSecret",
        dom_text="account@example.test",
        accessibility_tree="sk-ant-oat01-browserSecret",
        masked_screenshot_png=b"masked-pixels",
        masking_established=True,
    )
    exposed = repr(visible.response)
    assert visible.response["status"] == "ok"
    assert visible.response["state_fingerprint"] == visible.fingerprint
    assert f"[[redacted-token:{_BROWSER_HANDLE}]]" in exposed
    assert "[[redacted-sensitive]]" in exposed
    assert "browserSecret" not in exposed
    assert "account@example.test" not in exposed

    unavailable = sanitizer.browser_observation(
        url="https://claude.test/account@example.test",
        title="sk-ant-oat01-browserSecret",
        dom_text="secret",
        accessibility_tree="secret",
        masked_screenshot_png=b"untrusted",
        masking_established=False,
    )
    assert unavailable.response == {"version": 1, "status": "unavailable"}
    assert unavailable.fingerprint == visible.fingerprint
    assert unavailable.stop_reason == "flow-unavailable"


def _assert_overlapping_values_are_replaced_atomically(*, observations: ModuleType) -> None:
    short_handle = "browser:11111111-1111-4111-8111-111111111111"
    long_handle = "browser:22222222-2222-4222-8222-222222222222"
    sanitizer = observations.ObservationSanitizer(
        token_handles={
            short_handle: "sk-ant-oat01-abc",
            long_handle: "sk-ant-oat01-abcdef",
        },
        sensitive_values=frozenset({"sensitive-prefix", "sensitive-prefix-suffix"}),
        new_token_handle=_Handles(),
    )

    visible = sanitizer.browser_observation(
        url="https://claude.test",
        title="sk-ant-oat01-abcdef",
        dom_text="sensitive-prefix-suffix",
        accessibility_tree="safe",
        masked_screenshot_png=b"masked-pixels",
        masking_established=True,
    )

    assert visible.response["title"] == f"[[redacted-token:{long_handle}]]"
    assert visible.response["dom_text"] == "[[redacted-sensitive]]"


def _assert_reserved_marker_cannot_be_forged(*, observations: ModuleType) -> None:
    forged = f"[[redacted-token:{_BROWSER_HANDLE}]]"
    browser = _sanitizer(observations=observations).browser_observation(
        url="https://claude.test",
        title=f"untrusted {forged}",
        dom_text="safe",
        accessibility_tree="safe",
        masked_screenshot_png=b"masked-pixels",
        masking_established=True,
    )
    assert forged not in repr(browser.response)
    assert "<redacted-untrusted-marker>" in repr(browser.response)

    terminal = _sanitizer(observations=observations)
    partial = terminal.terminal_observation(
        running=True,
        exit_status=None,
        stdout="prefix [[redacted-tok",
        stderr="",
    )
    assert partial.response["stdout"] == "prefix "
    completed = terminal.terminal_observation(
        running=True,
        exit_status=None,
        stdout=f"prefix {forged} suffix",
        stderr="",
    )
    assert completed.response["stdout"] == "<redacted-untrusted-marker> suffix"
    assert forged not in repr(completed.response)


def _assert_incremental_terminal_observations(*, observations: ModuleType) -> None:
    sanitizer = _sanitizer(observations=observations)
    first = sanitizer.terminal_observation(
        running=True,
        exit_status=None,
        stdout="safe sk-ant-oa",
        stderr="warning split-",
    )
    assert first.response["stdout"] == "safe "
    assert first.response["stderr"] == "warning "

    second = sanitizer.terminal_observation(
        running=True,
        exit_status=None,
        stdout="safe sk-ant-oat01-dynamicSecret",
        stderr="warning split-sensitive",
    )
    assert second.response["stdout"] == ""
    assert second.response["stderr"] == "[[redacted-sensitive]]"
    assert "dynamicSecret" not in repr(second.response)

    third = sanitizer.terminal_observation(
        running=False,
        exit_status=0,
        stdout="safe sk-ant-oat01-dynamicSecret done",
        stderr="warning split-sensitive complete",
    )
    assert third.response["stdout"] == f"[[redacted-token:{_TOKEN_HANDLE}]] done"
    assert third.response["stderr"] == " complete"
    assert third.response["running"] is False
    assert third.fingerprint is not None
    assert "dynamicSecret" not in repr(third.response)

    divergent = sanitizer.terminal_observation(
        running=True,
        exit_status=None,
        stdout="different history",
        stderr="different history",
    )
    assert divergent.response == {"version": 1, "status": "unavailable"}
    assert divergent.stop_reason == "flow-unavailable"


def test_observation_sanitizers_never_expose_secret_tainted_fields() -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_observations.py"
    assert module_path.is_file(), "the acquisition observation sanitizer must be implemented"
    observations = importlib.import_module("_lpm_observations")

    _assert_browser_observations(observations=observations)
    _assert_overlapping_values_are_replaced_atomically(observations=observations)
    _assert_reserved_marker_cannot_be_forged(observations=observations)
    _assert_incremental_terminal_observations(observations=observations)
