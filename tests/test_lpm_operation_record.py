"""The write-ahead operation record is exactly ten members, and its phases are closed.

SPECIFICATION/contracts.md states the record as containing EXACTLY `version`,
`operation_id`, `command`, `phase`, `idempotency_key`, `accepted_at`, `normalized_input`,
`terminal_result`, `ordered_effects` and `completed_step`, closes the nine-command
vocabulary and the phases each command may stand in, fixes every phase's ordered effect
array literally, and derives each position's `effect_id` from
`LP(operation_id) || LP(command) || LP(idempotency_key) || LP(phase) || LP(base10-index)`.

THE POSITIONAL TESTS ARE THE LOAD-BEARING ONES. Repeated effect names are permitted — an
acquire `terminal` phase appends to the audit log twice — so a name cannot identify a
position, and a replay keyed on names would mark the second append complete because the
first one was. These tests therefore re-derive the digest independently from the contract's
own formula rather than comparing the implementation with itself, and assert that two
positions holding the SAME effect name carry DIFFERENT identifiers.

The terminal-result tests exercise one defect per invariant. A validator that stops at the
first shape it recognizes passes a suite that only ever shows it well-formed results, and
the success and failure forms here are deliberately disjoint: a result carrying both a
publication time and a rejection reason would describe a credential that was simultaneously
published and refused.
"""

from __future__ import annotations

import hashlib
import importlib
import pathlib

__all__: list[str] = []

_OPERATION_ID = "1b4e28ba-2fa1-4d82-a4cc-3d9c5c0bb4a1"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_KEY = "b" * 64
_ACCEPTED_AT = "2026-09-30T12:00:00Z"
_NEXT_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def _acquire_input() -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "account_id": "acct-1",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "record_id": _RECORD_ID,
        "next_value_generation": _NEXT_GENERATION,
    }


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _operation():
    return _module("_lpm_operation")


def _identity():
    return _module("_lpm_operation_identity")


def _terminal():
    return _module("_lpm_operation_terminal")


def _plan():
    return _module("_lpm_operation_plan")


def _length_prefixed(value: str) -> bytes:
    data = value.encode("utf-8")
    return len(data).to_bytes(8, "big") + data


def _digest(*values: str) -> str:
    running = hashlib.sha256()
    for value in values:
        running.update(_length_prefixed(value))
    return running.hexdigest()


def _acquire_terminal_object() -> dict[str, object]:
    return {
        "version": 1,
        "operation_id": _OPERATION_ID,
        "command": "acquire",
        "phase": "terminal",
        "idempotency_key": _KEY,
        "accepted_at": _ACCEPTED_AT,
        "normalized_input": _acquire_input(),
        "terminal_result": {
            "outcome": "success",
            "validated_at": "2026-09-30T12:00:05Z",
            "published_at": "2026-09-30T12:00:05Z",
            "expires_at": None,
            "failure_reason": None,
        },
        "ordered_effects": [
            "audit-append",
            "secret-value-set",
            "audit-append",
            "credential-conditional-set",
            "worker-record-remove",
        ],
        "completed_step": -1,
    }


def _refusal(**changes: object):
    source = _acquire_terminal_object()
    source.update(changes)
    return _operation().operation_from_object(parsed=source).failure()


def _accepted(**changes: object):
    source = _acquire_terminal_object()
    source.update(changes)
    return _operation().operation_from_object(parsed=source).unwrap()


# ---------------------------------------------------------------------------
# The ten-member record and its closed vocabularies
# ---------------------------------------------------------------------------


def test_the_operation_record_is_exactly_the_ten_ratified_members():
    module = _operation()

    assert module.OPERATION_MEMBERS == (
        "version",
        "operation_id",
        "command",
        "phase",
        "idempotency_key",
        "accepted_at",
        "normalized_input",
        "terminal_result",
        "ordered_effects",
        "completed_step",
    )
    assert (
        len(module.OPERATION_MEMBERS) == 10
    ), "a five-field substitute was refused for this engine"
    assert module.UNSTARTED_STEP == -1
    operation = _accepted()
    assert module.operation_object(operation=operation) == _acquire_terminal_object()


