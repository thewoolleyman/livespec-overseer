"""Read-only edge coverage for parked-delivery attention."""

from __future__ import annotations

from overseer import registry
from overseer.test_supervisor_builders import (
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def parked_delivery_capture(*, ctx: int = 80) -> str:
    return (
        "How do you want to proceed?\n"
        "❯ 1. Dispatch the waiting children\n"
        "  2. Leave the track parked\n"
        "Enter to select · ↑/↓ to navigate · Esc to cancel\n"
        "  @ livespec-console-beads-fabro-foreman❯\n"
        "    Console foreman, decision-relevant update for your open dispatch picker\n"
        "    fleet-ci-runner-pool track has EXECUTED the ClusterQueue resize (2026-08\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def make_parked_delivery_track(*, tmp_path, capture: str):
    repo, topic = make_plan(tmp_path=tmp_path, topic="parked-delivery")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        now=lambda: 2000.0,
        own_pane="%7",
        watch_repos=[str(repo)],
    )
    track = mapped_track(repo=repo, topic=topic, session=session)
    write_fresh_supervisor_state(repo=repo, topic=topic)
    return repo, topic, session, fake, sup, track


def test_parked_delivery_attention_projects_without_alerting_on_read_only_tick(*, tmp_path):
    _repo, _topic, _session, _fake, sup, track = make_parked_delivery_track(
        tmp_path=tmp_path, capture=parked_delivery_capture()
    )

    view = sup.evaluate(track=track, act=False)

    assert view.status == "parked-delivery"
    assert view.note == "queued delivery from livespec-console-beads-fabro-foreman"
    assert sup.alerted == {}
