"""CLI add refuses ordinary tracks without a defining plan directory."""

from __future__ import annotations

import contextlib
import io

import registry
import supervisor
from test_supervisor_builders import TEST_EPIC, isolate_store, make_plan

__all__: list[str] = []


def test_cli_add_refuses_ordinary_topic_without_plan_directory(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    before = store.read_bytes() if store.exists() else b""
    missing_plan = repo / "plan" / "missing-topic"

    with contextlib.redirect_stderr(io.StringIO()) as err:
        rc = supervisor.main(argv=["add", "--repo", str(repo), "--topic", "missing-topic"])

    assert rc == 1
    assert str(missing_plan) in err.getvalue()
    assert (store.read_bytes() if store.exists() else b"") == before


def test_cli_add_plan_directory_validation_keeps_allowed_controls(*, tmp_path, monkeypatch):
    repo, topic = make_plan(tmp_path=tmp_path)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert supervisor.main(argv=["add", "--repo", str(repo), "--topic", topic]) == 0
    assert len(registry.read_valid_mapping(store_path=store)) == 1

    assert (
        supervisor.main(
            argv=[
                "add",
                "--repo",
                str(repo),
                "--topic",
                "repo-foreman",
                "--epic",
                TEST_EPIC,
            ]
        )
        == 0
    )
    tracks = registry.read_valid_mapping(store_path=store)
    assert [type(track).__name__ for track in tracks] == ["PlanTrack", "ForemanSeat"]
