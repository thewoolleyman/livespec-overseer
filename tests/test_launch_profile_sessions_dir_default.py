"""The launch-profile refresh resolves the registry directory from the supervisor or the default."""

from __future__ import annotations

from types import SimpleNamespace

import _supervisor_launch_profile_refresh
import claude_sessions

__all__: list[str] = []


def test_profile_sessions_dir_prefers_the_supervisor_then_the_default():
    explicit = SimpleNamespace(sessions_dir="/explicit")
    default = SimpleNamespace(sessions_dir=None)

    assert _supervisor_launch_profile_refresh._profile_sessions_dir(sup=explicit) == "/explicit"
    assert (
        _supervisor_launch_profile_refresh._profile_sessions_dir(sup=default)
        == claude_sessions.default_sessions_dir()
    )
