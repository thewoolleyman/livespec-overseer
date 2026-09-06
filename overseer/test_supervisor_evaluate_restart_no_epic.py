"""Beside-tests for the ready-restart branch's refusal when no resume prompt exists.

These re-home coverage the foreman-test deletion took with it. The refusal arc — a
session declared `ready`, but the daemon can build no resume prompt for its track, so
the declaration is PRESERVED and the operator is told instead of a live process being
destroyed — used to be reached through a `ForemanSeat`, which SPECIFICATION v047
retired. It survives for every track kind that carries no resumable identity, and an
unassigned plan row is the surviving one: it records no epic and no tmux session, so
`resume_prompt` answers None and the one-shot epic re-derive does not apply to it.

``import _supervisor_evaluate_restart`` resolves via conftest.py.
"""

from __future__ import annotations

import _supervisor_evaluate_restart
import registry
from test_supervisor_builders import make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_PANE = "%7"
_SESSION = "demo-topic"


def _request(*, tmp_path, track: registry.Track, act: bool):
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    return sup, _supervisor_evaluate_restart.ReadyRestartRequest(
        sup=sup,
        track=track,
        session=_SESSION,
        target=_PANE,
        is_codex=False,
        note=None,
        act=act,
    )


def _unassigned_track(*, repo) -> registry.Track:
    return registry.Track(topic="demo-topic", repo=str(repo), assigned=False)


def test_a_track_with_no_resumable_identity_is_reported_instead_of_respawned(*, tmp_path):
    """The cardinal-rule-safe refusal: report, never spend the declaration on a respawn."""
    sup, request = _request(tmp_path=tmp_path, track=_unassigned_track(repo=tmp_path), act=True)

    decision = _supervisor_evaluate_restart.ready_restart_decision(request=request)

    assert decision.status == "blocked:human"
    assert decision.note == "ready cannot respawn: no plan epic recorded"
    assert decision.active_conditions == {"blocked-human"}
    assert not sup.tmux.has(method="respawn")


def test_that_refusal_alerts_the_operator_under_the_missing_epic_condition(*, tmp_path):
    sup, request = _request(tmp_path=tmp_path, track=_unassigned_track(repo=tmp_path), act=True)
    alerted: list[tuple[str, str, str]] = []
    sup.alert = lambda **kwargs: alerted.append(  # type: ignore[method-assign]
        (kwargs["condition"], kwargs["message"], kwargs["pane"])
    )

    _supervisor_evaluate_restart.ready_restart_decision(request=request)

    assert alerted == [
        ("restart-plan-epic-missing", "ready cannot respawn: no plan epic recorded", _PANE)
    ]


def test_a_read_only_evaluation_of_that_refusal_raises_no_alert(*, tmp_path):
    sup, request = _request(tmp_path=tmp_path, track=_unassigned_track(repo=tmp_path), act=False)
    alerted: list[str] = []
    sup.alert = lambda **kwargs: alerted.append(kwargs["condition"])  # type: ignore[method-assign]

    decision = _supervisor_evaluate_restart.ready_restart_decision(request=request)

    assert decision.status == "blocked:human"
    assert alerted == []


def test_a_track_that_does_have_a_resume_prompt_restarts(*, tmp_path):
    """The contrasting arc, so the refusal above is not vacuously satisfied."""
    track = registry.Track(
        topic="demo-topic", repo=str(tmp_path), tmux=_SESSION, epic="demo-epic-1"
    )
    sup, request = _request(tmp_path=tmp_path, track=track, act=False)
    del sup

    decision = _supervisor_evaluate_restart.ready_restart_decision(request=request)

    assert decision.status == "restarting"
    assert decision.active_conditions == set()
