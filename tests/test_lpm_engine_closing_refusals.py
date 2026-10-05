"""Every refusal a closing effect owes, driven one position at a time.

SPECIFICATION/contracts.md gives these effects one shared no-reset rule: "any malformed,
non-regular, symlinked, incorrectly owned or more-broadly-accessible manager-local file MUST
return `store-unavailable` with exit `4` WITHOUT reset or mutation", and "any other state MUST
follow an explicitly defined conditional no-op or refusal, otherwise return `store-unavailable`
without overwriting it". The closing phases add two of their own: a tombstone must commit BEFORE
the assignment is removed, and a fenced conditional set advances only on an authoritative desired
revision.

EACH POSITION IS DRIVEN THROUGH `drive_phase`, NOT CALLED DIRECTLY. The effect table is the only
path an executor is reached by in production, so a refusal asserted through a direct call proves
nothing about whether the engine would actually surface it. A one-element phase is the smallest
composition that still goes through the real executor lookup, the real positional identity and
the real replay driver.

TWO HAZARDS CANNOT BE PRODUCED WITHOUT A DELEGATING DOUBLE, AND BOTH ARE REAL. A transport that
loses its answer after the backend already accepted the append is the whole reason a fence
exists; and an envelope whose `item_id` names no revision of its own record is something the
hermetic in-memory backend cannot emit but a replaceable backend can. Both doubles DELEGATE to
the real store for everything else, so the append-only chain, the predecessor comparison and the
byte-identical collapse are all still the real protocol.

EVERY REFUSAL ASSERTION NAMES ITS MESSAGE, not only its error type. Several of these conditions
are `store-unavailable` or `internal-bug` for quite different reasons, and an assertion on the
type alone passes against an engine that refused for a reason nobody asked about — including the
"this effect is not registered" refusal, which is what these very positions answered before they
existed.
"""

from __future__ import annotations

import importlib
import os
import pathlib
from dataclasses import dataclass, field

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_OPERATION_ID = "4c8b6e21-9f3a-4d77-b1e5-8a0c2d4f6b93"
_KEY = "c" * 64
_ACCEPTED_AT = "2026-10-04T14:00:00Z"
_RUN_ID = "run-closing-refusal"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_OTHER_GENERATION = "16fd2706-8baf-433b-82eb-8c7fada847da"
_TARGET_REF = "ref-closing-4b17"
_ACCOUNT = "acct-primary"
_VALUE_REF = "op://llm-provider-manager-token-values/3f2504e0-gen/credential"
_LEASE_STARTED_AT = "2026-10-04T11:00:00Z"
_LEASE_EXPIRES_AT = "2026-10-04T13:00:00Z"
_COMMITTED_AT = "2026-10-04T11:00:05Z"
_NORMALIZED_CLOSE_AT = "2026-10-04T13:00:00Z"
_OCCURRED_AT = "2026-10-04T11:30:00Z"
_SEED_EFFECT_ID = "d" * 64
_OTHER_EFFECT_ID = "e" * 64

_LIVE_APPLY = (
    "audit-append",
    "credential-conditional-set",
    "proof-update",
    "report-marker-update",
    "assignment-end-update",
    "lease-release",
    "tombstone-create",
    "assignment-close",
)


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _provision_request() -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": _RUN_ID,
        "target_ref": _TARGET_REF,
        "strategy": "consume-first",
        "lease_seconds": 7200,
    }


def _report_input(**changes: object) -> dict[str, object]:
    source: dict[str, object] = {
        "version": 1,
        "consumer_run_id": _RUN_ID,
        "record_id": _RECORD_ID,
        "occurred_at": _OCCURRED_AT,
        "classification": "authentication",
    }
    source.update(changes)
    return source


def _credential(**changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "version": 1,
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": _ACCOUNT,
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-10-04T10:00:00Z",
        "expires_at": None,
        "last_validated": "2026-10-04T10:30:00Z",
        "value_generation": _GENERATION,
        "value_ref": _VALUE_REF,
        "previous_value_ref": None,
    }
    record.update(changes)
    return record


