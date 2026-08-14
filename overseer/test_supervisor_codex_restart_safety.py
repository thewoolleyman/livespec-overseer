"""Beside-tests for supervisor.py — codex restart safety.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import codex_sessions
import pytest
import registry
import signals
import supervisor
from _supervisor_launch import canonical_codex_session_id
from test_supervisor_builders import (
    adopt_codex_ready,
    adopt_sup,
    assert_no_tmux_scoping,
    codex_busy_capture,
    codex_idle_capture,
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


def test_an_adopted_codex_track_declaring_ready_is_restarted_with_the_codex_command(*, tmp_path):
    """A Codex track is now a FULL CITIZEN (maintainer-declared 2026-07-17): its own `ready`
    IS honoured — but via `codex resume <id>`, NEVER the claude launch command.

    This replaces the former monitor-only refusal. `_do_restart` runtime-dispatches: a Codex
    track routes to `_do_codex_restart`, which respawns `codex resume <session-id> "<kick>"`
    (reattaches the SAME rollout → adoptability survives; the kick auto-submits). The
    destructive bug this daemon can have is aiming `claude -n <topic>` at a codex pane; the
    routing prevents it and its sibling below pins it by sabotage.
    """
    repo, topic, session, session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "restarting"  # its own `ready` is honoured, not refused
    respawns = [c for c in fake.calls if c[0] == "respawn"]
    assert len(respawns) == 1
    command = respawns[0][3]
    assert_no_tmux_scoping(command=command)
    assert "codex resume " in command  # the CODEX command, not claude
    assert session_id in command  # resumes the SAME session by id → adoptability survives
    # Autonomy parity with the Claude path's `--dangerously-skip-permissions`: without this
    # the resumed codex stalls at an interactive approval picker and the restart is not
    # hands-off (maintainer-declared 2026-07-17).
    assert "--dangerously-bypass-approvals-and-sandbox" in command
    assert not fake.has(method="paste")  # the kick is the resume ARGUMENT — no separate paste
    # THE ROUND IS CLOSED on success — and this is the high-consequence property. The await
    # (`_await_pane(pane_is_codex)`, which needs FakeTmux to model the respawn as a codex
    # pane) must succeed AND `_clear_state` must delete the marker, or a stale `ready` would
    # respawn-KILL the just-resumed codex EVERY tick — a destructive loop. Pin both: the
    # state file is gone, and a SECOND tick issues no second respawn.
    assert signals.read_state(repo=str(repo), topic=topic) is None
    fake.calls.clear()
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert not fake.has(method="respawn")  # no re-restart of the session we just resumed


def test_two_codex_tracks_sharing_a_tmux_session_each_restart_their_own_session(*, tmp_path):
    """#4: two codex sessions live in ONE tmux session, each named for its own plan topic.
    Before the (tmux, name) keying, `self.live_codex` kept ONE CodexSession per tmux session,
    so the SECOND track resolved to the wrong session id (or None) — its restart aimed at
    the wrong rollout and its monitoring was silently lost, invisible in the table. Keyed
    by (tmux, topic), each track's `_do_codex_restart` resolves to ITS OWN session, so each
    respawns `codex resume <its-own-id>`. Sabotage: revert the lookup to `.get(session)`
    and the second track resolves to None → no respawn → this goes red."""
    repo, topic_a = make_plan(tmp_path=tmp_path, topic="alpha")
    _, topic_b = make_plan(tmp_path=tmp_path, topic="beta")
    shared = "shared-tmux"
    fake = FakeTmux()
    fake.serve(session=shared, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    id_a = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
    id_b = "019f548d-6071-7893-9c2e-472cce81da02"
    sup.live_codex = {
        (shared, topic_a): codex_sessions.CodexSession(
            pid=10, name=topic_a, cwd=str(repo), session_id=id_a
        ),
        (shared, topic_b): codex_sessions.CodexSession(
            pid=20, name=topic_b, cwd=str(repo), session_id=id_b
        ),
    }

    def keep_seeded_codex_sessions() -> None:
        sup.live_codex = {
            (shared, topic_a): codex_sessions.CodexSession(
                pid=10, name=topic_a, cwd=str(repo), session_id=id_a
            ),
            (shared, topic_b): codex_sessions.CodexSession(
                pid=20, name=topic_b, cwd=str(repo), session_id=id_b
            ),
        }

    sup._refresh_codex_sessions = keep_seeded_codex_sessions
    target = fake.pane_id(session=shared)
    with contextlib.redirect_stderr(_io.StringIO()):
        sup._do_codex_restart(
            track=mapped_track(repo=repo, topic=topic_a, session=shared), target=target
        )
        sup._do_codex_restart(
            track=mapped_track(repo=repo, topic=topic_b, session=shared), target=target
        )
    respawn_cmds = [c[3] for c in fake.calls if c[0] == "respawn"]
    assert len(respawn_cmds) == 2  # each track resolved to a live session and respawned
    assert id_a in respawn_cmds[0] and id_b not in respawn_cmds[0]  # track alpha → A's rollout
    assert id_b in respawn_cmds[1] and id_a not in respawn_cmds[1]  # track beta → B's rollout


def test_a_codex_restart_keeps_the_ready_marker_when_the_respawn_fails(*, tmp_path):
    """B5 for the Codex arm: a failed `respawn-pane` must NOT clear the `ready` marker —
    the certification is preserved so the next tick retries, never silently destroyed
    (the Codex twin of `test_restart_keeps_marker_when_respawn_fails`).
    """
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    fake.respawn_ok = False  # the atomic respawn fails
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert signals.read_state(repo=str(repo), topic=topic) is not None  # marker KEPT for retry
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY


def test_a_codex_restart_keeps_the_ready_marker_when_the_pane_never_becomes_codex(*, tmp_path):
    """B5 for the Codex arm: if the respawned pane never becomes a live Codex TUI
    (`_await_pane(pane_is_codex)` fails), the round is NOT closed — the `ready` marker is
    kept so the restart retries. Models the await-fail leg the success test's runtime
    modeling otherwise hides.
    """
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    fake.respawn_yields_codex = False  # respawn succeeds but the pane comes up non-codex
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert signals.read_state(repo=str(repo), topic=topic) is not None  # marker KEPT for retry
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY


def test_a_codex_restart_refuses_an_empty_live_session_id_before_killing_the_pane(*, tmp_path):
    """A blank id would turn `codex resume` into the interactive picker.

    The live proof caught this exact failure shape: treating an empty string as a
    positional id is destructive because respawn-pane first kills the cleanly-ready
    session, then leaves its successor in a picker.  The UUID is therefore an
    interlock input, not merely a command-formatting detail.
    """
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    sup.live_codex[(session, topic)] = codex_sessions.CodexSession(
        pid=4242, name=topic, cwd=str(repo), session_id=""
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup._do_codex_restart(
            track=mapped_track(repo=repo, topic=topic, session=session),
            target=fake.pane_id(session=session),
        )

    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert "no valid UUID" in err.getvalue()
    assert canonical_codex_session_id(value=object()) is None


def test_a_codex_restart_keeps_ready_when_the_resume_kick_is_not_observed(*, tmp_path):
    """A Codex TUI alone is insufficient: the daemon must observe its kick too."""
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    # The fake models a Codex pane after respawn, but it did not receive the argv
    # prompt.  A bare picker has the same runtime process shape, so only the exact
    # kick observation distinguishes it from a useful successor.
    fake.respawn_shows_command = False

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY


def test_a_codex_restart_with_no_post_respawn_live_process_is_not_success(*, tmp_path):
    """A loose Codex-looking foreground command is not enough after respawn."""
    repo, topic, session, _session_id, _fake, sup = adopt_codex_ready(tmp_path=tmp_path)

    def refresh_to_bare_shell() -> None:
        sup.live_codex = {}

    sup._refresh_codex_sessions = refresh_to_bare_shell
    log = _io.StringIO()
    with contextlib.redirect_stderr(log):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert signals.read_state(repo=str(repo), topic=topic) is not None
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert "no live Codex process" in log.getvalue()
    assert f"restarted (codex) {repo}::{topic}" not in log.getvalue()


def test_a_codex_restart_requires_post_respawn_live_process_before_success(*, tmp_path):
    """The success leg refreshes exact live Codex process evidence after respawn."""
    repo, topic, session, session_id, _fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    refreshed = {"called": False}

    def refresh_to_live_codex() -> None:
        refreshed["called"] = True
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=5150, name=topic, cwd=str(repo), session_id=session_id
            )
        }

    sup._refresh_codex_sessions = refresh_to_live_codex
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert refreshed["called"] is True
    assert signals.read_state(repo=str(repo), topic=topic) is None


def test_a_codex_restart_without_recorded_epic_alerts_and_keeps_ready_marker(*, tmp_path):
    """A Codex `ready` with no ledger epic is refused before respawn, preserving retry state."""
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    target = fake.pane_id(session=session)
    track = registry.Track(topic=topic, repo=str(repo), tmux=session, epic=None)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup._do_codex_restart(track=track, target=target)

    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic) is not None
    assert "no plan epic recorded" in err.getvalue()


def test_a_codex_ready_restart_never_issues_the_claude_command(*, tmp_path):
    """THE sabotage-target guard: no respawn for a Codex `ready` track may carry the claude
    launch command. Aimed at a codex pane, `claude --dangerously-skip-permissions -n <topic>`
    REPLACES the codex session with a claude one and destroys it — the one destructive bug
    here.

    Teeth: reroute the restart to the claude command (delete the `is_codex=is_codex` on
    `_do_restart`, or the `if is_codex:` dispatch inside it) and this goes RED, because the
    respawn command becomes `claude …`. The claude launch string must appear in NO respawn.
    """
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    claude_command = supervisor.Supervisor._launch_command(
        track=mapped_track(repo=repo, topic=topic, session=session)
    )
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    respawn_commands = [c[3] for c in fake.calls if c[0] == "respawn"]
    assert respawn_commands  # it WAS restarted (full citizen)...
    assert claude_command not in respawn_commands  # ...but NEVER with the claude command
    assert not any("claude" in c for c in respawn_commands)  # belt-and-suspenders


def test_a_codex_track_below_threshold_gets_the_escalating_wrapup(*, tmp_path):
    """A Codex track below its wind-down threshold receives the SAME escalating wrap-up a
    Claude track does — the change that makes Codex a full citizen. Monitor-only left a
    Codex track a passenger that ran to context exhaustion; now the daemon's only lever
    reaches it too.

    The Codex submit is confirmed by the pane going BUSY after Enter (`is_busy`), not by a
    cleared `❯` box (Codex has none). The capture frames model that: idle for the main read
    + the settle pair, then busy after the paste's Enter.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    # frames: [main, settle-1, settle-2 (== settle-1), pre-paste recheck, post-Enter busy]
    fake.serve(
        session=session,
        repo=repo,
        capture=[codex_idle_capture(ctx=40)] * 4 + [codex_busy_capture(ctx=40)],
        cmd="bun",
    )
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={})
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=4242, name=topic, cwd=str(repo), session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
        )
    }
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "warned"  # below threshold, above danger → warned (not idle)
    assert fake.has(method="paste")  # the wrap-up reached the Codex track
    assert "wind" in " ".join(fake.paste_texts()).lower()  # it IS the wrap-up text


