"""The closed registry, the reservation rule it guards, and the closed result vocabulary.

Three closures from the credential-provider contract in SPECIFICATION/contracts.md,
tested together because the middle one is only correct BECAUSE of the other two.

The initial provider registry has exactly one row, and it declares shared-usage
observation `unsupported` — not as a gap awaiting an adapter, but because the Anthropic
setup token receives HTTP `403` from the usage endpoint, so issuing that request or
claiming an observed remainder for it is forbidden.

That contract then says a multi-purpose reservation requires `remaining-percent`
AND a declared observer on every registered kind for that provider. Against the row above
that combination is unsatisfiable for `anthropic` today, and it must be refused at
CONFIGURATION time for every command: under `none` no health-based exclusion is applied at
all, so a shared factory/interactive account would be handed to a second purpose with no
observation that the first already consumed it.

It also closes the result set and its exit statuses. The exit status is the half
a JSON-inspecting test misses, and it is the half a consumer reads.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []


def _modules():
    for name in ("_lpm_registry.py", "_lpm_reservations.py", "_lpm_results.py"):
        assert (
            pathlib.Path(__file__).parents[1] / "overseer" / name
        ).is_file(), f"overseer/{name} must exist"
    return (
        importlib.import_module("_lpm_registry"),
        importlib.import_module("_lpm_reservations"),
        importlib.import_module("_lpm_results"),
    )


def _reservation_refusal(*, value: object, health_strategy: str = "none") -> str:
    _, reservations, _ = _modules()
    return (
        reservations.reservations_from_object(value=value, health_strategy=health_strategy)
        .failure()
        .message
    )


def test_the_initial_registry_is_exactly_one_row_declaring_no_shared_usage_observer():
    registry, _, _ = _modules()

    assert len(registry.PROVIDER_REGISTRY) == 1
    row = registry.provider_row(provider="anthropic", kind="claude-code-oauth")
    assert row is not None
    assert row.acquisition_terminal == "claude setup-token"
    assert row.shared_usage_observation == registry.UNSUPPORTED_SHARED_USAGE


def test_an_unregistered_provider_or_kind_has_no_row_to_fall_back_to():
    registry, _, _ = _modules()

    assert registry.provider_row(provider="openai", kind="claude-code-oauth") is None
    assert registry.provider_row(provider="anthropic", kind="api-key") is None
    assert registry.provider_is_registered(provider="anthropic")
    assert not registry.provider_is_registered(provider="openai")
    assert registry.rows_for_provider(provider="openai") == ()


def test_purpose_is_not_registered_and_both_declared_spellings_are_only_conventions():
    registry, _, _ = _modules()

    assert registry.CONVENTIONAL_FACTORY_PURPOSE == "factory"
    assert registry.RESERVED_INTERACTIVE_PURPOSE == "interactive"
    assert registry.REGISTERED_TARGET_ADAPTERS == ("isolated-run",)
    assert registry.REGISTERED_SECRET_STORE_BACKENDS == ("onepassword",)


def test_a_well_shaped_reservation_is_accepted_and_reserves_only_what_it_lists():
    _, reservations, _ = _modules()

    accepted = reservations.reservations_from_object(
        value={"anthropic": {"acct-1": ["factory"], "acct-2": ["interactive"]}},
        health_strategy="none",
    ).unwrap()

    assert accepted == {"anthropic": {"acct-1": ("factory",), "acct-2": ("interactive",)}}
    # A well-shaped key with no matching record is harmless and reserves nothing.
    assert reservations.reservations_from_object(
        value={"openai": {"acct-9": ["factory"]}}, health_strategy="none"
    ).unwrap() == {"openai": {"acct-9": ("factory",)}}


def test_every_malformed_reservation_shape_is_refused_whole():
    assert _reservation_refusal(value=[]) == "account_reservations must be an object"
    assert _reservation_refusal(value={"": {}}) == (
        "account_reservations provider must be non-empty"
    )
    assert _reservation_refusal(value={"anthropic": []}) == (
        "account_reservations[anthropic] must be an object"
    )
    assert _reservation_refusal(value={"anthropic": {"": ["factory"]}}) == (
        "account_reservations[anthropic] key must be non-empty"
    )
    assert _reservation_refusal(value={"anthropic": {"a": []}}) == (
        "account_reservations[anthropic][a] must be a non-empty array"
    )
    assert _reservation_refusal(value={"anthropic": {"a": "factory"}}) == (
        "account_reservations[anthropic][a] must be a non-empty array"
    )
    assert _reservation_refusal(value={"anthropic": {"a": [""]}}) == (
        "account_reservations[anthropic][a] purposes must be non-empty strings"
    )
    assert _reservation_refusal(value={"anthropic": {"a": [1]}}) == (
        "account_reservations[anthropic][a] purposes must be non-empty strings"
    )
    assert _reservation_refusal(value={"anthropic": {"a": ["factory", "factory"]}}) == (
        "account_reservations[anthropic][a] purposes must be unique"
    )


def test_a_multi_purpose_reservation_needs_remaining_percent_and_a_declared_observer():
    shared = {"anthropic": {"acct-1": ["factory", "interactive"]}}

    assert _reservation_refusal(value=shared) == (
        "account_reservations[anthropic][acct-1] reserves several purposes, which "
        "requires health_strategy remaining-percent"
    )
    assert _reservation_refusal(value=shared, health_strategy="remaining-percent") == (
        "account_reservations[anthropic][acct-1] reserves several purposes, but "
        "registered kind claude-code-oauth declares no shared-usage observer"
    )


def test_a_multi_purpose_reservation_for_an_unregistered_provider_has_no_row_to_refuse():
    _, reservations, _ = _modules()

    accepted = reservations.reservations_from_object(
        value={"openai": {"acct-1": ["factory", "interactive"]}},
        health_strategy="remaining-percent",
    ).unwrap()

    # No registered row declares `unsupported` for this provider, so the capacity-floor
    # premise is not violated; the key simply reserves nothing until a row exists.
    assert accepted == {"openai": {"acct-1": ("factory", "interactive")}}


def test_every_error_type_carries_its_contract_exit_status():
    _, _, results = _modules()

    assert results.exit_status_for(error_type=results.INVALID_REQUEST) == 2
    assert results.exit_status_for(error_type=results.INVALID_REPORT) == 2
    assert results.exit_status_for(error_type=results.RETRYABLE_EXHAUSTION) == 3
    assert results.exit_status_for(error_type=results.STORE_UNAVAILABLE) == 4
    assert results.exit_status_for(error_type=results.PROVISIONING_FAILED) == 5
    assert results.exit_status_for(error_type=results.INTERNAL_BUG) == 70
    assert results.SUCCESS_EXIT_STATUS == 0


def test_an_unregistered_error_type_maps_to_internal_bug_rather_than_a_plausible_neighbour():
    _, _, results = _modules()

    # `2` would let a bug present itself to a consumer as an ordinary invalid request and
    # be retried forever; `70` is the contract's own name for "no branch admits this".
    assert results.exit_status_for(error_type="provisioning-deferred") == 70


def test_a_failure_object_has_exactly_the_four_declared_members():
    _, _, results = _modules()

    emitted = results.error_object(error=results.store_unavailable(message="namespace absent"))

    assert emitted == {
        "version": 1,
        "status": "error",
        "error_type": "store-unavailable",
        "message": "namespace absent",
    }
    assert results.invalid_request(message="m").error_type == "invalid-request"
    assert results.internal_bug(message="m").error_type == "internal-bug"
