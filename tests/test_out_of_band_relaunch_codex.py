"""Codex-specific proof rails for the attended relaunch entrypoint."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import herdr_identity
import registry


def _track(*, tmp_path: Path) -> registry.PlanTrack:
    return registry.PlanTrack(
        repo=str(tmp_path),
        topic="alpha",
        tmux="old-pane",
        epic="overseer-alpha",
        model_profile={"harness": "codex", "model": "gpt-5.1-codex", "wrapper": None},
    )


def test_confirm_rename_requires_a_new_indexed_thread_and_reports_only_herdr(
    *, monkeypatch, tmp_path: Path
) -> None:
    codex = importlib.import_module("_out_of_band_relaunch_codex")
    sent: list[tuple[str, str]] = []
    sup = SimpleNamespace(
        tmux=SimpleNamespace(
            bracketed_paste=lambda *, session, text: sent.append((session, text)) or True,
            send_keys=lambda **kwargs: True,
        ),
        sleep=lambda _seconds: None,
    )
    fresh = "00000000-0000-0000-0000-000000000007"
    monkeypatch.setattr(codex, "indexed_codex_thread", lambda **kwargs: fresh)

    assert (
        codex.confirm_codex_rename(
            name="alpha", prior_thread="00000000-0000-0000-0000-000000000006", sup=sup, target="p"
        )
        == fresh
    )
    assert sent == [("p", "/rename alpha")]
    assert codex.report_codex_agent_session(target="legacy-pane", thread_id=fresh)

    target = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/tmp/herdr.sock", server_pid=1, server_starttime="2", pane_id="w1:p2"
        )
    )
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        codex.subprocess,
        "run",
        lambda argv, **kwargs: calls.append(argv) or SimpleNamespace(returncode=0),
    )
    assert codex.report_codex_agent_session(target=target, thread_id=fresh)
    assert calls[0][-1] == "w1:p2"


def test_unconfirmed_rename_reports_no_session_and_leaves_mapping_unchanged(
    *, monkeypatch, tmp_path: Path
) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    request = entrypoint.RelaunchRequest(topic="alpha", target="target-pane", invoker="operator")
    finished: list[dict[str, object]] = []
    monkeypatch.setattr(entrypoint, "_derived_session_name", lambda **kwargs: "alpha")
    monkeypatch.setattr(entrypoint, "_indexed_codex_thread", lambda **kwargs: "old-thread")
    monkeypatch.setattr(entrypoint, "_confirm_codex_rename", lambda **kwargs: None)
    monkeypatch.setattr(entrypoint, "_finish_intent", lambda **kwargs: finished.append(kwargs))
    monkeypatch.setattr(
        entrypoint,
        "_report_codex_agent_session",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    result = entrypoint._relaunch_codex(
        intent=tmp_path / "intent",
        profile_track=track,
        request=request,
        sup=SimpleNamespace(),
        track=track,
    )

    assert not result.ok
    assert "target-pane" in result.message and "old-thread" in result.message
    assert finished[0]["outcome"] == "rename_unconfirmed"


def test_report_failure_precedes_resume_and_mapping_rebind(*, monkeypatch, tmp_path: Path) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    request = entrypoint.RelaunchRequest(topic="alpha", target="target-pane", invoker="operator")
    monkeypatch.setattr(entrypoint, "_report_codex_agent_session", lambda **kwargs: False)
    monkeypatch.setattr(
        entrypoint, "resume_for_track", lambda **kwargs: (_ for _ in ()).throw(AssertionError())
    )
    monkeypatch.setattr(entrypoint, "_finish_intent", lambda **kwargs: None)

    result = entrypoint._deliver_codex_resume_and_rebind(
        intent=tmp_path / "intent",
        profile_track=track,
        request=request,
        sup=SimpleNamespace(),
        track=track,
        thread_id="thread-7",
    )

    assert not result.ok
