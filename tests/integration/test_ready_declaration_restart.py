"""Integration-tier scenario tests: the `ready` declaration and the restart interlock.

Top-of-pyramid evidence for the five `## Scenario:` headings of
SPECIFICATION/scenarios.md that govern THE CARDINAL RULE — a session's own
declaration is the sole authorization for a restart.

Every test here OPENS A REAL ROUND first: it lets the Supervisor warn a track
(which is what writes the injection stamp) and only then writes the state file.
That ordering is the whole point. A test that seeds the stamp with
`registry.write_injection_stamp` is testing the interlock's arithmetic, not the
protocol — the beside-tests already own that tier. Driving the round is what
makes the stamp/declaration ordering an OBSERVED consequence rather than an
assumed precondition.

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

from overseer import registry, signals, supervisor
from overseer.test_supervisor_builders import (
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import (
    FakeTmux,
)


def _open_round(*, tmp_path, ctx=40, topic="topic", clock=None, declare_first=None):
    """Drive a REAL wrap-up round and return everything needed to continue it.

    The Supervisor observes an idle track below its threshold, which warns it and
    — the part that matters here — writes the round's injection stamp. Callers
    then write the state file with an mtime relative to that stamp, exactly as a
    supervised session does.

    ``declare_first`` writes a ``(value, mtime)`` state file BEFORE the round is
    opened, for the prior-round case — so "the declaration predates this round's
    stamp" is a fact about the sequence rather than a hand-picked pair of numbers.
    """
    repo, topic = make_plan(tmp_path=tmp_path, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    now = (lambda: clock["t"]) if clock is not None else (lambda: 1000.0)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=now, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    if declare_first is not None:
        declare(repo=repo, topic=topic, value=declare_first[0], mtime=declare_first[1])

    opened = sup.evaluate(track=track, act=True)

    assert opened.status == "warned"  # the round really did open...
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )
    return repo, topic, session, fake, sup, track


def _respawns(*, fake):
    return [call for call in fake.calls if call[0] == "respawn"]


def test_scenario_a_fresh_ready_declaration_triggers_the_atomic_restart(*, tmp_path):
    """Scenario: A fresh ready declaration triggers the atomic restart.

    Given a warned session that wrote `ready` AFTER this round's injection stamp, and an
    idle, settled, positively-identified pane. Then the pane's process is replaced in ONE
    atomic operation, the fresh session is handed exactly one prompt pointing at the
    track's handoff, and both the state file and the round's stamp are deleted so the
    declaration cannot re-trigger.

    "Atomic" is asserted as the ABSENCE of the alternatives as much as the presence of the
    respawn: no `new-session`, and no `send-keys` carrying an `/exit` — the `❯` glyph is
    ambiguously both the Claude idle prompt and the zsh prompt, so an exit-then-scrape
    restart could type the launch command into a still-live session.

    The final re-tick is what pins "cannot re-trigger". Asserting only that the file is
    gone proves a deletion happened; re-observing the track proves the deletion was
    load-bearing.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `_clear_state` skipped on the success path -> the state-file assertion. The
        re-trigger assertion below reddens on the SAME defect, but the run aborts before
        reaching it, so it was verified separately against a probe carrying only that
        assertion: the daemon logged `restarted …` twice and the respawn count was 2.
        Two assertions failing on one defect is not redundancy here — the deletion and
        its consequence are different claims, and only the second survives a change that
        clears the file some other way.
      - `_launch_command` re-pointed at the codex command -> the launch-command assertion.
    """
    repo, topic, _session, fake, sup, track = _open_round(tmp_path=tmp_path)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)  # POST-dates the stamp

    view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert len(_respawns(fake=fake)) == 1  # ONE atomic op...
    assert not fake.has(method="new")  # ...not a teardown and a re-create
    assert not any(call[0] == "keys" and "exit" in str(call[2]).lower() for call in fake.calls)
    assert _respawns(fake=fake)[0][3] == f"claude --dangerously-skip-permissions -n {topic}"

    pastes = fake.paste_texts()
    assert len(pastes) == 2  # the wrap-up that opened the round, then ONE resume prompt
    assert pastes[1] == supervisor.default_resume(repo=str(repo), topic=topic)
    assert supervisor.default_handoff(repo=str(repo), topic=topic) in pastes[1]

    assert not signals.state_path(repo=str(repo), topic=topic).exists()
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )

    sup.evaluate(track=track, act=True)  # the consumed declaration must not fire again
    assert len(_respawns(fake=fake)) == 1


def test_scenario_a_ready_declaration_from_a_prior_round_never_restarts(*, tmp_path):
    """Scenario: A ready declaration from a prior round never restarts.

    Given a state file declaring `ready` whose modification time PREDATES this round's
    injection stamp, the interlock fails and no restart occurs.

    The declaration is written BEFORE `_open_round` runs, so its mtime predating the stamp
    is a fact about the sequence rather than a hand-set number: the round genuinely opens
    after the session had already spoken.

    Note what is NOT asserted — that the stale declaration is cleaned up. It is not, and
    should not be: voiding a `ready` is the busy branch's job (`_void_if_stale`), and an
    idle track is left holding its own file. Asserting a deletion here would pin behavior
    the daemon does not have.

    INJECTED DEFECT THAT REDDENS IT (run 2026-07-26, reverted): dropping the mtime
    comparison from `signals.ready_valid` (`return state.mtime > injection_stamp` ->
    `return True`) restarts the track on the prior round's declaration.
    """
    repo, topic, _session, fake, sup, track = _open_round(
        tmp_path=tmp_path,
        declare_first=(signals.STATE_READY, 999.0),  # a PRIOR round's word, then the stamp
    )
    state = signals.state_path(repo=str(repo), topic=topic)
    stamp = registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert stamp is not None and state.stat().st_mtime < stamp  # the given, now observed

    view = sup.evaluate(track=track, act=True)

    assert view.status != "restarting"
    assert not fake.has(method="respawn")
    assert state.exists()  # the interlock refused it; nothing consumed it
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == stamp
    )


def test_scenario_a_ready_declaration_is_voided_when_its_session_resumes_work(*, tmp_path):
    """Scenario: A ready declaration is voided when its session resumes work.

    Both halves of the scenario are here because they are one rule seen from two sides,
    and pinning either alone is what makes this dangerous to change:

    - Older than the voiding grace, seen busy: the daemon clears the now-false declaration
      INSTEAD OF restarting later. The "instead of restarting later" is asserted by going
      idle again afterwards — a void that left the file in place would show up there, not
      on the busy tick.
    - Younger than the grace: it SURVIVES its own turn's busy tail. The declaring turn's
      final text and stop hooks legitimately keep the pane busy for 10-60s after the
      write, so voiding on ANY busy would destroy every legitimate declaration before the
      pane ever went idle. Here the young declaration survives and then really does
      restart the track.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `MARKER_VOID_GRACE = 0.0` -> the young half's declaration is voided and the
        restart never fires.
      - the void made unconditional (drop the `age > MARKER_VOID_GRACE` guard) -> same.
      - `MARKER_VOID_GRACE = 10_000.0` -> the stale half is never voided and restarts.
    """
    # --- younger than the grace: survives the declaring turn's own busy tail --------- #
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup, track = _open_round(
        tmp_path=tmp_path, topic="young", clock=clock
    )
    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    fake.serve(
        session=session, repo=repo, capture=busy_capture(ctx=40)
    )  # the declaring turn's tail
    clock["t"] = 1060.0  # age 59s, inside the 120s grace
    busy = sup.evaluate(track=track, act=True)

    assert busy.status == "working"
    assert marker.exists()  # NOT voided — this is the certifying tail

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))  # the tail finishes
    assert sup.evaluate(track=track, act=True).status == "restarting"
    assert fake.has(method="respawn")  # the surviving declaration was honoured

    # --- older than the grace: cleared instead of restarting later ------------------- #
    stale_clock = {"t": 1000.0}
    repo, topic, session, fake, sup, track = _open_round(
        tmp_path=tmp_path, topic="stale", clock=stale_clock
    )
    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))  # the session resumed WORK
    stale_clock["t"] = 1201.0  # age 200s, past the 120s grace
    resumed = sup.evaluate(track=track, act=True)

    assert resumed.status == "working"
    assert not marker.exists()  # the now-false declaration is cleared...
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))  # ...and going idle again
    assert sup.evaluate(track=track, act=True).status != "restarting"  # does not restart LATER
    assert not fake.has(method="respawn")


def test_scenario_an_undeclared_session_at_the_danger_line_is_reported_never_restarted(
    *,
    tmp_path,
):
    """Scenario: An undeclared session at the danger line is reported, never restarted.

    Given a warned session at twenty percent remaining or below whose state file holds no
    declaration, the track is reported LOUDLY with full coordinates, and the daemon
    performs no restart and no further act against the session.

    "No FURTHER act" is the clause that needs care. The daemon is not silent at the danger
    line — crossing into it coalesces the remaining bands into one last wrap-up, and that
    paste is authorized by the threshold, not by anything the session said. What must not
    happen is the daemon continuing to act tick after tick. So the paste count is captured
    AFTER the crossing settles and pinned across ten further observations, which is the
    difference between "it acted once on a real crossing" and "it keeps keystroking a
    session that is not answering".

    The alert is checked for every coordinate, not merely for the topic: because the
    overseer never prompts on a track's behalf (notify, never block), this line is the
    operator's ONLY handover and has to be self-sufficient.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `DANGER_CTX_REMAINING = 0` -> the track reads `warned`, and no NOT RESPONDING
        alert is emitted at all.
      - `alert` reduced to `repo::topic` text -> the session/pane/jump assertions.
    """
    repo, topic, session, fake, sup, track = _open_round(tmp_path=tmp_path)
    assert not signals.state_path(repo=str(repo), topic=topic).exists()  # the session said nothing

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=13))  # crosses the danger line
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)
    settled_pastes = len(fake.paste_texts())

    assert view.status == "danger"
    report = err.getvalue()
    assert "NOT RESPONDING" in report
    assert "declared NOTHING" in report  # ...distinct from a stale ACK's "hung mid-wrap-up"
    for coordinate in (topic, registry.repo_slug(repo=str(repo)), session):
        assert coordinate in report
    assert f"tmux switch-client -t {session}" in report  # a copy-pasteable jump

    with contextlib.redirect_stderr(_io.StringIO()):
        for _ in range(10):  # tick and tick — it must never escalate to a kill
            view = sup.evaluate(track=track, act=True)

    assert view.status == "danger"
    assert not fake.has(method="respawn")  # no restart...
    assert len(fake.paste_texts()) == settled_pastes  # ...and no further act
    assert not signals.state_path(repo=str(repo), topic=topic).exists()  # the daemon wrote nothing


def test_scenario_a_malformed_state_value_is_surfaced_and_treated_as_no_declaration(
    *,
    tmp_path,
):
    """Scenario: A malformed state value is surfaced and treated as no declaration.

    Given a state file whose first line is not one of the protocol's values, the malformed
    value is surfaced to the operator BY NAME, the track is treated as having declared
    nothing, and no act is ever authorized by it.

    The setup is deliberately DIFFERENTIAL: every restart precondition is satisfied — a
    real round is open, the pane is idle and settled, and the declaration post-dates the
    stamp — so the ONLY difference from the fresh-`ready` scenario above is the token
    itself. That is what makes "no act is authorized" a claim about the value rather than
    about some other unmet condition; a test written on an already-ineligible track would
    pass no matter how the token were handled.

    "Treated as having declared nothing" is then asserted where the daemon actually has to
    make that judgement: at the danger line, where the non-responder report distinguishes
    a session that declared NOTHING from one that acknowledged and hung. A typo must land
    in the former.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `signals.valid_token` returning True for anything -> the value is never surfaced
        and the note is unset.
      - `read_state` coercing an unknown token to `ready` -> the track is respawned on a
        typo, which is the reason this scenario exists.
    """
    repo, topic, session, fake, sup, track = _open_round(tmp_path=tmp_path)
    stamp = registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    state = declare(
        repo=repo, topic=topic, value="redy", mtime=1001.0
    )  # a typo, post-dating the stamp

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)

    report = err.getvalue()
    assert "MALFORMED state file" in report
    assert "'redy'" in report  # surfaced BY NAME, not as a generic complaint
    assert view.note is not None and "redy" in view.note
    assert view.status != "restarting"
    assert not fake.has(method="respawn")  # a typo is NOT a restart authorization
    assert state.exists()  # nothing consumed it...
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == stamp
    )  # round open

    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=13)
    )  # ...and at the danger line
    with contextlib.redirect_stderr(err):
        sup.evaluate(track=track, act=True)

    assert "declared NOTHING" in err.getvalue()  # treated as no declaration
