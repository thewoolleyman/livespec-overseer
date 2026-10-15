"""Integration-tier SPECIFICATION v058 busy-session wrap-up delivery.

Maintainer ruling 2026-10-15: a busy session whose input is positively empty still
receives the owed wind-down; a ready with no delivered round is retired once the track
owes one; and the context-compaction latch is a defined obligation. Each test drives a
real ``Supervisor.evaluate`` act tick over the fake terminal and names the scenario
heading of ``SPECIFICATION/scenarios.md`` it proves.
"""

import contextlib
import importlib
import io as _io
import os
import pathlib

import pytest

from overseer import (
    _supervisor_observe,
    codex_sessions,
    registry,
    signals,
)
from overseer._supervisor_config import (
    ACK_STALE_AFTER,
    MARKER_VOID_GRACE,
    READY_ARM_MAX_AGE,
    track_key,
)
from overseer.test_supervisor_builders import (
    SPINNER,
    WRAPUP_SENTINEL,
    busy_capture,
    busy_typed_capture,
    codex_busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    wrapup_count,
)
from overseer.test_supervisor_compaction_builders import (
    SUCCESSOR_CLAUDE_IDENTITY,
    claude_compaction_track,
    claude_idle,
    compaction_record,
    show_pane,
    stored_track,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _v058(*, module, name):
    # Resolved at call time, not import time, so a tree without the v058 modules fails
    # each test on its own assertion rather than failing the whole file at collection.
    return getattr(importlib.import_module(f"overseer.{module}"), name)


def _codex_busy_withheld_note():
    return _v058(module="_supervisor_busy_delivery", name="CODEX_BUSY_WITHHELD_NOTE")


def _claude_track(*, tmp_path, capture, clock=None):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    kwargs = {} if clock is None else {"now": lambda: clock["t"]}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, **kwargs)
    return repo, topic, session, fake, sup


def _act(*, sup, repo, topic, session, err=None):
    sink = err if err is not None else _io.StringIO()
    with contextlib.redirect_stderr(sink):
        return sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)


def _stamp(*, sup, repo, topic):
    return registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


def _busy_picker(*, ctx):
    return (
        f"● response\n{SPINNER}\nHow do you want to ratify?\n"
        "❯ 1. Yes, run /livespec:revise\n  2. No, ask the operator\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


# ## Scenario: A busy session with an empty input box receives the wrap-up
@pytest.mark.parametrize(
    ("capture", "claude_status"),
    [(busy_capture(ctx=40), None), (idle_capture(ctx=40), "busy")],
    ids=["generating", "sub-agent"],
)
def test_scenario_busy_session_with_empty_input_receives_the_wrapup(
    *, tmp_path, capture, claude_status
):
    repo, topic, session, fake, sup = _claude_track(tmp_path=tmp_path, capture=capture)
    if claude_status is not None:
        sup.claude_status_by_session = {session: claude_status}

    view = _act(sup=sup, repo=repo, topic=topic, session=session)

    assert view.status == "warned"
    assert wrapup_count(fake=fake) == 1
    assert _stamp(sup=sup, repo=repo, topic=topic) is not None
    assert "this session is still working" in "".join(fake.paste_texts())
    assert not fake.has(method="respawn")


# ## Scenario: Typed input, a gate, or a human wait suppresses the wrap-up of a busy session
@pytest.mark.parametrize(
    ("capture", "claude_status"),
    [
        (busy_typed_capture(ctx=40), None),
        (_busy_picker(ctx=40), None),
        (busy_capture(ctx=40), "waiting"),
    ],
    ids=["typed-input", "gate", "human-wait"],
)
def test_scenario_typed_input_gate_or_human_wait_suppresses_a_busy_wrapup(
    *, tmp_path, capture, claude_status
):
    repo, topic, session, fake, sup = _claude_track(tmp_path=tmp_path, capture=capture)
    if claude_status is not None:
        sup.claude_status_by_session = {session: claude_status}

    _act(sup=sup, repo=repo, topic=topic, session=session)

    assert wrapup_count(fake=fake) == 0
    assert _stamp(sup=sup, repo=repo, topic=topic) is None
    assert not fake.has(method="respawn")


# ## Scenario: A busy Codex session whose empty composer cannot be proven is surfaced, not pasted
def test_scenario_busy_codex_without_proven_empty_composer_is_surfaced(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=codex_busy_capture(ctx=40), cmd="bun")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=321, name=topic, cwd=str(repo), session_id="codex-1"
        )
    }
    err = _io.StringIO()

    view = _act(sup=sup, repo=repo, topic=topic, session=session, err=err)

    assert wrapup_count(fake=fake) == 0
    assert _stamp(sup=sup, repo=repo, topic=topic) is None
    assert view.status == "working"
    assert _codex_busy_withheld_note() in (view.note or "")
    assert _codex_busy_withheld_note() in err.getvalue()


