"""Beside-tests for terminal evidence in :mod:`_codex_proc`."""

from __future__ import annotations

from pathlib import Path

import _codex_proc

__all__: list[str] = []


def _fake_proc(*, tmp_path, monkeypatch):
    """Redirect the module's `/proc` reads to a test-owned tree."""
    root = tmp_path / "proc"
    root.mkdir()

    def _redirect(arg):
        text = str(arg)
        if text.startswith("/proc/"):
            return root / text[len("/proc/") :]
        return Path(text)

    monkeypatch.setattr(_codex_proc, "Path", _redirect)
    return root


def test_proc_foreground_pgrp_accepts_only_the_terminal_foreground_group(*, tmp_path, monkeypatch):
    """A Codex TUI is its tty's foreground group; app-server helpers are not."""
    root = _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    cases = (
        ("137 (codex) S 34 113 113 34816 113", 113),
        ("379 (codex) S 137 379 379 0 -1", None),
        ("138 (codex) S 34 114 114 34816 113", None),
        ("137 codex S 34 113 113 34816 113", None),
        ("137 (codex) S 34", None),
        ("137 (codex) S 34 bad 113 34816 113", None),
    )
    for pid, (raw, expected) in enumerate(cases, start=1):
        directory = root / str(pid)
        directory.mkdir()
        (directory / "stat").write_text(raw, encoding="utf-8")
        assert _codex_proc.proc_foreground_pgrp(pid=pid) == expected


def test_proc_foreground_pgrp_is_none_when_the_process_disappears(*, tmp_path, monkeypatch):
    _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    assert _codex_proc.proc_foreground_pgrp(pid=999999) is None
