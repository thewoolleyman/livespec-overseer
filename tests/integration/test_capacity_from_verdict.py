"""Integration coverage for the capacity clause and for its absence branch.

Pins two ratified scenarios in `SPECIFICATION/scenarios.md`: capacity is stated
from the composed verdict rather than from raw statuses, and capacity with no
available verdict is stated as unknown rather than inferred.

The second is the closest analogue of the motivating incident, in which three
surfaces each asserted an occupied slot because each re-derived capacity from
raw work-item statuses. Without it, an implementation that silently infers
whenever no verdict exists passes every other scenario here.

Every evaluation drives the shipped capacity surface end to end over a real
repository, so the attention view under test is the one the shipped gatherer
COMPOSES rather than a document this test hands to an evaluator. That matters
for the discrimination: the same composed document carries both the capacity
verdict and the raw work-item statuses, so a statement that matches the verdict
is a statement that passed over statuses it had in hand.

The raw statuses are the fleet's own phantom-claim shape, not a strawman: a row
reading `active` with no run behind it is documented behaviour here, which is
exactly why a count of `active` rows is not a capacity verdict.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[2] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_capacity.py"
JOURNAL_RELATIVE_PATH = Path("tmp") / "fabro-dispatch-journal.jsonl"
OBSERVED_AT = "2026-08-27T02:00:00Z"
# Ten rows reading `active`, none of which is evidence that a run exists. A
# re-derivation against the cap below reads this as a closed queue.
BUSY_STATUSES: list[dict[str, object]] = [
    {"id": f"overseer-busy-{index}", "status": "active"} for index in range(10)
]
# Not one row reading `active`. A re-derivation reads this as an empty queue.
IDLE_STATUSES: list[dict[str, object]] = [
    {"id": "overseer-idle-1", "status": "ready"},
    {"id": "overseer-idle-2", "status": "backlog"},
    {"id": "overseer-idle-3", "status": "closed"},
]
# What the dispatch machinery actually holds, against what the rows suggest.
FOUR_FREE: dict[str, object] = {
    "active_count": 6,
    "free_slots": 4,
    "observed_at": OBSERVED_AT,
    "wip_cap": 10,
}
NONE_FREE: dict[str, object] = {
    "active_count": 10,
    "free_slots": 0,
    "observed_at": OBSERVED_AT,
    "wip_cap": 10,
}
# A journal record carrying no capacity report at all, so the machinery source
# is genuinely absent rather than merely unread.
UNRELATED_JOURNAL_RECORD: dict[str, object] = {
    "at": "2026-08-27T01:00:00Z",
    "stage": "dispatch-id",
    "work_item_id": "overseer-7ranbh.4",
}


def capacity_module() -> ModuleType:
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_capacity")


def write_repo(
    *,
    repo: Path,
    statuses: list[dict[str, object]],
    capacity: dict[str, object] | None = None,
    journal: list[dict[str, object]] | None = None,
) -> None:
    """Lay down a repository whose attention view carries statuses, and maybe a verdict."""
    repo.mkdir(parents=True, exist_ok=True)
    (repo / JOURNAL_RELATIVE_PATH.parent).mkdir(parents=True, exist_ok=True)
    view: dict[str, object] = {"schema_version": 1, "items": statuses}
    if capacity is not None:
        view["capacity"] = capacity
    (repo / "attention.json").write_text(json.dumps(view, sort_keys=True), encoding="utf-8")
    records = [UNRELATED_JOURNAL_RECORD] if journal is None else journal
    (repo / JOURNAL_RELATIVE_PATH).write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def state(
    *, module: ModuleType, capsys: pytest.CaptureFixture[str], repo: Path
) -> dict[str, object]:
    """Drive the shipped surface over the repository and return what it authored."""
    argv = ["--repo", str(repo), "--snapshot-path", str(repo / "absent-snapshot.json")]
    assert module.main(argv=argv) == 0
    emitted = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    document = json.loads(emitted[-1])
    assert isinstance(document, dict)
    return document


def surface_sentences(*, document: dict[str, object]) -> list[str]:
    surfaces = document["surfaces"]
    assert isinstance(surfaces, dict)
    return [str(value) for _, value in sorted(surfaces.items())]


def test_capacity_is_stated_from_the_composed_verdict_not_from_raw_statuses(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    module = capacity_module()

    # Ten rows read `active` against a cap of ten, so a re-derivation says the
    # queue is closed. The verdict the view carries says four slots are free.
    free = tmp_path / "free"
    write_repo(repo=free, statuses=BUSY_STATUSES, capacity=FOUR_FREE)
    stated_free = state(module=module, capsys=capsys, repo=free)

    assert stated_free["statement"] == module.AVAILABLE
    assert stated_free["free_slots"] == FOUR_FREE["free_slots"]
    assert stated_free["source"] == module.ATTENTION_VIEW
    assert stated_free["observed_at"] == OBSERVED_AT
    assert stated_free["unknown_reason"] is None
    assert stated_free["verdict"] == FOUR_FREE
    # The statuses were in the very document the statement was composed from.
    assert len(BUSY_STATUSES) == FOUR_FREE["wip_cap"]

    # THE OTHER DIRECTION, and it is what makes this discriminating. Not one row
    # reads `active`, so a re-derivation says every slot is free; the verdict
    # says none is. An implementation keyed on raw statuses fails one half of
    # this test whichever way it guesses.
    saturated = tmp_path / "saturated"
    write_repo(repo=saturated, statuses=IDLE_STATUSES, capacity=NONE_FREE)
    stated_saturated = state(module=module, capsys=capsys, repo=saturated)

    assert stated_saturated["statement"] == module.SATURATED
    assert stated_saturated["free_slots"] == 0
    assert stated_saturated["source"] == module.ATTENTION_VIEW
    assert not any(row["status"] == "active" for row in IDLE_STATUSES)

    # THREE SURFACES, ONE STATEMENT. The incident was three surfaces agreeing on
    # a wrong claim because each derived its own; here every surface renders the
    # same sentence, so there is nothing for one to disagree with.
    assert set(module.SURFACES) == {"escalation", "panel-dossier", "tick-report"}
    for document in (stated_free, stated_saturated):
        sentences = surface_sentences(document=document)
        assert len(sentences) == len(module.SURFACES)
        assert set(sentences) == {document["sentence"]}
    assert str(stated_free["sentence"]) != str(stated_saturated["sentence"])


def test_capacity_with_no_available_verdict_is_stated_as_unknown_never_inferred(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    module = capacity_module()

    # The same rows that would tempt an inference, and no verdict anywhere: the
    # view carries none, and the journal carries no capacity report either.
    repo = tmp_path / "repo"
    write_repo(repo=repo, statuses=BUSY_STATUSES)
    stated = state(module=module, capsys=capsys, repo=repo)

    assert stated["statement"] == module.UNKNOWN
    assert stated["source"] is None
    assert stated["verdict"] is None
    assert stated["unknown_reason"] == module.NO_VERDICT_AVAILABLE
    # It does not assert that a slot is occupied or free. `free_slots` is absent
    # rather than zero, because zero is the claim that the queue is closed.
    assert stated["free_slots"] is None
    sentence = str(stated["sentence"])
    assert "unknown" in sentence
    assert set(surface_sentences(document=stated)) == {sentence}

    # THE DISCRIMINATING CONTROL. The identical repository, identical statuses,
    # with a verdict added and nothing else changed, states a determined answer.
    # So the unknown above is caused by the verdict's absence, and not by a path
    # that never resolves anything.
    write_repo(repo=repo, statuses=BUSY_STATUSES, capacity=FOUR_FREE)
    determined = state(module=module, capsys=capsys, repo=repo)

    assert determined["statement"] == module.AVAILABLE
    assert determined["free_slots"] == FOUR_FREE["free_slots"]
    assert str(determined["sentence"]) != sentence


def test_the_dispatch_machinery_verdict_is_read_where_the_view_carries_none(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    module = capacity_module()
    stale = {"at": "2026-08-27T00:00:00Z", "free_slots": 9, "stage": "capacity-deferred"}
    current = {
        "active_count": 10,
        "at": OBSERVED_AT,
        "free_slots": 0,
        "stage": "capacity-deferred",
        "wip_cap": 10,
    }

    # No verdict on the view, and the machinery's own report stands in for it.
    machinery = tmp_path / "machinery"
    write_repo(repo=machinery, statuses=IDLE_STATUSES, journal=[stale, current])
    stated = state(module=module, capsys=capsys, repo=machinery)

    assert stated["statement"] == module.SATURATED
    assert stated["source"] == module.DISPATCH_MACHINERY
    # The LATEST report, not the first one the scan met.
    assert stated["free_slots"] == 0
    assert stated["observed_at"] == OBSERVED_AT

    # ORDERING IS BY THE RECORD'S OWN INSTANT, NOT BY POSITION. The journal is
    # append-only and cumulative, so the same two reports written in the other
    # order must still state the later one; a scan that trusted file order would
    # answer with a nine-slot queue that has since closed.
    reversed_journal = tmp_path / "reversed"
    write_repo(repo=reversed_journal, statuses=IDLE_STATUSES, journal=[current, stale])
    from_reversed = state(module=module, capsys=capsys, repo=reversed_journal)

    assert from_reversed["free_slots"] == 0
    assert from_reversed["observed_at"] == OBSERVED_AT

    # PRECEDENCE. Where the view carries a verdict it is the one stated, because
    # the view is the thing the foreman composes for this tick.
    both = tmp_path / "both"
    write_repo(repo=both, statuses=IDLE_STATUSES, capacity=FOUR_FREE, journal=[current])
    preferred = state(module=module, capsys=capsys, repo=both)

    assert preferred["source"] == module.ATTENTION_VIEW
    assert preferred["free_slots"] == FOUR_FREE["free_slots"]


def test_every_unreadable_verdict_resolves_unknown_and_infers_nothing() -> None:
    assert MODULE_PATH.is_file()
    module = capacity_module()
    unreadable: tuple[object, ...] = (
        None,
        "not-an-object",
        {},
        {"capacity": "not-an-object"},
        {"capacity": {}},
        {"capacity": {"free_slots": "not-a-count"}},
        {"capacity": {"free_slots": True}},
        {"capacity": {"free_slots": -1}},
        {"capacity": {"active_count": 6}},
        {"capacity": {"wip_cap": 10}},
    )
    for attention in unreadable:
        statement = module.capacity_statement(attention=attention, journal_records=None)
        assert statement.statement == module.UNKNOWN
        assert statement.free_slots is None
        assert statement.source is None
        assert statement.unknown_reason == module.NO_VERDICT_AVAILABLE

    # The journal side fails the same way, and for the same reasons.
    unreadable_journal: tuple[object, ...] = (
        None,
        "not-a-list",
        [],
        ["not-an-object"],
        [{"stage": "dispatch-id", "free_slots": 4}],
        [{"stage": "capacity-deferred"}],
        [{"stage": "capacity-deferred", "free_slots": "not-a-count"}],
    )
    for records in unreadable_journal:
        statement = module.capacity_statement(attention=None, journal_records=records)
        assert statement.statement == module.UNKNOWN
        assert statement.source is None

    # THE CONTROLS, so each unknown above is an unreadable input rather than a
    # branch that never resolves. A cap and a count with no free-slot field is a
    # verdict the machinery reported, and it is read as one.
    derived = module.capacity_statement(
        attention={"capacity": {"active_count": 10, "wip_cap": 10}}, journal_records=None
    )
    assert derived.statement == module.SATURATED
    assert derived.free_slots == 0
    assert derived.observed_at is None

    over_cap = module.capacity_statement(
        attention={"capacity": {"active_count": 12, "wip_cap": 10}}, journal_records=None
    )
    assert over_cap.free_slots == 0

    from_journal = module.capacity_statement(
        attention=None, journal_records=[{"stage": "capacity", "free_slots": 2}]
    )
    assert from_journal.statement == module.AVAILABLE
    assert from_journal.source == module.DISPATCH_MACHINERY
    assert from_journal.free_slots == 2
