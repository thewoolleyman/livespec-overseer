"""The sanctioned operator relaunch is a separate, non-destructive surface."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import herdr_adapter
import herdr_identity
import herdr_write
import pane_router
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
    codex = entrypoint._profile_for_request(
        track=track,
        request=_request(runtime="codex", model="gpt-5.1-codex"),
    )
    assert codex.model_profile == {
        "harness": "codex",
        "model": "gpt-5.1-codex",
        "wrapper": None,
    }
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


def test_herdr_relaunch_submits_the_launch_as_one_native_input(*, tmp_path: Path) -> None:
    """A Herdr shell launch must not rely on tmux's separate Enter route."""
    entrypoint = importlib.import_module("out_of_band_relaunch")
    target = herdr_identity.HerdrPaneTarget(
        socket_path="/run/herdr-test.sock",
        server_pid=41,
        server_starttime="777",
        pane_id="w1:p1",
    )
    coordinate = herdr_identity.encode_herdr_target(target=target)
    calls: list[tuple[herdr_identity.HerdrPaneTarget, str, str, dict[str, str | None]]] = []

    class Writer:
        def bracketed_paste(self, **_kwargs: object) -> herdr_write.WriteOutcome:
            return herdr_write.WriteOutcome(
                ok=False, error="not the launch route", effect_unknown=False
            )

        def launch(
            self,
            *,
            target: herdr_identity.HerdrPaneTarget,
            cwd: str,
            command: str,
            env: dict[str, str | None],
        ) -> herdr_write.WriteOutcome:
            calls.append((target, cwd, command, env))
            return herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)

    driver = pane_router.MixedPaneDriver(herdr=object(), herdr_writer=Writer())
    plan = entrypoint.ClaudeLaunchPlan(command="claude --model claude-opus", env={"MODEL": None})

    assert entrypoint._launch_at_shell(
        sup=SimpleNamespace(tmux=driver),
        track=_track(tmp_path=tmp_path),
        target=coordinate,
        plan=plan,
    )
    assert calls == [(target, str(tmp_path), "claude --model claude-opus", {"MODEL": None})]


def test_herdr_relaunch_refreshes_a_preflight_cached_shell_before_confirming_launch(
    *, monkeypatch, tmp_path: Path
) -> None:
    """A bounded launch wait must not reuse the shell read that admitted the launch."""
    entrypoint = importlib.import_module("out_of_band_relaunch")
    target = herdr_identity.HerdrPaneTarget(
        socket_path="/run/herdr-test.sock",
        server_pid=41,
        server_starttime="777",
        pane_id="w1:p1",
    )
    coordinate = herdr_identity.encode_herdr_target(target=target)

    class Herdr:
        def __init__(self) -> None:
            self.command = "zsh"
            self.foreground_reads = 0

        def capture_pane(
            self, *, target: herdr_identity.HerdrPaneTarget, retain_ansi: bool = True
        ) -> herdr_adapter.PaneCapture:
            del target, retain_ansi
            return herdr_adapter.PaneCapture(
                ok=True,
                text=("─" * 40) + "\n❯ \n" + ("─" * 40) + "\n",
                error="",
            )

        def foreground(
            self, *, target: herdr_identity.HerdrPaneTarget
        ) -> herdr_adapter.ForegroundReading:
            self.foreground_reads += 1
            return herdr_adapter.ForegroundReading(
                ok=True,
                process=SimpleNamespace(name=self.command),
                error="",
            )

    herdr = Herdr()
    driver = pane_router.MixedPaneDriver(herdr=herdr)
    assert driver.pane_current_command(session=coordinate) == "zsh"
    track = _track(
        tmp_path=tmp_path,
        profile={"harness": "claude", "model": "claude-opus", "wrapper": None},
    )
    plan = entrypoint.ClaudeLaunchPlan(command="claude", env={})
    delivered: list[str] = []
    outcomes: list[str] = []
    sup = SimpleNamespace(tmux=driver, sleep=lambda _seconds: None, store_path=tmp_path / "store")

    monkeypatch.setattr(entrypoint, "_validated_launch", lambda **_kwargs: (track, track, plan))
    monkeypatch.setattr(entrypoint, "_start_intent", lambda **_kwargs: tmp_path / "intent")
    monkeypatch.setattr(
        entrypoint,
        "_finish_intent",
        lambda **kwargs: outcomes.append(str(kwargs["outcome"])),
    )
    monkeypatch.setattr(
        entrypoint,
        "_launch_at_shell",
        lambda **_kwargs: setattr(herdr, "command", "claude") or True,
    )
    monkeypatch.setattr(entrypoint, "resume_for_track", lambda **_kwargs: "resume")
    monkeypatch.setattr(
        entrypoint,
        "submit_prompt_result",
        lambda **kwargs: delivered.append(str(kwargs["text"])) or SimpleNamespace(submitted=True),
    )
    monkeypatch.setattr(entrypoint, "_identity_after_launch", lambda **_kwargs: "claude:1:2:alpha")
    monkeypatch.setattr(entrypoint, "_rebind", lambda **_kwargs: True)

    result = entrypoint.relaunch(
        request=_request(target=coordinate),
        sup=sup,
    )

    assert result.ok
    assert delivered == ["resume"]
    assert outcomes == ["succeeded"]
    assert herdr.foreground_reads == 2


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


