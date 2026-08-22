"""Regression tests for the foreman loop's picker-muted cadence."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import registry
import supervisor
from test_supervisor_builders import make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"


def foreman_runtime():
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_runtime")


def make_repo(*, tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    (repo / "plan" / "alpha").mkdir(parents=True)
    (repo / "tmp" / "overseer").mkdir(parents=True)
    return repo


def state_json(*, repo: Path) -> dict[str, object]:
    return json.loads(
        (repo / "tmp" / "overseer" / "foreman" / "runtime.json").read_text(encoding="utf-8")
    )


def make_tick_supervisor(*, tmp_path: Path, fake: FakeTmux, repo: Path, now: float):
    return make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        own_pane="%7",
        watch_repos=[str(repo)],
        now=lambda: now,
        status_writer=lambda *, path, body: None,
    )


def picker_capture(*, ctx: int = 80) -> str:
    return (
        "Choose how the foreman should proceed.\n"
        "❯ 1. Resume the loop\n"
        "  2. Leave it stopped\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def test_non_blocking_foreman_escalation_keeps_next_scheduled_tick(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    clock = {"now": 1000.0}
    calls: list[float] = []
    runtime = module.ForemanRuntime(
        repo=repo,
        now=lambda: clock["now"],
        llm_tick=lambda *, document: calls.append(clock["now"]) or False,
    )
    document = {
        "snapshot": {
            "rows": [
                {
                    "topic": "alpha",
                    "status": "foreman-escalated",
                    "picker_open": False,
                }
            ]
        }
    }

    first = runtime.step(document=document)
    clock["now"] += 3600.0
    second = runtime.step(document=document)

    assert hasattr(first, "blocking_prompt_open")
    assert first.blocking_prompt_open is False
    assert second.llm_tick is True
    assert second.loop_lapsed is False
    assert second.heartbeat_age_seconds == 3600.0
    assert second.blocking_prompt_open is False
    assert state_json(repo=repo)["next_llm_tick_at"] == 8200.0
    assert calls == [1000.0, 4600.0]


def test_foreman_runtime_reports_own_open_blocking_prompt_from_snapshot(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    runtime = module.ForemanRuntime(repo=repo, now=lambda: 1000.0)

    result = runtime.step(
        document={
            "snapshot": {
                "rows": [
                    {
                        "topic": "repo-foreman",
                        "status": "blocked:human",
                        "picker_open": True,
                    }
                ]
            }
        }
    )

    assert result.blocking_prompt_open is True


def test_foreman_blocking_prompt_renders_distinct_report_only_attention(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    foreman_topic = "repo-foreman"
    fake = FakeTmux()
    fake.serve(session=foreman_topic, repo=repo, capture=picker_capture())
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=fake, repo=repo, now=2000.0)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=foreman_topic, session=foreman_topic),
        store_path=sup.store_path,
        added_at="t",
    )

    rows = sup.tick(act=True)
    row = next(item for item in rows if item.status == "foreman-blocking-prompt")

    assert row.topic == "foreman"
    assert row.tmux == foreman_topic
    assert row.picker_open is True
    assert "suppresses scheduled ticks" in (row.note or "")
    assert supervisor.needs_attention(row=row) is True
    assert not fake.has(method="paste")
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")
    assert not fake.has(method="new")
