"""A report's conditional metadata write is decided by a reread, never by an acknowledgement.

SPECIFICATION/contracts.md: "A deadline, interruption, unavailable transport or malformed adapter
result MUST make its physical-create outcome unknown... After an unknown result, the exact
expected predecessor or expected absence proves only that no desired revision was visible by that
reread; the manager MUST retain the effect and every owning operation or worker safety fence as
the record's pending-effect fence and return `store-unavailable`, and a retry MAY issue only the
byte-identical revision title and fields. An exact desired next revision carrying that effect_id
proves the logical effect committed and MUST advance it without another adapter call." A fence's
"writer role MUST equal the semantic audit actor assigned to that owning operation, phase and
effect by the actor table" — `report-writer` here.

THE RETAINED FENCE IS ASSERTED AS A WHOLE RECORD, not merely as a file that exists. Its writer
role, revision, derived title, predecessor digest and both complete records are what a LATER
process reconstructs the byte-identical retry from; a fence that existed but named anything else
would authorize a revision nobody asked for. So the exercise reads it back and compares it to the
fence the contract's own builder derives for that position.

THE ADVANCE-WITHOUT-ANOTHER-CALL CASE IS DRIVEN AGAINST A BACKEND THAT WOULD STILL ANSWER
`unavailable`. The desired revision is committed out of band — through the retained fence's OWN
authorized request, which is the only thing a retry is permitted to issue — and the retry then
makes NO adapter call at all, because the reread can already see the revision. The double counts
its calls so the absence is asserted rather than assumed, and the chain still holds exactly two
revisions. An engine that advanced on acknowledgements would be indistinguishable from this one on
the happy path and would strand this record forever.

THE SAME STATE REACHED BY A DIFFERENT ROUTE IS WHAT MAKES THAT NECESSARY. Once the desired
`suspect` revision is authoritative, the report's own lifecycle reasoning reaches a completed
no-op — the record is already `suspect` — so a settled position that did not look at the fence
would leave it behind forever, guarding a record whose effect had in fact committed. A fence is
therefore reconciled on the settled path too, and a fence that is unreadable, belongs to another
operation, or whose desired revision is NOT authoritative keeps the position closed instead.

THE AUDIT LINE SURVIVES THE FAILURE, which is the append-only rule doing its job: the log attests
an attempt that really was made, and "a definitively-uncommitted mutation deliberately LEAVES its
entry behind". A retry recognizes that line by its effect identity and appends no second one, so
the count stays at one across every pass below.

A SECOND REPORT CANNOT STEP AROUND THE FENCE. While it remains, no other conditional set for that
record may create another revision — so a later operation's own position refuses rather than
appending a competing revision 2 that would outrank the one still in flight.
"""

from __future__ import annotations

import importlib
import os
import pathlib
from dataclasses import dataclass, field

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_OPERATION_ID = "5c1e8f44-2a76-4b03-9e58-d7a0b3c62f91"
_SECOND_OPERATION_ID = "e3b70d29-6c85-4f17-a042-9b5c1e8d7306"
_KEY = "6" * 64
_SECOND_KEY = "7" * 64
_ACCEPTED_AT = "2026-10-05T14:00:00Z"
_RUN_ID = "run-fenced-one"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_TARGET_REF = "ref-fenced-5d02"
_ACCOUNT = "acct-primary"
_VALUE_REF = "op://llm-provider-manager-token-values/3f2504e0-gen/credential"
_LEASE_STARTED_AT = "2026-10-05T11:00:00Z"
_LEASE_EXPIRES_AT = "2026-10-05T13:00:00Z"
_COMMITTED_AT = "2026-10-05T11:00:05Z"
_OCCURRED_AT = "2026-10-05T11:30:00Z"
_SECOND_OCCURRED_AT = "2026-10-05T11:45:00Z"
_SEED_EFFECT_ID = "8" * 64

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
        "acquired_at": "2026-10-05T10:00:00Z",
        "expires_at": None,
        "last_validated": "2026-10-05T10:30:00Z",
        "value_generation": _GENERATION,
        "value_ref": _VALUE_REF,
        "previous_value_ref": None,
    }
    record.update(changes)
    return record


