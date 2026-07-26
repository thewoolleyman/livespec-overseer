"""Beside-tests for supervisor.py — tmux column annotates.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import _supervisor_view
import codex_sessions
import pytest
import registry
import supervisor
from test_supervisor_builders import (
    GREEN,
    RESET,
    adopt_sup,
    cell_row,
    codex_idle_capture,
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


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_evaluate_derives_codex_runtime_and_annotates_the_tmux_cell(tmp_path):
    """END-TO-END: `evaluate` derives `runtime="codex"` for a track adopted in `live_codex`
    on a `bun` pane, and the rendered tmux cell reads `<session> (codex)`. Sabotage
    target for the Codex arm (route it to `"claude"` and this goes red)."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=codex_idle_capture(ctx=80, topic=topic), cmd="bun")
    sup = make_supervisor(tmp_path, fake)
    # `live_codex` is keyed by (tmux_session, name) so two codex sessions can share a tmux
    # session (fix a24e3e13) — key this fixture the same way the other codex tests do.
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=4242, name=topic, cwd=str(repo), session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
        )
    }
    view = sup.evaluate(mapped_track(repo, topic, session), act=False)
    assert view.runtime == "codex"
    line = cell_row(render_of(sup, [view]), topic)
    assert f"{session} (codex)" in line


