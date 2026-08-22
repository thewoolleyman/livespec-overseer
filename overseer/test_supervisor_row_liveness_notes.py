"""Beside-tests for supervisor.py — row color operator.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io
import json

import pytest
import registry
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    render_of,
    row_line,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


def _alert_events(*, text: str) -> list[dict[str, object]]:
    return [
        event for line in text.splitlines() if (event := json.loads(line))["severity"] == "alert"
    ]


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_liveness_helper_edges_are_covered(*, tmp_path):
    import _supervisor_liveness
    import signals
    from _supervisor_records import InjectState, Observation

    assert _supervisor_liveness.age_label(seconds=-10.0) == "0m"
    assert _supervisor_liveness.blocked_note(blocked="waiting", blocked_age_label=None) == "waiting"
    assert _supervisor_liveness.blocked_band_seconds(age=49 * 3600.0) == [14400, 86400, 172800]
    assert _supervisor_liveness.append_note(note="alpha", extra="beta") == "alpha; beta"

    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: 1000.0 + 901.0)
    track = mapped_track(repo=repo, topic=topic, session=session)
    obs = Observation(
        capture="",
        busy=False,
        gate=False,
        idle=True,
        is_codex=False,
        runtime="claude",
        codex_fallback=False,
        claude_status="idle",
        current_ctx=79,
        eff_ctx=79,
        ctx_stale_age=None,
        stale_ctx=None,
        injection_stamp=None,
        round_record=registry.RoundRecord(
            at=None,
            bands=[],
            expired_at=None,
            session_identity=None,
            malformed_reason=None,
        ),
        session_identity="claude:session:topic",
        ready_uncertifiable_reason="no supervision round open",
        istate=InjectState(),
        observed_at=1000.0 + 901.0,
        declared=signals.TrackState(token=signals.STATE_READY, detail="", mtime=1000.0),
        malformed=False,
        blocked=None,
        acked=False,
        ready=False,
    )

    surface = _supervisor_liveness.uncertifiable_ready_surface(
        sup=sup, track=track, session=session, pane=session, obs=obs, act=False
    )
    assert surface == (
        "15m: ready cannot certify: no supervision round open",
        {"ready-uncertifiable"},
    )

    obs.istate.uncertifiable_ready_mtime = 1000.0
    obs.istate.uncertifiable_ready_entry_age_label = "15m"
    obs.istate.uncertifiable_ready_alerted_bands = {14400}
    older = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: 1000.0 + 14401.0)
    _note, conditions = _supervisor_liveness.uncertifiable_ready_surface(
        sup=older, track=track, session=session, pane=session, obs=obs, act=True
    )
    assert "ready-uncertifiable-age-14400" in conditions


def test_uncertifiable_ready_renders_the_dead_end_not_restart_in_progress(*, tmp_path):
    """A structurally impossible `ready` act is an attention state, not acting status.

    The daemon can see the standing declaration, but with no open supervision round there
    is no stamp against which to certify it. The row must name that dead end and must not
    render as though a restart is already in progress.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=79))
    declare(repo=repo, topic=topic, value="ready", mtime=1000.0)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0 + 901.0)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)
    line = row_line(out=render_of(sup=sup, views=[view]), topic=topic)

    assert view.status == "ready-uncertifiable"
    assert "restarting" not in line
    assert "restart-in-progress" not in line
    assert "ready cannot certify" in line
    assert "no supervision round" in line
    assert not fake.has(method="respawn")


def test_alert_reports_again_when_the_reason_changes(*, tmp_path):
    """Edge-triggering is on the CONDITION, not merely on the status: a track that stays
    blocked for a DIFFERENT reason is a new event and must be reported."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        declare(repo=repo, topic=topic, value="blocked: reason one")
        sup.evaluate(track=track, act=True)
        declare(repo=repo, topic=topic, value="blocked: reason two")
        sup.evaluate(track=track, act=True)
    surfaced = _alert_events(text=err.getvalue())
    assert len(surfaced) == 2, surfaced
    assert "reason one" in str(surfaced[0]["message"])
    assert "reason two" in str(surfaced[1]["message"])