def test_relaunch_requires_a_ready_input_box_before_submitting_resume(
    *, monkeypatch, tmp_path: Path
) -> None:
    """A fresh Claude pane must be ready before the resume prompt is pasted."""
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(
        tmp_path=tmp_path,
        profile={"harness": "claude", "model": "claude-opus", "wrapper": None},
    )
    request = _request()
    plan = entrypoint.ClaudeLaunchPlan(command="claude", env={})
    outcomes: list[str] = []
    submitted: list[str] = []
    sup = SimpleNamespace(store_path=tmp_path / "store")

    monkeypatch.setattr(entrypoint, "_validated_launch", lambda **kwargs: (track, track, plan))
    monkeypatch.setattr(entrypoint, "_start_intent", lambda **kwargs: tmp_path / "intent")
    monkeypatch.setattr(
        entrypoint,
        "_finish_intent",
        lambda **kwargs: outcomes.append(str(kwargs["outcome"])),
    )
    monkeypatch.setattr(entrypoint, "_launch_at_shell", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "await_pane", lambda **kwargs: True)
    monkeypatch.setattr(entrypoint, "await_input_box", lambda **kwargs: False)
    monkeypatch.setattr(
        entrypoint,
        "submit_prompt_result",
        lambda **kwargs: submitted.append(str(kwargs["text"])) or SimpleNamespace(submitted=True),
    )
    monkeypatch.setattr(entrypoint, "_identity_after_launch", lambda **kwargs: "identity")
    monkeypatch.setattr(entrypoint, "_rebind", lambda **kwargs: True)

    result = entrypoint.relaunch(request=request, sup=sup)

    assert result.ok is False
    assert "input box" in result.message
    assert submitted == []
    assert outcomes == ["resume_input_unavailable"]