def test_a_codex_approval_gate_suppresses_the_wrapup(*, tmp_path):
    """A Codex approval / directory-trust picker (`› 1.`) must SUPPRESS the wrap-up — the
    paste would otherwise type into the `1/2` chooser. The extended gate-cursor regex
    (`[❯›]`) is what catches the `›` cursor Codex uses (Claude uses `❯`).
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    gate = (
        "Do you trust the contents of this directory?\n"
        "› 1. Yes, continue\n"
        "  2. No, quit\n"
        "  Context 40% left · topic\n"
    )
    fake.serve(session=session, repo=repo, capture=gate, cmd="bun")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={})
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=4242, name=topic, cwd=str(repo), session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
        )
    }
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "blocked:human"  # a gate, not idle
    assert not fake.has(method="paste")  # nothing keystroked into the picker


def test_a_claude_pane_keeps_its_wrapup_when_codex_shares_its_tmux_session(*, tmp_path):
    """A live CLAUDE track must NOT be reclassified as codex just because a codex process
    resolves into the same tmux SESSION (adversarial review, 2026-07-17).

    Reachable, not exotic: `resolve_tmux_session` walks pid ancestry, so a `codex resume
    <topic>` launched from INSIDE this Claude session's own Bash tool lands in its tmux
    session — and the naming convention this work establishes is "codex threads named
    after plan topics", so the name matches the track's topic exactly.

    When `_is_codex_track` was session-scoped (while the Claude identity gate is
    pane-scoped) this Claude track went monitor-only and SILENTLY lost its wrap-up, its
    NOT-RESPONDING alert, and its restart — and `idle` kept it out of NEEDS YOU, so
    nothing surfaced. A live Claude track going quiet is the worst failure this daemon
    can have.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    # A PROVEN live Claude pane (`node`), below its wind-down threshold => must be warned.
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    # ...while a codex session for the SAME topic sits in the SAME tmux session.
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=4242, name=topic, cwd=str(repo), session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
        )
    }
    assert not sup._is_codex_track(
        session=session, repo=str(repo), topic=topic, target=fake.pane_id(session=session)
    )  # pane is node
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "warned"  # the Claude track is still supervised...
    assert fake.has(method="paste")  # ...and still gets the wrap-up, the daemon's only lever