def test_each_command_declares_only_its_ratified_phases():
    module = _operation()

    assert module.PHASES_BY_COMMAND == {
        "acquire": ("launch", "terminal", "recovery"),
        "reacquire": ("launch", "terminal", "recovery"),
        "revalidate": ("launch", "terminal", "recovery"),
        "target": ("issue",),
        "provision": ("start", "cleanup", "postcommit"),
        "report": ("apply",),
        "complete": ("apply",),
        "release": ("apply",),
        "expire": ("close",),
    }
    assert tuple(module.PHASES_BY_COMMAND) == module.OPERATION_COMMANDS
    assert module.WORKER_COMMANDS == ("acquire", "reacquire", "revalidate")
    assert _refusal(phase="issue").message == (
        "phase must be one of launch, terminal, recovery for acquire"
    ), "a command may stand only in a phase its own vocabulary declares"
    assert _refusal(terminal_result=None).message == (
        "a terminal phase must carry its command's terminal-result object"
    ), "the record validator refuses a terminal phase with no durable outcome"


def test_the_effect_vocabulary_is_closed_and_repeated_names_are_permitted():
    module = _operation()

    assert module.EFFECT_NAMES == (
        "worker-record-create",
        "audit-append",
        "secret-value-set",
        "credential-conditional-set",
        "worker-record-remove",
        "registration-remove",
        "issuance-create",
        "lease-create",
        "prepared-assignment-create",
        "target-write",
        "assignment-commit",
        "prepared-assignment-discard",
        "selection-update",
        "proof-update",
        "report-marker-update",
        "completion-update",
        "assignment-end-update",
        "lease-release",
        "tombstone-create",
        "assignment-close",
    )
    accepted = _accepted()
    assert accepted.ordered_effects.count("audit-append") == 2, "repeated names are permitted"
    assert _refusal(ordered_effects=["audit-append", "not-an-effect"]).message == (
        "ordered_effects must name only ratified effects"
    )


def test_every_membership_and_type_defect_fails_closed_as_store_unavailable():
    module = _operation()
    missing = _acquire_terminal_object()
    del missing["accepted_at"]

    assert module.operation_from_object(parsed=["not", "an", "object"]).failure().message == (
        "operation record must be a JSON object"
    )
    assert module.operation_from_object(parsed=missing).failure().message == (
        "operation record is missing accepted_at"
    )
    assert _refusal(extra_member=1).message == "operation record has extra member extra_member"
    assert _refusal(version=True).message == "operation record version must be the integer 1"
    assert _refusal(version=2).message == "operation record version must be the integer 1"
    assert _refusal(operation_id="NOT-A-UUID").message == (
        "operation_id must be a lowercase RFC 4122 UUIDv4"
    )
    assert _refusal(command="rotate").message == "command must be one ratified operation command"
    assert _refusal(idempotency_key="short").message == (
        "idempotency_key must be a lowercase SHA-256 hex digest"
    )
    assert _refusal(accepted_at="2026-09-30 12:00:00").message == (
        "accepted_at must be a UTC RFC 3339-second timestamp"
    )
    assert _refusal(normalized_input=["a"]).message == "normalized_input must be a JSON object"
    assert _refusal(operation_id="NOT-A-UUID").error_type == "store-unavailable"


def test_completed_step_runs_from_minus_one_through_the_last_effect_index():
    assert _refusal(ordered_effects=[]).message == "ordered_effects must be a non-empty array"
    assert _refusal(ordered_effects="audit-append").message == (
        "ordered_effects must be a non-empty array"
    )
    assert _refusal(completed_step=True).message == "completed_step must be an integer"
    assert _refusal(completed_step=-2).message == (
        "completed_step must run from -1 through the last effect index"
    )
    assert _refusal(completed_step=5).message == (
        "completed_step must run from -1 through the last effect index"
    )
    assert _accepted(completed_step=4).completed_step == 4, "the last index is in range"


