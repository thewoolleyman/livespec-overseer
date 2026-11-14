"""Edge coverage for provider-neutral reset parsing."""

from __future__ import annotations

from caam_resets import QuotaReset, claim_request, lapsing_claim, parse_anthropic_resets

__all__: list[str] = []


def test_client_surface_refusal_is_not_reported_as_an_empty_reset_list() -> None:
    """The provider's client-surface refusal leaves a visible unreadable reading."""
    reading = parse_anthropic_resets(
        body={"cedar_ember": {"eligible": False, "ineligible_reason": "surface"}}
    )

    assert reading.resets == ()
    assert reading.unreadable_reason == "client surface is ineligible"


def test_absent_reset_programs_are_an_empty_reading() -> None:
    """A readable provider answer with neither program is genuinely empty."""
    reading = parse_anthropic_resets(body={})

    assert reading.resets == ()
    assert reading.unreadable_reason is None


def test_recurring_reset_claim_has_no_grant_identifier() -> None:
    """The session-reset program's claim identifies the program alone."""
    reading = parse_anthropic_resets(
        body={"juniper_tide": {"available": True, "resets_per_week": 1}}
    )

    request = claim_request(
        organization_uuid="org",
        reset=reading.resets[0],
        request_id="request",
    )

    assert request.body == {"program": "juniper_tide", "request_id": "request"}


def test_reset_selection_treats_missing_or_invalid_lapse_times_as_nonexpiring() -> None:
    """A reset without a parseable lapse never crashes the expiry policy."""
    reset = QuotaReset(
        program="cedar_ember",
        reset_id="grant",
        clears=("five_hour",),
        uses_left=1,
        uses_total=1,
        lapses_at=None,
        usable_now=True,
        requires_limit=False,
    )
    invalid = QuotaReset(
        program="cedar_ember",
        reset_id="invalid",
        clears=("five_hour",),
        uses_left=1,
        uses_total=1,
        lapses_at="not-a-timestamp",
        usable_now=True,
        requires_limit=False,
    )

    assert (
        lapsing_claim(
            resets=(reset, invalid),
            spent={"five_hour": 100.0},
            at_limit=frozenset(),
            now=1_800_000_000.0,
            eligibility_margin=1.0,
            expiry_horizon_s=86_400.0,
        )
        is None
    )
