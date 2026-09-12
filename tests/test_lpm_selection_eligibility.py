"""Seven independent eligibility axes, each answerable — and answered — on its own.

SPECIFICATION/spec.md composes eligibility from separate concerns: byte-exact provider, kind and
purpose MATCHING; purpose reservation as an ADDITIONAL filter that does not make a differently-
purposed record match; the validation state; a live run-scoped lease, which makes an account
ineligible under BOTH strategies; and the shared-usage observation, which under `remaining-
percent` excludes an account whose remainder is unavailable or below the inclusive floor while the
default `none` strategy consults no observation at all.

These tests exercise each axis alone as well as the composition, because the harm from
collapsing a pair is invisible in a combined "is this usable" answer: a reservation reading
as a match rule, or a health floor excluding under `none`, both look like ordinary
ineligibility from the outside.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_FIRST = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_NOW = "2026-09-12T10:00:00Z"


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_eligibility.py"
    assert module_path.is_file(), "overseer/_lpm_eligibility.py must exist"
    return (
        importlib.import_module("_lpm_eligibility"),
        importlib.import_module("_lpm_record"),
    )


def _record(records, **changes):
    fields = {
        "record_id": _FIRST,
        "provider": "anthropic",
        "account_id": "one@example.test",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-09-12T09:00:00Z",
        "expires_at": None,
        "last_validated": "2026-09-12T09:58:00Z",
        "value_generation": _GENERATION,
        "value_ref": f"op://provisionable/{_FIRST}/value#{_GENERATION}",
        "previous_value_ref": None,
    }
    fields.update(changes)
    return records.CredentialRecord(**fields)


def _inputs(eligibility, records, *, record_changes=None, observation=None, **policy_changes):
    policy = {
        "now": _NOW,
        "maximum_validation_age_seconds": 300,
        "health_strategy": "none",
        "health_floor_percent": 10,
        "account_reservations": {},
    }
    policy.update(policy_changes)
    return eligibility.AxisInputs(
        request=eligibility.SelectionRequest(
            provider="anthropic", kind="claude-code-oauth", purpose="factory"
        ),
        record=_record(records, **(record_changes or {})),
        observation=observation or eligibility.AccountObservation(),
        policy=eligibility.EligibilityPolicy(**policy),
    )


def test_the_axis_table_is_the_declared_order_and_every_axis_is_callable_alone():
    eligibility, records = _modules()

    assert eligibility.ELIGIBILITY_AXES == (
        "provider",
        "credential-kind",
        "purpose",
        "validation-state",
        "purpose-reservation",
        "account-lease",
        "shared-account-usage",
    )
    assert set(eligibility.EXCLUSION_BY_AXIS) == set(eligibility.ELIGIBILITY_AXES)
    assert eligibility.excluding_axis(inputs=_inputs(eligibility, records)) is None


def test_matching_is_byte_exact_on_provider_kind_and_purpose():
    eligibility, records = _modules()

    assert (
        eligibility.provider_excludes(
            inputs=_inputs(eligibility, records, record_changes={"provider": "Anthropic"})
        )
        is True
    )
    assert eligibility.provider_excludes(inputs=_inputs(eligibility, records)) is False
    assert (
        eligibility.credential_kind_excludes(
            inputs=_inputs(eligibility, records, record_changes={"kind": "claude-code-oauth2"})
        )
        is True
    )
    assert eligibility.credential_kind_excludes(inputs=_inputs(eligibility, records)) is False
    assert (
        eligibility.purpose_excludes(
            inputs=_inputs(eligibility, records, record_changes={"purpose": "interactive"})
        )
        is True
    )
    assert eligibility.purpose_excludes(inputs=_inputs(eligibility, records)) is False


def test_only_a_fresh_unexpired_valid_record_survives_the_validation_state_axis():
    eligibility, records = _modules()

    for changes in (
        {"status": "suspect"},
        {"last_validated": "2026-09-12T09:55:00Z"},
        {"expires_at": _NOW},
    ):
        assert (
            eligibility.validation_state_excludes(
                inputs=_inputs(eligibility, records, record_changes=changes)
            )
            is True
        ), changes
    assert eligibility.validation_state_excludes(inputs=_inputs(eligibility, records)) is False


def test_a_reserved_account_permits_only_its_listed_purposes_and_reserves_nothing_else():
    eligibility, records = _modules()
    reserved = {"anthropic": {"one@example.test": ("interactive",)}}
    shared = {"anthropic": {"one@example.test": ("factory", "interactive")}}
    elsewhere = {"anthropic": {"two@example.test": ("interactive",)}}

    assert (
        eligibility.purpose_reservation_excludes(
            inputs=_inputs(eligibility, records, account_reservations=reserved)
        )
        is True
    )
    assert (
        eligibility.purpose_reservation_excludes(
            inputs=_inputs(eligibility, records, account_reservations=shared)
        )
        is False
    )
    assert (
        eligibility.purpose_reservation_excludes(
            inputs=_inputs(eligibility, records, account_reservations=elsewhere)
        )
        is False
    )
    assert eligibility.purpose_reservation_excludes(inputs=_inputs(eligibility, records)) is False


def test_a_live_lease_hides_the_account_from_every_other_request():
    eligibility, records = _modules()
    leased = eligibility.AccountObservation(leased=True)

    assert eligibility.account_lease_excludes(inputs=_inputs(eligibility, records)) is False
    assert (
        eligibility.account_lease_excludes(inputs=_inputs(eligibility, records, observation=leased))
        is True
    )


def test_the_shared_usage_axis_is_inert_under_none_and_floor_enforcing_otherwise():
    eligibility, records = _modules()
    unobserved = eligibility.AccountObservation()
    at_floor = eligibility.AccountObservation(shared_usage_remaining=10)
    below = eligibility.AccountObservation(shared_usage_remaining=9)

    def _excludes(observation, strategy):
        return eligibility.shared_account_usage_excludes(
            inputs=_inputs(eligibility, records, observation=observation, health_strategy=strategy)
        )

    assert _excludes(unobserved, "none") is False
    assert _excludes(below, "none") is False
    assert _excludes(unobserved, "remaining-percent") is True
    assert _excludes(below, "remaining-percent") is True
    assert _excludes(at_floor, "remaining-percent") is False


def test_the_first_excluding_axis_is_named_in_its_declared_order():
    eligibility, records = _modules()
    leased = eligibility.AccountObservation(leased=True)

    assert (
        eligibility.excluding_axis(
            inputs=_inputs(
                eligibility,
                records,
                record_changes={"provider": "openai", "status": "dead"},
                observation=leased,
            )
        )
        == "provider"
    )
    assert (
        eligibility.excluding_axis(
            inputs=_inputs(eligibility, records, record_changes={"status": "dead"})
        )
        == "validation-state"
    )
    assert (
        eligibility.excluding_axis(inputs=_inputs(eligibility, records, observation=leased))
        == "account-lease"
    )


def test_an_account_with_no_observation_is_unobserved_rather_than_observed_healthy():
    eligibility, records = _modules()
    request = eligibility.SelectionRequest(
        provider="anthropic", kind="claude-code-oauth", purpose="factory"
    )
    policy = eligibility.EligibilityPolicy(
        now=_NOW,
        maximum_validation_age_seconds=300,
        health_strategy="remaining-percent",
        health_floor_percent=10,
        account_reservations={},
    )
    observed = _record(records, record_id=_GENERATION, account_id="two@example.test")

    admitted = eligibility.eligible_records(
        request=request,
        records=(_record(records), observed),
        observations={
            "two@example.test": eligibility.AccountObservation(shared_usage_remaining=50)
        },
        policy=policy,
    )

    assert admitted == (observed,)
