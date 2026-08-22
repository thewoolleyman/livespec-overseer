"""Defensive edge coverage for release-runtime rollback state."""

from __future__ import annotations

import contextlib
import io as _io
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OVERSEER_ROOT = _REPO_ROOT / "overseer"
if str(_OVERSEER_ROOT) not in sys.path:
    sys.path.insert(0, str(_OVERSEER_ROOT))

from test_supervisor_builders import make_supervisor  # noqa: E402
from test_supervisor_fakes import FakeTmux  # noqa: E402

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_successful_first_tick_clears_pending_adoption(*, tmp_path):
    state_path = tmp_path / "runtime-state.json"
    current = tmp_path / "release-a" / "overseerd"
    current.parent.mkdir()
    current.write_text("#!/bin/sh\n", encoding="utf-8")
    state_path.write_text(
        json.dumps({"pending": str(current), "previous": "/old", "rejected": [""]}),
        encoding="utf-8",
    )
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        argv=lambda: [str(current)],
        runtime_state_path=state_path,
    )
    sup.tick = lambda *, act: []  # type: ignore[assignment]

    sup.run(once=True)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["pending"] is None
    assert state["previous"] == str(current)
    assert state["last_good"] == str(current)
    assert state["rejected"] == []


def test_malformed_state_shape_reads_as_no_rejections(*, tmp_path):
    state_path = tmp_path / "runtime-state.json"
    state_path.write_text("[]", encoding="utf-8")
    target = tmp_path / "release-a" / "overseerd"
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), runtime_state_path=state_path)

    assert sup.runtime_state_path == state_path
    assert target not in []
    import _supervisor_runtime_rollback

    assert _supervisor_runtime_rollback.is_rejected(sup=sup, target=target) is False


def test_malformed_rejected_field_reads_as_no_rejections(*, tmp_path):
    state_path = tmp_path / "runtime-state.json"
    state_path.write_text(
        json.dumps({"pending": None, "previous": None, "rejected": "not-a-list"}),
        encoding="utf-8",
    )
    target = tmp_path / "release-a" / "overseerd"
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), runtime_state_path=state_path)
    import _supervisor_runtime_rollback

    assert _supervisor_runtime_rollback.is_rejected(sup=sup, target=target) is False


def test_runtime_rollback_reports_absent_prior_value(*, tmp_path):
    state_path = tmp_path / "runtime-state.json"
    current = tmp_path / "release-a" / "overseerd"
    current.parent.mkdir()
    current.write_text("#!/bin/sh\n", encoding="utf-8")
    state_path.write_text(
        json.dumps({"pending": str(current), "previous": None, "rejected": []}),
        encoding="utf-8",
    )
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        argv=lambda: [str(current)],
        runtime_state_path=state_path,
    )

    def boom(*, act):
        raise RuntimeError("startup crash")

    sup.tick = boom  # type: ignore[assignment]
    err = _io.StringIO()
    with contextlib.redirect_stderr(err), pytest.raises(RuntimeError, match="startup crash"):
        sup.run(once=True)

    assert "prior runtime <absent> is not executable" in err.getvalue()


def test_repeated_runtime_rollback_does_not_duplicate_rejection(*, tmp_path):
    state_path = tmp_path / "runtime-state.json"
    current = tmp_path / "release-a" / "overseerd"
    current.parent.mkdir()
    current.write_text("#!/bin/sh\n", encoding="utf-8")
    state_path.write_text(
        json.dumps({"pending": str(current), "previous": None, "rejected": [str(current)]}),
        encoding="utf-8",
    )
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        argv=lambda: [str(current)],
        runtime_state_path=state_path,
    )

    def boom(*, act):
        raise RuntimeError("startup crash")

    sup.tick = boom  # type: ignore[assignment]
    with contextlib.redirect_stderr(_io.StringIO()), pytest.raises(RuntimeError):
        sup.run(once=True)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["rejected"] == [str(current)]
