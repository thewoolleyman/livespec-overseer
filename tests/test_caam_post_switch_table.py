"""Carrier R13: after a successful switch the table is re-rendered, so CURRENT is not stale.

The inventory states it in one sentence, and this plan's own scope event lists it
under group I -- "the switch: non-blocking flock, under-lock re-read and re-probe,
caam activate, stick verification, TABLE RE-RENDER". Every other clause of that
line shipped. This one did not, and it survived a completeness re-score that
asserted the range "R1-R13": twelve of thirteen were present, so the range-level
claim read true.

Without it the operator sees a table whose CURRENT column marks the account the
pass has just LEFT, immediately above a line saying it moved somewhere else. The
rotation is correct; the artifact the operator contract tells them to read
verbatim is the thing that lies.

TWO WAYS TO GET THIS WRONG, and each has a leg below rather than a comment.

Re-polling. Every profile was already polled earlier in the pass, so the second
table needs no request. An implementation that re-polls renders a correct table
and is still wrong: it spends a request per switch, and its figures disagree with
the table above it for reasons unrelated to the move.

Keying on the exit code. Three paths in the switch return zero and only one of
them moved anything -- a lock held by another pass, and an active account that
changed while this pass was deciding, both HOLD successfully. A second table on
either asserts a switch that did not happen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from caam_decision import UsageRecord

from tests.test_caam_anthropic_loop import (
    FakeProcess,
    caam_loop_module,
    write_creds,
    write_snapshot,
)

_ACTIVE = "active"
_TARGET = "idle"


def _usage(*, five_hour: float, seven_day: float) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at="2026-08-24T00:00:00Z",
        fable=10.0,
        fable_resets_at="2026-08-24T00:00:00Z",
    )


class _Run:
    """One whole pass, with the accounts arranged so a switch is the right outcome."""

    def __init__(self, *, home: Path) -> None:
        self.home = home
        self.lines: list[str] = []
        self.fetches = 0
        write_snapshot(home=home, name=_ACTIVE, credential="active", expires_at_s=30_000.0)
        write_snapshot(home=home, name=_TARGET, credential="idle", expires_at_s=30_000.0)
        write_creds(
            path=home / ".claude" / ".credentials.json",
            bearer="active",
            expires_at_s=30_000.0,
        )

    def _fetcher(self, *, creds_path: Path, now: float | None = None):
        del now
        self.fetches += 1
        spent = _ACTIVE in creds_path.parts or creds_path.name == ".credentials.json"
        if spent and _TARGET not in creds_path.parts:
            return _usage(five_hour=95.0, seven_day=60.0), None
        return _usage(five_hour=10.0, seven_day=20.0), None

    def go(self, *, argv: list[str] | None = None, switch_account=None) -> int:
        """Run the pass, optionally standing in for the switch through its own seam."""
        module = caam_loop_module()
        overrides: dict[str, object] = {}
        if switch_account is not None:
            overrides["switch_account"] = switch_account
        return module.run_pass(
            flags=module.parse_flags(argv=argv or []),
            home=self.home,
            now=2_000.0,
            stdout=self.lines.append,
            caam_runner=lambda *, args: FakeProcess(),
            fetcher=self._fetcher,
            save_state=lambda *, state, state_path: None,
            agent_runner=None,
            enforce_models=lambda **kwargs: [],
            **overrides,
        )

    def tables(self) -> list[int]:
        """Indices of every rendered header row -- one per table drawn."""
        return [i for i, line in enumerate(self.lines) if line.startswith("PROFILE")]

    def marked_current(self, *, header_index: int) -> str:
        """The account carrying the active marker in the table at this header."""
        for line in self.lines[header_index + 1 :]:
            if not line.strip():
                break
            if "✅" in line:
                return line.split()[0]
        return ""


def _switched(*, run: _Run) -> bool:
    return any(line.startswith("SWITCHED") for line in run.lines)


@dataclass(frozen=True, kw_only=True)
class _Switched:
    """What a switch that moved the credential reports back through the seam.

    Deliberately the test's own type rather than the real `SwitchResult`. The pass
    hard-wires the real `caam` binary as its under-lock active reader, so a pass
    driven end to end here reads THIS host's live profile and abandons the
    decision before switching -- a separate matter from carrier R13. Standing in
    at the seam keeps this file about the re-render, and it keeps the Red
    behavioural: against the shipped code these legs fail because no second table
    appears, not because a field is missing. That the REAL switch reports this
    faithfully is pinned separately, below.
    """

    exit_code: int = 0
    switched: bool = True
    lines: tuple[str, ...] = (
        f"SWITCHED {_ACTIVE} -> {_TARGET} (5h left was 5%; target has 80% week left)",
    )


def _a_real_switch(*, request: object) -> _Switched:
    del request
    return _Switched()


def test_a_successful_switch_renders_a_second_table_naming_the_new_account(
    *, tmp_path: Path
) -> None:
    """THE CARRIER. Two tables, and the second marks the account now in use."""
    run = _Run(home=tmp_path)
    run.go(switch_account=_a_real_switch)

    assert _switched(run=run), "arrangement is wrong: this pass was supposed to switch"
    headers = run.tables()
    assert len(headers) == 2, f"expected a table before and after the switch, got {len(headers)}"
    assert run.marked_current(header_index=headers[0]) == _ACTIVE
    assert run.marked_current(header_index=headers[1]) == _TARGET


def test_the_second_table_follows_the_switched_line(*, tmp_path: Path) -> None:
    """Order is part of the carrier: table, decision, outcome, corrected table.

    A re-render emitted before the outcome reads as the pass drawing the same
    table twice for no reason.
    """
    run = _Run(home=tmp_path)
    run.go(switch_account=_a_real_switch)

    switched_at = next(i for i, line in enumerate(run.lines) if line.startswith("SWITCHED"))
    assert run.tables()[1] > switched_at


def test_the_second_table_costs_no_additional_poll(*, tmp_path: Path) -> None:
    """ASSERTED, NOT ASSUMED. A re-polling implementation satisfies the carrier and is wrong."""
    switching = _Run(home=tmp_path)
    switching.go(switch_account=_a_real_switch)
    assert _switched(run=switching)

    holding = _Run(home=tmp_path / "held")
    holding.go(argv=["--dry-run"])

    assert switching.fetches == holding.fetches, (
        f"the switch cost {switching.fetches - holding.fetches} extra poll(s); "
        "the rows for the second table were already in hand"
    )


@pytest.mark.parametrize("argv", [[], ["--dry-run"]])
def test_a_pass_that_does_not_switch_renders_exactly_one_table(
    *, tmp_path: Path, argv: list[str]
) -> None:
    """DISCRIMINATING LEG. A hold and a dry run must not gain a second table.

    Both accounts are equally spent here, so nothing clears the margin and the
    pass holds. An implementation that re-renders unconditionally passes every
    leg above and fails this one.
    """
    run = _Run(home=tmp_path)
    run._fetcher = lambda *, creds_path, now=None: (  # type: ignore[method-assign]
        _usage(five_hour=95.0, seven_day=60.0),
        None,
    )
    run.go(argv=argv)

    assert not _switched(run=run)
    assert len(run.tables()) == 1


def test_a_hold_that_exits_zero_without_moving_renders_no_second_table(*, tmp_path: Path) -> None:
    """THE EXIT-CODE TRAP, pinned directly.

    A lock held by another pass returns exit code ZERO and moves nothing. Keying
    the re-render on the code rather than on a positive switched signal would
    announce a switch that never happened, which is exactly what the Z carriers
    forbid the table from doing.
    """
    run = _Run(home=tmp_path)
    code = run.go(
        switch_account=lambda *, request: _Switched(
            switched=False, lines=("hold: another pass holds the switch lock",)
        )
    )

    assert code == 0
    assert not _switched(run=run)
    assert len(run.tables()) == 1


def test_the_switched_flag_is_set_only_by_a_switch_that_moved_the_credential(
    *, tmp_path: Path
) -> None:
    """WHAT MAKES THE FLAG WORTH KEYING ON, against the REAL switch rather than a stand-in.

    Three of the switch's returns carry exit code zero and only one of them moved
    anything. If the flag tracked the code, the two holds would re-render a table
    announcing a switch that did not happen; if it were merely always true, every
    failure would. Both directions are pinned here, so the seam contract the pass
    relies on is verified rather than assumed.
    """
    from caam_decision import ProfileUsage

    from tests.test_caam_switch import (
        FakeActivator,
        FakeActive,
        FakeLock,
        FakeLockFactory,
        caam_switch_module,
        usage,
        write_creds,
    )

    module = caam_switch_module()

    def _switch(*, home: Path, active_reader, lock, activator=None):
        return module.switch_account(
            request=module.SwitchRequest(
                active_name="active",
                target=ProfileUsage(name="target", source="live", usage=usage(seven_day=25.0)),
                current=usage(five_hour=90.0),
                state={"profiles": {}},
                home=home,
                now=1787356770.0,
                active_reader=active_reader,
                fetcher=lambda *, creds_path, now=None: (usage(), None),
                activator=activator or FakeActivator(),
                lock_factory=FakeLockFactory(lock=lock),
                save=lambda *, state: None,
            )
        )

    # the one path that moved the credential
    moved_home = tmp_path / "moved"
    lock = FakeLock()
    activator = FakeActivator()
    activator.lock = lock
    write_creds(
        path=moved_home / ".local/share/caam/vault/claude/target/.credentials.json",
        access_value="target-value",
    )
    write_creds(path=moved_home / ".claude/.credentials.json", access_value="target-value")
    moved = _switch(
        home=moved_home, active_reader=FakeActive("active"), lock=lock, activator=activator
    )
    assert moved.exit_code == 0
    assert getattr(moved, "switched", None) is True

    # a lock held by another pass: zero, and nothing moved
    held = _switch(home=tmp_path / "held", active_reader=FakeActive("active"), lock=None)
    assert held.exit_code == 0
    assert getattr(held, "switched", None) is False

    # the active account changed while this pass was deciding: zero, and nothing moved
    changed = _switch(
        home=tmp_path / "changed", active_reader=FakeActive("someone-else"), lock=FakeLock()
    )
    assert changed.exit_code == 0
    assert getattr(changed, "switched", None) is False
