"""Persistence coverage for the restart-interlock one-shot epic re-derive.

Companion to the behavioral proof in
`tests/integration/test_ready_declaration_restart.py::test_stale_epic_null_row_heals_and_restarts_on_ready`,
which shows the current TICK restarts once healed. This covers the durable
side: overseer-vbmq's whole point is that a LATER tick must see the healed
row directly rather than re-deriving from scratch every time.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "overseer"))

import _registry_core
import _supervisor_restart
import registry
from test_supervisor_builders import TEST_EPIC, make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _isolate_store(*, tmp_path, monkeypatch):
    store = tmp_path / "map.jsonl"
    monkeypatch.setattr(_registry_core, "DEFAULT_STORE_PATH", store)
    return store


def test_rederive_persists_the_healed_epic_for_a_later_tick_to_see(*, tmp_path, monkeypatch):
    """POSITIVE: a stored row with epic=None gets its epic written back."""
    _isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo, topic = make_plan(tmp_path=tmp_path, topic="stale-epic")
    track = registry.Track(topic=topic, repo=str(repo), tmux=topic, epic=None)
    registry.append_mapping(track=track, store_path=None)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())

    healed = _supervisor_restart.rederive_epic_if_stale(sup=sup, track=track, act=True)

    assert healed.epic == TEST_EPIC
    stored = registry.read_valid_mapping(store_path=None)
    assert len(stored) == 1
    assert stored[0].epic == TEST_EPIC


def test_rederive_is_a_noop_when_the_anchor_is_genuinely_unresolvable(*, tmp_path, monkeypatch):
    """CONTROL: a row whose anchor doesn't resolve stays None, store untouched.

    Stubs `registry.epic_from_plan_anchor` to return None rather than pointing
    it at a genuinely anchorless plan directory — that function's own
    unresolvable-anchor behavior (including its ledger-tag fallback via a real
    `bd` subprocess) is that function's OWN test surface, not this one's; this
    isolates `rederive_epic_if_stale`'s handling of a None result.
    """
    store = _isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    monkeypatch.setattr(registry, "epic_from_plan_anchor", lambda *, repo, topic: None)
    repo, topic = make_plan(tmp_path=tmp_path, topic="stale-epic")
    track = registry.Track(topic=topic, repo=str(repo), tmux=topic, epic=None)
    registry.append_mapping(track=track, store_path=None)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())

    healed = _supervisor_restart.rederive_epic_if_stale(sup=sup, track=track, act=True)

    assert healed.epic == "legacy-unresolved:stale-epic"
    assert healed is track
    stored = registry.read_valid_mapping(store_path=None)
    assert stored[0].epic == "legacy-unresolved:stale-epic"
    assert store.exists()


def test_record_derived_epic_idempotent_when_the_row_already_matches(*, tmp_path, monkeypatch):
    """CONTROL: writing the same epic twice no-ops the second time (mirrors repoint_tmux)."""
    store = _isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo, topic = make_plan(tmp_path=tmp_path, topic="stale-epic")
    track = registry.Track(topic=topic, repo=str(repo), tmux=topic, epic=None)
    registry.append_mapping(track=track, store_path=None)

    assert registry.record_derived_epic(repo=str(repo), topic=topic, epic=TEST_EPIC) is True
    before = store.stat().st_mtime_ns
    assert registry.record_derived_epic(repo=str(repo), topic=topic, epic=TEST_EPIC) is False
    assert store.stat().st_mtime_ns == before
    assert registry.record_derived_epic(repo=str(repo), topic="missing", epic=TEST_EPIC) is False


def test_rederive_never_reads_or_writes_on_a_read_only_tick(*, tmp_path, monkeypatch):
    """CONTROL: act=False (the `list` command's read-only path) never re-derives."""
    _isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo, topic = make_plan(tmp_path=tmp_path, topic="stale-epic")
    track = registry.Track(topic=topic, repo=str(repo), tmux=topic, epic=None)
    registry.append_mapping(track=track, store_path=None)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())

    healed = _supervisor_restart.rederive_epic_if_stale(sup=sup, track=track, act=False)

    assert healed is track
    stored = registry.read_valid_mapping(store_path=None)
    assert stored[0].epic == "legacy-unresolved:stale-epic"