def _assignment() -> dict[str, object]:
    return {
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
            "validated_at": "2026-10-05T10:30:00Z",
            "lease_expires_at": _LEASE_EXPIRES_AT,
        },
        "lease_started_at": _LEASE_STARTED_AT,
        "lease_expires_at": _LEASE_EXPIRES_AT,
        "target_committed_at": _COMMITTED_AT,
        "actual_lease_ended_at": None,
        "report_markers": [],
        "completion": None,
    }


@dataclass(kw_only=True)
class _LostTransport:
    """A backend whose conditional set changes nothing and says so unhelpfully.

    `unavailable` is the contract's UNKNOWN bucket: the caller cannot tell a write that never
    happened from one that did, which is precisely the state a pending-effect fence exists to make
    survivable. Everything else delegates, so the append-only chain and the predecessor comparison
    remain the real protocol.
    """

    inner: object
    calls: list[str] = field(default_factory=list)

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        return self.inner.metadata_get(record_id=record_id)  # type: ignore[attr-defined]

    def metadata_list(self) -> dict[str, object]:
        return self.inner.metadata_list()  # type: ignore[attr-defined]

    def credential_conditional_set(self, *, request: object) -> dict[str, object]:
        self.calls.append("set")
        return _module("_lpm_store").set_result(status="unavailable")


def _state(*, tmp_path: pathlib.Path) -> pathlib.Path:
    state_dir = tmp_path / "manager-state"
    state_dir.mkdir(mode=0o700, parents=True)
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


def _read(*, path: pathlib.Path):
    stored = _module("_lpm_localstate").read_local_record(path=path, owner_uid=os.getuid())
    assert isinstance(stored, Success), stored
    return stored.unwrap()


def _healthy_store():
    store_module = _module("_lpm_store")
    store = store_module.InMemorySecretStore()
    encoded = _module("_lpm_canonical").canonical_json_text(value=_credential())
    assert isinstance(encoded, Success), encoded
    committed = store.credential_conditional_set(
        request=store_module.ConditionalSet(
            record_id=_RECORD_ID,
            effect_id=_SEED_EFFECT_ID,
            expected_record=None,
            desired_record=encoded.unwrap(),
        )
    )
    assert committed["status"] == "committed", committed
    return store


def _operation(
    *, operation_id: str = _OPERATION_ID, key: str = _KEY, occurred_at: str = _OCCURRED_AT
):
    return _module("_lpm_operation").OperationRecord(
        operation_id=operation_id,
        command="report",
        phase="apply",
        idempotency_key=key,
        accepted_at=_ACCEPTED_AT,
        normalized_input=_report_input(occurred_at=occurred_at),
        terminal_result=None,
        ordered_effects=_LIVE_APPLY,
        completed_step=-1,
    )


def _driven(*, state_dir: pathlib.Path, store, operation):
    context_module = _module("_lpm_engine_context")
    return _module("_lpm_engine").drive_phase(
        engine=context_module.OperationEngine(
            state_dir=state_dir, owner_uid=os.getuid(), store=store
        ),
        operation=operation,
        inputs=context_module.EffectInputs(),
    )


def _fence_file(*, state_dir: pathlib.Path) -> pathlib.Path:
    return _family_path(
        state_dir=state_dir, family="pending-metadata-effect", identity=(_RECORD_ID,)
    )


