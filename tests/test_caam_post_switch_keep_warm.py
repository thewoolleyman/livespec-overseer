"""Carrier X13: the account a pass has just left must be warmable in that same pass.

The oracle invokes keep-warm at three sites -- "both hold paths and after a
successful switch, THE LAST USING THE NEW ACTIVE PROFILE". The rebuild hoisted it
to one site above the decision, which covers both hold paths and the switch path
from a single place and cannot drift the way three copies can. That half is an
improvement and is kept.

What the hoist alone cannot cover is the oracle's last site. A single call placed
before the switch necessarily runs with the OLD active name, and keep-warm skips
whichever profile it is told is active, so the account being rotated away from is
never a warming candidate in the pass that rotates away from it.

Usually that is invisible: the warm margin skips any snapshot more than two hours
from expiry, and both accounts that differ between the two placements are normally
fresh. It bites when the account being LEFT is already inside that margin -- which
is ordinary late in a five-hour window, and is the one moment in a pass when a
token is most likely near expiry and the pass has just decided to stop using it.
That is the deadlock this slice exists to prevent.

WHY THE HOLD LEG BELOW USES A REAL HOLD AND NOT A DRY RUN. keep_warm returns
immediately when dry_run is set, so a dry-run pass cannot warm twice whatever the
implementation does. A "holds warm once" leg written against --dry-run passes for
a reason that has nothing to do with the code under test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from caam_decision import UsageRecord

from tests.test_caam_anthropic_loop import (
    FakeProcess,
    caam_loop_module,
    write_creds,
    write_snapshot,
)

_ACTIVE = "active"
_TARGET = "idle"
_MARGIN_S = 7200.0
# A realistic epoch, not a small number. keep_warm skips any profile whose last
# warm attempt is inside CAAM_ROTATE_WARM_RETRY_S (3600s), and with an empty memo
# that comparison is `now - 0`. A clock of 2000 makes every profile look like it
# was attempted 2000 seconds ago and skips the lot -- silently, as an empty warm
# list that reads exactly like the feature being absent.
_NOW = 1_787_000_000.0


@dataclass(frozen=True, kw_only=True)
class _Switched:
    """A switch that moved the credential, standing in at the pass's own seam."""

    exit_code: int = 0
    switched: bool = True
    lines: tuple[str, ...] = (f"SWITCHED {_ACTIVE} -> {_TARGET}",)


def _usage(*, five_hour: float, seven_day: float) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at="2026-08-24T00:00:00Z",
        fable=10.0,
        fable_resets_at="2026-08-24T00:00:00Z",
    )


class _WarmRecorder:
    """Stands in for the refreshing agent, recording which profiles were warmed.

    The profile is not in the argv -- every invocation is the same `claude -p ok`.
    It is identified by the isolated CLAUDE_CONFIG_DIR the sandbox was built at,
    which is the only thing distinguishing one warm from another.
    """

    def __init__(self) -> None:
        self.warmed: list[str] = []

    def __call__(self, *, args: tuple[str, ...], env: dict[str, str], timeout: float) -> object:
        del args, timeout
        sandbox = Path(env["CLAUDE_CONFIG_DIR"])
        self.warmed.append(sandbox.name)
        return type("Process", (), {"stdout": "ok\n", "stderr": ""})()