def _assignment(**changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "version": 1,
        "status": "committed",
        "request": _provision_request(),
        "target_ref": _TARGET_REF,
        "account_id": _ACCOUNT,
        "value_generation": _GENERATION,
        "value_ref": _VALUE_REF,
        "record_id": _RECORD_ID,
        "receipt": {
            "record_id": _RECORD_ID,
            "account_id": _ACCOUNT,
            "purpose": "factory",
            "validated_at": "2026-10-04T10:30:00Z",
            "lease_expires_at": _LEASE_EXPIRES_AT,
        },
        "lease_started_at": _LEASE_STARTED_AT,
        "lease_expires_at": _LEASE_EXPIRES_AT,
        "target_committed_at": _COMMITTED_AT,
        "actual_lease_ended_at": None,
        "report_markers": [],
        "completion": None,
    }
    record.update(changes)
    return record


def _prepared_assignment() -> dict[str, object]:
    return _assignment(
        status="prepared",
        target_committed_at=None,
        actual_lease_ended_at=None,
        report_markers=[],
        completion=None,
    )


def _tombstone(**changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "version": 1,
        "request": _provision_request(),
        "target_ref": _TARGET_REF,
        "account_id": _ACCOUNT,
        "value_generation": _GENERATION,
        "value_ref": _VALUE_REF,
        "record_id": _RECORD_ID,
        "lease_started_at": _LEASE_STARTED_AT,
        "lease_expires_at": _LEASE_EXPIRES_AT,
        "target_committed_at": _COMMITTED_AT,
        "actual_lease_ended_at": _NORMALIZED_CLOSE_AT,
        "closed_at": _ACCEPTED_AT,
        "report_markers": [],
        "completion": None,
    }
    record.update(changes)
    return record


def _state(*, tmp_path: pathlib.Path) -> pathlib.Path:
    state_dir = tmp_path / "manager-state"
    state_dir.mkdir(mode=0o700)
    return state_dir


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


