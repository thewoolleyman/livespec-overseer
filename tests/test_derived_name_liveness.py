"""`overseer-j1r` — a live, in-tmux, working track must not report `session-gone`.

THE DEFECT. A manually-started Claude DERIVES its registry name from the repo
directory (``livespec-overseer-01``, ``nameSource: derived``); a daemon-spawned one
receives ``-n <topic>`` explicitly (``nameSource`` null). The daemon matched on topic
equality in TWO places — the identity gate (``topic in names``) and the
``live-outside-tmux`` softener (``live.name != topic``) — so a derived name failed
BOTH, and the row degraded straight past the informational status to
``session-gone``: the daemon's ONLY red status, on a track that was working fine.
Measured 2026-07-28: pid 3057142 alive in tmux ``codex-parity-and-rollout-safety``,
cwd in the repo, while the operator was told the work was lost.

WHY A CONTROL IS THE POINT OF THIS MODULE. A fix that simply stops saying
``session-gone`` is WORSE than the defect — ``session-gone`` is the alarm the whole
supervision contract rests on. So the two directions are pinned together here: a
derived-name live track must NOT read red, AND a genuinely absent session must STILL
read red. A third test pins that the identity gate was not relaxed: the daemon still
refuses to ACT on the name-mismatched pane, which is the R2/SF5 protection against a
reused window taking another topic's wrap-up and then being respawn-KILLED as it.
"""

import contextlib
import io as _io
import json

import registry
from test_supervisor_builders import (
    adopt_sup,
    idle_capture,
    make_plan,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_DERIVED_NAME = "repo-01"


def _stamp_name_source(*, sessions_dir, pid, name_source):
    """Add Claude's ``nameSource`` marker to an already-written registry file.

    Deliberately local rather than a parameter on the shared ``write_session``: only
    this module cares about the marker, and adding a seventh argument to that builder
    trips ``PLR0913`` — widening a lint waiver across every beside-test to serve one
    module is the wrong trade. ``None`` leaves the key ABSENT, which is exactly how a
    session launched with an explicit ``-n <topic>`` appears.
    """
    if name_source is None:
        return
    path = sessions_dir / f"{pid}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["nameSource"] = name_source
    path.write_text(json.dumps(data), encoding="utf-8")


def _sup_with_live_session(*, tmp_path, name, serve=True, ppid_to_pane=True, name_source="derived"):
    """A track whose mapped tmux session holds a live registry session called ``name``."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    if serve:
        fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40), cmd="node")
        fake.pane_pids[500] = session
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    if name is not None:
        write_session(sessions_dir=sessions_dir, pid=100, name=name, cwd=str(repo), status="busy")
        _stamp_name_source(sessions_dir=sessions_dir, pid=100, name_source=name_source)
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={100: 500} if ppid_to_pane else {},
        starttimes={100: "pt"},
    )
    # Drive the PRODUCTION wiring (registry → `_refresh_claude_status` →
    # `claude_names_by_session` → gate) rather than hand-injecting the map, so this
    # module exercises the same path the daemon runs every tick (the SF2 precedent).
    with contextlib.redirect_stderr(_io.StringIO()):
        sup._refresh_claude_status()
    return sup, fake, repo, topic, session


def test_a_live_in_tmux_track_with_a_derived_registry_name_is_not_reported_gone(*, tmp_path):
    """THE RED. Everything about this track is healthy except the NAME."""
    sup, _fake, repo, topic, session = _sup_with_live_session(tmp_path=tmp_path, name=_DERIVED_NAME)
    # Precondition: the mapped session really does hold a live agent under a name
    # that is NOT the topic — otherwise this test would pass vacuously.
    assert sup.claude_names_by_session.get(session) == {_DERIVED_NAME}
    assert topic != _DERIVED_NAME

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status != "session-gone"
    assert view.status == "live-name-mismatch"
    assert view.note is not None
    assert _DERIVED_NAME in view.note


def test_a_genuinely_absent_session_still_reports_session_gone(*, tmp_path):
    """THE CONTROL. The alarm must survive the fix — nothing live anywhere."""
    sup, _fake, repo, topic, session = _sup_with_live_session(
        tmp_path=tmp_path, name=None, serve=False
    )
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "session-gone"


def test_a_dead_pane_whose_agent_is_not_in_the_mapped_session_still_reports_gone(*, tmp_path):
    """THE SHARPER CONTROL. A live agent EXISTS for the repo, but it does not resolve
    to the mapped tmux session, so it is no evidence about THIS track. Without the
    ``== session`` scoping the softener would match any live agent in the repo and
    report every gone track as merely mismatched — silencing the alarm wholesale."""
    sup, _fake, repo, topic, session = _sup_with_live_session(
        tmp_path=tmp_path, name=_DERIVED_NAME, serve=False, ppid_to_pane=False
    )
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "session-gone"


def test_an_explicitly_named_foreign_session_still_reports_session_gone(*, tmp_path):
    """THE DISCRIMINATOR CONTROL, and the one that keeps this fix honest.

    By NAME alone, our own auto-named track (``repo-01``) and a DIFFERENT topic's
    session squatting in a reused window (``beta``, launched with an explicit
    ``-n beta``) are indistinguishable — both simply differ from the topic. Only
    ``nameSource`` separates them. Softening the explicit case too would tell the
    operator to rename a window another LIVE track is using, which would hijack it,
    and would weaken the R2/SF5 report that this really is not our session.
    """
    sup, _fake, repo, topic, session = _sup_with_live_session(
        tmp_path=tmp_path, name="beta", name_source=None
    )
    # Precondition: identical shape to the RED case except for the name's provenance.
    assert sup.claude_names_by_session.get(session) == {"beta"}

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "session-gone"


def test_the_identity_gate_is_not_relaxed_by_the_softer_report(*, tmp_path):
    """THE ACT CONTROL (R2/SF5). Reporting changed; the ACT guard did not. The daemon
    must still refuse to keystroke into a pane it cannot prove is ours — that is what
    stops a reused window taking another topic's wrap-up and then a `ready` respawn
    KILLING it."""
    sup, fake, repo, topic, session = _sup_with_live_session(tmp_path=tmp_path, name=_DERIVED_NAME)
    sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")