def _run(
    *,
    home: Path,
    active_expires_in_s: float,
    target_expires_in_s: float,
    switch_account: object | None = None,
    argv: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """One pass with --warm on; returns (emitted lines, profiles warmed)."""
    for name, expires_in in ((_ACTIVE, active_expires_in_s), (_TARGET, target_expires_in_s)):
        write_snapshot(home=home, name=name, credential=name, expires_at_s=_NOW + expires_in)
    write_creds(
        path=home / ".claude" / ".credentials.json",
        bearer=_ACTIVE,
        expires_at_s=_NOW + active_expires_in_s,
    )
    agent = _WarmRecorder()
    lines: list[str] = []
    module = caam_loop_module()
    overrides: dict[str, object] = {}
    if switch_account is not None:
        overrides["switch_account"] = switch_account

    def _fetcher(*, creds_path: Path, now: float | None = None):
        del now
        if _TARGET in creds_path.parts:
            return _usage(five_hour=10.0, seven_day=20.0), None
        return _usage(five_hour=95.0, seven_day=60.0), None

    module.run_pass(
        flags=module.parse_flags(argv=argv or ["--warm"]),
        home=home,
        now=_NOW,
        stdout=lines.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=_fetcher,
        save_state=lambda *, state, state_path: None,
        agent_runner=agent,
        enforce_models=lambda **kwargs: [],
        **overrides,
    )
    return lines, agent.warmed


def test_the_account_just_left_is_warmed_in_the_pass_that_left_it(*, tmp_path: Path) -> None:
    """THE CARRIER. The account being rotated away from is inside the warm margin.

    Before this, it was skipped as the active profile and had to wait for the next
    tick -- which is too late if less than a tick of token life remains.
    """
    _lines, warmed = _run(
        home=tmp_path,
        active_expires_in_s=_MARGIN_S / 2,
        target_expires_in_s=_MARGIN_S * 10,
        switch_account=lambda *, request: _Switched(),
    )

    assert _ACTIVE in warmed, "the vacated account was never a warming candidate"


def test_a_pass_that_holds_warms_exactly_once(*, tmp_path: Path) -> None:
    """A hold warms once -- and BE HONEST ABOUT HOW HARD THIS LEG IS TO BREAK.

    Deliberately a REAL hold and not a dry run: keep_warm returns immediately
    under --dry-run, so a dry-run pass cannot warm twice whatever the
    implementation does, and a leg written against --dry-run would pass for a
    reason unrelated to the code. Here both accounts are equally spent, nothing
    clears the margin, and the pass genuinely holds.

    THIS IS A REGRESSION GUARD RATHER THAN A DISCRIMINATOR FOR THIS CHANGE, and
    the difference was measured rather than assumed. Double-warming is prevented
    TWICE OVER: the seam fires only on a switch that moved the credential, and
    the per-profile retry memo skips any profile already attempted inside
    CAAM_ROTATE_WARM_RETRY_S, which a second run in the same pass always is.
    Making the second warm unconditional does NOT redden this leg on its own --
    the memo absorbs it. It takes bypassing the memo AND making the warm
    unconditional together, which is what a sabotage pair confirmed.

    It is kept because those two mechanisms are independent and either could be
    removed by someone who did not know the other was load-bearing. It is
    labelled because a leg that survives its most obvious sabotage should say so
    rather than let a reader count it as proof.
    """
    lines, warmed = _run(
        home=tmp_path,
        active_expires_in_s=_MARGIN_S / 2,
        target_expires_in_s=_MARGIN_S / 2,
        argv=["--warm", "--dry-run"],
    )
    del lines

    assert warmed == [], "a dry run must not warm at all"

    lines, warmed = _run(
        home=tmp_path / "held",
        active_expires_in_s=_MARGIN_S / 2,
        target_expires_in_s=_MARGIN_S / 2,
    )

    assert not any(line.startswith("SWITCHED") for line in lines)
    assert warmed.count(_TARGET) == 1, f"a hold warmed more than once: {warmed}"
    assert _ACTIVE not in warmed, "the active account is never its own warming candidate"


def test_the_second_run_skips_the_new_active_rather_than_the_old_one(*, tmp_path: Path) -> None:
    """SECOND DISCRIMINATING LEG -- the one a call-counting test cannot make.

    A second invocation still keyed on the OLD active name warms the same set the
    first did and is indistinguishable from the shipped behaviour by counting. The
    property that matters is WHICH account each run skips: after the switch the new
    active must be skipped and the old one must be reachable.

    Both snapshots sit inside the margin here, so the only thing deciding who gets
    warmed is which name each run is told is active.
    """
    _lines, warmed = _run(
        home=tmp_path,
        active_expires_in_s=_MARGIN_S / 2,
        target_expires_in_s=_MARGIN_S / 2,
        switch_account=lambda *, request: _Switched(),
    )

    assert warmed.count(_TARGET) == 1, (
        f"the target was warmed {warmed.count(_TARGET)} times; the run after the switch "
        "should skip it as the new active"
    )
    assert warmed.count(_ACTIVE) == 1, (
        f"the vacated account was warmed {warmed.count(_ACTIVE)} times; expected exactly "
        "the one run that no longer considers it active"
    )
