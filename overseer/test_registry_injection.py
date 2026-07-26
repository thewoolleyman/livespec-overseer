"""Tests for registry.py — the injection-stamp sidecar.

Split out of `test_registry.py` at the section banners it already carried, when
that module crossed the 250-LLOC hard ceiling. This module owns the sidecar
round-trip: repo-qualified stamps, notified bands, resume-pending, atomic row
writes, and the tmux re-point.

The fail-soft behaviour over a corrupt, legacy, or half-shaped value used to live
here too, on the ground that both sections cover the same module surface. It now
sits in `test_registry_injection_failsoft.py`: the keyword-only conversion
(`overseer-bg2.9`) re-wrapped enough call sites to take the combined module past
the 200-LLOC soft ceiling, and the split runs along the banner already drawn
between them.

``import registry`` resolves via conftest.py.
"""

import json
from pathlib import Path

import pytest
import registry

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    """Every test runs with cwd inside tmp_path (repo convention)."""
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Injection-stamp sidecar.
# --------------------------------------------------------------------------- #


def test_injection_stamp_roundtrip_is_repo_qualified(*, tmp_path):
    stamp = tmp_path / "stamps.json"
    repo_a = "/data/projects/livespec"
    repo_b = "/data/projects/other"
    assert registry.read_injection_stamp(repo=repo_a, topic="t", stamp_path=stamp) is None

    registry.write_injection_stamp(repo=repo_a, topic="t", ts=123.5, stamp_path=stamp)
    assert registry.read_injection_stamp(repo=repo_a, topic="t", stamp_path=stamp) == 123.5
    # Same topic, different repo → independent (no cross-link).
    assert registry.read_injection_stamp(repo=repo_b, topic="t", stamp_path=stamp) is None

    registry.write_injection_stamp(repo=repo_a, topic="t", ts=200.0, stamp_path=stamp)  # overwrite
    assert registry.read_injection_stamp(repo=repo_a, topic="t", stamp_path=stamp) == 200.0


def test_injection_stamp_fail_soft_on_garbage(*, tmp_path):
    stamp = tmp_path / "stamps.json"
    stamp.write_text("not json at all", encoding="utf-8")
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) is None


def test_archived_or_gone_active_wins_over_same_named_archive(*, tmp_path):
    # B6: an ACTIVE plan whose topic ALSO exists under plan/archive/ must NOT be
    # reported archived (else its mapping is GC-dropped every tick).
    repo = tmp_path / "repo"
    (repo / "plan" / "collector").mkdir(parents=True)
    (repo / "plan" / "archive" / "collector").mkdir(parents=True)
    assert registry.archived_or_gone(repo=str(repo), topic="collector") is False
    # truly archived (no active dir) → True
    (repo / "plan" / "old").mkdir()  # keep plan/ around
    (repo / "plan" / "archive" / "gone").mkdir(parents=True)
    assert registry.archived_or_gone(repo=str(repo), topic="gone") is True
    # plan dir simply missing under an existing repo → gone
    assert registry.archived_or_gone(repo=str(repo), topic="never-existed") is True


def test_repo_root_present(*, tmp_path):
    assert registry.repo_root_present(repo=str(tmp_path)) is True
    assert registry.repo_root_present(repo=str(tmp_path / "nope")) is False


def test_repo_root_present_is_false_when_the_root_cannot_be_stated(*, tmp_path, monkeypatch):
    """B6: a root that raises rather than answering (an untraversable parent — the
    unmounted-volume / mid-move case) reads as ABSENT, so the daemon's GC keeps the
    mapping row instead of crashing the tick.

    The raise is injected at ``Path.is_dir`` rather than via ``chmod`` on the parent —
    CI runs as root, where mode bits deny nothing.
    """
    parent = tmp_path / "untraversable"
    (parent / "repo").mkdir(parents=True)

    def _deny(self):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "is_dir", _deny)
    assert registry.repo_root_present(repo=str(parent / "repo")) is False


def test_clear_injection_stamp(*, tmp_path):
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo="/r", topic="t", ts=123.5, stamp_path=stamp)
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 123.5
    registry.clear_injection_stamp(repo="/r", topic="t", stamp_path=stamp)
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) is None
    # clearing an absent stamp is a no-op (no crash)
    registry.clear_injection_stamp(repo="/r", topic="t", stamp_path=stamp)


def test_injection_stamp_dict_shape_bands_roundtrip(*, tmp_path):
    """Part 2: the sidecar value is {"at": <float>, "bands": [...]}. write opens a
    fresh round (at set, bands reset); add_notified_band appends idempotently and
    preserves at; a re-write resets the bands for the new round."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo="/r", topic="t", ts=500.0, stamp_path=stamp)
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 500.0
    assert (
        registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == []
    )  # fresh round: no bands

    registry.add_notified_band(repo="/r", topic="t", band=45, stamp_path=stamp)
    registry.add_notified_band(repo="/r", topic="t", band=40, stamp_path=stamp)
    registry.add_notified_band(
        repo="/r", topic="t", band=45, stamp_path=stamp
    )  # duplicate → idempotent no-op
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == [45, 40]
    assert (
        registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 500.0
    )  # `at` preserved

    registry.write_injection_stamp(
        repo="/r", topic="t", ts=600.0, stamp_path=stamp
    )  # a NEW round resets bands
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == []
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 600.0


def test_clear_injection_stamp_resets_at_and_bands(*, tmp_path):
    """Part 2: clear deletes the key entirely → both `at` and `bands` reset."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo="/r", topic="t", ts=500.0, stamp_path=stamp)
    registry.add_notified_band(repo="/r", topic="t", band=45, stamp_path=stamp)
    registry.clear_injection_stamp(repo="/r", topic="t", stamp_path=stamp)
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) is None
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == []


