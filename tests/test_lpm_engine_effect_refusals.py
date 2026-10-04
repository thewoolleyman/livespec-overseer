"""Every refusal and conditional no-op the engine's effects owe, exercised one by one.

SPECIFICATION/contracts.md makes the non-happy answers part of the contract rather than
incidental error handling: after inspecting its position's authoritative state, an executor
whose postcondition is neither satisfied nor exactly its permitted predecessor "MUST follow an
explicitly defined conditional no-op or refusal, otherwise return `store-unavailable` without
overwriting it". So these are behaviours to prove, not branches to reach for coverage.

THE THREE RAILS ARE KEPT APART ON PURPOSE, and this file asserts which one each case rides.
`internal-bug` means the ENGINE composed a phase without the facts its own effect array needs —
the operator asked for nothing wrong. `store-unavailable` means authoritative state cannot be
read, or stands in a shape this position may not overwrite, and the record is left exactly as
found. `retryable-exhaustion` means another in-flight run holds the resource and asking again
later is the defined remedy. Collapsing any pair would turn a wait into a failure, or a defect
into something an operator is asked to retry.

AN UNSAFE RECORD IS NEVER RESET, and that is checked by BYTES rather than by the rail alone.
The contract's no-reset rule is the half that cannot be undone: a corrupt lease, assignment or
issuance is EVIDENCE of state this manager may still be bound by, and rewriting it with a fresh
one converts "I cannot tell what is running" into "nothing is running".

THE PROGRESSIVE-INPUT TABLE IS DELIBERATE. Each row fills one more member of the normalized
input than the row before it, so the refusal that fires names the NEXT missing fact. That is
the only way to show an executor asks for what it needs in a definite order instead of failing
on whichever member happens to be read first.
"""

from __future__ import annotations

import importlib
import os
import pathlib

import pytest

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_OPERATION_ID = "4d6a1bcc-5fb3-4f5d-a4e2-d6c3f4e5a617"
_KEY = "e" * 64
_ACCEPTED_AT = "2026-10-02T11:00:00Z"
_RUN_ID = "run-refusals"
_TARGET_REF = "ref-refusals-55aa"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_ACCOUNT = "acct-primary"

_PROVISION_EFFECTS = (
    "lease-create",
    "prepared-assignment-create",
    "target-write",
    "assignment-commit",
    "prepared-assignment-discard",
    "selection-update",
    "proof-update",
    "lease-release",
)


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _state(*, tmp_path: pathlib.Path) -> pathlib.Path:
    state_dir = tmp_path / "manager-state"
    state_dir.mkdir(mode=0o700)
    return state_dir


def _engine(*, state_dir: pathlib.Path):
    return _module("_lpm_engine_context").OperationEngine(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        store=_module("_lpm_store").InMemorySecretStore(),
    )


def _operation(*, command: str, phase: str, effect: str, normalized_input: dict[str, object]):
    return _module("_lpm_operation").OperationRecord(
        operation_id=_OPERATION_ID,
        command=command,
        phase=phase,
        idempotency_key=_KEY,
        accepted_at=_ACCEPTED_AT,
        normalized_input=normalized_input,
        terminal_result=None,
        ordered_effects=(effect,),
        completed_step=-1,
    )


def _selected():
    context_module = _module("_lpm_engine_context")
    return context_module.SelectedCredential(
        account_id=_ACCOUNT,
        record_id=_RECORD_ID,
        value_generation=_GENERATION,
        value_ref=f"op://values/{_GENERATION}/credential",
        receipt={
            "record_id": _RECORD_ID,
            "account_id": _ACCOUNT,
            "purpose": "factory",
            "validated_at": "2026-10-02T10:00:00Z",
            "lease_expires_at": "2026-10-02T12:00:00Z",
        },
    )


