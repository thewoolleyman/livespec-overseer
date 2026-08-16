"""Integration-tier scenario tests: the startup refusals, the retry, and the runtimes.

Top-of-pyramid evidence for the last six `## Scenario:` headings of
SPECIFICATION/scenarios.md — the three gates the daemon refuses to start behind,
the self-healing resume submit, the runtime-dispatched restart, and the
fail-safe handling of an unreadable context reading.

The three refusal tests drive `Supervisor.run(once=True)` — the real startup
path — against a track that WOULD be warned had the daemon got that far. That is
what makes "refuses to run" observable: the absence of a wrap-up the same fixture
produces when the gate passes, rather than the absence of an exception.

Tier: `tests.integration` is one of the documented default `scenario_tiers`
prefixes, so `check-heading-coverage` direction 4 accepts these node ids without
this repo having to declare `scenario_tiers` in `pyproject.toml`.

The harness (`FakeTmux`, `make_supervisor`, `make_plan`, `declare`) is imported from the
beside-test module that owns it rather than duplicated — a second FakeTmux would
be a second thing to keep true.
"""

from __future__ import annotations

import contextlib
import io as _io

from overseer import _supervisor_view, codex_sessions, registry, signals, supervisor
from overseer.test_supervisor_builders import (
    TEST_EPIC,
    busy_capture,
    codex_busy_capture,
    codex_idle_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    on_respawn,
    unsubmitted_resume_capture,
    wrapup_count,
    write_session,
)
from overseer.test_supervisor_fakes import (
    FakeTmux,
)

_CODEX_SESSION_ID = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"


def _warnable(*, tmp_path, **kwargs):
    """A watched repo holding one live track that a RUNNING daemon would warn.

    Every refusal test uses this, so "it refused" is the absence of a wrap-up the
    same fixture produces once the gate passes — not merely the absence of a crash.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))  # below the 50% threshold
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=str(repo), status="idle")
    fake.pane_pids[50] = session
    kwargs.setdefault("gitignore_check", lambda *, repo: True)
    kwargs.setdefault("sessions_dir", str(sessions_dir))
    kwargs.setdefault("ppid_of", lambda *, pid: 50 if pid == 100 else None)
    kwargs.setdefault("starttime_of", lambda *, pid: "pt" if pid == 100 else None)
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)], out=_io.StringIO(), **kwargs
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )
    return repo, topic, session, fake, sup


def _run(*, sup) -> str:
    """Run one daemon cycle, returning everything it surfaced on stderr."""
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.run(once=True)
    return err.getvalue()


def _respawn_commands(*, fake) -> list[str]:
    return [call[3] for call in fake.calls if call[0] == "respawn"]


def _enters(*, fake, session) -> int:
    return fake.calls.count(("keys", session, "Enter"))


def _stranded_restart(*, tmp_path):
    """Drive a real round to a restart whose fresh session DROPPED the resume Enter.

    The drop is modelled where it happens: a hook on the respawn leaves the pane showing a
    box that HOLDS the resume text, which is what a fresh TUI that swallowed the Enter looks
    like. `paste_ok = False` would be a failed paste — a different fault with the same
    return value, and one that never produces the stranded box.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    on_respawn(
        fake=fake, after=lambda s: fake.panes.__setitem__(s, unsubmitted_resume_capture(ctx=95))
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)  # opens the round
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        restarted = sup.evaluate(track=track, act=True)  # respawns; the submit does NOT land

    assert restarted.status == "restarting"
    return repo, topic, session, fake, sup, track


def _codex_restart_commands(*, tmp_path) -> list[str]:
    """Drive a codex track through a REAL round to its restart; return the respawn commands.

    The round is driven rather than seeded because a codex submit is confirmed by the pane
    going BUSY — codex has no empty-`❯` signal — so the `on_paste` hook models the pane
    responding. A hand-seeded stamp would skip the runtime-aware submit entirely, and that
    submit is part of what "supervised under one agent runtime" means.
    """
    repo, topic = make_plan(tmp_path=tmp_path, topic="codex-track")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=40, topic=topic), cmd="bun"
    )
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, sessions_dir=str(sessions_dir), out=_io.StringIO()
    )
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=4242, name=topic, cwd=str(repo), session_id=_CODEX_SESSION_ID
        )
    }
    track = mapped_track(repo=repo, topic=topic, session=session)
    fake.on_paste = lambda s, _t: fake.panes.__setitem__(s, codex_busy_capture(ctx=40))

    with contextlib.redirect_stderr(_io.StringIO()):
        assert (
            sup.evaluate(track=track, act=True).status == "warned"
        )  # a real, codex-submitted round

    fake.on_paste = None
    fake.panes[session] = codex_idle_capture(ctx=40, topic=topic)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.evaluate(track=track, act=True).status == "restarting"
    return _respawn_commands(fake=fake)


