"""Integration tests: the read-time epic placeholder is never written back.

SPECIFICATION/contracts.md, Durable stores: where a reader substitutes an in-memory
placeholder for an ABSENT `epic` so downstream code has a value to carry, that
placeholder is a READ-TIME PROJECTION and MUST NOT be written back into the store —
absent and recorded are the only two persisted states, and the projection MUST NOT
become a third. A row already carrying such a persisted placeholder MUST be treated
exactly as a row with NO recorded `epic`, including by the restart interlock.

These tests drive the ordinary operator and daemon surfaces — link, upsert, identity
update, the store chokepoint, the null-epic audit, and a `ready` declaration reaching
the restart interlock — rather than the projection helpers directly, because every
clause above is user-observable behaviour.

The motivating case was measured live and is what makes the audit clause load-bearing:
the store held one row whose `epic` was a persisted placeholder, and an audit keyed on
ABSENCE reported the store clean while that unresolvable row sat in it.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
from pathlib import Path

import _registry_rows_io

from overseer import registry, signals
from overseer.test_supervisor_builders import (
    FakeTmux,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
)

__all__: list[str] = []

REPO = "/repo"
PLACEHOLDER_PREFIX = "legacy-unresolved:"


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


def test_a_read_project_write_round_trip_leaves_the_epic_absent_in_the_stored_row(*, tmp_path):
    """Given a row with no recorded epic, when a later write rewrites it, it stays absent.

    The reader really does project — asserted here rather than assumed, because a
    round trip that never produced a placeholder would pass vacuously.
    """
    store = tmp_path / "map.jsonl"
    seed(store=store, rows=[plan_row(topic="alpha")])

    [projected] = registry.read_valid_mapping(store_path=store)

    assert projected.epic == registry.unresolved_plan_epic(topic="alpha")

    # The link surface appends the PROJECTED track as a new row, which is the write the
    # daemon performs when it binds a live session to a discovered plan.
    registry.append_mapping(track=projected, store_path=store, added_at="2026-08-26T00:00:00Z")

    assert [row.get("epic") for row in stored_rows(store=store)] == [None, None]

    # And an upsert ASKED to write `epic` back carries the same projected value; it
    # collapses the duplicate identity, so one row survives and it still records none.
    assert (
        registry.upsert_mapping(
            track=projected,
            store_path=store,
            update_fields=frozenset({"epic", "tmux"}),
        )
        is True
    )

    assert [row.get("epic") for row in stored_rows(store=store)] == [None]
    assert PLACEHOLDER_PREFIX not in store.read_text(encoding="utf-8")


def test_an_already_persisted_projection_is_treated_as_a_row_with_no_recorded_epic(*, tmp_path):
    """The placeholder is not a third persisted state, so a rewrite retires it.

    The unrelated identity update is what makes this the CHANGED-row case: the write
    is not about the epic at all, and the row still comes out recording none.
    """
    store = tmp_path / "map.jsonl"
    seed(
        store=store,
        rows=[
            plan_row(topic="alpha", epic=registry.unresolved_plan_epic(topic="alpha")),
            plan_row(topic="beta", epic="overseer-beta"),
        ],
    )

    assert registry.record_observed_session_identity(
        repo=REPO, topic="alpha", session_identity="claude:alpha", store_path=store
    )

    rows = stored_rows(store=store)

    assert rows[0]["observed_session_identity"] == "claude:alpha"
    assert rows[0]["epic"] is None
    assert PLACEHOLDER_PREFIX not in store.read_text(encoding="utf-8")
    # A genuinely recorded epic on a row the write merely carries along is untouched.
    assert rows[1]["epic"] == "overseer-beta"


def test_a_write_introducing_a_persisted_projection_is_refused_at_the_store_chokepoint(
    *, tmp_path, capsys
):
    """The raw chokepoint refuses what track serialization can no longer produce.

    Not every store write serializes a Track, so the prohibition is also a predicate
    on the write itself. The control is the same row with its `epic` simply absent:
    an absent epic CONFORMS, so accepting it is what shows the refusal turns on the
    placeholder rather than on the row being epic-less.
    """
    store = tmp_path / "map.jsonl"
    seed(store=store, rows=[plan_row(topic="alpha", epic="overseer-alpha")])
    before = store.read_bytes()

    refused = _registry_rows_io.write_rows(
        rows=[
            plan_row(topic="alpha", epic="overseer-alpha"),
            plan_row(topic="beta", epic=registry.unresolved_plan_epic(topic="beta")),
        ],
        store_path=store,
    )

    assert refused is False
    assert store.read_bytes() == before
    err = capsys.readouterr().err
    assert "epic" in err
    assert "beta" in err

    accepted = _registry_rows_io.write_rows(
        rows=[plan_row(topic="alpha", epic="overseer-alpha"), plan_row(topic="beta")],
        store_path=store,
    )

    assert accepted is True
    assert [row.get("epic") for row in stored_rows(store=store)] == ["overseer-alpha", None]


def test_the_null_epic_audit_reports_a_persisted_projection_rather_than_skipping_it(*, tmp_path):
    """The audit keyed on ABSENCE alone reported a store holding this row as clean."""
    store = tmp_path / "map.jsonl"
    documented = plan_row(topic="documented")
    documented["epic"] = None
    documented["epic_null_audit"] = "deliberately unassigned pending the scope event"
    undocumented = plan_row(topic="undocumented")
    undocumented["epic"] = None
    seed(
        store=store,
        rows=[
            documented,
            undocumented,
            plan_row(topic="stale", epic=registry.unresolved_plan_epic(topic="stale")),
            plan_row(topic="recorded", epic="overseer-recorded"),
        ],
    )

    audited = registry.audit_null_epics(store_path=store)

    assert [(row.topic, row.status) for row in audited] == [
        ("documented", "documented-null"),
        ("undocumented", "undocumented-null"),
        ("stale", "persisted-projection"),
    ]


def _warned_round(*, tmp_path, epic: str | None):
    """Open a real wrap-up round on a track read back OUT OF THE STORE.

    Reading the track back is the whole point: the interlock must judge the row as it
    is PERSISTED, so a hand-built in-memory track would beg the question.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    store = Path(sup.store_path)
    row = {"kind": "plan", "topic": topic, "repo": str(repo), "tmux": session}
    if epic is not None:
        row["epic"] = epic
    seed(store=store, rows=[row])
    [track] = registry.read_valid_mapping(store_path=store)
    opened = sup.evaluate(track=track, act=True)

    assert opened.status == "warned"

    return repo, topic, fake, sup, store, track