def _seed_text(*, path: pathlib.Path, text: str) -> None:
    written = _module("_lpm_localstate").write_local_text(
        path=path, text=text, owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written


def _canonical(*, value: object) -> str:
    encoded = _module("_lpm_canonical").canonical_json_text(value=value)
    assert isinstance(encoded, Success), encoded
    return encoded.unwrap()


def _store(*, record: dict[str, object] | None = None, available: bool = True):
    store_module = _module("_lpm_store")
    store = store_module.InMemorySecretStore(available=True)
    if record is not None:
        committed = store.credential_conditional_set(
            request=store_module.ConditionalSet(
                record_id=_RECORD_ID,
                effect_id=_SEED_EFFECT_ID,
                expected_record=None,
                desired_record=_canonical(value=record),
            )
        )
        assert committed["status"] == "committed", committed
    store.available = available
    return store


def _raw_chain_store(*, record_text: str):
    """A real backend whose stored revision text is seeded directly, bytes and all."""
    revisions = _module("_lpm_revisions")
    store = _module("_lpm_store").InMemorySecretStore()
    store.items[_RECORD_ID] = [
        revisions.RevisionItem(
            title=revisions.revision_title(
                record_id=_RECORD_ID, revision=1, effect_id=_SEED_EFFECT_ID
            ),
            predecessor_sha256=revisions.GENESIS_PREDECESSOR,
            record=record_text,
        )
    ]
    return store


@dataclass(kw_only=True)
class _ForgedEnvelope:
    """A store whose metadata read answers `ok` with an envelope it did not build.

    A replaceable backend's output crosses a process boundary, so an `ok` result carrying
    something other than a revision envelope of the requested record is a shape the hermetic
    backend cannot emit and a real one can. Everything else delegates.
    """

    inner: object
    item: object = None

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        _ = record_id
        return _module("_lpm_store").metadata_get_result(status="ok", payload=self.item)

    def metadata_list(self) -> dict[str, object]:
        return _module("_lpm_store").metadata_list_result(status="unavailable")

    def credential_conditional_set(self, *, request: object) -> dict[str, object]:
        _ = request
        return _module("_lpm_store").set_result(status="unavailable")


@dataclass(kw_only=True)
class _LostTransport:
    """A store that COMMITS nothing and reports `unavailable` for the conditional set.

    The outcome is UNKNOWN to the caller, which is exactly the hazard the pending-effect fence
    exists for and the one shape a hermetic test cannot otherwise produce.
    """

    inner: object

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        return self.inner.metadata_get(record_id=record_id)  # type: ignore[attr-defined]

    def metadata_list(self) -> dict[str, object]:
        return self.inner.metadata_list()  # type: ignore[attr-defined]

    def credential_conditional_set(self, *, request: object) -> dict[str, object]:
        _ = request
        return _module("_lpm_store").set_result(status="unavailable")


@dataclass(kw_only=True)
class _WideningFence:
    """A store that commits the revision and then widens the fence file's permissions.

    The fence removal that follows an authoritative commit sits in its own crash window, and the
    no-reset rule covers deletion too: a more-broadly-accessible path is evidence and is refused
    rather than unlinked. Nothing else can make that removal fail mid-effect.
    """

    inner: object
    fence_file: pathlib.Path
    widened: list[bool] = field(default_factory=list)

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        return self.inner.metadata_get(record_id=record_id)  # type: ignore[attr-defined]

    def metadata_list(self) -> dict[str, object]:
        return self.inner.metadata_list()  # type: ignore[attr-defined]

    def credential_conditional_set(self, *, request: object) -> dict[str, object]:
        committed = self.inner.credential_conditional_set(request=request)  # type: ignore[attr-defined]
        if not self.widened:
            self.fence_file.chmod(0o644)
            self.widened.append(True)
        return committed


def _operation(
    *,
    effects: tuple[str, ...],
    command: str = "report",
    phase: str = "apply",
    normalized_input: dict[str, object] | None = None,
    completed_step: int = -1,
):
    return _module("_lpm_operation").OperationRecord(
        operation_id=_OPERATION_ID,
        command=command,
        phase=phase,
        idempotency_key=_KEY,
        accepted_at=_ACCEPTED_AT,
        normalized_input=_report_input() if normalized_input is None else normalized_input,
        terminal_result=None,
        ordered_effects=effects,
        completed_step=completed_step,
    )


def _driven(
    *,
    state_dir: pathlib.Path,
    effects: tuple[str, ...],
    store: object | None = None,
    command: str = "report",
    normalized_input: dict[str, object] | None = None,
    completed_step: int = -1,
):
    context_module = _module("_lpm_engine_context")
    return _module("_lpm_engine").drive_phase(
        engine=context_module.OperationEngine(
            state_dir=state_dir,
            owner_uid=os.getuid(),
            store=_store() if store is None else store,  # type: ignore[arg-type]
        ),
        operation=_operation(
            effects=effects,
            command=command,
            normalized_input=normalized_input,
            completed_step=completed_step,
        ),
        inputs=context_module.EffectInputs(),
    )


def _refused(driven) -> object:
    assert isinstance(driven, Failure), driven
    return driven.failure()


def test_a_closing_effect_with_no_binding_record_at_all_refuses(
    tmp_path: pathlib.Path,
) -> None:
    failure = _refused(
        _driven(state_dir=_state(tmp_path=tmp_path), effects=("assignment-end-update",))
    )

    assert failure.error_type == "store-unavailable"
    assert "no live assignment or tombstone stands" in failure.message


def test_a_closing_effect_whose_operation_carries_no_run_identity_is_an_internal_bug(
    tmp_path: pathlib.Path,
) -> None:
    failure = _refused(
        _driven(
            state_dir=_state(tmp_path=tmp_path),
            effects=("assignment-end-update",),
            normalized_input={},
        )
    )

    assert failure.error_type == "internal-bug"
    assert "carries no consumer_run_id" in failure.message


def test_an_unreadable_tombstone_file_refuses_every_closing_effect(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    _seed_text(path=path, text="not json at all")
    untouched = path.read_bytes()

    failure = _refused(_driven(state_dir=state_dir, effects=("assignment-end-update",)))

    assert failure.error_type == "store-unavailable"
    assert "malformed JSON" in failure.message
    assert path.read_bytes() == untouched


def test_a_malformed_tombstone_object_refuses_without_rewriting_it(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    broken = _tombstone()
    del broken["closed_at"]
    _seed(path=path, value=broken)
    untouched = path.read_bytes()

    failure = _refused(_driven(state_dir=state_dir, effects=("assignment-end-update",)))

    assert failure.error_type == "store-unavailable"
    assert "a tombstone is missing closed_at" in failure.message
    assert path.read_bytes() == untouched


def test_a_malformed_assignment_object_refuses_without_rewriting_it(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    broken = _assignment()
    del broken["receipt"]
    _seed(path=path, value=broken)
    untouched = path.read_bytes()

    failure = _refused(_driven(state_dir=state_dir, effects=("assignment-end-update",)))

    assert failure.error_type == "store-unavailable"
    assert "an assignment is missing receipt" in failure.message
    assert path.read_bytes() == untouched


def test_a_prepared_assignment_is_never_closed_or_reported_on(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    _seed(path=path, value=_prepared_assignment())
    untouched = path.read_bytes()

    failure = _refused(_driven(state_dir=state_dir, effects=("assignment-end-update",)))

    assert failure.error_type == "store-unavailable"
    assert "only a committed assignment may be closed" in failure.message
    assert path.read_bytes() == untouched


def test_a_close_time_outside_its_own_lease_window_refuses_rather_than_persisting(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    _seed(path=path, value=_assignment(target_committed_at="2026-10-04T23:00:00Z"))
    untouched = path.read_bytes()

    failure = _refused(_driven(state_dir=state_dir, effects=("assignment-end-update",)))

    assert failure.error_type == "store-unavailable"
    assert "no later than lease_expires_at" in failure.message
    assert path.read_bytes() == untouched


def test_a_non_closing_command_cannot_compute_an_assignment_end(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("assignment-end-update",),
            command="provision",
            normalized_input=_provision_request(),
        )
    )

    assert failure.error_type == "internal-bug"
    assert "provision does not close an assignment" in failure.message


def test_a_marker_update_with_no_binding_record_refuses(tmp_path: pathlib.Path) -> None:
    failure = _refused(
        _driven(state_dir=_state(tmp_path=tmp_path), effects=("report-marker-update",))
    )

    assert failure.error_type == "store-unavailable"
    assert "no live assignment or tombstone stands" in failure.message


def test_a_marker_update_whose_operation_carries_no_report_fields_is_an_internal_bug(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    missing_time = _refused(
        _driven(
            state_dir=state_dir,
            effects=("report-marker-update",),
            normalized_input={"consumer_run_id": _RUN_ID},
        )
    )
    missing_classification = _refused(
        _driven(
            state_dir=state_dir,
            effects=("report-marker-update",),
            normalized_input={"consumer_run_id": _RUN_ID, "occurred_at": _OCCURRED_AT},
        )
    )

    assert missing_time.error_type == "internal-bug"
    assert "carries no occurred_at" in missing_time.message
    assert missing_classification.error_type == "internal-bug"
    assert "carries no classification" in missing_classification.message


def test_an_audit_append_that_attests_nothing_is_an_internal_bug(
    tmp_path: pathlib.Path,
) -> None:
    failure = _refused(_driven(state_dir=_state(tmp_path=tmp_path), effects=("audit-append",)))

    assert failure.error_type == "internal-bug"
    assert "immediately before the effect it attests" in failure.message


def test_an_audit_append_in_a_phase_that_audits_nothing_is_an_internal_bug(
    tmp_path: pathlib.Path,
) -> None:
    failure = _refused(
        _driven(
            state_dir=_state(tmp_path=tmp_path),
            effects=("audit-append", "credential-conditional-set"),
            command="complete",
        )
    )

    assert failure.error_type == "internal-bug"
    assert "complete apply audits no credential effect" in failure.message


def test_an_audit_append_whose_transition_cannot_be_decided_refuses(
    tmp_path: pathlib.Path,
) -> None:
    failure = _refused(
        _driven(
            state_dir=_state(tmp_path=tmp_path),
            effects=("audit-append", "credential-conditional-set"),
        )
    )

    assert failure.error_type == "store-unavailable"
    assert "no live assignment or tombstone stands" in failure.message


def test_an_audit_log_already_recording_this_effect_differently_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    derived = _module("_lpm_operation_identity").effect_id(
        operation=_operation(effects=("audit-append", "credential-conditional-set")), index=0
    )
    assert isinstance(derived, Success), derived
    audit_path = state_dir / _module("_lpm_paths").AUDIT_LOG_NAME
    _seed_text(
        path=audit_path,
        text=_canonical(
            value={
                "version": 1,
                "record_id": _RECORD_ID,
                "effect_id": derived.unwrap(),
                "actor": "recovery-writer",
                "operation": "credential-conditional-set",
                "attempted_at": _ACCEPTED_AT,
            }
        )
        + "\n",
    )
    untouched = audit_path.read_bytes()

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("audit-append", "credential-conditional-set"),
            store=_store(record=_credential()),
        )
    )

    assert failure.error_type == "store-unavailable"
    assert "records this effect_id differently" in failure.message
    assert audit_path.read_bytes() == untouched


def test_a_conditional_set_whose_transition_cannot_be_decided_refuses(
    tmp_path: pathlib.Path,
) -> None:
    failure = _refused(
        _driven(state_dir=_state(tmp_path=tmp_path), effects=("credential-conditional-set",))
    )

    assert failure.error_type == "store-unavailable"
    assert "no live assignment or tombstone stands" in failure.message


def test_a_conditional_set_whose_operation_carries_no_record_identity_is_an_internal_bug(
    tmp_path: pathlib.Path,
) -> None:
    failure = _refused(
        _driven(
            state_dir=_state(tmp_path=tmp_path),
            effects=("credential-conditional-set",),
            normalized_input={"consumer_run_id": _RUN_ID},
        )
    )

    assert failure.error_type == "internal-bug"
    assert "carries no record_id" in failure.message


def test_a_conditional_set_in_a_phase_that_audits_nothing_is_an_internal_bug(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            command="release",
            store=_store(record=_credential()),
        )
    )

    assert failure.error_type == "internal-bug"
    assert "release apply audits no credential effect" in failure.message


def test_a_different_pending_fence_on_the_same_record_refuses_and_is_left_alone(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    foreign = _module("_lpm_fence").fence_for_effect(
        effect_id=_OTHER_EFFECT_ID,
        writer_role="recovery-writer",
        revision=2,
        expected_record=_credential(),
        desired_record=_credential(status="dead", last_validated=None),
        owner_operation_id=_OPERATION_ID,
    )
    assert isinstance(foreign, Success), foreign
    fence_file = _family_path(
        state_dir=state_dir, family="pending-metadata-effect", identity=(_RECORD_ID,)
    )
    _seed(path=fence_file, value=_module("_lpm_fence").fence_object(fence=foreign.unwrap()))
    untouched = fence_file.read_bytes()

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            store=_store(record=_credential()),
        )
    )

    assert failure.error_type == "store-unavailable"
    assert "a different pending metadata-effect fence" in failure.message
    assert fence_file.read_bytes() == untouched


def test_an_unknown_conditional_write_retains_its_fence_and_fails_closed(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    store = _store(record=_credential())

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            store=_LostTransport(inner=store),
        )
    )

    assert failure.error_type == "store-unavailable"
    assert "resolved to store-unavailable" in failure.message
    assert _family_path(
        state_dir=state_dir, family="pending-metadata-effect", identity=(_RECORD_ID,)
    ).exists()
    assert len(store.items[_RECORD_ID]) == 1


def test_a_fence_that_cannot_be_removed_after_its_commit_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    fence_file = _family_path(
        state_dir=state_dir, family="pending-metadata-effect", identity=(_RECORD_ID,)
    )

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            store=_WideningFence(inner=_store(record=_credential()), fence_file=fence_file),
        )
    )

    assert failure.error_type == "store-unavailable"
    assert "more broadly accessible" in failure.message
    assert fence_file.exists()


