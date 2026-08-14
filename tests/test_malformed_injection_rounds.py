"""Regression coverage for malformed injection-round self-healing."""

from __future__ import annotations

import json
from pathlib import Path

import registry
import signals
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    wrapup_count,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_malformed_round_is_reopened_with_current_session_identity(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    stamp_path = Path(sup.stamp_path)
    stamp_path.write_text(
        json.dumps({f"{repo}\t{topic}": {"at": 700.0, "bands": []}}),
        encoding="utf-8",
    )

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=stamp_path)
    assert record.at == 1000.0
    assert record.session_identity == f"claude:{session}:{topic}"
    assert record.malformed_reason is None
    assert wrapup_count(fake=fake) == 1


def test_ready_uncertifiable_status_names_malformed_round_record_not_absence(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    stamp_path = Path(sup.stamp_path)
    stamp_path.write_text(
        json.dumps({f"{repo}\t{topic}": {"at": 1000.0, "bands": []}}),
        encoding="utf-8",
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1.0)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "ready-uncertifiable"
    assert view.note is not None
    assert "ready cannot certify: round record missing session identity" in view.note
    assert "no supervision round open" not in view.note