def _expected_fence(*, operation) -> object:
    derived = _module("_lpm_operation_identity").effect_id(operation=operation, index=1)
    assert isinstance(derived, Success), derived
    fence = _module("_lpm_fence").fence_for_effect(
        effect_id=derived.unwrap(),
        writer_role="report-writer",
        revision=2,
        expected_record=_credential(),
        desired_record=_credential(status="suspect"),
        owner_operation_id=operation.operation_id,
    )
    assert isinstance(fence, Success), fence
    return _module("_lpm_fence").fence_object(fence=fence.unwrap())


def _audit_entries(*, state_dir: pathlib.Path) -> tuple[object, ...]:
    log = _module("_lpm_audit").read_audit_log(
        path=state_dir / _module("_lpm_paths").AUDIT_LOG_NAME, owner_uid=os.getuid()
    )
    assert isinstance(log, Success), log
    return log.unwrap()


def _commit_through_the_retained_fence(*, state_dir: pathlib.Path, store) -> None:
    """Append exactly the revision the retained fence authorizes, and nothing else."""
    held = _module("_lpm_fence_store").read_fence(
        path=_fence_file(state_dir=state_dir), owner_uid=os.getuid()
    )
    assert isinstance(held, Success), held
    fence = held.unwrap()
    assert fence is not None
    request = _module("_lpm_fence_reread").conditional_set_request(fence=fence)
    assert isinstance(request, Success), request
    committed = store.credential_conditional_set(request=request.unwrap())
    assert committed["status"] == "committed", committed


def _live(*, tmp_path: pathlib.Path) -> pathlib.Path:
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    return state_dir


def _suspect_store():
    """A chain whose single revision already holds the `suspect` record a report would desire."""
    store_module = _module("_lpm_store")
    store = store_module.InMemorySecretStore()
    encoded = _module("_lpm_canonical").canonical_json_text(value=_credential(status="suspect"))
    assert isinstance(encoded, Success), encoded
    committed = store.credential_conditional_set(
        request=store_module.ConditionalSet(
            record_id=_RECORD_ID,
            effect_id=_SEED_EFFECT_ID,
            expected_record=None,
            desired_record=encoded.unwrap(),
        )
    )
    assert committed["status"] == "committed", committed
    return store


def _commit_a_rival_revision(*, store) -> None:
    """Append a revision 2 nobody's fence authorized, so no fence's desired record is current."""
    store_module = _module("_lpm_store")
    expected = _module("_lpm_canonical").canonical_json_text(value=_credential())
    desired = _module("_lpm_canonical").canonical_json_text(value=_credential(status="dead"))
    assert isinstance(expected, Success) and isinstance(desired, Success)
    committed = store.credential_conditional_set(
        request=store_module.ConditionalSet(
            record_id=_RECORD_ID,
            effect_id=_SEED_EFFECT_ID,
            expected_record=expected.unwrap(),
            desired_record=desired.unwrap(),
        )
    )
    assert committed["status"] == "committed", committed


def _lost_pass(*, tmp_path: pathlib.Path):
    state_dir = _live(tmp_path=tmp_path)
    healthy = _healthy_store()
    operation = _operation()
    refused = _driven(state_dir=state_dir, store=_LostTransport(inner=healthy), operation=operation)
    assert isinstance(refused, Failure), refused
    return state_dir, healthy, operation, refused


