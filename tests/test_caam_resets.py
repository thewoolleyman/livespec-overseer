"""Quota-reset policy and provider-neutral representation."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


def test_reset_selection_prefers_the_narrowest_usable_claim_and_tracks_retries(*, tmp_path: Path):
    """The reset rules distinguish unavailable, broad, spent, and retryable grants."""
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_resets.py"
    assert module_path.is_file()
    module = importlib.import_module("caam_resets")
    narrow = module.QuotaReset(
        program="juniper_tide",
        reset_id=None,
        clears=("five_hour",),
        uses_left=1,
        uses_total=1,
        lapses_at=None,
        usable_now=True,
        requires_limit=True,
    )
    broad = module.QuotaReset(
        program="cedar_ember",
        reset_id="weekly",
        clears=("five_hour", "seven_day"),
        uses_left=1,
        uses_total=1,
        lapses_at="2026-11-14T00:00:00Z",
        usable_now=True,
        requires_limit=False,
    )
    unavailable = module.QuotaReset(
        program="cedar_ember",
        reset_id="empty",
        clears=("five_hour",),
        uses_left=0,
        uses_total=1,
        lapses_at="2026-11-13T01:00:00Z",
        usable_now=True,
        requires_limit=False,
    )

    assert (
        module.exhausted_claim(
            resets=(broad, narrow, unavailable),
            triggered=frozenset({"five_hour"}),
            at_limit=frozenset({"five_hour"}),
        )
        == narrow
    )
    assert (
        module.lapsing_claim(
            resets=(broad, unavailable),
            spent={"five_hour": 20.0, "seven_day": 2.0},
            at_limit=frozenset(),
            now=1_794_528_000.0,
            eligibility_margin=10.0,
            expiry_horizon_s=86_400.0,
        )
        == broad
    )
    state: dict[str, object] = {}
    first = module.claim_identifier(state=state, account="a", reset=broad, new_id=lambda: "one")
    assert first == "one"
    assert (
        module.claim_identifier(state=state, account="a", reset=broad, new_id=lambda: "two")
        == "one"
    )


def test_anthropic_reset_reading_keeps_limit_only_grants_and_client_refusals_distinct():
    """A declined reset surface is unreadable, rather than an empty grant list."""
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_resets.py"
    assert module_path.is_file()
    module = importlib.import_module("caam_resets")

    readable = module.parse_anthropic_resets(
        body={
            "rate_limit_resets": [
                {
                    "program": "cedar_ember",
                    "grant_id": "grant-1",
                    "clears": ["five_hour", "seven_day"],
                    "uses_remaining": 1,
                    "uses_total": 2,
                    "expires_at": "2026-11-14T00:00:00Z",
                    "use_requires_limit": False,
                },
                {
                    "program": "juniper_tide",
                    "clears": ["five_hour"],
                    "uses_remaining": 3,
                    "uses_total": 3,
                    "use_requires_limit": True,
                },
            ]
        }
    )
    assert readable.unreadable_reason is None
    assert readable.resets[0].clears == ("five_hour", "seven_day")
    assert readable.resets[1].requires_limit is True

    unreadable = module.parse_anthropic_resets(
        body={"rate_limit_resets": {"error": "client surface is not entitled"}}
    )
    assert unreadable.resets == ()
    assert unreadable.unreadable_reason == "client surface is not entitled"


def test_anthropic_blocks_parse_each_grant_and_build_an_idempotent_claim():
    """The provider blocks retain their real fields through parsing and claim."""
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_resets.py"
    assert module_path.is_file()
    module = importlib.import_module("caam_resets")
    reading = module.parse_anthropic_resets(
        body={
            "cedar_ember": {
                "eligible": True,
                "grants": [
                    {
                        "id": "grant-1",
                        "clears": ["five_hour", "seven_day"],
                        "resets_left": 1,
                        "resets_total": 2,
                        "ends_at": "2026-11-14T00:00:00Z",
                        "usable_now": True,
                        "use_requires_limit": False,
                    }
                ],
            },
            "juniper_tide": {
                "eligible": True,
                "available": True,
                "resets_per_week": 1,
                "weekly_resets_at": "2026-11-15T00:00:00Z",
            },
        }
    )

    claim = module.claim_request(
        organization_uuid="org-1",
        reset=reading.resets[0],
        request_id="request-1",
    )
    assert claim.url.endswith("/api/organizations/org-1/reset_rate_limits")
    assert claim.body == {
        "program": "cedar_ember",
        "grant_id": "grant-1",
        "request_id": "request-1",
    }
