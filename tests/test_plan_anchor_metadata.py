"""Direct coverage for the plan-anchor metadata check.

This module's behaviour used to be exercised indirectly, through the grooming
conformance report that aggregated it (`tests/test_grooming_conformance.py`).
That suite went with the grooming seat, so the check is pinned here against its
own surface instead — which is also the surface its one live consumer,
`scripts/check-plan-anchor-metadata.py`, actually calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "overseer"))

import plan_anchor_metadata as anchors

__all__: list[str] = []


def _epic(*, item_id: str, slug: str | None, status: str = "backlog") -> dict[str, object]:
    metadata: dict[str, object] = {} if slug is None else {"plan_slug": slug}
    return {
        "id": item_id,
        "status": status,
        "issue_type": "epic",
        "title": f"Plan anchor for {slug}",
        "metadata": metadata,
    }


def _repo(*, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "plan").mkdir(parents=True)
    return repo


def test_check_discriminates_missing_duplicate_and_correctly_tagged_directories(
    *,
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path=tmp_path)
    (repo / "plan" / "missing").mkdir()
    (repo / "plan" / "duplicate").mkdir()
    (repo / "plan" / "tagged").mkdir()
    # `archive` is deliberately NOT a live plan directory and must not be scanned.
    (repo / "plan" / "archive").mkdir()

    check = anchors.plan_anchor_metadata_check(
        repo=repo,
        items=[
            _epic(item_id="duplicate-1", slug="duplicate"),
            _epic(item_id="duplicate-2", slug="duplicate"),
            _epic(item_id="tagged-anchor", slug="tagged"),
            # A closed epic is terminal, so it cannot satisfy `plan/missing`.
            _epic(item_id="closed-ignored", slug="missing", status="closed"),
        ],
    )

    assert check.key == "plan-anchor-metadata"
    assert check.status == "checked"
    assert check.scanned_item_count == 3
    assert check.breaching_item_ids == ("duplicate-1", "duplicate-2", "plan/missing")
    assert "exactly one same-tenant epic" in check.reason
    assert "livespec-dev-tooling-aqmr" in check.reason


def test_check_passes_when_every_live_directory_has_exactly_one_anchor(
    *,
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path=tmp_path)
    (repo / "plan" / "tagged").mkdir()

    check = anchors.plan_anchor_metadata_check(
        repo=repo,
        items=[_epic(item_id="tagged-anchor", slug="tagged")],
    )

    assert check.breaching_item_ids == ()
    assert check.scanned_item_count == 1


def test_live_plan_directory_slugs_skips_files_and_the_archive(*, tmp_path: Path) -> None:
    repo = _repo(tmp_path=tmp_path)
    (repo / "plan" / "beta").mkdir()
    (repo / "plan" / "alpha").mkdir()
    (repo / "plan" / "archive").mkdir()
    (repo / "plan" / "README.md").write_text("not a plan", encoding="utf-8")

    assert anchors.live_plan_directory_slugs(repo=repo) == ("alpha", "beta")


def test_anchor_breaches_reports_the_directory_when_absent_and_the_ids_when_duplicated() -> None:
    assert anchors.anchor_breaches(slug="solo", anchor_ids=["only"]) == ()
    assert anchors.anchor_breaches(slug="none", anchor_ids=[]) == ("plan/none",)
    assert anchors.anchor_breaches(slug="many", anchor_ids=["a", "b"]) == ("a", "b")


def test_is_open_epic_reads_either_type_key_and_excludes_terminal_statuses() -> None:
    assert anchors.is_open_epic(item={"issue_type": "epic", "status": "backlog"})
    assert anchors.is_open_epic(item={"type": "epic", "status": "ready"})
    assert not anchors.is_open_epic(item={"issue_type": "task", "status": "backlog"})
    assert not anchors.is_open_epic(item={"issue_type": "epic", "status": "closed"})
    assert not anchors.is_open_epic(item={"issue_type": "epic", "status": "DONE"})


def test_metadata_plan_slug_is_none_for_every_unusable_shape() -> None:
    assert anchors.metadata_plan_slug(item={"metadata": {"plan_slug": " slug "}}) == "slug"
    assert anchors.metadata_plan_slug(item={"metadata": None}) is None
    assert anchors.metadata_plan_slug(item={"metadata": "not-an-object"}) is None
    assert anchors.metadata_plan_slug(item={"metadata": {}}) is None
    assert anchors.metadata_plan_slug(item={"metadata": {"plan_slug": 7}}) is None
    assert anchors.metadata_plan_slug(item={"metadata": {"plan_slug": "   "}}) is None


def test_item_id_and_item_status_normalize_missing_and_wrong_typed_values() -> None:
    assert anchors.item_id(item={"id": "overseer-1"}) == "overseer-1"
    assert anchors.item_id(item={"id": ""}) is None
    assert anchors.item_id(item={"id": 7}) is None
    assert anchors.item_id(item={}) is None

    assert anchors.item_status(item={"status": "Closed"}) == "closed"
    assert anchors.item_status(item={"status": None}) == ""
    assert anchors.item_status(item={}) == ""


def test_anchor_ids_by_slug_skips_rows_missing_a_slug_or_an_id(*, tmp_path: Path) -> None:
    by_slug = anchors.plan_anchor_epic_ids_by_slug(
        items=[
            _epic(item_id="has-both", slug="alpha"),
            _epic(item_id="no-slug", slug=None),
            {"id": "", "status": "backlog", "issue_type": "epic", "metadata": {"plan_slug": "a"}},
        ],
    )

    assert by_slug == {"alpha": ("has-both",)}
