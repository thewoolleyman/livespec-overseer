"""Codex proof rails for the attended relaunch entrypoint."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import herdr_identity
import pytest
import registry
from _supervisor_launch_profile import CodexLaunchPlan

ROOT = Path(__file__).resolve().parent.parent
CODEX_MODULE_PATH = ROOT / "overseer" / "_out_of_band_relaunch_codex.py"


def _track(*, tmp_path: Path) -> registry.PlanTrack:
    return registry.PlanTrack(
        repo=str(tmp_path),
        topic="alpha",
        tmux="old-pane",
        epic="overseer-alpha",
        model_profile={"harness": "codex", "model": "gpt-5.1-codex", "wrapper": None},
    )


def _codex_module():
    assert CODEX_MODULE_PATH.is_file()
    return importlib.import_module("_out_of_band_relaunch_codex")


def _relaunch_actions(**kwargs: object):
    actions = importlib.import_module("out_of_band_relaunch_actions")
    return actions.RelaunchActions(**kwargs)


def _codex_relaunch_world(
    *, tmp_path: Path
) -> tuple[object, str, list[dict[str, object]], list[str]]:
    target = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/tmp/herdr.sock", server_pid=1, server_starttime="2", pane_id="w1:p2"
        )
    )
    home = tmp_path / "codex"
    home.mkdir()
    index = home / "session_index.jsonl"
    index.write_text(json.dumps({"id": "old-thread", "thread_name": "alpha"}) + "\n")
    reports: list[dict[str, object]] = []
    pastes: list[str] = []

    def send_keys(*, session: str, keys: str) -> bool:
        if keys == "Enter" and pastes[-1] == "/rename alpha":
            with index.open("a", encoding="utf-8") as handle:
                _ = handle.write(
                    json.dumps(
                        {
                            "id": "00000000-0000-0000-0000-000000000007",
                            "thread_name": "alpha",
                        }
                    )
                    + "\n"
                )
        return True

    tmux = SimpleNamespace(
        herdr_launch=lambda **_kwargs: SimpleNamespace(ok=True),
        bracketed_paste=lambda *, text, **_kwargs: pastes.append(text) or True,
        send_keys=send_keys,
        herdr_writer=SimpleNamespace(
            report_agent_session=lambda **kwargs: reports.append(kwargs) or SimpleNamespace(ok=True)
        ),
    )
    return (
        SimpleNamespace(
            tmux=tmux,
            codex_home=home,
            colliding_topics=frozenset(),
            sleep=lambda _seconds: None,
        ),
        target,
        reports,
        pastes,
    )


def test_codex_relaunch_confirms_a_fresh_rename_before_reporting_and_rebinding(
    *, monkeypatch, tmp_path: Path
) -> None:
    """The target pane alone receives the fresh indexed Codex thread."""
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    sup, target, reports, pastes = _codex_relaunch_world(tmp_path=tmp_path)
    request = entrypoint.RelaunchRequest(topic="alpha", target=target, invoker="operator")
    rebound: list[registry.Track] = []
    plan = CodexLaunchPlan(command="codex -m gpt-5.1-codex", env={})
    monkeypatch.setattr(entrypoint, "_validated_launch", lambda **_kwargs: (track, track, plan))
    monkeypatch.setattr(entrypoint, "_start_intent", lambda **_kwargs: tmp_path / "intent")
    monkeypatch.setattr(entrypoint, "_finish_intent", lambda **_kwargs: None)
    monkeypatch.setattr(entrypoint, "await_pane", lambda **_kwargs: True)
    monkeypatch.setattr(entrypoint, "await_input_box", lambda **_kwargs: True)
    monkeypatch.setattr(entrypoint, "resume_for_track", lambda **_kwargs: "resume")
    monkeypatch.setattr(
        entrypoint,
        "submit_prompt_result",
        lambda **kwargs: pastes.append(str(kwargs["text"])) or SimpleNamespace(submitted=True),
    )
    monkeypatch.setattr(
        entrypoint,
        "_rebind",
        lambda *, track, **_kwargs: rebound.append(track) or True,
    )
    monkeypatch.setattr(entrypoint, "_identity_after_launch", lambda **_kwargs: None)

    result = entrypoint.relaunch(request=request, sup=sup)

    assert result.ok
    assert pastes[-2:] == ["/rename alpha", "resume"]
    assert reports == [
        {
            "target": herdr_identity.decode_herdr_target(value=target),
            "source": "overseer",
            "agent_session_id": "00000000-0000-0000-0000-000000000007",
        }
    ]
    assert rebound[0].tmux == target
    assert rebound[0].observed_session_identity == "codex:00000000-0000-0000-0000-000000000007"
    assert rebound[0].model_profile == track.model_profile


def test_codex_confirmation_fails_closed_without_a_new_exactly_named_thread(
    *, monkeypatch, tmp_path: Path
) -> None:
    """A missed rename does not use an old index row or report a backend session."""
    codex = _codex_module()
    track = _track(tmp_path=tmp_path)
    request = SimpleNamespace(target="legacy-pane")
    finished: list[dict[str, object]] = []
    actions = _relaunch_actions(
        finish_intent=lambda **kwargs: finished.append(kwargs),
        resume_for_track=lambda **_kwargs: "resume",
        submit_prompt_result=lambda **_kwargs: SimpleNamespace(submitted=True),
        rebind=lambda **_kwargs: True,
    )
    relaunch = codex.CodexRelaunch(
        intent=tmp_path / "intent",
        name="alpha",
        prior_thread_ids=frozenset(),
        profile_track=track,
        request=request,
        track=track,
    )
    sup = SimpleNamespace(
        codex_home=None,
        sleep=lambda _seconds: None,
        tmux=SimpleNamespace(bracketed_paste=lambda **_kwargs: False),
    )

    result = codex.relaunch_codex(actions=actions, relaunch=relaunch, sup=sup)

    assert not result.ok
    assert "legacy-pane" in result.message and "observed thread none" in result.message
    assert finished[0]["outcome"] == "rename_unconfirmed"
    assert codex.report_codex_agent_session(sup=sup, target="legacy-pane", thread_id="thread")
    sup.tmux.bracketed_paste = lambda **_kwargs: True
    sup.tmux.send_keys = lambda **_kwargs: False
    assert (
        codex.confirm_codex_rename(
            name="alpha", prior_thread_ids=frozenset(), sup=sup, target="legacy-pane"
        )
        is None
    )
    sup.tmux.send_keys = lambda **_kwargs: True
    assert (
        codex.confirm_codex_rename(
            name="alpha", prior_thread_ids=frozenset(), sup=sup, target="legacy-pane"
        )
        is None
    )


def test_codex_confirmation_rejects_an_unsent_rename_and_an_unindexed_rename(
    *, tmp_path: Path
) -> None:
    """A failed Enter and a bounded empty index both leave no usable thread."""
    codex = _codex_module()
    sup = SimpleNamespace(
        codex_home=tmp_path / "codex",
        sleep=lambda _seconds: None,
        tmux=SimpleNamespace(
            bracketed_paste=lambda **_kwargs: True,
            send_keys=lambda **_kwargs: False,
        ),
    )

    assert (
        codex.confirm_codex_rename(
            name="alpha", prior_thread_ids=frozenset(), sup=sup, target="target-pane"
        )
        is None
    )
    sup.tmux.send_keys = lambda **_kwargs: True
    assert (
        codex.confirm_codex_rename(
            name="alpha", prior_thread_ids=frozenset(), sup=sup, target="target-pane"
        )
        is None
    )


@pytest.mark.parametrize("failure", ["report", "resume", "submit", "rebind"])
def test_codex_post_rename_failures_finish_the_intent_without_rebinding(
    *, monkeypatch, tmp_path: Path, failure: str
) -> None:
    """Every post-confirmation failure is durable and cannot become a successful mapping."""
    codex = _codex_module()
    track = _track(tmp_path=tmp_path)
    finished: list[str] = []
    submitted = failure != "submit"
    actions = _relaunch_actions(
        finish_intent=lambda **kwargs: finished.append(str(kwargs["outcome"])),
        resume_for_track=lambda **_kwargs: None if failure == "resume" else "resume",
        submit_prompt_result=lambda **_kwargs: SimpleNamespace(submitted=submitted),
        rebind=lambda **_kwargs: failure != "rebind",
    )
    relaunch = codex.CodexRelaunch(
        intent=tmp_path / "intent",
        name="alpha",
        prior_thread_ids=frozenset(),
        profile_track=track,
        request=SimpleNamespace(target="target-pane"),
        track=track,
    )
    monkeypatch.setattr(codex, "report_codex_agent_session", lambda **_kwargs: failure != "report")

    result = codex._deliver_resume(
        actions=actions,
        relaunch=relaunch,
        sup=SimpleNamespace(),
        thread_id="thread-7",
    )

    assert not result.ok
    assert finished == [
        "agent_session_report_failed"
        if failure == "report"
        else "resume_unavailable"
        if failure == "resume"
        else "resume_or_rebind_failed"
    ]
