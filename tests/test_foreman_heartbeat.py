"""Repo-level foreman heartbeat attention regressions."""

import contextlib
import importlib
import io
import json
from pathlib import Path

import pytest
import supervisor
from test_supervisor_builders import make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def foreman_module():
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "_supervisor_foreman.py"
    assert module_path.is_file()
    return importlib.import_module("_supervisor_foreman")


def heartbeat_path(*, repo: Path) -> Path:
    return repo / "tmp" / "overseer" / "foreman" / "heartbeat.json"


def write_heartbeat(
    *,
    repo: Path,
    written_at: object = "1970-01-01T00:00:00Z",
    pid: object = 1234,
    tick_generation: object = 7,
    tick_interval_seconds: object = 600,
) -> Path:
    path = heartbeat_path(repo=repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "written_at": written_at,
                "pid": pid,
                "tick_generation": tick_generation,
                "tick_interval_seconds": tick_interval_seconds,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def make_tick_supervisor(*, tmp_path, fake, repo, now):
    return make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        now=lambda: now,
        status_writer=lambda *, path, body: None,
    )


@pytest.mark.parametrize(
    ("now", "interval", "expected"),
    [
        (1800.0, 600, False),
        (1800.1, 600, True),
        (7200.0, 3600, False),
        (7200.1, 3600, True),
    ],
)
def test_foreman_heartbeat_stale_bounds(*, tmp_path, now, interval, expected):
    module = foreman_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    heartbeat = write_heartbeat(repo=repo, tick_interval_seconds=interval)

    row = module.foreman_row(repo=str(repo), now=lambda: now)

    assert (row is not None) is expected
    if row is not None:
        assert row.status == "foreman-heartbeat-stale"
        assert row.topic == "foreman"
        assert row.tmux == "repo-foreman"
        assert f"interval {interval}s" in (row.note or "")
        assert heartbeat.is_file()


@pytest.mark.parametrize(
    "payload",
    [
        "{",
        json.dumps({"pid": 1234, "tick_generation": 1, "tick_interval_seconds": 600}),
        json.dumps({"written_at": "not a timestamp", "pid": 1234, "tick_generation": 1}),
        json.dumps([]),
        json.dumps(42),
        json.dumps(
            {
                "written_at": 12345,
                "pid": 1234,
                "tick_generation": 1,
                "tick_interval_seconds": 600,
            }
        ),
        json.dumps(
            {
                "written_at": "1970-01-01T00:00:00Z",
                "pid": 1234,
                "tick_generation": 1,
                "tick_interval_seconds": [600],
            }
        ),
        json.dumps(
            {
                "written_at": "1970-01-01T00:00:00Z",
                "pid": True,
                "tick_generation": 1,
                "tick_interval_seconds": 600,
            }
        ),
        json.dumps(
            {
                "written_at": "1970-01-01T00:00:00Z",
                "pid": 1234,
                "tick_generation": 1,
                "tick_interval_seconds": -1,
            }
        ),
    ],
)
def test_foreman_heartbeat_malformed_or_wrong_shape_is_absent(*, tmp_path, payload):
    module = foreman_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    path = heartbeat_path(repo=repo)
    path.parent.mkdir(parents=True)
    path.write_text(payload, encoding="utf-8")

    assert module.read_heartbeat(repo=str(repo)) is None
    assert module.foreman_row(repo=str(repo), now=lambda: 4000.0) is None


def test_foreman_heartbeat_accepts_naive_timestamp_and_fractional_interval(*, tmp_path):
    module = foreman_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    write_heartbeat(repo=repo, written_at="1970-01-01T00:00:00", tick_interval_seconds=1.5)

    row = module.foreman_row(repo=str(repo), now=lambda: 1800.1)

    assert row is not None
    assert "interval 1.5s" in (row.note or "")


def test_absent_foreman_heartbeat_is_silent(*, tmp_path):
    _module = foreman_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=FakeTmux(), repo=repo, now=4000.0)

    rows = sup.tick(act=True)
    output = sup.out.getvalue()

    assert all(row.topic != "foreman" for row in rows)
    assert "foreman" not in output
    assert "NEEDS YOU: nothing" in output


def test_stale_foreman_heartbeat_renders_attention_but_authorizes_no_act(*, tmp_path):
    _module = foreman_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    write_heartbeat(repo=repo, tick_interval_seconds=600)
    fake = FakeTmux()
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=fake, repo=repo, now=1801.0)

    rows = sup.tick(act=True)
    output = sup.out.getvalue()

    assert any(row.topic == "foreman" and supervisor.needs_attention(row=row) for row in rows)
    assert "NEEDS YOU (1):" in output
    assert "topic: foreman | tmux: repo-foreman | repo: repo" in output
    assert "foreman-heartbeat-stale" in output
    assert not fake.has(method="paste")
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")
    assert not fake.has(method="new")


def test_stale_foreman_heartbeat_read_only_tick_does_not_alert(*, tmp_path):
    _module = foreman_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    write_heartbeat(repo=repo, tick_interval_seconds=600)
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=FakeTmux(), repo=repo, now=1801.0)

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rows = sup.tick(act=False)

    assert any(row.topic == "foreman" for row in rows)
    assert "overseer[SURFACE]" not in err.getvalue()


def test_stale_foreman_heartbeat_alert_is_edge_triggered_and_rearmed(*, tmp_path):
    _module = foreman_module()
    repo, _topic = make_plan(tmp_path=tmp_path)
    write_heartbeat(repo=repo, tick_interval_seconds=600)
    sup = make_tick_supervisor(tmp_path=tmp_path, fake=FakeTmux(), repo=repo, now=1801.0)

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        for _ in range(3):
            _ = sup.tick(act=True)
        write_heartbeat(repo=repo, written_at="1970-01-01T00:30:00Z", tick_interval_seconds=600)
        _ = sup.tick(act=True)
        write_heartbeat(repo=repo, tick_interval_seconds=600)
        _ = sup.tick(act=True)

    surfaced = [line for line in err.getvalue().splitlines() if "overseer[SURFACE]" in line]
    assert len(surfaced) == 2
    assert all("foreman heartbeat stale" in line for line in surfaced)