def test_an_unreadable_credential_chain_refuses_the_transition(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            store=_store(record=_credential(), available=False),
        )
    )

    assert failure.error_type == "store-unavailable"
    assert "authoritative revision chain is unreadable" in failure.message


def test_an_absent_credential_record_refuses_the_transition(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    failure = _refused(
        _driven(state_dir=state_dir, effects=("credential-conditional-set",), store=_store())
    )

    assert failure.error_type == "store-unavailable"
    assert "no authoritative credential record stands" in failure.message


def test_an_envelope_naming_no_revision_of_its_record_refuses(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            store=_ForgedEnvelope(inner=_store(), item=42),
        )
    )

    assert failure.error_type == "store-unavailable"
    assert "names no revision of this record" in failure.message


def test_a_revision_whose_stored_text_is_not_canonical_json_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            store=_raw_chain_store(record_text="{not json"),
        )
    )

    assert failure.error_type == "store-unavailable"
    assert "the authoritative record is malformed JSON" in failure.message


def test_a_revision_holding_an_invalid_credential_record_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    broken = _credential()
    del broken["purpose"]

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            store=_raw_chain_store(record_text=_canonical(value=broken)),
        )
    )

    assert failure.error_type == "store-unavailable"
    assert "the authoritative record is invalid" in failure.message