def test_injection_stamp_legacy_bare_float_backcompat(*, tmp_path):
    """Part 2 back-compat: a pre-escalation sidecar stores a BARE float per key.
    read_injection_stamp still returns it, read_notified_bands is empty, and
    add_notified_band UPGRADES the value to the dict shape preserving the float
    as `at`."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(json.dumps({"/r\tt": 321.0}), encoding="utf-8")  # legacy bare-float value
    assert registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 321.0
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == []
    registry.add_notified_band(repo="/r", topic="t", band=45, stamp_path=stamp)
    assert (
        registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 321.0
    )  # `at` preserved on upgrade
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == [45]


def test_write_rows_is_atomic_and_skips_when_unchanged(*, tmp_path):
    # B6: rewrite_mapping skips the write entirely when no row is dropped.
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        track=registry.Track(topic="a", repo="/r", tmux="r--a"), store_path=store
    )
    before = store.stat().st_mtime_ns
    dropped = registry.rewrite_mapping(keep=lambda *, row: True, store_path=store)  # keep all
    assert dropped == 0
    assert store.stat().st_mtime_ns == before  # unchanged → not rewritten


def test_resume_pending_roundtrip_and_preserves_at_and_bands(*, tmp_path):
    """R1: set_resume_pending marks the flag on the round dict WITHOUT disturbing `at`
    (so the ready marker still certifies — mtime > at) or the notified bands."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo="/r", topic="t", ts=500.0, stamp_path=stamp)
    registry.add_notified_band(repo="/r", topic="t", band=40, stamp_path=stamp)
    assert (
        registry.read_resume_pending(repo="/r", topic="t", stamp_path=stamp) is False
    )  # not set yet

    registry.set_resume_pending(repo="/r", topic="t", stamp_path=stamp)
    assert registry.read_resume_pending(repo="/r", topic="t", stamp_path=stamp) is True
    assert (
        registry.read_injection_stamp(repo="/r", topic="t", stamp_path=stamp) == 500.0
    )  # `at` preserved
    assert registry.read_notified_bands(repo="/r", topic="t", stamp_path=stamp) == [
        40
    ]  # bands preserved


def test_resume_pending_is_cleared_by_round_close_and_by_a_fresh_round(*, tmp_path):
    """R1: the pending flag is round-scoped — clear_injection_stamp (restart closed) and
    write_injection_stamp (a fresh round) both drop it, so it can never outlive its round."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo="/r", topic="t", ts=500.0, stamp_path=stamp)
    registry.set_resume_pending(repo="/r", topic="t", stamp_path=stamp)
    registry.clear_injection_stamp(repo="/r", topic="t", stamp_path=stamp)
    assert (
        registry.read_resume_pending(repo="/r", topic="t", stamp_path=stamp) is False
    )  # round closed → flag gone

    registry.write_injection_stamp(repo="/r", topic="t", ts=600.0, stamp_path=stamp)
    registry.set_resume_pending(repo="/r", topic="t", stamp_path=stamp)
    registry.write_injection_stamp(
        repo="/r", topic="t", ts=700.0, stamp_path=stamp
    )  # a NEW round overwrites the dict
    assert registry.read_resume_pending(repo="/r", topic="t", stamp_path=stamp) is False


def test_repoint_tmux_rewrites_only_the_matching_row_and_is_idempotent(*, tmp_path):
    """R2: repoint_tmux rewrites a (repo, topic) row's tmux field, preserves unknown keys,
    leaves other rows untouched, and no-ops (returns False, no write) when already correct."""
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps({"topic": "a", "repo": "/r", "tmux": "old", "added_at": "keep"})
        + "\n"
        + json.dumps({"topic": "b", "repo": "/r", "tmux": "b-tmux"})
        + "\n",
        encoding="utf-8",
    )
    assert registry.repoint_tmux(repo="/r", topic="a", new_tmux="new", store_path=store) is True
    rows = {r.topic: r.tmux for r in registry.read_mapping(store_path=store)}
    assert rows == {"a": "new", "b": "b-tmux"}  # only `a` moved
    raw_a = next(
        json.loads(ln) for ln in store.read_text().splitlines() if json.loads(ln)["topic"] == "a"
    )
    assert raw_a["added_at"] == "keep"  # unknown key survives the rewrite

    before = store.stat().st_mtime_ns
    assert (
        registry.repoint_tmux(repo="/r", topic="a", new_tmux="new", store_path=store) is False
    )  # already correct → no-op
    assert store.stat().st_mtime_ns == before  # not rewritten
    assert (
        registry.repoint_tmux(repo="/r", topic="missing", new_tmux="x", store_path=store) is False
    )  # no such row → no-op
