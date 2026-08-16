"""Integration-tier scenario tests: the escalating wrap-up.

These are the top-of-pyramid evidence for the first five `## Scenario:` headings
of SPECIFICATION/scenarios.md, and the first tests this repo has above the
unit tier. Each drives a REAL `Supervisor` observe-and-act round end to end —
discovery, the liveness gate, the injection stamp, the paste, the state file —
against the hermetic tmux double, rather than calling a single helper.

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

from overseer import registry, signals
from overseer.test_supervisor_builders import (
    TEST_EPIC,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import (
    FakeTmux,
)

_STATE_FILE_HINT = ".overseer-state"


def _track(*, tmp_path, ctx, topic="topic"):
    """A discovered, mapped, live track sitting idle at `ctx`% remaining."""
    repo, topic = make_plan(tmp_path=tmp_path, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    return repo, topic, session, fake


def _audit_state_file_mutations(*, monkeypatch, state):
    state_mutations = []
    original_write_text = type(state).write_text
    original_unlink = type(state).unlink

    def audited_write_text(self, *args, **kwargs):
        if self == state:
            state_mutations.append(("write_text", self))
        return original_write_text(self, *args, **kwargs)

    def audited_unlink(self, *args, **kwargs):
        if self == state:
            state_mutations.append(("unlink", self))
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(type(state), "write_text", audited_write_text)
    monkeypatch.setattr(type(state), "unlink", audited_unlink)
    return state_mutations


def test_scenario_a_wrapup_is_injected_when_a_track_crosses_its_threshold(*, tmp_path):
    """Scenario: A wrap-up is injected when a track crosses its threshold.

    Then it durably records an injection stamp BEFORE touching the pane, pastes the
    wrap-up as one atomic paste, and the message names the state-file path, the three
    writable values, and the handoff path.

    The stamp-before-paste ordering is asserted by reading the stamp from INSIDE the
    paste callback — the only way to prove the write preceded the paste rather than
    merely both having happened by the end of the round.
    """
    repo, topic, session, fake = _track(tmp_path=tmp_path, ctx=40)  # below the default 50
    stamp_at_paste = []
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    fake.on_paste = lambda _s, _t: stamp_at_paste.append(
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    )

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    assert stamp_at_paste == [1000.0]  # recorded BEFORE the pane was touched
    pastes = fake.paste_texts()
    assert len(pastes) == 1  # ONE atomic paste, never typed line by line
    message = pastes[0]
    assert _STATE_FILE_HINT in message
    for value in ("ready", "blocked:", "winding-down"):
        assert value in message
    # The read-first source the successor inherits, named by BOTH coordinates and by no
    # path into the plan tree.
    assert TEST_EPIC in message
    assert str(repo) in message
    assert "handoff.md" not in message


def test_scenario_the_wrapup_sharpens_as_context_keeps_falling(*, tmp_path):
    """Scenario: The wrap-up sharpens as context keeps falling.

    Then one further wrap-up per lower band, a SUGGESTION above thirty percent
    remaining and an insistent demand at thirty and below.
    """
    repo, topic, session, fake = _track(tmp_path=tmp_path, ctx=40)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    assert len(fake.paste_texts()) == 1
    suggestion = fake.paste_texts()[0]

    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=28)
    )  # crosses into 30-and-below
    sup.evaluate(track=track, act=True)
    assert len(fake.paste_texts()) == 2
    demand = fake.paste_texts()[1]

    assert "Please start wrapping up" in suggestion
    assert "STOP AND WIND DOWN NOW" not in suggestion
    assert "STOP AND WIND DOWN NOW" in demand


def test_scenario_a_band_never_fires_twice_in_one_round(*, tmp_path):
    """Scenario: A band never fires twice in one round.

    ...BECAUSE the notified bands are recorded DURABLY, not in daemon memory. The
    `Because` clause is the load-bearing part, so this rebuilds the Supervisor from
    scratch between observations — a fresh in-memory state standing in for the daemon
    restart the scenario describes. A test that reused one Supervisor would pass on
    an in-memory band set and prove nothing.
    """
    repo, topic, session, fake = _track(tmp_path=tmp_path, ctx=40)
    track = mapped_track(repo=repo, topic=topic, session=session)

    first = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    first.evaluate(track=track, act=True)
    assert len(fake.paste_texts()) == 1

    reborn = make_supervisor(
        tmp_path=tmp_path, fake=fake, out=_io.StringIO()
    )  # new process, same stores
    reborn.evaluate(track=track, act=True)

    assert len(fake.paste_texts()) == 1  # no second wrap-up for an already-notified band
    assert set(
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=reborn.stamp_path)
    ) == {50, 40}


def test_scenario_a_winding_down_acknowledgement_pauses_the_escalation(*, tmp_path):
    """Scenario: A winding-down acknowledgement pauses the escalation.

    Then no further wrap-up is pasted while the acknowledgement is FRESH — the daemon
    never keystrokes into a session that is actively wrapping up.
    """
    repo, topic, session, fake = _track(tmp_path=tmp_path, ctx=40)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    assert len(fake.paste_texts()) == 1

    declare(
        repo=repo, topic=topic, value="winding-down", mtime=1000.0
    )  # fresh: clock is pinned at 1000.0
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=28)
    )  # would otherwise cross a band
    view = sup.evaluate(track=track, act=True)

    assert len(fake.paste_texts()) == 1  # still ONE — the acknowledgement paused it
    assert view.status == "winding-down"


def test_scenario_a_stale_acknowledgement_resumes_escalation_but_authorizes_nothing(*, tmp_path):
    """Scenario: A stale acknowledgement resumes escalation but authorizes nothing.

    Then the escalation resumes and the track is re-reported — AND the daemon still
    takes no action against the session. "No action" is the safety half: staleness must
    never become a restart authorization.

    THE ORDERING HERE IS LOAD-BEARING, and an earlier draft got it wrong. The round is
    opened FIRST (a real warn, which writes the injection stamp), and only then is the
    acknowledgement written with an mtime NEWER than that stamp. That is what forces the
    restart interlock all the way to its token check: a stamp exists and the declaration
    post-dates it, so the ONLY thing left standing between this session and a respawn is
    that `winding-down` is not `ready`.

    Written the other way round — acknowledge first, never warn — the assertion passes
    for an unrelated reason (no stamp, no round, so the interlock short-circuits before
    the token is ever examined). Sabotaging `ready_valid` to accept `winding-down` left
    that draft GREEN. It is red now.
    """
    repo, topic, session, fake = _track(tmp_path=tmp_path, ctx=28)
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)  # opens the round: stamp written at 1000.0
    assert len(fake.paste_texts()) == 1
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )

    declare(repo=repo, topic=topic, value="winding-down", mtime=1001.0)  # POST-dates the stamp
    clock["t"] = 1000.0 + (16 * 60)  # ...and is now past the freshness window
    # Drop a band lower so "escalation resumes" is OBSERVABLE. The opening warn at 28%
    # coalesced bands 50/40/30 into its one message (several bands crossed at once
    # coalesce, per the contract), so at an unchanged 28% nothing further is due and a
    # resumed escalation would look identical to a suppressed one.
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=18))
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)

    assert len(fake.paste_texts()) == 2  # escalation resumed: the 20-band fired
    assert "20%" in fake.paste_texts()[1] or "18%" in fake.paste_texts()[1]
    assert topic in err.getvalue()  # ...and the track was re-reported to the operator
    assert not fake.has(method="respawn")  # ...but staleness authorized NOTHING
    assert view.status != "restarting"


def test_scenario_a_compacted_session_that_re_crosses_threshold_is_re_warned(
    *, tmp_path, monkeypatch
):
    """Scenario: A compacted session that re-crosses its threshold is re-warned in a fresh round."""
    repo, topic, session, fake = _track(tmp_path=tmp_path, ctx=8)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    assert len(fake.paste_texts()) == 1
    assert set(
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    ) == {50, 40, 30, 20, 10}

    state = signals.state_path(repo=str(repo), topic=topic)
    state_mutations = _audit_state_file_mutations(monkeypatch=monkeypatch, state=state)

    calls_before_recovery = list(fake.calls)
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=80))
    recovered = sup.evaluate(track=track, act=True)
    recovery_calls = fake.calls[len(calls_before_recovery) :]

    assert recovered.status == "idle"
    assert (
        registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path).at
        is None
    )
    assert not fake.has(method="respawn")
    assert not any(call[0] in {"keys", "paste", "respawn"} for call in recovery_calls)
    assert len(fake.paste_texts()) == 1
    assert not signals.state_path(repo=str(repo), topic=topic).exists()
    assert state_mutations == []

    declare(repo=repo, topic=topic, value="ready", mtime=1001.0)
    sup.evaluate(track=track, act=True)
    assert not fake.has(method="respawn")

    declare(repo=repo, topic=topic, value="idle-with-context-left", mtime=1002.0)
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=35))
    rewarned = sup.evaluate(track=track, act=True)

    assert rewarned.status == "warned"
    assert len(fake.paste_texts()) == 2
    assert signals.state_path(repo=str(repo), topic=topic).read_text(encoding="utf-8") == (
        "idle-with-context-left\n"
    )


def test_scenario_recovered_round_closure_defers_to_standing_state_file_content(*, tmp_path):
    """Scenario: A recovered-round closure defers to any standing state-file content."""
    repo, topic, session, fake = _track(tmp_path=tmp_path, ctx=8)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    assert len(fake.paste_texts()) == 1
    assert registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path).at

    state = declare(repo=repo, topic=topic, value="winding-down", mtime=1001.0)
    calls_before_recovery = list(fake.calls)
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=80))
    recovered = sup.evaluate(track=track, act=True)
    recovery_calls = fake.calls[len(calls_before_recovery) :]

    assert recovered.status == "idle"
    assert (
        registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path).at
        == 1000.0
    )
    assert state.read_text(encoding="utf-8") == "winding-down\n"
    assert not any(call[0] in {"keys", "paste", "respawn"} for call in recovery_calls)
    assert len(fake.paste_texts()) == 1
