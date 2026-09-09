"""The drain treats a PLAN as a completable unit (`overseer-exz7`, `overseer-9gfh`).

Every test here pins one of the five defects measured against livespec-dev-tooling
on 2026-09-08. The first four are `overseer-exz7`'s, and the load-bearing one of
those is that the predecessor anomaly detector fired only on "epic CLOSED and
directory live", which is the INVERSE of the failure that occurs, so running it
over that whole tenant flagged nothing.

The FIFTH is `overseer-9gfh`, and it was found by running exz7's delivered code:
completion was inferred from the ABSENCE of open children rather than from POSITIVE
evidence that the plan's DECLARED scope is drained. Two shapes in that tenant are
pinned below as the false positives they are, and BOTH were once read as true ones
— `test_the_console_factory_build_cache_shape_declares_no_scope_and_is_not_finished`
is the correction of this module's own first regression test, which pinned a false
positive as the exemplar of `finished-unarchived`. The genuinely-finished control is
CONSTRUCTED, because no plan in that tenant was ever verified genuinely finished.

The module under test is a plugin script rather than a package module, so it is
reached through an explicit path insert. `snapshot.py` is deliberately NOT imported
here: it shells out to `bd` and its own coverage is not this test's subject.

The positive-evidence readers the fifth defect produced sit in `plan_evidence`
beside `plan_completion`, which composes with them; both are imported here, and
each assertion drives whichever module now owns the name.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

__all__: list[str] = []

SCRIPTS = Path(__file__).resolve().parent.parent / ".claude-plugin" / "scripts" / "drain-backlog"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

pc = importlib.import_module("plan_completion")
ev = importlib.import_module("plan_evidence")

Item = dict[str, Any]


def _item(
    *,
    identifier: str,
    status: str = "backlog",
    issue_type: str = "task",
    slug: str | None = None,
) -> Item:
    item: Item = {"id": identifier, "status": status, "issue_type": issue_type}
    if slug is not None:
        item["metadata"] = {"plan_slug": slug}
    return item


def _repo(*, tmp_path: Path, slugs: tuple[str, ...], anchors: dict[str, str] | None = None) -> Path:
    plan = tmp_path / "plan"
    (plan / "archive" / "an-old-plan").mkdir(parents=True)
    (plan / "not-a-directory.md").write_text("stray file beside the plan dirs\n")
    for slug in slugs:
        (plan / slug).mkdir()
    for slug, body in (anchors or {}).items():
        (plan / slug / pc.ANCHOR_FILENAME).write_text(body)
    return tmp_path


def _snapshot(*, repo: Path, slug: str, rel: str, body: str) -> None:
    """Write one scope document into a plan directory, at any depth beneath it."""
    path = repo / "plan" / slug / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _frozen(*, ids: list[str]) -> str:
    """A frozen-snapshot document in the shape `snapshot.py` itself writes."""
    return json.dumps({"taken_at": "2026-09-06T07:45:00Z", "frozen_ids": ids})


# ---------------------------------------------------------------------------
# Defect 1 — the anomaly detector was pointed at the inverse of the real failure
# ---------------------------------------------------------------------------


def test_the_console_factory_build_cache_shape_declares_no_scope_and_is_not_finished(
    *, tmp_path: Path
) -> None:
    """CORRECTION: this shape was pinned here as the TRUE positive and it is a FALSE one.

    Epic `3u3gm2` OPEN, children `.1` and `.2` both CLOSED, directory live — so the
    child set says finished. Measured 2026-09-08T15:35Z, it is not: that plan's own
    plan-scope-event of 2026-09-04T20:14:05Z names THREE requirement carriers, and
    only shape 1 was ever filed as a child. The shape-2 host-backed-sccache carrier
    was NEVER FILED, and the epic's typed next_action still says to file it. The
    plan reads 2/2 complete BECAUSE its second carrier is missing from the child
    set, which is this defect's exact shape.
    """
    repo = _repo(tmp_path=tmp_path, slugs=("console-factory-build-cache",))
    items = [
        _item(
            identifier="livespec-dev-tooling-3u3gm2",
            status="backlog",
            issue_type="epic",
            slug="console-factory-build-cache",
        ),
        _item(identifier="livespec-dev-tooling-3u3gm2.1", status="closed"),
        _item(identifier="livespec-dev-tooling-3u3gm2.2", status="closed"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state != pc.FINISHED_UNARCHIVED
    assert record.state == pc.SCOPE_UNDECLARED
    assert record.epic == "livespec-dev-tooling-3u3gm2"
    assert record.epic_status == "backlog"
    assert (record.closed_child_count, record.child_count) == (2, 2)
    assert (record.scope_size, record.scope_open_count) == (0, 0)
    assert pc.records_needing_action(records=(record,)) == ()


def test_an_epic_with_open_children_is_in_progress_and_needs_no_act(*, tmp_path: Path) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=("half-done",))
    items = [
        _item(identifier="dt-a", issue_type="epic", slug="half-done"),
        _item(identifier="dt-a.1", status="closed"),
        _item(identifier="dt-a.2", status="ready"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.IN_PROGRESS
    assert pc.records_needing_action(records=(record,)) == ()


def test_an_epic_with_no_children_at_all_is_never_called_finished(*, tmp_path: Path) -> None:
    """Every-child-is-closed is VACUOUSLY true of an epic nobody has filed work under."""
    repo = _repo(tmp_path=tmp_path, slugs=("unstarted",))
    items = [_item(identifier="dt-b", issue_type="epic", slug="unstarted")]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.IN_PROGRESS
    assert record.child_count == 0


def test_the_old_anomaly_epic_closed_with_a_live_directory_is_still_detected(
    *, tmp_path: Path
) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=("landed",))
    items = [_item(identifier="dt-c", status="closed", issue_type="epic", slug="landed")]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.EPIC_CLOSED_DIR_LIVE
    assert "archive plan/landed/" in record.action


def test_an_archived_directory_whose_epic_is_still_open_is_reported(*, tmp_path: Path) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=())
    items = [_item(identifier="dt-d", issue_type="epic", slug="already-archived")]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.EPIC_OPEN_DIR_ARCHIVED
    assert record.dir_live is False


def test_the_archived_directory_action_names_the_directory_and_counts_the_open_children(
    *, tmp_path: Path
) -> None:
    """Measured 2026-09-08: TEN of twelve queued records were this state.

    Several of those epics were nowhere near closeable — `8o8e` at 12 of 31
    children closed — while the action said "dispose every child, review the epic,
    then close it" unconditionally. Ten such lines in a twelve-line queue train the
    reader to skip the queue, which is the same ignore-the-check failure the
    cross-tenant sentinel exists to avoid. The act named now is reconciling the
    DIRECTORY against its open epic, and the open-child count is in the line so a
    one-item tail is distinguishable from a live 19-item epic. The CLASSIFICATION
    is unchanged.
    """
    repo = _repo(tmp_path=tmp_path, slugs=())
    items = [
        _item(identifier="dt-8o8e", issue_type="epic", slug="rop-railway-enforcement"),
        _item(identifier="dt-8o8e.1", status="closed"),
        _item(identifier="dt-8o8e.2", status="ready"),
        _item(identifier="dt-8o8e.3", status="ready"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.EPIC_OPEN_DIR_ARCHIVED
    assert "plan/rop-railway-enforcement/" in record.action
    assert "open children: 2" in record.action


def test_a_closed_epic_with_an_archived_directory_is_simply_archived(*, tmp_path: Path) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=())
    items = [_item(identifier="dt-e", status="done", issue_type="epic", slug="finished-long-ago")]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.ARCHIVED
    assert pc.records_needing_action(records=(record,)) == ()


# ---------------------------------------------------------------------------
# Defect 2 — the membership key missed the plans that need attention
# ---------------------------------------------------------------------------


def test_a_plan_directory_with_no_slug_tagged_epic_is_still_reported(*, tmp_path: Path) -> None:
    """Four of eight measured plan directories had no epic carrying their slug."""
    repo = _repo(tmp_path=tmp_path, slugs=("rop-railway-enforcement",))
    items = [_item(identifier="dt-8o8e", issue_type="epic")]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.plan_slug == "rop-railway-enforcement"
    assert record.state == pc.UNLINKED
    assert record.epic is None
    assert pc.ANCHOR_FILENAME in record.action


def test_the_anchor_file_reaches_a_subject_epic_the_slug_cannot(*, tmp_path: Path) -> None:
    repo = _repo(
        tmp_path=tmp_path,
        slugs=("pure-trees-role-key-scope",),
        anchors={"pure-trees-role-key-scope": "\n\ndt-8o8e\n"},
    )
    items = [
        _item(identifier="dt-8o8e", issue_type="epic"),
        _item(identifier="dt-8o8e.1", status="closed"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.anchor == "dt-8o8e"
    assert record.epic == "dt-8o8e"
    assert record.child_count == 1


def test_an_anchor_naming_no_local_row_falls_back_to_the_slug(*, tmp_path: Path) -> None:
    repo = _repo(
        tmp_path=tmp_path,
        slugs=("dangling",),
        anchors={"dangling": "dt-vanished\n"},
    )
    items = [_item(identifier="dt-real", issue_type="epic", slug="dangling")]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.epic == "dt-real"


def test_an_anchor_file_of_only_blank_lines_reads_as_no_anchor(*, tmp_path: Path) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=("blank-anchor",), anchors={"blank-anchor": "\n  \n"})

    assert pc.anchor_of(repo=repo, slug="blank-anchor") is None


def test_a_repo_with_no_plan_directory_at_all_reports_no_live_slugs(*, tmp_path: Path) -> None:
    assert pc.live_plan_slugs(repo=tmp_path) == ()


def test_the_archive_directory_and_stray_files_are_not_plans(*, tmp_path: Path) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=("real-plan",))

    assert pc.live_plan_slugs(repo=repo) == ("real-plan",)


# ---------------------------------------------------------------------------
# Defect 3 — the membership key over-counted, because children inherit the slug
# ---------------------------------------------------------------------------


def test_a_plan_whose_children_inherit_its_slug_is_counted_exactly_once(*, tmp_path: Path) -> None:
    """`performance-improvements-01` came back eleven times: the epic plus `.1`-`.10`."""
    repo = _repo(tmp_path=tmp_path, slugs=("performance-improvements-01",))
    slug = "performance-improvements-01"
    items = [_item(identifier="dt-yilyxr", issue_type="epic", slug=slug)]
    items += [_item(identifier=f"dt-yilyxr.{n}", status="closed", slug=slug) for n in range(1, 11)]

    records = pc.plan_records(items=items, repo=repo)

    assert [record.plan_slug for record in records] == [slug]
    assert records[0].epic == "dt-yilyxr"
    assert records[0].child_count == 10
    assert pc.ledger_plan_slugs(items=items) == (slug,)


def test_the_subject_epic_is_never_an_inheriting_child_even_with_no_epic_typed_row(
    *, tmp_path: Path
) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=("task-rooted",))
    items = [
        _item(identifier="dt-zzz.2", slug="task-rooted"),
        _item(identifier="dt-root", slug="task-rooted"),
        _item(identifier="dt-zzz.1", slug="task-rooted"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.epic == "dt-root"


def test_the_slug_fallback_prefers_an_epic_and_is_deterministic(*, tmp_path: Path) -> None:
    items = [
        _item(identifier="dt-b", slug="shared"),
        _item(identifier="dt-z", issue_type="epic", slug="shared"),
        _item(identifier="dt-a", issue_type="epic", slug="shared"),
    ]

    epic = pc.subject_epic(items=items, slug="shared", anchor=None)

    assert epic is not None
    assert epic["id"] == "dt-a"


def test_children_are_rooted_by_the_dotted_id_and_exclude_the_epic_itself() -> None:
    items = [
        _item(identifier="dt-a", issue_type="epic"),
        _item(identifier="dt-a.1"),
        _item(identifier="dt-a.1.3"),
        _item(identifier="dt-ab.1"),
        _item(identifier="dt-b"),
    ]

    children = pc.children_of(items=items, epic_id="dt-a")

    assert [str(child["id"]) for child in children] == ["dt-a.1", "dt-a.1.3"]


# ---------------------------------------------------------------------------
# Defect 5 — completion inferred from ABSENCE, not from positive scope evidence
# ---------------------------------------------------------------------------


def test_the_drains_own_plan_is_not_finished_while_its_frozen_snapshot_holds_open_ids(
    *, tmp_path: Path
) -> None:
    """MEASURED 2026-09-08T15:25Z: `dev-tooling-backlog-drain` reported finished at 114/258.

    Epic `kcoslm` OPEN, exactly ONE child and it is CLOSED, directory live — a
    mechanical child the plan filed for itself, which is the state EVERY plan
    reaches sooner or later. Its scope is not its children: it is the frozen
    snapshot beside its research, and that snapshot still held 144 open ids.
    Acting on the record's named action would have closed the epic and archived
    the directory of a LIVE drive, destroying the resume path for all 144.
    """
    slug = "dev-tooling-backlog-drain"
    repo = _repo(tmp_path=tmp_path, slugs=(slug,))
    closed_ids = [f"livespec-dev-tooling-c{n}" for n in range(114)]
    open_ids = [f"livespec-dev-tooling-o{n}" for n in range(144)]
    _snapshot(
        repo=repo,
        slug=slug,
        rel="research/002-snapshot-2026-09-06.json",
        body=_frozen(ids=[*closed_ids, *open_ids]),
    )
    items = [
        _item(identifier="livespec-dev-tooling-kcoslm", issue_type="epic", slug=slug),
        _item(identifier="livespec-dev-tooling-kcoslm.1", status="closed"),
        *[_item(identifier=identifier, status="closed") for identifier in closed_ids],
        *[_item(identifier=identifier, status="ready") for identifier in open_ids],
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.IN_PROGRESS
    assert record.state != pc.FINISHED_UNARCHIVED
    assert (record.closed_child_count, record.child_count) == (1, 1)
    assert (record.scope_size, record.scope_open_count) == (258, 144)
    assert pc.records_needing_action(records=(record,)) == ()


def test_a_plan_whose_declared_scope_is_drained_is_finished_and_is_queued(
    *, tmp_path: Path
) -> None:
    """THE TRUE POSITIVE, and it is CONSTRUCTED rather than taken from that tenant.

    Both tenant shapes above were read as genuinely finished at some point and both
    are false; no plan there was ever verified finished, so the positive control is
    built here. The evidence is POSITIVE: the plan declares a scope this module can
    read, and every id in it is closed.
    """
    repo = _repo(tmp_path=tmp_path, slugs=("scope-drained",))
    _snapshot(
        repo=repo,
        slug="scope-drained",
        rel="snapshot.json",
        body=_frozen(ids=["dt-1", "dt-2", "dt-3"]),
    )
    items = [
        _item(identifier="dt-f", issue_type="epic", slug="scope-drained"),
        _item(identifier="dt-f.1", status="closed"),
        *[_item(identifier=f"dt-{n}", status="closed") for n in (1, 2, 3)],
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.FINISHED_UNARCHIVED
    assert (record.scope_size, record.scope_open_count) == (3, 0)
    assert record in pc.records_needing_action(records=(record,))


def test_the_declared_scope_decides_completion_and_the_child_set_does_not(
    *, tmp_path: Path
) -> None:
    """A DRAINED scope is finished even with an open child; a child set alone never is.

    This is the skill's own §2 rule that nothing filed after the freeze extends the
    plan, read through to its consequence: the frozen scope is the scope, and a row
    that arrived later is `admitted_after_snapshot` rather than a widened exit gate.
    The named act's FIRST step is disposing every child, so an open child is inside
    the action rather than a contradiction of it.
    """
    repo = _repo(tmp_path=tmp_path, slugs=("scope-rules",))
    _snapshot(repo=repo, slug="scope-rules", rel="snapshot.json", body=_frozen(ids=["dt-1"]))
    items = [
        _item(identifier="dt-g", issue_type="epic", slug="scope-rules"),
        _item(identifier="dt-g.1", status="ready"),
        _item(identifier="dt-1", status="closed"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.FINISHED_UNARCHIVED
    assert (record.closed_child_count, record.child_count) == (0, 1)


def test_an_id_in_the_declared_scope_that_no_ledger_row_carries_counts_as_open(
    *, tmp_path: Path
) -> None:
    """Unknown is not evidence of exhaustion, so an id the ledger cannot show is OPEN."""
    repo = _repo(tmp_path=tmp_path, slugs=("scope-unknown",))
    _snapshot(
        repo=repo,
        slug="scope-unknown",
        rel="snapshot.json",
        body=_frozen(ids=["dt-1", "dt-vanished"]),
    )
    items = [
        _item(identifier="dt-h", issue_type="epic", slug="scope-unknown"),
        _item(identifier="dt-h.1", status="closed"),
        _item(identifier="dt-1", status="closed"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state == pc.IN_PROGRESS
    assert (record.scope_size, record.scope_open_count) == (2, 1)


def test_an_empty_frozen_scope_is_not_a_declaration(*, tmp_path: Path) -> None:
    """The same vacuity rule the child set already has: an empty scope proves nothing.

    Without this, freezing an EMPTY snapshot would be the shortest possible route to
    a false `finished` — every id in it is closed, vacuously.
    """
    repo = _repo(tmp_path=tmp_path, slugs=("empty-scope",))
    _snapshot(repo=repo, slug="empty-scope", rel="snapshot.json", body=_frozen(ids=[]))
    items = [
        _item(identifier="dt-i", issue_type="epic", slug="empty-scope"),
        _item(identifier="dt-i.1", status="closed"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state != pc.FINISHED_UNARCHIVED
    assert record.state == pc.SCOPE_UNDECLARED
    assert record.scope_size == 0


def test_a_snapshot_that_will_not_parse_withdraws_the_whole_declaration(*, tmp_path: Path) -> None:
    """A scope read from the READABLE siblings alone is missing exactly what the bad one held.

    So an unreadable document does not merely contribute nothing — it withdraws the
    plan's declaration, and the plan drops back to the unproven state rather than
    being declared finished off a scope that is known to be partial.
    """
    repo = _repo(tmp_path=tmp_path, slugs=("torn-scope",))
    _snapshot(repo=repo, slug="torn-scope", rel="snapshot.json", body=_frozen(ids=["dt-1"]))
    _snapshot(repo=repo, slug="torn-scope", rel="research/002-snapshot.json", body="{not json")
    items = [
        _item(identifier="dt-j", issue_type="epic", slug="torn-scope"),
        _item(identifier="dt-j.1", status="closed"),
        _item(identifier="dt-1", status="closed"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert record.state != pc.FINISHED_UNARCHIVED
    assert record.state == pc.SCOPE_UNDECLARED
    assert record.scope_size == 0


def test_the_declared_scope_is_the_union_of_every_snapshot_the_plan_holds(
    *, tmp_path: Path
) -> None:
    """A plan that re-froze keeps the history beside it; the SUPERSET is the safe read."""
    repo = _repo(tmp_path=tmp_path, slugs=("refrozen",))
    _snapshot(
        repo=repo,
        slug="refrozen",
        rel="research/001-snapshot-2026-09-01.json",
        body=_frozen(ids=["dt-1", "dt-2"]),
    )
    _snapshot(
        repo=repo,
        slug="refrozen",
        rel="research/002-snapshot-2026-09-06.json",
        body=_frozen(ids=["dt-2", "dt-3"]),
    )
    items = [
        _item(identifier="dt-k", issue_type="epic", slug="refrozen"),
        _item(identifier="dt-1", status="closed"),
        _item(identifier="dt-2", status="closed"),
        _item(identifier="dt-3", status="ready"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert (record.scope_size, record.scope_open_count) == (3, 1)
    assert record.state == pc.IN_PROGRESS


def test_scope_ids_are_read_from_every_shape_snapshot_py_writes() -> None:
    """POSITIVE CONTROL for the reader: a zero is otherwise indistinguishable from a miss."""
    assert ev.scope_ids_of(payload={"frozen_ids": [" dt-1 ", "", 7, {"id": "dt-2"}]}) == (
        "dt-1",
        "dt-2",
    )
    assert ev.scope_ids_of(payload={"items": [{"id": "dt-3"}, {"tier": 1}]}) == ("dt-3",)
    assert ev.scope_ids_of(payload=["dt-4"]) == ("dt-4",)
    assert ev.scope_ids_of(payload={"frozen_ids": "not-a-list", "items": 3}) == ()
    assert ev.scope_ids_of(payload={"taken_at": "2026-09-06T07:45:00Z"}) == ()
    assert ev.scope_ids_of(payload="not a scope document") == ()


def test_read_json_document_reports_an_unreadable_document_as_none(*, tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    good.write_text('{"frozen_ids": []}', encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")

    assert ev.read_json_document(path=good) == {"frozen_ids": []}
    assert ev.read_json_document(path=bad) is None


def test_the_finished_plans_action_names_closing_the_epic_and_archiving_the_directory(
    *, tmp_path: Path
) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=("console-factory-build-cache",))
    _snapshot(
        repo=repo,
        slug="console-factory-build-cache",
        rel="snapshot.json",
        body=_frozen(ids=["dt-1"]),
    )
    items = [
        _item(
            identifier="dt-3u3gm2",
            issue_type="epic",
            slug="console-factory-build-cache",
        ),
        _item(identifier="dt-3u3gm2.1", status="closed"),
        _item(identifier="dt-1", status="closed"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert "close the epic" in record.action
    assert "plan/console-factory-build-cache/" in record.action
    assert "independent completeness review" in record.action
    assert "declared scope: 1 ids" in record.action


def test_the_scope_undeclared_action_refuses_to_name_a_drive_to_completion(
    *, tmp_path: Path
) -> None:
    """The state is REPORTED and NOT actionable, and its action line must say why.

    An action that names closing the epic here is the destructive fire this whole
    rule exists to prevent — and a queue full of them is how a check earns its way
    into being ignored.
    """
    repo = _repo(tmp_path=tmp_path, slugs=("unproven",))
    items = [
        _item(identifier="dt-u", issue_type="epic", slug="unproven"),
        _item(identifier="dt-u.1", status="closed"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert "close the epic" not in record.action
    assert "UNPROVEN" in record.action
    assert "plan/unproven/" in record.action
    assert record.state == pc.SCOPE_UNDECLARED


# ---------------------------------------------------------------------------
# The cross-tenant anchor sentinel — a DECLARATION, never a missing link
# ---------------------------------------------------------------------------


def test_a_cross_tenant_anchor_sentinel_is_not_reported_as_unlinked(*, tmp_path: Path) -> None:
    """`mutation-testing-keystone`'s real anchor is `livespec-mutreal`, in another tenant."""
    repo = _repo(
        tmp_path=tmp_path,
        slugs=("mutation-testing-keystone",),
        anchors={"mutation-testing-keystone": f"{pc.CROSS_TENANT_ANCHOR_SENTINEL}\n"},
    )

    (record,) = pc.plan_records(items=[], repo=repo)

    assert record.state == pc.CROSS_TENANT_ANCHOR
    assert record.state != pc.UNLINKED
    assert pc.records_needing_action(records=(record,)) == ()