def test_a_report_whose_stored_input_is_not_a_report_refuses(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            normalized_input=_report_input(classification="not-a-classification"),
        )
    )

    assert failure.error_type == "invalid-report"
    assert "classification must be one of" in failure.message


def test_a_report_against_an_acquiring_credential_is_refused(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("credential-conditional-set",),
            store=_store(
                record=_credential(
                    status="acquiring",
                    value_generation=None,
                    value_ref=None,
                    last_validated=None,
                )
            ),
        )
    )

    assert failure.error_type == "invalid-report"
    assert "could not have been provisioned" in failure.message


def test_a_lease_release_whose_retained_tombstone_is_unreadable_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    _seed_text(path=path, text="not json at all")

    failure = _refused(_driven(state_dir=state_dir, effects=("lease-release",)))

    assert failure.error_type == "store-unavailable"
    assert "malformed JSON" in failure.message


def test_a_lease_release_whose_retained_tombstone_is_malformed_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    broken = _tombstone()
    del broken["account_id"]
    _seed(
        path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)),
        value=broken,
    )

    failure = _refused(_driven(state_dir=state_dir, effects=("lease-release",)))

    assert failure.error_type == "store-unavailable"
    assert "a tombstone is missing account_id" in failure.message


def test_a_tombstone_create_with_no_binding_record_refuses(tmp_path: pathlib.Path) -> None:
    failure = _refused(_driven(state_dir=_state(tmp_path=tmp_path), effects=("tombstone-create",)))

    assert failure.error_type == "store-unavailable"
    assert "no live assignment or tombstone stands" in failure.message


