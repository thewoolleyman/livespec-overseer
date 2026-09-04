"""The pass-level caam enforcement span (work-item overseer-m7qrgp.3).

ONE ``caam.enforcement.pass`` record per ``run_pass`` call, on the same
fail-open, env-gated seam as the per-pane spans from overseer-m7qrgp.2 -- and
the parent of those pane spans, so a pass and its per-pane decisions form one
trace.

Two properties carry the weight here, and both are about what a pane span
CANNOT say. The first is the pass's CONDITIONS: which account was active,
whether its Fable was spent, what the foremen were therefore wanted on, and
which sessions were exceptions to that. Those are identical for every pane in a
pass, so they belong to the pass, and the 2026-08-30/31
"livespec-overseer-foreman unknown->fable" incident turned on exactly them.

The second is COVERAGE OF A PASS THAT DID NOTHING. A pass that never resolved an
active profile emits no pane spans at all, so a pane-only record set is silent
in precisely the case an operator is trying to explain. The third test below is
that case, and it asserts the named absents rather than defaulted readings: a
Fable balance reported as `false` when the pass never took one would be a
fabricated measurement indistinguishable from a genuine exhaustion.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import caam_enforcement
import pytest
from caam_anthropic_loop import Flags
from caam_decision import UsageRecord
from caam_profile_state import STATE_REL

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PASS_EVENT = "caam.enforcement.pass"
PANE_EVENT = "caam.enforcement.pane"
OPEN_AT = 1000.0
CLOSE_AT = 1002.5


def pass_span_module() -> ModuleType:
    """The pass record shape and the trace its pane spans hang from.

    The module FILE is asserted before the import so the Red fails on a genuine
    assertion rather than dying at collection with a ``ModuleNotFoundError``.
    """
    assert (ROOT / "overseer" / "_caam_pass_span.py").is_file()
    return importlib.import_module("_caam_pass_span")


def span_module() -> ModuleType:
    assert (ROOT / "overseer" / "_caam_span.py").is_file()
    return importlib.import_module("_caam_span")


def pass_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_anthropic_pass.py").is_file()
    return importlib.import_module("caam_anthropic_pass")


def seam_module() -> ModuleType:
    assert (ROOT / "overseer" / "_caam_span_seam.py").is_file()
    return importlib.import_module("_caam_span_seam")


def collector(*, records: list[dict[str, object]]) -> Callable[..., None]:
    def emit(*, record: Mapping[str, object]) -> None:
        records.append(dict(record))

    return emit


def stepped_clock() -> Callable[[], float]:
    """Open at `OPEN_AT`, close at `CLOSE_AT`, so the wall clock is a fixed 2.5s."""
    ticks: Iterator[float] = iter((OPEN_AT, CLOSE_AT))

    def clock() -> float:
        return next(ticks)

    return clock


def only_pass_span(*, records: list[dict[str, object]]) -> dict[str, object]:
    spans = [record for record in records if record["event"] == PASS_EVENT]
    assert len(spans) == 1
    return spans[0]


def pane_spans(*, records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [record for record in records if record["event"] == PANE_EVENT]


# ---------------------------------------------------------------------------
# An enforcing pass: the conditions it ran under, and what came of it.
# ---------------------------------------------------------------------------


def test_one_enforcing_pass_emits_exactly_one_span_carrying_its_conditions(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = pass_module()
    records: list[dict[str, object]] = []
    home = caam_home(tmp_path=tmp_path, model="claude-opus-5")
    patch_production_model_boundaries(monkeypatch=monkeypatch)

    code = drive_pass(
        module=module,
        home=home,
        flags=flags(),
        fable=42.0,
        records=records,
    )

    assert code == 0
    span = only_pass_span(records=records)
    assert span["ts"] == "1970-01-01T00:16:40.000000Z"
    assert span["caam.account"] == "active"
    assert span["caam.enforcement.reached"] is True
    assert span["caam.fable.balance"] == "left"
    assert span["model.want.foreman"] == "fable"
    assert span["caam.pane.count"] == 1
    assert span["caam.session_models.exceptions"] == "none"
    assert span["caam.outcome"] == "alpha-foreman opus->fable"
    assert span["caam.exit_code"] == 0
    assert span["caam.wall_clock_seconds"] == CLOSE_AT - OPEN_AT
    assert span["caam.dry_run"] is False


def test_the_pane_spans_of_a_pass_hang_from_its_pass_span(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One pass and its per-pane decisions are ONE trace, not two unrelated records."""
    module = pass_module()
    spans = pass_span_module()
    wire = span_module()
    records: list[dict[str, object]] = []
    home = caam_home(tmp_path=tmp_path, model="claude-opus-5")
    patch_production_model_boundaries(monkeypatch=monkeypatch)

    _ = drive_pass(module=module, home=home, flags=flags(), fable=42.0, records=records)

    span = only_pass_span(records=records)
    panes = pane_spans(records=records)
    assert len(panes) == 1
    # The module's exported wire name is the literal this file selects on. It is
    # bound as ROTATION_EVENT rather than PASS_EVENT because ruff's S105 reads a
    # constant named for a "pass" as a hardcoded credential; the WIRE name is the
    # one that has to stay stable, so that is what this pins.
    assert spans.ROTATION_EVENT == PASS_EVENT
    # The pass names its own trace and span; the pane names the same trace and
    # the pass as its parent, and mints its own span id on the wire.
    assert isinstance(span[wire.TRACE_ID_KEY], str)
    assert wire.PARENT_SPAN_ID_KEY not in span
    assert panes[0][wire.TRACE_ID_KEY] == span[wire.TRACE_ID_KEY]
    assert panes[0][wire.PARENT_SPAN_ID_KEY] == span[wire.SPAN_ID_KEY]


