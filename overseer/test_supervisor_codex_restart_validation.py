"""Beside-tests for supervisor.py — codex restart safety.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io
from dataclasses import replace

import codex_sessions
import pytest
import registry
import signals
import supervisor
from _supervisor_launch import canonical_codex_session_id
from test_supervisor_builders import (
    TEST_EPIC,
    adopt_codex_ready,
    assert_no_tmux_scoping,
    codex_idle_capture,
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


def test_an_adopted_codex_track_declaring_ready_is_restarted_with_a_fresh_codex_session(
    *, tmp_path
):
    """A Codex track is a FULL CITIZEN (maintainer-declared 2026-07-17): its own `ready` IS
    honoured — but via a BRAND-NEW `codex` session, never the claude launch command and
    never a resume of the rollout it just wound down out of.

    The resume arm is the defect this replaced. `codex resume <id>` reattaches the prior
    rollout AND the context it accumulated, so the restart consumed the `ready`
    declaration while handing the successor back the same exhausted window (measured live
    on `fix-git-email` 2026-09-10: one rollout id resumed four times, 50% → 17% remaining,
    until Codex compacted itself). A fresh launch resets the window, which is the whole
    point of a wrap-up restart — and `codex resume` remains correct for CRASH RECOVERY,
    where restoring the interrupted conversation is the goal.

    The destructive bug this daemon can have is aiming `claude -n <topic>` at a codex
    pane; the routing prevents it and its sibling below pins it by sabotage.
    """
    repo, topic, session, session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "restarting"  # its own `ready` is honoured, not refused
    respawns = [c for c in fake.calls if c[0] == "respawn"]
    assert len(respawns) == 1
    command = respawns[0][3]
    assert_no_tmux_scoping(command=command)
    assert command.startswith("codex ")  # the CODEX command, not claude
    assert " resume " not in command  # ...and a FRESH rollout, not the predecessor's
    assert session_id not in command  # the exhausted window is not handed back
    # Autonomy parity with the Claude path's `--dangerously-skip-permissions`: without this
    # the fresh codex stalls at an interactive approval picker and the restart is not
    # hands-off (maintainer-declared 2026-07-17).
    assert "--dangerously-bypass-approvals-and-sandbox" in command
    # A fresh rollout carries no `thread_name`, so it is NAMED before it is kicked or
    # discovery could never join it back to the plan topic; the ledger-grounded resume
    # line is then pasted, since a fresh launch — unlike `codex resume` — takes no argv
    # prompt to auto-submit.
    assert fake.paste_texts()[0] == f"/rename {topic}"
    assert TEST_EPIC in fake.paste_texts()[1]
    # THE ROUND IS CLOSED on success — and this is the high-consequence property. The await
    # (`_await_pane(pane_is_codex)`, which needs FakeTmux to model the respawn as a codex
    # pane) must succeed AND `_clear_state` must delete the marker, or a stale `ready` would
    # respawn-KILL the just-resumed codex EVERY tick — a destructive loop. Pin both: the
    # state file is inert, and a SECOND tick issues no second respawn.
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_RESTARTED
    fake.calls.clear()
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert not fake.has(method="respawn")  # no re-restart of the session we just resumed


def test_two_codex_tracks_sharing_a_tmux_session_each_restart_their_own_session(*, tmp_path):
    """#4: two codex sessions live in ONE tmux session, each named for its own plan topic.
    Before the (tmux, name) keying, `self.live_codex` kept ONE CodexSession per tmux session,
    so the SECOND track resolved to None — its restart never fired and its monitoring was
    silently lost, invisible in the table. Keyed by (tmux, topic), each track's
    `_do_codex_restart` resolves to ITS OWN live session and restarts for ITS OWN topic.

    The per-track evidence moved when the wrap-up arm stopped resuming: a FRESH launch
    carries no session id, so both tracks render one identical command, and what
    distinguishes them is the `/rename <topic>` the daemon submits to each successor.
    Sabotage: revert the lookup to `.get(session)` and the second track resolves to None →
    one respawn and one rename instead of two → this goes red."""
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
    assert id_a not in respawn_cmds[0] and id_b not in respawn_cmds[1]  # fresh, not resumed
    renames = [text for text in fake.paste_texts() if text.startswith("/rename ")]
    assert renames == [f"/rename {topic_a}", f"/rename {topic_b}"]  # each names its OWN topic


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


def test_a_codex_restart_refuses_a_claude_launch_profile_before_killing_the_pane(*, tmp_path):
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=session),
        model_profile={"harness": "claude", "model": "claude-opus", "wrapper": None},
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.evaluate(track=track, act=True)

    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert "cannot relaunch a Codex track" in err.getvalue()


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
