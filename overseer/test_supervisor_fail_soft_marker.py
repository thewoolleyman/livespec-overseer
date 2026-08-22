"""Beside-tests for supervisor.py — fail soft marker.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import _supervisor_config
import _supervisor_nudge
import _supervisor_records
import _supervisor_state
import pytest
import registry
import signals
from test_supervisor_builders import (
    arm_ready_marker,
    declare,
    idle_capture,
    key_for,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
    undeletable_state_file,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_clear_state_logs_an_undeletable_marker_and_still_closes_the_round(*, tmp_path):
    """`_clear_state` must not raise when the marker cannot be deleted: it logs the
    failure and still performs the REST of the clear (stamp + in-memory round), so a
    single unlink failure cannot abort the tick mid-restart."""
    repo, topic = make_plan(tmp_path=tmp_path)
    undeletable_state_file(repo=repo, topic=topic)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    key = key_for(repo=repo, topic=topic)
    sup.inject[key] = _supervisor_records.InjectState(last_ctx=30)
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup._clear_state(track=mapped_track(repo=repo, topic=topic, session="sesA"))

    assert "could not delete state file" in err.getvalue()
    assert topic in err.getvalue()
    # The round still closed: the durable stamp is gone and the in-memory state popped.
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )
    assert key not in sup.inject


def test_state_diagnostic_write_failure_logs_and_returns_false(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    blocker = signals.marker_dir(repo=str(repo), topic=topic)
    blocker.parent.mkdir(parents=True)
    blocker.write_text("file where topic dir belongs\n", encoding="utf-8")
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        written = _supervisor_state.write_state_diagnostic(
            sup=sup,
            track=mapped_track(repo=repo, topic=topic, session="sesA"),
            token=signals.STATE_RESTARTED,
            detail="restart completed",
        )

    assert written is False
    assert "could not write state diagnostic" in err.getvalue()
    assert topic in err.getvalue()


def test_unreadable_ready_marker_is_never_expired(*, tmp_path):
    """`_expire_aged_ready` expires a declaration it can prove is aged. An UNREADABLE
    marker proves nothing, so nothing is expired and nothing is cleared —
    `ready_valid` is the gate that already refused to trust it."""
    repo, topic = make_plan(tmp_path=tmp_path)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    track = mapped_track(repo=repo, topic=topic, session="sesA")

    assert sup._expire_aged_ready(track=track) is False  # no state file → unreadable
    # and the round was NOT closed behind the daemon's back
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )


def test_void_stale_blocked_keeps_the_reason_when_the_marker_no_longer_declares_one(*, tmp_path):
    """`_void_stale_blocked` only retires a `blocked:` it can still SEE on disk. An
    unreadable file, or one that now declares something else, leaves the caller's reason
    untouched — voiding on a read it could not make would destroy a live declaration."""
    repo, topic = make_plan(tmp_path=tmp_path)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    track = mapped_track(repo=repo, topic=topic, session="sesA")
    blocked = "blocked: waiting on the schema call"

    # (a) no state file at all → unreadable
    assert sup._void_stale_blocked(track=track, blocked=blocked, generating=True) == blocked
    # (b) the file exists but the session has since declared `ready` — not a block anymore
    arm_ready_marker(
        repo=repo, topic=topic, mtime=1.0
    )  # far past the grace, so only the token gates
    assert sup._void_stale_blocked(track=track, blocked=blocked, generating=True) == blocked
    # Neither path ran `_clear_state`, so the round is intact.
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )


def test_idle_nudge_marker_write_failure_is_logged_not_raised(*, tmp_path):
    """The daemon-owned `idle-with-context-left` marker lives under a per-topic dir. When
    that dir cannot be created the write is logged and skipped — never raised — and no
    marker is left behind, so the next idle tick simply re-nudges."""
    repo, topic = make_plan(tmp_path=tmp_path)
    marker_dir = signals.state_path(repo=str(repo), topic=topic).parent
    marker_dir.parent.mkdir(parents=True, exist_ok=True)
    marker_dir.write_text("a FILE where the marker dir belongs\n", encoding="utf-8")
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup._write_idle_nudge_state(track=mapped_track(repo=repo, topic=topic, session="sesA"))

    assert "could not write idle-nudge marker" in err.getvalue()
    assert signals.read_state(repo=str(repo), topic=topic) is None  # nothing was written


def test_idle_nudge_clear_diagnostic_failure_does_not_log_a_clear(*, tmp_path, monkeypatch):
    repo, topic = make_plan(tmp_path=tmp_path)
    declare(repo=repo, topic=topic, value=signals.STATE_IDLE_WITH_CONTEXT_LEFT)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    monkeypatch.setattr(
        _supervisor_nudge._supervisor_state, "write_state_diagnostic", lambda **_kw: False
    )
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        _supervisor_nudge.clear_idle_nudge_state(
            sup=sup, track=mapped_track(repo=repo, topic=topic, session="sesA")
        )

    assert "cleared idle-with-context-left marker" not in err.getvalue()
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT


def test_failed_nudge_alerts_and_writes_no_marker_so_it_retries(*, tmp_path):
    """The nudge marker is written only AFTER the paste lands. A failed paste must
    ALERT (naming the tmux coordinate) and leave the episode unmarked, so the next tick
    re-nudges rather than silently recording a keep-going prompt that never arrived."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=73)
    )  # idle, well above threshold
    fake.paste_ok = False  # the bracketed paste does not land
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)  # stamps idle_since
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "idle-with-context-left"
    assert "idle-with-context-left nudge FAILED" in err.getvalue()
    assert session in err.getvalue()  # the alert names where to go
    assert signals.read_state(repo=str(repo), topic=topic) is None  # episode NOT marked handled
    # Unmarked means un-given-up-on: the next idle tick tries the nudge again.
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
    assert nudge_count(fake=fake) == 2  # re-attempted, not silently marked handled