def test_the_sentinel_never_resolves_to_a_row_that_happens_to_be_named_for_it() -> None:
    items = [_item(identifier=pc.CROSS_TENANT_ANCHOR_SENTINEL, issue_type="epic")]

    assert pc.subject_epic(items=items, slug="s", anchor=pc.CROSS_TENANT_ANCHOR_SENTINEL) is None


def test_a_slug_known_only_to_the_ledger_with_no_directory_is_archived_not_unlinked(
    *, tmp_path: Path
) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=())

    (record,) = pc.plan_records(items=[_item(identifier="dt-x.1", slug="gone")], repo=repo)

    assert record.state == pc.ARCHIVED
    assert record.epic is None


# ---------------------------------------------------------------------------
# Record shape, and the primitives the states are built from
# ---------------------------------------------------------------------------


def test_plan_records_unions_both_identification_routes_and_sorts_by_slug(
    *, tmp_path: Path
) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=("zeta-on-disk", "alpha-on-disk"))
    items = [_item(identifier="dt-m", issue_type="epic", slug="mid-in-ledger")]

    records = pc.plan_records(items=items, repo=repo)

    assert [record.plan_slug for record in records] == [
        "alpha-on-disk",
        "mid-in-ledger",
        "zeta-on-disk",
    ]


def test_record_json_round_trips_every_field(*, tmp_path: Path) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=("shape",))
    items = [_item(identifier="dt-s", issue_type="epic", slug="shape")]

    (record,) = pc.plan_records(items=items, repo=repo)
    payload = pc.record_json(record=record)

    assert set(payload) == {
        "plan_slug",
        "state",
        "action",
        "epic",
        "epic_status",
        "anchor",
        "dir_live",
        "child_count",
        "closed_child_count",
        "scope_size",
        "scope_open_count",
    }
    assert payload["plan_slug"] == "shape"


