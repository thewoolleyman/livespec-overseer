"""Beside-tests for supervisor.py — row color operator.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    GREEN,
    RESET,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    render_of,
    row_line,
)
from test_supervisor_fakes import (
    FakeTmux,
    TtyOut,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_tty_render_leaves_unassigned_rows_uncolored(tmp_path):
    """`unassigned` is background noise, not a track that wants attention — it keeps
    the terminal default color, never a tint."""
    sup = make_supervisor(tmp_path, FakeTmux(), out=TtyOut())
    view = supervisor.RowView(topic="un", repo="/r", tmux=None, ctx=None, status="unassigned")
    line = row_line(render_of(sup, [view]), "un")
    assert "\x1b[3" not in line  # no SGR color introducer at all


def test_tty_render_leaves_header_and_separator_uncolored(tmp_path):
    sup = make_supervisor(tmp_path, FakeTmux(), out=TtyOut())
    view = supervisor.RowView(topic="wk", repo="/r", tmux="s", ctx=50, status="working")
    out = render_of(sup, [view])
    header = next(ln for ln in out.splitlines() if "Status" in ln and "Topic" in ln)
    assert "\x1b[3" not in header


def test_non_tty_render_is_plain_text(tmp_path):
    """A StringIO (and any piped `list`) is not a TTY, so no color leaks into it —
    this is what keeps every existing `row.split()` assertion valid."""
    sup = make_supervisor(tmp_path, FakeTmux())  # default out is a plain StringIO
    view = supervisor.RowView(topic="wk", repo="/r", tmux="s", ctx=50, status="working")
    line = row_line(render_of(sup, [view]), "wk")
    assert "\x1b[3" not in line
    assert line.split() == ["working", "wk", "s", "50%", "r"]


def test_color_wraps_the_whole_line_so_alignment_is_preserved(tmp_path):
    """The ANSI codes wrap the padded line, never a cell — so once stripped, a green
    working row aligns to the same columns as an uncolored one."""
    sup = make_supervisor(tmp_path, FakeTmux(), out=TtyOut())
    views = [
        supervisor.RowView(topic="alpha", repo="/r", tmux="s1", ctx=50, status="working"),
        supervisor.RowView(topic="beta", repo="/r", tmux="s2", ctx=None, status="unassigned"),
    ]
    out = render_of(sup, views)
    green = row_line(out, "alpha")
    plain = row_line(out, "beta")
    stripped = green[len(GREEN) : -len(RESET)]
    # Both data rows share the Topic column start, proving the color did not shift
    # the padded columns.
    assert stripped.index("alpha") == plain.index("beta")


# --------------------------------------------------------------------------- #
# The Status-cell note is elided so a session-authored value (a long `blocked:`
# reason) cannot blow up the column width or break the row (maintainer 2026-07-16).
# --------------------------------------------------------------------------- #


def test_render_elides_an_over_long_note_so_the_table_does_not_blow_up(tmp_path):
    """A `blocked:` reason can be arbitrarily long; the Status cell must flatten + truncate
    it with an ellipsis so it never blows up the column (a 705-byte completion summary
    written to a state file broke the live table)."""
    sup = make_supervisor(tmp_path, FakeTmux())
    huge = "arc COMPLETE " + "x" * 500
    view = supervisor.RowView(topic="el", repo="/r", tmux="s", ctx=50, status="working", note=huge)
    out = render_of(sup, [view])
    line = row_line(out, "el")
    assert line.startswith("working (")
    assert "…" in line
    assert "x" * 500 not in out  # the raw blob never reaches the table
    assert max(len(ln) for ln in out.splitlines()) < 160  # no cell blows the line up


def test_render_flattens_a_multiline_note_onto_one_row(tmp_path):
    """A newline in the note must not split the row across lines — it is collapsed to spaces."""
    sup = make_supervisor(tmp_path, FakeTmux())
    view = supervisor.RowView(
        topic="ml", repo="/r", tmux="s", ctx=50, status="working", note="alpha\nbeta\ngamma"
    )
    line = row_line(render_of(sup, [view]), "ml")
    assert "working (alpha beta gamma)" in line


def test_render_leaves_a_short_note_intact(tmp_path):
    """Elision only fires past the cap — a normal `working (background shell)` note renders
    verbatim, no ellipsis."""
    sup = make_supervisor(tmp_path, FakeTmux())
    view = supervisor.RowView(
        topic="sh", repo="/r", tmux="s", ctx=50, status="working", note="background shell"
    )
    line = row_line(render_of(sup, [view]), "sh")
    assert "working (background shell)" in line
    assert "…" not in line


def test_needs_you_block_elides_an_over_long_reason(tmp_path):
    """The NEEDS YOU block embeds the reason too; a huge `blocked:` reason is capped there
    (the full text is in the pane the jump command points at)."""
    sup = make_supervisor(tmp_path, FakeTmux())
    huge = "blocked reason " + "y" * 400
    view = supervisor.RowView(
        topic="bh", repo="/r", tmux="s", ctx=None, status="blocked:human", note=huge
    )
    needs = render_of(sup, [view]).split("NEEDS YOU")[1]
    assert "…" in needs
    assert "y" * 400 not in needs
    assert "jump: tmux switch-client -t s" in needs  # the pane pointer is still there


def test_blocked_human_alert_caps_an_over_long_reason(tmp_path, capsys):
    """The edge-triggered `alert` (daemon.log line) also caps the reason — a 705-byte
    `blocked:` dump must not become a 705-byte log line."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    declare(repo, topic, "blocked: " + "y" * 400)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path, fake)
    sup.evaluate(mapped_track(repo, topic, session), act=True)
    err = capsys.readouterr().err
    assert "blocked on human:" in err
    assert "…" in err
    assert "y" * 400 not in err