def test_a_tombstone_create_over_an_unreadable_assignment_file_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)),
        value=_tombstone(),
    )
    _seed_text(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        text="not json at all",
    )

    failure = _refused(_driven(state_dir=state_dir, effects=("tombstone-create",)))

    assert failure.error_type == "store-unavailable"
    assert "malformed JSON" in failure.message


def test_a_tombstone_create_over_a_malformed_assignment_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)),
        value=_tombstone(),
    )
    broken = _assignment()
    del broken["value_ref"]
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=broken,
    )

    failure = _refused(_driven(state_dir=state_dir, effects=("tombstone-create",)))

    assert failure.error_type == "store-unavailable"
    assert "an assignment is missing value_ref" in failure.message


def test_a_non_closing_command_cannot_derive_a_tombstone(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )

    failure = _refused(
        _driven(
            state_dir=state_dir,
            effects=("tombstone-create",),
            command="provision",
            normalized_input=_provision_request(),
        )
    )

    assert failure.error_type == "internal-bug"
    assert "provision does not close an assignment" in failure.message


def test_only_a_committed_assignment_may_become_a_tombstone(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)),
        value=_tombstone(),
    )
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_prepared_assignment(),
    )

    failure = _refused(_driven(state_dir=state_dir, effects=("tombstone-create",)))

    assert failure.error_type == "store-unavailable"
    assert "only a committed assignment may become a tombstone" in failure.message


