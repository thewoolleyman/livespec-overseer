"""A daemon drawing its table in a herdr pane is not a headless daemon.

Measured 2026-10-12 on the live fleet (v5.27.2): overseerd ran in herdr top pane
w5:pA and its table was plainly visible there, yet every tick NEEDS YOU led with
"daemon surface — daemon-table-headless — rendering to non-terminal stream; restore
the two-pane model with /overseer bootstrap". The check only recognized a tmux pane
($TMUX_PANE), so a herdr-hosted daemon always read as headless.
"""

from __future__ import annotations

import _supervisor_attention
from test_supervisor_builders import make_supervisor
from test_supervisor_fakes import FakeTmux, TtyOut

__all__: list[str] = []

_HERDR_EXPORT = {
    "HERDR_SOCKET_PATH": "/home/ubuntu/.config/herdr/herdr.sock",
    "HERDR_PANE_ID": "w5:pA",
}


def test_a_terminal_attached_daemon_in_its_own_herdr_pane_is_not_headless(*, tmp_path):
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        own_pane=None,
        environ=lambda: dict(_HERDR_EXPORT),
        out=TtyOut(),
        require_render_terminal=True,
    )

    assert _supervisor_attention.render_surface_attention(sup=sup, act=True) is None


def test_a_herdr_pane_does_not_excuse_a_non_terminal_stream(*, tmp_path):
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        own_pane=None,
        environ=lambda: dict(_HERDR_EXPORT),
        require_render_terminal=True,
    )

    attention = _supervisor_attention.render_surface_attention(sup=sup, act=False)

    assert attention is not None
    assert attention.status == _supervisor_attention.SURFACE_HEADLESS_STATUS


def test_a_terminal_attached_daemon_outside_any_pane_is_still_headless(*, tmp_path):
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        own_pane=None,
        environ=lambda: {"HERDR_SOCKET_PATH": "/run/herdr.sock"},
        out=TtyOut(),
        require_render_terminal=True,
    )

    attention = _supervisor_attention.render_surface_attention(sup=sup, act=False)

    assert attention is not None
