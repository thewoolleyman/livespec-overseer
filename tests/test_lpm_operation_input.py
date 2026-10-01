"""A stored operation carries its command's EXACT input and a phase's LEGAL effect array.

SPECIFICATION/contracts.md states `normalized_input` as "the command's exact validated input
with provisioning defaults materialized" and then fixes each command's membership literally;
it separately requires a phase's `ordered_effects` to be the array that phase states, in the
stated relative order.

MEMBERSHIP IS THE REPLAY CONTRACT, WHICH IS WHY THESE ARE EXACT IN BOTH DIRECTIONS. A resuming
process re-derives what to do from this object alone — which lease to take, which record to
transition, which target to write — so a merely-a-JSON-object input would let a recovery replay
a command whose inputs it cannot reconstruct. Two rules are sharper than they look and are
asserted directly: `report` MUST OMIT `diagnostic`, because the diagnostic is validated and then
discarded and a stored copy would put consumer prose into a durable record; and provision's
optional members MUST already be materialized, because the stored object is what an "identical
request" is compared against.

THE EFFECT-ARRAY CHECK IS A RELATION, NOT A SPELL-CHECK. An array of perfectly ratified names
that no phase states is exactly the shape a hand-edited or half-migrated record has, and it is
the one a positional replay would walk off the end of. A stored record carries no `PlanContext`,
so the validator cannot pick the ONE right array — but it can refuse every array the contract
never admits, and the test asserts both halves of that: the admissible set for a phase, and the
empty set for a pair the contract does not state.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_OPERATION_ID = "1b4e28ba-2fa1-4d82-a4cc-3d9c5c0bb4a1"
_KEY = "b" * 64
_ACCEPTED_AT = "2026-09-30T12:00:00Z"


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _input():
    return _module("_lpm_operation_input")


def _inputs_by_command() -> dict[str, dict[str, object]]:
    return {
        "acquire": {
            "version": 1,
            "provider": "anthropic",
            "account_id": "acct-1",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "record_id": _RECORD_ID,
            "next_value_generation": _GENERATION,
        },
        "reacquire": {"record_id": _RECORD_ID, "next_value_generation": _GENERATION},
        "revalidate": {"record_id": _RECORD_ID},
        "target": {"version": 1, "consumer_run_id": "run-7", "adapter": "isolated-run"},
        "provision": {
            "version": 1,
            "provider": "anthropic",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "consumer_run_id": "run-7",
            "target_ref": "ref-7",
            "strategy": "consume-first",
            "lease_seconds": 21600,
        },
        "report": {
            "version": 1,
            "consumer_run_id": "run-7",
            "record_id": _RECORD_ID,
            "occurred_at": _ACCEPTED_AT,
            "classification": "authentication",
        },
        "complete": {
            "version": 1,
            "consumer_run_id": "run-7",
            "record_id": _RECORD_ID,
            "completed_at": _ACCEPTED_AT,
            "consumer_class": "production",
            "provider_authenticated": True,
            "alternate_credential_used": False,
            "legacy_pool_absent": False,
        },
        "release": {"version": 1, "consumer_run_id": "run-7", "record_id": _RECORD_ID},
        "expire": {"consumer_run_id": "run-7", "record_id": _RECORD_ID},
    }


def _defect(*, command: str, **changes: object) -> str | None:
    stored = _inputs_by_command()[command]
    stored.update(changes)
    return _input().normalized_input_defect(command=command, normalized_input=stored)


# ---------------------------------------------------------------------------
# The exact per-command membership
# ---------------------------------------------------------------------------


def test_every_command_declares_the_exact_membership_the_contract_states():
    module = _input()

    assert module.NORMALIZED_INPUT_MEMBERS == {
        "acquire": (
            "version",
            "provider",
            "account_id",
            "kind",
            "purpose",
            "record_id",
            "next_value_generation",
        ),
        "reacquire": ("record_id", "next_value_generation"),
        "revalidate": ("record_id",),
        "target": ("version", "consumer_run_id", "adapter"),
        "provision": (
            "version",
            "provider",
            "kind",
            "purpose",
            "consumer_run_id",
            "target_ref",
            "strategy",
            "lease_seconds",
        ),
        "report": ("version", "consumer_run_id", "record_id", "occurred_at", "classification"),
        "complete": (
            "version",
            "consumer_run_id",
            "record_id",
            "completed_at",
            "consumer_class",
            "provider_authenticated",
            "alternate_credential_used",
            "legacy_pool_absent",
        ),
        "release": ("version", "consumer_run_id", "record_id"),
        "expire": ("consumer_run_id", "record_id"),
    }
    for command, stored in _inputs_by_command().items():
        assert (
            _input().normalized_input_defect(command=command, normalized_input=stored) is None
        ), f"{command}'s own exact input must validate"


def test_the_three_internal_commands_carry_no_request_version():
    module = _input()

    for command in ("reacquire", "revalidate", "expire"):
        assert (
            "version" not in module.NORMALIZED_INPUT_MEMBERS[command]
        ), f"{command} is never invoked by a consumer and has no request envelope to version"
        assert _defect(command=command, version=1) == (
            f"{command} normalized_input must contain exactly "
            f"{', '.join(module.NORMALIZED_INPUT_MEMBERS[command])}"
        )


def test_a_report_input_must_omit_the_diagnostic_it_discarded():
    assert _defect(command="report", diagnostic="a 401 from the provider") == (
        "report normalized_input must contain exactly version, consumer_run_id, record_id, "
        "occurred_at, classification"
    ), "the diagnostic is validated and then DISCARDED; a stored copy is durable consumer prose"


def test_a_provision_input_must_already_have_its_optional_members_materialized():
    stored = _inputs_by_command()["provision"]
    del stored["strategy"]

    assert _input().normalized_input_defect(command="provision", normalized_input=stored) == (
        "provision normalized_input must contain exactly version, provider, kind, purpose, "
        "consumer_run_id, target_ref, strategy, lease_seconds"
    ), "the stored object is what an identical request is compared against"


def test_an_unregistered_command_or_a_non_object_input_is_refused():
    module = _input()

    assert module.normalized_input_defect(command="rotate", normalized_input={}) == (
        "unregistered operation command: rotate"
    )
    assert module.normalized_input_defect(command="revalidate", normalized_input=[_RECORD_ID]) == (
        "normalized_input must be a JSON object"
    )


def test_every_field_kind_has_its_own_rule_rather_than_a_shared_string_check():
    module = _input()

    assert module.NORMALIZED_INPUT_VERSION == 1
    assert module.CONSUMER_CLASSES == ("test", "production")
    assert (
        _defect(command="acquire", version=True) == "normalized_input version must be the integer 1"
    )
    assert _defect(command="acquire", provider="") == (
        "normalized_input provider must be a non-empty string"
    )
    assert _defect(command="acquire", record_id="NOT-A-UUID") == (
        "normalized_input record_id must be a lowercase RFC 4122 UUIDv4"
    )
    assert _defect(command="report", occurred_at="2026-09-30 12:00:00") == (
        "normalized_input occurred_at must be a UTC RFC 3339-second timestamp"
    )
    assert _defect(command="report", classification="vibes") == (
        "normalized_input classification must be one of: authentication, rate-limit, "
        "provider-outage, unknown"
    )
    assert _defect(command="provision", strategy="whatever") == (
        "normalized_input strategy must be one of: consume-first, spread"
    )
    assert _defect(command="provision", lease_seconds=59) == (
        "normalized_input lease_seconds must be an integer from 60 through 86400"
    )
    assert _defect(command="provision", lease_seconds=True) == (
        "normalized_input lease_seconds must be an integer from 60 through 86400"
    )
    assert _defect(command="complete", consumer_class="staging") == (
        "normalized_input consumer_class must be one of: test, production"
    )
    assert _defect(command="complete", provider_authenticated="yes") == (
        "normalized_input provider_authenticated must be a Boolean"
    )


# ---------------------------------------------------------------------------
# The legal phase/effect relation, at the record boundary
# ---------------------------------------------------------------------------


def _record(**changes: object) -> dict[str, object]:
    source: dict[str, object] = {
        "version": 1,
        "operation_id": _OPERATION_ID,
        "command": "report",
        "phase": "apply",
        "idempotency_key": _KEY,
        "accepted_at": _ACCEPTED_AT,
        "normalized_input": _inputs_by_command()["report"],
        "terminal_result": None,
        "ordered_effects": [
            "audit-append",
            "credential-conditional-set",
            "proof-update",
            "report-marker-update",
            "assignment-end-update",
            "lease-release",
            "tombstone-create",
            "assignment-close",
        ],
        "completed_step": -1,
    }
    source.update(changes)
    return source


def test_the_admissible_arrays_for_a_phase_are_the_ones_the_contract_states():
    plan = _module("_lpm_operation_plan")

    report = plan.admissible_effect_arrays(command="report", phase="apply")
    cleanup = plan.admissible_effect_arrays(command="provision", phase="cleanup")
    launch = plan.admissible_effect_arrays(command="acquire", phase="launch")

    assert len(report) == 2, "report apply states a live array and its tombstone prefix"
    assert report[0][:4] == (
        "audit-append",
        "credential-conditional-set",
        "proof-update",
        "report-marker-update",
    )
    assert report[1] == report[0][:4]
    assert cleanup == (("lease-release",), ("prepared-assignment-discard", "lease-release"))
    assert len(launch) == 1, "a worker launch states exactly one array"
    assert (
        plan.admissible_effect_arrays(command="acquire", phase="issue") == ()
    ), "a pair the contract does not state admits NO array"


def test_a_ratified_name_in_an_array_no_phase_states_is_still_refused():
    operation = _module("_lpm_operation")

    tombstone_prefix = operation.operation_from_object(
        parsed=_record(
            ordered_effects=[
                "audit-append",
                "credential-conditional-set",
                "proof-update",
                "report-marker-update",
            ]
        )
    )
    reordered = operation.operation_from_object(
        parsed=_record(
            ordered_effects=[
                "credential-conditional-set",
                "audit-append",
                "proof-update",
                "report-marker-update",
            ]
        )
    )
    truncated = operation.operation_from_object(
        parsed=_record(ordered_effects=["audit-append", "credential-conditional-set"])
    )
    unregistered = operation.operation_from_object(
        parsed=_record(ordered_effects=["audit-append", "not-an-effect"])
    )

    assert (
        tombstone_prefix.unwrap().ordered_effects[-1] == "report-marker-update"
    ), "the tombstone prefix IS an admissible array"
    assert reordered.failure().message == (
        "ordered_effects must be an effect array the contract admits for this phase"
    ), "an audit-append ordered AFTER its paired credential effect breaks the pairing rule"
    assert truncated.failure().message == (
        "ordered_effects must be an effect array the contract admits for this phase"
    )
    assert (
        unregistered.failure().message == "ordered_effects must name only ratified effects"
    ), "the vocabulary check still reports an unratified name as such"


def test_a_record_whose_input_is_not_its_command_s_exact_input_is_refused():
    operation = _module("_lpm_operation")

    wrong_command_input = operation.operation_from_object(
        parsed=_record(normalized_input=_inputs_by_command()["release"])
    )

    assert wrong_command_input.failure().error_type == "store-unavailable"
    assert wrong_command_input.failure().message == (
        "report normalized_input must contain exactly version, consumer_run_id, record_id, "
        "occurred_at, classification"
    )