def _claude_restart_commands(*, tmp_path) -> tuple[str, list[str]]:
    """The Claude twin of `_codex_restart_commands`; returns `(topic, commands)`."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="claude-track")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.evaluate(track=track, act=True).status == "restarting"
    return topic, _respawn_commands(fake=fake)


def test_scenario_the_fixture_track_is_warned_when_every_startup_gate_passes(*, tmp_path):
    """The CONTROL for the three refusal tests below — not a scenario row of its own.

    Each refusal test asserts that no wrap-up was pasted. That assertion is worth exactly
    as much as the proof that this fixture pastes one when nothing is refused, and without
    it all three would pass against a daemon that never warns anything.
    """
    _repo, _topic, _session, fake, sup = _warnable(tmp_path=tmp_path)

    _ = _run(sup=sup)

    assert wrapup_count(fake=fake) == 1  # the gates passed and the track really was warned


def test_scenario_the_daemon_refuses_an_unsupported_host(*, tmp_path):
    """Scenario: The daemon refuses an unsupported host.

    Given a host missing a declared runtime requirement, the daemon refuses to run, names
    the failed precondition, and that refusal PRECEDES every other startup gate.

    The ordering clause is the substantive half, and it is asserted by failing ALL THREE
    gates at once: no `/proc`, a repo that does not ignore the scratch path, and a singleton
    lock already held. A daemon that checked them in any other order would name a different
    offender, so the assertion is not merely that the host reason appears but that the other
    two do NOT. Testing the host gate in isolation could not distinguish "first" from "only
    one failing".

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - the host gate moved below the gitignore gate -> the refusal names the repository.
      - `unsupported_host_reasons` returning `[]` -> nothing refuses on the host at all and
        the next gate speaks instead.
    """
    repo, _topic, _session, fake, sup = _warnable(
        tmp_path=tmp_path,
        proc_root=str(tmp_path / "absent-proc"),  # no /proc: the declared Linux requirement
        gitignore_check=lambda *, repo: False,  # ...and the SECOND gate would fail too
    )
    contender = supervisor.Supervisor(  # ...and the THIRD gate is contested as well
        tmux=FakeTmux(), store_path=sup.store_path, stamp_path=sup.stamp_path
    )
    held = contender._acquire_singleton_lock()
    assert held is not None
    try:
        report = _run(sup=sup)
    finally:
        supervisor.Supervisor._release_singleton_lock(handle=held)

    assert "refusing to start" in report
    assert "unsupported host" in report
    assert "/proc" in report  # the failed precondition is NAMED
    assert "not gitignored" not in report  # ...and it PRECEDES the gitignore gate...
    assert "holds" not in report  # ...and the singleton gate
    assert wrapup_count(fake=fake) == 0  # nothing was supervised
    assert not fake.has(method="capture")


def test_scenario_the_daemon_refuses_a_repository_that_does_not_ignore_its_scratch_path(
    *,
    tmp_path,
):
    """Scenario: The daemon refuses a repository that does not ignore its scratch path.

    Given a watched repository that does not gitignore the overseer's scratch directory, the
    daemon refuses to run and names the offending repository.

    Two repos are watched and only ONE offends. Naming the offender is the whole point of
    the clause — with a single watched repo, a refusal message that named the wrong repo, or
    every repo, would still contain the right string.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `unignored_tmp_repos` returning `[]` -> the daemon starts and warps the track.
      - the offender list replaced by the full watch set -> the innocent repo is named too.
    """
    repo, _topic, _session, fake, sup = _warnable(tmp_path=tmp_path)
    innocent, _ = make_plan(tmp_path=tmp_path, repo_name="innocent", topic="other")
    sup.watch_repos = [str(repo), str(innocent)]
    # The Protocol fixes the keyword as `repo`, which shadows this test's own `repo`,
    # so the offending path is bound first.
    offender = str(repo)
    sup.gitignore_check = lambda *, repo: repo != offender  # only the offender offends

    report = _run(sup=sup)

    assert "refusing to start" in report
    assert "NOT gitignored" in report
    assert str(repo) in report  # the OFFENDING repository is named...
    assert str(innocent) not in report  # ...and the innocent one is not
    assert wrapup_count(fake=fake) == 0
    assert not fake.has(method="capture")


def test_scenario_a_second_daemon_instance_refuses_to_start(*, tmp_path):
    """Scenario: A second daemon instance refuses to start.

    Given a daemon already holding the singleton lock for the mapping store, a second daemon
    against the same store refuses and names the contested lock.

    The lock is taken by ACQUIRING it the way the daemon does, not by writing a sentinel
    file: `flock` locks belong to the open file description, so a second `open` + `flock`
    contends even inside one process — which means this exercises the real mechanism rather
    than a stand-in for it.

    The second half — releasing the lock lets a daemon start — is what proves the refusal is
    the LOCK's doing. Without it, a daemon broken in some unrelated way would look identical.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `flock` called without `LOCK_NB`/`LOCK_EX` (shared, blocking) -> the second instance
        acquires it and supervises the track.
      - `_singleton_lock_path` keyed to a constant instead of the store -> ditto.
    """
    _repo, _topic, _session, fake, sup = _warnable(tmp_path=tmp_path)
    first = supervisor.Supervisor(
        tmux=FakeTmux(), store_path=sup.store_path, stamp_path=sup.stamp_path
    )
    held = first._acquire_singleton_lock()
    assert held is not None

    contested = _run(sup=sup)

    assert "refusing to start" in contested
    assert str(sup._singleton_lock_path()) in contested  # the contested lock is NAMED
    assert wrapup_count(fake=fake) == 0
    assert not fake.has(method="capture")

    supervisor.Supervisor._release_singleton_lock(handle=held)  # the first daemon exits
    _ = _run(sup=sup)

    assert wrapup_count(fake=fake) == 1  # ...and the refusal really was the lock's doing


def test_scenario_a_dropped_resume_submission_is_retried_without_a_second_kill(*, tmp_path):
    """Scenario: A dropped resume submission is retried without a second kill.

    Given a restart whose fresh session came up with the resume prompt unsubmitted, the
    daemon re-sends the SUBMISSION only until the prompt lands, never kills the fresh
    session again without a fresh `ready`, and keeps the track visible as needing attention
    until the resume submits.

    The drop is modelled where it actually happens: a hook on the respawn leaves the pane
    showing a box that HOLDS the resume text, which is what a fresh TUI that swallowed the
    Enter looks like. Setting `paste_ok = False` would be a failed paste — a different fault
    with the same return value, and one that never produces the stranded box this scenario
    is about.

    "Never kills it again" is asserted as a respawn count of ONE across the entire sequence,
    including the ticks where a still-valid `ready` marker is sitting right there. That
    marker is the danger: without the retry interception the `elif ready:` branch would
    respawn-kill the fresh session every tick, which is the destructive loop this self-heal
    exists to prevent.

    The final phase — the box clearing — is what makes "until the prompt lands" a real
    claim rather than a description of an infinite retry.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - the retry branch re-entering `_do_restart` instead of `_resend_enter` -> the respawn
        count climbs past one, and the fresh session is killed.
      - `_do_restart` clearing the state on a FAILED submit -> `resume_pending` is never
        recorded, the row stops needing attention, and the stranding is hidden.
    """
    repo, topic, session, fake, sup, track = _stranded_restart(tmp_path=tmp_path)

    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )
    assert signals.read_state(repo=str(repo), topic=topic) is not None  # the marker is KEPT

    enters = _enters(fake=fake, session=session)
    for _ in range(3):  # later cycles: submission only
        with contextlib.redirect_stderr(_io.StringIO()):
            view = sup.evaluate(track=track, act=True)
        assert view.status == "restarting"
        assert view.note == _supervisor_view.RESUME_PENDING_NOTE
        assert supervisor.needs_attention(row=view)  # still visible as needing attention
        assert _enters(fake=fake, session=session) > enters  # another Enter...
        enters = _enters(fake=fake, session=session)
        assert len(_respawn_commands(fake=fake)) == 1  # ...and NO second kill

    fake.panes[session] = idle_capture(ctx=95)  # the prompt finally lands
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)

    assert signals.read_state(repo=str(repo), topic=topic) is None  # the round closes
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is False
    )
    assert len(_respawn_commands(fake=fake)) == 1


def test_restarted_session_never_begins_work_retries_without_second_kill(*, tmp_path):
    """Scenario: restarted-never-worked retries submission without a second kill."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture=unsubmitted_resume_capture(ctx=100, repo=str(repo), epic=TEST_EPIC),
    )
    clock = {"now": 1000.0}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        now=lambda: clock["now"],
        out=_io.StringIO(),
        own_pane="%7",
    )
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is False
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        first = sup.evaluate(track=track, act=True)
    assert first.status == "restarting"
    assert first.note == _supervisor_view.RESUME_PENDING_NOTE
    assert registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert _enters(fake=fake, session=session) > 0
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic) is None

    clock["now"] += 61.0
    with contextlib.redirect_stderr(_io.StringIO()):
        due = sup.evaluate(track=track, act=True)
    assert due.status == "restarting"
    assert supervisor.needs_attention(row=due) is True
    sup._refresh_window_name(attention=int(supervisor.needs_attention(row=due)))
    assert fake.window_name == "overseer(1!)"


