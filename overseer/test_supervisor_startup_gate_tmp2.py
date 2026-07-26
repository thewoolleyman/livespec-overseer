"""Beside-tests for supervisor.py — startup gate tmp2.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    cell_row,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    render_of,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_streaming_pane_is_working_not_idle(tmp_path):
    """LIVE-EXERCISE regression: the real TUI shows NO persistent busy spinner
    while streaming, so a single frame looks idle. The settled-delta must catch
    the change between captures and classify it `working` — never injecting
    despite ctx below threshold."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo)
    fake.panes[session] = [
        idle_capture(ctx=40, body="line one"),
        idle_capture(ctx=40, body="line one two"),
        idle_capture(ctx=40, body="line one two three"),
    ]
    sup = make_supervisor(tmp_path, fake, watch_repos=[str(repo)])
    registry.append_mapping(track=mapped_track(repo, topic, session), store_path=sup.store_path)
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    assert not fake.has(method="paste")  # never injected despite ctx 40 <= the default 50


def test_settled_idle_pane_still_injects(tmp_path):
    """Counterpart: an idle pane NOT changing between the two settled captures
    (same frame every call) is still eligible to inject at/below threshold."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=40)
    )  # identical frames → settled
    sup = make_supervisor(tmp_path, fake, watch_repos=[str(repo)])
    registry.append_mapping(track=mapped_track(repo, topic, session), store_path=sup.store_path)
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "warned"
    assert fake.has(method="paste")  # settled idle + low ctx → wrap-up injected


def test_submit_prompt_resends_enter_until_box_clears(tmp_path):
    """LIVE-EXERCISE regression: a freshly-respawned session can DROP the first
    Enter while still drawing its welcome screen. `_submit_prompt` re-sends Enter
    until the empty box returns, and returns True on success."""
    fake = FakeTmux()
    session = "s"
    fake.sessions.add(session)
    not_ready = "❯ read handoff.md and follow it\n" + ("─" * 40) + "\nwelcome screen\n"
    fake.panes[session] = [not_ready, not_ready, idle_capture()]  # 3rd frame = empty box
    sup = make_supervisor(tmp_path, fake)
    assert sup._submit_prompt(target=session, text="read handoff.md and follow it") is True
    enters = [c for c in fake.calls if c[0] == "keys" and c[2] == "Enter"]
    assert len(enters) == 3  # dropped twice, submitted on the third
    assert fake.paste_texts() == ["read handoff.md and follow it"]  # pasted once


def test_submit_prompt_returns_false_on_failed_paste(tmp_path):
    """B5: a failed bracketed paste is a hard False — never a false 'submitted'."""
    fake = FakeTmux()
    session = "s"
    fake.sessions.add(session)
    fake.panes[session] = idle_capture()
    fake.paste_ok = False
    sup = make_supervisor(tmp_path, fake)
    assert sup._submit_prompt(target=session, text="hello") is False
    assert not any(c[0] == "keys" for c in fake.calls)  # no Enter sent after a failed paste


def test_submit_prompt_single_enter_when_already_ready(tmp_path):
    """On a steady session (empty box every capture) a single Enter suffices."""
    fake = FakeTmux()
    session = "s"
    fake.sessions.add(session)
    fake.panes[session] = idle_capture()  # empty box → input_box_ready True at once
    sup = make_supervisor(tmp_path, fake)
    assert sup._submit_prompt(target=session, text="hello") is True
    enters = [c for c in fake.calls if c[0] == "keys" and c[2] == "Enter"]
    assert len(enters) == 1


def test_table_header_column_order(tmp_path):
    """Column order is Status · Topic · tmux · Ctx% · Repo — Status leads, the column the
    operator scans first (maintainer 2026-07-15)."""
    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    out = render_of(sup, [])
    header = next(ln for ln in out.splitlines() if "Status" in ln and "Topic" in ln)
    assert header.split() == ["Status", "Topic", "tmux", "Ctx%", "Repo"]


def test_render_header_includes_pinned_release_version(tmp_path):
    """The live-state header carries the release-please maintained app semver."""
    assert hasattr(supervisor, "APP_VERSION")
    assert supervisor.APP_VERSION.count(".") == 2

    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    out = render_of(sup, [])

    first_line = out.splitlines()[0].removeprefix("\x1b[3J\x1b[2J\x1b[H")
    assert first_line.endswith(f" — 0 track(s) - {supervisor.APP_VERSION}")


def test_table_row_cells_follow_the_header_order(tmp_path):
    """A rendered row places each value under its (reordered) header."""
    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    view = supervisor.RowView(
        topic="mytopic", repo="/data/projects/livespec", tmux="sess", ctx=42, status="idle"
    )
    out = render_of(sup, [view])
    row = next(ln for ln in out.splitlines() if "mytopic" in ln)
    assert row.split() == ["idle", "mytopic", "sess", "42%", "livespec"]


def test_tmux_column_annotates_a_claude_row_with_its_runtime(tmp_path):
    """A row with a live Claude pane renders its tmux cell as `<tmux> (claude)`."""
    sup = make_supervisor(tmp_path, FakeTmux())
    view = supervisor.RowView(
        topic="wk", repo="/r", tmux="livespec", ctx=50, status="working", runtime="claude"
    )
    line = cell_row(render_of(sup, [view]), "wk")
    assert "livespec (claude)" in line


def test_tmux_column_annotates_a_codex_row_with_its_runtime(tmp_path):
    """A row with a live Codex pane renders its tmux cell as `<tmux> (codex)`."""
    sup = make_supervisor(tmp_path, FakeTmux())
    view = supervisor.RowView(
        topic="cx", repo="/r", tmux="livespec1", ctx=70, status="idle", runtime="codex"
    )
    line = cell_row(render_of(sup, [view]), "cx")
    assert "livespec1 (codex)" in line


def test_tmux_column_is_a_bare_dash_with_no_runtime_for_no_pane_rows(tmp_path):
    """`unassigned` and `session-gone` have no live session — their tmux cell is a bare
    `—`, never a `(...)` annotation (both carry `tmux=None` and `runtime=None`)."""
    sup = make_supervisor(tmp_path, FakeTmux())
    for topic, status in (("un", "unassigned"), ("sg", "session-gone")):
        view = supervisor.RowView(topic=topic, repo="/r", tmux=None, ctx=None, status=status)
        line = cell_row(render_of(sup, [view]), topic)
        assert "—" in line
        assert "(" not in line  # no runtime annotation, and no note to add parens


def test_tmux_runtime_annotation_preserves_column_alignment(tmp_path):
    """Column invariant 1: the tmux column width is computed from the ANNOTATED cell
    (`livespec (claude)`), so a short bare-`—` cell is padded to that same width and the
    following Repo column still lines up."""
    sup = make_supervisor(tmp_path, FakeTmux())
    views = [
        supervisor.RowView(
            topic="alpha",
            repo="/x/repoZZ",
            tmux="livespec",
            ctx=50,
            status="working",
            runtime="claude",
        ),
        supervisor.RowView(topic="beta", repo="/x/repoZZ", tmux=None, ctx=60, status="unassigned"),
    ]
    out = render_of(sup, views)
    wide = cell_row(out, "alpha")  # tmux cell "livespec (claude)" sets the column width
    narrow = cell_row(out, "beta")  # tmux cell "—" padded to that same width
    # Both rows share a repo slug; if the column is aligned it starts at the same index.
    assert wide.index("repoZZ") == narrow.index("repoZZ")


def test_evaluate_derives_claude_runtime_and_annotates_the_tmux_cell(tmp_path):
    """END-TO-END: `evaluate` derives `runtime="claude"` for a live Claude track (no
    `live_codex` entry → `is_codex` False), and the rendered tmux cell reads `<session>
    (claude)`. Sabotage target: drop `runtime=runtime` on evaluate's final RowView and
    the cell falls back to the bare session name → this goes red."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=80))  # a live Claude idle pane
    sup = make_supervisor(tmp_path, fake)
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=False)
    assert view.runtime == "claude"
    line = cell_row(render_of(sup, [view]), topic)
    assert f"{session} (claude)" in line
