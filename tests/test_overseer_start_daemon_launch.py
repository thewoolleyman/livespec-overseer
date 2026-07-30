"""Regression coverage for overseer-start daemon launch reporting."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


class _Layout:
    def __init__(self, *, panes_alive: dict[str, bool] | None = None):
        self.calls: list[tuple[str, object, object, object]] = []
        self.panes_alive = dict(panes_alive or {})
        self.titles: list[str] = []

    def window_pane_titles(self, *, pane: str) -> list[str]:
        self.calls.append(("window_pane_titles", pane, None, None))
        return []

    def split_window_top(self, *, pane: str, cwd: str, command: str) -> str:
        self.calls.append(("split_window_top", pane, cwd, command))
        if "%77" not in self.panes_alive:
            self.panes_alive["%77"] = True
        return "%77"

    def pane_exists(self, *, pane: str) -> bool:
        self.calls.append(("pane_exists", pane, None, None))
        return self.panes_alive.get(pane, False)

    def set_pane_title(self, *, pane: str, title: str) -> bool:
        self.calls.append(("set_pane_title", pane, title, None))
        self.titles.append(title)
        return True

    def select_layout_even(self, *, pane: str) -> bool:
        self.calls.append(("select_layout_even", pane, None, None))
        return True

    def pane_by_title(self, *, pane: str, title: str) -> str | None:
        self.calls.append(("pane_by_title", pane, title, None))
        return "%77" if title in self.titles else None

    def set_pane_height_percent(self, *, pane: str, percent: int) -> bool:
        self.calls.append(("set_pane_height_percent", pane, percent, None))
        return True


class _Supervisor:
    def adopt_sessions(self) -> list[object]:
        return []


def _load():
    return importlib.import_module("overseer.start")


def _in_agent_tmux(*, monkeypatch) -> None:
    mod = _load()
    monkeypatch.setattr(mod, "_running_under_supported_agent", lambda: True)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("TMUX_PANE", "%9")


def _call_kinds(*, layout: _Layout) -> list[str]:
    return [call[0] for call in layout.calls]


def test_daemon_command_uses_absolute_checkout_log_path() -> None:
    mod = _load()
    log_path = Path(mod.__file__).resolve().parent.parent / "tmp" / "overseer" / "daemon.log"

    assert mod.daemon_command(warn_percent=None) == f"overseerd 2>> {log_path}"
    assert mod.daemon_command(warn_percent=25) == f"overseerd --warn-percent 25 2>> {log_path}"


def test_split_launch_uses_absolute_core_root_log_path(*, monkeypatch, tmp_path) -> None:
    mod = _load()
    _in_agent_tmux(monkeypatch=monkeypatch)
    layout = _Layout()

    assert mod.main(argv=[], io=layout, build_supervisor=_Supervisor, core_root=tmp_path) == 0

    command = layout.calls[1][3]
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"
    assert command == f"overseerd 2>> {log_path}"
    assert Path(str(command).rpartition(" ")[2]).is_absolute()


def test_split_launch_fails_when_daemon_pane_dies(*, monkeypatch, tmp_path, capsys) -> None:
    mod = _load()
    _in_agent_tmux(monkeypatch=monkeypatch)
    layout = _Layout(panes_alive={"%77": False})

    assert mod.main(argv=[], io=layout, build_supervisor=_Supervisor, core_root=tmp_path) == 1

    err = capsys.readouterr().err
    assert "overseerd did not stay alive" in err
    assert "daemon.log" in err
    assert "select_layout_even" not in _call_kinds(layout=layout)
