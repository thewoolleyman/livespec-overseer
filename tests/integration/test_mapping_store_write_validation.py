"""Integration tests for mapping-store write validation as a predicate on the WRITE.

SPECIFICATION/contracts.md states the predicate over the row as it stands BEFORE
together with the row as it would stand AFTER, and NOT over the resulting row
alone. These tests drive that through the ordinary operator and daemon store
surfaces — upsert, epic re-derive, re-point, remove — rather than through the
predicate directly, because the refusal is user-observable behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import _registry_rows_io
import registry

__all__: list[str] = []

REPO = "/repo"


def plan_row(*, topic: str, epic: str | None = None, tmux: str | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "kind": "plan",
        "topic": topic,
        "repo": REPO,
        "tmux": tmux if tmux is not None else topic,
    }
    if epic is not None:
        row["epic"] = epic
    return row


def seed(*, store: Path, rows: list[dict[str, object]]) -> None:
    store.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def stored_rows(*, store: Path) -> list[dict[str, object]]:
    text = store.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def topics(*, store: Path) -> list[object]:
    return [row.get("topic") for row in stored_rows(store=store)]


def test_a_write_that_strips_a_recorded_epic_is_refused_though_the_resulting_row_conforms(
    *, tmp_path, capsys
):
    """The discriminating control for the write predicate.

    A stripped row satisfies the durable-key contract exactly as a never-assigned
    row does, so this can pass ONLY under a predicate evaluated over the write; an
    implementation validating the resulting row alone accepts it.
    """
    store = tmp_path / "map.jsonl"
    seed(store=store, rows=[plan_row(topic="alpha", epic="overseer-recorded")])
    before = store.read_bytes()

    stripped = registry.upsert_mapping(
        track=registry.Track(topic="alpha", repo=REPO, tmux="alpha"),
        store_path=store,
        update_fields=frozenset({"epic"}),
    )

    assert stripped is False
    assert store.read_bytes() == before
    assert "epic" in capsys.readouterr().err

    # The identical resulting row is ACCEPTED when it INTRODUCES a track, so the
    # refusal is a property of the transition and never of the row taken alone.
    introduced = registry.upsert_mapping(
        track=registry.Track(topic="alpha", repo="/other-repo", tmux="alpha"),
        store_path=store,
        update_fields=frozenset({"epic"}),
    )

    assert introduced is True
    assert topics(store=store) == ["alpha", "alpha"]


def test_a_write_that_replaces_a_recorded_epic_is_refused_independently_of_malformedness(
    *, tmp_path, capsys
):
    store = tmp_path / "map.jsonl"
    seed(
        store=store,
        rows=[plan_row(topic="alpha", epic="overseer-recorded"), plan_row(topic="beta")],
    )
    before = store.read_bytes()

    replaced = registry.record_derived_epic(
        repo=REPO, topic="alpha", epic="overseer-different", store_path=store
    )

    assert replaced is False
    assert store.read_bytes() == before
    assert "epic" in capsys.readouterr().err

    # The refusal does not depend on the replacement value: recording that SAME
    # well-formed id on a row carrying no recorded epic is accepted.
    recorded = registry.record_derived_epic(
        repo=REPO, topic="beta", epic="overseer-different", store_path=store
    )

    assert recorded is True
    assert stored_rows(store=store)[1]["epic"] == "overseer-different"
    assert stored_rows(store=store)[0]["epic"] == "overseer-recorded"


def test_a_row_with_no_recorded_epic_is_accepted_at_introduction(*, tmp_path):
    """An ABSENT epic CONFORMS; the REQUIRED-for-restart sentence gates RESTART."""
    store = tmp_path / "map.jsonl"

    assert not store.exists()
    assert (
        registry.upsert_mapping(
            track=registry.Track(topic="alpha", repo=REPO, tmux="alpha"), store_path=store
        )
        is True
    )
    assert topics(store=store) == ["alpha"]

    # And the chokepoint accepts a row carrying no `epic` key at all.
    assert _registry_rows_io.write_rows(rows=[plan_row(topic="beta")], store_path=store) is True
    assert stored_rows(store=store) == [plan_row(topic="beta")]


def test_a_pre_existing_non_conforming_row_does_not_block_an_unrelated_store_rewrite(
    *, tmp_path, capsys
):
    store = tmp_path / "map.jsonl"
    seed(
        store=store,
        rows=[
            plan_row(topic="legacy", epic="plan/legacy/handoff.md"),
            plan_row(topic="alpha", epic="overseer-alpha"),
            plan_row(topic="beta", epic="overseer-beta"),
        ],
    )

    dropped = registry.remove_mapping(repo=REPO, topic="beta", store_path=store)

    assert dropped == 1
    assert topics(store=store) == ["legacy", "alpha"]
    # Surfaced rather than silently rewritten or silently dropped.
    assert stored_rows(store=store)[0]["epic"] == "plan/legacy/handoff.md"
    err = capsys.readouterr().err
    assert "legacy" in err
    assert "epic" in err


def test_removing_a_row_entirely_is_not_refused_as_removing_its_epic(*, tmp_path):
    """Whole-row removal is not epic removal, so archived-plan GC is unaffected."""
    store = tmp_path / "map.jsonl"
    seed(
        store=store,
        rows=[
            plan_row(topic="alpha", epic="overseer-alpha"),
            plan_row(topic="beta", epic="overseer-beta"),
        ],
    )

    dropped = registry.remove_mapping(repo=REPO, topic="alpha", store_path=store)

    assert dropped == 1
    assert topics(store=store) == ["beta"]


def test_recording_an_epic_that_is_not_a_ledger_epic_id_is_refused_naming_the_key(
    *, tmp_path, capsys
):
    store = tmp_path / "map.jsonl"
    seed(store=store, rows=[plan_row(topic="alpha")])
    before = store.read_bytes()

    recorded = registry.record_derived_epic(
        repo=REPO, topic="alpha", epic="plan/alpha/handoff.md", store_path=store
    )

    assert recorded is False
    assert store.read_bytes() == before
    assert "epic" in capsys.readouterr().err


def test_a_repoint_of_a_row_whose_epic_already_fails_the_contract_completes(*, tmp_path):
    """A write is never refused for a non-conformance it did not introduce."""
    store = tmp_path / "map.jsonl"
    seed(
        store=store,
        rows=[plan_row(topic="legacy", tmux="old", epic="plan/legacy/handoff.md")],
    )

    assert (
        registry.repoint_tmux(repo=REPO, topic="legacy", new_tmux="new", store_path=store) is True
    )

    row = stored_rows(store=store)[0]
    assert row["tmux"] == "new"
    assert row["epic"] == "plan/legacy/handoff.md"


def test_a_write_introducing_a_structurally_invalid_row_is_refused_naming_its_key(
    *, tmp_path, capsys
):
    store = tmp_path / "map.jsonl"
    kept = plan_row(topic="alpha", epic="overseer-alpha")
    seed(store=store, rows=[kept])
    before = store.read_bytes()

    unknown_kind = _registry_rows_io.write_rows(
        rows=[kept, {"kind": "bogus", "topic": "x", "repo": REPO, "tmux": "x"}],
        store_path=store,
    )

    assert unknown_kind is False
    assert "kind" in capsys.readouterr().err

    topicless = _registry_rows_io.write_rows(
        rows=[kept, {"kind": "plan", "repo": REPO, "tmux": "y"}, {"kind": "plan", "repo": REPO}],
        store_path=store,
    )

    assert topicless is False
    assert "topic" in capsys.readouterr().err
    assert store.read_bytes() == before


def test_malformed_store_lines_are_not_read_as_rows_by_the_write_predicate(*, tmp_path):
    """The read-side and write-side rules govern different failures.

    An unparseable line is not a row, so it is neither a pre-image for a write nor
    a row the write can be said to remove.
    """
    store = tmp_path / "map.jsonl"
    store.write_text(
        "not json\n[1, 2]\n\n" + json.dumps(plan_row(topic="alpha", epic="overseer-alpha")) + "\n",
        encoding="utf-8",
    )

    assert (
        registry.upsert_mapping(
            track=registry.Track(topic="beta", repo=REPO, tmux="beta"), store_path=store
        )
        is True
    )
    assert topics(store=store) == ["alpha", "beta"]
