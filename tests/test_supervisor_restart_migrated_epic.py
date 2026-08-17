"""Migrated supervisor epic certification for the restart interlock."""

from __future__ import annotations

import contextlib
import io as _io
import os
from pathlib import Path

import _supervisor_restart
import registry
import signals
from test_supervisor_builders import (
    TEST_EPIC,
    arm_ready_marker,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _canonical_migrated_epic_md(*, epic: str) -> str:
    return (
        f"# Ledger epic anchor\n\n{epic}\n\n"
        "This migrated research record preserves the legacy handoff's immutable "
        "epic anchor. Read live status from the ledger, not from this file.\n"
    )


def _write_migrated_epic(*, repo: Path, topic: str, epic: str) -> None:
    plan = repo / "plan" / topic
    plan.mkdir(parents=True, exist_ok=True)
    (plan / "epic.md").write_text(_canonical_migrated_epic_md(epic=epic), encoding="utf-8")


def _alert_key(*, repo: Path, topic: str, condition: str) -> tuple[str, str, str]:
    return (os.path.normpath(str(repo)), topic, condition)


def test_canonical_migrated_epic_certifies_supervisor_ready_restart_without_legacy_handoff(
    *, tmp_path: Path
) -> None:
    """The exact migrated epic.md template certifies; no hand-edited magic word needed."""
    repo, worker_topic = make_plan(tmp_path=tmp_path, topic="foreman")
    _write_migrated_epic(repo=repo, topic=worker_topic, epic=TEST_EPIC)
    topic = signals.supervisor_entity_topic(topic=worker_topic)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30), cmd="node")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    write_fresh_supervisor_state(repo=repo, topic=topic)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert fake.has(method="respawn")
    assert (
        _alert_key(repo=repo, topic=topic, condition="supervisor-handoff-missing")
        not in sup.alerted
    )


def test_migrated_supervisor_epic_without_own_epic_id_still_refuses(*, tmp_path: Path) -> None:
    """CONTROL: a migrated-looking epic.md must name this track's recorded epic id."""
    repo, worker_topic = make_plan(tmp_path=tmp_path, topic="foreman")
    _write_migrated_epic(repo=repo, topic=worker_topic, epic="overseer-other-epic")
    topic = signals.supervisor_entity_topic(topic=worker_topic)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30), cmd="node")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    with contextlib.redirect_stderr(_io.StringIO()):
        _supervisor_restart.do_restart(
            sup=sup, track=mapped_track(repo=repo, topic=topic, session=session), target=session
        )

    assert not fake.has(method="respawn")
    assert _alert_key(repo=repo, topic=topic, condition="supervisor-handoff-missing") in sup.alerted


def test_missing_migrated_supervisor_epic_still_refuses(*, tmp_path: Path) -> None:
    """CONTROL: a live supervisor plan with no epic.md remains uncertified."""
    repo, worker_topic = make_plan(tmp_path=tmp_path, topic="foreman")
    topic = signals.supervisor_entity_topic(topic=worker_topic)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30), cmd="node")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    with contextlib.redirect_stderr(_io.StringIO()):
        _supervisor_restart.do_restart(
            sup=sup, track=mapped_track(repo=repo, topic=topic, session=session), target=session
        )

    assert not fake.has(method="respawn")
    assert _alert_key(repo=repo, topic=topic, condition="supervisor-handoff-missing") in sup.alerted
