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
    intent_store = importlib.import_module("out_of_band_relaunch_intent")
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

    intent = intent_store.record_start_intent(track=track, request=request)
    assert json.loads(intent.read_text(encoding="utf-8")) == {
        "action": "sanctioned-out-of-band-relaunch",
        "invoker": "operator",
        "outcome": None,
        "target": "target-pane",
        "track": f"{tmp_path}::alpha",
    }
    intent_store.finish_intent(path=intent, track=track, request=request, outcome="succeeded")
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
    monkeypatch.setattr(entrypoint, "record_start_intent", lambda **kwargs: tmp_path / "intent")
    monkeypatch.setattr(
        entrypoint,
        "finish_intent",
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


def _tmux_target(*, socket: str, pane: str = "%1") -> str:
    return herdr_identity.encode_tmux_target(
        target=herdr_identity.TmuxPaneTarget(
            socket_path=socket,
            server_pid=41,
            server_starttime="100",
            pane_id=pane,
        )
    )


def _herdr_target(*, socket: str, pane: str = "window:pane") -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=socket,
            server_pid=41,
            server_starttime="100",
            pane_id=pane,
        )
    )


def test_track_and_backend_matching_refuse_every_ambiguous_or_foreign_target(
    *, tmp_path: Path
) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    mapped = _track(tmp_path=tmp_path)

    assert entrypoint._matching_track(topic="missing", tracks=[mapped]) is None
    assert entrypoint._matching_track(topic="alpha", tracks=[mapped, mapped]) is None
    assert entrypoint._matching_track(topic="alpha", tracks=[mapped]) == mapped
    assert not entrypoint._same_backend(recorded="tmux:not-a-coordinate", target="target")
    assert not entrypoint._same_backend(
        recorded=_tmux_target(socket="/tmp/tmux.sock"),
        target=_herdr_target(socket="/tmp/herdr.sock"),
    )
    assert entrypoint._same_backend(recorded="legacy", target="target")
    assert not entrypoint._same_backend(
        recorded=_herdr_target(socket="/tmp/herdr.sock"),
        target=_tmux_target(socket="/tmp/tmux.sock"),
    )
    assert entrypoint._same_backend(
        recorded=_herdr_target(socket="/tmp/herdr.sock"),
        target=_herdr_target(socket="/tmp/herdr.sock", pane="other"),
    )


def test_profileless_request_keeps_the_recorded_track_and_refusals_precede_intent(
    *, monkeypatch, tmp_path: Path
) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path, profile=None)
    request = _request()
    sup = SimpleNamespace(store_path=tmp_path / "store")

    assert entrypoint._profile_for_request(track=track, request=request) is track
    monkeypatch.setattr(entrypoint.registry, "read_valid_mapping", lambda **kwargs: [])
    assert "recorded epic" in entrypoint.relaunch(request=request, sup=sup).message
    assert not (tmp_path / "tmp").exists()


def test_validation_refuses_before_any_record_for_every_unsafe_premise(
    *, monkeypatch, tmp_path: Path
) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    request = _request()
    track = _track(
        tmp_path=tmp_path,
        profile={"harness": "claude", "model": "claude-opus", "wrapper": None},
    )
    sup = SimpleNamespace(store_path=tmp_path / "store")
    monkeypatch.setattr(entrypoint, "_same_backend", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "_target_is_idle_shell", lambda **kwargs: True)

    unmapped = SimpleNamespace(topic="alpha", assigned=True, epic=None)
    assert (
        "recorded epic"
        in entrypoint._validated_launch(request=request, sup=sup, tracks=[unmapped]).message
    )
    monkeypatch.setattr(entrypoint, "_same_backend", lambda **kwargs: False)
    assert (
        "backend" in entrypoint._validated_launch(request=request, sup=sup, tracks=[track]).message
    )
    monkeypatch.setattr(entrypoint, "_same_backend", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "_target_is_idle_shell", lambda **kwargs: False)
    assert (
        "idle interactive shell"
        in entrypoint._validated_launch(request=request, sup=sup, tracks=[track]).message
    )
    monkeypatch.setattr(entrypoint, "_target_is_idle_shell", lambda **kwargs: True)
    assert (
        "unsupported runtime"
        in entrypoint._validated_launch(
            request=_request(runtime="codex"), sup=sup, tracks=[track]
        ).message
    )
    assert isinstance(entrypoint._validated_launch(request=request, sup=sup, tracks=[track]), tuple)
    monkeypatch.setattr(
        entrypoint,
        "claude_launch_plan",
        lambda **kwargs: entrypoint.LaunchProfileProblem(message="stale"),
    )
    assert "stale" in entrypoint._validated_launch(request=request, sup=sup, tracks=[track]).message
    assert not (tmp_path / "tmp").exists()


def test_successful_relaunch_records_intent_launches_resumes_and_rebinds_without_rename(
    *, monkeypatch, tmp_path: Path
) -> None:
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(
        tmp_path=tmp_path,
        profile={"harness": "claude", "model": "claude-opus", "wrapper": None},
    )
    request = _request()
    plan = entrypoint.ClaudeLaunchPlan(command="claude", env={})
    submitted: list[str] = []
    rebound: list[tuple[object, str, str]] = []
    sup = SimpleNamespace(store_path=tmp_path / "store")
    monkeypatch.setattr(entrypoint, "_validated_launch", lambda **kwargs: (track, track, plan))
    monkeypatch.setattr(entrypoint, "_launch_at_shell", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "await_pane", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "await_input_box", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "resume_for_track", lambda **kwargs: "resume plan epic")
    monkeypatch.setattr(
        entrypoint,
        "submit_prompt_result",
        lambda **kwargs: submitted.append(kwargs["text"]) or SimpleNamespace(submitted=True),
    )
    monkeypatch.setattr(entrypoint, "_identity_after_launch", lambda **kwargs: "claude:1:2:alpha")
    monkeypatch.setattr(
        entrypoint,
        "_rebind",
        lambda **kwargs: rebound.append((kwargs["track"], kwargs["target"], kwargs["identity"]))
        or True,
    )

    assert entrypoint.relaunch(request=request, sup=sup).ok
    intent = tmp_path / "tmp" / "overseer" / "alpha" / ".out-of-band-relaunch-intent.json"
    assert json.loads(intent.read_text(encoding="utf-8"))["outcome"] == "succeeded"
    assert submitted == ["resume plan epic"]
    assert rebound == [(track, "target-pane", "claude:1:2:alpha")]


def test_cli_handler_reports_a_sanctioned_relaunch_outcome(*, monkeypatch) -> None:
    supervisor = importlib.import_module("supervisor")
    results: list[tuple[str, str]] = []
    monkeypatch.setattr(supervisor, "build_supervisor", lambda: "supervisor")
    monkeypatch.setattr(
        supervisor.out_of_band_relaunch,
        "relaunch",
        lambda **kwargs: supervisor.out_of_band_relaunch.RelaunchResult(
            ok=False, message="refused"
        ),
    )
    monkeypatch.setattr(
        supervisor.streams, "write_stderr", lambda *, text: results.append(("stderr", text))
    )

    assert (
        supervisor._relaunch_handler(
            args=SimpleNamespace(
                topic="alpha",
                target="pane",
                invoker="operator",
                runtime=None,
                model=None,
                wrapper=None,
            )
        )
        == 1
    )
    assert results == [("stderr", "refused\n")]
