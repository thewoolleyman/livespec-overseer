"""Red probe for Codex admission in overseer-start."""

import importlib

__all__: list[str] = []


def test_codex_runtime_reaches_the_tmux_pane_check_without_claudecode(*, monkeypatch, capsys):
    mod = importlib.import_module("overseer.start")
    monkeypatch.setattr(mod, "_running_under_supported_agent", lambda: True, raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)

    assert mod.main(argv=[]) == 1

    err = capsys.readouterr().err
    assert "$TMUX_PANE unset" in err
    assert "Refusing to run outside Claude Code or Codex" not in err