def test_a_dry_run_reports_an_exhausted_balance_and_the_exceptions_in_effect(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other side of every conditional attribute, in one pass.

    A spent Fable allowance, a session pinned by `--session-model`, and a pass
    that drove nothing because it was told not to.
    """
    module = pass_module()
    records: list[dict[str, object]] = []
    home = caam_home(tmp_path=tmp_path, model="claude-fable-5")
    patch_production_model_boundaries(monkeypatch=monkeypatch)

    code = drive_pass(
        module=module,
        home=home,
        flags=flags(dry_run=True, session_models=(("alpha-foreman", "opus"),)),
        fable=100.0,
        records=records,
    )

    assert code == 0
    span = only_pass_span(records=records)
    assert span["caam.fable.balance"] == "exhausted"
    assert span["model.want.foreman"] == "opus"
    assert span["caam.session_models.exceptions"] == "exceptions: alpha-foreman=opus"
    assert span["caam.outcome"] == "alpha-foreman would fable->opus"
    assert span["caam.dry_run"] is True


# ---------------------------------------------------------------------------
# A pass that never reached enforcement is the case a pane-only record set loses.
# ---------------------------------------------------------------------------


def test_a_pass_that_resolves_no_active_profile_still_emits_one_named_absent_span(
    *, tmp_path: Path
) -> None:
    module = pass_module()
    spans = pass_span_module()
    records: list[dict[str, object]] = []
    (tmp_path / ".local/share/caam/vault/claude/active").mkdir(parents=True)

    code = module.run_pass(
        flags=flags(),
        home=tmp_path,
        now=1234.0,
        stdout=[].append,
        caam_runner=lambda **_: no_active_profile_process(),
        save_state=lambda **_: None,
        clock=stepped_clock(),
        emit_pass_event=collector(records=records),
    )

    assert code == 2
    assert pane_spans(records=records) == []
    span = only_pass_span(records=records)
    assert span["caam.account"] == spans.ACCOUNT_NONE
    assert span["caam.enforcement.reached"] is False
    assert span["caam.fable.balance"] == spans.FABLE_UNKNOWN
    assert span["model.want.foreman"] == spans.FOREMAN_WANT_NONE
    assert span["caam.pane.count"] == 0
    assert span["caam.session_models.exceptions"] == spans.EXCEPTIONS_NONE
    assert span["caam.outcome"] == spans.OUTCOME_NOT_REACHED
    assert span["caam.exit_code"] == 2
    assert span["caam.wall_clock_seconds"] == CLOSE_AT - OPEN_AT


# ---------------------------------------------------------------------------
# The wire: the parentage rides as OTLP span fields, never as attributes.
# ---------------------------------------------------------------------------


def test_the_production_seam_exports_the_pass_span_as_the_parent_of_its_pane_span(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = pass_module()
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
    home = caam_home(tmp_path=tmp_path, model="claude-opus-5")
    patch_production_model_boundaries(monkeypatch=monkeypatch)

    code = module.run_pass(
        flags=flags(),
        home=home,
        now=1234.0,
        stdout=[].append,
        caam_runner=lambda **_: active_profile_process(),
        fetcher=usage_fetcher(fable=42.0),
        save_state=lambda **_: None,
        switch_account=lambda **_: None,
        agent_runner=lambda **_: agent_process(),
        clock=stepped_clock(),
    )

    assert code == 0
    exported = [wire_span(request=request) for request in requests]
    pane = next(span for span in exported if span["name"] == PANE_EVENT)
    root = next(span for span in exported if span["name"] == PASS_EVENT)
    assert root["parentSpanId"] == ""
    assert pane["traceId"] == root["traceId"]
    assert pane["parentSpanId"] == root["spanId"]
    assert pane["spanId"] != root["spanId"]
    # Parentage is an OTLP span FIELD; shipping it as an attribute too would make
    # a reader group traces by a key that only sometimes exists.
    attributes = {item["key"] for item in cast(list[Any], root["attributes"])}
    assert attributes.isdisjoint(
        {span_module().TRACE_ID_KEY, span_module().SPAN_ID_KEY, span_module().PARENT_SPAN_ID_KEY}
    )
    assert "caam.wall_clock_seconds" in attributes


# ---------------------------------------------------------------------------
# Harness.
# ---------------------------------------------------------------------------


def flags(
    *,
    dry_run: bool = False,
    session_models: tuple[tuple[str, str], ...] = (),
) -> Flags:
    return Flags(
        scheduled=True,
        force=False,
        dry_run=dry_run,
        no_models=False,
        no_warm=True,
        foreman_model=None,
        session_models=session_models,
    )


def drive_pass(
    *,
    module: ModuleType,
    home: Path,
    flags: Flags,
    fable: float,
    records: list[dict[str, object]],
) -> int:
    return cast(
        int,
        module.run_pass(
            flags=flags,
            home=home,
            now=1234.0,
            stdout=[].append,
            caam_runner=lambda **_: active_profile_process(),
            fetcher=usage_fetcher(fable=fable),
            save_state=lambda **_: None,
            switch_account=lambda **_: None,
            agent_runner=lambda **_: agent_process(),
            clock=stepped_clock(),
            emit_pass_event=collector(records=records),
        ),
    )


def wire_span(*, request: dict[str, object]) -> dict[str, object]:
    payload = cast(dict[str, Any], request["payload"])
    return cast(dict[str, object], payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0])


def patch_production_model_boundaries(*, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(caam_enforcement, "real_picker_tmux", lambda: SilentTmux(), raising=False)
    monkeypatch.setattr(caam_enforcement, "_sleep", lambda seconds: None, raising=False)
    monkeypatch.setattr(caam_enforcement, "proc_children", lambda *, pid: (), raising=False)
    monkeypatch.setattr(
        caam_enforcement,
        "proc_environ",
        lambda *, pid: b"CLAUDE_CODE_SESSION_ID=sid-1\0" if pid == 101 else None,
        raising=False,
    )


class SilentTmux:
    """One idle foreman pane whose picker keystrokes go nowhere.

    The pane's model is read from the transcript, never from this screen, so an
    idle prompt is the whole contract the enforcement path needs from tmux here.
    """

    def list_sessions(self) -> list[str]:
        return ["alpha-foreman"]

    def pane_pid(self, *, session: str) -> int:
        del session
        return 101

    def capture_pane(self, *, session: str) -> str:
        del session
        return "❯"

    def send_keys(self, *, session: str, keys: str) -> bool:
        del session, keys
        return True

    def send_literal_keys(self, *, session: str, text: str) -> bool:
        del session, text
        return True


def caam_home(*, tmp_path: Path, model: str) -> Path:
    home = tmp_path / "home"
    vault_profile = home / ".local/share/caam/vault/claude/active"
    projects = home / ".claude/projects/project"
    settings = home / ".claude/settings.json"
    vault_profile.mkdir(parents=True)
    projects.mkdir(parents=True)
    settings.write_text("{}", encoding="utf-8")
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": "account-1"}}),
        encoding="utf-8",
    )
    (vault_profile / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": "account-1"}}),
        encoding="utf-8",
    )
    (vault_profile / ".credentials.json").write_text("{}", encoding="utf-8")
    (projects / "sid-1.jsonl").write_text(
        json.dumps({"message": {"model": model}}) + "\n",
        encoding="utf-8",
    )
    state_path = home / STATE_REL
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{}", encoding="utf-8")
    return home


def usage_fetcher(*, fable: float) -> Callable[..., tuple[UsageRecord | None, str | None]]:
    record = UsageRecord(
        five_hour_remaining=90.0,
        seven_day_remaining=90.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None if fable is None else 100.0 - fable,
        fable_resets_at=None,
    )

    def fetcher(**_: Any) -> tuple[UsageRecord | None, str | None]:
        return record, None

    return fetcher


def active_profile_process() -> Any:
    return type(
        "Completed",
        (),
        {
            "returncode": 0,
            "stdout": json.dumps({"tools": [{"tool": "claude", "active_profile": "active"}]}),
        },
    )()


def no_active_profile_process() -> Any:
    return type("Completed", (), {"returncode": 1, "stdout": ""})()


def agent_process() -> Any:
    return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
