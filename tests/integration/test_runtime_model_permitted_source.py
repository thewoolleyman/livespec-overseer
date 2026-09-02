"""Runtime-model permitted-source tests for the launch-profile capture.

Two integration-tier scenario tests drive the real adoption capture path
(`sup.adopt_sessions()`) and back the `scenarios.md` headings for this behavior; the
remaining tests pin the transcript reader and the base-model preference rule directly.
All live in one file to keep the red-green-replay pair a single staged test file.
"""

from __future__ import annotations

import json
from pathlib import Path

import _claude_runtime_model as crm
import _supervisor_launch_profile_capture as capture
from test_supervisor_builders import (
    adopt_sup,
    idle_capture,
    make_plan,
    write_session,
)
from test_supervisor_fakes import FakeTmux


def _nul(*, argv: list[str]) -> bytes:
    return b"\0".join(part.encode() for part in argv) + b"\0"


def _jsonl_rows(*, store: Path) -> list[dict]:
    return [json.loads(line) for line in store.read_text().splitlines() if line.strip()]


def _reader(*, model: str | None):
    def read(*, pid: int) -> str | None:
        return model

    return read


# --- Integration-tier scenario capture tests (heading-coverage backed) -------------


def test_scenario_captures_a_mid_session_model_change_from_the_transcript(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    fake = FakeTmux()
    fake.panes[topic] = idle_capture(ctx=40)
    fake.pane_pids = {100: topic}
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={200: 100},
        starttimes={200: "pt"},
        watch_repos=[str(repo)],
        cmdline_of=lambda *, pid: _nul(argv=["claude", "--model", "claude-opus-4-8", "-n", topic])
        if pid == 200
        else None,
        runtime_model_of=lambda *, pid: "claude-fable-5-1" if pid == 200 else None,
    )

    adopted = sup.adopt_sessions()

    assert [track.topic for track in adopted] == [topic]
    profile = _jsonl_rows(store=tmp_path / "map.jsonl")[0]["model_profile"]
    assert profile["harness"] == "claude"
    assert profile["model"] == "claude-fable-5-1"


def test_scenario_a_same_base_transcript_model_retains_the_launch_token_variant(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    fake = FakeTmux()
    fake.panes[topic] = idle_capture(ctx=40)
    fake.pane_pids = {100: topic}
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={200: 100},
        starttimes={200: "pt"},
        watch_repos=[str(repo)],
        cmdline_of=lambda *, pid: _nul(
            argv=["claude", "--model", "claude-opus-4-8[1m]", "-n", topic]
        )
        if pid == 200
        else None,
        runtime_model_of=lambda *, pid: "claude-opus-4-8" if pid == 200 else None,
    )

    adopted = sup.adopt_sessions()

    assert [track.topic for track in adopted] == [topic]
    profile = _jsonl_rows(store=tmp_path / "map.jsonl")[0]["model_profile"]
    assert profile["model"] == "claude-opus-4-8[1m]"


# --- apply_runtime_model + the base-model preference rule ----------------------------


def _profile(*, model: str):
    return {"harness": "claude", "model": model, "wrapper": None}


def test_transcript_token_is_preferred_over_a_differing_base_launch_model():
    profile = capture.apply_runtime_model(
        profile=_profile(model="claude-opus-4-8"),
        harness="claude",
        pid=200,
        runtime_model_of=_reader(model="claude-fable-5-1"),
    )
    assert profile["model"] == "claude-fable-5-1"


def test_transcript_token_with_the_same_base_retains_the_launch_variant():
    profile = capture.apply_runtime_model(
        profile=_profile(model="claude-opus-4-8[1m]"),
        harness="claude",
        pid=200,
        runtime_model_of=_reader(model="claude-opus-4-8"),
    )
    assert profile["model"] == "claude-opus-4-8[1m]"


def test_an_absent_transcript_token_leaves_the_launch_model():
    profile = capture.apply_runtime_model(
        profile=_profile(model="claude-opus-4-8[1m]"),
        harness="claude",
        pid=200,
        runtime_model_of=_reader(model=None),
    )
    assert profile["model"] == "claude-opus-4-8[1m]"


def test_apply_runtime_model_is_a_no_op_for_a_non_claude_harness():
    profile = capture.apply_runtime_model(
        profile=_profile(model="gpt-x"),
        harness="codex",
        pid=200,
        runtime_model_of=_reader(model="claude-fable-5-1"),
    )
    assert profile["model"] == "gpt-x"


def test_apply_runtime_model_passes_a_launch_profile_problem_through_unchanged():
    problem = capture.LaunchProfileProblem(message="no model token")
    result = capture.apply_runtime_model(
        profile=problem,
        harness="claude",
        pid=200,
        runtime_model_of=_reader(model="claude-fable-5-1"),
    )
    assert result is problem


def test_preferred_model_supplies_the_runtime_token_when_the_launch_model_is_absent():
    assert capture._preferred_model(runtime="claude-fable-5-1", launch=None) == "claude-fable-5-1"


