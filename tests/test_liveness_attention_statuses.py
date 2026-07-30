"""Repo-level attention membership regressions for liveness report statuses."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import supervisor


def test_winddown_starved_needs_attention():
    row = supervisor.RowView(topic="t", repo="/r", tmux="s", ctx=40, status="winddown-starved")
    assert supervisor.needs_attention(row=row) is True


def test_shell_prolonged_needs_attention():
    row = supervisor.RowView(topic="t", repo="/r", tmux="s", ctx=73, status="shell-prolonged")
    assert supervisor.needs_attention(row=row) is True