# --------------------------------------------------------------------------- #
# The log is an EVENT HISTORY: timestamped, and edge-triggered (not per-tick).
# --------------------------------------------------------------------------- #


def test_alert_is_edge_triggered_not_repeated_every_tick(tmp_path):
    """A track blocked overnight used to log ~3,000 identical lines, burying the history
    the bottom pane reads to answer "what happened?". One line per condition ENTERED."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    declare(repo, topic, "blocked: needs a human")
    sup = make_supervisor(tmp_path, fake)
    track = mapped_track(repo, topic, session)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        for _ in range(5):  # five ticks of the SAME unchanged condition
            assert sup.evaluate(track, act=True).status == "blocked:human"
    surfaced = [ln for ln in err.getvalue().splitlines() if "overseer[SURFACE]" in ln]
    assert len(surfaced) == 1, surfaced


def test_alert_re_arms_after_the_track_recovers(tmp_path):
    """Edge-triggering must not SWALLOW a genuine re-entry: once a track goes healthy, the
    next time it goes bad it reports afresh."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    # 90% remaining: comfortably above the warn threshold, so the recovered tick is
    # healthy — `idle-with-context-left` (idle with room, so nudged to keep going). It is
    # NOT an attention status, so the edge-triggered alert still re-arms.
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=90))
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    fake.serve(session=f"{session}-supervisor", repo=repo, capture=idle_capture(ctx=90), cmd="node")
    sup = make_supervisor(tmp_path, fake)
    track = mapped_track(repo, topic, session)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        state = declare(repo, topic, "blocked: first")
        assert sup.evaluate(track, act=True).status == "blocked:human"
        state.unlink()  # the human answered → the track is healthy again
        assert sup.evaluate(track, act=True).status == "idle-with-context-left"
        declare(repo, topic, "blocked: first")  # blocks AGAIN on the same reason
        assert sup.evaluate(track, act=True).status == "blocked:human"
    surfaced = [ln for ln in err.getvalue().splitlines() if "overseer[SURFACE]" in ln]
    assert len(surfaced) == 2, surfaced  # entered, recovered, entered again


def test_alert_reports_again_when_the_reason_changes(tmp_path):
    """Edge-triggering is on the CONDITION, not merely on the status: a track that stays
    blocked for a DIFFERENT reason is a new event and must be reported."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    sup = make_supervisor(tmp_path, fake)
    track = mapped_track(repo, topic, session)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        declare(repo, topic, "blocked: reason one")
        sup.evaluate(track, act=True)
        declare(repo, topic, "blocked: reason two")
        sup.evaluate(track, act=True)
    surfaced = [ln for ln in err.getvalue().splitlines() if "overseer[SURFACE]" in ln]
    assert len(surfaced) == 2, surfaced
    assert "reason one" in surfaced[0]
    assert "reason two" in surfaced[1]
