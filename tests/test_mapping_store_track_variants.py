"""Typed track variants at the mapping-store boundary."""

import contextlib
import inspect
import io
import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
import registry
import signals
from test_supervisor_builders import declare, idle_capture, make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
UV = shutil.which("uv")
assert UV is not None


def _run_pyright_snippet(*, tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    snippet = tmp_path / "snippet.py"
    snippet.write_text(textwrap.dedent(body), encoding="utf-8")
    config = tmp_path / "pyrightconfig.json"
    config.write_text(
        json.dumps(
            {
                "include": [snippet.name],
                "extraPaths": [str(ROOT / "overseer")],
                "pythonVersion": "3.10",
                "typeCheckingMode": "strict",
            }
        ),
        encoding="utf-8",
    )
    return subprocess.run(  # noqa: S603
        [UV, "run", "pyright", "-p", str(config)],
        cwd=tmp_path,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _assert_pyright_passes(*, completed: subprocess.CompletedProcess[str]) -> None:
    assert completed.returncode == 0, completed.stdout


def _assert_pyright_fails_with(*, completed: subprocess.CompletedProcess[str], needle: str) -> None:
    assert completed.returncode != 0, completed.stdout
    assert needle in completed.stdout


def test_mapping_writes_and_reads_the_variant_discriminator(*, tmp_path):
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="alpha",
            repo="/repo",
            tmux="alpha",
            epic="overseer-alpha",
        ),
        store_path=store,
    )

    row = json.loads(store.read_text(encoding="utf-8"))
    assert row["kind"] == "plan"
    [track] = registry.read_valid_mapping(store_path=store)
    assert type(track).__name__ == "PlanTrack"
    assert track.kind == "plan"
    assert track.epic == "overseer-alpha"


def test_the_four_track_variants_are_distinct_records():
    variants = [
        registry.UnassignedPlan.make(repo="/repo", topic="alpha"),
        registry.PlanTrack(topic="alpha", repo="/repo", tmux="alpha", epic="overseer-alpha"),
        registry.SupervisorSeat(
            topic="alpha-supervisor",
            repo="/repo",
            tmux="alpha-supervisor",
            epic="overseer-alpha",
            supervised_topic="alpha",
        ),
        registry.ForemanSeat(
            topic="repo-foreman",
            repo="/repo",
            tmux="repo-foreman",
            epic="overseer-foreman",
        ),
    ]

    assert [type(variant).__name__ for variant in variants] == [
        "UnassignedPlan",
        "PlanTrack",
        "SupervisorSeat",
        "ForemanSeat",
    ]
    assert [variant.kind for variant in variants] == [
        "unassigned_plan",
        "plan",
        "supervisor",
        "foreman",
    ]
    assert "tmux" not in inspect.signature(registry.UnassignedPlan).parameters
    assert "epic" not in inspect.signature(registry.UnassignedPlan).parameters
    assert (
        inspect.signature(registry.PlanTrack).parameters["epic"].default is inspect.Parameter.empty
    )
    assert (
        inspect.signature(registry.SupervisorSeat).parameters["epic"].default
        is inspect.Parameter.empty
    )
    assert (
        inspect.signature(registry.ForemanSeat).parameters["epic"].default
        is inspect.Parameter.empty
    )


def test_foreman_seat_explicit_empty_epic_fails_at_construction():
    with pytest.raises(ValueError, match="foreman.*epic"):
        registry.ForemanSeat(topic="repo-foreman", repo="/repo", tmux="repo-foreman", epic="")


