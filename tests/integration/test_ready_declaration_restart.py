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
import subprocess
from dataclasses import replace

from overseer import _supervisor_config, registry, signals, supervisor
from overseer.test_supervisor_builders import (
    TEST_EPIC,
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    on_respawn,
    render_of,
    row_line,
)
from overseer.test_supervisor_fakes import (
    FakeTmux,
)


def _open_round(*, tmp_path, ctx=40, topic="topic", clock=None):
    """Drive a REAL wrap-up round and return everything needed to continue it.

    The Supervisor observes an idle track below its threshold, which warns it and
    — the part that matters here — writes the round's injection stamp. Callers
    then write the state file with an mtime relative to that stamp, exactly as a
    supervised session does.

    """
    repo, topic = make_plan(tmp_path=tmp_path, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    now = (lambda: clock["t"]) if clock is not None else (lambda: 1000.0)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=now, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    opened = sup.evaluate(track=track, act=True)

    assert opened.status == "warned"  # the round really did open...
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )
    return repo, topic, session, fake, sup, track


def _respawns(*, fake):
    return [call for call in fake.calls if call[0] == "respawn"]


def test_recognition_timeout_after_successful_respawn_pends_resume_not_second_kill(*, tmp_path):
    """A successful respawn consumes the one `ready` authorization even if the bounded
    recognition poll times out. The next tick must resume-retry the fresh pane instead
    of re-entering the `ready` branch and respawn-killing it."""
    repo, topic, session, fake, sup, track = _open_round(tmp_path=tmp_path)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    on_respawn(
        fake=fake, after=lambda s: fake.cmds.__setitem__(s, ["zsh"] * 30)
    )  # fresh pane is real but not recognized before the bounded poll expires

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view1 = sup.evaluate(track=track, act=True)

    assert view1.status == "restarting"
    assert "respawned pane never became Claude" in err.getvalue()
    assert len(_respawns(fake=fake)) == 1
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY

    fake.cmds[session] = "node"
    fake.calls.clear()
    with contextlib.redirect_stderr(_io.StringIO()):
        view2 = sup.evaluate(track=track, act=True)

    assert view2.status == "restarting"
    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is False
    )


