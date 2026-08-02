"""Tests for overseer-start — the /overseer skill's two-pane bootstrap guard.

Run: ``uv run pytest .claude/skills/overseer/ -q``. The bootstrap is a hyphen-named
executable (Python source under a `uv` shebang), so it is loaded via importlib; its
`if __name__ == "__main__"` guard keeps the import side-effect-free. Only the
agent-runtime precondition (the guard added 2026-07-13) is exercised here before
the proceed path's fake tmux layout.
"""

import importlib
from pathlib import Path

__all__: list[str] = []


def _load():
    return importlib.import_module("overseer.start")


def _runtime_supported(*, monkeypatch, supported: bool):
    monkeypatch.setattr(_load(), "_running_under_supported_agent", lambda: supported)


def test_refuses_outside_agent_runtime(*, monkeypatch, capsys):
    # Run by hand in a plain shell: refuse BEFORE any tmux op,
    # so no half-set-up daemon pane / bare-shell bottom pane is ever created.
    mod = _load()
    _runtime_supported(monkeypatch=monkeypatch, supported=False)
    monkeypatch.setenv("TMUX_PANE", "%9")  # in tmux, but not an agent session
    # main(argv=[]) — pass an explicit empty argv so argparse does not read pytest's own
    # sys.argv (main now parses `--warn-percent`); no flags → the guards still run.
    assert mod.main(argv=[]) == 1
    err = capsys.readouterr().err
    assert "/overseer" in err
    assert "outside Claude Code or Codex" in err


def test_agent_runtime_guard_precedes_tmux_check(*, monkeypatch, capsys):
    # The agent-runtime precondition is checked FIRST: with neither marker set, the
    # message is the standalone-refusal, not the "$TMUX_PANE unset" one.
    mod = _load()
    _runtime_supported(monkeypatch=monkeypatch, supported=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    assert mod.main(argv=[]) == 1
    err = capsys.readouterr().err
    assert "Refusing to run outside Claude Code or Codex" in err
    assert "TMUX_PANE" not in err


def test_allows_when_agent_runtime_detected(*, monkeypatch, capsys):
    # With an agent runtime detected but $TMUX_PANE unset, the runtime guard PASSES and
    # execution falls through to the tmux-pane check.
    mod = _load()
    _runtime_supported(monkeypatch=monkeypatch, supported=True)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    assert mod.main(argv=[]) == 1
    err = capsys.readouterr().err
    assert "$TMUX_PANE unset" in err  # reached the tmux check
    assert "Refusing to run outside Claude Code or Codex" not in err  # NOT the guard


def test_codex_runtime_is_accepted_without_claudecode(*, monkeypatch, capsys):
    # A real standalone Codex session does not carry $CLAUDECODE. Process ancestry,
    # not that inherited env marker, must admit it.
    mod = _load()
    _runtime_supported(monkeypatch=monkeypatch, supported=True)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    assert mod.main(argv=[]) == 1
    err = capsys.readouterr().err
    assert "$TMUX_PANE unset" in err
    assert "Refusing to run outside Claude Code or Codex" not in err


def test_still_refuses_when_neither_runtime_marker_is_present(*, monkeypatch, capsys):
    mod = _load()
    _runtime_supported(monkeypatch=monkeypatch, supported=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    assert mod.main(argv=[]) == 1
    err = capsys.readouterr().err
    assert "Refusing to run outside Claude Code or Codex" in err
    assert "TMUX_PANE" not in err


def test_claude_code_marker_alone_does_not_admit_a_session(*, monkeypatch, capsys):
    # $CLAUDECODE can leak into nested Codex sessions and other descendants, so the
    # launch gate must not treat the env marker alone as sufficient.
    mod = _load()
    _runtime_supported(monkeypatch=monkeypatch, supported=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("TMUX_PANE", raising=False)
    assert mod.main(argv=[]) == 1
    err = capsys.readouterr().err
    assert "Refusing to run outside Claude Code or Codex" in err
    assert "TMUX_PANE" not in err


def test_claude_code_runtime_is_accepted(*, monkeypatch, capsys):
    # With a supported runtime detected and $TMUX_PANE unset, the runtime guard PASSES and
    # execution falls through to the tmux-pane check — proving the guard does not
    # block a genuine Claude Code session (it stops later, for the tmux reason).
    mod = _load()
    _runtime_supported(monkeypatch=monkeypatch, supported=True)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("TMUX_PANE", raising=False)
    assert mod.main(argv=[]) == 1
    err = capsys.readouterr().err
    assert "$TMUX_PANE unset" in err  # reached the tmux check
    assert "Refusing to run outside Claude Code or Codex" not in err  # NOT the guard


def test_daemon_command_threads_warn_percent():
    # Part 1: --warn-percent N is appended to the overseerd launch command; without
    # it the command is unchanged (default threshold applies inside overseerd).
    mod = _load()
    log_path = Path(mod.__file__).resolve().parent.parent / "tmp" / "overseer" / "daemon.log"
    assert mod.daemon_command(warn_percent=None) == f"overseerd 2>> {log_path}"
    assert mod.daemon_command(warn_percent=30) == f"overseerd --warn-percent 30 2>> {log_path}"


def test_warn_percent_arg_parses(*, monkeypatch):
    # main(argv=[--warn-percent, N]) parses the flag; with no runtime marker the guard
    # still short-circuits (return 1), proving the flag doesn't break arg parsing.
    mod = _load()
    _runtime_supported(monkeypatch=monkeypatch, supported=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    assert mod.main(argv=["--warn-percent", "25"]) == 1


def test_overseer_start_console_entry_point_targets_importable_module():
    module_path = Path(__file__).resolve().parent / "start.py"
    assert module_path.is_file(), "overseer-start logic must live in importable overseer.start"

    mod = importlib.import_module("overseer.start")
    assert mod.main is not None
    log_path = Path(mod.__file__).resolve().parent.parent / "tmp" / "overseer" / "daemon.log"
    assert mod.daemon_command(warn_percent=None) == f"overseerd 2>> {log_path}"

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert 'overseer-start = "overseer.start:main"' in pyproject.read_text(encoding="utf-8")


class _FakeSupervisor:
    def __init__(self, adopted=()):
        self._adopted = list(adopted)

    def adopt_sessions(self):
        return list(self._adopted)


def _in_claude_tmux(*, monkeypatch):
    _runtime_supported(monkeypatch=monkeypatch, supported=True)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("TMUX_PANE", "%9")


def _kinds(*, layout):
    return [c[0] for c in layout.calls]