# ---------------------------------------------------------------------------
# Positional, stable effect identity
# ---------------------------------------------------------------------------


def test_effect_identity_is_positional_so_two_identical_names_differ():
    module = _identity()
    operation = _accepted()

    first = module.effect_id(operation=operation, index=0).unwrap()
    third = module.effect_id(operation=operation, index=2).unwrap()

    assert operation.ordered_effects[0] == operation.ordered_effects[2] == "audit-append"
    assert first == _digest(_OPERATION_ID, "acquire", _KEY, "terminal", "0")
    assert third == _digest(_OPERATION_ID, "acquire", _KEY, "terminal", "2")
    assert first != third, "a name cannot identify a position; the index must"


def test_replacing_the_phase_gives_every_effect_a_new_identity():
    module = _identity()
    terminal = _accepted()
    recovery = _accepted(
        phase="recovery",
        terminal_result=_terminal().recovery_terminal_result(command="acquire"),
        ordered_effects=["audit-append", "credential-conditional-set", "worker-record-remove"],
    )

    assert module.effect_id(operation=terminal, index=0).unwrap() != (
        module.effect_id(operation=recovery, index=0).unwrap()
    )
    assert module.effect_id(operation=recovery, index=0).unwrap() == _digest(
        _OPERATION_ID, "acquire", _KEY, "recovery", "0"
    )


def test_an_index_outside_the_stored_plan_is_a_caller_bug():
    module = _identity()
    operation = _accepted()

    assert module.effect_id(operation=operation, index=-1).failure().error_type == "internal-bug"
    assert module.effect_id(operation=operation, index=5).failure().message == (
        "effect index is outside the operation's ordered effects"
    )


def test_the_idempotency_key_is_the_contract_s_length_prefixed_digest_per_command():
    module = _identity()

    assert _operation().IDEMPOTENCY_FIELDS["acquire"] == (
        "provider",
        "account_id",
        "kind",
        "purpose",
    )
    acquire = module.idempotency_key_for(
        command="acquire",
        identity={
            "provider": "anthropic",
            "account_id": "acct-1",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "ignored": "not part of the digest",
        },
    ).unwrap()
    report = module.idempotency_key_for(
        command="report",
        identity={
            "consumer_run_id": "run-7",
            "record_id": _RECORD_ID,
            "occurred_at": _ACCEPTED_AT,
            "classification": "authentication",
        },
    ).unwrap()

    assert acquire == _digest("anthropic", "acct-1", "claude-code-oauth", "factory")
    assert report == _digest("run-7", _RECORD_ID, _ACCEPTED_AT, "authentication")
    assert module.idempotency_key_for(command="rotate", identity={}).failure().message == (
        "unregistered operation command: rotate"
    )
    assert module.idempotency_key_for(
        command="complete", identity={"record_id": _RECORD_ID}
    ).failure().message == ("complete identity needs consumer_run_id, record_id")


# ---------------------------------------------------------------------------
# The terminal-result shapes
# ---------------------------------------------------------------------------


def test_terminal_result_is_null_outside_a_worker_terminal_or_recovery_phase():
    module = _terminal()

    assert module.WORKER_RESULT_PHASES == ("terminal", "recovery")
    assert (
        module.terminal_result_defect(
            command="provision", phase="start", terminal_result={"outcome": "success"}
        )
        == "terminal_result must be null outside a worker terminal or recovery phase"
    )
    assert (
        module.terminal_result_defect(command="provision", phase="start", terminal_result=None)
        is None
    )
    assert (
        module.terminal_result_defect(command="acquire", phase="terminal", terminal_result=None)
        == "a terminal phase must carry its command's terminal-result object"
    )


