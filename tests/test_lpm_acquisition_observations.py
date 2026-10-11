"""Browser and terminal observations expose only sanitized values and opaque handles."""

from __future__ import annotations

import importlib
from pathlib import Path


def _assert_sanitized_browser(*, sanitizer):
    outcome = sanitizer.browser_observation(
        url="https://claude.com/callback?token=sk-ant-oat01-browserSecret",
        title="Signed in as login@example.test",
        dom_text="token sk-ant-oat01-browserSecret for login@example.test",
        accessibility_tree="copy sk-ant-oat01-browserSecret",
        masked_screenshot_png=b"masked-png",
        masking_established=True,
    )
    response = outcome.response
    assert response is not None
    assert set(response) == {
        "version",
        "status",
        "url",
        "title",
        "dom_text",
        "accessibility_tree",
        "screenshot_png",
        "state_fingerprint",
    }
    assert "sk-ant-oat01-browserSecret" not in repr(response)
    assert "login@example.test" not in repr(response)
    assert "[[redacted-token:browser:11111111-1111-4111-8111-111111111111]]" in repr(response)
    assert "[[redacted-sensitive]]" in repr(response)
    assert outcome.stop_reason is None
    return outcome.fingerprint


def _assert_sanitized_terminal(*, sanitizer):
    outcome = sanitizer.terminal_observation(
        running=False,
        exit_status=0,
        stdout="Authorize at https://claude.com then sk-ant-oat01-terminalSecret",
        stderr="mailbox code 654321",
    )
    assert outcome.response == {
        "version": 1,
        "status": "ok",
        "running": False,
        "exit_status": 0,
        "stdout": (
            "Authorize at https://claude.com then "
            "[[redacted-token:terminal:22222222-2222-4222-8222-222222222222]]"
        ),
        "stderr": "mailbox code [[redacted-sensitive]]",
    }


def test_observations_are_sanitized_and_unprovable_masking_fails_closed():
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_observations.py"
    assert module_path.is_file(), "the observation sanitizer must be implemented"
    observations = importlib.import_module("_lpm_observations")
    sanitizer = observations.ObservationSanitizer(
        token_handles={
            "browser:11111111-1111-4111-8111-111111111111": ("sk-ant-oat01-browserSecret"),
            "terminal:22222222-2222-4222-8222-222222222222": ("sk-ant-oat01-terminalSecret"),
        },
        sensitive_values=frozenset({"login@example.test", "654321"}),
    )

    prior_fingerprint = _assert_sanitized_browser(sanitizer=sanitizer)
    _assert_sanitized_terminal(sanitizer=sanitizer)
    failed = sanitizer.browser_observation(
        url="https://claude.com",
        title="unsafe",
        dom_text="login@example.test",
        accessibility_tree="unsafe",
        masked_screenshot_png=b"untrusted",
        masking_established=False,
    )
    assert failed.response == {"version": 1, "status": "unavailable"}
    assert failed.fingerprint == prior_fingerprint
    assert failed.stop_reason == "flow-unavailable"
    assert set(failed.response) == {"version", "status"}
