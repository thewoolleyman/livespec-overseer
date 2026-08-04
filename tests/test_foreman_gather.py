"""Tests for foreman_gather.py — deterministic Phase A composition."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_gather.py"

__all__: list[str] = []


def foreman_gather():
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_gather")


def foreman_gather_collect():
    _ = foreman_gather()
    return importlib.import_module("foreman_gather_collect")


def foreman_gather_sources():
    _ = foreman_gather()
    return importlib.import_module("foreman_gather_sources")


def write_json(*, path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(*, path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def test_composes_canonical_document_from_snapshot_attention_and_journal(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot_path = tmp_path / "status.json"
    attention_path = repo / "attention.json"
    journal_path = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal_path.parent.mkdir()
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "written_at": "2026-08-03T08:00:00Z",
            "rows": [
                {
                    "acked": False,
                    "ctx": 42,
                    "human_wait": False,
                    "note": "low context",
                    "progress_now": True,
                    "repo": str(repo),
                    "round_open": True,
                    "runtime": "codex",
                    "session_identity": "codex:abc",
                    "status": "warned",
                    "tmux": "alpha",
                    "topic": "plan-a",
                },
                {
                    "acked": False,
                    "ctx": None,
                    "human_wait": False,
                    "note": None,
                    "progress_now": False,
                    "repo": str(tmp_path / "other"),
                    "round_open": False,
                    "runtime": None,
                    "session_identity": "none:/other:plan-b",
                    "status": "unassigned",
                    "tmux": None,
                    "topic": "plan-b",
                },
            ],
        },
    )
    write_json(
        path=attention_path,
        payload={
            "schema_version": 1,
            "generated_at": "2026-08-03T08:01:00Z",
            "items": [{"id": "overseer-a", "kind": "impl_next", "title": "ship it"}],
        },
    )
    write_jsonl(
        path=journal_path,
        records=[
            {"at": "2026-08-03T07:59:00Z", "action": "impl:old"},
            {"at": "2026-08-03T08:02:00Z", "action": "impl:overseer-a"},
        ],
    )

    document = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=["/bin/cat", str(attention_path)],
        journal_path=journal_path,
        now=lambda: "2026-08-03T08:03:00Z",
        journal_limit=1,
    )

    assert document == {
        "schema_version": 1,
        "generated_at": "2026-08-03T08:03:00Z",
        "repo": str(repo),
        "sources": {
            "dispatch_journal": {
                "path": str(journal_path),
                "records_read": 1,
                "status": "ok",
            },
            "needs_attention": {"command": ["/bin/cat", str(attention_path)], "status": "ok"},
            "snapshot": {
                "freshness": {
                    "mtime": pytest.approx(snapshot_path.stat().st_mtime),
                    "tick_generation": 7,
                    "written_at": "2026-08-03T08:00:00Z",
                },
                "mode": "daemon-snapshot",
                "path": str(snapshot_path),
                "rows_total": 2,
                "rows_used": 1,
                "status": "ok",
            },
        },
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "rows": [
                {
                    "acked": False,
                    "ctx": 42,
                    "human_wait": False,
                    "note": "low context",
                    "progress_now": True,
                    "repo": str(repo),
                    "round_open": True,
                    "runtime": "codex",
                    "session_identity": "codex:abc",
                    "status": "warned",
                    "tmux": "alpha",
                    "topic": "plan-a",
                }
            ],
            "tick_generation": 7,
            "written_at": "2026-08-03T08:00:00Z",
        },
        "needs_attention": {
            "generated_at": "2026-08-03T08:01:00Z",
            "items": [{"id": "overseer-a", "kind": "impl_next", "title": "ship it"}],
            "schema_version": 1,
        },
        "dispatch_journal": [{"action": "impl:overseer-a", "at": "2026-08-03T08:02:00Z"}],
    }


def test_snapshot_fallback_is_marked_observation_only(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    fallback_path = tmp_path / "list.json"
    write_json(
        path=fallback_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "cli",
            "tick_generation": 1,
            "written_at": "2026-08-03T08:00:00Z",
            "rows": [],
        },
    )

    document = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing.json",
        list_json_command=["/bin/cat", str(fallback_path)],
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        now=lambda: "2026-08-03T08:03:00Z",
    )

    assert document["sources"]["snapshot"]["mode"] == "list-json-observation-only"
    assert document["snapshot"]["daemon_instance_id"] == "cli"


def test_embedded_and_fixture_attention_feed_needs_you_render(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot_path = tmp_path / "status.json"
    attention = {
        "schema_version": 1,
        "items": [{"id": "overseer-b", "kind": "approve", "tmux": "beta", "title": "approve me"}],
    }
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 1,
            "rows": [{"repo": str(repo), "topic": "beta", "tmux": "beta"}],
            "needs_attention": attention,
        },
    )

    embedded = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
    )

    assert embedded["needs_attention"] == attention
    assert "\nNEEDS YOU:\n  overseer-b | beta | approve | approve me\n" in (
        module.render_document(document=embedded)
    )

    (repo / "attention.json").write_text(json.dumps(attention), encoding="utf-8")
    fixture = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
    )
    assert fixture["needs_attention"] == attention


def test_unreachable_inputs_are_skipped_and_named(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()

    document = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing-status.json",
        list_json_command=None,
        needs_attention_command=["/definitely/missing/needs_attention.py", "--json"],
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        now=lambda: "2026-08-03T08:03:00Z",
    )

    assert document["sources"]["snapshot"] == {
        "path": str(tmp_path / "missing-status.json"),
        "reason": "snapshot unavailable and no list --json fallback configured",
        "status": "skipped",
    }
    assert document["sources"]["needs_attention"] == {
        "command": ["/definitely/missing/needs_attention.py", "--json"],
        "reason": "command not found",
        "status": "skipped",
    }
    assert document["sources"]["dispatch_journal"] == {
        "path": str(repo / "tmp" / "fabro-dispatch-journal.jsonl"),
        "reason": "file not found",
        "status": "skipped",
    }

    fallback_missing = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing-status.json",
        list_json_command=["/definitely/missing/overseer", "list", "--json"],
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
    )
    assert fallback_missing["sources"]["snapshot"] == {
        "command": ["/definitely/missing/overseer", "list", "--json"],
        "reason": "command not found",
        "status": "skipped",
    }


def test_malformed_primitive_output_is_rejected(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    primitive_path = tmp_path / "primitive.json"
    primitive_path.write_text("17\n", encoding="utf-8")

    with pytest.raises(module.ValidationError, match="needs_attention"):
        module.compose_document(
            repo=repo,
            snapshot_path=tmp_path / "missing.json",
            needs_attention_command=["/bin/cat", str(primitive_path)],
            journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        )


def test_render_is_stable_and_token_free(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    document = {
        "schema_version": 1,
        "generated_at": "2026-08-03T08:03:00Z",
        "repo": str(repo),
        "sources": {
            "snapshot": {"status": "ok", "mode": "daemon-snapshot", "rows_used": 1},
            "needs_attention": {"status": "skipped", "reason": "command not configured"},
            "dispatch_journal": {"status": "ok", "records_read": 1},
        },
        "snapshot": {
            "rows": [
                {
                    "topic": "plan-a",
                    "status": "warned",
                    "ctx": 42,
                    "human_wait": False,
                    "note": "low context",
                }
            ]
        },
        "needs_attention": None,
        "dispatch_journal": [{"action": "impl:overseer-a"}],
    }

    assert module.render_document(document=document) == (
        "foreman-gather 2026-08-03T08:03:00Z\n"
        f"repo: {repo}\n"
        "sources: snapshot=ok daemon-snapshot rows=1; needs_attention=skipped "
        "command not configured; dispatch_journal=ok records=1\n"
        "\n"
        "snapshot rows:\n"
        "  plan-a | warned | ctx=42 | human_wait=no | low context\n"
        "\n"
        "needs attention:\n"
        "  none\n"
        "\n"
        "dispatch journal:\n"
        "  impl:overseer-a\n"
    )


def test_render_lists_attention_items_and_empty_sections(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()

    assert module.render_document(
        document={
            "schema_version": 1,
            "generated_at": "2026-08-03T08:03:00Z",
            "repo": str(repo),
            "sources": {
                "snapshot": {"status": "ok", "mode": "daemon-snapshot", "rows_used": 0},
                "needs_attention": {"status": "ok"},
                "dispatch_journal": {"status": "skipped"},
            },
            "snapshot": {"rows": []},
            "needs_attention": {
                "items": [{"id": "overseer-b", "kind": "approve", "title": "approve me"}]
            },
            "dispatch_journal": [],
        }
    ) == (
        "foreman-gather 2026-08-03T08:03:00Z\n"
        f"repo: {repo}\n"
        "sources: snapshot=ok daemon-snapshot rows=0; needs_attention=ok; "
        "dispatch_journal=skipped records=None\n"
        "\n"
        "snapshot rows:\n"
        "  none\n"
        "\n"
        "needs attention:\n"
        "  overseer-b | approve | approve me\n"
        "\n"
        "dispatch journal:\n"
        "  none\n"
    )


def test_snapshot_validation_rejects_malformed_primitives(*, tmp_path):
    module = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(ValueError, match="primitive"):
        module.compose_document(
            repo=repo,
            snapshot_path=tmp_path / "missing_rows.json",
            list_json_command=["/bin/echo", '{"schema_version": 1, "tick_generation": 1}'],
            needs_attention_command=None,
        )
    with pytest.raises(TypeError, match="tick_generation"):
        module.compose_document(
            repo=repo,
            snapshot_path=tmp_path / "bad_generation.json",
            list_json_command=[
                "/bin/echo",
                '{"schema_version": 1, "tick_generation": true, "rows": []}',
            ],
            needs_attention_command=None,
        )
    with pytest.raises(ValueError, match="row"):
        module.compose_document(
            repo=repo,
            snapshot_path=tmp_path / "bad_row.json",
            list_json_command=[
                "/bin/echo",
                '{"schema_version": 1, "tick_generation": 1, "rows": [17]}',
            ],
            needs_attention_command=None,
        )


def test_snapshot_fallback_command_failures_are_skip_annotations(*, tmp_path):
    module = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()

    document = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing.json",
        list_json_command=["/bin/sh", "-c", "exit 7"],
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
    )

    assert document["sources"]["snapshot"] == {
        "command": ["/bin/sh", "-c", "exit 7"],
        "reason": "exit 7",
        "status": "skipped",
    }

    attention_failed = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing.json",
        needs_attention_command=["/bin/sh", "-c", "exit 8"],
        journal_path=str(repo / "tmp" / "fabro-dispatch-journal.jsonl"),
    )
    assert attention_failed["sources"]["needs_attention"] == {
        "command": ["/bin/sh", "-c", "exit 8"],
        "reason": "exit 8",
        "status": "skipped",
    }


def test_invalid_options_are_rejected(*, tmp_path):
    module = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(TypeError, match="now"):
        module.compose_document(repo=repo, needs_attention_command=None, now="soon")
    with pytest.raises(TypeError, match="journal_limit"):
        module.compose_document(repo=repo, needs_attention_command=None, journal_limit=True)
    with pytest.raises(TypeError, match="journal_path"):
        module.compose_document(repo=repo, needs_attention_command=None, journal_path=17)


def test_attention_without_items_renders_as_empty(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()

    rendered = module.render_document(
        document={
            "schema_version": 1,
            "generated_at": "2026-08-03T08:03:00Z",
            "repo": str(repo),
            "sources": {
                "snapshot": {"status": "ok", "mode": "daemon-snapshot", "rows_used": 0},
                "needs_attention": {"status": "ok"},
                "dispatch_journal": {"status": "ok", "records_read": 0},
            },
            "snapshot": {"rows": []},
            "needs_attention": {},
            "dispatch_journal": [],
        }
    )

    assert "\nneeds attention:\n  none\n" in rendered


def test_default_needs_attention_command_uses_repo_credential_wrapper(*, tmp_path):
    module = foreman_gather_sources()
    repo = tmp_path / "repo"
    repo.mkdir()
    script = repo / "needs_attention.py"
    script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    (repo / ".livespec.jsonc").write_text(
        '{\n  "credential_wrapper": ["/wrap", "--"],\n'
        '  "url": "https://example.test//kept"\n}\n',
        encoding="utf-8",
    )

    assert module.default_needs_attention_command(repo=repo) == [
        "/wrap",
        "--",
        sys.executable,
        str(script),
        "--json",
    ]
    assert module.strip_jsonc_line_comment(line='"//kept" // dropped') == '"//kept" '
    assert module.strip_jsonc_line_comment(line='"quote \\" // kept" // dropped') == (
        '"quote \\" // kept" '
    )


def test_default_needs_attention_command_handles_absent_or_bad_config(*, tmp_path):
    module = foreman_gather_sources()
    repo = tmp_path / "repo"
    repo.mkdir()

    assert module.default_needs_attention_command(repo=repo) is None
    script = repo / "needs_attention.py"
    script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    assert module.default_needs_attention_command(repo=repo) == [
        sys.executable,
        str(script),
        "--json",
    ]
    (repo / ".livespec.jsonc").write_text('{"credential_wrapper": "bad"}\n', encoding="utf-8")
    assert module.default_needs_attention_command(repo=repo) == [
        sys.executable,
        str(script),
        "--json",
    ]


def test_run_json_command_fail_soft_edges(*, monkeypatch):
    module = foreman_gather_sources()

    def boom(*args, **kwargs):
        del args, kwargs
        raise OSError

    monkeypatch.setattr(module.subprocess, "run", boom)
    assert module.run_json_command(command=["tool"], source_name="demo") == {
        "__skip_reason__": "OSError"
    }
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: module.subprocess.CompletedProcess(
            args=args, returncode=0, stdout="[]\n", stderr=""
        ),
    )
    with pytest.raises(ValueError, match="demo"):
        module.run_json_command(command=["tool"], source_name="demo")


def test_journal_reader_rejects_malformed_records_and_limits_to_zero(*, tmp_path):
    module = foreman_gather_sources()
    journal = tmp_path / "journal.jsonl"
    write_jsonl(path=journal, records=[{"action": "one"}])

    assert module.read_journal(path=journal, limit=0) == (
        [],
        {"path": str(journal), "records_read": 0, "status": "ok"},
    )
    journal.write_text("{}\nnot-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dispatch_journal"):
        module.read_journal(path=journal, limit=20)


def test_cli_emits_json_render_and_errors(*, tmp_path, capsys):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot = tmp_path / "status.json"
    write_json(
        path=snapshot,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 1,
            "written_at": "2026-08-03T08:00:00Z",
            "rows": [],
        },
    )

    assert module.default_list_json_command()[-2:] == ["list", "--json"]
    assert (
        module.main(
            argv=[
                "--repo",
                str(repo),
                "--snapshot-path",
                str(snapshot),
                "--no-list-json-fallback",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["schema_version"] == 1

    assert (
        module.main(
            argv=[
                "--repo",
                str(repo),
                "--snapshot-path",
                str(snapshot),
                "--no-list-json-fallback",
                "--render",
            ]
        )
        == 0
    )
    assert "snapshot rows:\n  none" in capsys.readouterr().out

    bad_snapshot = tmp_path / "bad.json"
    bad_snapshot.write_text("17\n", encoding="utf-8")
    assert (
        module.main(
            argv=[
                "--repo",
                str(repo),
                "--snapshot-path",
                str(bad_snapshot),
                "--no-list-json-fallback",
            ]
        )
        == 1
    )
    assert "foreman-gather:" in capsys.readouterr().err
