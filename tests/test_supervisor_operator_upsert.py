"""Regression tests for operator CLI mapping upserts."""

from __future__ import annotations

import json

import _registry_rows_io
import registry
import supervisor
from test_supervisor_builders import isolate_store

__all__: list[str] = []


def _rows(*, store) -> list[dict[str, object]]:
    return [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]


def test_cli_add_epic_preserves_unsupplied_durable_fields(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    registry.append_mapping(
        track=registry.Track(
            topic="alpha",
            repo=str(repo),
            tmux="old-session",
            resume="custom restart prompt",
            epic="overseer-old",
            ctx_threshold=45,
            pinned_session_id="pinned-session",
            observed_session_identity="identity-1",
            added_at="2026-08-19T07:42:57Z",
            model_profile={"harness": "claude", "model": "opus", "wrapper": None},
        ),
        store_path=store,
    )

    assert (
        supervisor.main(
            argv=["add", "--repo", str(repo), "--topic", "alpha", "--epic", "overseer-new"]
        )
        == 0
    )

    rows = _rows(store=store)
    assert len(rows) == 1
    assert rows[0]["epic"] == "overseer-new"
    assert rows[0]["tmux"] == "alpha"
    assert rows[0]["ctx_threshold"] == 45
    assert rows[0]["resume"] == "custom restart prompt"
    assert rows[0]["pinned_session_id"] == "pinned-session"
    assert rows[0]["observed_session_identity"] == "identity-1"
    assert rows[0]["model_profile"] == {"harness": "claude", "model": "opus", "wrapper": None}
    assert rows[0]["added_at"] == "2026-08-19T07:42:57Z"


def test_cli_add_ctx_threshold_is_explicitly_written_and_clearable(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    registry.append_mapping(
        track=registry.Track(
            topic="alpha",
            repo=str(repo),
            tmux="old-session",
            epic="overseer-old",
            ctx_threshold=45,
            added_at="2026-08-19T07:42:57Z",
        ),
        store_path=store,
    )

    assert (
        supervisor.main(
            argv=["add", "--repo", str(repo), "--topic", "alpha", "--ctx-threshold", "60"]
        )
        == 0
    )
    rows = _rows(store=store)
    assert rows[0]["ctx_threshold"] == 60
    assert rows[0]["epic"] == "overseer-old"
    assert rows[0]["added_at"] == "2026-08-19T07:42:57Z"

    assert (
        supervisor.main(
            argv=[
                "add",
                "--repo",
                str(repo),
                "--topic",
                "alpha",
                "--ctx-threshold",
                "inherit",
            ]
        )
        == 0
    )
    rows = _rows(store=store)
    assert "ctx_threshold" not in rows[0]
    assert rows[0]["epic"] == "overseer-old"
    assert rows[0]["added_at"] == "2026-08-19T07:42:57Z"


def test_mapping_upsert_preserves_fields_not_named_by_the_update_spec(*, tmp_path):
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        track=registry.Track(
            topic="alpha",
            repo="/repo",
            tmux="old-session",
            epic="overseer-old",
            ctx_threshold=45,
        ),
        store_path=store,
        added_at="2026-08-19T07:42:57Z",
    )

    registry.upsert_mapping(
        track=registry.Track(
            topic="alpha",
            repo="/repo",
            tmux="new-session",
            epic="overseer-new",
        ),
        store_path=store,
        added_at="2026-08-20T00:00:00Z",
        update_fields=frozenset({"epic"}),
    )

    rows = _rows(store=store)
    assert rows == [
        {
            "kind": "plan",
            "topic": "alpha",
            "repo": "/repo",
            "tmux": "old-session",
            "resume": None,
            "epic": "overseer-new",
            "pinned_session_id": None,
            "observed_session_identity": None,
            "added_at": "2026-08-19T07:42:57Z",
            "ctx_threshold": 45,
        }
    ]

    registry.upsert_mapping(
        track=registry.Track(topic="alpha", repo="/repo/", tmux="new-session"),
        store_path=store,
        update_fields=frozenset({"ctx_threshold"}),
    )

    rows = _rows(store=store)
    assert rows[0]["repo"] == "/repo/"
    assert rows[0]["tmux"] == "old-session"
    assert "ctx_threshold" not in rows[0]

    registry.upsert_mapping(
        track=registry.Track(topic="alpha", repo="/repo/", tmux="newer-session"),
        store_path=store,
        update_fields=frozenset({"ctx_threshold"}),
    )

    assert _rows(store=store)[0]["tmux"] == "old-session"


def test_cli_add_atomic_write_failure_keeps_existing_live_row(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    registry.append_mapping(
        track=registry.Track(
            topic="alpha",
            repo=str(repo),
            tmux="old-session",
            epic="overseer-old",
        ),
        store_path=store,
    )

    atomic_write_calls = 0

    def fail_atomic_write(*, path, body, raise_errors=False):
        nonlocal atomic_write_calls
        atomic_write_calls += 1
        del body
        assert path == store
        assert raise_errors is True
        raise OSError("disk full")

    monkeypatch.setattr(_registry_rows_io, "atomic_write", fail_atomic_write)

    assert (
        supervisor.main(
            argv=["add", "--repo", str(repo), "--topic", "alpha", "--epic", "overseer-new"]
        )
        == 0
    )

    assert atomic_write_calls == 1
    rows = _rows(store=store)
    assert len(rows) == 1
    assert rows[0]["topic"] == "alpha"
    assert rows[0]["repo"] == str(repo)
    assert rows[0]["tmux"] == "old-session"
    assert rows[0]["epic"] == "overseer-old"
