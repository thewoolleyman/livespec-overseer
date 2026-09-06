"""Archive-GC row-keeping edge coverage."""

import json
from pathlib import Path

from test_supervisor_builders import make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_archive_gc_keeps_raw_row_without_repo_or_topic(*, tmp_path):
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.store_path).write_text(
        json.dumps({"kind": "plan", "repo": "/repo-only"}) + "\n",
        encoding="utf-8",
    )

    dropped = sup.archive_gc()

    assert dropped == 0


def test_archive_gc_keeps_unknown_kind_row(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.store_path).write_text(
        json.dumps({"kind": "mystery", "repo": str(repo), "topic": topic}) + "\n",
        encoding="utf-8",
    )

    dropped = sup.archive_gc()

    assert dropped == 0


def test_archive_gc_keeps_row_when_repo_root_is_missing(*, tmp_path):
    missing_repo = tmp_path / "missing"
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.store_path).write_text(
        json.dumps({"kind": "plan", "repo": str(missing_repo), "topic": "topic"}) + "\n",
        encoding="utf-8",
    )

    dropped = sup.archive_gc()

    assert dropped == 0
