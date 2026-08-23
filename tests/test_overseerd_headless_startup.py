"""Regression tests for headless overseerd startup."""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "overseer"))

import supervisor

__all__: list[str] = []


class _FakeTmux:
    def list_sessions(self) -> list[str]:
        return []


def test_overseerd_refuses_when_stdout_is_not_a_terminal(*, tmp_path):
    """A setsid-style redirected launch has nowhere operator-visible to render."""
    err = io.StringIO()
    sup = supervisor.Supervisor(
        tmux=_FakeTmux(),
        store_path=tmp_path / "map.jsonl",
        stamp_path=tmp_path / "stamps.json",
        watch_repos=[],
        status_path=tmp_path / "status.json",
        runtime_state_path=tmp_path / "runtime-state.json",
        proc_root=tmp_path,
        which=lambda _name: "/usr/bin/tmux",
        out=io.StringIO(),
        sleep=lambda _seconds: None,
    )
    ticked: list[bool] = []
    sup.tick = lambda *, act: ticked.append(act)  # type: ignore[assignment]

    with contextlib.redirect_stderr(err):
        sup.run(once=True)

    assert ticked == []
    text = err.getvalue()
    assert "refusing to start: no controlling terminal" in text
    assert "live table has nowhere to render" in text
