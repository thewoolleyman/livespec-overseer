"""Edge coverage for release-lane foreman gather sources."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"

__all__: list[str] = []


def overseer_module(*, name: str):
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module(name)


def test_collect_supervisor_handoff_compatibility_wrapper_covers_all_states(
    *, tmp_path, monkeypatch
):
    collect = overseer_module(name="foreman_gather_collect")
    repo = tmp_path / "repo"
    (repo / "plan" / "present").mkdir(parents=True)
    (repo / "plan" / "present" / "supervisor-handoff.md").write_text("ok\n", encoding="utf-8")
    (repo / "plan" / "missing").mkdir(parents=True)

    monkeypatch.setattr(
        collect.signals,
        "topic_reserved_for_supervisor",
        lambda *, topic: topic == "reserved",
    )

    assert collect.supervisor_handoff_state(repo=repo, topic="outside") == "not-plan"
    assert collect.supervisor_handoff_state(repo=repo, topic="present") == "present"
    assert collect.supervisor_handoff_state(repo=repo, topic="missing") == "missing"
    assert collect.supervisor_handoff_state(repo=repo, topic="reserved") == "supervisor-topic"


def test_release_lane_config_defaults_and_malformed_supplied_runs(*, tmp_path):
    module = overseer_module(name="foreman_gather_release_lane")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {"release_lane_watch": {"enabled": True}}}),
        encoding="utf-8",
    )

    item, source = module.release_lane_payload(
        repo=repo,
        options={"release_lane_runs": [{"conclusion": "success", "created_at": "2026"}]},
        measured_at="2026-08-20T08:03:00Z",
    )

    assert item is None
    assert source["workflow"] == "release-tag"
    assert (repo / "tmp/overseer/release-lane-watch.json").is_file()
    assert module.release_lane_cache_path(
        repo=repo,
        config={},
        options={"release_lane_cache_path": "custom-cache.json"},
    ) == Path("custom-cache.json")
    assert module.normalized_runs(value={}) is None
    assert module.normalized_runs(value=[17]) is None


def test_release_lane_unknown_without_cache_and_unreadable_cache(*, tmp_path, monkeypatch):
    module = overseer_module(name="foreman_gather_release_lane")
    missing_cache = tmp_path / "missing.json"
    directory_cache = tmp_path / "cache-dir"
    directory_cache.mkdir()

    assert module.unknown_source(workflow="release-tag", cache_path=missing_cache) == {
        "reason": "forge unreachable or unavailable",
        "status": "unknown",
        "workflow": "release-tag",
    }
    assert module.unknown_item(label="release-tag", cache_path=missing_cache)["title"].endswith(
        "no successful measurement cached"
    )
    assert module.last_successful_measurement(path=directory_cache) is None

    def fail_write_text(*args, **kwargs):
        del args, kwargs
        raise OSError

    monkeypatch.setattr(Path, "write_text", fail_write_text)
    module.write_cache(
        path=tmp_path / "will-not-write.json",
        workflow="release-tag",
        measured_at="2026-08-20T08:03:00Z",
        state={"healthy": True},
    )


def test_release_lane_default_fetcher_is_used_when_no_history_is_supplied(*, tmp_path, monkeypatch):
    module = overseer_module(name="foreman_gather_release_lane")
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(
        module,
        "fetch_release_lane_runs",
        lambda *, repo, workflow: [{"conclusion": "success", "created_at": workflow}],
    )

    assert module.release_lane_runs(repo=repo, workflow="release-tag.yml", options={}) == [
        {"conclusion": "success", "created_at": "release-tag.yml"}
    ]


def test_release_lane_source_line_renders_unknown_reason():
    render = overseer_module(name="foreman_gather_render")

    assert "release_lane=unknown release-tag forge unreachable" in render.source_line(
        document={
            "sources": {
                "snapshot": {"status": "ok", "mode": "daemon-snapshot", "rows_used": 0},
                "needs_attention": {"status": "ok"},
                "dispatch_journal": {"status": "ok", "records_read": 0},
                "release_lane": {
                    "reason": "forge unreachable",
                    "status": "unknown",
                    "workflow": "release-tag",
                },
            }
        }
    )


def test_snapshot_supervisor_handoff_unknown_topic(*, tmp_path):
    snapshot = overseer_module(name="foreman_gather_snapshot")

    assert snapshot.supervisor_handoff_state(repo=tmp_path, topic=None) == "unknown"


def test_release_lane_source_fetches_workflow_scoped_runs(*, tmp_path, monkeypatch):
    sources = overseer_module(name="foreman_gather_sources")
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    commands: list[list[str]] = []

    def run_json_command(*, command, source_name):
        commands.append(command)
        assert source_name == "release_lane"
        return {
            "workflow_runs": [
                {"conclusion": "success", "created_at": "2026-08-20T08:19:21Z"},
                {"conclusion": None, "created_at": None},
                17,
            ]
        }

    monkeypatch.setattr(sources, "run_json_command", run_json_command)

    assert sources.fetch_release_lane_runs(repo=repo, workflow="release-tag.yml") == [
        {"conclusion": "success", "created_at": "2026-08-20T08:19:21Z"},
        {"conclusion": "", "created_at": ""},
    ]
    assert commands == [
        [
            "gh",
            "api",
            "repos/owner/repo/actions/workflows/release-tag.yml/runs?per_page=100&page=1",
        ]
    ]


def test_release_lane_source_paginates_until_short_page_or_limit(*, tmp_path, monkeypatch):
    sources = overseer_module(name="foreman_gather_sources")
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    full_page = [
        {"conclusion": "success", "created_at": f"2026-08-20T00:{index:02}:00Z"}
        for index in range(100)
    ]
    short_page = [{"conclusion": "failure", "created_at": "2026-08-20T02:00:00Z"}]
    pages = [full_page, short_page]

    def short_second_page(*, command, source_name):
        del source_name
        endpoint = command[2]
        page = int(endpoint.rsplit("page=", maxsplit=1)[1])
        return {"workflow_runs": pages[page - 1]}

    monkeypatch.setattr(sources, "run_json_command", short_second_page)

    assert len(sources.fetch_release_lane_runs(repo=repo, workflow="release-tag.yml")) == 101

    def always_full_page(*, command, source_name):
        del command, source_name
        return {"workflow_runs": full_page}

    monkeypatch.setattr(sources, "run_json_command", always_full_page)

    assert len(sources.fetch_release_lane_runs(repo=repo, workflow="release-tag.yml")) == 400


def test_release_lane_source_fetch_fail_soft_edges(*, tmp_path, monkeypatch):
    sources = overseer_module(name="foreman_gather_sources")
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    assert sources.fetch_release_lane_runs(repo=repo, workflow="release-tag.yml") is None

    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setattr(sources, "run_json_command", lambda *, command, source_name: None)
    assert sources.fetch_release_lane_runs(repo=repo, workflow="release-tag.yml") is None

    monkeypatch.setattr(
        sources,
        "run_json_command",
        lambda *, command, source_name: {"__skip_reason__": "exit 1"},
    )
    assert sources.fetch_release_lane_runs(repo=repo, workflow="release-tag.yml") is None

    monkeypatch.setattr(
        sources,
        "run_json_command",
        lambda *, command, source_name: {"not_runs": []},
    )
    assert sources.fetch_release_lane_runs(repo=repo, workflow="release-tag.yml") is None


def test_repo_slug_falls_back_to_git_remote(*, tmp_path, monkeypatch):
    sources = overseer_module(name="foreman_gather_sources")
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    monkeypatch.setattr(
        sources.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="git@github.com:owner/repo.git\n",
            stderr="",
        ),
    )
    assert sources.repo_slug(repo=repo) == "owner/repo"

    monkeypatch.setattr(
        sources.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr="missing",
        ),
    )
    assert sources.repo_slug(repo=repo) is None
