"""The ROTATION half of a caam pass, as spans (work-item overseer-m7qrgp.4).

overseer-m7qrgp.2 and .3 made model ENFORCEMENT answerable: what a pass decided
about each foreman pane, and under what conditions. Neither says anything about
the other half of the same pass -- whether the idle accounts rotation depends on
are still switchable, when the next keep-warm wake is due, and what happened
when the pass actually tried to move. Those questions were answerable only from
a tmux scrollback.

Two records close that gap, and each is asserted here for what it says that the
operator line beside it cannot.

  - ``caam.warm.schedule`` names the ACCOUNT, the PROFILE whose expiry sets the
    next wake, and that WAKE. The operator line prints the instant alone, so a
    reader could not tell which idle account it belonged to, nor whether the
    warm stage had run at all -- which is why a pass with warming switched off
    emits one too, reporting ``caam.warm.maintained`` false rather than staying
    silent.

  - ``caam.rotation.switch`` names FROM, TO, ``switched`` and the TRIGGER. The
    boolean is the only attribute that says a credential actually moved: an exit
    code of zero does not, because a lock held by another pass also holds
    successfully. The last test below is exactly that case, driven through the
    real ``switch_account`` so the reason is the one the switch named itself
    rather than one this file invented.

Red: every leg asserts the new module FILE before importing it, so the failure
is a genuine assertion rather than a collection error.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from caam_decision import ProfileUsage, UsageRecord

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PASS_EVENT = "caam.enforcement.pass"
OPEN_AT = 1000.0
CLOSE_AT = 1002.5
NOW = 2_000.0
# A warm wake is the soonest FUTURE idle expiry plus the wake delay (15s default),
# so these two instants are the ones the spans below are expected to name.
IDLE_EXPIRY = 20_000.0
IDLE_WAKE_STAMP = "1970-01-01T05:33:35.000000Z"
REFRESHED_EXPIRY = 30_000.0
REFRESHED_WAKE_STAMP = "1970-01-01T08:20:15.000000Z"
# Past `warm_retry_s` (3600s default) measured from the never-attempted epoch, so
# the per-account rate backoff does not skip the one refresh that leg is about.
AFTER_BACKOFF = 10_000.0


def rotation_span_module() -> ModuleType:
    """The warm and switch record shapes, and the sink that hangs them off the pass.

    The module FILE is asserted before the import so the Red fails on a genuine
    assertion rather than dying at collection with a ``ModuleNotFoundError``.
    """
    assert (ROOT / "overseer" / "_caam_rotation_span.py").is_file()
    return importlib.import_module("_caam_rotation_span")


def warm_records_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_warm_records.py").is_file()
    return importlib.import_module("caam_warm_records")


def loop_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_anthropic_loop.py").is_file()
    return importlib.import_module("caam_anthropic_loop")


def switch_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_switch.py").is_file()
    return importlib.import_module("caam_switch")


def span_module() -> ModuleType:
    assert (ROOT / "overseer" / "_caam_span.py").is_file()
    return importlib.import_module("_caam_span")


# ---------------------------------------------------------------------------
# The warm stage: which account, which profile, and when the next wake is due.
# ---------------------------------------------------------------------------


def test_a_warm_pass_emits_one_span_naming_the_account_profile_and_next_wake(
    *, tmp_path: Path
) -> None:
    spans = rotation_span_module()
    wire = span_module()
    records: list[dict[str, object]] = []
    out: list[str] = []
    caam_home(tmp_path=tmp_path, idle_expiry=IDLE_EXPIRY)

    code = drive_pass(
        home=tmp_path,
        argv=[],
        fetcher=steady_fetcher(five_hour=10.0),
        records=records,
        out=out,
        agent_runner=StaticAgent(),
    )

    assert code == 0
    span = only(records=records, event=spans.WARM_SCHEDULE_EVENT)
    assert span["ts"] == "1970-01-01T00:33:20.000000Z"
    assert span["caam.account"] == "active"
    assert span["caam.warm.profile"] == "idle"
    assert span["caam.warm.next_wake"] == IDLE_WAKE_STAMP
    assert span["caam.warm.maintained"] is True
    # The idle snapshot is still valid, so the pass correctly attempted nothing:
    # keep-warm refreshes an EXPIRED credential and would only burn a request here.
    assert span["caam.warm.attempted"] == 0
    assert span["caam.warm.refreshed"] == 0
    # The operator line carries the same instant, and only the instant -- which is
    # the whole reason the span names the account it belongs to.
    assert "next-warm-wake: 1970-01-01T05:33:35Z" in out

    root = only(records=records, event=PASS_EVENT)
    assert span[wire.TRACE_ID_KEY] == root[wire.TRACE_ID_KEY]
    assert span[wire.PARENT_SPAN_ID_KEY] == root[wire.SPAN_ID_KEY]


def test_a_warm_pass_that_refreshed_an_expired_snapshot_counts_the_attempt(
    *, tmp_path: Path
) -> None:
    """An attempt and a refresh are separate counts, and the wake moves with them."""
    spans = rotation_span_module()
    records: list[dict[str, object]] = []
    out: list[str] = []
    caam_home(tmp_path=tmp_path, idle_expiry=1_000.0)

    code = drive_pass(
        home=tmp_path,
        argv=[],
        now=AFTER_BACKOFF,
        fetcher=steady_fetcher(five_hour=10.0),
        records=records,
        out=out,
        agent_runner=RefreshingAgent(expires_at_s=REFRESHED_EXPIRY),
    )

    assert code == 0
    span = only(records=records, event=spans.WARM_SCHEDULE_EVENT)
    assert span["caam.warm.maintained"] is True
    assert span["caam.warm.attempted"] == 1
    assert span["caam.warm.refreshed"] == 1
    assert span["caam.warm.profile"] == "idle"
    assert span["caam.warm.next_wake"] == REFRESHED_WAKE_STAMP


def test_a_pass_with_warming_switched_off_and_no_idle_account_names_both_absences(
    *, tmp_path: Path
) -> None:
    """A silent warm stage still emits a record, and every absence is NAMED.

    Omitting the keys would make a disabled warm stage indistinguishable from a
    healthy one with nothing to do, and would vary the key set by branch so no
    reader could group warm records at all.
    """
    spans = rotation_span_module()
    records: list[dict[str, object]] = []
    out: list[str] = []
    caam_home(tmp_path=tmp_path, idle_expiry=None)

    code = drive_pass(
        home=tmp_path,
        argv=["--no-warm"],
        fetcher=steady_fetcher(five_hour=10.0),
        records=records,
        out=out,
        agent_runner=StaticAgent(),
    )

    assert code == 0
    span = only(records=records, event=spans.WARM_SCHEDULE_EVENT)
    assert span["caam.warm.maintained"] is False
    assert span["caam.warm.attempted"] == 0
    assert span["caam.warm.refreshed"] == 0
    assert span["caam.warm.profile"] == spans.PROFILE_NONE
    assert span["caam.warm.next_wake"] == spans.WAKE_NONE
    assert not [line for line in out if line.startswith("next-warm-wake:")]


def test_keep_warm_and_the_wake_schedule_report_what_the_span_carries(*, tmp_path: Path) -> None:
    """The two caam_warm entry points answer the span's questions directly."""
    records = warm_records_module()
    warm = importlib.import_module("caam_warm")
    caam_home(tmp_path=tmp_path, idle_expiry=IDLE_EXPIRY)
    out: list[str] = []

    outcome = warm.keep_warm(
        state={},
        config=warm.WarmConfig(active_name="active", home=tmp_path, dry_run=False, no_warm=False),
        agent_runner=StaticAgent(),
        logger=out.append,
        now=NOW,
    )
    schedule = warm.emit_next_warm_wake(
        home=tmp_path, active_name="active", now=NOW, stdout=out.append
    )

    assert outcome == records.WarmOutcome(maintained=True, attempted=0, refreshed=0)
    assert schedule == records.WarmSchedule(profile="idle", wake=IDLE_EXPIRY + 15.0)
    assert warm.idle_snapshots(home=tmp_path, active_name="active") == (("idle", IDLE_EXPIRY),)


