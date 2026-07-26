"""Tests for registry.py — the injection-stamp sidecar.

Split out of `test_registry.py` at the section banners it already carried, when
that module crossed the 250-LLOC hard ceiling. This module owns the sidecar
round-trip (repo-qualified stamps, notified bands, resume-pending) together with
its fail-soft behavior over a corrupt, legacy, or half-shaped value — the two
sections stay together because both are the same module surface.

``import registry`` resolves via conftest.py.
"""

import json

import pytest
import registry


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Every test runs with cwd inside tmp_path (repo convention)."""
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Injection-stamp sidecar.
# --------------------------------------------------------------------------- #


def test_injection_stamp_roundtrip_is_repo_qualified(tmp_path):
    stamp = tmp_path / "stamps.json"
    repo_a = "/data/projects/livespec"
    repo_b = "/data/projects/other"
    assert registry.read_injection_stamp(repo_a, "t", stamp) is None

    registry.write_injection_stamp(repo_a, "t", 123.5, stamp)
    assert registry.read_injection_stamp(repo_a, "t", stamp) == 123.5
    # Same topic, different repo → independent (no cross-link).
    assert registry.read_injection_stamp(repo_b, "t", stamp) is None

    registry.write_injection_stamp(repo_a, "t", 200.0, stamp)  # overwrite
    assert registry.read_injection_stamp(repo_a, "t", stamp) == 200.0


def test_injection_stamp_fail_soft_on_garbage(tmp_path):
    stamp = tmp_path / "stamps.json"
    stamp.write_text("not json at all", encoding="utf-8")
    assert registry.read_injection_stamp("/r", "t", stamp) is None


def test_archived_or_gone_active_wins_over_same_named_archive(tmp_path):
    # B6: an ACTIVE plan whose topic ALSO exists under plan/archive/ must NOT be
    # reported archived (else its mapping is GC-dropped every tick).
    repo = tmp_path / "repo"
    (repo / "plan" / "collector").mkdir(parents=True)
    (repo / "plan" / "archive" / "collector").mkdir(parents=True)
    assert registry.archived_or_gone(str(repo), "collector") is False
    # truly archived (no active dir) → True
    (repo / "plan" / "old").mkdir()  # keep plan/ around
    (repo / "plan" / "archive" / "gone").mkdir(parents=True)
    assert registry.archived_or_gone(str(repo), "gone") is True
    # plan dir simply missing under an existing repo → gone
    assert registry.archived_or_gone(str(repo), "never-existed") is True


def test_repo_root_present(tmp_path):
    assert registry.repo_root_present(str(tmp_path)) is True
    assert registry.repo_root_present(str(tmp_path / "nope")) is False


def test_repo_root_present_is_false_when_the_root_cannot_be_stated(tmp_path, monkeypatch):
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

    monkeypatch.setattr(registry.Path, "is_dir", _deny)
    assert registry.repo_root_present(str(parent / "repo")) is False


def test_clear_injection_stamp(tmp_path):
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp("/r", "t", 123.5, stamp)
    assert registry.read_injection_stamp("/r", "t", stamp) == 123.5
    registry.clear_injection_stamp("/r", "t", stamp)
    assert registry.read_injection_stamp("/r", "t", stamp) is None
    # clearing an absent stamp is a no-op (no crash)
    registry.clear_injection_stamp("/r", "t", stamp)


def test_injection_stamp_dict_shape_bands_roundtrip(tmp_path):
    """Part 2: the sidecar value is {"at": <float>, "bands": [...]}. write opens a
    fresh round (at set, bands reset); add_notified_band appends idempotently and
    preserves at; a re-write resets the bands for the new round."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp("/r", "t", 500.0, stamp)
    assert registry.read_injection_stamp("/r", "t", stamp) == 500.0
    assert registry.read_notified_bands("/r", "t", stamp) == []  # fresh round: no bands

    registry.add_notified_band("/r", "t", 45, stamp)
    registry.add_notified_band("/r", "t", 40, stamp)
    registry.add_notified_band("/r", "t", 45, stamp)  # duplicate → idempotent no-op
    assert registry.read_notified_bands("/r", "t", stamp) == [45, 40]
    assert registry.read_injection_stamp("/r", "t", stamp) == 500.0  # `at` preserved

    registry.write_injection_stamp("/r", "t", 600.0, stamp)  # a NEW round resets bands
    assert registry.read_notified_bands("/r", "t", stamp) == []
    assert registry.read_injection_stamp("/r", "t", stamp) == 600.0