def test_the_acquire_terminal_result_shape_is_exact():
    module = _terminal()

    def _defect(**changes: object) -> str | None:
        result: dict[str, object] = {
            "outcome": "success",
            "validated_at": "2026-09-30T12:00:05Z",
            "published_at": "2026-09-30T12:00:06Z",
            "expires_at": "2026-09-30T13:00:00Z",
            "failure_reason": None,
        }
        result.update(changes)
        return module.terminal_result_defect(
            command="acquire", phase="terminal", terminal_result=result
        )

    assert module.ACQUIRE_TERMINAL_MEMBERS == (
        "outcome",
        "validated_at",
        "published_at",
        "expires_at",
        "failure_reason",
    )
    assert module.ACQUIRE_FAILURE_REASONS == (
        "provider-rejected",
        "flow-unavailable",
        "step-limit",
    )
    assert _defect() is None
    assert _defect(expires_at=None) is None
    assert _defect(outcome="partial") == "outcome must be success or failure"
    assert _defect(unexpected=1) == (
        "terminal_result must contain exactly outcome, validated_at, published_at, "
        "expires_at, failure_reason"
    )
    assert _defect(validated_at=None) == (
        "validated_at must be a UTC RFC 3339-second timestamp on success"
    )
    assert _defect(published_at="later") == (
        "published_at must be a UTC RFC 3339-second timestamp on success"
    )
    assert _defect(failure_reason="step-limit") == (
        "a success terminal result carries no failure_reason"
    )
    assert _defect(published_at="2026-09-30T12:00:04Z") == (
        "published_at must be no earlier than validated_at"
    )
    assert _defect(expires_at="whenever") == (
        "expires_at must be null or a UTC RFC 3339-second timestamp"
    )
    assert _defect(expires_at="2026-09-30T12:00:06Z") == (
        "expires_at must be later than published_at"
    ), "equality is not later"


def test_an_acquire_failure_terminal_result_carries_no_timestamp_at_all():
    module = _terminal()

    def _defect(**changes: object) -> str | None:
        result: dict[str, object] = {
            "outcome": "failure",
            "validated_at": None,
            "published_at": None,
            "expires_at": None,
            "failure_reason": "provider-rejected",
        }
        result.update(changes)
        return module.terminal_result_defect(
            command="reacquire", phase="terminal", terminal_result=result
        )

    assert _defect() is None
    assert _defect(validated_at="2026-09-30T12:00:05Z") == (
        "a failure terminal result must have null validated_at"
    )
    assert _defect(expires_at="2026-09-30T12:00:05Z") == (
        "a failure terminal result must have null expires_at"
    )
    assert _defect(failure_reason="gave-up") == (
        "failure_reason must be one of provider-rejected, flow-unavailable, step-limit"
    )


def test_the_revalidate_terminal_result_shape_is_exact():
    module = _terminal()

    def _defect(**changes: object) -> str | None:
        result: dict[str, object] = {
            "outcome": "success",
            "validated_at": "2026-09-30T12:00:05Z",
            "failure_kind": None,
        }
        result.update(changes)
        return module.terminal_result_defect(
            command="revalidate", phase="terminal", terminal_result=result
        )

    assert module.REVALIDATE_TERMINAL_MEMBERS == ("outcome", "validated_at", "failure_kind")
    assert module.REVALIDATE_FAILURE_KINDS == ("rejected", "inconclusive")
    assert _defect() is None
    assert _defect(validated_at=None) == (
        "validated_at must be a UTC RFC 3339-second timestamp on success"
    )
    assert _defect(failure_kind="rejected") == "a success terminal result carries no failure_kind"
    assert _defect(outcome="failure") == "a failure terminal result must have null validated_at"
    assert _defect(outcome="failure", validated_at=None, failure_kind="unsure") == (
        "failure_kind must be one of rejected, inconclusive"
    )
    assert _defect(outcome="failure", validated_at=None, failure_kind="rejected") is None