# ---------------------------------------------------------------------------
# The switch: what moved, from where to where, and what made the pass leave.
# ---------------------------------------------------------------------------


def test_a_switch_emits_one_rotation_span_carrying_from_to_switched_and_trigger(
    *, tmp_path: Path
) -> None:
    spans = rotation_span_module()
    wire = span_module()
    switch = switch_module()
    records: list[dict[str, object]] = []
    out: list[str] = []
    caam_home(tmp_path=tmp_path, idle_expiry=IDLE_EXPIRY, idle_name="target")

    code = drive_pass(
        home=tmp_path,
        argv=[],
        fetcher=binding_fetcher(active_five_hour=90.0),
        records=records,
        out=out,
        agent_runner=StaticAgent(),
        switch_account=switched_to(name="target", reason=switch.REASON_SWITCHED),
    )

    assert code == 0
    span = only(records=records, event=spans.ROTATION_SWITCH_EVENT)
    assert span["caam.account"] == "active"
    assert span["caam.rotation.from"] == "active"
    assert span["caam.rotation.to"] == "target"
    assert span["caam.rotation.switched"] is True
    assert span["caam.rotation.reason"] == switch.REASON_SWITCHED
    # The 5-hour window is what bound, so it is what made the pass leave. A reason
    # derived from the operator line could not separate it from the weekly reserve.
    assert span["caam.rotation.trigger"] == "five_hour"
    assert span["caam.exit_code"] == 0

    root = only(records=records, event=PASS_EVENT)
    assert span[wire.TRACE_ID_KEY] == root[wire.TRACE_ID_KEY]
    assert span[wire.PARENT_SPAN_ID_KEY] == root[wire.SPAN_ID_KEY]
    # The post-switch re-warm is not a second warm stage, and must not read as one.
    assert len([record for record in records if record["event"] == spans.WARM_SCHEDULE_EVENT]) == 1


