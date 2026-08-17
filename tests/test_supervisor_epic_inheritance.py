"""A `-supervisor` entity topic inherits its epic from the topic it supervises.

Regression for overseer-h6e0: a supervisor track can never have its own
`plan/<topic>/` directory by design, so `epic_from_plan_anchor` had nothing to
derive an epic from, and `supervisor.py add` refused the reserved `-supervisor`
suffix outright — a supervisor track could never record a plan epic id, so it
could never be respawned. This fix derives the epic from the SUPERVISED
worker topic's plan directory instead, only when that directory exists; the
guard must still refuse a `-supervisor` topic with no supervised counterpart,
and must still refuse `-foreman` topics entirely (untouched by this fix).
"""

from __future__ import annotations

import contextlib
import io as _io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "overseer"))

import signals
import supervisor
from test_supervisor_builders import TEST_EPIC, isolate_store

__all__: list[str] = []


def _write_epic_md(*, plan_dir: Path, epic_id: str) -> None:
    plan_dir.mkdir(parents=True)
    plan_dir.joinpath("epic.md").write_text(
        f"# Ledger epic anchor\n\n{epic_id}\n\n"
        "This migrated research record preserves the legacy handoff's immutable "
        "epic anchor. Read live status from the ledger, not from this file.\n",
        encoding="utf-8",
    )


def test_supervisor_topic_inherits_epic_from_the_supervised_worker_plan(*, tmp_path, monkeypatch):
    """POSITIVE: a `-supervisor` topic with a real supervised plan directory."""
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = tmp_path / "repo"
    _write_epic_md(plan_dir=repo / "plan" / "topic", epic_id=TEST_EPIC)

    rc = supervisor.main(argv=["add", "--repo", str(repo), "--topic", "topic-supervisor"])

    assert rc == 0
    rows = [line for line in store.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert '"topic": "topic-supervisor"' in rows[0]
    assert f'"epic": "{TEST_EPIC}"' in rows[0]


def test_supervisor_topic_with_no_supervised_plan_still_refused(*, tmp_path, monkeypatch):
    """CONTROL: the guard must still refuse a `-supervisor` topic with no counterpart."""
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        rc = supervisor.main(argv=["add", "--repo", str(repo), "--topic", "topic-supervisor"])

    assert rc == 1
    assert "refusing reserved supervisor topic" in err.getvalue()
    assert not store.exists()


def test_foreman_topic_still_refused_unconditionally(*, tmp_path, monkeypatch):
    """CONTROL: `-foreman` topics are untouched by this fix, even with a matching plan dir."""
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = tmp_path / "repo"
    _write_epic_md(plan_dir=repo / "plan" / "topic", epic_id=TEST_EPIC)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        rc = supervisor.main(argv=["add", "--repo", str(repo), "--topic", "topic-foreman"])

    assert rc == 1
    assert "refusing reserved supervisor topic" in err.getvalue()
    assert not store.exists()


def test_topic_supervised_worker_precise_about_the_suffix():
    """CONTROL: the new signals helper distinguishes -supervisor from -foreman and plain."""
    assert signals.topic_supervised_worker(topic="topic-supervisor") == "topic"
    assert signals.topic_supervised_worker(topic="topic-foreman") is None
    assert signals.topic_supervised_worker(topic="topic") is None


def test_foreman_topic_helper_precise_and_supervisor_topic_fails_closed():
    assert signals.is_foreman_topic(topic="topic-foreman") is True
    assert signals.is_foreman_topic(topic="topic-supervisor") is False
    assert signals.is_foreman_topic(topic="topic") is False

    with pytest.raises(ValueError, match="-foreman"):
        signals.supervisor_topic(entity_topic="topic-foreman")