# --- latest_top_level_model (transcript parsing) -------------------------------------


def _assistant(*, model, sidechain=False):
    record: dict[str, object] = {"type": "assistant", "message": {"model": model}}
    if sidechain:
        record["isSidechain"] = True
    return json.dumps(record)


def test_latest_top_level_model_returns_the_last_main_thread_token():
    lines = [
        _assistant(model="claude-opus-4-8"),
        _assistant(model="claude-fable-5-1"),
    ]
    assert crm.latest_top_level_model(lines=lines) == "claude-fable-5-1"


def test_latest_top_level_model_ignores_sidechain_sub_agent_messages():
    lines = [
        _assistant(model="claude-opus-4-8"),
        _assistant(model="claude-fable-5-1", sidechain=True),
    ]
    assert crm.latest_top_level_model(lines=lines) == "claude-opus-4-8"


def test_latest_top_level_model_skips_a_synthetic_model_value():
    lines = [
        _assistant(model="claude-opus-4-8"),
        _assistant(model="<synthetic>"),
    ]
    assert crm.latest_top_level_model(lines=lines) == "claude-opus-4-8"


def test_latest_top_level_model_is_none_without_a_usable_token():
    lines = [
        "",
        "not json",
        json.dumps([1, 2, 3]),
        json.dumps({"type": "user", "message": {"model": "claude-opus-4-8"}}),
        json.dumps({"type": "assistant", "message": "not-a-dict"}),
        json.dumps({"type": "assistant", "message": {"model": ""}}),
        _assistant(model="<synthetic>"),
    ]
    assert crm.latest_top_level_model(lines=lines) is None


# --- read_runtime_model (path resolution + fail-soft) -------------------------------


def _write_session_json(*, sessions_dir: Path, pid: int, session_id, cwd) -> None:
    payload: dict[str, object] = {}
    if session_id is not None:
        payload["sessionId"] = session_id
    if cwd is not None:
        payload["cwd"] = cwd
    (sessions_dir / f"{pid}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_read_runtime_model_resolves_the_transcript_and_returns_the_latest_model(*, tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    projects_dir = tmp_path / "projects"
    cwd = "/data/projects/example"
    _write_session_json(sessions_dir=sessions_dir, pid=7, session_id="sid-1", cwd=cwd)
    transcript_dir = projects_dir / cwd.replace("/", "-")
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "sid-1.jsonl").write_text(
        "\n".join([_assistant(model="claude-opus-4-8"), _assistant(model="claude-fable-5-1")]),
        encoding="utf-8",
    )

    model = crm.read_runtime_model(pid=7, sessions_dir=sessions_dir, projects_dir=projects_dir)

    assert model == "claude-fable-5-1"


def test_read_runtime_model_is_none_when_the_session_file_is_absent(*, tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    assert crm.read_runtime_model(pid=7, sessions_dir=sessions_dir, projects_dir=tmp_path) is None


def test_read_runtime_model_is_none_on_unparseable_session_json(*, tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "7.json").write_text("{not json", encoding="utf-8")
    assert crm.read_runtime_model(pid=7, sessions_dir=sessions_dir, projects_dir=tmp_path) is None


def test_read_runtime_model_is_none_when_session_json_is_not_an_object(*, tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "7.json").write_text("[1, 2]", encoding="utf-8")
    assert crm.read_runtime_model(pid=7, sessions_dir=sessions_dir, projects_dir=tmp_path) is None


def test_read_runtime_model_is_none_without_a_session_id(*, tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    _write_session_json(sessions_dir=sessions_dir, pid=7, session_id=None, cwd="/x")
    assert crm.read_runtime_model(pid=7, sessions_dir=sessions_dir, projects_dir=tmp_path) is None


def test_read_runtime_model_is_none_without_a_cwd(*, tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    _write_session_json(sessions_dir=sessions_dir, pid=7, session_id="sid-1", cwd=None)
    assert crm.read_runtime_model(pid=7, sessions_dir=sessions_dir, projects_dir=tmp_path) is None


def test_read_runtime_model_is_none_when_the_transcript_file_is_absent(*, tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    _write_session_json(sessions_dir=sessions_dir, pid=7, session_id="sid-1", cwd="/x")
    assert crm.read_runtime_model(pid=7, sessions_dir=sessions_dir, projects_dir=tmp_path) is None


# --- production seam wiring ----------------------------------------------------------


def test_the_production_runtime_model_reader_fails_soft_for_an_unknown_pid():
    assert crm.runtime_model_of(pid=999_999_999) is None


def test_the_supervisor_default_runtime_model_seam_is_the_production_reader():
    import _supervisor_core

    default = _supervisor_core.Supervisor.__dataclass_fields__["runtime_model_of"].default
    assert default is crm.runtime_model_of


def test_default_projects_dir_is_under_the_claude_home():
    assert crm.default_projects_dir() == Path.home() / ".claude" / "projects"