def test_a_different_tombstone_already_closing_this_run_refuses(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    tombstone_path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    _seed(path=tombstone_path, value=_tombstone(closed_at="2026-10-04T12:30:00Z"))
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    untouched = tombstone_path.read_bytes()

    failure = _refused(_driven(state_dir=state_dir, effects=("tombstone-create",)))

    assert failure.error_type == "store-unavailable"
    assert "a different tombstone already closes this run" in failure.message
    assert tombstone_path.read_bytes() == untouched


def test_a_byte_identical_tombstone_settles_the_creation_without_rewriting_it(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    first = _driven(state_dir=state_dir, effects=_LIVE_APPLY, completed_step=5)
    assert isinstance(first, Success), first
    assert first.unwrap().performed == (6, 7)
    tombstone_path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    written = tombstone_path.read_bytes()
    assignment_path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    _seed(path=assignment_path, value=_assignment())

    replay = _driven(state_dir=state_dir, effects=_LIVE_APPLY, completed_step=5)

    assert isinstance(replay, Success), replay
    assert replay.unwrap().skipped == (6,)
    assert replay.unwrap().performed == (7,)
    assert tombstone_path.read_bytes() == written
    assert not assignment_path.exists()


def test_an_assignment_close_with_no_binding_record_refuses(tmp_path: pathlib.Path) -> None:
    failure = _refused(_driven(state_dir=_state(tmp_path=tmp_path), effects=("assignment-close",)))

    assert failure.error_type == "store-unavailable"
    assert "no live assignment or tombstone stands" in failure.message


def test_an_assignment_is_never_removed_before_its_tombstone_commits(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    _seed(path=path, value=_assignment())
    untouched = path.read_bytes()

    failure = _refused(_driven(state_dir=state_dir, effects=("assignment-close",)))

    assert failure.error_type == "store-unavailable"
    assert "the tombstone must commit before" in failure.message
    assert path.read_bytes() == untouched


def test_a_replaced_generation_makes_the_audited_pair_a_completed_no_op(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(value_generation=_OTHER_GENERATION),
    )
    store = _store(record=_credential())

    settled = _driven(state_dir=state_dir, effects=_LIVE_APPLY, store=store)

    assert isinstance(settled, Success), settled
    assert settled.unwrap().skipped == (0, 1, 2, 5)
    assert settled.unwrap().performed == (3, 4, 6, 7)
    assert len(store.items[_RECORD_ID]) == 1
    assert not (state_dir / _module("_lpm_paths").AUDIT_LOG_NAME).exists()
    assert not _family_path(
        state_dir=state_dir, family="pending-metadata-effect", identity=(_RECORD_ID,)
    ).exists()