def test_an_unknown_conditional_write_retains_the_exact_fence_it_authorized(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, healthy, operation, refused = _lost_pass(tmp_path=tmp_path)

    assert refused.failure().error_type == "store-unavailable"
    assert "resolved to store-unavailable" in refused.failure().message
    assert _read(path=_fence_file(state_dir=state_dir)) == _expected_fence(operation=operation)
    assert len(healthy.items[_RECORD_ID]) == 1
    assert len(_audit_entries(state_dir=state_dir)) == 1
    standing = _read(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    )
    assert isinstance(standing, dict)
    assert standing["actual_lease_ended_at"] is None, "no later position ran past the refusal"


def test_a_retry_through_a_healthy_backend_issues_only_the_byte_identical_revision(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, healthy, operation, _ = _lost_pass(tmp_path=tmp_path)

    retried = _driven(state_dir=state_dir, store=healthy, operation=operation)

    assert isinstance(retried, Success), retried
    assert retried.unwrap().skipped == (0, 2, 5)
    assert not _fence_file(state_dir=state_dir).exists()
    assert len(healthy.items[_RECORD_ID]) == 2
    assert healthy.items[_RECORD_ID][-1].title == _module("_lpm_revisions").revision_title(
        record_id=_RECORD_ID,
        revision=2,
        effect_id=_module("_lpm_operation_identity")
        .effect_id(operation=operation, index=1)
        .unwrap(),
    )
    assert len(_audit_entries(state_dir=state_dir)) == 1


def test_an_authoritative_reread_advances_the_effect_without_another_revision(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, healthy, operation, _ = _lost_pass(tmp_path=tmp_path)
    _commit_through_the_retained_fence(state_dir=state_dir, store=healthy)
    still_lost = _LostTransport(inner=healthy)

    retried = _driven(state_dir=state_dir, store=still_lost, operation=operation)

    assert isinstance(retried, Success), retried
    assert still_lost.calls == [], "an authoritative revision needs no further adapter call"
    assert not _fence_file(state_dir=state_dir).exists()
    assert len(healthy.items[_RECORD_ID]) == 2
    assert len(_audit_entries(state_dir=state_dir)) == 1
    assert (
        _read(path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)))
        is not None
    )


def test_a_later_report_cannot_create_another_revision_while_a_fence_remains(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, healthy, _, _ = _lost_pass(tmp_path=tmp_path)
    retained = _read(path=_fence_file(state_dir=state_dir))

    refused = _driven(
        state_dir=state_dir,
        store=healthy,
        operation=_operation(
            operation_id=_SECOND_OPERATION_ID, key=_SECOND_KEY, occurred_at=_SECOND_OCCURRED_AT
        ),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "a different pending metadata-effect fence" in refused.failure().message
    assert _read(path=_fence_file(state_dir=state_dir)) == retained
    assert len(healthy.items[_RECORD_ID]) == 1
    assert len(_audit_entries(state_dir=state_dir)) == 2, "each attempt is its own audited effect"


def test_an_unreadable_fence_keeps_a_settled_report_closed(tmp_path: pathlib.Path) -> None:
    state_dir = _live(tmp_path=tmp_path)
    fence_file = _fence_file(state_dir=state_dir)
    written = _module("_lpm_localstate").write_local_text(
        path=fence_file, text="not json at all", owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written
    untouched = fence_file.read_bytes()

    refused = _driven(state_dir=state_dir, store=_suspect_store(), operation=_operation())

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "malformed JSON" in refused.failure().message
    assert fence_file.read_bytes() == untouched


def test_a_fence_owned_by_another_operation_keeps_a_settled_report_closed(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _live(tmp_path=tmp_path)
    fence_file = _fence_file(state_dir=state_dir)
    _seed(
        path=fence_file,
        value=_expected_fence(
            operation=_operation(operation_id=_SECOND_OPERATION_ID, key=_SECOND_KEY)
        ),
    )
    untouched = fence_file.read_bytes()

    refused = _driven(state_dir=state_dir, store=_suspect_store(), operation=_operation())

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "owner_operation_id must name its owning operation" in refused.failure().message
    assert fence_file.read_bytes() == untouched


def test_a_fence_whose_desired_revision_is_not_authoritative_stays_retained(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, healthy, operation, _ = _lost_pass(tmp_path=tmp_path)
    retained = _read(path=_fence_file(state_dir=state_dir))
    _commit_a_rival_revision(store=healthy)

    refused = _driven(state_dir=state_dir, store=healthy, operation=operation)

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "desired revision is not authoritative" in refused.failure().message
    assert _read(path=_fence_file(state_dir=state_dir)) == retained
    assert len(healthy.items[_RECORD_ID]) == 2
