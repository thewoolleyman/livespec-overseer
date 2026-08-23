"""Edge coverage for daemon render-surface attention."""

from __future__ import annotations

import contextlib
import io as _io
import json

import _supervisor_attention
from test_supervisor_builders import make_supervisor
from test_supervisor_fakes import FakeTmux, TtyOut

__all__: list[str] = []


def test_terminal_stream_without_daemon_tmux_pane_surfaces_headless_attention(*, tmp_path):
    fake = FakeTmux()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        own_pane=None,
        out=TtyOut(),
        require_render_terminal=True,
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        attention = _supervisor_attention.render_surface_attention(sup=sup, act=True)

    assert attention is not None
    assert attention.status == _supervisor_attention.SURFACE_HEADLESS_STATUS
    assert attention.note == (
        "rendering to non-terminal stream; restore the two-pane model with /overseer bootstrap"
    )
    event = json.loads(err.getvalue())
    assert event["message"] == f"daemon table is not reaching a tmux pane; {attention.note}"
