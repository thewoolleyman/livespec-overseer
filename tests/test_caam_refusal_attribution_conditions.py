"""The attribution conditions a scenario cannot state through a transcript.

Two conditions are about the RECORD rather than about the pass: an identity the
provider named in it, and the window it named. Both are driven here against the
attribution stage directly, with the refusals handed in through the reader seam,
so each condition is read on its own rather than through whatever a transcript
happened to make expressible.
"""

from __future__ import annotations

from pathlib import Path

from caam_decision import ProfileUsage, UsageRecord
from caam_profiles import ActiveIdentity
from caam_refusal_attribution import RefusalObservation, observe_refusals
from caam_refusal_store import remembered_refusals
from caam_refusals import (
    WINDOW_FIVE_HOUR,
    WINDOW_SEVEN_DAY,
    Refusal,
    TrackedSession,
    window_label,
)

__all__: list[str] = []

NOW = 1_800_000_000.0
ACTIVATION = NOW - 3_600.0
WEEKLY_RESET = "2027-01-22T08:00:00Z"
WEEKLY_RESET_AT = 1_800_604_800.0


def reading(*, five_hour_resets_at: str | None = None) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=45.0,
        seven_day_remaining=60.0,
        five_hour_resets_at=five_hour_resets_at,
        seven_day_resets_at=WEEKLY_RESET,
        fable_remaining=None,
        fable_resets_at=None,
    )


def observed(
    *,
    state: dict[str, object],
    refusals: tuple[Refusal, ...],
    active: str = "anthropic-1",
    uuid: str | None = "uuid-anthropic-1",
) -> None:
    observe_refusals(
        observation=RefusalObservation(
            home=Path("/home/op"),
            state=state,
            active=ActiveIdentity(profile=active, account_uuid=uuid),
            current=reading(),
            profiles=(ProfileUsage(name=active, source="live", usage=reading()),),
            sessions=(TrackedSession(session_id="s1", config_dir=Path("/home/op/.claude")),),
            now=NOW,
            reader=lambda *, session: refusals,
        )
    )


def test_a_refusal_naming_another_accounts_identity_is_not_attributed() -> None:
    """A profile can be renamed; the identity the provider named cannot.

    Where the record carries one, it is the discriminator -- and it outranks the
    fact that this session was on the live credential, because the credential
    may have been swapped under it since the refusal was written.
    """
    state: dict[str, object] = {"active_since": {"account": "anthropic-1", "at": ACTIVATION}}

    observed(
        state=state,
        refusals=(
            Refusal(
                recorded_at=NOW - 60.0,
                window=WINDOW_FIVE_HOUR,
                resets_at=NOW + 3_600.0,
                account="uuid-anthropic-3",
            ),
        ),
    )

    assert remembered_refusals(state=state) == ()


def test_a_refusal_naming_the_active_accounts_own_identity_is_attributed() -> None:
    """The control: the identity condition only excludes a MISMATCH."""
    state: dict[str, object] = {"active_since": {"account": "anthropic-1", "at": ACTIVATION}}

    observed(
        state=state,
        refusals=(
            Refusal(
                recorded_at=NOW - 60.0,
                window=WINDOW_FIVE_HOUR,
                resets_at=NOW + 3_600.0,
                account="uuid-anthropic-1",
            ),
        ),
    )

    assert len(remembered_refusals(state=state)) == 1


def test_a_lagging_weekly_refusal_is_matched_against_the_weekly_reset_departed_at() -> None:
    """The window the refusal names decides which of a departed entry's resets is read.

    A weekly refusal matched against a departed account's SHORT-window reset
    would be a coincidence test between two unrelated figures, in both
    directions: it would attribute a lagging weekly refusal to the new account,
    and it could withhold one that belongs to it.
    """
    state: dict[str, object] = {
        "active_since": {"account": "anthropic-1", "at": ACTIVATION},
        "departed_accounts": {
            "anthropic-3": {
                "five_hour_resets_at": "2027-01-15T09:00:00Z",
                "seven_day_resets_at": WEEKLY_RESET,
            }
        },
    }

    observed(
        state=state,
        refusals=(
            Refusal(
                recorded_at=NOW - 60.0,
                window=WINDOW_SEVEN_DAY,
                resets_at=WEEKLY_RESET_AT + 30.0,
            ),
        ),
    )

    assert remembered_refusals(state=state) == ()
    assert window_label(window=WINDOW_SEVEN_DAY) == "weekly window"
