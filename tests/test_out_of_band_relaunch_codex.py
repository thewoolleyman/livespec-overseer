"""Codex proof rails for the attended relaunch entrypoint."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType, SimpleNamespace

import herdr_identity
import registry

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "overseer" / "_out_of_band_relaunch_codex.py"

_FRESH = "00000000-0000-0000-0000-000000000007"
_PRIOR = "00000000-0000-0000-0000-000000000006"


def _codex() -> ModuleType:
    assert MODULE_PATH.is_file()
    return importlib.import_module("_out_of_band_relaunch_codex")


def _track(*, tmp_path: Path) -> registry.PlanTrack:
    return registry.PlanTrack(
        repo=str(tmp_path),
        topic="alpha",
        tmux="old-pane",
        epic="overseer-alpha",
        model_profile={"harness": "codex", "model": "gpt-5.1-codex", "wrapper": None},
    )


def _request(*, entrypoint: ModuleType) -> object:
    return entrypoint.RelaunchRequest(topic="alpha", target="target-pane", invoker="operator")


def test_confirm_rename_requires_a_new_indexed_thread_within_its_stated_bound(
    *, monkeypatch
) -> None:
    codex = _codex()
    sent: list[tuple[str, str]] = []
    indexed = iter((_PRIOR, _FRESH))
    sup = SimpleNamespace(
        tmux=SimpleNamespace(
            bracketed_paste=lambda *, session, text: sent.append((session, text)) or True,
            send_keys=lambda **kwargs: True,
        ),
        sleep=lambda _seconds: None,
    )
    monkeypatch.setattr(codex, "indexed_codex_thread", lambda **kwargs: next(indexed))

    assert (
        codex.confirm_codex_rename(name="derived-alpha", prior_thread=_PRIOR, sup=sup, target="p")
        == _FRESH
    )
    assert sent == [("p", "/rename derived-alpha")]
    assert "polls" in codex.codex_rename_wait_bound()


def test_reported_thread_is_verified_on_its_exact_herdr_pane(*, monkeypatch) -> None:
    codex = _codex()
    target = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/tmp/herdr.sock", server_pid=1, server_starttime="2", pane_id="w1:p2"
        )
    )
    calls: list[tuple[str, ...]] = []
    sup = SimpleNamespace(tmux=SimpleNamespace(pane_agent_session=lambda *, session: _FRESH))
    monkeypatch.setattr(
        codex.subprocess,
        "run",
        lambda argv, **kwargs: calls.append(argv) or SimpleNamespace(returncode=0),
    )

    assert codex.report_codex_agent_session(sup=sup, target=target, thread_id=_FRESH)
    assert calls == [
        (
            "herdr",
            "pane",
            "report-agent-session",
            "--source",
            "overseer",
            "--agent",
            "codex",
            "--agent-session-id",
            _FRESH,
            "w1:p2",
        )
    ]


def test_confirmation_and_report_fail_closed_on_every_unproven_path(*, monkeypatch) -> None:
    codex = _codex()
    refusing = SimpleNamespace(
        tmux=SimpleNamespace(bracketed_paste=lambda **kwargs: False), sleep=lambda _seconds: None
    )
    assert (
        codex.confirm_codex_rename(name="alpha", prior_thread=None, sup=refusing, target="p")
        is None
    )

    timed_out = SimpleNamespace(
        tmux=SimpleNamespace(
            bracketed_paste=lambda **kwargs: True,
            send_keys=lambda **kwargs: True,
        ),
        sleep=lambda _seconds: None,
    )
    monkeypatch.setattr(codex, "indexed_codex_thread", lambda **kwargs: _PRIOR)
    assert (
        codex.confirm_codex_rename(name="alpha", prior_thread=_PRIOR, sup=timed_out, target="p")
        is None
    )
    assert codex.report_codex_agent_session(sup=timed_out, target="legacy-pane", thread_id=_FRESH)

    target = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/tmp/herdr.sock", server_pid=1, server_starttime="2", pane_id="w1:p2"
        )
    )
    herdr = SimpleNamespace(tmux=SimpleNamespace(pane_agent_session=lambda **kwargs: _PRIOR))
    monkeypatch.setattr(
        codex.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1)
    )
    assert not codex.report_codex_agent_session(sup=herdr, target=target, thread_id=_FRESH)


def test_codex_relaunch_refuses_an_unconfirmed_rename_without_reporting_or_rebinding(
    *, monkeypatch, tmp_path: Path
) -> None:
    codex = _codex()
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    reported: list[object] = []
    rebound: list[object] = []
    monkeypatch.setattr(codex, "confirm_codex_rename", lambda **kwargs: None)
    monkeypatch.setattr(codex, "indexed_codex_thread", lambda **kwargs: _PRIOR)
    monkeypatch.setattr(
        codex, "report_codex_agent_session", lambda **kwargs: reported.append(kwargs)
    )
    monkeypatch.setattr(codex.registry, "upsert_mapping", lambda **kwargs: rebound.append(kwargs))

    result = codex.relaunch_codex(
        intent=tmp_path / "intent",
        profile_track=track,
        request=_request(entrypoint=entrypoint),
        sup=SimpleNamespace(colliding_topics=frozenset()),
        track=track,
    )

    assert result.ok is False
    assert "target-pane" in result.message and _PRIOR in result.message
    assert reported == []
    assert rebound == []


def test_confirmed_codex_relaunch_reports_then_resumes_and_rebinds_profile(
    *, monkeypatch, tmp_path: Path
) -> None:
    codex = _codex()
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(codex, "confirm_codex_rename", lambda **kwargs: _FRESH)
    monkeypatch.setattr(
        codex,
        "report_codex_agent_session",
        lambda **kwargs: calls.append(("report", kwargs)) or True,
    )
    monkeypatch.setattr(
        codex, "resume_for_track", lambda **kwargs: "resume plan epic overseer-alpha"
    )
    monkeypatch.setattr(
        codex,
        "submit_prompt_result",
        lambda **kwargs: calls.append(("resume", kwargs)) or SimpleNamespace(submitted=True),
    )
    monkeypatch.setattr(
        codex.registry,
        "upsert_mapping",
        lambda **kwargs: calls.append(("rebind", kwargs)) or True,
    )

    result = codex.relaunch_codex(
        intent=tmp_path / "intent",
        profile_track=track,
        request=_request(entrypoint=entrypoint),
        sup=SimpleNamespace(colliding_topics=frozenset()),
        track=track,
    )

    assert result.ok is True
    assert "within" in result.message
    assert calls[0][0] == "report" and calls[0][1]["thread_id"] == _FRESH
    assert calls[1][0] == "resume" and calls[1][1]["expect_codex"] is True
    assert calls[2][0] == "rebind"
    rebound = calls[2][1]["track"]
    assert rebound.tmux == "target-pane"
    assert rebound.observed_session_identity == f"codex:{_FRESH}"
    assert rebound.model_profile == track.model_profile


def test_confirmed_codex_relaunch_stops_before_unproved_resume_or_rebind(
    *, monkeypatch, tmp_path: Path
) -> None:
    codex = _codex()
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    request = _request(entrypoint=entrypoint)
    sup = SimpleNamespace(colliding_topics=frozenset())
    monkeypatch.setattr(codex, "confirm_codex_rename", lambda **kwargs: _FRESH)
    monkeypatch.setattr(codex, "report_codex_agent_session", lambda **kwargs: False)
    assert not codex.relaunch_codex(
        intent=tmp_path / "report", profile_track=track, request=request, sup=sup, track=track
    ).ok

    monkeypatch.setattr(codex, "report_codex_agent_session", lambda **kwargs: True)
    monkeypatch.setattr(codex, "resume_for_track", lambda **kwargs: None)
    assert not codex.relaunch_codex(
        intent=tmp_path / "resume", profile_track=track, request=request, sup=sup, track=track
    ).ok

    monkeypatch.setattr(codex, "resume_for_track", lambda **kwargs: "resume")
    monkeypatch.setattr(
        codex, "submit_prompt_result", lambda **kwargs: SimpleNamespace(submitted=False)
    )
    assert not codex.relaunch_codex(
        intent=tmp_path / "submit", profile_track=track, request=request, sup=sup, track=track
    ).ok


def test_validation_selects_a_fresh_codex_launch_profile(*, tmp_path: Path) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    sup = SimpleNamespace(
        store_path=tmp_path / "store",
        tmux=SimpleNamespace(
            pane_id=lambda *, session: session,
            pane_current_command=lambda *, session: "bash",
        ),
    )
    request = entrypoint.RelaunchRequest(topic="alpha", target="old-pane", invoker="operator")

    validated = entrypoint._validated_launch(request=request, sup=sup, tracks=[track])

    assert isinstance(validated, tuple)
    assert "codex" in validated[2].command and "resume" not in validated[2].command


def test_entrypoint_awaits_codex_then_delegates_its_binding(*, monkeypatch, tmp_path: Path) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    plan = SimpleNamespace(command="codex", env={})
    request = _request(entrypoint=entrypoint)
    awaited: list[object] = []
    expected = entrypoint.RelaunchResult(ok=True, message="relaunched")
    monkeypatch.setattr(entrypoint, "_validated_launch", lambda **kwargs: (track, track, plan))
    monkeypatch.setattr(entrypoint, "_start_intent", lambda **kwargs: tmp_path / "intent")
    monkeypatch.setattr(entrypoint, "_launch_at_shell", lambda **kwargs: True)
    monkeypatch.setattr(
        entrypoint, "await_pane", lambda **kwargs: awaited.append(kwargs["is_ready"]) or True
    )
    monkeypatch.setattr(
        entrypoint._out_of_band_relaunch_codex, "relaunch_codex", lambda **kwargs: expected
    )

    result = entrypoint.relaunch(
        request=request, sup=SimpleNamespace(store_path=tmp_path / "store")
    )

    assert result == expected
    assert awaited == [entrypoint.signals.pane_is_codex]
