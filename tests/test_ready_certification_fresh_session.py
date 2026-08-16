"""Repo-level certification coverage for fresh ready declarations."""

import _supervisor_ready
import signals
from test_supervisor_builders import declare, make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _declared_ready(*, repo, topic):
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    return state


def test_ready_certifies_without_round_when_live_session_identity_matches_topic(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    obs = _supervisor_ready.round_observation(
        sup=sup,
        repo=str(repo),
        topic=topic,
        session="session",
        runtime="claude",
        declared=_declared_ready(repo=repo, topic=topic),
    )

    assert obs.record.at is None
    assert obs.session_identity == f"claude:session:{topic}"
    assert obs.ready is True
    assert obs.ready_uncertifiable_reason is None
