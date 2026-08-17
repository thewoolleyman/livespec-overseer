"""The post-ready downgrade write may never clobber a declaration the session wrote.

`downgrade_ready_after_activity` rewrites a `ready` the session has contradicted into a
diagnostic `winding-down: auto @<ts>`. That write lands on a SESSION-OWNED file, so it
needs the same "only while the file still holds X" shape every other daemon write onto
session state carries (the idle-nudge marker removal). A `blocked: <reason>` is a human
escalation the daemon must never destroy.
"""

from __future__ import annotations

from overseer import _supervisor_state, registry, signals
from overseer.test_supervisor_builders import (
    declare,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import FakeTmux


def test_a_blocked_written_inside_the_write_window_is_never_clobbered(*, tmp_path, capsys):
    """The session wins the race between the daemon's observation and its write.

    `sup.now()` is read after the daemon observes the declaration and before it writes,
    so a clock that declares `blocked:` reproduces exactly that interleaving: the daemon
    decided to downgrade a `ready` that no longer exists by the time the write lands.
    The escalation must survive.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)

    def _now() -> float:
        declare(
            repo=repo,
            topic=topic,
            value=f"{signals.STATE_BLOCKED}: needs a human",
            mtime=1400.0,
        )
        return 1400.0

    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=_now)
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)

    assert (
        _supervisor_state.downgrade_ready_after_activity(sup=sup, track=track, ready=True) is True
    )

    surviving = signals.read_state(repo=str(repo), topic=topic)
    assert surviving is not None
    assert surviving.token == signals.STATE_BLOCKED
    assert surviving.detail == "needs a human"
    assert "skipped downgrading ready declaration" in capsys.readouterr().err


def test_the_downgrade_still_rewrites_a_ready_that_is_unchanged_at_write_time(*, tmp_path):
    """The guard must not silently disable the downgrade in the ordinary case."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: 1400.0)
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)

    assert (
        _supervisor_state.downgrade_ready_after_activity(sup=sup, track=track, ready=True) is False
    )

    downgraded = signals.read_state(repo=str(repo), topic=topic)
    assert downgraded is not None
    assert downgraded.token == signals.STATE_WINDING_DOWN
    assert downgraded.detail == "auto @1400"