def test_a_recovery_phase_carries_only_its_command_s_undecided_failure_form():
    module = _terminal()
    acquire = module.recovery_terminal_result(command="acquire")
    revalidate = module.recovery_terminal_result(command="revalidate")

    assert acquire == {
        "outcome": "failure",
        "validated_at": None,
        "published_at": None,
        "expires_at": None,
        "failure_reason": "flow-unavailable",
    }
    assert revalidate == {
        "outcome": "failure",
        "validated_at": None,
        "failure_kind": "inconclusive",
    }
    assert (
        module.terminal_result_defect(command="acquire", phase="recovery", terminal_result=acquire)
        is None
    )
    assert (
        module.terminal_result_defect(
            command="revalidate", phase="recovery", terminal_result=revalidate
        )
        is None
    )
    assert (
        module.terminal_result_defect(
            command="acquire",
            phase="recovery",
            terminal_result={**acquire, "failure_reason": "provider-rejected"},
        )
        == "acquire recovery must use failure_reason flow-unavailable"
    )
    assert (
        module.terminal_result_defect(
            command="revalidate",
            phase="recovery",
            terminal_result={**revalidate, "failure_kind": "rejected"},
        )
        == "revalidate recovery must use failure_kind inconclusive"
    ), "rejected would make the durable target state dead rather than suspect"
    assert (
        module.terminal_result_defect(
            command="acquire",
            phase="recovery",
            terminal_result={
                "outcome": "success",
                "validated_at": "2026-09-30T12:00:05Z",
                "published_at": "2026-09-30T12:00:05Z",
                "expires_at": None,
                "failure_reason": None,
            },
        )
        == "a recovery phase must carry its command's failure terminal result"
    )


# ---------------------------------------------------------------------------
# The ordered effect arrays, the transitions and the actor table
# ---------------------------------------------------------------------------


def test_every_worker_phase_declares_its_literal_effect_array():
    module = _plan()
    context = module.PlanContext()

    def _effects(command: str, phase: str) -> tuple[str, ...]:
        return module.ordered_effects_for(command=command, phase=phase, context=context).unwrap()

    assert _effects("acquire", "launch") == (
        "worker-record-create",
        "audit-append",
        "credential-conditional-set",
    )
    assert _effects("revalidate", "launch") == _effects("reacquire", "launch")
    assert _effects("acquire", "terminal") == (
        "audit-append",
        "secret-value-set",
        "audit-append",
        "credential-conditional-set",
        "worker-record-remove",
    )
    assert _effects("revalidate", "terminal") == (
        "audit-append",
        "credential-conditional-set",
        "worker-record-remove",
    )
    assert _effects("acquire", "recovery") == _effects("revalidate", "recovery")
    assert (
        module.ordered_effects_for(command="acquire", phase="issue", context=context)
        .failure()
        .message
        == "acquire has no issue phase"
    )


def test_target_provision_and_expire_phases_declare_their_literal_arrays():
    module = _plan()
    plain = module.PlanContext()
    prepared = module.PlanContext(prepared_state_exists=True)

    def _effects(command: str, phase: str, context) -> tuple[str, ...]:
        return module.ordered_effects_for(command=command, phase=phase, context=context).unwrap()

    assert _effects("target", "issue", plain) == ("issuance-create", "registration-remove")
    assert _effects("provision", "start", plain) == (
        "lease-create",
        "prepared-assignment-create",
        "target-write",
    )
    assert _effects("provision", "postcommit", plain) == (
        "assignment-commit",
        "selection-update",
        "proof-update",
    )
    assert _effects("provision", "cleanup", prepared) == (
        "prepared-assignment-discard",
        "lease-release",
    )
    assert _effects("provision", "cleanup", plain) == (
        "lease-release",
    ), "cleanup always ends with lease-release, so it is never empty"
    assert _effects("expire", "close", plain) == (
        "assignment-end-update",
        "lease-release",
        "tombstone-create",
        "assignment-close",
    )
    assert (
        module.ordered_effects_for(command="target", phase="start", context=plain).failure().message
        == "the only phase here is issue, not start"
    )
    assert (
        module.ordered_effects_for(command="provision", phase="apply", context=plain)
        .failure()
        .message
        == "provision has no apply phase"
    )


