"""Tests for registry.py — the Track dataclass and the mapping-store API.

Split from a single `test_registry.py` that carried the whole module and crossed
the 250-LLOC hard ceiling. The seams are the section banners the file already
documented, so no test changed meaning in the move. This module owns the `Track`
dataclass and the mapping store's happy-path append / read / remove / rewrite;
`test_registry_resilience.py` owns the fail-soft guarantees over a corrupt,
unreadable, or unwritable store, `test_registry_discovery.py` owns discovery,
the discovery-mapping join, and the watch set, and
`test_registry_injection.py` owns the injection-stamp sidecar.

``import registry`` resolves via conftest.py.
"""

import dataclasses
import json

import pytest
import registry
from registry import Track

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Every test runs with cwd inside tmp_path (repo convention)."""
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Track dataclass.
# --------------------------------------------------------------------------- #


def test_track_is_frozen_and_keyword_only():
    track = Track(topic="t", repo="/r")
    with pytest.raises(dataclasses.FrozenInstanceError):
        track.topic = "other"  # type: ignore[misc]
    with pytest.raises(TypeError):
        Track("t", "/r")  # type: ignore[call-arg]  # positional is rejected


def test_make_unassigned():
    track = Track.make_unassigned(repo="/r", topic="x", handoff="/r/plan/x/handoff.md")
    assert track.is_unassigned is True
    assert track.assigned is False
    assert track.tmux is None
    assert track.handoff == "/r/plan/x/handoff.md"


def test_tmux_id_is_the_bare_topic_by_default():
    # Default (no known collision): a session is named after the bare plan topic —
    # NOT repo-qualified (maintainer-declared 2026-07-19). repo_slug still returns the
    # basename (it is used for DISPLAY and for the collision prefix below).
    assert registry.repo_slug("/data/projects/livespec") == "livespec"
    assert registry.tmux_id("/data/projects/livespec", "collector") == "collector"
    # A topic that itself contains dashes stays bare (a dash is never sanitized).
    assert registry.tmux_id("/data/projects/livespec", "autonomous-mode") == "autonomous-mode"


def test_tmux_id_single_dash_repo_prefix_only_on_collision():
    # When the topic collides across repos, and ONLY then, it is repo-qualified as
    # `<slug>-<topic>` with a SINGLE dash (not the retired double-dash).
    assert (
        registry.tmux_id("/data/projects/livespec", "collector", {"collector"})
        == "livespec-collector"
    )
    # A collision set that does NOT contain this topic leaves it bare.
    assert registry.tmux_id("/data/projects/livespec", "collector", {"other"}) == "collector"


def test_colliding_topics_are_topics_in_two_or_more_repos():
    discovered = [
        ("/data/projects/livespec", "shared", "h1"),
        ("/data/projects/livespec-console-beads-fabro", "shared", "h2"),
        ("/data/projects/livespec", "solo", "h3"),
    ]
    assert registry.colliding_topics(discovered) == frozenset({"shared"})


def test_colliding_topics_ignores_the_same_repo_seen_twice():
    # Two triples for the SAME (normalized) repo + topic is NOT a cross-repo collision.
    discovered = [
        ("/data/projects/livespec", "dup", "h1"),
        ("/data/projects/livespec/", "dup", "h2"),
    ]
    assert registry.colliding_topics(discovered) == frozenset()


# --------------------------------------------------------------------------- #
# Mapping store: append / read / remove / rewrite.
# --------------------------------------------------------------------------- #


def test_append_read_roundtrip(tmp_path):
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        Track(
            topic="alpha",
            repo="/data/projects/livespec",
            tmux="livespec:alpha",
            handoff="/data/projects/livespec/plan/alpha/handoff.md",
            resume="read handoff and follow it",
            epic="livespec-0001",
            ctx_threshold=40,
            pinned_session_id="sess-1",
        ),
        store,
    )
    registry.append_mapping(
        Track(topic="beta", repo="/data/projects/other", tmux="other:beta"),
        store,
    )

    tracks = registry.read_mapping(store)
    assert [t.topic for t in tracks] == ["alpha", "beta"]
    alpha = tracks[0]
    assert alpha.tmux == "livespec:alpha"
    assert alpha.ctx_threshold == 40
    assert alpha.epic == "livespec-0001"
    assert alpha.pinned_session_id == "sess-1"
    assert alpha.assigned is True
    # A row without an explicit threshold has NO per-track override → None (so the
    # daemon-wide default applies at evaluate time), NOT DEFAULT_CTX_THRESHOLD.
    assert tracks[1].ctx_threshold is None


def test_ctx_threshold_none_is_omitted_explicit_int_roundtrips(tmp_path):
    """A track with no override (ctx_threshold=None) serializes a row WITHOUT the
    key and reads back None; an explicit int serializes the key and round-trips."""
    store = tmp_path / "map.jsonl"
    registry.append_mapping(Track(topic="nooverride", repo="/r", tmux="r--nooverride"), store)
    registry.append_mapping(
        Track(topic="pinned", repo="/r", tmux="r--pinned", ctx_threshold=60), store
    )

    rows = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
    assert "ctx_threshold" not in rows[0]  # None → key omitted
    assert rows[1]["ctx_threshold"] == 60  # explicit int → key present

    tracks = registry.read_mapping(store)
    by_topic = {t.topic: t for t in tracks}
    assert by_topic["nooverride"].ctx_threshold is None
    assert by_topic["pinned"].ctx_threshold == 60


def test_read_mapping_fail_soft_on_malformed_lines(tmp_path):
    store = tmp_path / "map.jsonl"
    good_a = json.dumps({"topic": "a", "repo": "/r"})
    good_b = json.dumps({"topic": "b", "repo": "/r"})
    store.write_text(
        good_a
        + "\n"
        + "{ this is not json\n"  # malformed → skipped
        + "\n"  # blank → skipped silently
        + "[1, 2, 3]\n"  # non-object → skipped
        + json.dumps({"repo": "/r"})  # missing topic → skipped
        + "\n"
        + good_b
        + "\n",
        encoding="utf-8",
    )
    tracks = registry.read_mapping(store)
    assert [t.topic for t in tracks] == ["a", "b"]


def test_remove_mapping_is_repo_qualified(tmp_path):
    """Same topic in two repos: removing one must not remove the other."""
    store = tmp_path / "map.jsonl"
    registry.append_mapping(Track(topic="shared", repo="/data/projects/livespec"), store)
    registry.append_mapping(Track(topic="shared", repo="/data/projects/other"), store)
    registry.append_mapping(Track(topic="solo", repo="/data/projects/livespec"), store)

    removed = registry.remove_mapping("/data/projects/livespec", "shared", store)
    assert removed == 1

    remaining = registry.read_mapping(store)
    keys = {(t.repo, t.topic) for t in remaining}
    assert keys == {("/data/projects/other", "shared"), ("/data/projects/livespec", "solo")}


def test_rewrite_mapping_preserves_unknown_keys(tmp_path):
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps({"topic": "a", "repo": "/r", "added_at": "2026-07-12T13:00:00Z"})
        + "\n"
        + json.dumps({"topic": "b", "repo": "/r", "added_at": "2026-07-12T14:00:00Z"})
        + "\n",
        encoding="utf-8",
    )
    dropped = registry.rewrite_mapping(lambda row: row.get("topic") != "a", store)
    assert dropped == 1

    surviving = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
    assert len(surviving) == 1
    assert surviving[0]["topic"] == "b"
    assert surviving[0]["added_at"] == "2026-07-12T14:00:00Z"  # unknown key preserved
