"""Beside-tests for fitting the live overseer table to its TTY width."""

import os
import re

import supervisor
from test_supervisor_builders import make_supervisor, render_of
from test_supervisor_fakes import FakeTmux, TtyOut

__all__: list[str] = []

_ANSI_CONTROL = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class _SizedTtyOut(TtyOut):
    """A TTY double with a descriptor for ``os.get_terminal_size``."""

    def fileno(self):
        return 97


def _wide_row() -> supervisor.RowView:
    """The measured pre-fix shape: its unconstrained data line is 232 columns."""
    return supervisor.RowView(
        status="working",
        note="n" * 80,
        topic="t" * 58,
        tmux="m" * 51,
        runtime="claude",
        ctx=100,
        repo="/" + "r" * 44,
    )


def _visible(text: str) -> str:
    return _ANSI_CONTROL.sub("", text)


def _table_lines(rendered: str) -> list[str]:
    """Return title, header, rule, and the sole row after the attention block."""
    return rendered.splitlines()[-4:]


def _data_line(rendered: str) -> str:
    """Return the sole data row after title, header, and separator."""
    return _table_lines(rendered)[3]


def _set_columns(*, monkeypatch, columns):
    monkeypatch.setattr(os, "get_terminal_size", lambda _fd: os.terminal_size((columns(), 62)))


def test_tty_render_fits_the_measured_213_column_pane(*, tmp_path, monkeypatch):
    """The live failure was a 232-column row painted into a 213-column tmux pane."""
    _set_columns(monkeypatch=monkeypatch, columns=lambda: 213)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), out=_SizedTtyOut())

    rendered = render_of(sup=sup, views=[_wide_row()])

    data = _visible(_data_line(rendered))
    assert len(data) <= 213
    assert all(len(_visible(line)) <= 213 for line in _table_lines(rendered))


def test_tty_width_is_read_again_on_every_render(*, tmp_path, monkeypatch):
    """A pane resize changes the very next repaint without restarting the daemon."""
    width = {"columns": 213}
    _set_columns(monkeypatch=monkeypatch, columns=lambda: width["columns"])
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), out=_SizedTtyOut())

    first = render_of(sup=sup, views=[_wide_row()])
    first_data = _visible(_data_line(first))
    prior_output_length = len(sup.out.getvalue())
    width["columns"] = 80

    sup.render(rows=[_wide_row()])

    second = sup.out.getvalue()[prior_output_length:]
    second_data = _visible(_data_line(second))
    assert len(first_data) <= 213
    assert len(second_data) <= 80
    assert len(second_data) < len(first_data)
    assert second_data.count("…") >= 4  # Status, Topic, tmux, and Repo are bounded.


def test_tty_render_uses_a_compact_five_column_table_below_the_full_minimum(
    *, tmp_path, monkeypatch
):
    _set_columns(monkeypatch=monkeypatch, columns=lambda: 24)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), out=_SizedTtyOut())

    rendered = render_of(sup=sup, views=[_wide_row()])

    table = _table_lines(rendered)
    assert all(len(_visible(line)) <= 24 for line in table)
    assert _visible(table[1]).split() == ["S", "T", "M", "C", "R"]


def test_tty_render_remains_bounded_at_ultra_narrow_widths(*, tmp_path, monkeypatch):
    width = {"columns": 7}
    _set_columns(monkeypatch=monkeypatch, columns=lambda: width["columns"])
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), out=_SizedTtyOut())

    seven_columns = render_of(sup=sup, views=[_wide_row()])
    prior_output_length = len(sup.out.getvalue())
    width["columns"] = 4
    sup.render(rows=[_wide_row()])
    four_columns = sup.out.getvalue()[prior_output_length:]

    assert all(len(_visible(line)) <= 7 for line in _table_lines(seven_columns))
    assert all(len(_visible(line)) <= 4 for line in _table_lines(four_columns))


def test_tty_width_lookup_failure_uses_a_bounded_fallback(*, tmp_path, monkeypatch):
    def fail(_fd):
        raise OSError("terminal size unavailable")

    monkeypatch.setattr(os, "get_terminal_size", fail)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), out=_SizedTtyOut())

    rendered = render_of(sup=sup, views=[_wide_row()])

    assert all(len(_visible(line)) <= 120 for line in _table_lines(rendered))


def test_non_tty_list_output_remains_unbounded_and_does_not_read_terminal_width(
    *, tmp_path, monkeypatch
):
    def fail(_fd):
        raise AssertionError("non-TTY output must not inspect terminal width")

    monkeypatch.setattr(os, "get_terminal_size", fail)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())

    rendered = render_of(sup=sup, views=[_wide_row()])

    data = _data_line(rendered)
    assert len(data) == 232
    assert "\x1b[3" not in data
