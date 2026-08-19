"""Adoption preserves mapping epic identity across row recreation."""

from __future__ import annotations

import os

import registry
from test_supervisor_builders import adopt_sup, make_plan, write_session
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_adopt_sessions_preserves_epic_seen_before_mapping_removal(*, tmp_path):
    """A removed mapping row must not lose its epic when a live session re-adopts it."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="foreman-improvements")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    ppid, starttimes = {100: 101}, {100: "pt"}
    fake.pane_pids[101] = "live-renamed-session"
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo)
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid=ppid,
        starttimes=starttimes,
        watch_repos=[str(repo)],
    )
    registry.append_mapping(
        track=registry.Track(
            topic=topic,
            repo=str(repo),
            tmux="old-session",
            epic="overseer-au3pt3",
        ),
        store_path=sup.store_path,
    )

    assert sup.adopt_sessions() == []
    assert registry.remove_mapping(repo=str(repo), topic=topic, store_path=sup.store_path) == 1

    adopted = sup.adopt_sessions()

    assert [(track.topic, track.epic) for track in adopted] == [(topic, "overseer-au3pt3")]
    rows = registry.read_valid_mapping(store_path=sup.store_path)
    assert [(row.repo, row.topic, row.tmux, row.epic) for row in rows] == [
        (
            os.path.normpath(str(repo)),
            topic,
            "live-renamed-session",
            "overseer-au3pt3",
        )
    ]
