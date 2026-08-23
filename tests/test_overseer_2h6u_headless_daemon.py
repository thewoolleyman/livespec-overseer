"""Regression tests for headless daemon table detection."""

from __future__ import annotations

import contextlib
import io as _io
import json

from test_supervisor_builders import make_supervisor
from test_supervisor_fakes import FakeTmux, TtyOut

__all__: list[str] = []


def test_headless_daemon_rendering_to_file_surfaces_attention_and_badge(*, tmp_path):
    """A live daemon whose table is going to a file must not look the same as a dead one."""
    table_log = tmp_path / "overseer-table.log"
    fake = FakeTmux()
    fake.sessions.add("%7")
    with table_log.open("w+", encoding="utf-8") as out:
        sup = make_supervisor(
            tmp_path=tmp_path,
            fake=fake,
            own_pane="%7",
            out=out,
            watch_set_path=None,
            watch_repos=[],
        )
        err = _io.StringIO()
        with contextlib.redirect_stderr(err):
            sup.tick(act=True)
        out.seek(0)
        rendered = out.read()

    assert "NEEDS YOU (1):" in rendered
    assert "daemon-table-headless" in rendered
    assert str(table_log) in rendered
    assert fake.window_name == "overseer(SURFACE!)"
    events = [json.loads(line) for line in err.getvalue().splitlines()]
    assert [event["message"] for event in events] == [
        "daemon table is not reaching a tmux pane; rendering to "
        f"{table_log}; restore the two-pane model with /overseer bootstrap"
    ]


def test_daemon_rendering_to_tmux_pane_does_not_surface_headless_attention(*, tmp_path):
    """A TTY stream plus the daemon's own tmux pane is the healthy render surface."""
    fake = FakeTmux()
    fake.sessions.add("%7")
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        own_pane="%7",
        out=TtyOut(),
        watch_set_path=None,
        watch_repos=[],
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.tick(act=True)
    rendered = sup.out.getvalue()

    assert "daemon-table-headless" not in rendered
    assert "NEEDS YOU: nothing" in rendered
    assert fake.window_name == "overseer"
    assert err.getvalue() == ""
