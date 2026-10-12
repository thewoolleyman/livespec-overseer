"""A running terminal stream never releases a registered token that may still grow."""

from __future__ import annotations

import importlib

_REGISTERED_HANDLE = "browser:11111111-1111-4111-8111-111111111111"
_DYNAMIC_HANDLE = "terminal:22222222-2222-4222-8222-222222222222"


class _Handles:
    def __call__(self, *, value: str) -> str:
        assert value.startswith("sk-ant-oat01-")
        return _DYNAMIC_HANDLE


def test_registered_token_at_running_end_is_held_until_it_cannot_extend() -> None:
    observations = importlib.import_module("_lpm_observations")
    sanitizer = observations.ObservationSanitizer(
        token_handles={_REGISTERED_HANDLE: "sk-ant-oat01-abc"},
        sensitive_values=frozenset(),
        new_token_handle=_Handles(),
    )

    first = sanitizer.terminal_observation(
        running=True,
        exit_status=None,
        stdout="token sk-ant-oat01-abc",
        stderr="",
    )
    second = sanitizer.terminal_observation(
        running=True,
        exit_status=None,
        stdout="token sk-ant-oat01-abcdef ",
        stderr="",
    )

    released = first.response["stdout"] + second.response["stdout"]
    assert first.response["stdout"] == "token "
    assert released == f"token [[redacted-token:{_DYNAMIC_HANDLE}]] "
    assert "def" not in released
