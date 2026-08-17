"""Tests for foreman_gather_evidence.py row enrichment helpers."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_gather_evidence.py"

__all__: list[str] = []


def foreman_gather_evidence():
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_gather_evidence")


def completed(*, returncode: int, stdout: str = ""):
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def test_git_proposed_changes_count_filters_internal_paths_and_renames(*, monkeypatch, tmp_path):
    module = foreman_gather_evidence()
    monkeypatch.setattr(module.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: completed(
            returncode=0,
            stdout=(
                " M overseer/foreman_gather.py\n"
                "?? plan/topic/epic.md\n"
                "?? tmp/overseer/state\n"
                "R  old.txt -> new.txt\n"
            ),
        ),
    )

    assert module.git_proposed_changes_count(repo=tmp_path) == 2
    assert module.proposed_changes_count(repo=tmp_path) == 2
    assert module.git_status_path(line="??") == ""
    assert module.proposed_path_excluded(path=".beads/state") is True


def test_git_proposed_changes_count_falls_back_on_unavailable_git(*, monkeypatch, tmp_path):
    module = foreman_gather_evidence()
    monkeypatch.setattr(module.shutil, "which", lambda name: None)

    assert module.git_proposed_changes_count(repo=tmp_path) is None

    monkeypatch.setattr(module.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: completed(returncode=7),
    )
    assert module.git_proposed_changes_count(repo=tmp_path) is None

    def raise_os_error(*args, **kwargs):
        del args, kwargs
        raise OSError

    monkeypatch.setattr(module.subprocess, "run", raise_os_error)
    assert module.git_proposed_changes_count(repo=tmp_path) is None


def test_fallback_proposed_changes_count_excludes_overseer_internal_dirs(*, tmp_path):
    module = foreman_gather_evidence()
    (tmp_path / "changed.txt").write_text("pending\n", encoding="utf-8")
    (tmp_path / "plan" / "topic").mkdir(parents=True)
    (tmp_path / "plan" / "topic" / "epic.md").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / "state").write_text("ignored\n", encoding="utf-8")

    assert module.fallback_proposed_changes_count(repo=tmp_path) == 1


def test_fallback_proposed_changes_count_fails_soft_on_walk_error(*, monkeypatch, tmp_path):
    module = foreman_gather_evidence()

    def raise_os_error(*args, **kwargs):
        del args, kwargs
        raise OSError

    monkeypatch.setattr(module.Path, "rglob", raise_os_error)

    assert module.fallback_proposed_changes_count(repo=tmp_path) == 0


def test_pane_capture_hash_sources_are_fail_soft(*, monkeypatch):
    module = foreman_gather_evidence()

    assert module.row_pane_content_hash(row={"tmux": None}, pane_captures={}) is None
    assert module.row_pane_content_hash(row={"tmux": "alpha"}, pane_captures={}) is None
    assert module.pane_capture_text(session="alpha", pane_captures=lambda *, session: session) == (
        "alpha"
    )

    class FakeTmux:
        def capture_pane(self, *, session: str) -> str:
            return f"pane:{session}"

    monkeypatch.setattr(module.tmuxio, "TmuxIO", lambda: FakeTmux())

    assert module.pane_capture_text(session="beta", pane_captures=None) == "pane:beta"
