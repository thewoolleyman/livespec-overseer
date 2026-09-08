"""The drain treats a PLAN as a completable unit (work-item `overseer-exz7`).

Every test here pins one of the four defects measured against livespec-dev-tooling
on 2026-09-08, and the load-bearing one is
`test_the_console_factory_build_cache_shape_is_finished_but_unarchived`: the
predecessor anomaly detector fired only on "epic CLOSED and directory live", which
is the INVERSE of the failure that occurs, so running it over that whole tenant
flagged nothing while a genuinely finished plan sat unarchived.

The module under test is a skill script rather than a package module, so it is
reached through an explicit path insert. `snapshot.py` is deliberately NOT imported
here: it shells out to `bd` and its own coverage is not this test's subject.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

__all__: list[str] = []

SCRIPTS = (
    Path(__file__).resolve().parent.parent / ".claude" / "skills" / "drain-backlog" / "scripts"
)
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

pc = importlib.import_module("plan_completion")

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


# ---------------------------------------------------------------------------
# Defect 1 — the anomaly detector was pointed at the inverse of the real failure
# ---------------------------------------------------------------------------


def test_the_console_factory_build_cache_shape_is_finished_but_unarchived(
    *, tmp_path: Path
) -> None:
    """Epic OPEN, every child CLOSED, directory live — the state that used to be invisible."""
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

    assert record.state == pc.FINISHED_UNARCHIVED
    assert record.epic == "livespec-dev-tooling-3u3gm2"
    assert record.epic_status == "backlog"
    assert (record.closed_child_count, record.child_count) == (2, 2)
    assert record in pc.records_needing_action(records=(record,))


def test_the_finished_plans_action_names_closing_the_epic_and_archiving_the_directory(
    *, tmp_path: Path
) -> None:
    repo = _repo(tmp_path=tmp_path, slugs=("console-factory-build-cache",))
    items = [
        _item(
            identifier="dt-3u3gm2",
            issue_type="epic",
            slug="console-factory-build-cache",
        ),
        _item(identifier="dt-3u3gm2.1", status="closed"),
    ]

    (record,) = pc.plan_records(items=items, repo=repo)

    assert "close the epic" in record.action
    assert "plan/console-factory-build-cache/" in record.action
    assert "independent completeness review" in record.action


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
    assert record.state == pc.FINISHED_UNARCHIVED


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
        pc.UNLINKED,
    }

    assert set(pc.ACTIONS) == states
    assert states > pc.ACTIONABLE_STATES
    assert pc.ARCHIVED not in pc.ACTIONABLE_STATES
    assert pc.IN_PROGRESS not in pc.ACTIONABLE_STATES
    assert pc.CROSS_TENANT_ANCHOR not in pc.ACTIONABLE_STATES


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

    assert pc.plan_state(epic=None, children=(), dir_live=True, anchor=None) == pc.UNLINKED
    assert pc.plan_state(epic=epic, children=(), dir_live=True, anchor=None) == pc.IN_PROGRESS
