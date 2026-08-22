"""Release-runtime rollback tests for daemon self re-exec."""

from __future__ import annotations

import contextlib
import io as _io
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OVERSEER_ROOT = _REPO_ROOT / "overseer"
sys.path.insert(0, str(_OVERSEER_ROOT))

import supervisor  # noqa: E402
from test_supervisor_builders import make_supervisor  # noqa: E402
from test_supervisor_fakes import FakeTmux  # noqa: E402

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _release_row():
    return supervisor.RowView(
        topic="release", repo="/repo", tmux=None, status="idle", ctx=None, note=None
    )


def test_reexec_records_the_prior_runtime_before_adopting_a_release(*, tmp_path):
    """The new process needs a last-known-good executable if it dies before its first tick."""
    state_path = tmp_path / "runtime-state.json"
    current = tmp_path / "current" / "overseerd"
    target = tmp_path / "release-a" / "overseerd"
    current.parent.mkdir()
    target.parent.mkdir()
    current.write_text("#!/bin/sh\n", encoding="utf-8")
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    execs: list[tuple[str, list[str]]] = []
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        reexec_target=lambda: target,
        argv=lambda: [str(current), "--warn-percent", "40"],
        execv=lambda *, path, argv: execs.append((path, argv)),
        runtime_state_path=state_path,
    )

    supervisor.maybe_reexec(sup=sup, rows=[_release_row()])

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["pending"] == str(target)
    assert state["previous"] == str(current)
    assert state["rejected"] == []
    assert execs == [(str(target), [str(target), "--warn-percent", "40"])]


def test_runtime_that_dies_before_its_first_tick_rolls_back_and_is_rejected(*, tmp_path):
    """A just-adopted runtime that crashes before completing a tick re-execs the prior one."""
    state_path = tmp_path / "runtime-state.json"
    previous = tmp_path / "previous" / "overseerd"
    current = tmp_path / "release-a" / "overseerd"
    previous.parent.mkdir()
    current.parent.mkdir()
    previous.write_text("#!/bin/sh\n", encoding="utf-8")
    current.write_text("#!/bin/sh\n", encoding="utf-8")
    state_path.write_text(
        json.dumps({"pending": str(current), "previous": str(previous), "rejected": []}),
        encoding="utf-8",
    )
    execs: list[tuple[str, list[str]]] = []
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        argv=lambda: [str(current), "--warn-percent", "45"],
        execv=lambda *, path, argv: execs.append((path, argv)),
        runtime_state_path=state_path,
    )

    def boom(*, act):
        raise RuntimeError("startup crash")

    sup.tick = boom  # type: ignore[assignment]
    err = _io.StringIO()
    with contextlib.redirect_stderr(err), pytest.raises(RuntimeError, match="startup crash"):
        sup.run(once=True)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["pending"] is None
    assert state["previous"] == str(previous)
    assert state["last_good"] == str(previous)
    assert state["rejected"] == [str(current)]
    assert "rolling back release runtime" in err.getvalue()
    assert str(current) in err.getvalue()
    assert str(previous) in err.getvalue()
    assert execs == [(str(previous), [str(previous), "--warn-percent", "45"])]


def test_runtime_rollback_terminates_when_the_prior_runtime_is_absent(*, tmp_path):
    """Rollback is bounded: a missing prior runtime is reported and the crash propagates."""
    state_path = tmp_path / "runtime-state.json"
    previous = tmp_path / "missing" / "overseerd"
    current = tmp_path / "release-a" / "overseerd"
    current.parent.mkdir()
    current.write_text("#!/bin/sh\n", encoding="utf-8")
    state_path.write_text(
        json.dumps({"pending": str(current), "previous": str(previous), "rejected": []}),
        encoding="utf-8",
    )
    execs: list[tuple[str, list[str]]] = []
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        argv=lambda: [str(current)],
        execv=lambda *, path, argv: execs.append((path, argv)),
        runtime_state_path=state_path,
    )

    def boom(*, act):
        raise RuntimeError("startup crash")

    sup.tick = boom  # type: ignore[assignment]
    err = _io.StringIO()
    with contextlib.redirect_stderr(err), pytest.raises(RuntimeError, match="startup crash"):
        sup.run(once=True)

    assert execs == []
    assert "cannot roll back release runtime" in err.getvalue()
    assert str(previous) in err.getvalue()


def test_rejected_runtime_is_not_reattempted_but_a_different_release_is_adopted(*, tmp_path):
    """The negative filter must not brick future good releases."""
    state_path = tmp_path / "runtime-state.json"
    current = tmp_path / "current" / "overseerd"
    rejected = tmp_path / "release-a" / "overseerd"
    different = tmp_path / "release-b" / "overseerd"
    for path in (current, rejected, different):
        path.parent.mkdir()
        path.write_text("#!/bin/sh\n", encoding="utf-8")
    state_path.write_text(
        json.dumps({"pending": None, "previous": str(current), "rejected": [str(rejected)]}),
        encoding="utf-8",
    )
    offered = [rejected, different]
    execs: list[tuple[str, list[str]]] = []
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        reexec_target=lambda: offered.pop(0),
        argv=lambda: [str(current)],
        execv=lambda *, path, argv: execs.append((path, argv)),
        runtime_state_path=state_path,
    )

    supervisor.maybe_reexec(sup=sup, rows=[_release_row()])
    supervisor.maybe_reexec(sup=sup, rows=[_release_row()])

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["pending"] == str(different)
    assert state["previous"] == str(current)
    assert state["rejected"] == [str(rejected)]
    assert execs == [(str(different), [str(different)])]
