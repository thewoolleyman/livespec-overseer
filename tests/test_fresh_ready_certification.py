"""Fresh ready certification edges for sessions with no opened round."""

from __future__ import annotations

import json
from pathlib import Path

import _supervisor_ready
import signals
from test_supervisor_builders import declare, make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _declared_ready(*, repo: Path, topic: str) -> signals.TrackState:
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    return state


def test_fresh_never_observed_ready_certifies_without_round(*, tmp_path: Path) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.store_path).write_text(
        json.dumps(
            {
                "topic": topic,
                "repo": str(repo),
                "tmux": "session",
                "added_at": "2026-08-16T23:45:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    obs = _supervisor_ready.round_observation(
        sup=sup,
        repo=str(repo),
        topic=topic,
        session="session",
        runtime="claude",
        declared=_declared_ready(repo=repo, topic=topic),
    )

    assert obs.ready is True
    assert obs.ready_uncertifiable_reason is None


def test_previously_observed_ready_without_round_stays_uncertifiable(*, tmp_path: Path) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.store_path).write_text(
        json.dumps(
            {
                "topic": topic,
                "repo": str(repo),
                "tmux": "session",
                "observed_session_identity": "claude:session:topic",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    obs = _supervisor_ready.round_observation(
        sup=sup,
        repo=str(repo),
        topic=topic,
        session="session",
        runtime="claude",
        declared=_declared_ready(repo=repo, topic=topic),
    )

    assert obs.ready is False
    assert obs.ready_uncertifiable_reason == "no supervision round open"
