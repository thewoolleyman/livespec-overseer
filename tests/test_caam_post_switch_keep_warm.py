"""Carrier X13, under expiry-scheduled keep-warm: the account a pass has just left
must be warmable in that same pass when its token has EXPIRED.

The oracle invokes keep-warm at two sites -- once before the decision and once
after a switch that moved the credential (the last using the NEW active profile).
keep-warm skips whichever profile it is told is active, so the account being
rotated AWAY FROM is never a warming candidate in the pre-decision call; only the
post-switch call, keyed on the new active, can reach it.

Under expiry-scheduled maintenance (overseer-54k2za.52) keep-warm refreshes an
idle snapshot only once its token has EXPIRED -- a still-valid token is left for
the wake scheduled at its own expiry. So the moment the post-switch site matters
is exactly when the account being LEFT is already EXPIRED, which is ordinary late
in a five-hour window and is the deadlock this slice exists to prevent: without
the post-switch call that just-left, now-idle, expired account would wait a whole
tick to become selectable again.

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
# Offsets from _NOW: a token already past expiry, and one comfortably valid.
_EXPIRED_IN = -100.0
_VALID_IN = 100_000.0
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
    which is the only thing distinguishing one warm from another. It also refreshes
    the sandbox credential to a far-future expiry, so a warmed snapshot copied back
    reads as valid on any later read within the same pass.
    """

    def __init__(self) -> None:
        self.warmed: list[str] = []

    def __call__(self, *, args: tuple[str, ...], env: dict[str, str], timeout: float) -> object:
        del args, timeout
        sandbox = Path(env["CLAUDE_CONFIG_DIR"])
        self.warmed.append(sandbox.name)
        write_creds(
            path=sandbox / ".credentials.json",
            bearer=f"{sandbox.name}-refreshed",
            expires_at_s=_NOW + _VALID_IN,
        )
        return type("Process", (), {"stdout": "ok\n", "stderr": ""})()


def _run(
    *,
    home: Path,
    active_expires_in_s: float,
    target_expires_in_s: float,
    switch_account: object | None = None,
    argv: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """One default (keep-warm on) pass; returns (emitted lines, profiles warmed)."""
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
        flags=module.parse_flags(argv=argv or []),
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


def test_the_expired_account_just_left_is_warmed_in_the_pass_that_left_it(
    *, tmp_path: Path
) -> None:
    """THE CARRIER. The account being rotated away from has an EXPIRED token.

    Only the post-switch keep-warm call, keyed on the new active, can reach it; the
    pre-decision call skipped it as the (old) active. Without that call it would
    stay dark until the next tick.
    """
    _lines, warmed = _run(
        home=tmp_path,
        active_expires_in_s=_EXPIRED_IN,
        target_expires_in_s=_VALID_IN,
        switch_account=lambda *, request: _Switched(),
    )

    assert _ACTIVE in warmed, "the vacated, expired account was never a warming candidate"
    assert _TARGET not in warmed, "the still-valid target must not be refreshed pre-expiry"


def test_a_pass_that_holds_warms_an_expired_idle_account_exactly_once(*, tmp_path: Path) -> None:
    """A hold warms an EXPIRED idle account once -- and BE HONEST ABOUT HOW HARD THIS
    LEG IS TO BREAK.

    Deliberately a REAL hold and not a dry run: keep_warm returns immediately under
    --dry-run, so a dry-run pass cannot warm twice whatever the implementation does.
    Here the active account is healthy so the pass holds, and the idle account's
    token has expired so it is the one warming candidate.

    Double-warming across the two call sites is prevented twice over: the
    post-switch seam fires only on a switch that moved the credential (there is no
    switch here), and the per-profile retry memo skips any profile already attempted
    inside CAAM_ROTATE_WARM_RETRY_S, which a second call in the same pass always is.
    """
    lines, warmed = _run(
        home=tmp_path / "dry",
        active_expires_in_s=_VALID_IN,
        target_expires_in_s=_EXPIRED_IN,
        argv=["--no-warm", "--dry-run"],
    )
    del lines

    assert warmed == [], "a --no-warm dry run must not warm at all"

    lines, warmed = _run(
        home=tmp_path / "held",
        active_expires_in_s=_VALID_IN,
        target_expires_in_s=_EXPIRED_IN,
    )

    assert not any(line.startswith("SWITCHED") for line in lines)
    assert warmed.count(_TARGET) == 1, f"an expired idle account warmed more than once: {warmed}"
    assert _ACTIVE not in warmed, "the active account is never its own warming candidate"


def test_each_site_warms_its_own_expired_idle_account_and_the_wake_is_emitted(
    *, tmp_path: Path
) -> None:
    """The two sites skip DIFFERENT active accounts, and a next-warm-wake is emitted.

    Both accounts start expired. The pre-decision call (keyed on the OLD active)
    warms the idle target; the post-switch call (keyed on the NEW active) warms the
    just-left account. Neither account is warmed twice -- the property a
    call-counting test cannot make -- and the pass emits the wake keyed to the
    soonest idle-account expiry (both are refreshed far into the future by the warm).
    """
    lines, warmed = _run(
        home=tmp_path,
        active_expires_in_s=_EXPIRED_IN,
        target_expires_in_s=_EXPIRED_IN,
        switch_account=lambda *, request: _Switched(),
    )

    assert warmed == [_TARGET, _ACTIVE], f"each site must warm its own account once: {warmed}"
    assert any(line.startswith("next-warm-wake: ") for line in lines)