def test_evaluate_leaves_runtime_none_for_a_session_gone_row(tmp_path):
    """A track whose mapped tmux session is gone (and no live Claude for the topic) is
    `session-gone`: no pane, so no runtime — the rendered tmux cell is a bare `—`."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()  # the mapped session is NOT served → session_exists False
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()  # empty registry → no live Claude anywhere → session-gone
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {})
    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "session-gone"
    assert view.tmux is None
    assert view.runtime is None
    line = cell_row(render_of(sup, [view]), topic)
    assert "—" in line
    assert "(claude)" not in line and "(codex)" not in line


def test_evaluate_leaves_runtime_none_for_an_unassigned_row(tmp_path):
    """An unassigned plan (no mapping) never has a pane, so it carries no runtime — the
    `unassigned` branch returns before any runtime is derived."""
    repo, topic = make_plan(tmp_path)
    sup = make_supervisor(tmp_path, FakeTmux())
    track = registry.Track.make_unassigned(repo=str(repo), topic=topic)
    view = sup.evaluate(track, act=True)
    assert view.status == "unassigned"
    assert view.runtime is None


def test_attention_block_annotates_the_tmux_coordinate_with_the_runtime(tmp_path):
    """The NEEDS YOU block's `tmux:` coordinate is annotated the SAME way the table is,
    so the operator knows whether they are jumping into a Claude or Codex pane. The jump
    command itself stays the bare session name (`tmux switch-client -t` takes no runtime)."""
    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    view = supervisor.RowView(
        topic="autonomous-mode",
        repo="/data/projects/livespec",
        tmux="livespec-autonomous-mode",
        ctx=41,
        status="blocked:human",
        note="waiting on a decision",
        runtime="codex",
    )
    out = render_of(sup, [view])
    assert "tmux: livespec-autonomous-mode (codex)" in out
    assert "jump: tmux switch-client -t livespec-autonomous-mode" in out  # bare name


def test_attention_block_lists_a_blocked_track_with_its_jump_command(tmp_path):
    """The block must be a SUFFICIENT handover on its own: what is stuck, and where to go."""
    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    views = [
        supervisor.RowView(
            topic="autonomous-mode",
            repo="/data/projects/livespec",
            tmux="livespec-autonomous-mode",
            ctx=41,
            status="blocked:human",
            note="waiting on a cost-gate decision",
        )
    ]
    out = render_of(sup, views)
    assert "NEEDS YOU (1):" in out
    # LABELED coordinates, tmux INCLUDED — the operator must not have to guess which
    # unlabeled token is the topic vs the repo vs the session to jump to.
    assert "topic: autonomous-mode | tmux: livespec-autonomous-mode | repo: livespec" in out
    assert "waiting on a cost-gate decision" in out
    assert "jump: tmux switch-client -t livespec-autonomous-mode" in out


def test_attention_block_says_nothing_when_every_track_is_healthy(tmp_path):
    """An empty block must SAY it is empty — silence is ambiguous with a broken render."""
    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    views = [
        supervisor.RowView(topic="a", repo="/r", tmux="s1", ctx=80, status="idle"),
        supervisor.RowView(topic="b", repo="/r", tmux="s2", ctx=60, status="working"),
    ]
    out = render_of(sup, views)
    assert "NEEDS YOU: nothing" in out


def test_attention_block_excludes_unassigned_plans(tmp_path):
    """`unassigned` is startable, not stuck — and there are dozens. Including them would
    bury the rows that genuinely want the operator, which is the bug this block fixes."""
    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    views = [
        supervisor.RowView(topic=f"plan{i}", repo="/r", tmux=None, ctx=None, status="unassigned")
        for i in range(20)
    ] + [supervisor.RowView(topic="stuck", repo="/r", tmux="s", ctx=9, status="danger")]
    out = render_of(sup, views)
    assert "NEEDS YOU (1):" in out  # the ONE danger row, not 21
    assert "stuck" in out.split("NEEDS YOU")[1]
    assert "plan0" not in out.split("NEEDS YOU")[1]


def test_attention_block_includes_a_malformed_state_file(tmp_path):
    """A malformed declaration has no status of its own (it rides on the note) and is
    fail-closed — it needs a human, so it must appear in the block."""
    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    views = [
        supervisor.RowView(
            topic="t", repo="/r", tmux="s", ctx=50, status="idle", note="BAD state file: 'redy'"
        )
    ]
    out = render_of(sup, views)
    assert "NEEDS YOU (1):" in out
    assert "BAD state file" in out


def test_needs_attention_predicate_covers_every_attention_status():
    """Guards the membership test itself, so a new attention status cannot be added to the
    tuple without the block picking it up."""
    for status in supervisor.ATTENTION_STATUSES:
        row = supervisor.RowView(topic="t", repo="/r", tmux="s", ctx=1, status=status)
        assert supervisor.needs_attention(row) is True
    for status in ("idle", "working", "warned", "winding-down", "settling", "unassigned"):
        row = supervisor.RowView(topic="t", repo="/r", tmux="s", ctx=99, status=status)
        assert supervisor.needs_attention(row) is False


_YELLOW = "\x1b[33m"
_RED = "\x1b[31m"


def test_tty_render_tints_working_rows_green(tmp_path):
    sup = make_supervisor(tmp_path, FakeTmux(), out=TtyOut())
    view = supervisor.RowView(topic="wk", repo="/r", tmux="s", ctx=50, status="working")
    line = row_line(render_of(sup, [view]), "wk")
    assert line.startswith(GREEN)
    assert line.endswith(RESET)


def test_tty_render_tints_idle_and_waiting_rows_yellow(tmp_path):
    """Idle and `blocked:human` (waiting on a human decision) both read yellow — a
    human should glance at them (maintainer feature request 2026-07-15)."""
    for status in ("idle", "idle-with-context-left", "blocked:human", "warned", "danger"):
        sup = make_supervisor(tmp_path, FakeTmux(), out=TtyOut())
        view = supervisor.RowView(topic="yl", repo="/r", tmux="s", ctx=15, status=status)
        line = row_line(render_of(sup, [view]), "yl")
        assert line.startswith(_YELLOW), status
        assert line.endswith(RESET), status


def test_tty_render_tints_broken_rows_red(tmp_path):
    """`session-gone` is still the "broken" red — a plan we have seen running is no
    longer in any tmux. `not-claude` is DELETED and must never come back."""
    sup = make_supervisor(tmp_path, FakeTmux(), out=TtyOut())
    view = supervisor.RowView(topic="br", repo="/r", tmux=None, ctx=None, status="session-gone")
    line = row_line(render_of(sup, [view]), "br")
    assert line.startswith(_RED)


def test_not_claude_is_gone_from_every_surface(tmp_path):
    """One guard so the jargon cannot creep back via the colour map or attention list."""
    assert "not-claude" not in _supervisor_view._STATUS_COLOR
    assert "not-claude" not in supervisor.ATTENTION_STATUSES
    assert "session-gone" in supervisor.ATTENTION_STATUSES  # still attention