def test_a_forced_switch_names_the_operator_rather_than_a_usage_dimension(
    *, tmp_path: Path
) -> None:
    """`--force` leaves an account nothing bound on, so no dimension explains it."""
    spans = rotation_span_module()
    switch = switch_module()
    records: list[dict[str, object]] = []
    out: list[str] = []
    caam_home(tmp_path=tmp_path, idle_expiry=IDLE_EXPIRY, idle_name="target")

    code = drive_pass(
        home=tmp_path,
        argv=["--force"],
        fetcher=binding_fetcher(active_five_hour=20.0),
        records=records,
        out=out,
        agent_runner=StaticAgent(),
        switch_account=switched_to(name="target", reason=switch.REASON_SWITCHED),
    )

    assert code == 0
    span = only(records=records, event=spans.ROTATION_SWITCH_EVENT)
    assert span["caam.rotation.trigger"] == spans.TRIGGER_FORCE
    assert span["caam.rotation.switched"] is True


def test_a_switch_held_by_the_lock_names_its_own_reason_and_stays_unswitched(
    *, tmp_path: Path
) -> None:
    """A hold exits ZERO, so only the named reason and the boolean separate it.

    Driven through the real `switch_account` rather than a double: the point of
    the vocabulary is that the switch names its outcome where it reaches it, so a
    reason invented by this file would prove nothing.
    """
    spans = rotation_span_module()
    switch = switch_module()

    result = switch.switch_account(
        request=switch.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage(five_hour=20.0)),
            current=usage(five_hour=90.0),
            state={},
            home=tmp_path,
            now=NOW,
            active_reader=lambda: "active",
            fetcher=lambda **_: (usage(five_hour=20.0), None),
            activator=lambda **_: None,
            lock_factory=lambda *, lock_path: None,
            save=lambda *, state: None,
        )
    )

    assert result.exit_code == 0
    assert result.switched is False
    assert result.reason == switch.REASON_HOLD_LOCK_HELD

    record = spans.rotation_record(
        outcome=spans.RotationOutcome(
            from_account="active",
            to_account="target",
            switched=result.switched,
            reason=result.reason,
            trigger="five_hour",
            exit_code=result.exit_code,
        ),
        at=NOW,
    )

    assert record["event"] == spans.ROTATION_SWITCH_EVENT
    assert record["caam.rotation.switched"] is False
    assert record["caam.rotation.reason"] == switch.REASON_HOLD_LOCK_HELD
    assert record["caam.exit_code"] == 0


# ---------------------------------------------------------------------------
# Harness.
# ---------------------------------------------------------------------------


def drive_pass(
    *,
    home: Path,
    argv: list[str],
    fetcher: Callable[..., tuple[UsageRecord | None, str | None]],
    records: list[dict[str, object]],
    out: list[str],
    now: float = NOW,
    **extra: Any,
) -> int:
    module = loop_module()
    return cast(
        int,
        module.run_pass(
            flags=module.parse_flags(argv=argv),
            home=home,
            now=now,
            stdout=out.append,
            caam_runner=lambda *, args: ActiveProfileProcess(),
            fetcher=fetcher,
            save_state=lambda *, state, state_path: None,
            enforce_models=lambda **kwargs: [],
            clock=stepped_clock(),
            emit_pass_event=collector(records=records),
            **extra,
        ),
    )


