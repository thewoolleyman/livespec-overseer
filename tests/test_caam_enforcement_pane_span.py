"""The per-pane caam enforcement decision span (work-item overseer-m7qrgp.2).

ONE ``caam.enforcement.pane`` record per pane per pass, emitted on the fail-open
seam from overseer-m7qrgp.1. This is the load-bearing span: it turns the
2026-08-30/31 "livespec-overseer-foreman unknown->fable" incident into a
filterable query — WHICH transcript resolved, WHAT model the pane read, from
WHICH source, and WHY enforcement drove it.

The distinction the incident actually needed is the last leg of the transcript
tests below: a transcript that RESOLVES but attests no model reads as unknown,
and reads identically to a session whose transcript was never found at all. Only
the span separates them, because it carries ``caam.transcript.path`` beside
``model.read``.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent


def decision_module() -> ModuleType:
    """The decision vocabulary and record builder.

    The module FILE is asserted before the import so the Red fails on a genuine
    assertion rather than dying at collection with a ``ModuleNotFoundError``.
    """
    assert (ROOT / "overseer" / "_caam_pane_decision.py").is_file()
    return importlib.import_module("_caam_pane_decision")


def sessions_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_sessions.py").is_file()
    return importlib.import_module("caam_sessions")


def enforcement_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_enforcement.py").is_file()
    return importlib.import_module("caam_enforcement")


def transcript_module() -> ModuleType:
    assert (ROOT / "overseer" / "_caam_transcript_model.py").is_file()
    return importlib.import_module("_caam_transcript_model")


def seam_module() -> ModuleType:
    assert (ROOT / "overseer" / "_caam_span_seam.py").is_file()
    return importlib.import_module("_caam_span_seam")


def collector(*, records: list[dict[str, object]]) -> Callable[..., None]:
    def emit(*, record: Mapping[str, object]) -> None:
        records.append(dict(record))

    return emit


def one_span(*, records: list[dict[str, object]]) -> dict[str, object]:
    assert len(records) == 1
    span = records[0]
    # Every leg owes these three, whatever it decided.
    assert span["event"] == "caam.enforcement.pane"
    assert span["caam.session"] == "alpha-foreman"
    assert span["model.want"] == "fable"
    return span


def write_transcript(*, home: Path, session_id: str, lines: list[str]) -> Path:
    path = home / ".claude" / "projects" / "-work" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# enforce_session_models -- one span per pane per pass, one per decision.
# ---------------------------------------------------------------------------


def test_a_pane_already_on_the_wanted_model_reports_skip_already_set() -> None:
    """Case (i): the read equals the want, so nothing is driven and nothing is said."""
    sessions = sessions_module()
    decisions = decision_module()
    transcripts = transcript_module()
    records: list[dict[str, object]] = []
    calls: list[tuple[str, str]] = []
    pane = sessions.SessionModel(
        session="alpha-foreman",
        session_id="sid-already",
        model="fable",
        source=transcripts.READ_SOURCE_ASSISTANT,
        transcript="/home/u/.claude/projects/-work/sid-already.jsonl",
    )

    messages = sessions.enforce_session_models(
        panes=(pane,),
        state={},
        want="fable",
        now=1000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        emit_event=collector(records=records),
    )

    assert messages == []
    assert calls == []
    span = one_span(records=records)
    assert span["caam.decision"] == decisions.DECISION_SKIP_ALREADY_SET
    assert span["caam.driven"] is False
    assert span["model.read"] == "fable"
    assert span["model.read.source"] == "assistant-message"
    assert span["caam.session_id"] == "sid-already"
    assert span["caam.transcript.path"] == "/home/u/.claude/projects/-work/sid-already.jsonl"
    assert span["caam.picker.outcome"] == "none"
    assert span["ts"] == "1970-01-01T00:16:40.000000Z"


def test_an_unknown_read_reports_the_drive_and_the_actuators_own_outcome() -> None:
    """Case (ii), driving half: unknown is not a model, and no transcript resolved."""
    sessions = sessions_module()
    decisions = decision_module()
    records: list[dict[str, object]] = []
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid-blind", model=None)

    def set_model(*, session: str, model: str) -> str:
        del session, model
        return "switched"

    messages = sessions.enforce_session_models(
        panes=(pane,),
        state={},
        want="fable",
        now=1000.0,
        set_model=set_model,
        emit_event=collector(records=records),
    )

    assert messages == ["alpha-foreman unknown->fable"]
    span = one_span(records=records)
    assert span["caam.decision"] == decisions.DECISION_DRIVE
    assert span["caam.driven"] is True
    assert span["model.read"] == "unknown"
    assert span["model.read.source"] == "none"
    assert span["caam.transcript.path"] == "none"
    assert span["caam.picker.outcome"] == "switched"


def test_an_unknown_read_already_verified_reports_the_skip_instead_of_a_drive() -> None:
    """Case (ii), skipping half: the one verifying drive is spent, so this pass holds."""
    sessions = sessions_module()
    decisions = decision_module()
    records: list[dict[str, object]] = []
    calls: list[tuple[str, str]] = []
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid-blind", model=None)

    messages = sessions.enforce_session_models(
        panes=(pane,),
        state={"models_unknown": {"alpha-foreman": "fable"}},
        want="fable",
        now=1000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        emit_event=collector(records=records),
    )

    assert messages == []
    assert calls == []
    span = one_span(records=records)
    assert span["caam.decision"] == decisions.DECISION_SKIP_UNKNOWN_VERIFIED
    assert span["caam.driven"] is False
    assert span["model.read"] == "unknown"
    assert span["model.read.source"] == "none"


def test_a_busy_pane_reports_busy_and_drives_nothing() -> None:
    """Case (iii): the pane is not idle, so the picker is never opened."""
    sessions = sessions_module()
    decisions = decision_module()
    records: list[dict[str, object]] = []
    calls: list[tuple[str, str]] = []
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid-busy", model="opus")

    def pane_idle(*, session: str) -> bool:
        del session
        return False

    messages = sessions.enforce_session_models(
        panes=(pane,),
        state={},
        want="fable",
        now=1000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        pane_idle=pane_idle,
        emit_event=collector(records=records),
    )

    assert messages == ["alpha-foreman busy(opus->fable)"]
    assert calls == []
    span = one_span(records=records)
    assert span["caam.decision"] == decisions.DECISION_BUSY
    assert span["caam.driven"] is False
    assert span["model.read"] == "opus"
    assert span["caam.picker.outcome"] == "none"


def test_an_operator_set_pane_reports_the_kept_decision() -> None:
    """Case (iv): a known read diverging from enforcement's own set-record is the operator's."""
    sessions = sessions_module()
    decisions = decision_module()
    records: list[dict[str, object]] = []
    calls: list[tuple[str, str]] = []
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid-op", model="sonnet")

    messages = sessions.enforce_session_models(
        panes=(pane,),
        state={"models": {"alpha-foreman": {"want": "fable", "at": 1.0}}},
        want="fable",
        now=1_000_000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        respect_operator_set=True,
        emit_event=collector(records=records),
    )

    assert messages == ["alpha-foreman operator-set(sonnet) kept"]
    assert calls == []
    span = one_span(records=records)
    assert span["caam.decision"] == decisions.DECISION_OPERATOR_SET_KEPT
    assert span["caam.driven"] is False
    assert span["model.read"] == "sonnet"


def test_a_recently_set_pane_is_reported_apart_from_one_already_on_the_model() -> None:
    """The time-boxed memo and an agreeing read are DIFFERENT reasons to hold.

    Enforcement short-circuits both to `continue`, and before this span the two were
    indistinguishable from outside. A suppression memo masking a pane that never
    actually moved is precisely the shape the incident wore.
    """
    sessions = sessions_module()
    decisions = decision_module()
    records: list[dict[str, object]] = []
    calls: list[tuple[str, str]] = []
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid-memo", model="opus")

    messages = sessions.enforce_session_models(
        panes=(pane,),
        state={"models": {"alpha-foreman": {"want": "fable", "at": 999.0}}},
        want="fable",
        now=1000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        emit_event=collector(records=records),
    )

    assert messages == []
    assert calls == []
    span = one_span(records=records)
    assert span["caam.decision"] == decisions.DECISION_SKIP_RECENTLY_SET
    assert span["caam.driven"] is False
    assert span["model.read"] == "opus"


def test_a_dry_run_pass_reports_would_without_driving() -> None:
    sessions = sessions_module()
    decisions = decision_module()
    records: list[dict[str, object]] = []
    calls: list[tuple[str, str]] = []
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid-dry", model="opus")

    messages = sessions.enforce_session_models(
        panes=(pane,),
        state={},
        want="fable",
        now=1000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        dry_run=True,
        emit_event=collector(records=records),
    )

    assert messages == ["alpha-foreman would opus->fable"]
    assert calls == []
    span = one_span(records=records)
    assert span["caam.decision"] == decisions.DECISION_WOULD
    assert span["caam.driven"] is False


def test_an_actuator_that_fails_reports_the_error_outcome_and_still_raises() -> None:
    """A drive that blows up is the one shape a message-only report loses entirely.

    `caam_enforcement` collapses it to `SKIPPED(<type>)` for the operator table, so the
    span has to be emitted BEFORE the exception continues on its way — and it reports
    `caam.driven` false, because an attempt that raised did not settle the pane.
    """
    sessions = sessions_module()
    decisions = decision_module()
    records: list[dict[str, object]] = []
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid-boom", model="opus")

    def set_model(*, session: str, model: str) -> str:
        raise RuntimeError(f"tmux gone for {session}->{model}")

    with pytest.raises(RuntimeError):
        _ = sessions.enforce_session_models(
            panes=(pane,),
            state={},
            want="fable",
            now=1000.0,
            set_model=set_model,
            emit_event=collector(records=records),
        )

    span = one_span(records=records)
    assert span["caam.decision"] == decisions.DECISION_DRIVE
    assert span["caam.driven"] is False
    assert span["caam.picker.outcome"] == "error"


# ---------------------------------------------------------------------------
# The read the span reports: model, source, and the transcript it came from.
# ---------------------------------------------------------------------------


def test_an_assistant_entry_and_a_model_answer_are_reported_as_distinct_sources(
    *, tmp_path: Path
) -> None:
    transcripts = transcript_module()
    assistant = write_transcript(
        home=tmp_path,
        session_id="sid-assistant",
        lines=[json.dumps({"message": {"model": "claude-opus-4-8"}})],
    )
    answered = write_transcript(
        home=tmp_path,
        session_id="sid-answer",
        lines=[
            json.dumps(
                {
                    "message": {
                        "content": (
                            "<local-command-stdout>Set model to Fable 5</local-command-stdout>"
                        )
                    }
                }
            )
        ],
    )

    from_assistant = transcripts.pane_read(home=tmp_path, session_id="sid-assistant")
    from_answer = transcripts.pane_read(home=tmp_path, session_id="sid-answer")

    assert (from_assistant.model, from_assistant.source) == ("opus", "assistant-message")
    assert from_assistant.transcript == str(assistant)
    assert (from_answer.model, from_answer.source) == ("fable", "model-answer")
    assert from_answer.transcript == str(answered)


def test_a_resolved_transcript_that_attests_nothing_is_not_an_unresolved_one(
    *, tmp_path: Path
) -> None:
    """The incident's own shape: unknown read, but the file WAS found.

    `pane_model` collapses both to None, which is why the pass drove. The span keeps
    them apart, so a Honeycomb query can ask "unknown with a transcript" — a scan that
    found no attesting line — separately from "unknown with none" — a session whose
    transcript was never located at all.
    """
    transcripts = transcript_module()
    silent = write_transcript(
        home=tmp_path,
        session_id="sid-silent",
        lines=[json.dumps({"type": "user", "message": {"content": "hello"}})],
    )

    resolved = transcripts.pane_read(home=tmp_path, session_id="sid-silent")
    unresolved = transcripts.pane_read(home=tmp_path, session_id="sid-absent")

    assert (resolved.model, resolved.source, resolved.transcript) == (
        None,
        "none",
        str(silent),
    )
    assert (unresolved.model, unresolved.source, unresolved.transcript) == (None, "none", None)
    assert transcripts.pane_model(home=tmp_path, session_id="sid-silent") is None


# ---------------------------------------------------------------------------
# The production pass: discovery fills the read, the env-configured seam ships it.
# ---------------------------------------------------------------------------


def test_the_production_pass_exports_one_pane_span_through_the_configured_seam(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enforcement = enforcement_module()
    requests: list[dict[str, object]] = []
    # Patch the module object the SEAM holds. This package imports FLAT, so
    # `overseer._supervisor_otel` is a different module object than the one the seam
    # resolves at call time, and patching that one silently does nothing.
    monkeypatch.setattr(
        seam_module()._supervisor_otel,
        "default_emitter",
        lambda *, request: requests.append(dict(request)),
    )
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://api.honeycomb.io")
    monkeypatch.setenv("HONEYCOMB_INGEST_KEY_LIVESPEC", "key")
    transcript = write_transcript(
        home=tmp_path,
        session_id="sid-1",
        lines=[json.dumps({"message": {"model": "claude-opus-4-8"}})],
    )

    _ = enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=("alpha-foreman",),
        active_fable=58.0,
        foreman_model=None,
        now=1000.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_idle=lambda **_: True,
        set_model=lambda **_: None,
        state={},
    )

    assert len(requests) == 1
    payload = cast(dict[str, Any], requests[0]["payload"])
    span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["name"] == "caam.enforcement.pane"
    attributes = {item["key"]: item["value"] for item in span["attributes"]}
    assert attributes["caam.session"] == {"stringValue": "alpha-foreman"}
    assert attributes["caam.session_id"] == {"stringValue": "sid-1"}
    assert attributes["caam.transcript.path"] == {"stringValue": str(transcript)}
    assert attributes["model.read"] == {"stringValue": "opus"}
    assert attributes["model.read.source"] == {"stringValue": "assistant-message"}
    assert attributes["model.want"] == {"stringValue": "fable"}
    assert attributes["caam.decision"] == {"stringValue": "drive"}
    assert attributes["caam.driven"] == {"boolValue": True}
    assert attributes["caam.picker.outcome"] == {"stringValue": "none"}


def test_an_unconfigured_host_exports_no_pane_span_and_enforces_normally(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seam's no-op is the default on every host that never set an endpoint."""
    enforcement = enforcement_module()
    requests: list[dict[str, object]] = []
    # Patch the module object the SEAM holds. This package imports FLAT, so
    # `overseer._supervisor_otel` is a different module object than the one the seam
    # resolves at call time, and patching that one silently does nothing.
    monkeypatch.setattr(
        seam_module()._supervisor_otel,
        "default_emitter",
        lambda *, request: requests.append(dict(request)),
    )
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    calls: list[tuple[str, str]] = []

    lines = enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=("alpha-foreman",),
        active_fable=58.0,
        foreman_model=None,
        now=1000.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_idle=lambda **_: True,
        set_model=lambda *, session, model: calls.append((session, model)),
        state={},
    )

    assert requests == []
    assert calls == [("alpha-foreman", "fable")]
    assert "alpha-foreman unknown->fable" in lines[-1]