def test_report_and_complete_apply_against_a_tombstone_are_the_leading_prefix():
    module = _plan()
    live = module.PlanContext()
    tombstone = module.PlanContext(against_tombstone=True)

    def _effects(command: str, context) -> tuple[str, ...]:
        return module.ordered_effects_for(command=command, phase="apply", context=context).unwrap()

    assert _effects("report", live) == (
        "audit-append",
        "credential-conditional-set",
        "proof-update",
        "report-marker-update",
        "assignment-end-update",
        "lease-release",
        "tombstone-create",
        "assignment-close",
    )
    assert _effects("report", tombstone) == _effects("report", live)[:4]
    assert _effects("complete", live) == (
        "proof-update",
        "completion-update",
        "assignment-end-update",
        "lease-release",
        "tombstone-create",
        "assignment-close",
    )
    assert _effects("complete", tombstone) == _effects("complete", live)[:2]
    assert _effects("release", live) == (
        "assignment-end-update",
        "lease-release",
        "tombstone-create",
        "assignment-close",
    )
    assert (
        module.ordered_effects_for(command="report", phase="close", context=live).failure().message
        == "report has no close phase"
    )
    assert (
        module.ordered_effects_for(command="rotate", phase="apply", context=live).failure().message
        == "unregistered operation command: rotate"
    )


def test_phase_transitions_are_named_conditions_rather_than_inferences():
    module = _plan()

    assert module.TRANSITION_CONDITIONS == (
        "worker-terminal",
        "worker-lost",
        "terminal-success-rewrite",
        "target-committed",
        "pre-commit-failure",
        "every-effect-committed",
    )
    assert module.next_phase(phase="launch", condition="worker-terminal").unwrap() == "terminal"
    assert module.next_phase(phase="launch", condition="worker-lost").unwrap() == "recovery"
    assert (
        module.next_phase(phase="terminal", condition="terminal-success-rewrite").unwrap()
        == "recovery"
    )
    assert module.next_phase(phase="start", condition="target-committed").unwrap() == "postcommit"
    assert module.next_phase(phase="start", condition="pre-commit-failure").unwrap() == "cleanup"
    assert module.next_phase(phase="close", condition="every-effect-committed").unwrap() is None
    assert module.next_phase(phase="launch", condition="target-committed").failure().message == (
        "no ratified transition from launch under target-committed"
    )


def test_the_audit_actor_is_a_property_of_the_phase_not_of_the_resuming_process():
    module = _plan()

    def _role(command: str, phase: str, effect: str, outcome: str | None = None) -> str:
        return module.writer_role_for(
            command=command, phase=phase, effect=effect, outcome=outcome
        ).unwrap()

    assert module.WRITER_ROLES == (
        "acquisition-writer",
        "lifecycle-writer",
        "report-writer",
        "recovery-writer",
    )
    assert _role("acquire", "launch", "credential-conditional-set") == "acquisition-writer"
    assert _role("reacquire", "launch", "credential-conditional-set") == "lifecycle-writer"
    assert _role("revalidate", "launch", "audit-append") == "lifecycle-writer"
    assert _role("acquire", "terminal", "secret-value-set", "failure") == "acquisition-writer"
    assert _role("acquire", "terminal", "credential-conditional-set", "success") == (
        "acquisition-writer"
    )
    assert _role("acquire", "terminal", "credential-conditional-set", "failure") == (
        "lifecycle-writer"
    )
    assert _role("revalidate", "terminal", "credential-conditional-set", "success") == (
        "lifecycle-writer"
    )
    assert _role("acquire", "recovery", "credential-conditional-set") == "recovery-writer"
    assert _role("report", "apply", "credential-conditional-set") == "report-writer"
    assert (
        module.writer_role_for(
            command="provision", phase="start", effect="lease-create", outcome=None
        )
        .failure()
        .message
        == "lease-create is not an audited effect"
    )
    assert (
        module.writer_role_for(command="target", phase="issue", effect="audit-append", outcome=None)
        .failure()
        .message
        == "target issue audits no credential effect"
    )