def test_scenario_a_restart_never_switches_a_tracks_runtime(*, tmp_path):
    """Scenario: A restart never switches a track's runtime.

    Both directions, because the clause is symmetric: a track supervised under one runtime is
    resumed under that same runtime, and the OTHER runtime's launch command is never issued
    at that pane.

    This is the one place a bug in this daemon is DESTRUCTIVE rather than merely wrong.
    Aiming `claude -n <topic>` at a codex pane replaces the codex session with a claude one
    and orphans its rollout; the routing, not a monitor-only refusal, is what prevents it.

    The codex half drives a REAL round rather than seeding the stamp: the wrap-up is pasted
    and the pane is made to go BUSY in response, which is how a codex submit is confirmed
    (codex has no `❯` box, so "the model started responding" is the only usable signal). A
    round seeded by hand would skip the runtime-aware submit entirely — and that submit is
    part of what the scenario's "supervised under one agent runtime" means.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `_do_restart`'s dispatch inverted (`is_codex` negated) -> the codex pane is issued
        the claude command, and the claude pane the codex one.
      - `_codex_launch_command` replaced by `_launch_command` -> the codex half only.
    """
    codex = _codex_restart_commands(tmp_path=tmp_path)
    assert len(codex) == 1
    assert "codex resume " in codex[0]  # resumed under the SAME runtime...
    assert _CODEX_SESSION_ID in codex[0]  # ...and the same rollout
    assert "claude " not in codex[0]  # the other runtime's command is never issued

    claude_topic, claude = _claude_restart_commands(tmp_path=tmp_path)
    assert len(claude) == 1
    assert claude[0] == f"claude --dangerously-skip-permissions -n {claude_topic}"
    assert "codex" not in claude[0]