def test_clear_injection_stamp_resets_at_and_bands(tmp_path):
    """Part 2: clear deletes the key entirely → both `at` and `bands` reset."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp("/r", "t", 500.0, stamp)
    registry.add_notified_band("/r", "t", 45, stamp)
    registry.clear_injection_stamp("/r", "t", stamp)
    assert registry.read_injection_stamp("/r", "t", stamp) is None
    assert registry.read_notified_bands("/r", "t", stamp) == []


def test_injection_stamp_legacy_bare_float_backcompat(tmp_path):
    """Part 2 back-compat: a pre-escalation sidecar stores a BARE float per key.
    read_injection_stamp still returns it, read_notified_bands is empty, and
    add_notified_band UPGRADES the value to the dict shape preserving the float
    as `at`."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(json.dumps({"/r\tt": 321.0}), encoding="utf-8")  # legacy bare-float value
    assert registry.read_injection_stamp("/r", "t", stamp) == 321.0
    assert registry.read_notified_bands("/r", "t", stamp) == []
    registry.add_notified_band("/r", "t", 45, stamp)
    assert registry.read_injection_stamp("/r", "t", stamp) == 321.0  # `at` preserved on upgrade
    assert registry.read_notified_bands("/r", "t", stamp) == [45]


def test_write_rows_is_atomic_and_skips_when_unchanged(tmp_path):
    # B6: rewrite_mapping skips the write entirely when no row is dropped.
    store = tmp_path / "map.jsonl"
    registry.append_mapping(registry.Track(topic="a", repo="/r", tmux="r--a"), store)
    before = store.stat().st_mtime_ns
    dropped = registry.rewrite_mapping(lambda _row: True, store)  # keep all
    assert dropped == 0
    assert store.stat().st_mtime_ns == before  # unchanged → not rewritten


def test_resume_pending_roundtrip_and_preserves_at_and_bands(tmp_path):
    """R1: set_resume_pending marks the flag on the round dict WITHOUT disturbing `at`
    (so the ready marker still certifies — mtime > at) or the notified bands."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp("/r", "t", 500.0, stamp)
    registry.add_notified_band("/r", "t", 40, stamp)
    assert registry.read_resume_pending("/r", "t", stamp) is False  # not set yet

    registry.set_resume_pending("/r", "t", stamp)
    assert registry.read_resume_pending("/r", "t", stamp) is True
    assert registry.read_injection_stamp("/r", "t", stamp) == 500.0  # `at` preserved
    assert registry.read_notified_bands("/r", "t", stamp) == [40]  # bands preserved


def test_resume_pending_is_cleared_by_round_close_and_by_a_fresh_round(tmp_path):
    """R1: the pending flag is round-scoped — clear_injection_stamp (restart closed) and
    write_injection_stamp (a fresh round) both drop it, so it can never outlive its round."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp("/r", "t", 500.0, stamp)
    registry.set_resume_pending("/r", "t", stamp)
    registry.clear_injection_stamp("/r", "t", stamp)
    assert registry.read_resume_pending("/r", "t", stamp) is False  # round closed → flag gone

    registry.write_injection_stamp("/r", "t", 600.0, stamp)
    registry.set_resume_pending("/r", "t", stamp)
    registry.write_injection_stamp("/r", "t", 700.0, stamp)  # a NEW round overwrites the dict
    assert registry.read_resume_pending("/r", "t", stamp) is False


def test_repoint_tmux_rewrites_only_the_matching_row_and_is_idempotent(tmp_path):
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
    assert registry.repoint_tmux("/r", "a", "new", store) is True
    rows = {r.topic: r.tmux for r in registry.read_mapping(store)}
    assert rows == {"a": "new", "b": "b-tmux"}  # only `a` moved
    raw_a = next(
        json.loads(ln) for ln in store.read_text().splitlines() if json.loads(ln)["topic"] == "a"
    )
    assert raw_a["added_at"] == "keep"  # unknown key survives the rewrite

    before = store.stat().st_mtime_ns
    assert registry.repoint_tmux("/r", "a", "new", store) is False  # already correct → no-op
    assert store.stat().st_mtime_ns == before  # not rewritten
    assert registry.repoint_tmux("/r", "missing", "x", store) is False  # no such row → no-op


