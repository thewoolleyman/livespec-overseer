"""Tests for caam session discovery, transcript model reads, and model-set memo."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Protocol, cast

__all__: list[str] = []


class SessionModelCtor(Protocol):
    def __call__(self, *, session: str, session_id: str, model: str | None) -> object: ...


class CaamSessionsModule(Protocol):
    ModelSetter: type[object]
    PaneCapture: type[object]
    PanePid: type[object]
    PidToIntList: type[object]
    PidToOptionalBytes: type[object]
    SessionModel: SessionModelCtor

    def discover_session_models(
        self,
        *,
        session_names: tuple[str, ...],
        home: Path,
        pane_pid: object,
        children_of: object,
        environ_of: object,
        capture_pane: object,
    ) -> tuple[object, ...]: ...

    def enforce_session_models(
        self,
        *,
        panes: tuple[object, ...],
        state: dict[str, object],
        want: str,
        now: float,
        set_model: object,
    ) -> list[str]: ...

    def pane_model(self, *, home: Path, session_id: str) -> str | None: ...

    def newest_project_model_for_test(self, *, home: Path, project: str) -> str | None: ...


class CaamEnforcementModule(Protocol):
    def enforce_models(
        self,
        *,
        settings_path: Path,
        no_models: bool,
        **model_options: object,
    ) -> list[str]: ...


def caam_sessions_module() -> CaamSessionsModule:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_sessions.py"
    assert module_path.is_file()
    return cast(CaamSessionsModule, importlib.import_module("caam_sessions"))


def caam_enforcement_module() -> CaamEnforcementModule:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_enforcement.py"
    assert module_path.is_file()
    return cast(CaamEnforcementModule, importlib.import_module("caam_enforcement"))


def write_transcript(*, home: Path, project: str, session_id: str, models: list[str]) -> Path:
    path = home / ".claude" / "projects" / project / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        "".join(json.dumps({"message": {"model": model}}) + "\n" for model in models),
        encoding="utf-8",
    )
    return path


def high_effort_settings(*, tmp_path: Path) -> Path:
    settings = tmp_path / "settings.json"
    _ = settings.write_text(json.dumps({"effortLevel": "high"}), encoding="utf-8")
    return settings


def session_tree(*, session_ids: dict[str, str]) -> tuple[object, object, object]:
    roots = {session: index * 10 for index, session in enumerate(session_ids, start=1)}

    def pane_pid(*, session: str) -> int:
        return roots[session]

    def children_of(*, pid: int) -> list[int]:
        return [pid + 1] if pid in roots.values() else []

    def environ_of(*, pid: int) -> bytes:
        for session, root in roots.items():
            if pid == root + 1:
                return f"CLAUDE_CODE_SESSION_ID={session_ids[session]}".encode()
        return b""

    return pane_pid, children_of, environ_of


def test_session_discovery_seams_are_keyword_only_protocol_shapes() -> None:
    module = caam_sessions_module()
    seams = importlib.import_module("_seams")

    pane_pid_signature = inspect.signature(module.PanePid.__call__)
    pane_capture_signature = inspect.signature(module.PaneCapture.__call__)
    model_setter_signature = inspect.signature(module.ModelSetter.__call__)

    assert pane_pid_signature.parameters["session"].kind is inspect.Parameter.KEYWORD_ONLY
    assert pane_capture_signature.parameters["session"].kind is inspect.Parameter.KEYWORD_ONLY
    assert model_setter_signature.parameters["session"].kind is inspect.Parameter.KEYWORD_ONLY
    assert model_setter_signature.parameters["model"].kind is inspect.Parameter.KEYWORD_ONLY
    assert module.PidToIntList is seams.PidToIntList
    assert module.PidToOptionalBytes is seams.PidToOptionalBytes


def test_no_session_identifier_skips_pane_without_reading_status_line_or_setting_model(
    *, tmp_path: Path
):
    module = caam_sessions_module()
    set_calls: list[tuple[str, str]] = []
    capture_reads: list[str] = []

    def pane_pid(*, session: str) -> int:
        del session
        return 10

    def children_of(*, pid: int) -> list[int]:
        return [11] if pid == 10 else []

    def environ_of(*, pid: int) -> bytes:
        del pid
        return b"SHELL=/bin/bash\0"

    def capture_pane(*, session: str) -> str:
        capture_reads.append(session)
        return "claude-fable truncated"

    def set_model(*, session: str, model: str) -> None:
        set_calls.append((session, model))

    panes = module.discover_session_models(
        session_names=("worker-foreman",),
        home=tmp_path,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        capture_pane=capture_pane,
    )
    messages = module.enforce_session_models(
        panes=panes,
        state={},
        want="fable",
        now=1000.0,
        set_model=set_model,
    )

    assert panes == ()
    assert messages == []
    assert set_calls == []
    assert capture_reads == []


def test_transcript_is_resolved_by_session_identifier_not_newest_project_file(*, tmp_path: Path):
    module = caam_sessions_module()
    older = write_transcript(
        home=tmp_path,
        project="-work",
        session_id="sid-target",
        models=["claude-sonnet-5"],
    )
    newest_wrong = write_transcript(
        home=tmp_path,
        project="-work",
        session_id="sid-other",
        models=["claude-opus-5"],
    )
    older.touch()
    newest_wrong.touch()

    assert module.pane_model(home=tmp_path, session_id="sid-target") == "sonnet"
    assert module.newest_project_model_for_test(home=tmp_path, project="-work") == "opus"


def test_transcript_reader_uses_tail_and_last_model_mention_wins(*, tmp_path: Path):
    module = caam_sessions_module()
    path = tmp_path / ".claude" / "projects" / "-work" / "sid-tail.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        json.dumps({"message": {"model": "claude-opus-5"}})
        + "\n"
        + ("x" * 70_000)
        + "\n"
        + json.dumps({"message": {"model": "claude-fable-5"}})
        + "\n",
        encoding="utf-8",
    )

    assert module.pane_model(home=tmp_path, session_id="sid-tail") == "fable"


def test_unreadable_model_is_treated_as_may_need_setting(*, tmp_path: Path):
    module = caam_sessions_module()
    set_calls: list[tuple[str, str]] = []

    def set_model(*, session: str, model: str) -> None:
        set_calls.append((session, model))

    messages = module.enforce_session_models(
        panes=(
            module.SessionModel(session="worker-foreman", session_id="sid-missing", model=None),
        ),
        state={},
        want="fable",
        now=1000.0,
        set_model=set_model,
    )

    assert messages == ["model: worker-foreman -> fable"]
    assert set_calls == [("worker-foreman", "fable")]


def test_narrow_truncated_status_line_does_not_control_agent_classification(*, tmp_path: Path):
    module = caam_sessions_module()
    _ = write_transcript(
        home=tmp_path,
        project="-work",
        session_id="sid-narrow",
        models=["claude-opus-5"],
    )

    def pane_pid(*, session: str) -> int:
        del session
        return 20

    def children_of(*, pid: int) -> list[int]:
        return [21] if pid == 20 else []

    def environ_of(*, pid: int) -> bytes:
        return b"CLAUDE_CODE_SESSION_ID=sid-narrow\0" if pid == 21 else b""

    def capture_pane(*, session: str) -> str:
        del session
        return "claude-fa"

    panes = module.discover_session_models(
        session_names=("worker-foreman",),
        home=tmp_path,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        capture_pane=capture_pane,
    )

    assert panes == (
        module.SessionModel(session="worker-foreman", session_id="sid-narrow", model="opus"),
    )


def test_saved_memo_suppresses_repeat_within_window(*, tmp_path: Path):
    module = caam_enforcement_module()
    settings = tmp_path / "settings.json"
    _ = settings.write_text(json.dumps({"effortLevel": "high"}), encoding="utf-8")
    state_path = tmp_path / "state" / "state.json"
    calls: list[tuple[str, str]] = []

    def pane_pid(*, session: str) -> int:
        del session
        return 30

    def children_of(*, pid: int) -> list[int]:
        del pid
        return []

    def environ_of(*, pid: int) -> bytes:
        del pid
        return b"CLAUDE_CODE_SESSION_ID=sid-unreadable\0"

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    for now in (1000.0, 1001.0):
        messages = module.enforce_models(
            settings_path=settings,
            no_models=False,
            home=tmp_path,
            state_path=state_path,
            session_names=("worker-foreman",),
            want_model="fable",
            now=now,
            pane_pid=pane_pid,
            children_of=children_of,
            environ_of=environ_of,
            set_model=set_model,
        )
        assert messages == ([] if now == 1001.0 else ["model: worker-foreman -> fable"])

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["models"] == {"worker-foreman": {"at": 1000.0, "want": "fable"}}
    assert calls == [("worker-foreman", "fable")]


def test_model_orchestration_precedence_foreman_gets_fable_when_fable_left(
    *, tmp_path: Path
) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)
    session_ids = {
        "alpha-foreman": "sid-foreman",
        "alpha-worker": "sid-worker",
    }
    pane_pid, children_of, environ_of = session_tree(session_ids=session_ids)
    write_transcript(
        home=tmp_path,
        project="-alpha",
        session_id="sid-foreman",
        models=["claude-opus-5"],
    )
    write_transcript(
        home=tmp_path,
        project="-alpha",
        session_id="sid-worker",
        models=["claude-sonnet-5"],
    )
    calls: list[tuple[str, str]] = []

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    messages = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=tuple(session_ids),
        active_fable=25.0,
        now=1000.0,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=set_model,
    )

    assert messages == [
        "models: foremen want fable (active account Fable left); " "model: alpha-foreman -> fable"
    ]
    assert calls == [("alpha-foreman", "fable")]


def test_model_orchestration_precedence_every_session_gets_opus_when_fable_spent(
    *, tmp_path: Path
) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)
    session_ids = {
        "alpha-foreman": "sid-foreman",
        "alpha-worker": "sid-worker",
    }
    pane_pid, children_of, environ_of = session_tree(session_ids=session_ids)
    write_transcript(
        home=tmp_path,
        project="-alpha",
        session_id="sid-foreman",
        models=["claude-fable-5"],
    )
    write_transcript(
        home=tmp_path,
        project="-alpha",
        session_id="sid-worker",
        models=["claude-sonnet-5"],
    )
    calls: list[tuple[str, str]] = []

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    messages = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=tuple(session_ids),
        active_fable=100.0,
        now=1000.0,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=set_model,
    )

    assert messages == [
        "models: foremen want opus (active account Fable EXHAUSTED); "
        "model: alpha-foreman -> opus, model: alpha-worker -> opus"
    ]
    assert calls == [("alpha-foreman", "opus"), ("alpha-worker", "opus")]


def test_model_orchestration_treats_missing_fable_limit_as_exhausted(*, tmp_path: Path) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)
    session_ids = {"alpha-foreman": "sid-foreman"}
    pane_pid, children_of, environ_of = session_tree(session_ids=session_ids)
    write_transcript(
        home=tmp_path,
        project="-alpha",
        session_id="sid-foreman",
        models=["claude-fable-5"],
    )
    calls: list[tuple[str, str]] = []

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    messages = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=tuple(session_ids),
        active_fable=None,
        now=1000.0,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=set_model,
    )

    assert messages == [
        "models: foremen want opus (active account Fable EXHAUSTED); "
        "model: alpha-foreman -> opus"
    ]
    assert calls == [("alpha-foreman", "opus")]


def test_model_orchestration_foreman_suffix_match_is_exact(*, tmp_path: Path) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)
    session_ids = {
        "alpha-foreman": "sid-foreman",
        "alpha-foreman-helper": "sid-helper",
    }
    pane_pid, children_of, environ_of = session_tree(session_ids=session_ids)
    write_transcript(
        home=tmp_path,
        project="-alpha",
        session_id="sid-foreman",
        models=["claude-opus-5"],
    )
    write_transcript(
        home=tmp_path,
        project="-alpha",
        session_id="sid-helper",
        models=["claude-opus-5"],
    )
    calls: list[tuple[str, str]] = []

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    messages = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=tuple(session_ids),
        active_fable=25.0,
        now=1000.0,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=set_model,
    )

    assert messages == [
        "models: foremen want fable (active account Fable left); " "model: alpha-foreman -> fable"
    ]
    assert calls == [("alpha-foreman", "fable")]


def test_model_orchestration_records_per_session_failure_and_continues(*, tmp_path: Path) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)
    session_ids = {
        "alpha-foreman": "sid-foreman",
        "beta-foreman": "sid-beta",
    }
    pane_pid, children_of, environ_of = session_tree(session_ids=session_ids)
    for session_id in session_ids.values():
        write_transcript(
            home=tmp_path,
            project="-alpha",
            session_id=session_id,
            models=["claude-opus-5"],
        )
    calls: list[tuple[str, str]] = []

    def set_model(*, session: str, model: str) -> None:
        if session == "alpha-foreman":
            raise RuntimeError("picker broke")
        calls.append((session, model))

    messages = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=tuple(session_ids),
        active_fable=25.0,
        now=1000.0,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=set_model,
    )

    assert messages == [
        "models: foremen want fable (active account Fable left); "
        "alpha-foreman SKIPPED(RuntimeError), model: beta-foreman -> fable"
    ]
    assert calls == [("beta-foreman", "fable")]


def test_foreman_model_override_persists_and_overrides_only_foremen(*, tmp_path: Path) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)
    state_path = tmp_path / "state.json"
    session_ids = {
        "alpha-foreman": "sid-foreman",
        "alpha-worker": "sid-worker",
    }
    pane_pid, children_of, environ_of = session_tree(session_ids=session_ids)
    for session_id in session_ids.values():
        write_transcript(
            home=tmp_path,
            project="-alpha",
            session_id=session_id,
            models=["claude-fable-5"],
        )
    calls: list[tuple[str, str]] = []

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    first = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=state_path,
        session_names=tuple(session_ids),
        active_fable=25.0,
        foreman_model="opus",
        now=1000.0,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=set_model,
    )
    second = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=state_path,
        session_names=tuple(session_ids),
        active_fable=25.0,
        now=1001.0,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=set_model,
    )

    assert first == [
        "models: foreman override set to opus -- persists until --foreman-model=auto",
        "models: foremen want opus [pinned] (active account Fable left); "
        "model: alpha-foreman -> opus",
    ]
    assert second == [
        "models: foremen want opus [pinned] (active account Fable left); nothing to change"
    ]
    assert json.loads(state_path.read_text(encoding="utf-8"))["foreman_model"] == "opus"
    assert calls == [("alpha-foreman", "opus")]


def test_foreman_model_override_clear_values_restore_default(*, tmp_path: Path) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)

    for clear_value in ("auto", "", "none"):
        state_path = tmp_path / f"state-{clear_value or 'empty'}.json"
        _ = state_path.write_text(json.dumps({"foreman_model": "opus"}), encoding="utf-8")

        messages = module.enforce_models(
            settings_path=settings,
            no_models=False,
            home=tmp_path,
            state_path=state_path,
            session_names=(),
            active_fable=25.0,
            foreman_model=clear_value,
            now=1000.0,
            pane_pid=lambda *, session: 0,
            children_of=lambda *, pid: [],
            environ_of=lambda *, pid: b"",
            set_model=lambda *, session, model: None,
        )

        assert messages == [
            "models: foreman override cleared -- back to Fable unless spent",
            "models: foremen want fable (active account Fable left); nothing to change",
        ]
        assert "foreman_model" not in json.loads(state_path.read_text(encoding="utf-8"))


def test_foreman_model_override_ignores_unknown_and_corrupt_stored_values(
    *, tmp_path: Path
) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)
    state_path = tmp_path / "state.json"
    _ = state_path.write_text(json.dumps({"foreman_model": "opus"}), encoding="utf-8")

    ignored = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=state_path,
        session_names=(),
        active_fable=25.0,
        foreman_model="sonnet",
        now=1000.0,
        pane_pid=lambda *, session: 0,
        children_of=lambda *, pid: [],
        environ_of=lambda *, pid: b"",
        set_model=lambda *, session, model: None,
    )
    _ = state_path.write_text(json.dumps({"foreman_model": "sonnet"}), encoding="utf-8")
    corrupt = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=state_path,
        session_names=(),
        active_fable=25.0,
        now=1001.0,
        pane_pid=lambda *, session: 0,
        children_of=lambda *, pid: [],
        environ_of=lambda *, pid: b"",
        set_model=lambda *, session, model: None,
    )

    assert ignored == [
        "models: ignoring --foreman-model=sonnet (expected fable/opus or auto)",
        "models: foremen want opus [pinned] (active account Fable left); nothing to change",
    ]
    assert json.loads(state_path.read_text(encoding="utf-8"))["foreman_model"] == "sonnet"
    assert corrupt == ["models: foremen want fable (active account Fable left); nothing to change"]


def test_foreman_model_override_warns_but_honors_spent_fable_pin(*, tmp_path: Path) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)
    session_ids = {
        "alpha-foreman": "sid-foreman",
        "alpha-worker": "sid-worker",
    }
    pane_pid, children_of, environ_of = session_tree(session_ids=session_ids)
    for session_id in session_ids.values():
        write_transcript(
            home=tmp_path,
            project="-alpha",
            session_id=session_id,
            models=["claude-sonnet-5"],
        )
    calls: list[tuple[str, str]] = []

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    messages = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=tuple(session_ids),
        active_fable=100.0,
        foreman_model="fable",
        now=1000.0,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=set_model,
    )

    assert messages == [
        "models: foreman override set to fable -- persists until --foreman-model=auto",
        "models: WARNING foreman override pins fable but the active account's Fable is spent -- "
        "those sessions will be blocked",
        "models: foremen want fable [pinned] (active account Fable EXHAUSTED); "
        "model: alpha-foreman -> fable, model: alpha-worker -> opus",
    ]
    assert calls == [("alpha-foreman", "fable"), ("alpha-worker", "opus")]


def test_foreman_model_override_is_after_no_models_early_return(*, tmp_path: Path) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)
    state_path = tmp_path / "state.json"
    _ = state_path.write_text(json.dumps({"foreman_model": "opus"}), encoding="utf-8")

    messages = module.enforce_models(
        settings_path=settings,
        no_models=True,
        home=tmp_path,
        state_path=state_path,
        session_names=(),
        active_fable=25.0,
        foreman_model="auto",
        now=1000.0,
        pane_pid=lambda *, session: 0,
        children_of=lambda *, pid: [],
        environ_of=lambda *, pid: b"",
        set_model=lambda *, session, model: None,
    )

    assert messages == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["foreman_model"] == "opus"


def test_post_enforcement_save_failure_cannot_break_run(*, tmp_path: Path, monkeypatch) -> None:
    module = importlib.import_module("caam_enforcement")
    settings = high_effort_settings(tmp_path=tmp_path)

    def save_state(*, state: dict[str, object], state_path: Path) -> None:
        del state, state_path
        raise RuntimeError("disk full")

    monkeypatch.setattr(module, "save_state", save_state)

    assert module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=(),
        active_fable=25.0,
        now=1000.0,
        pane_pid=lambda *, session: 0,
        children_of=lambda *, pid: [],
        environ_of=lambda *, pid: b"",
        set_model=lambda *, session, model: None,
    ) == ["models: foremen want fable (active account Fable left); nothing to change"]


def test_model_orchestration_whole_pass_failure_is_advisory(*, tmp_path: Path) -> None:
    module = caam_enforcement_module()
    settings = high_effort_settings(tmp_path=tmp_path)

    def pane_pid(*, session: str) -> int:
        del session
        raise ValueError("tmux unavailable")

    def children_of(*, pid: int) -> list[int]:
        del pid
        return []

    def environ_of(*, pid: int) -> bytes:
        del pid
        return b""

    messages = module.enforce_models(
        settings_path=settings,
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=("alpha-foreman",),
        active_fable=25.0,
        now=1000.0,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=lambda *, session, model: None,
    )

    assert messages == [
        "models: enforcement failed (ValueError: tmux unavailable) -- "
        "table and rotation unaffected"
    ]