def test_scenario_an_unknown_context_reading_never_triggers_a_wrapup(*, tmp_path):
    """Scenario: An unknown context reading never triggers a wrap-up.

    Given a pane whose capture yields no readable remaining-context value, the last known
    value is kept, the unknown reading counts as no crossing, and the track's context renders
    as unknown rather than a guess.

    The two clauses need two different tracks, because they are about different states:

    - A track with a KNOWN reading that then goes unreadable must keep the known value. The
      reading is deliberately taken ABOVE the threshold, so that treating unknown as a low or
      zero percentage — the natural way to get this wrong — would cross and warn. Below the
      threshold the track would warn either way and the test would prove nothing.
    - A track that has NEVER had a readable value has nothing to keep, and that is where
      "renders as unknown rather than a guess" is observable: it must reach the table as a
      dash, not as `0%`.

    The render is exercised through `Supervisor.render` rather than asserted on `view.ctx`,
    because the clause is about what the OPERATOR sees; a row carrying `None` that printed
    as `0%` would satisfy an assertion on the field and still mislead.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `_effective_ctx` returning the raw `current` (so unknown erases the last known) ->
        the kept-value assertion, and the row falls to a dash mid-flight.
      - the unknown cell rendered as `0%` instead of the dash -> the never-known assertion.
    """
    repo, topic = make_plan(tmp_path=tmp_path, topic="was-known")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=60))  # ABOVE the 50% threshold
    out = _io.StringIO()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=out)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        known = sup.evaluate(track=track, act=True)
    assert known.ctx == 60
    assert wrapup_count(fake=fake) == 0  # above threshold: nothing due

    fake.panes[session] = busy_capture()  # a capture with NO `Ctx: N% left` at all
    with contextlib.redirect_stderr(_io.StringIO()):
        unknown = sup.evaluate(track=track, act=True)

    assert unknown.ctx == 60  # the last known value is KEPT...
    assert wrapup_count(fake=fake) == 0  # ...and the unknown reading crossed nothing

    never, never_topic = make_plan(tmp_path=tmp_path, repo_name="never", topic="never-known")
    never_session = registry.tmux_id(repo=str(never), topic=never_topic)
    fake.serve(session=never_session, repo=never, capture=idle_capture())  # no ctx, ever
    with contextlib.redirect_stderr(_io.StringIO()):
        blank = sup.evaluate(
            track=mapped_track(repo=never, topic=never_topic, session=never_session), act=True
        )

    assert blank.ctx is None
    assert wrapup_count(fake=fake) == 0
    sup.render(rows=[blank])
    rendered = next(line for line in out.getvalue().splitlines() if never_topic in line)
    assert "—" in rendered  # renders as UNKNOWN...
    assert "0%" not in rendered  # ...never as a guess
