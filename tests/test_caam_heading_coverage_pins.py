"""Heading pins for the account-rotation spec sections.

Two ratified headings that were seeded ahead of implementation and later built
out — spec.md (the "Account rotation and quota supervision" section) and
contracts.md (the "The account-rotation operation" section) — are pinned here at
unit tier (both are non-scenario headings, so a unit-tier pin is permitted by the
heading-coverage tier rule).

Each test carries a CONTROL arm: a companion assertion that fails if the
behaviour under test silently stops discriminating. A check that merely stopped
firing — a trigger wired always-on, or a publisher that writes unconditionally —
would pass the positive assertion alone; the control is what a hollow
implementation cannot satisfy.
"""

from __future__ import annotations

import json
from pathlib import Path

import caam_decision
import caam_selection_record

__all__: list[str] = []


def _usage(*, five_hour_remaining: float, seven_day_remaining: float) -> caam_decision.UsageRecord:
    """A minimal, dollar-meter-free usage record.

    `extra_usage` and the dollar fields are left at their None defaults, so
    `spend_capped` reads "no meter observed" and cannot stand in for the
    percentage triggers this test is isolating.
    """
    return caam_decision.UsageRecord(
        five_hour_remaining=five_hour_remaining,
        seven_day_remaining=seven_day_remaining,
        five_hour_resets_at="2026-08-21T12:00:00Z",
        seven_day_resets_at="2026-08-23T12:00:00Z",
        fable_remaining=0.0,
        fable_resets_at="2026-08-23T12:00:00Z",
    )


def test_rotation_triggers_when_short_window_reaches_its_floor(*, monkeypatch):
    """spec.md (the "Account rotation and quota supervision" section) — **Rotation triggers**.

    "The operation MUST rotate when the active account's short-window allowance is
    at or above a configurable threshold" — expressed in the remaining direction
    every stored figure runs in, at or BELOW a configurable floor.

    CONTROL: a healthy account, whose short-window remaining sits comfortably
    above the floor with an ample weekly balance, MUST NOT trigger. Without this
    arm a `triggered` wired to return True unconditionally would pass the
    positive assertion; the control is what fails on such a regression.
    """
    monkeypatch.setenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", "15")
    monkeypatch.setenv("CAAM_ROTATE_WEEKLY_RESERVE", "10")

    at_floor = _usage(five_hour_remaining=15.0, seven_day_remaining=90.0)
    assert caam_decision.triggered(usage=at_floor) is True

    # CONTROL: nothing is nearly spent — the trigger must stay quiet.
    healthy = _usage(five_hour_remaining=90.0, seven_day_remaining=90.0)
    assert caam_decision.triggered(usage=healthy) is False


def test_publish_selection_names_both_identities_and_suppresses_a_partial_one(*, tmp_path):
    """contracts.md (the "The account-rotation operation" section) — **Published selection record**.

    The record "MUST name the selected account by BOTH the account manager's
    profile name AND the stable account identifier ... Neither field MAY be
    omitted", it "MUST carry the time at which it was written", and it "MUST NOT
    contain credential material of any kind". "A pass that cannot supply both
    MUST NOT publish."

    CONTROL: a pass with the profile but no stable identifier MUST write nothing
    at all — not a degraded, name-only record. Without this arm a publisher that
    wrote a partial record would pass the positive assertion; the control is what
    catches a suppression rule that was dropped.
    """
    home: Path = tmp_path
    record_path = caam_selection_record.selection_record_path(home=home)

    wrote = caam_selection_record.publish_selection(
        profile="work-anthropic",
        account_uuid="acct-0000-1111-2222",
        written_at="2026-09-11T00:00:00Z",
        home=home,
    )
    assert wrote is True
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    assert payload["profile"] == "work-anthropic"
    assert payload["account_uuid"] == "acct-0000-1111-2222"
    assert payload["written_at"] == "2026-09-11T00:00:00Z"
    # Identity only — no credential material of any kind rides along.
    assert not {"token", "access_token", "refresh_token", "credential"} & set(payload)
    # Owner-only permissions, per the atomic-write contract.
    assert (record_path.stat().st_mode & 0o777) == 0o600

    # CONTROL: an unresolved stable identifier suppresses publication entirely.
    home_partial: Path = tmp_path / "partial"
    partial_path = caam_selection_record.selection_record_path(home=home_partial)
    suppressed = caam_selection_record.publish_selection(
        profile="work-anthropic",
        account_uuid=None,
        written_at="2026-09-11T00:00:00Z",
        home=home_partial,
    )
    assert suppressed is False
    assert not partial_path.exists()