def test_validation_refuses_unsafe_targets_before_an_intent_is_written(
    *, monkeypatch, tmp_path: Path
) -> None:
    """Topic, backend, shell and profile failures all reject before launch state."""
    entrypoint = importlib.import_module("out_of_band_relaunch")
    target = herdr_identity.encode_tmux_target(
        target=herdr_identity.TmuxPaneTarget(
            socket_path="/tmp/tmux-a.sock",
            server_pid=41,
            server_starttime="100",
            pane_id="%2",
        )
    )
    track = registry.PlanTrack(
        repo=str(tmp_path),
        topic="alpha",
        tmux=target,
        epic="overseer-alpha",
        model_profile={"harness": "claude", "model": "claude-opus", "wrapper": None},
    )
    tmux = SimpleNamespace(
        pane_id=lambda *, session: session,
        pane_current_command=lambda *, session: "bash",
    )
    sup = SimpleNamespace(tmux=tmux, store_path=tmp_path / "store")
    request = _request(target=target)

    accepted = entrypoint._validated_launch(request=request, sup=sup, tracks=[track])
    assert isinstance(accepted, tuple)
    assert accepted[0] == track
    assert entrypoint._profile_for_request(
        track=_track(tmp_path=tmp_path), request=request
    ) == _track(tmp_path=tmp_path)
    assert entrypoint._matching_track(topic="alpha", tracks=[track, track]) is None
    assert entrypoint._same_backend(recorded="tmux:broken", target=target) is False
    assert entrypoint._same_backend(recorded=target, target="herdr:broken") is False
    assert entrypoint._same_backend(recorded="legacy", target="legacy") is True
    assert entrypoint._same_backend(recorded="legacy", target=target) is False

    monkeypatch.setattr(entrypoint.registry, "read_valid_mapping", lambda **kwargs: [])
    assert (
        "recorded epic"
        in entrypoint._validated_launch(request=request, sup=sup, tracks=None).message
    )
    assert (
        "recorded epic" in entrypoint._validated_launch(request=request, sup=sup, tracks=[]).message
    )
    assert (
        "backend instance"
        in entrypoint._validated_launch(
            request=_request(target="different-pane"), sup=sup, tracks=[track]
        ).message
    )
    tmux.pane_id = lambda *, session: None
    assert (
        "idle interactive shell"
        in entrypoint._validated_launch(request=request, sup=sup, tracks=[track]).message
    )
    tmux.pane_id = lambda *, session: session
    tmux.pane_current_command = lambda *, session: "claude"
    assert (
        "idle interactive shell"
        in entrypoint._validated_launch(request=request, sup=sup, tracks=[track]).message
    )
    tmux.pane_current_command = lambda *, session: "bash"
    assert isinstance(
        entrypoint._validated_launch(
            request=_request(target=target, runtime="codex", model="gpt-5.1-codex"),
            sup=sup,
            tracks=[track],
        ),
        tuple,
    )
    stale = registry.PlanTrack(
        repo=str(tmp_path),
        topic="alpha",
        tmux=target,
        epic="overseer-alpha",
        model_profile={"harness": "claude", "model": "claude-opus", "wrapper": "/missing"},
    )
    assert (
        "stale launch profile"
        in entrypoint._validated_launch(request=request, sup=sup, tracks=[stale]).message
    )


def test_cli_handler_reports_relaunch_result_without_running_start(*, monkeypatch) -> None:
    """The sanctioned command delegates only to the non-destructive entrypoint."""
    supervisor = importlib.import_module("supervisor")
    result = SimpleNamespace(ok=False, message="relaunch REFUSED: unsafe")
    writes: list[str] = []
    args = SimpleNamespace(
        topic="alpha",
        target="target-pane",
        invoker="operator",
        runtime=None,
        model=None,
        wrapper=None,
    )
    monkeypatch.setattr(supervisor.out_of_band_relaunch, "relaunch", lambda **kwargs: result)
    monkeypatch.setattr(supervisor, "build_supervisor", lambda: object())
    monkeypatch.setattr(supervisor.streams, "write_stderr", lambda *, text: writes.append(text))

    assert supervisor._relaunch_handler(args=args) == 1
    assert writes == ["relaunch REFUSED: unsafe\n"]


def test_failed_launch_intent_records_the_failure_detail(*, tmp_path: Path) -> None:
    """A post-launch failure leaves the operator a durable error beside its outcome."""
    entrypoint = importlib.import_module("out_of_band_relaunch")
    track = _track(tmp_path=tmp_path)
    request = _request()
    intent = entrypoint._start_intent(track=track, request=request)

    result = entrypoint._record_failed_launch(
        intent=intent,
        track=track,
        request=request,
        outcome="launch_failed",
        message="relaunch FAILED: launch input was not accepted",
    )

    assert result.ok is False
    assert json.loads(intent.read_text(encoding="utf-8")).get("error") == (
        "relaunch FAILED: launch input was not accepted"
    )