def test_every_state_has_an_action_and_the_actionable_set_excludes_the_healthy_ones() -> None:
    states = {
        pc.ARCHIVED,
        pc.CROSS_TENANT_ANCHOR,
        pc.EPIC_CLOSED_DIR_LIVE,
        pc.EPIC_OPEN_DIR_ARCHIVED,
        pc.FINISHED_UNARCHIVED,
        pc.IN_PROGRESS,
        pc.SCOPE_UNDECLARED,
        pc.UNLINKED,
    }

    assert set(pc.ACTIONS) == states
    assert states > pc.ACTIONABLE_STATES
    assert pc.ARCHIVED not in pc.ACTIONABLE_STATES
    assert pc.IN_PROGRESS not in pc.ACTIONABLE_STATES
    assert pc.CROSS_TENANT_ANCHOR not in pc.ACTIONABLE_STATES
    assert pc.SCOPE_UNDECLARED not in pc.ACTIONABLE_STATES


def test_plan_slug_of_reads_only_a_truthy_string_metadata_key() -> None:
    assert pc.plan_slug_of(item={"id": "a"}) is None
    assert pc.plan_slug_of(item={"id": "a", "metadata": "not-a-mapping"}) is None
    assert pc.plan_slug_of(item={"id": "a", "metadata": {}}) is None
    assert pc.plan_slug_of(item={"id": "a", "metadata": {"plan_slug": "  "}}) is None
    assert pc.plan_slug_of(item={"id": "a", "metadata": {"plan_slug": " s "}}) == "s"


def test_status_of_normalises_and_is_closed_reads_both_terminal_names() -> None:
    assert pc.status_of(item={"status": " Closed "}) == "closed"
    assert pc.status_of(item={"status": None}) == ""
    assert pc.is_closed(item={"status": "closed"}) is True
    assert pc.is_closed(item={"status": "done"}) is True
    assert pc.is_closed(item={"status": "ready"}) is False


def test_root_id_of_strips_every_dotted_suffix() -> None:
    assert pc.root_id_of(identifier="dt-a.1.2") == "dt-a"
    assert pc.root_id_of(identifier="dt-a") == "dt-a"


def test_plan_state_dispatches_on_whether_a_subject_epic_was_found() -> None:
    epic = _item(identifier="dt-a", issue_type="epic")
    undeclared = pc.PlanScope(ids=(), open_ids=())

    assert (
        pc.plan_state(epic=None, children=(), dir_live=True, anchor=None, scope=undeclared)
        == pc.UNLINKED
    )
    assert (
        pc.plan_state(epic=epic, children=(), dir_live=True, anchor=None, scope=undeclared)
        == pc.IN_PROGRESS
    )
