"""Integration-facing tests for the validated declaration command forms."""

from __future__ import annotations

import json
from pathlib import Path

import declare
import pytest
import registry
import signals

__all__: list[str] = []


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["winding-down"], "winding-down"),
        (["ready"], "ready"),
        (["blocked", "waiting", "for", "review"], "blocked: waiting for review"),
        (["done"], "done"),
        (["done", "shipped", "it"], "done: shipped it"),
    ],
)
def test_declaration_forms_write_a_value_the_daemon_accepts(*, tmp_path, argv, expected):
    repo = tmp_path / "repo"
    repo.mkdir()
    topic = "topic"

    code = declare.main(argv=[*argv, "--repo", str(repo), "--topic", topic])

    path = signals.state_path(repo=str(repo), topic=topic)
    assert code == 0
    assert path.read_text(encoding="utf-8").splitlines()[0] == expected
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert signals.valid_token(token=state.token)


@pytest.mark.parametrize(
    "argv",
    [
        ["blocked"],
        ["blocked", "two\nlines"],
        ["blocked", "bad\x00control"],
        ["blocked", "x" * 201],
        ["done", "two\nlines"],
        ["done", "bad\x00control"],
        ["done", "x" * 201],
    ],
)
def test_declaration_refuses_invalid_detail_without_touching_existing_state(
    *, tmp_path, capsys, argv
):
    repo = tmp_path / "repo"
    repo.mkdir()
    topic = "topic"
    path = signals.state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"ready\n")

    code = declare.main(argv=[*argv, "--repo", str(repo), "--topic", topic])

    assert code == 2
    assert (
        "winding-down, ready, blocked <reason>, done [summary], or clear" in capsys.readouterr().err
    )
    assert path.read_bytes() == b"ready\n"


@pytest.mark.parametrize(
    "value",
    [
        "winding-down\n",
        "ready\n",
        "blocked: waiting\n",
        "done: shipped\n",
        "idle-with-context-left\n",
    ],
)
def test_clear_removes_only_session_or_idle_marker_values(*, tmp_path, value):
    repo = tmp_path / "repo"
    repo.mkdir()
    topic = "topic"
    path = signals.state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True)
    path.write_text(value, encoding="utf-8")

    code = declare.main(argv=["clear", "--repo", str(repo), "--topic", topic])

    assert code == 0
    assert not path.exists()


@pytest.mark.parametrize("value", ["ready-expired\n", "restarted\n", "blocked-voided\n"])
def test_clear_retains_other_daemon_values_and_absent_state_succeeds(*, tmp_path, capsys, value):
    repo = tmp_path / "repo"
    repo.mkdir()
    topic = "topic"
    path = signals.state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True)
    path.write_text(value, encoding="utf-8")

    code = declare.main(argv=["clear", "--repo", str(repo), "--topic", topic])

    assert code == 0
    assert path.read_text(encoding="utf-8") == value
    assert "left in place" in capsys.readouterr().out
    path.unlink()
    assert declare.main(argv=["clear", "--repo", str(repo), "--topic", topic]) == 0


def test_clear_does_not_delete_a_state_rewritten_between_checks(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    topic = "topic"
    path = signals.state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True)
    path.write_text("ready\n", encoding="utf-8")
    original_read_text = Path.read_text
    reads = 0

    def rewrite_before_second_read(*, self, encoding=None, errors=None):
        nonlocal reads
        if self == path:
            reads += 1
            if reads == 2:
                self.write_text("blocked: changed\n", encoding="utf-8")
        return original_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", rewrite_before_second_read)

    code = declare.main(argv=["clear", "--repo", str(repo), "--topic", topic])

    assert code == 0
    assert path.read_text(encoding="utf-8") == "blocked: changed\n"


def test_supervisor_ready_uses_the_pair_entity_round_and_mapping(*, tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    worker = "topic"
    entity = "topic-supervisor"
    store = tmp_path / "mapping.jsonl"
    stamps = tmp_path / "rounds.json"
    monkeypatch.setattr(registry, "DEFAULT_STORE_PATH", store)
    monkeypatch.setattr(registry, "DEFAULT_STAMP_PATH", stamps)
    registry.append_mapping(
        track=registry.Track(
            repo=str(repo), topic=worker, tmux="worker", added_at="2026-08-16T23:45:00Z"
        ),
        store_path=store,
    )
    key = f"{registry.norm(repo=repo)}\t"
    stamps.write_text(
        json.dumps(
            {
                f"{key}{worker}": {"at": "invalid", "session_identity": "worker"},
                f"{key}{entity}": {"at": 1.0, "session_identity": "supervisor"},
            }
        ),
        encoding="utf-8",
    )

    code = declare.main(argv=["ready", "--repo", str(repo), "--topic", entity])

    assert code == 0
    assert signals.read_state(repo=str(repo), topic=entity).token == signals.STATE_READY
    assert declare.READY_CONTRACT in capsys.readouterr().out
