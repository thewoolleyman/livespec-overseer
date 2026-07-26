"""Tests for supervisor.py — the daemon state machine, injection, restart, GC.

Run: ``uv run pytest .claude/skills/overseer/ -q``. A FAKE tmux object supplies
canned pane captures / process-identity / session existence; NO real tmux runs.
The adversarial-critical behaviors are covered: state precedence (busy/gate/
blocked suppress injection), stamp-before-paste, the restart interlock firing
ONLY on marker-valid + not-busy + idle, auto-link refusing a cross-repo session,
archive-GC dropping an archived row, ctx-unknown never injecting — PLUS the
2026-07-13 adversarial code-review blocker fixes (B1..B8): the identity gate,
failure propagation, marker/round lifecycle, read-only list, and the start guard.
"""

import pytest
import registry
from test_supervisor_builders import (
    WRAPUP_SENTINEL,
    adopt_sup,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# State precedence: busy / gate / blocked SUPPRESS injection.
# --------------------------------------------------------------------------- #


def test_busy_suppresses_injection(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture="running... esc to interrupt\n  Ctx: 40% left\n")
    sup = make_supervisor(tmp_path, fake)
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    assert not fake.has(method="paste")  # busy must suppress the wrap-up injection


def test_structured_gate_suppresses_injection(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture="Do you want to proceed?\n❯ 1. Yes\n  2. No\n  Ctx: 40% left\n",
    )
    sup = make_supervisor(tmp_path, fake)
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "blocked:human"
    assert not fake.has(method="paste")


def test_blocked_marker_suppresses_injection(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    declare(repo, topic, "blocked: waiting on schema call")
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=40)
    )  # idle+low ctx but blocked marker
    sup = make_supervisor(tmp_path, fake)
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "blocked:human"
    assert view.note == "waiting on schema call"
    assert not fake.has(method="paste")


# --------------------------------------------------------------------------- #
# B3 identity gate: NEVER keystroke into a shell / wrong-repo pane.
# --------------------------------------------------------------------------- #


def test_shell_pane_never_pastes(tmp_path):
    """A tracked session that dropped to a shell (pane_current_command != claude)
    must get NO paste — even at low ctx with an idle-looking old box in scrollback
    (B3: else the wrap-up executes in the shell and forges a marker).

    This pins the SAFETY half only. The status LABEL such a pane earns is asserted
    by the `exited to a shell` tests below (it is `session-gone`, not `not-claude`).
    """
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    # Old idle box still on screen + a shell prompt; pane command is now zsh.
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40), cmd="zsh")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()  # isolated + empty: no live Claude anywhere
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {})
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status != "working"  # never mistaken for a live session
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


# --------------------------------------------------------------------------- #
# A pane that EXITED to a shell is a track whose session ENDED — `session-gone`,
# not the alarming `not-claude` (which means the mapping points at a FOREIGN
# pane). The shipped daemon conflated the two: `not-claude` was designed as the
# identity GATE for acts (correct, and unchanged) but was reused as the row
# STATUS, so an ordinary finished track sat red in NEEDS YOU claiming a live tmux
# mapping. Found live 2026-07-16 (fabro-ci-image-factoring → livespec1, a bare
# zsh, no live Claude anywhere).
# --------------------------------------------------------------------------- #


def test_pane_exited_to_shell_is_session_gone(tmp_path):
    """The mapped tmux session is ALIVE but its Claude EXITED, leaving a bare shell,
    and no Claude for the topic is live anywhere → the track's session is GONE."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40), cmd="zsh")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()  # no live Claude for the topic
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {})
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "session-gone"
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


def test_no_managed_pane_row_never_names_a_tmux_session(tmp_path):
    """The `tmux` cell means "the tmux session holding this track" — so a track with
    NO session there must not name one (maintainer-declared 2026-07-16: "it shouldn't
    display the session name; the session doesn't exist in that panel anymore").

    A leftover MAPPING to a tmux session that now holds a bare shell is not a session:
    rendering `livespec1` there asserted a live session that did not exist. The cell
    goes empty (like `unassigned`); `session-gone` alone carries "this WAS mapped and
    is now dead", and `alert` degrades to "no live tmux session" with no jump command
    (there is nowhere to jump).
    """
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40), cmd="zsh")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {})
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "session-gone"
    assert view.tmux is None


def test_missing_tmux_session_also_never_names_a_tmux_session(tmp_path):
    """Same rule via the other route into the helper — the mapped tmux session is gone
    outright, so there is even less of a session to name."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # session never added → session_exists False
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {})
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "session-gone"
    assert view.tmux is None