# ## Scenario: A ready with no delivered round is retired and a fresh round delivered
def test_scenario_unrounded_ready_is_retired_and_a_fresh_round_delivered(*, tmp_path):
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup = _claude_track(
        tmp_path=tmp_path, capture=idle_capture(ctx=40), clock=clock
    )
    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"])

    clock["t"] += MARKER_VOID_GRACE + 1
    err = _io.StringIO()
    retired = _act(sup=sup, repo=repo, topic=topic, session=session, err=err)

    assert not marker.exists()
    assert "retired a ready declaration with no delivered round" in err.getvalue()
    assert wrapup_count(fake=fake) == 0
    assert not fake.has(method="respawn")
    assert retired.status != "restarting"

    clock["t"] += 1
    assert _act(sup=sup, repo=repo, topic=topic, session=session).status == "warned"
    assert wrapup_count(fake=fake) == 1
    stamp = _stamp(sup=sup, repo=repo, topic=topic)
    assert stamp is not None

    clock["t"] += 5
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=stamp + 1.0)
    assert _act(sup=sup, repo=repo, topic=topic, session=session).status == "restarting"
    assert fake.has(method="respawn")


# ## Scenario: A ready with no delivered round on a track that owes no wind-down is surfaced,
# not retired
def test_scenario_unrounded_ready_owing_no_wind_down_is_left_standing(*, tmp_path):
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup = _claude_track(
        tmp_path=tmp_path, capture=idle_capture(ctx=70), clock=clock
    )
    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"])
    clock["t"] += MARKER_VOID_GRACE * 30

    view = _act(sup=sup, repo=repo, topic=topic, session=session)

    assert marker.exists()
    assert view.status == "ready-uncertifiable"
    assert wrapup_count(fake=fake) == 0
    assert not fake.has(method="respawn")


def _latched(*, tmp_path):
    """A same-session compaction during busy work: 45% busy, then 82% busy, no paste."""
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    track = stored_track(sup=sup, repo=repo, topic=topic)
    show_pane(fake=fake, session=session, capture=busy_typed_capture(ctx=45))
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
    show_pane(fake=fake, session=session, capture=busy_typed_capture(ctx=82))
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.evaluate(track=stored_track(sup=sup, repo=repo, topic=topic), act=True)
    return repo, topic, session, fake, sup, err


def _tick(*, sup, repo, topic):
    with contextlib.redirect_stderr(_io.StringIO()):
        return sup.evaluate(track=stored_track(sup=sup, repo=repo, topic=topic), act=True)


# ## Scenario: A context rise under an unchanged session identity latches a restart obligation
def test_scenario_same_identity_rise_latches_and_the_wrapup_states_the_compaction(*, tmp_path):
    repo, topic, session, fake, sup, err = _latched(tmp_path=tmp_path)

    latched = compaction_record(sup=sup, repo=repo, topic=topic)
    assert latched is not None and latched.restart_required is True
    assert err.getvalue().count("CONTEXT COMPACTION detected") == 1
    assert wrapup_count(fake=fake) == 0

    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    assert _tick(sup=sup, repo=repo, topic=topic).status == "warned"
    pasted = "".join(fake.paste_texts())
    assert WRAPUP_SENTINEL in pasted
    notice = _v058(module="_supervisor_wrapup_injection", name="COMPACTION_WRAPUP_NOTICE")
    assert notice.split(":", 1)[0] in pasted
    assert not fake.has(method="respawn")


# ## Scenario: A changed session identity clears the compaction latch
def test_scenario_a_changed_session_identity_clears_the_latch(*, tmp_path):
    repo, topic, session, fake, sup, _err = _latched(tmp_path=tmp_path)

    sup.claude_identity_by_session[(session, topic)] = SUCCESSOR_CLAUDE_IDENTITY
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=96))
    _tick(sup=sup, repo=repo, topic=topic)

    cleared = compaction_record(sup=sup, repo=repo, topic=topic)
    assert cleared is not None and cleared.restart_required is False
    assert cleared.session_identity == SUCCESSOR_CLAUDE_IDENTITY


# ## Scenario: A latched round is never closed as recovered
def test_scenario_a_latched_round_is_never_closed_as_recovered(*, tmp_path):
    repo, topic, session, fake, sup, _err = _latched(tmp_path=tmp_path)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    _tick(sup=sup, repo=repo, topic=topic)
    stamp = _stamp(sup=sup, repo=repo, topic=topic)
    assert stamp is not None
    assert signals.read_state(repo=str(repo), topic=topic) is None

    _tick(sup=sup, repo=repo, topic=topic)

    assert _stamp(sup=sup, repo=repo, topic=topic) == stamp


# ## Scenario: A session told of a compaction keeps its declaration on context recovery
def test_scenario_the_latched_wrapup_tells_the_session_not_to_expire_its_declaration(*, tmp_path):
    repo, topic, session, fake, sup, _err = _latched(tmp_path=tmp_path)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    _tick(sup=sup, repo=repo, topic=topic)

    pasted = "".join(fake.paste_texts())
    assert "A restart is REQUIRED regardless of the remaining context you now see" in pasted
    assert "do NOT treat this wind-down, or any declaration you write for it, as expired" in (
        " ".join(pasted.split())
    )