def test_a_ready_declaration_on_a_persisted_projection_row_is_surfaced_not_respawned(*, tmp_path):
    """The restart interlock reads the persisted placeholder as NO recorded epic.

    So the declaration is not spent: the track is surfaced, the `ready` file survives,
    and nothing is respawned — exactly what a row with an absent epic gets.
    """
    repo, topic, fake, sup, _store, track = _warned_round(
        tmp_path=tmp_path, epic=registry.unresolved_plan_epic(topic="topic")
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    sup.epic_lookup = lambda *, repo, topic: None

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "blocked:human"
    assert "no plan epic" in err.getvalue()
    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY


def test_the_interlock_records_a_derived_epic_over_a_persisted_projection(*, tmp_path):
    """The discriminating control for "treated exactly as a row with no recorded epic".

    The write predicate refuses REPLACING a recorded epic. So this passes only while
    the persisted placeholder counts as no recorded epic at all: read it as recorded
    and the one-shot re-derive is refused, the row stays unresolvable forever, and the
    track can never be restarted again.
    """
    repo, topic, fake, sup, store, track = _warned_round(
        tmp_path=tmp_path, epic=registry.unresolved_plan_epic(topic="topic")
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    sup.epic_lookup = lambda *, repo, topic: "overseer-derived"

    view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert fake.has(method="respawn")
    assert stored_rows(store=store)[0]["epic"] == "overseer-derived"
