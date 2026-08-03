"""Coverage for the q3f Red helper's pre-implementation branch."""

from __future__ import annotations

import importlib

__all__: list[str] = []


def test_red_helper_still_runs_against_the_old_detector_signature(*, monkeypatch):
    module = importlib.import_module("test_q3f_shell_argv_identity")

    def old_has_active_subshell(*, root_pid, children_of, comm_of, starttime_of):
        assert root_pid == 100
        assert children_of(pid=100) == [200]
        assert comm_of(pid=200) == "codex"
        assert starttime_of(pid=200) == "1000"
        return False

    monkeypatch.setattr(module.claude_sessions, "has_active_subshell", old_has_active_subshell)
    assert module._has_active_subshell(cmdlines={}) is False