def collector(*, records: list[dict[str, object]]) -> Callable[..., None]:
    def emit(*, record: Mapping[str, object]) -> None:
        records.append(dict(record))

    return emit


def stepped_clock() -> Callable[[], float]:
    ticks: Iterator[float] = iter((OPEN_AT, CLOSE_AT))

    def clock() -> float:
        return next(ticks)

    return clock


def only(*, records: list[dict[str, object]], event: str) -> dict[str, object]:
    matched = [record for record in records if record["event"] == event]
    assert len(matched) == 1, f"expected exactly one {event}, got {len(matched)}"
    return matched[0]


def usage(*, five_hour: float, seven_day: float = 10.0) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=100.0 - five_hour,
        seven_day_remaining=100.0 - seven_day,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at="2026-08-24T00:00:00Z",
        fable_remaining=90.0,
        fable_resets_at="2026-08-24T00:00:00Z",
    )


def steady_fetcher(*, five_hour: float) -> Callable[..., tuple[UsageRecord | None, str | None]]:
    def fetcher(**_: Any) -> tuple[UsageRecord | None, str | None]:
        return usage(five_hour=five_hour), None

    return fetcher


def binding_fetcher(
    *, active_five_hour: float
) -> Callable[..., tuple[UsageRecord | None, str | None]]:
    """The active account spent, every candidate fresh -- enough to rank a target."""

    def fetcher(*, creds_path: Path, now: float | None = None) -> Any:
        del now
        if creds_path.parent.name in {"active", ".claude"}:
            return usage(five_hour=active_five_hour, seven_day=20.0), None
        return usage(five_hour=5.0, seven_day=5.0), None

    return fetcher


def switched_to(*, name: str, reason: str) -> Callable[..., Any]:
    def switch_account(*, request: Any) -> Any:
        module = switch_module()
        return module.SwitchResult(
            exit_code=0,
            lines=(f"SWITCHED {request.active_name} -> {name}",),
            switched=True,
            reason=reason,
        )

    return switch_account


def caam_home(*, tmp_path: Path, idle_expiry: float | None, idle_name: str = "idle") -> None:
    """An active account and, unless `idle_expiry` is None, one idle account beside it."""

    write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=30_000.0)
    if idle_expiry is not None:
        write_snapshot(
            home=tmp_path, name=idle_name, credential=idle_name, expires_at_s=idle_expiry
        )
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json", bearer="active", expires_at_s=30_000.0
    )


def write_creds(*, path: Path, bearer: str, expires_at_s: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        json.dumps(
            {"claudeAiOauth": {"accessToken": bearer, "expiresAt": int(expires_at_s * 1000)}}
        ),
        encoding="utf-8",
    )


def write_snapshot(*, home: Path, name: str, credential: str, expires_at_s: float) -> None:
    profile = home / ".local" / "share" / "caam" / "vault" / "claude" / name
    write_creds(path=profile / ".credentials.json", bearer=credential, expires_at_s=expires_at_s)
    _ = (profile / ".claude.json").write_text('{"oauthAccount":{}}\n', encoding="utf-8")
    _ = (profile / "settings.json").write_text('{"effortLevel":"high"}\n', encoding="utf-8")


class ActiveProfileProcess:
    returncode = 0
    stdout = '{"tools": [{"tool": "claude", "active_profile": "active"}]}'
    stderr = ""


class StaticAgent:
    """An agent that answers without touching the sandbox, so nothing refreshes."""

    def __call__(self, *, args: tuple[str, ...], env: dict[str, str], timeout: float) -> object:
        del args, env, timeout
        return type("Process", (), {"stdout": "ok\n", "stderr": ""})()


class RefreshingAgent:
    """An agent that renews the sandbox credential, as a real one would."""

    def __init__(self, *, expires_at_s: float) -> None:
        self.expires_at_s = expires_at_s

    def __call__(self, *, args: tuple[str, ...], env: dict[str, str], timeout: float) -> object:
        del args, timeout
        write_creds(
            path=Path(env["CLAUDE_CONFIG_DIR"]) / ".credentials.json",
            bearer="refreshed",
            expires_at_s=self.expires_at_s,
        )
        return type("Process", (), {"stdout": "ok\n", "stderr": ""})()
