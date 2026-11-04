"""The Herdr writer reports a Codex agent session for exactly one target pane."""

from __future__ import annotations

import json
from pathlib import Path

import herdr_identity
import herdr_transport
import herdr_write
import pytest

__all__: list[str] = []

THREAD = "019f548d-0000-7000-8000-0000000000aa"
TARGET_PANE = "w1:p9"
OTHER_PANE = "w1:p2"


def _target(*, tmp_path: Path) -> herdr_identity.HerdrPaneTarget:
    return herdr_identity.HerdrPaneTarget(
        socket_path=str(tmp_path / "herdr.sock"),
        server_pid=700,
        server_starttime="server-start",
        pane_id=TARGET_PANE,
    )


def _outcome(*, ok: bool, error: str, request_sent: bool) -> herdr_transport.RpcOutcome:
    return herdr_transport.RpcOutcome(
        ok=ok,
        result={},
        error=error,
        peer=None,
        timed_out=False,
        request_sent=request_sent,
    )


def _capture(
    *, monkeypatch: pytest.MonkeyPatch, outcome: herdr_transport.RpcOutcome
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def request(_self: object, **kwargs: object) -> herdr_transport.RpcOutcome:
        calls.append(kwargs)
        return outcome

    monkeypatch.setattr(herdr_write.HerdrWriter, "request", request)
    return calls


def test_the_thread_is_reported_as_the_agent_session_of_the_one_target_pane(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _capture(
        monkeypatch=monkeypatch, outcome=_outcome(ok=True, error="", request_sent=True)
    )
    target = _target(tmp_path=tmp_path)

    outcome = herdr_write.HerdrWriter().report_agent_session(
        target=target, source="overseer", agent_session_id=THREAD
    )

    assert outcome.ok
    assert len(calls) == 1
    assert calls[0]["target"] == target
    params = calls[0]["params"]
    assert isinstance(params, dict)
    assert params["pane_id"] == TARGET_PANE
    assert params["agent"] == "codex"
    assert params["agent_session_id"] == THREAD
    assert params["source"] == "overseer"


def test_no_other_pane_is_named_by_the_report(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _capture(
        monkeypatch=monkeypatch, outcome=_outcome(ok=True, error="", request_sent=True)
    )

    herdr_write.HerdrWriter().report_agent_session(
        target=_target(tmp_path=tmp_path), source="overseer", agent_session_id=THREAD
    )

    wire = json.dumps(calls[0]["params"])
    assert TARGET_PANE in wire
    assert OTHER_PANE not in wire
    assert len(calls) == 1


def test_a_rejected_report_is_surfaced_and_not_recorded_as_a_session(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture(
        monkeypatch=monkeypatch,
        outcome=_outcome(ok=False, error="herdr rejected the report", request_sent=True),
    )

    outcome = herdr_write.HerdrWriter().report_agent_session(
        target=_target(tmp_path=tmp_path), source="overseer", agent_session_id=THREAD
    )

    assert not outcome.ok
    assert outcome.error == "herdr rejected the report"
    assert outcome.effect_unknown


def test_a_report_refused_before_it_was_sent_is_not_effect_unknown(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture(
        monkeypatch=monkeypatch,
        outcome=_outcome(ok=False, error="server generation replaced", request_sent=False),
    )

    outcome = herdr_write.HerdrWriter().report_agent_session(
        target=_target(tmp_path=tmp_path), source="overseer", agent_session_id=THREAD
    )

    assert not outcome.ok
    assert outcome.error == "server generation replaced"
    assert not outcome.effect_unknown
