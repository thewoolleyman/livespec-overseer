"""Tick publish side-effect coverage for read-only versus acting ticks."""

from pathlib import Path

import _supervisor_render
import supervisor
from test_supervisor_builders import make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


PublishRecord = tuple[str, int | str | list[str]]


def _supervisor_with_publish_recorders(*, tmp_path, monkeypatch):
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    published: list[PublishRecord] = []
    target = tmp_path / "runtime" / "bin" / "overseerd"

    def build_no_rows(*, act: bool):
        return []

    def refresh_window_name(*, sup, attention: int) -> None:
        published.append(("window", attention))

    def write_snapshot(*, sup, rows) -> None:
        published.append(("snapshot", len(rows)))

    def execv(*, path: str, argv: list[str]) -> None:
        published.append(("execv_path", Path(path).name))
        published.append(("execv_argv", argv))

    sup.build_rows = build_no_rows
    sup.status_snapshot_writer = write_snapshot
    sup.reexec_target = lambda: target
    sup.execv = execv
    sup.argv = lambda: ["overseerd", "--warn-percent", "30"]
    monkeypatch.setattr(_supervisor_render, "refresh_window_name", refresh_window_name)
    return sup, published


def test_read_only_tick_performs_no_daemon_only_publish_writes(*, tmp_path, monkeypatch):
    sup, published = _supervisor_with_publish_recorders(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    rows = supervisor.Supervisor.tick(sup, act=False)

    assert rows == []
    assert published == []
    assert sup.tick_generation == 0


def test_acting_tick_performs_all_daemon_only_publish_writes(*, tmp_path, monkeypatch):
    sup, published = _supervisor_with_publish_recorders(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    rows = supervisor.Supervisor.tick(sup, act=True)

    assert rows == []
    assert published == [
        ("window", 0),
        ("snapshot", 0),
        ("execv_path", "overseerd"),
        ("execv_argv", [str(tmp_path / "runtime" / "bin" / "overseerd"), "--warn-percent", "30"]),
    ]
    assert sup.tick_generation == 1