# --------------------------------------------------------------------------- #
# Injection-stamp sidecar: fail-soft over a corrupt / legacy / half-shaped value.
# --------------------------------------------------------------------------- #


def test_injection_stamp_fail_soft_when_the_sidecar_is_not_a_json_object(tmp_path, capsys):
    """Well-formed JSON of the WRONG shape (a bare array) is reported distinctly
    from malformed JSON, and every reader degrades to its empty answer."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(json.dumps([1, 2]), encoding="utf-8")

    assert registry.read_injection_stamp("/r", "t", stamp) is None
    assert registry.read_notified_bands("/r", "t", stamp) == []
    assert registry.read_resume_pending("/r", "t", stamp) is False
    assert "is not a JSON object" in capsys.readouterr().err


def test_read_injection_stamp_is_none_when_the_round_dict_has_no_at(tmp_path):
    """A dict-shaped value that never opened a round (no ``at``) has no timestamp —
    but the rest of the entry is still readable, so it is not discarded wholesale."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(
        json.dumps({"/r\tt": {"bands": [45], "resume_pending": True}}), encoding="utf-8"
    )
    assert registry.read_injection_stamp("/r", "t", stamp) is None
    assert registry.read_notified_bands("/r", "t", stamp) == [45]
    assert registry.read_resume_pending("/r", "t", stamp) is True


def test_read_injection_stamp_warns_and_returns_none_on_a_non_numeric_stamp(tmp_path, capsys):
    """Both sidecar shapes name the offending track on an unusable ``at``. ``true``
    is deliberately NOT numeric (jsonio.as_float rejects bool, which is an int
    subclass), so it must not silently read back as 1.0."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(
        json.dumps({"/r\tdict": {"at": True}, "/r\tlegacy": "not-a-number"}), encoding="utf-8"
    )
    assert registry.read_injection_stamp("/r", "dict", stamp) is None
    assert registry.read_injection_stamp("/r", "legacy", stamp) is None

    err = capsys.readouterr().err
    assert "non-numeric injection stamp for /r::dict" in err
    assert "non-numeric injection stamp for /r::legacy" in err


def test_read_notified_bands_ignores_a_non_list_bands_member(tmp_path):
    """A ``bands`` member of the wrong type reads as "nothing notified yet" without
    costing the entry its still-usable ``at``."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(json.dumps({"/r\tt": {"at": 500.0, "bands": "45"}}), encoding="utf-8")
    assert registry.read_notified_bands("/r", "t", stamp) == []
    assert registry.read_injection_stamp("/r", "t", stamp) == 500.0


def test_add_notified_band_on_a_track_with_no_open_round(tmp_path):
    """Part 2: an absent key yields a bare bands-only entry — the band is recorded
    without inventing an ``at`` (no round was opened, so none may certify)."""
    stamp = tmp_path / "stamps.json"
    registry.add_notified_band("/r", "t", 45, stamp)
    assert registry.read_notified_bands("/r", "t", stamp) == [45]
    assert registry.read_injection_stamp("/r", "t", stamp) is None


def test_set_resume_pending_on_a_track_with_no_open_round(tmp_path):
    """R1: the retry keys on the FLAG, not on ``at`` — an absent key is written as a
    bare {"resume_pending": true} so the submit still retries."""
    stamp = tmp_path / "stamps.json"
    registry.set_resume_pending("/r", "t", stamp)
    assert registry.read_resume_pending("/r", "t", stamp) is True
    assert registry.read_injection_stamp("/r", "t", stamp) is None


def test_set_resume_pending_upgrades_a_legacy_bare_scalar_value(tmp_path):
    """R1 back-compat: a legacy bare-float value is upgraded to the dict shape with
    the float preserved as ``at``; a legacy bare NON-numeric value is unusable, so
    the upgrade keeps only the flag."""
    stamp = tmp_path / "stamps.json"
    stamp.write_text(
        json.dumps({"/r\tnumeric": 321.0, "/r\tjunk": "not-a-number"}), encoding="utf-8"
    )
    registry.set_resume_pending("/r", "numeric", stamp)
    registry.set_resume_pending("/r", "junk", stamp)

    assert registry.read_resume_pending("/r", "numeric", stamp) is True
    assert registry.read_injection_stamp("/r", "numeric", stamp) == 321.0  # `at` preserved
    assert registry.read_resume_pending("/r", "junk", stamp) is True
    assert registry.read_injection_stamp("/r", "junk", stamp) is None  # unusable → dropped