# --- edges of the same scenarios -------------------------------------------------------


def _codex_busy_track(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=codex_busy_capture(ctx=40), cmd="bun")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=321, name=topic, cwd=str(repo), session_id="codex-1"
        )
    }
    return repo, topic, session, fake, sup


def test_the_read_only_listing_names_a_withheld_codex_wrapup_without_alerting(*, tmp_path):
    repo, topic, session, fake, sup = _codex_busy_track(tmp_path=tmp_path)
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)

    assert _codex_busy_withheld_note() in (view.note or "")
    assert _codex_busy_withheld_note() not in err.getvalue()
    assert wrapup_count(fake=fake) == 0


def test_a_busy_session_owing_only_the_expiry_notice_receives_it_and_stays_working(*, tmp_path):
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup = _claude_track(
        tmp_path=tmp_path, capture=idle_capture(ctx=48), clock=clock
    )
    assert _act(sup=sup, repo=repo, topic=topic, session=session).status == "warned"
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
    clock["t"] = 1010.0 + READY_ARM_MAX_AGE + 1.0
    _act(sup=sup, repo=repo, topic=topic, session=session)

    # A stale `winding-down` holds the round open against recovery, and the track is back
    # above the line (a rise within the compaction tolerance) and busy: only the round's
    # expiry notice is owed, and it lands through the empty box.
    declare(
        repo=repo,
        topic=topic,
        value=signals.STATE_WINDING_DOWN,
        mtime=clock["t"] - ACK_STALE_AFTER - 1.0,
    )
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=52))
    clock["t"] += 1.0
    listed = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)
    assert listed.status == "working"
    assert [t for t in fake.paste_texts() if "EXPIRED" in t] == []
    view = _act(sup=sup, repo=repo, topic=topic, session=session)

    assert view.status == "working"
    assert len([t for t in fake.paste_texts() if "EXPIRED" in t]) == 1


def test_context_rising_above_the_line_before_a_busy_paste_cancels_it(*, tmp_path):
    repo, topic, session, fake, sup = _claude_track(
        tmp_path=tmp_path,
        capture=[busy_capture(ctx=40)] * 3 + [busy_capture(ctx=70)],
    )

    view = _act(sup=sup, repo=repo, topic=topic, session=session)

    assert view.status == "settling"
    assert wrapup_count(fake=fake) == 0
    assert _stamp(sup=sup, repo=repo, topic=topic) is None


def _unrounded_ready_track(*, tmp_path):
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup = _claude_track(
        tmp_path=tmp_path, capture=idle_capture(ctx=40), clock=clock
    )
    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"])
    clock["t"] += MARKER_VOID_GRACE + 1
    return repo, topic, session, fake, sup, marker


def test_a_retirement_never_clobbers_a_declaration_rewritten_after_it_was_judged(*, tmp_path):
    repo, topic, session, fake, sup, marker = _unrounded_ready_track(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=session)
    obs = _supervisor_observe.observe(
        sup=sup,
        track=track,
        session=session,
        target=session,
        key=track_key(repo=str(repo), topic=topic),
    )
    os.utime(marker, (2000.0, 2000.0))  # the session wrote a fresh `ready` meanwhile

    retire_unrounded_ready = _v058(
        module="_supervisor_unrounded_ready", name="retire_unrounded_ready"
    )
    retired = retire_unrounded_ready(
        sup=sup, track=track, obs=obs, session=session, pane=session, act=True
    )

    assert retired is False
    assert marker.exists()


def test_a_declaration_already_gone_at_delete_time_counts_as_retired(*, tmp_path, monkeypatch):
    repo, topic, session, fake, sup, marker = _unrounded_ready_track(tmp_path=tmp_path)

    def vanished(self, *_args, **_kwargs):
        raise FileNotFoundError(str(self))

    monkeypatch.setattr(pathlib.Path, "unlink", vanished)
    err = _io.StringIO()
    _act(sup=sup, repo=repo, topic=topic, session=session, err=err)

    assert "retired a ready declaration with no delivered round" in err.getvalue()


def test_a_failed_retirement_delete_is_surfaced_and_keeps_the_declaration(*, tmp_path, monkeypatch):
    repo, topic, session, fake, sup, marker = _unrounded_ready_track(tmp_path=tmp_path)

    def refused(self, *_args, **_kwargs):
        raise PermissionError(str(self))

    monkeypatch.setattr(pathlib.Path, "unlink", refused)
    err = _io.StringIO()
    _act(sup=sup, repo=repo, topic=topic, session=session, err=err)

    assert "could not retire a ready declaration" in err.getvalue()
    assert marker.exists()
    assert wrapup_count(fake=fake) == 0
