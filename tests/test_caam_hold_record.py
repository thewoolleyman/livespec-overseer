"""The CAAM-HOLD alarm record: a session-window hold is never silent (overseer-yzbdlq).

Every scheduled pass writes `caam-hold.json` beside the other state files, and
journals `CAAM-HOLD ...` on a state change and once per pass while held.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import ProfileUsage, UsageRecord
from caam_hold_record import (
    HOLD_RECORD_REL,
    build_hold_record,
    hold_record_path,
    observe_pass_hold,
)

__all__: list[str] = []

ACTIVE = "active"
OTHER = "other"
NOW = 1789000000.0
STAMP = "2026-09-09T06:26:40Z"


def _usage(*, five: float) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=five,
        seven_day_remaining=70.0,
        five_hour_resets_at="2026-09-09T12:00:00Z",
        seven_day_resets_at="2026-09-11T00:00:00Z",
        fable_remaining=90.0,
        fable_resets_at="2026-09-11T00:00:00Z",
    )


def _row(*, name: str, five: float | None, source: str = "live") -> ProfileUsage:
    usage = None if five is None else _usage(five=five)
    return ProfileUsage(name=name, usage=usage, source=source)


def _build(
    *,
    current: UsageRecord,
    profiles: tuple[ProfileUsage, ...],
    protected: dict[str, float] | None = None,
    final: str = ACTIVE,
) -> dict[str, object]:
    return build_hold_record(
        active_name=ACTIVE,
        final_name=final,
        current=current,
        profiles=profiles,
        protection_floors=protected or {},
        written_at=STAMP,
    )


def test_held_when_no_destination_clears_the_floor() -> None:
    record = _build(
        current=_usage(five=10.0),
        profiles=(_row(name=ACTIVE, five=10.0), _row(name=OTHER, five=12.0)),
    )
    assert record == {
        "state": "held",
        "active_account": ACTIVE,
        "active_session_headroom_pct": 10.0,
        "floor_pct": 20.0,
        "best_destination": {"account": OTHER, "headroom_pct": 12.0},
        "written_at": STAMP,
    }


def test_held_with_no_destination_at_all() -> None:
    record = _build(current=_usage(five=10.0), profiles=(_row(name=ACTIVE, five=10.0),))
    assert record["state"] == "held"
    assert record["best_destination"] is None


def test_held_when_only_a_protected_destination_clears_it() -> None:
    record = _build(
        current=_usage(five=10.0),
        profiles=(_row(name=ACTIVE, five=10.0), _row(name=OTHER, five=90.0)),
        protected={OTHER: 10.0},
    )
    assert record["state"] == "held"
    assert record["best_destination"] == {"account": OTHER, "headroom_pct": 90.0}


def test_ignores_rows_that_are_not_live_or_have_no_usage() -> None:
    record = _build(
        current=_usage(five=10.0),
        profiles=(
            _row(name=ACTIVE, five=10.0),
            _row(name="stale", five=90.0, source="snapshot"),
            _row(name="blind", five=None),
        ),
    )
    assert record["state"] == "held"
    assert record["best_destination"] is None


def test_cleared_when_an_unprotected_destination_clears_the_floor() -> None:
    record = _build(
        current=_usage(five=10.0),
        profiles=(_row(name=ACTIVE, five=10.0), _row(name=OTHER, five=60.0)),
    )
    assert record["state"] == "cleared"
    assert record["best_destination"] == {"account": OTHER, "headroom_pct": 60.0}


def test_cleared_when_the_session_trigger_did_not_fire() -> None:
    record = _build(
        current=_usage(five=80.0),
        profiles=(_row(name=ACTIVE, five=80.0), _row(name=OTHER, five=5.0)),
    )
    assert record["state"] == "cleared"
    assert record["active_session_headroom_pct"] == 80.0


def test_cleared_when_the_pass_switched_names_the_new_account() -> None:
    record = _build(
        current=_usage(five=10.0),
        profiles=(_row(name=ACTIVE, five=10.0), _row(name=OTHER, five=60.0)),
        final=OTHER,
    )
    assert record["state"] == "cleared"
    assert record["active_account"] == OTHER
    assert record["active_session_headroom_pct"] == 60.0


def test_headroom_is_null_when_the_new_account_row_has_no_reading() -> None:
    record = _build(
        current=_usage(five=10.0),
        profiles=(_row(name=ACTIVE, five=10.0),),
        final="ghost",
    )
    assert record["active_account"] == "ghost"
    assert record["active_session_headroom_pct"] is None


def test_headroom_is_null_when_no_short_window_was_read() -> None:
    usage = UsageRecord(
        five_hour_remaining=0.0,
        seven_day_remaining=70.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=90.0,
        fable_resets_at=None,
        short_window_present=False,
    )
    record = _build(current=usage, profiles=(_row(name=ACTIVE, five=0.0),))
    assert record["state"] == "cleared"
    assert record["active_session_headroom_pct"] is None


# --- the pass-level behaviour ------------------------------------------------


class _Caam:
    returncode = 0
    stderr = ""
    stdout = json.dumps({"tools": [{"tool": "claude", "active_profile": ACTIVE}]})


def _home(*, tmp_path: Path) -> Path:
    vault = tmp_path / ".local/share/caam/vault/claude"
    for name in (ACTIVE, OTHER):
        (vault / name).mkdir(parents=True, exist_ok=True)
        _ = (vault / name / ".claude.json").write_text(
            json.dumps({"oauthAccount": {"accountUuid": f"uuid-{name}"}}), encoding="utf-8"
        )
    _ = (tmp_path / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": f"uuid-{ACTIVE}"}}), encoding="utf-8"
    )
    return tmp_path


def _pass(
    *, home: Path, active_five: float, other_five: float, scheduled: bool = True, dry: bool = False
) -> tuple[int, list[str]]:
    lines: list[str] = []
    by_account = {ACTIVE: active_five, OTHER: other_five}

    def fetch(*, creds_path: Path, now: float | None = None) -> tuple[UsageRecord, None]:
        owner = OTHER if f"/{OTHER}/" in str(creds_path) else ACTIVE
        return (_usage(five=by_account[owner]), None)

    code = run_pass(
        flags=Flags(
            scheduled=scheduled,
            force=False,
            dry_run=dry,
            no_models=True,
            no_warm=True,
            session_models=(),
            protected_accounts=((OTHER, ""),),
        ),
        home=home,
        now=NOW,
        stdout=lines.append,
        caam_runner=lambda *, args: _Caam(),
        fetcher=fetch,
        save_state=lambda *, state, state_path: None,
    )
    return code, lines


def _read(*, home: Path) -> dict[str, object]:
    parsed: object = json.loads(hold_record_path(home=home).read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def test_a_holding_scheduled_pass_writes_the_record_and_journals_it(*, tmp_path: Path) -> None:
    home = _home(tmp_path=tmp_path)
    _code, lines = _pass(home=home, active_five=10.0, other_five=90.0)
    record = _read(home=home)
    assert record["state"] == "held"
    assert record["active_account"] == ACTIVE
    assert set(record) == {
        "state",
        "active_account",
        "active_session_headroom_pct",
        "floor_pct",
        "best_destination",
        "written_at",
    }
    assert stat.S_IMODE(hold_record_path(home=home).stat().st_mode) == 0o600
    assert not hold_record_path(home=home).with_name("caam-hold.json.tmp").exists()
    assert "CAAM-HOLD held active=active headroom=10 floor=20 best=other" in lines


def test_a_second_held_pass_journals_again_and_the_end_of_the_hold_once(*, tmp_path: Path) -> None:
    home = _home(tmp_path=tmp_path)
    _pass(home=home, active_five=10.0, other_five=90.0)
    _code, again = _pass(home=home, active_five=10.0, other_five=90.0)
    assert sum(line.startswith("CAAM-HOLD held") for line in again) == 1
    _code, ended = _pass(home=home, active_five=80.0, other_five=90.0)
    assert [line for line in ended if line.startswith("CAAM-HOLD")] == [
        "CAAM-HOLD cleared active=active headroom=80 floor=20 best=other"
    ]
    assert _read(home=home)["state"] == "cleared"
    _code, quiet = _pass(home=home, active_five=80.0, other_five=90.0)
    assert not [line for line in quiet if line.startswith("CAAM-HOLD")]


def test_a_cleared_pass_with_no_prior_record_is_silent_but_still_writes(*, tmp_path: Path) -> None:
    home = _home(tmp_path=tmp_path)
    _code, lines = _pass(home=home, active_five=80.0, other_five=90.0)
    assert _read(home=home)["state"] == "cleared"
    assert not [line for line in lines if line.startswith("CAAM-HOLD")]


def test_an_unreadable_prior_record_counts_as_cleared(*, tmp_path: Path) -> None:
    home = _home(tmp_path=tmp_path)
    path = hold_record_path(home=home)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text("not json", encoding="utf-8")
    _code, lines = _pass(home=home, active_five=10.0, other_five=90.0)
    assert any(line.startswith("CAAM-HOLD held") for line in lines)


def test_a_non_object_prior_record_counts_as_cleared(*, tmp_path: Path) -> None:
    home = _home(tmp_path=tmp_path)
    path = hold_record_path(home=home)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text("[1]", encoding="utf-8")
    _code, lines = _pass(home=home, active_five=80.0, other_five=90.0)
    assert not [line for line in lines if line.startswith("CAAM-HOLD")]


def test_an_unscheduled_pass_writes_nothing(*, tmp_path: Path) -> None:
    home = _home(tmp_path=tmp_path)
    _pass(home=home, active_five=10.0, other_five=90.0, scheduled=False)
    assert not hold_record_path(home=home).exists()


def test_a_dry_run_prints_what_it_would_write_and_writes_nothing(*, tmp_path: Path) -> None:
    home = _home(tmp_path=tmp_path)
    _code, lines = _pass(home=home, active_five=10.0, other_five=90.0, dry=True)
    assert not hold_record_path(home=home).exists()
    would = [line for line in lines if line.startswith("CAAM-HOLD would write ")]
    assert len(would) == 1
    assert str(hold_record_path(home=home)) in would[0]
    assert '"state": "held"' in would[0]


def test_a_write_failure_is_reported_not_raised(*, tmp_path: Path) -> None:
    home = _home(tmp_path=tmp_path)
    blocker = home / ".local/state"
    blocker.parent.mkdir(parents=True, exist_ok=True)
    _ = blocker.write_text("a file where a directory must be", encoding="utf-8")
    lines: list[str] = []
    observe_pass_hold(
        home=home,
        record={
            "state": "held",
            "active_account": ACTIVE,
            "active_session_headroom_pct": 10.0,
            "floor_pct": 20.0,
            "best_destination": None,
            "written_at": STAMP,
        },
        dry_run=False,
        stdout=lines.append,
    )
    assert any(line.startswith("FAIL could not write the caam hold record") for line in lines)


def test_the_record_lives_in_the_state_directory() -> None:
    assert Path(".local/state/caam-usage-rotate/caam-hold.json") == HOLD_RECORD_REL


@pytest.mark.parametrize("state", ["held", "cleared"])
def test_the_journal_line_names_none_when_there_is_no_destination(
    *, tmp_path: Path, state: str
) -> None:
    lines: list[str] = []
    observe_pass_hold(
        home=tmp_path,
        record={
            "state": state,
            "active_account": ACTIVE,
            "active_session_headroom_pct": None,
            "floor_pct": 20.0,
            "best_destination": None,
            "written_at": STAMP,
        },
        dry_run=False,
        stdout=lines.append,
    )
    expected = f"CAAM-HOLD held active={ACTIVE} headroom=unknown floor=20 best=none"
    assert (expected in lines) is (state == "held")
