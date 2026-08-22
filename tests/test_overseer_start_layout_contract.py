"""Repo-level regressions for the overseer-start pane-layout contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from overseer import start

__all__: list[str] = []


@dataclass(kw_only=True)
class PaneGeometry:
    pane: str
    top: int
    height: int


class Layout:
    def __init__(self, *, split_result: str = "%88", initial_title: bool = False) -> None:
        self.split_result = split_result
        self.initial_title = initial_title
        self.titles = ["operator"]
        if initial_title:
            self.titles.append("overseer-daemon")
        self.geometry_reads = 0
        self.calls: list[tuple[str, object, object, object] | tuple[str, object]] = []

    def pane_by_title(self, *, pane: str, title: str) -> str | None:
        self.calls.append(("pane_by_title", pane, title, ""))
        return self.split_result if title in self.titles else None

    def split_window_top(self, *, pane: str, cwd: str, command: str) -> str | None:
        self.calls.append(("split_window_top", pane, cwd, command))
        return self.split_result

    def set_pane_title(self, *, pane: str, title: str) -> bool:
        self.calls.append(("set_pane_title", pane, title, ""))
        self.titles.append(title)
        return True

    def pane_exists(self, *, pane: str) -> bool:
        self.calls.append(("pane_exists", pane))
        return True

    def select_layout_even(self, *, pane: str) -> bool:
        self.calls.append(("select_layout_even", pane))
        return True

    def window_pane_geometries(self, *, pane: str) -> list[PaneGeometry]:
        self.calls.append(("window_pane_geometries", pane))
        self.geometry_reads += 1
        if self.geometry_reads == 1 and self.initial_title:
            return [PaneGeometry(pane=self.split_result, top=0, height=30)]
        return [
            PaneGeometry(pane=self.split_result, top=0, height=20),
            PaneGeometry(pane="%9", top=20, height=10),
        ]

    def set_pane_height_percent(self, *, pane: str, percent: int) -> bool:
        self.calls.append(("set_pane_height_percent", pane, percent, ""))
        return True


class Supervisor:
    def adopt_sessions(self) -> list[object]:
        return []


def test_overseer_start_restores_a_missing_daemon_top_pane(*, monkeypatch, tmp_path: Path) -> None:
    """A collapsed daemon pane is rebuilt above the operator pane, then verified by id."""
    monkeypatch.setattr(start, "_running_under_supported_agent", lambda: True)
    monkeypatch.setenv("TMUX_PANE", "%9")
    monkeypatch.setattr(start.runtime_prefix, "ensure_current_runtime", lambda: tmp_path / "d")
    layout = Layout(split_result="%88")

    rc = start.main(argv=[], io=layout, build_supervisor=Supervisor, core_root=tmp_path)

    assert rc == 0
    assert ("split_window_top", "%9", str(tmp_path), layout.calls[1][3]) in layout.calls
    assert ("window_pane_geometries", "%88") in layout.calls
    assert ("set_pane_height_percent", "%88", 66, "") in layout.calls


def test_overseer_start_rebuilds_when_the_titled_daemon_pane_is_not_in_two_panes(
    *, monkeypatch, tmp_path: Path
) -> None:
    """A stale title on a collapsed layout is not enough to accept the daemon pane."""
    monkeypatch.setattr(start, "_running_under_supported_agent", lambda: True)
    monkeypatch.setenv("TMUX_PANE", "%9")
    monkeypatch.setattr(start.runtime_prefix, "ensure_current_runtime", lambda: tmp_path / "d")
    layout = Layout(split_result="%88", initial_title=True)

    rc = start.main(argv=[], io=layout, build_supervisor=Supervisor, core_root=tmp_path)

    assert rc == 0
    assert ("split_window_top", "%9", str(tmp_path), layout.calls[2][3]) in layout.calls