def _provision_inputs(*, tmp_path: pathlib.Path, fence_now: str = "2026-10-02T11:00:05Z"):
    context_module = _module("_lpm_engine_context")
    target_module = _module("_lpm_target")
    return context_module.EffectInputs(
        provision=context_module.ProvisionInputs(
            selected=_selected(),
            credential_value=b"sk-ant-oat0-refusals",
            destination=str(tmp_path / "target" / "credential"),
            lock=target_module.TargetLock(
                path=tmp_path / "target-lock",
                timeout_seconds=0.01,
                monotonic=lambda: 0.0,
                sleep=lambda _seconds: None,
            ),
            fence_now=fence_now,
        )
    )


def _executed(*, state_dir: pathlib.Path, operation, inputs, effect: str):
    context_module = _module("_lpm_engine_context")
    identity = _module("_lpm_operation_identity")
    return _module("_lpm_effect_registry").execute_effect(
        context=context_module.EffectContext(
            engine=_engine(state_dir=state_dir),
            operation=operation,
            inputs=inputs,
            position=identity.EffectPosition(index=0, effect=effect, effect_id="f" * 64),
        )
    )


def _run_effect(
    *,
    state_dir: pathlib.Path,
    effect: str,
    normalized_input: dict[str, object],
    inputs=None,
    command: str = "provision",
    phase: str = "start",
):
    operation = _operation(
        command=command, phase=phase, effect=effect, normalized_input=normalized_input
    )
    return _executed(
        state_dir=state_dir,
        operation=operation,
        inputs=inputs if inputs is not None else _module("_lpm_engine_context").EffectInputs(),
        effect=effect,
    )


def _family_path(*, state_dir: pathlib.Path, family: str, identity: tuple[str, ...]):
    located = _module("_lpm_paths").local_record_path(
        state_dir=state_dir, family=family, identity=identity
    )
    assert isinstance(located, Success)
    return located.unwrap()


