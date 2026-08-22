"""Daemon self re-exec safe-point coverage."""

from pathlib import Path

import _supervisor_reexec
import supervisor
from _supervisor_view import RowView
from test_supervisor_builders import make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_reexec_waits_for_a_restart_interlock_then_runs_at_the_next_clean_tick(*, tmp_path):
    """A session restart in flight defers daemon self-replacement, but only until it clears."""
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    target = tmp_path / "runtime" / "bin" / "overseerd"
    executed: list[tuple[str, list[str]]] = []
    rows = [
        [
            RowView(
                topic="topic",
                repo=str(tmp_path),
                tmux="topic",
                ctx=12,
                status="restarting",
            )
        ],
        [
            RowView(
                topic="topic",
                repo=str(tmp_path),
                tmux="topic",
                ctx=99,
                status="idle",
            )
        ],
    ]

    def execv(*, path: str, argv: list[str]) -> None:
        executed.append((path, argv))

    sup.reexec_target = lambda: target
    sup.execv = execv
    sup.argv = lambda: ["overseerd", "--warn-percent", "30"]

    _supervisor_reexec.maybe_reexec(sup=sup, rows=rows.pop(0))
    assert executed == []

    _supervisor_reexec.maybe_reexec(sup=sup, rows=rows.pop(0))
    assert executed == [
        (str(target), [str(target), "--warn-percent", "30"]),
    ]


def test_reexec_attempts_are_rate_limited_even_when_the_release_keeps_flapping(*, tmp_path):
    fake = FakeTmux()
    clock = {"now": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"])
    target = tmp_path / "runtime" / "bin" / "overseerd"
    executed: list[tuple[str, list[str]]] = []

    def build_no_rows(*, act: bool):
        return []

    def execv(*, path: str, argv: list[str]) -> None:
        executed.append((path, argv))

    sup.build_rows = build_no_rows
    sup.reexec_target = lambda: target
    sup.execv = execv
    sup.argv = lambda: ["overseerd"]
    sup.reexec_min_interval_seconds = 60.0

    _ = sup.tick(act=True)
    _ = sup.tick(act=True)
    assert executed == [(str(target), [str(target)])]

    clock["now"] += 61.0
    _ = sup.tick(act=True)
    assert executed == [
        (str(target), [str(target)]),
        (str(target), [str(target)]),
    ]


def test_read_only_tick_never_reexecs(*, tmp_path):
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    def build_no_rows(*, act: bool):
        return []

    def execv(*, path: str, argv: list[str]) -> None:
        raise AssertionError("read-only list tick must not re-exec")

    sup.build_rows = build_no_rows
    sup.reexec_target = lambda: Path("/tmp/overseerd")
    sup.execv = execv

    assert supervisor.Supervisor.tick(sup, act=False) == []
