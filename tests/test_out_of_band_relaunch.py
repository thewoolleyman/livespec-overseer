"""The sanctioned operator relaunch is a separate, non-destructive surface."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import herdr_identity
import registry

if TYPE_CHECKING:
    import out_of_band_relaunch

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "overseer" / "out_of_band_relaunch.py"


def test_sanctioned_relaunch_entrypoint_is_a_separate_operator_surface() -> None:
    """A relaunch cannot use `start`, whose respawn path is allowed to terminate."""
    assert MODULE_PATH.is_file()
    entrypoint = importlib.import_module("out_of_band_relaunch")
    assert callable(entrypoint.relaunch)


def test_qualified_tmux_targets_must_name_the_same_backend_instance() -> None:
    """A pane id alone cannot authorize typing into another tmux server."""
    entrypoint = importlib.import_module("out_of_band_relaunch")
    recorded = herdr_identity.encode_tmux_target(
        target=herdr_identity.TmuxPaneTarget(
            socket_path="/tmp/tmux-a.sock",
            server_pid=41,
            server_starttime="100",
            pane_id="%1",
        )
    )
    target = herdr_identity.encode_tmux_target(
        target=herdr_identity.TmuxPaneTarget(
            socket_path="/tmp/tmux-b.sock",
            server_pid=42,
            server_starttime="200",
            pane_id="%1",
        )
    )

    assert not entrypoint._same_backend(recorded=recorded, target=target)


def _track(*, tmp_path: Path, profile: registry.ModelProfile | None = None) -> registry.PlanTrack:
    return registry.PlanTrack(
        repo=str(tmp_path),
        topic="alpha",
        tmux="old-pane",
        epic="overseer-alpha",
        model_profile=profile,
    )


def _request(**changes: str) -> out_of_band_relaunch.RelaunchRequest:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    values = {
        "topic": "alpha",
        "target": "target-pane",
        "invoker": "operator",
    }
    values.update(changes)
    return entrypoint.RelaunchRequest(**values)


def test_profile_selection_and_intent_are_explicit_and_durable(*, tmp_path: Path) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    request = _request(model="claude-opus")

    selected = entrypoint._profile_for_request(track=track, request=request)

    assert selected.model_profile == {
        "harness": "claude",
        "model": "claude-opus",
        "wrapper": None,
    }
    assert (
        entrypoint._profile_for_request(track=track, request=_request(runtime="codex")).ok is False
    )
    assert (
        entrypoint._profile_for_request(track=track, request=_request(runtime="claude")).ok is False
    )

    intent = entrypoint._start_intent(track=track, request=request)
    assert json.loads(intent.read_text(encoding="utf-8")) == {
        "action": "sanctioned-out-of-band-relaunch",
        "invoker": "operator",
        "outcome": None,
        "target": "target-pane",
        "track": f"{tmp_path}::alpha",
    }
    entrypoint._finish_intent(path=intent, track=track, request=request, outcome="succeeded")
    assert json.loads(intent.read_text(encoding="utf-8"))["outcome"] == "succeeded"


def test_low_level_launch_identity_and_rebind_are_nondestructive(
    *, monkeypatch, tmp_path: Path
) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    pastes: list[tuple[str, str]] = []
    registrations: list[tuple[str, ...]] = []
    writes: list[object] = []
    tmux = SimpleNamespace(
        bracketed_paste=lambda *, session, text: pastes.append((session, text)) or True,
        send_keys=lambda *, session, keys: True,
        pane_id=lambda *, session: session,
        pane_current_command=lambda *, session: "zsh",
    )
    sup = SimpleNamespace(
        tmux=tmux,
        claude_identity_by_session={("target-pane", "alpha"): "claude:44:55:alpha"},
        refresh_claude_status=lambda: None,
    )
    track = _track(tmp_path=tmp_path)
    plan = entrypoint.ClaudeLaunchPlan(
        command="claude --model claude-opus --dangerously-skip-permissions -n alpha",
        env={"ANTHROPIC_MODEL": None},
    )
    monkeypatch.setattr(
        entrypoint.pane_router,
        "register_coordinates",
        lambda *, driver, coordinates: registrations.append(coordinates),
    )
    monkeypatch.setattr(
        entrypoint.registry,
        "upsert_mapping",
        lambda **kwargs: writes.append(kwargs["track"]) or True,
    )

    assert entrypoint._target_is_idle_shell(sup=sup, target="target-pane")
    assert entrypoint._launch_at_shell(sup=sup, track=track, target="target-pane", plan=plan)
    assert str(tmp_path) in pastes[0][1] and "ANTHROPIC_MODEL" in pastes[0][1]
    assert (
        entrypoint._identity_after_launch(sup=sup, track=track, target="target-pane")
        == "claude:44:55:alpha"
    )
    assert registrations == [("target-pane",)]
    assert entrypoint._rebind(track=track, target="target-pane", identity="claude:44:55:alpha")
    assert writes[0].tmux == "target-pane"


def test_relaunch_refuses_before_intent_or_input_and_records_each_post_launch_outcome(
    *, monkeypatch, tmp_path: Path
) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(
        tmp_path=tmp_path,
        profile={"harness": "claude", "model": "claude-opus", "wrapper": None},
    )
    request = _request()
    plan = entrypoint.ClaudeLaunchPlan(command="claude", env={})
    calls: list[str] = []
    sup = SimpleNamespace(store_path=tmp_path / "store")

    monkeypatch.setattr(
        entrypoint,
        "_validated_launch",
        lambda **kwargs: entrypoint.RelaunchResult(ok=False, message="relaunch REFUSED: unsafe"),
    )
    assert not entrypoint.relaunch(request=request, sup=sup).ok
    monkeypatch.setattr(entrypoint, "_validated_launch", lambda **kwargs: (track, track, plan))
    monkeypatch.setattr(entrypoint, "_start_intent", lambda **kwargs: tmp_path / "intent")
    monkeypatch.setattr(
        entrypoint,
        "_finish_intent",
        lambda **kwargs: calls.append(str(kwargs["outcome"])),
    )
    monkeypatch.setattr(entrypoint, "_launch_at_shell", lambda **kwargs: False)
    assert "launch input" in entrypoint.relaunch(request=request, sup=sup).message

    monkeypatch.setattr(entrypoint, "_launch_at_shell", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "await_pane", lambda **kwargs: False)
    assert "did not appear" in entrypoint.relaunch(request=request, sup=sup).message

    monkeypatch.setattr(entrypoint, "await_pane", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "await_input_box", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "resume_for_track", lambda **kwargs: None)
    assert "no resume" in entrypoint.relaunch(request=request, sup=sup).message

    monkeypatch.setattr(entrypoint, "resume_for_track", lambda **kwargs: "resume")
    monkeypatch.setattr(
        entrypoint,
        "submit_prompt_result",
        lambda **kwargs: SimpleNamespace(submitted=False),
    )
    monkeypatch.setattr(entrypoint, "_identity_after_launch", lambda **kwargs: "identity")
    assert "rebind" in entrypoint.relaunch(request=request, sup=sup).message

    monkeypatch.setattr(
        entrypoint,
        "submit_prompt_result",
        lambda **kwargs: SimpleNamespace(submitted=True),
    )
    monkeypatch.setattr(entrypoint, "_rebind", lambda **kwargs: True)
    assert entrypoint.relaunch(request=request, sup=sup).ok
    assert calls == [
        "launch_failed",
        "launch_unconfirmed",
        "resume_unavailable",
        "resume_or_rebind_failed",
        "succeeded",
    ]