def test_foreman_seat_epic_and_plan_anchor_are_static_requirements(*, tmp_path):
    omitted_epic = _run_pyright_snippet(
        tmp_path=tmp_path,
        body="""
            import registry

            registry.ForemanSeat(topic="repo-foreman", repo="/repo", tmux="repo-foreman")
        """,
    )
    _assert_pyright_fails_with(
        completed=omitted_epic,
        needle='Argument missing for parameter "epic"',
    )

    explicit_epic = _run_pyright_snippet(
        tmp_path=tmp_path,
        body="""
            import registry

            registry.ForemanSeat(
                topic="repo-foreman",
                repo="/repo",
                tmux="repo-foreman",
                epic="overseer-foreman",
            )
        """,
    )
    _assert_pyright_passes(completed=explicit_epic)

    foreman_as_plan_anchor_topic = _run_pyright_snippet(
        tmp_path=tmp_path,
        body="""
            import registry

            track = registry.ForemanSeat(
                topic="repo-foreman",
                repo="/repo",
                tmux="repo-foreman",
                epic="overseer-foreman",
            )
            registry.epic_from_plan_anchor(repo="/repo", topic=track)
        """,
    )
    _assert_pyright_fails_with(
        completed=foreman_as_plan_anchor_topic,
        needle='Argument of type "ForemanSeat" cannot be assigned to parameter "topic"',
    )

    plan_anchor_topic = _run_pyright_snippet(
        tmp_path=tmp_path,
        body="""
            import registry

            track = registry.ForemanSeat(
                topic="repo-foreman",
                repo="/repo",
                tmux="repo-foreman",
                epic="overseer-foreman",
            )
            registry.epic_from_plan_anchor(repo="/repo", topic=track.topic)
        """,
    )
    _assert_pyright_passes(completed=plan_anchor_topic)

    foreman_rederive = _run_pyright_snippet(
        tmp_path=tmp_path,
        body="""
            from typing import cast

            import _supervisor_restart
            import registry
            from _supervisor_core import Supervisor

            sup = cast(Supervisor, object())
            track = registry.ForemanSeat(
                topic="repo-foreman",
                repo="/repo",
                tmux="repo-foreman",
                epic="overseer-foreman",
            )
            _supervisor_restart.rederive_epic_if_stale(
                sup=sup,
                track=track,
                act=True,
            )
        """,
    )
    _assert_pyright_fails_with(
        completed=foreman_rederive,
        needle='Argument of type "ForemanSeat" cannot be assigned to parameter "track"',
    )


def test_legacy_foreman_row_with_null_or_absent_epic_loads_with_unresolved_sentinel(*, tmp_path):
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps(
            {
                "kind": "foreman",
                "topic": "repo-foreman",
                "repo": "/repo",
                "tmux": "repo-foreman",
                "epic": None,
            }
        )
        + "\n"
        + json.dumps(
            {
                "kind": "foreman",
                "topic": "other-foreman",
                "repo": "/repo",
                "tmux": "other-foreman",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    entries = registry.read_mapping(store_path=store)
    tracks = registry.read_valid_mapping(store_path=store)

    assert [type(entry).__name__ for entry in entries] == ["MappingValid", "MappingValid"]
    assert [(track.topic, track.epic) for track in tracks] == [
        ("repo-foreman", registry.unresolved_plan_epic(topic="repo-foreman")),
        ("other-foreman", registry.unresolved_plan_epic(topic="other-foreman")),
    ]


def test_foreman_ready_without_resolved_epic_never_queries_plan_anchor(*, tmp_path, monkeypatch):
    repo, _topic = make_plan(tmp_path=tmp_path)
    topic = "repo-foreman"
    session = topic
    epic_lookups: list[tuple[str, str]] = []

    def fake_epic_lookup(*, repo, topic):
        epic_lookups.append((str(repo), topic))

    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.epic_lookup = fake_epic_lookup
    monkeypatch.setattr(
        registry,
        "epic_from_plan_anchor",
        lambda *, repo, topic: pytest.fail("test escaped to the real registry epic lookup"),
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    track = registry.ForemanSeat(
        topic=topic,
        repo=str(repo),
        tmux=session,
        epic=registry.unresolved_plan_epic(topic=topic),
    )

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "blocked:human"
    assert view.note == "ready cannot respawn: no foreman epic recorded"
    assert "ready cannot respawn: no foreman epic recorded" in err.getvalue()
    assert epic_lookups == []
    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic) is not None


def test_foreman_row_with_non_string_epic_stays_invalid(*, tmp_path):
    store = tmp_path / "map.jsonl"
    raw = json.dumps(
        {
            "kind": "foreman",
            "topic": "repo-foreman",
            "repo": "/repo",
            "tmux": "repo-foreman",
            "epic": 42,
        }
    )
    store.write_text(raw + "\n", encoding="utf-8")

    [entry] = registry.read_mapping(store_path=store)

    assert type(entry).__name__ == "MappingInvalid"
    assert entry.reason == "missing_epic"
    assert entry.raw_line == raw


def test_raw_row_write_surface_is_not_public_registry_api():
    assert not hasattr(registry, "write_rows")
    assert not hasattr(registry, "read_rows")
    assert "_track_to_row" not in registry.__all__