def test_scenario_a_fresh_ready_declaration_triggers_the_atomic_restart(*, tmp_path):
    """Scenario: A fresh ready declaration triggers the atomic restart.

    Given a warned session that wrote `ready` AFTER this round's injection stamp, and an
    idle, settled, positively-identified pane. Then the pane's process is replaced in ONE
    atomic operation, the fresh session is handed exactly one prompt naming the track's
    repository and plan epic, and both the state file and the round's stamp are deleted so
    the declaration cannot re-trigger.

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
    assert str(repo) in pastes[1]
    assert "overseer-test-epic" in pastes[1]
    assert "handoff.md" not in pastes[1]

    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )

    sup.evaluate(track=track, act=True)  # the consumed declaration must not fire again
    assert len(_respawns(fake=fake)) == 1


def test_scenario_a_respawn_prompt_names_the_plan_epic_and_repository(*, tmp_path, monkeypatch):
    """Scenario: A respawn prompt names the plan epic and repository so a cold-open session
    can resolve it.

    Given a track whose mapping row records the plan's ledger epic id, the daemon
    respawns after a fresh `ready` declaration and pastes exactly one resume prompt naming
    the repository path and the epic id literally. A sibling track with no recorded epic id
    is surfaced as needing attention, preserves its declaration, and is never respawned.

    The test deliberately gives the mapped row a stale path-shaped `resume` string of the
    exact form assignment surfaces used to serialize. That proves the restart prompt comes
    from the ledger-held plan locator, not from a previously serialized handoff path a
    cold-open successor may no longer be able to resolve.
    """
    epic = "overseer-pfpfty"
    repo, topic, _session, fake, sup, track = _open_round(tmp_path=tmp_path)
    legacy_resume = f"read {repo / 'plan' / topic / 'handoff.md'} and follow it"
    track = replace(track, epic=epic, resume=legacy_resume)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert len(_respawns(fake=fake)) == 1
    resume = fake.paste_texts()[1]
    assert str(repo) in resume
    assert epic in resume
    assert legacy_resume not in resume
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED

    missing_repo, missing_topic, _missing_session, missing_fake, missing_sup, missing_track = (
        _open_round(tmp_path=tmp_path, topic="missing-epic")
    )
    # GENUINELY unresolvable, not merely a stale row: overseer-vbmq's restart-interlock
    # re-derive would otherwise heal a row whose plan anchor IS resolvable (that healing
    # is covered separately, in test_stale_epic_null_row_heals_and_restarts_on_ready
    # below), so this scenario must blank the anchor `_open_round`'s `make_plan` wrote.
    (missing_repo / "plan" / missing_topic / "handoff.md").write_bytes(b"no anchor here\n")
    # Once both epic.md and handoff.md fail to resolve, `epic_from_plan_anchor` falls
    # through to a real `bd` ledger-tag query subprocess. Simulate "bd absent" at the
    # `subprocess` layer (shared by both this package's dual import copies of
    # `_registry_epic`, unlike patching `registry` itself across that split) rather
    # than actually invoking a real `bd` process from a test.
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError("bd not found (stubbed)")),
    )
    missing_track = replace(
        missing_track,
        epic=registry.unresolved_plan_epic(topic=missing_topic),
        resume=legacy_resume,
    )
    missing_marker = declare(
        repo=missing_repo,
        topic=missing_topic,
        value=signals.STATE_READY,
        mtime=1001.0,
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        missing_view = missing_sup.evaluate(track=missing_track, act=True)

    assert missing_view.status == "blocked:human"
    assert "ready cannot respawn: no plan epic recorded" in missing_view.note
    assert not missing_fake.has(method="respawn")
    assert missing_marker.exists()
    assert "no plan epic recorded" in err.getvalue()


def test_stale_epic_null_row_heals_and_restarts_on_ready(*, tmp_path):
    """Scenario (overseer-vbmq): a row recorded `epic: None` at assignment time, whose
    plan anchor IS resolvable by the time a certified `ready` arrives, heals via a
    one-shot re-derive at the restart interlock and restarts — it is not stuck
    `blocked:human` forever waiting on a human to re-run `add` by hand.

    `_open_round`'s `make_plan` already wrote a REAL, resolvable anchor
    (`TEST_EPIC`); this only has to null out the ROW to reproduce the stale-row
    shape overseer-vbmq describes (the anchor was unreadable at add-time, or was
    written afterward — either way, the row predates a resolvable anchor).
    """
    repo, topic, _session, fake, sup, track = _open_round(tmp_path=tmp_path, topic="stale-epic")
    track = replace(track, epic=registry.unresolved_plan_epic(topic=topic))
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert len(_respawns(fake=fake)) == 1
    resume = fake.paste_texts()[1]
    assert TEST_EPIC in resume


def test_scenario_a_ready_declaration_from_a_prior_round_never_restarts(*, tmp_path):
    """Scenario: A ready declaration from a prior round never restarts.

    Given a state file declaring `ready` whose modification time PREDATES this round's
    injection stamp, the interlock fails and no restart occurs.

    The declaration is written BEFORE `_open_round` runs, so its mtime predating the stamp
    is a fact about the sequence rather than a hand-set number: the round genuinely opens
    after the session had already spoken.

    Note what is NOT asserted — that the stale declaration is cleaned up. It is not:
    an idle track is left holding its own file. Asserting a deletion here would pin
    behavior the daemon does not have.

    INJECTED DEFECT THAT REDDENS IT (run 2026-07-26, reverted): dropping the mtime
    comparison from `signals.ready_valid` (`return state.mtime > injection_stamp` ->
    `return True`) restarts the track on the prior round's declaration.
    """
    repo, topic, _session, fake, sup, track = _open_round(tmp_path=tmp_path)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=999.0)
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


def _bare_ready_no_round_fixture(*, tmp_path, clock):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=79))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    state = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"])
    return repo, topic, session, fake, sup, track, state


def test_scenario_an_uncertifiable_ready_declaration_surfaces_as_attention(*, tmp_path):
    """Scenario: An uncertifiable ready declaration is surfaced as attention.

    Given a session that wrote `ready` while no supervision round is open, the interlock
    must keep refusing it forever: no stamp means no round to certify against. Past the
    bounded floor, though, the row must stop looking like an acting restart and become an
    attention row naming the declaration, its age, and why it cannot certify.

    INJECTED DEFECTS THAT REDDEN IT:
      - treating a bare `ready` as plain `idle` keeps it out of NEEDS YOU and emits no
        alert.
      - adding the status to attention without the alert branch leaves stderr empty.
    """
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup, track, _state = _bare_ready_no_round_fixture(
        tmp_path=tmp_path, clock=clock
    )
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )
    assert (
        signals.ready_valid(
            repo=str(repo),
            topic=topic,
            certification_floor=None,
            round_session_identity=None,
            live_session_identity="claude:s:t",
        )
        is False
    )

    too_young = sup.evaluate(track=track, act=True)
    assert too_young.status != "restarting"
    assert not fake.has(method="respawn")

    clock["t"] += _supervisor_config.CONDITION_CONTINUITY_GAP + 1
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        surfaced = sup.evaluate(track=track, act=True)

    assert surfaced.status == "ready-uncertifiable"
    assert surfaced.note == "15m: ready cannot certify: no supervision round open"
    assert supervisor.needs_attention(row=surfaced) is True
    assert not fake.has(method="respawn")
    line = row_line(out=render_of(sup=sup, views=[surfaced]), topic=topic)
    assert "restarting" not in line
    assert "restart-in-progress" not in line
    assert "ready cannot certify" in line
    assert "no supervision round" in line
    report = err.getvalue()
    assert "ready cannot certify (15m): no supervision round open" in report
    for coordinate in (topic, registry.repo_slug(repo=str(repo)), session):
        assert coordinate in report
    assert f"tmux switch-client -t {session}" in report


def test_uncertifiable_ready_alert_stays_edge_triggered_behind_prior_branch(*, tmp_path):
    """A prior cascade branch must not re-arm the uncertifiable-ready alert every tick.

    INJECTED DEFECT THAT REDDENS IT: registering the condition only in the
    ``ready-uncertifiable`` branch makes the final per-condition clear forget the
    pre-cascade alert when ``settling`` wins, so the same declaration reports again
    on every observation.
    """
    clock = {"t": 1000.0}
    _repo, _topic, session, fake, sup, track, _state = _bare_ready_no_round_fixture(
        tmp_path=tmp_path, clock=clock
    )
    fake.panes[session] = "partial turn output\nCtx: 79% left\n"
    clock["t"] += _supervisor_config.CONDITION_CONTINUITY_GAP + 1
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        first = sup.evaluate(track=track, act=True)
        second = sup.evaluate(track=track, act=True)

    assert first.status == "settling"
    assert second.status == "settling"
    assert err.getvalue().count("ready cannot certify") == 1


def test_uncertifiable_ready_alert_quantizes_clears_and_rearms(*, tmp_path):
    """The report-only alert is edge-triggered, age-banded, and re-armed per episode.

    INJECTED DEFECT THAT REDDENS IT: forgetting per-condition clearing prevents the later
    episode from re-alerting after the declaration clears and a new one appears.
    """
    clock = {"t": 1000.0}
    repo, topic, _session, _fake, sup, track, state = _bare_ready_no_round_fixture(
        tmp_path=tmp_path, clock=clock
    )
    clock["t"] += _supervisor_config.CONDITION_CONTINUITY_GAP + 1
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup.evaluate(track=track, act=True)
        sup.evaluate(track=track, act=True)
    assert err.getvalue().count("ready cannot certify") == 1

    clock["t"] = 1000.0 + _supervisor_config.BLOCKED_AGE_ALERT_BANDS[0] + 1
    with contextlib.redirect_stderr(err):
        older = sup.evaluate(track=track, act=True)
    assert older.status == "ready-uncertifiable"
    assert "ready cannot certify (4h): no supervision round open" in err.getvalue()
    assert err.getvalue().count("ready cannot certify") == 2

    state.unlink()
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"

    err = _io.StringIO()
    clock["t"] = 20_000.0
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"])
    clock["t"] += _supervisor_config.CONDITION_CONTINUITY_GAP + 1
    with contextlib.redirect_stderr(err):
        rearmed = sup.evaluate(track=track, act=True)
    assert rearmed.status == "ready-uncertifiable"
    assert err.getvalue().count("ready cannot certify") == 1


def test_scenario_a_ready_declaration_stays_armed_when_its_session_emits_more_output(*, tmp_path):
    """A ready declaration survives intervening output and fires when the pane idles.

    The busy/settle gates already prevent a mid-work restart, so activity is not a reason
    to delete `ready`. The declaration remains armed until the first verified settled-idle
    observation, bounded separately by the ready max-age.
    """
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup, track = _open_round(tmp_path=tmp_path, clock=clock)
    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))
    clock["t"] = 1201.0
    resumed = sup.evaluate(track=track, act=True)

    assert resumed.status == "working"
    assert marker.exists()
    assert registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    assert sup.evaluate(track=track, act=True).status == "restarting"
    assert fake.has(method="respawn")


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