def test_a_foreign_pane_is_session_gone_not_a_status_of_its_own(tmp_path):
    """A live Claude in a DIFFERENT repo is not "not-claude" — from this plan's point of
    view the fact is identical to a bare shell: its session is NOT IN THIS TMUX. The plan
    was assigned to something once, so it is `session-gone`.

    The mapping ROW is kept — it is the memory of having seen the session, which is what
    separates `session-gone` from `unassigned` (maintainer-declared 2026-07-17: "KEEP
    session-gone if you've ever seen the session, only use unassigned if you've never
    seen it"). And no dead terminal is named: tmux is None.
    """
    repo, topic = make_plan(tmp_path)
    other = tmp_path / "elsewhere"
    other.mkdir()
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=other, capture=idle_capture(ctx=40))  # live claude, wrong repo
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {})
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "session-gone"
    assert view.tmux is None  # never name the pane it is wrongly pointed at
    assert not fake.has(method="paste")  # the identity gate still guards every act


def test_pane_exited_to_shell_with_live_claude_outside_tmux_is_live_outside_tmux(tmp_path):
    """The pane dropped to a shell BUT the topic's Claude is alive OUTSIDE tmux.

    The live-outside-tmux fallback was wired ONLY into the missing-tmux-session
    branch, so this case reported `not-claude` and hid a live session behind an
    alarm. Both no-managed-pane paths must consult it.
    """
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40), cmd="zsh")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    # Live registry session for the topic whose pid walks up to NO tmux pane.
    write_session(sessions_dir, 100, name=topic, cwd=str(repo), status="busy")
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {100: "pt"})
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "live-outside-tmux"
    assert view.note is not None and "OUTSIDE tmux" in view.note
    assert not fake.has(method="paste")


def test_identity_rechecked_before_acting_catches_shell(tmp_path):
    """Codex re-review #1: identity passes the TOP gate but the pane exits to a
    shell during the capture+settle window — the re-check immediately before
    acting must catch it (not-claude, no paste). The fake returns `node` at the
    top gate then `zsh` at the re-check."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=40)
    )  # idle, low ctx → would inject
    fake.cmds[session] = ["node", "zsh"]  # claude at top gate, shell at the re-check
    sup = make_supervisor(tmp_path, fake)
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    # `settling`: the pane changed UNDER US mid-tick — wait and re-read. The next tick's
    # top gate classifies the settled truth. The SAFETY property (no paste into the
    # shell) is what this test exists for and is unchanged.
    assert view.status == "settling"
    assert not fake.has(method="paste")  # never pasted into the shell


# --------------------------------------------------------------------------- #
# warned: stamp is written BEFORE the paste; ctx-unknown never injects.
# --------------------------------------------------------------------------- #


def test_warned_writes_stamp_before_pasting(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=40)
    )  # below the default warn threshold (50)
    stamp_path = str(tmp_path / "stamps.json")
    seen = []
    fake.on_paste = lambda _s, _t: seen.append(
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=stamp_path)
    )
    sup = make_supervisor(tmp_path, fake)
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "warned"
    assert fake.paste_texts() and WRAPUP_SENTINEL in fake.paste_texts()[0]
    assert seen == [1000.0]  # stamp written BEFORE the paste, at now()==1000.0
    assert ("keys", session, "Enter") in fake.calls
