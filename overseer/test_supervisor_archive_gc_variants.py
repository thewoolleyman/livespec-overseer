"""Variant-dispatched archive-GC beside-tests."""

import json
from pathlib import Path

import registry
from test_supervisor_builders import TEST_EPIC, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_archive_gc_uses_variant_kind_for_raw_rows(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    (repo / "plan" / "live").mkdir(parents=True)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    rows = [
        {
            "kind": "foreman",
            "topic": "repo-foreman",
            "repo": str(repo),
            "tmux": "repo-foreman",
            "epic": registry.unresolved_plan_epic(topic="repo-foreman"),
        },
        {
            "kind": "supervisor",
            "topic": "live-supervisor",
            "repo": str(repo),
            "tmux": "live-supervisor",
            "epic": TEST_EPIC,
            "supervised_topic": "live",
        },
        {
            "kind": "supervisor",
            "topic": "malformed-supervisor",
            "repo": str(repo),
            "tmux": "malformed-supervisor",
            "epic": TEST_EPIC,
        },
        {
            "topic": "legacy-unknown",
            "repo": str(repo),
            "tmux": "legacy-unknown",
            "epic": TEST_EPIC,
        },
    ]
    store = sup.store_path
    assert store is not None
    Path(store).write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    dropped = sup.archive_gc()

    assert dropped == 0
    raw = [json.loads(line) for line in Path(store).read_text(encoding="utf-8").splitlines()]
    assert [row["topic"] for row in raw] == [
        "repo-foreman",
        "live-supervisor",
        "malformed-supervisor",
        "legacy-unknown",
    ]
