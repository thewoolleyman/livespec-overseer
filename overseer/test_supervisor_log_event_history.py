"""Beside-tests for supervisor.py — log event history.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import datetime
import io as _io
import json

import pytest
import registry
from test_supervisor_builders import (
    adopt_sup,
    codex_idle_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_malformed_state_alert_is_edge_triggered_while_danger_repeats(*, tmp_path):
    """A malformed state file can coexist with danger/non-response. The alerts are two
    independent conditions, so neither may re-arm the other every tick."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=13))
    declare(repo=repo, topic=topic, value="working: still handling it")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        for _ in range(3):
            assert sup.evaluate(track=track, act=True).status == "danger"

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    malformed = [event for event in events if "MALFORMED state file" in str(event["message"])]
    not_responding = [event for event in events if "NOT RESPONDING" in str(event["message"])]
    assert len(malformed) == 1, events
    assert len(not_responding) == 1, events


def test_log_lines_are_timestamped(*, tmp_path):
    """The bottom pane answers "WHEN did this happen?" from the log, so every line must
    carry its own time — the alert lines used to carry none."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    declare(repo=repo, topic=topic, value="blocked: x")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    event = json.loads(err.getvalue().splitlines()[0])
    stamp = str(event["ts"])
    # Parses as the ISO-8601 instant the daemon stamps its table with.
    assert datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))


# --------------------------------------------------------------------------- #
# The tmux window-name badge (the only surface visible from ANOTHER session).
# --------------------------------------------------------------------------- #


def test_window_name_is_badged_with_the_attention_count(*, tmp_path):
    """tmux renders the window name in the status bar of whatever session the operator is
    attached to — so a track that wants them is seen without switching panes."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    declare(repo=repo, topic=topic, value="blocked: needs you")
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, own_pane="%7", watch_set_path=None, watch_repos=[str(repo)]
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="t",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.tick(act=True)
    assert fake.window_name == "overseer(1!)"


def test_window_name_drops_the_badge_when_nothing_needs_attention(*, tmp_path):
    """The badge must CLEAR, or it becomes another stale indicator — the very bug."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=90))  # healthy
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, own_pane="%7", watch_set_path=None, watch_repos=[str(repo)]
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="t",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.tick(act=True)
    assert fake.window_name == "overseer"


def test_window_name_is_only_rewritten_when_the_count_changes(*, tmp_path):
    """A tmux call every tick for an unchanged name is pure noise."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    declare(repo=repo, topic=topic, value="blocked: x")
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, own_pane="%7", watch_set_path=None, watch_repos=[str(repo)]
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="t",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        for _ in range(4):
            sup.tick(act=True)
    assert fake.renames() == ["overseer(1!)"]  # written ONCE, not four times


def test_read_only_list_never_renames_the_window(*, tmp_path):
    """`list` is advertised read-only, so printing a table must not rename the
    maintainer's window as a side effect."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    declare(repo=repo, topic=topic, value="blocked: x")
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, own_pane="%7", watch_set_path=None, watch_repos=[str(repo)]
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="t",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.tick(act=False)
    assert fake.renames() == []
    assert fake.window_name is None


def test_never_seen_is_unassigned_but_once_seen_is_session_gone(*, tmp_path):
    """THE distinction between the two, maintainer-declared 2026-07-17:

        "KEEP session-gone if you've ever seen the session, only use unassigned if
         you've never seen it"

    Both rows mean "no session here right now" — what separates them is whether we have
    EVER seen one. The MAPPING ROW is exactly that memory (adopt writes it when it first
    sees a session), which is why a dead mapping is KEPT, not pruned: pruning it would
    erase the very evidence that distinguishes these two states and silently demote a
    died-on-us track to look like one that never started.

    Neither row names a tmux session: `unassigned` never had one, and `session-gone`
    must not point at the bare terminal its session left behind.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()  # no tmux sessions exist at all
    sup = adopt_sup(tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={})

    # NEVER seen: a discovered plan with no mapping row.
    never = registry.Track.make_unassigned(repo=str(repo), topic=topic)
    never_view = sup.evaluate(track=never, act=True)
    assert never_view.status == "unassigned"
    assert never_view.tmux is None

    # SEEN once: a mapping row exists, but the session is not in any tmux now.
    session = registry.tmux_id(repo=str(repo), topic=topic)
    gone_view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert gone_view.status == "session-gone"
    assert gone_view.tmux is None

    # The two are distinguishable ONLY by the mapping row, so it must survive.
    assert never_view.status != gone_view.status


# --------------------------------------------------------------------------- #
# Codex restart safety — a FORWARD guard, deliberately written BEFORE the wiring.
# --------------------------------------------------------------------------- #


def test_an_unadopted_codex_looking_pane_is_never_restarted(*, tmp_path):
    """An UNADOPTED pane is never restarted, however much it looks like codex.

    A `bun` pane NOT proven to be a live codex session (absent from `live_codex`) is
    `session-gone`, and is never restarted or keystroked — even declaring `ready`.

    Any codex ACT (wrap-up, restart) requires the per-tick `live_codex` map to prove a real
    codex session for THIS topic in THIS repo resolves to this pane; `bun` alone is far too
    generic to act on (any bun app reports `bun`). With the map empty, `_pane_is_managed`
    rejects the pane and evaluation returns `session-gone` BEFORE any act branch. This
    guards the loose-`pane_is_codex` footgun — the adopted case (a real restart, via the
    codex command) is covered by the two sibling tests below.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    # A real codex pane: tmux reports `bun` (the launcher), NOT `codex` — the vendored
    # binary is its child. Verified live 2026-07-16 on tmux session `livespec3`.
    fake.serve(session=session, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(
        tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={}
    )  # live_codex EMPTY: not adopted
    declare(repo=repo, topic=topic, value="ready")
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "session-gone"  # unadopted `bun` pane is not ours to act on
    assert not fake.has(method="respawn")  # no restart of a pane we cannot prove is codex
    assert not fake.has(method="paste")  # and nothing keystroked into it either