def _seed(*, path: pathlib.Path, value: object) -> None:
    written = _module("_lpm_localstate").write_local_record(
        path=path, value=value, owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written


def _lease_object(*, run_id: str = _RUN_ID, expires_at: str = "2026-10-02T12:00:00Z"):
    return {
        "version": 1,
        "provider": "anthropic",
        "account_id": _ACCOUNT,
        "record_id": _RECORD_ID,
        "consumer_run_id": run_id,
        "lease_started_at": _ACCEPTED_AT,
        "lease_expires_at": expires_at,
    }


def _assignment_object(*, status: str = "prepared", committed_at: str | None = None):
    return {
        "version": 1,
        "status": status,
        "request": {
            "version": 1,
            "provider": "anthropic",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "consumer_run_id": _RUN_ID,
            "target_ref": _TARGET_REF,
            "strategy": "consume-first",
            "lease_seconds": 3600,
        },
        "target_ref": _TARGET_REF,
        "account_id": _ACCOUNT,
        "value_generation": _GENERATION,
        "value_ref": f"op://values/{_GENERATION}/credential",
        "record_id": _RECORD_ID,
        "receipt": {
            "record_id": _RECORD_ID,
            "account_id": _ACCOUNT,
            "purpose": "factory",
            "validated_at": "2026-10-02T10:00:00Z",
            "lease_expires_at": "2026-10-02T12:00:00Z",
        },
        "lease_started_at": _ACCEPTED_AT,
        "lease_expires_at": "2026-10-02T12:00:00Z",
        "target_committed_at": committed_at,
        "actual_lease_ended_at": None,
        "report_markers": [],
        "completion": None,
    }


@pytest.mark.parametrize("effect", _PROVISION_EFFECTS)
def test_every_provision_effect_refuses_a_phase_composed_with_no_facts_at_all(
    tmp_path: pathlib.Path, effect: str
) -> None:
    refused = _run_effect(state_dir=_state(tmp_path=tmp_path), effect=effect, normalized_input={})

    assert isinstance(refused, Failure), effect
    assert refused.failure().error_type == "internal-bug"


@pytest.mark.parametrize(
    ("effect", "normalized_input", "fragment"),
    [
        ("lease-create", {}, "carries no provider"),
        ("lease-create", {"provider": "anthropic"}, "carries no lease_seconds"),
        (
            "lease-create",
            {"provider": "anthropic", "lease_seconds": 3600},
            "carries no consumer_run_id",
        ),
        ("prepared-assignment-create", {}, "carries no target_ref"),
        ("prepared-assignment-create", {"target_ref": _TARGET_REF}, "carries no provider"),
        ("lease-release", {"consumer_run_id": _RUN_ID}, "carries no provider"),
        ("target-write", {}, "carries no consumer_run_id"),
        ("assignment-commit", {}, "carries no target_ref"),
    ],
)
def test_each_executor_names_the_next_fact_it_is_missing(
    tmp_path: pathlib.Path, effect: str, normalized_input: dict[str, object], fragment: str
) -> None:
    refused = _run_effect(
        state_dir=_state(tmp_path=tmp_path),
        effect=effect,
        normalized_input=normalized_input,
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "internal-bug"
    assert fragment in refused.failure().message


def test_a_prepared_assignment_with_no_lease_behind_it_refuses(tmp_path: pathlib.Path) -> None:
    refused = _run_effect(
        state_dir=_state(tmp_path=tmp_path),
        effect="prepared-assignment-create",
        normalized_input={"provider": "anthropic", "target_ref": _TARGET_REF},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "left no lease to bind against" in refused.failure().message


def test_a_target_write_with_no_prepared_assignment_refuses(tmp_path: pathlib.Path) -> None:
    refused = _run_effect(
        state_dir=_state(tmp_path=tmp_path),
        effect="target-write",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "no prepared assignment stands" in refused.failure().message


def test_an_assignment_commit_with_no_committed_target_write_refuses(
    tmp_path: pathlib.Path,
) -> None:
    refused = _run_effect(
        state_dir=_state(tmp_path=tmp_path),
        effect="assignment-commit",
        normalized_input={"target_ref": _TARGET_REF},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "no committed target write stands" in refused.failure().message


def test_an_assignment_commit_with_no_assignment_refuses(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="target-commit", identity=(_TARGET_REF,)),
        value={
            "version": 1,
            "target_ref": _TARGET_REF,
            "consumer_run_id": _RUN_ID,
            "record_id": _RECORD_ID,
            "value_generation": _GENERATION,
            "committed_at": "2026-10-02T11:00:05Z",
        },
    )

    refused = _run_effect(
        state_dir=state_dir,
        effect="assignment-commit",
        normalized_input={"target_ref": _TARGET_REF},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "no assignment stands for this post-commit update" in refused.failure().message


def test_an_assignment_committed_at_another_instant_is_a_bug_not_a_rewrite(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="target-commit", identity=(_TARGET_REF,)),
        value={
            "version": 1,
            "target_ref": _TARGET_REF,
            "consumer_run_id": _RUN_ID,
            "record_id": _RECORD_ID,
            "value_generation": _GENERATION,
            "committed_at": "2026-10-02T11:00:05Z",
        },
    )
    assignment_path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    _seed(
        path=assignment_path,
        value=_assignment_object(status="committed", committed_at="2026-10-02T11:30:00Z"),
    )
    untouched = assignment_path.read_bytes()

    refused = _run_effect(
        state_dir=state_dir,
        effect="assignment-commit",
        normalized_input={"target_ref": _TARGET_REF},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "internal-bug"
    assert assignment_path.read_bytes() == untouched


def test_an_uncommittable_target_write_reports_the_prior_bytes_standing(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)),
        value=_lease_object(),
    )
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(),
    )

    refused = _run_effect(
        state_dir=state_dir,
        effect="target-write",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path, fence_now="2026-10-02T12:00:00Z"),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "provisioning-failed"
    assert not pathlib.Path(str(tmp_path / "target" / "credential")).exists()


def test_an_unacquirable_reference_lock_is_in_progress_not_uncommitted(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)),
        value=_lease_object(),
    )
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(),
    )
    # A DIRECTORY at the lock path cannot be opened as a lock file, so the adapter never
    # learns whether the destination changed — which the contract answers `in-progress`.
    (tmp_path / "target-lock").mkdir()

    refused = _run_effect(
        state_dir=state_dir,
        effect="target-write",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "still owns this target reference" in refused.failure().message


def test_a_lease_this_run_already_holds_settles_without_rewriting_it(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    lease_path = _family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    _seed(path=lease_path, value=_lease_object())
    untouched = lease_path.read_bytes()

    settled = _run_effect(
        state_dir=state_dir,
        effect="lease-create",
        normalized_input={
            "provider": "anthropic",
            "lease_seconds": 3600,
            "consumer_run_id": _RUN_ID,
        },
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(settled, Success), settled
    assert settled.unwrap() == "satisfied"
    assert lease_path.read_bytes() == untouched


@pytest.mark.parametrize(
    ("effect", "family", "identity", "normalized_input"),
    [
        (
            "lease-create",
            "lease",
            ("anthropic", _ACCOUNT),
            {"provider": "anthropic", "lease_seconds": 3600, "consumer_run_id": _RUN_ID},
        ),
        (
            "prepared-assignment-create",
            "lease",
            ("anthropic", _ACCOUNT),
            {"provider": "anthropic", "target_ref": _TARGET_REF},
        ),
        ("target-write", "assignment", (_RUN_ID,), {"consumer_run_id": _RUN_ID}),
        ("assignment-commit", "target-commit", (_TARGET_REF,), {"target_ref": _TARGET_REF}),
        ("prepared-assignment-discard", "assignment", (_RUN_ID,), {"consumer_run_id": _RUN_ID}),
        ("selection-update", "assignment", (_RUN_ID,), {"consumer_run_id": _RUN_ID}),
        ("lease-release", "assignment", (_RUN_ID,), {"consumer_run_id": _RUN_ID}),
    ],
)
def test_a_more_broadly_accessible_record_refuses_and_is_left_exactly_as_found(
    tmp_path: pathlib.Path,
    effect: str,
    family: str,
    identity: tuple[str, ...],
    normalized_input: dict[str, object],
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family=family, identity=identity)
    _seed(path=path, value={"version": 1})
    path.chmod(0o644)
    untouched = path.read_bytes()

    refused = _run_effect(
        state_dir=state_dir,
        effect=effect,
        normalized_input=normalized_input,
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure), effect
    assert refused.failure().error_type == "store-unavailable"
    assert "more broadly accessible" in refused.failure().message
    assert path.read_bytes() == untouched


@pytest.mark.parametrize(
    ("effect", "normalized_input"),
    [
        ("prepared-assignment-discard", {"consumer_run_id": _RUN_ID}),
        ("target-write", {"consumer_run_id": _RUN_ID}),
        ("selection-update", {"consumer_run_id": _RUN_ID}),
        ("proof-update", {"consumer_run_id": _RUN_ID}),
        ("lease-release", {"consumer_run_id": _RUN_ID}),
    ],
)
def test_a_malformed_stored_assignment_refuses_rather_than_being_reset(
    tmp_path: pathlib.Path, effect: str, normalized_input: dict[str, object]
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    _seed(path=path, value={"version": 1, "status": "prepared"})
    untouched = path.read_bytes()

    refused = _run_effect(
        state_dir=state_dir,
        effect=effect,
        normalized_input=normalized_input,
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure), effect
    assert refused.failure().error_type == "store-unavailable"
    assert path.read_bytes() == untouched


def test_a_malformed_stored_lease_refuses_rather_than_being_replaced(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    _seed(path=path, value={"version": 1, "provider": "anthropic"})
    untouched = path.read_bytes()

    refused = _run_effect(
        state_dir=state_dir,
        effect="lease-create",
        normalized_input={
            "provider": "anthropic",
            "lease_seconds": 3600,
            "consumer_run_id": _RUN_ID,
        },
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert path.read_bytes() == untouched


@pytest.mark.parametrize("effect", ["selection-update", "proof-update"])
def test_a_merge_effect_contributes_only_for_a_committed_assignment(
    tmp_path: pathlib.Path, effect: str
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(),
    )

    refused = _run_effect(
        state_dir=state_dir,
        effect=effect,
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure), effect
    assert refused.failure().error_type == "store-unavailable"
    assert "only a committed assignment" in refused.failure().message


@pytest.mark.parametrize("effect", ["selection-update", "proof-update"])
def test_a_merge_effect_with_no_assignment_at_all_refuses(
    tmp_path: pathlib.Path, effect: str
) -> None:
    refused = _run_effect(
        state_dir=_state(tmp_path=tmp_path),
        effect=effect,
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure), effect
    assert refused.failure().error_type == "store-unavailable"
    assert "no assignment stands for this merge effect" in refused.failure().message


def test_an_unreadable_selection_state_refuses_rather_than_resetting_it(
    tmp_path: pathlib.Path,
) -> None:
    paths = _module("_lpm_paths")
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(status="committed", committed_at="2026-10-02T11:00:05Z"),
    )
    selection = state_dir / paths.SELECTION_STATE_NAME
    _seed(path=selection, value={"version": 1})
    untouched = selection.read_bytes()

    refused = _run_effect(
        state_dir=state_dir,
        effect="selection-update",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert selection.read_bytes() == untouched


def test_an_unreadable_proof_record_refuses_rather_than_resetting_it(
    tmp_path: pathlib.Path,
) -> None:
    paths = _module("_lpm_paths")
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(status="committed", committed_at="2026-10-02T11:00:05Z"),
    )
    proof = state_dir / paths.PROOF_RECORD_NAME
    _seed(path=proof, value={"version": 1})
    untouched = proof.read_bytes()

    refused = _run_effect(
        state_dir=state_dir,
        effect="proof-update",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert proof.read_bytes() == untouched


def test_a_non_qualifying_provider_contributes_nothing_to_the_proof_record(
    tmp_path: pathlib.Path,
) -> None:
    paths = _module("_lpm_paths")
    state_dir = _state(tmp_path=tmp_path)
    assignment = _assignment_object(status="committed", committed_at="2026-10-02T11:00:05Z")
    request = assignment["request"]
    assert isinstance(request, dict)
    request["provider"] = "openai"
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=assignment,
    )

    settled = _run_effect(
        state_dir=state_dir,
        effect="proof-update",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(settled, Success), settled
    assert settled.unwrap() == "satisfied"
    assert not (state_dir / paths.PROOF_RECORD_NAME).exists()


def test_a_spread_commit_records_its_assignment_time_and_leaves_incumbents_alone(
    tmp_path: pathlib.Path,
) -> None:
    paths = _module("_lpm_paths")
    state_dir = _state(tmp_path=tmp_path)
    assignment = _assignment_object(status="committed", committed_at="2026-10-02T11:00:05Z")
    request = assignment["request"]
    assert isinstance(request, dict)
    request["strategy"] = "spread"
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=assignment,
    )

    merged = _run_effect(
        state_dir=state_dir,
        effect="selection-update",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(merged, Success), merged
    stored = _module("_lpm_localstate").read_local_record(
        path=state_dir / paths.SELECTION_STATE_NAME, owner_uid=os.getuid()
    )
    assert isinstance(stored, Success)
    assert stored.unwrap() == {
        "version": 1,
        "incumbents": [],
        "last_assignments": [{"record_id": _RECORD_ID, "assigned_at": "2026-10-02T11:00:05Z"}],
    }


def test_a_newer_stored_incumbent_is_never_regressed_by_a_late_recovery(
    tmp_path: pathlib.Path,
) -> None:
    paths = _module("_lpm_paths")
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(status="committed", committed_at="2026-10-02T11:00:05Z"),
    )
    selection = state_dir / paths.SELECTION_STATE_NAME
    _seed(
        path=selection,
        value={
            "version": 1,
            "incumbents": [
                {
                    "provider": "anthropic",
                    "kind": "claude-code-oauth",
                    "purpose": "factory",
                    "record_id": "9f8c7b6a-5d4e-4f3a-8b2c-1d0e9f8a7b6c",
                    "target_committed_at": "2026-10-02T23:00:00Z",
                }
            ],
            "last_assignments": [{"record_id": _RECORD_ID, "assigned_at": "2026-10-02T22:00:00Z"}],
        },
    )
    untouched = selection.read_bytes()

    merged = _run_effect(
        state_dir=state_dir,
        effect="selection-update",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(merged, Success), merged
    assert merged.unwrap() == "satisfied"
    assert selection.read_bytes() == untouched


def test_a_lease_release_with_neither_assignment_nor_selection_reports_a_bug(
    tmp_path: pathlib.Path,
) -> None:
    refused = _run_effect(
        state_dir=_state(tmp_path=tmp_path),
        effect="lease-release",
        normalized_input={"consumer_run_id": _RUN_ID, "provider": "anthropic"},
        command="expire",
        phase="close",
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "internal-bug"
    assert "provision inputs" in refused.failure().message


def test_a_lease_release_with_no_matching_live_lease_is_a_completed_no_op(
    tmp_path: pathlib.Path,
) -> None:
    settled = _run_effect(
        state_dir=_state(tmp_path=tmp_path),
        effect="lease-release",
        normalized_input={"consumer_run_id": _RUN_ID, "provider": "anthropic"},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(settled, Success), settled
    assert settled.unwrap() == "satisfied"


def test_another_runs_lease_is_left_standing_by_a_release(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    lease_path = _family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    _seed(path=lease_path, value=_lease_object(run_id="run-somebody-else"))
    untouched = lease_path.read_bytes()

    settled = _run_effect(
        state_dir=state_dir,
        effect="lease-release",
        normalized_input={"consumer_run_id": _RUN_ID, "provider": "anthropic"},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(settled, Success), settled
    assert settled.unwrap() == "satisfied"
    assert lease_path.read_bytes() == untouched


def test_an_unreadable_lease_file_refuses_a_release(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    lease_path = _family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    _seed(path=lease_path, value=_lease_object())
    lease_path.chmod(0o644)
    untouched = lease_path.read_bytes()

    refused = _run_effect(
        state_dir=state_dir,
        effect="lease-release",
        normalized_input={"consumer_run_id": _RUN_ID, "provider": "anthropic"},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert lease_path.read_bytes() == untouched


def test_the_registry_reports_every_effect_it_can_perform(tmp_path: pathlib.Path) -> None:
    registry = _module("_lpm_effect_registry")
    plan = _module("_lpm_operation_plan")
    _ = tmp_path

    registered = registry.registered_effects()

    assert registered == tuple(sorted(registry.EFFECT_EXECUTORS))
    for command, phase in (
        ("target", "issue"),
        ("provision", "start"),
        ("provision", "postcommit"),
        ("provision", "cleanup"),
    ):
        for array in plan.admissible_effect_arrays(command=command, phase=phase):
            for effect in array:
                assert effect in registered, (command, phase, effect)


def test_a_create_whose_family_directory_is_a_symlink_refuses_rather_than_following_it(
    tmp_path: pathlib.Path,
) -> None:
    # Absence is still the READ's answer here — the dangling parent makes the record's own
    # stat report ENOENT — so this reaches the WRITE and proves the atomic replacement
    # refuses to follow a redirected family directory instead of advancing the position.
    state_dir = _state(tmp_path=tmp_path)
    (state_dir / "leases").symlink_to(tmp_path / "nowhere")

    refused = _run_effect(
        state_dir=state_dir,
        effect="lease-create",
        normalized_input={
            "provider": "anthropic",
            "lease_seconds": 3600,
            "consumer_run_id": _RUN_ID,
        },
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "is a symlink" in refused.failure().message


def test_a_discard_with_no_assignment_at_all_is_a_completed_no_op(
    tmp_path: pathlib.Path,
) -> None:
    settled = _run_effect(
        state_dir=_state(tmp_path=tmp_path),
        effect="prepared-assignment-discard",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(settled, Success), settled
    assert settled.unwrap() == "satisfied"


def test_a_release_reads_its_binding_from_the_standing_assignment(
    tmp_path: pathlib.Path,
) -> None:
    # A closing phase runs `lease-release` BEFORE `assignment-close`, and `report`, `complete`,
    # `release` and `expire` inputs carry no provider — so the stored assignment's own request
    # and binding are the only authoritative source for the three values the release compares.
    state_dir = _state(tmp_path=tmp_path)
    lease_path = _family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    _seed(path=lease_path, value=_lease_object())
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(status="committed", committed_at="2026-10-02T11:00:05Z"),
    )

    released = _run_effect(
        state_dir=state_dir,
        effect="lease-release",
        normalized_input={"consumer_run_id": _RUN_ID, "record_id": _RECORD_ID},
        command="release",
        phase="apply",
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )

    assert isinstance(released, Success), released
    assert released.unwrap() == "performed"
    assert not lease_path.exists()


def test_an_unreadable_target_commit_record_refuses_a_target_write(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(),
    )
    commit_path = _family_path(state_dir=state_dir, family="target-commit", identity=(_TARGET_REF,))
    _seed(path=commit_path, value={"version": 1})
    commit_path.chmod(0o644)

    refused = _run_effect(
        state_dir=state_dir,
        effect="target-write",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert not pathlib.Path(str(tmp_path / "target" / "credential")).exists()


def test_an_already_committed_target_write_settles_without_writing_again(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(),
    )
    _seed(
        path=_family_path(state_dir=state_dir, family="target-commit", identity=(_TARGET_REF,)),
        value={
            "version": 1,
            "target_ref": _TARGET_REF,
            "consumer_run_id": _RUN_ID,
            "record_id": _RECORD_ID,
            "value_generation": _GENERATION,
            "committed_at": "2026-10-02T11:00:05Z",
        },
    )

    settled = _run_effect(
        state_dir=state_dir,
        effect="target-write",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(settled, Success), settled
    assert settled.unwrap() == "satisfied"
    assert not pathlib.Path(str(tmp_path / "target" / "credential")).exists()


def test_an_assignment_commit_over_a_malformed_assignment_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="target-commit", identity=(_TARGET_REF,)),
        value={
            "version": 1,
            "target_ref": _TARGET_REF,
            "consumer_run_id": _RUN_ID,
            "record_id": _RECORD_ID,
            "value_generation": _GENERATION,
            "committed_at": "2026-10-02T11:00:05Z",
        },
    )
    assignment_path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    _seed(path=assignment_path, value={"version": 1, "status": "prepared"})
    untouched = assignment_path.read_bytes()

    refused = _run_effect(
        state_dir=state_dir,
        effect="assignment-commit",
        normalized_input={"target_ref": _TARGET_REF},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert assignment_path.read_bytes() == untouched


def test_a_merge_retains_a_concurrent_incumbent_for_another_row(
    tmp_path: pathlib.Path,
) -> None:
    paths = _module("_lpm_paths")
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(status="committed", committed_at="2026-10-02T11:00:05Z"),
    )
    peer = {
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "interactive",
        "record_id": "9f8c7b6a-5d4e-4f3a-8b2c-1d0e9f8a7b6c",
        "target_committed_at": "2026-10-02T10:00:00Z",
    }
    _seed(
        path=state_dir / paths.SELECTION_STATE_NAME,
        value={"version": 1, "incumbents": [peer], "last_assignments": []},
    )

    merged = _run_effect(
        state_dir=state_dir,
        effect="selection-update",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(merged, Success), merged
    stored = _module("_lpm_localstate").read_local_record(
        path=state_dir / paths.SELECTION_STATE_NAME, owner_uid=os.getuid()
    )
    assert isinstance(stored, Success)
    state = stored.unwrap()
    assert isinstance(state, dict)
    assert peer in state["incumbents"]
    assert len(state["incumbents"]) == 2


def test_a_merge_whose_state_directory_is_a_symlink_refuses_the_replacement(
    tmp_path: pathlib.Path,
) -> None:
    # Reads resolve THROUGH the link, so the merge is computed and only the atomic
    # replacement refuses — which is the one path that proves the write failure is reported
    # rather than swallowed into a `performed` the record never received.
    real = tmp_path / "real-state"
    real.mkdir(mode=0o700)
    _seed(
        path=_family_path(state_dir=real, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(status="committed", committed_at="2026-10-02T11:00:05Z"),
    )
    linked = tmp_path / "linked-state"
    linked.symlink_to(real)

    refused = _run_effect(
        state_dir=linked,
        effect="selection-update",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "is a symlink" in refused.failure().message


@pytest.mark.parametrize("effect", ["issuance-create", "registration-remove"])
def test_a_target_issue_effect_names_the_run_it_was_not_given(
    tmp_path: pathlib.Path, effect: str
) -> None:
    context_module = _module("_lpm_engine_context")
    inputs = context_module.EffectInputs(
        target=context_module.TargetInputs(
            reference=_TARGET_REF, adapter="isolated-run", destination=str(tmp_path / "dest")
        )
    )

    refused = _run_effect(
        state_dir=_state(tmp_path=tmp_path),
        effect=effect,
        normalized_input={},
        inputs=inputs,
        command="target",
        phase="issue",
    )

    assert isinstance(refused, Failure), effect
    assert refused.failure().error_type == "internal-bug"
    assert "carries no consumer_run_id" in refused.failure().message


def test_resuming_through_an_unreadable_operation_record_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    record = _family_path(state_dir=state_dir, family="operation", identity=("provision", _KEY))
    _seed(path=record, value={"version": 1})
    record.chmod(0o644)

    resumed = _module("_lpm_engine").resume_phase(
        engine=_engine(state_dir=state_dir),
        command="provision",
        idempotency_key=_KEY,
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )

    assert isinstance(resumed, Failure)
    assert resumed.failure().error_type == "store-unavailable"


def test_a_refusing_phase_never_reaches_its_transition(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    operation = _operation(
        command="provision",
        phase="cleanup",
        effect="lease-release",
        normalized_input={
            "version": 1,
            "provider": "anthropic",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "consumer_run_id": _RUN_ID,
            "target_ref": _TARGET_REF,
            "strategy": "consume-first",
            "lease_seconds": 3600,
        },
    )
    store_module = _module("_lpm_operation_store")
    located = store_module.operation_path(
        state_dir=state_dir, command="provision", idempotency_key=_KEY
    )
    assert isinstance(located, Success)
    written = store_module.write_operation(
        path=located.unwrap(), operation=operation, owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written

    driven = _module("_lpm_engine").drive_operation(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_module("_lpm_engine_context").EffectInputs(),
        condition="every-effect-committed",
        context=_module("_lpm_operation_plan").PlanContext(),
        terminal_result=None,
    )

    assert isinstance(driven, Failure)
    assert driven.failure().error_type == "internal-bug"
    stored = store_module.read_operation(path=located.unwrap(), owner_uid=os.getuid())
    assert isinstance(stored, Success)
    standing = stored.unwrap()
    assert standing is not None
    assert standing.completed_step == -1


def test_an_older_incumbent_for_the_same_row_is_replaced(tmp_path: pathlib.Path) -> None:
    paths = _module("_lpm_paths")
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment_object(status="committed", committed_at="2026-10-02T11:00:05Z"),
    )
    _seed(
        path=state_dir / paths.SELECTION_STATE_NAME,
        value={
            "version": 1,
            "incumbents": [
                {
                    "provider": "anthropic",
                    "kind": "claude-code-oauth",
                    "purpose": "factory",
                    "record_id": "9f8c7b6a-5d4e-4f3a-8b2c-1d0e9f8a7b6c",
                    "target_committed_at": "2026-10-01T09:00:00Z",
                }
            ],
            "last_assignments": [],
        },
    )

    merged = _run_effect(
        state_dir=state_dir,
        effect="selection-update",
        normalized_input={"consumer_run_id": _RUN_ID},
        inputs=_provision_inputs(tmp_path=tmp_path),
    )

    assert isinstance(merged, Success), merged
    assert merged.unwrap() == "performed"
    stored = _module("_lpm_localstate").read_local_record(
        path=state_dir / paths.SELECTION_STATE_NAME, owner_uid=os.getuid()
    )
    assert isinstance(stored, Success)
    state = stored.unwrap()
    assert isinstance(state, dict)
    assert state["incumbents"] == [
        {
            "provider": "anthropic",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "record_id": _RECORD_ID,
            "target_committed_at": "2026-10-02T11:00:05Z",
        }
    ]
