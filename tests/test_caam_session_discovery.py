"""Tests for caam session discovery, transcript model reads, and model-set memo."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Protocol, cast

__all__: list[str] = []


class SessionModelCtor(Protocol):
    def __call__(self, *, session: str, session_id: str, model: str | None) -> object: ...


class CaamSessionsModule(Protocol):
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
