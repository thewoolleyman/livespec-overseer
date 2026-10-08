"""Mandatory global recovery over every pending metadata-effect fence this manager holds.

SPECIFICATION/contracts.md: "Mandatory global recovery MUST attempt pending fences in lexical
`record_id` order. A malformed fence, unavailable authoritative reread, different authoritative
revision or unsuccessful identical retry MUST quarantine only that record for the current
invocation, retain its fence and owning safety state, and allow recovery to continue for every
other record. A requested command MUST return `store-unavailable` when its explicit or resolved
record identity is quarantined. Provision MUST exclude a quarantined record; if no
non-quarantined record can satisfy the requested provider, kind and purpose and at least one
otherwise matching record was quarantined, it MUST return `store-unavailable` rather than
`retryable-exhaustion`."

THE ORDER IS ASSERTED AT THE BACKEND, NOT IN A RETURNED LIST. A probe records the `record_id` of
every authoritative reread and every conditional set the pass issues, so "visited in lexical
record order" is proven by what the store was actually asked, in sequence — a list the engine
builds for itself could be sorted on the way out while the traversal ran in directory order.

THE SAME PROBE PROVES THE ABSENCE OF A CALL. An exact desired next revision "proves the logical
effect committed and MUST advance it without another adapter call", so a fence whose revision is
already authoritative must be removed on the strength of the reread alone. An engine that
re-issued the create would be indistinguishable from this one on the resulting chain — both end
with the same single revision, because byte-identical physical duplicates collapse — which is
exactly why the call count is the assertion.

THE OPERATION-LESS SHAPE IS THE ONE USED FOR ORDERING, deliberately. Lifecycle expiry "is exempt
from creating a write-ahead operation record", so its fence carries a null `owner_operation_id`
and the fixed `recovery-writer` role; a traversal that could only reach fences through an
operation record would never discover it at all.

A FENCE FILE NO IDENTITY BINDS TO FAILS THE WHOLE PASS, and every shape that can produce one is
exercised rather than just the representative stray. Quarantine is a bound on WHICH records a pass
may not touch, so a fence supplying no bound cannot be skipped under some stand-in — and the
shapes that supply none are not interchangeable: a JSON array, a non-string `record_id`, a
symlink, a directory, bytes that are not UTF-8 and bytes that are not JSON each reach that same
refusal down a different arm, and an implementation that handled five of them would strand the
sixth as a fence nobody looked at.

A RECORD WHOSE OWN FENCE IS UNUSABLE IS QUARANTINED, NOT REFUSED — the distinction being which
scope the failure bounds. An unsafe or malformed fence still NAMES its record, so the bound exists
and the pass stays successful while that one record becomes untouchable. The attribution read is
deliberately not the safe read, which is what lets an unsafe fence report anything about itself at
all; a safe read refuses such a file before it can name the record it guards.

THE RETRY IS ASSERTED AS AN EXACT REQUEST OBJECT, not as "a write happened". "A retry MAY issue
only the byte-identical revision title and fields", so the probe's recorded request is compared
against the one request the fence's own stored records authorize — an engine that rebuilt the
request from anything else would append a revision nobody asked for and still leave a two-revision
chain behind.

THE RECORDED WRITER ROLE IS VALIDATED BEFORE THE RETRY, AND THE ABSENCE OF A CALL IS THE PROOF.
A fence's "writer role MUST equal the semantic audit actor assigned to that owning operation, phase
and effect by the actor table", and a mismatch "MUST return `store-unavailable` without reset or
mutation" — so a fence whose stored role disagrees with what the table derives is quarantined with
NO conditional set issued at all. The matching case is pinned against the table's own answer rather
than against the literal `report-writer`, so the two cannot drift apart.

AN OWNER THAT CANNOT BE PROVEN IS NOT AN OWNER THAT IS ABSENT. Operation records are keyed by
command and idempotency key, so resolving `owner_operation_id` means reading them; an unsafe or
malformed record in that directory leaves the question unanswerable, and the conservative answer
is to quarantine rather than to conclude the fence is unowned and replay it anyway.
"""

from __future__ import annotations

import importlib
import os
import pathlib
from dataclasses import dataclass, field

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_FIRST_RECORD = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
_SECOND_RECORD = "6b7c8d9e-0f1a-4b2c-8d3e-4f5a6b7c8d9e"
_THIRD_RECORD = "cafebabe-1234-4567-89ab-cdef01234567"
_LEXICAL_RECORDS = (_FIRST_RECORD, _SECOND_RECORD, _THIRD_RECORD)

_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_SEED_EFFECT_ID = "9" * 64

_OPERATION_ID = "5c1e8f44-2a76-4b03-9e58-d7a0b3c62f91"
_STRANGER_OPERATION_ID = "e3b70d29-6c85-4f17-a042-9b5c1e8d7306"
_KEY = "6" * 64
_STRANGER_KEY = "7" * 64
_ACCEPTED_AT = "2026-10-07T14:00:00Z"
_OCCURRED_AT = "2026-10-07T14:30:00Z"
_RUN_ID = "run-global-recovery"
_REPORT_WRITE_POSITION = 1
_REPORT_APPLY = (
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


def _credential(*, record_id: str, **changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "version": 1,
        "record_id": record_id,
        "provider": "anthropic",
        "account_id": f"acct-{record_id[:8]}",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-10-07T10:00:00Z",
        "expires_at": None,
        "last_validated": "2026-10-07T10:30:00Z",
        "value_generation": _GENERATION,
        "value_ref": f"op://llm-provider-manager-token-values/{record_id}/credential",
        "previous_value_ref": None,
    }
    record.update(changes)
    return record


@dataclass(kw_only=True)
class _ProbedStore:
    """A real backend that records which record each call named, in call order."""

    inner: object
    reads: list[str] = field(default_factory=list)
    sets: list[object] = field(default_factory=list)

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        self.reads.append(record_id)
        return self.inner.metadata_get(record_id=record_id)  # type: ignore[attr-defined]

    def metadata_list(self) -> dict[str, object]:
        return self.inner.metadata_list()  # type: ignore[attr-defined]

    def credential_conditional_set(self, *, request: object) -> dict[str, object]:
        self.sets.append(request)
        return self.inner.credential_conditional_set(request=request)  # type: ignore[attr-defined]


@dataclass(kw_only=True)
class _LostTransport:
    """A backend that reads normally and whose every write says only that nobody can tell.

    `unavailable` is the contract's UNKNOWN bucket, so a fence guarded by this backend can never
    be settled by a retry — which is what keeps a case about the UNRECONCILED outcome honest
    across later work that teaches the pass to retry at all.
    """

    inner: object

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        return self.inner.metadata_get(record_id=record_id)  # type: ignore[attr-defined]

    def metadata_list(self) -> dict[str, object]:
        return self.inner.metadata_list()  # type: ignore[attr-defined]

    def credential_conditional_set(self, *, request: object) -> dict[str, object]:
        _ = request
        return _module("_lpm_store").set_result(status="unavailable")


def _state(*, tmp_path: pathlib.Path) -> pathlib.Path:
    state_dir = tmp_path / "manager-state"
    state_dir.mkdir(mode=0o700, parents=True)
    return state_dir


def _seed(*, path: pathlib.Path, value: object) -> None:
    written = _module("_lpm_localstate").write_local_record(
        path=path, value=value, owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written


def _fence_file(*, state_dir: pathlib.Path, record_id: str) -> pathlib.Path:
    located = _module("_lpm_fence_store").fence_path(state_dir=state_dir, record_id=record_id)
    assert isinstance(located, Success), located
    return located.unwrap()


def _genesis_store(*, record_ids: tuple[str, ...]):
    """A chain per record, each holding exactly its first `valid` revision."""
    store_module = _module("_lpm_store")
    store = store_module.InMemorySecretStore()
    for record_id in record_ids:
        encoded = _module("_lpm_canonical").canonical_json_text(
            value=_credential(record_id=record_id)
        )
        assert isinstance(encoded, Success), encoded
        committed = store.credential_conditional_set(
            request=store_module.ConditionalSet(
                record_id=record_id,
                effect_id=_SEED_EFFECT_ID,
                expected_record=None,
                desired_record=encoded.unwrap(),
            )
        )
        assert committed["status"] == "committed", committed
    return store


def _expire_effect_id(*, record_id: str) -> str:
    return _module("_lpm_canonical").sha256_hex(data=f"expire-lifecycle:{record_id}".encode())


def _expiry_fence(*, record_id: str):
    """The operation-less lifecycle-expiry fence: `recovery-writer`, null owner, `dead`."""
    built = _module("_lpm_fence").fence_for_effect(
        effect_id=_expire_effect_id(record_id=record_id),
        writer_role="recovery-writer",
        revision=2,
        expected_record=_credential(record_id=record_id),
        desired_record=_credential(record_id=record_id, status="dead"),
        owner_operation_id=None,
    )
    assert isinstance(built, Success), built
    return built.unwrap()


def _seed_fence(*, state_dir: pathlib.Path, fence) -> None:
    _seed(
        path=_fence_file(state_dir=state_dir, record_id=fence.record_id),
        value=_module("_lpm_fence").fence_object(fence=fence),
    )


def _expiry_fence_object(*, record_id: str) -> dict[str, object]:
    return _module("_lpm_fence").fence_object(fence=_expiry_fence(record_id=record_id))


def _fence_directory(*, state_dir: pathlib.Path) -> pathlib.Path:
    directory = _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD).parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory


def _report_input(*, record_id: str) -> dict[str, object]:
    return {
        "version": 1,
        "consumer_run_id": _RUN_ID,
        "record_id": record_id,
        "occurred_at": _OCCURRED_AT,
        "classification": "authentication",
    }


def _report_operation(*, record_id: str, operation_id: str = _OPERATION_ID, key: str = _KEY):
    """A `report` `apply` operation, whose position 1 the actor table assigns `report-writer`."""
    return _module("_lpm_operation").OperationRecord(
        operation_id=operation_id,
        command="report",
        phase="apply",
        idempotency_key=key,
        accepted_at=_ACCEPTED_AT,
        normalized_input=_report_input(record_id=record_id),
        terminal_result=None,
        ordered_effects=_REPORT_APPLY,
        completed_step=-1,
    )


def _operation_file(*, state_dir: pathlib.Path, command: str, key: str) -> pathlib.Path:
    located = _module("_lpm_operation_store").operation_path(
        state_dir=state_dir, command=command, idempotency_key=key
    )
    assert isinstance(located, Success), located
    return located.unwrap()


def _seed_operation(*, state_dir: pathlib.Path, operation) -> pathlib.Path:
    path = _operation_file(
        state_dir=state_dir, command=operation.command, key=operation.idempotency_key
    )
    _seed(path=path, value=_module("_lpm_operation").operation_object(operation=operation))
    return path


def _owned_fence(*, record_id: str, operation, writer_role: str = "report-writer"):
    derived = _module("_lpm_operation_identity").effect_id(
        operation=operation, index=_REPORT_WRITE_POSITION
    )
    assert isinstance(derived, Success), derived
    built = _module("_lpm_fence").fence_for_effect(
        effect_id=derived.unwrap(),
        writer_role=writer_role,
        revision=2,
        expected_record=_credential(record_id=record_id),
        desired_record=_credential(record_id=record_id, status="suspect"),
        owner_operation_id=operation.operation_id,
    )
    assert isinstance(built, Success), built
    return built.unwrap()


def _authorized_request(*, fence):
    """The one conditional set a retry of `fence` is permitted to issue."""
    request = _module("_lpm_fence_reread").conditional_set_request(fence=fence)
    assert isinstance(request, Success), request
    return request.unwrap()


def _validated_role(*, state_dir: pathlib.Path, store, fence):
    return _module("_lpm_fence_owner").validated_writer_role(
        engine=_engine(state_dir=state_dir, store=store), fence=fence
    )


def _actor_for_the_report_write():
    role = _module("_lpm_operation_plan").writer_role_for(
        command="report", phase="apply", effect="credential-conditional-set", outcome=None
    )
    assert isinstance(role, Success), role
    return role.unwrap()


def _commit_through_the_fence(*, store, fence) -> None:
    """Append exactly the revision the retained fence authorizes, and nothing else."""
    request = _module("_lpm_fence_reread").conditional_set_request(fence=fence)
    assert isinstance(request, Success), request
    committed = store.credential_conditional_set(request=request.unwrap())
    assert committed["status"] == "committed", committed


def _engine(*, state_dir: pathlib.Path, store):
    return _module("_lpm_engine_context").OperationEngine(
        state_dir=state_dir, owner_uid=os.getuid(), store=store
    )


def _recover(*, state_dir: pathlib.Path, store):
    return _module("_lpm_engine_recovery").recover_metadata_fences(
        engine=_engine(state_dir=state_dir, store=store)
    )


def test_global_recovery_visits_pending_fences_in_lexical_record_identity_order(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    store = _genesis_store(record_ids=_LEXICAL_RECORDS)
    for record_id in reversed(_LEXICAL_RECORDS):
        fence = _expiry_fence(record_id=record_id)
        _seed_fence(state_dir=state_dir, fence=fence)
        _commit_through_the_fence(store=store, fence=fence)
    probe = _ProbedStore(inner=store)

    recovered = _recover(state_dir=state_dir, store=probe)

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().reconciled == _LEXICAL_RECORDS
    assert recovered.unwrap().quarantined == ()
    assert probe.reads == list(_LEXICAL_RECORDS), "visited in lexical record identity order"
    assert probe.sets == [], "an authoritative desired revision needs no further adapter call"
    assert [
        _fence_file(state_dir=state_dir, record_id=record_id).exists()
        for record_id in _LEXICAL_RECORDS
    ] == [False, False, False]
    assert all(len(store.items[record_id]) == 2 for record_id in _LEXICAL_RECORDS)
    assert isinstance(_recover(state_dir=state_dir, store=store), Success), "nothing left pending"


def test_a_pending_fence_naming_no_bindable_record_identity_fails_the_whole_pass(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    fence = _expiry_fence(record_id=_FIRST_RECORD)
    _seed_fence(state_dir=state_dir, fence=fence)
    stray = _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD).parent / "stray.json"
    _seed(path=stray, value={"record_id": _SECOND_RECORD})
    untouched = _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD).read_bytes()

    refused = _recover(state_dir=state_dir, store=_genesis_store(record_ids=(_FIRST_RECORD,)))

    assert isinstance(refused, Failure), refused
    assert refused.failure().error_type == "store-unavailable"
    assert "naming no record identity" in refused.failure().message
    assert _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD).read_bytes() == untouched


def test_a_manager_holding_no_pending_fence_directory_recovers_an_empty_pass(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)

    recovered = _recover(state_dir=state_dir, store=_genesis_store(record_ids=(_FIRST_RECORD,)))

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().reconciled == ()
    assert recovered.unwrap().quarantined == ()


def test_a_staged_atomic_replacement_is_never_read_as_a_pending_fence(
    tmp_path: pathlib.Path,
) -> None:
    """A half-written temporary carries no family suffix, so the traversal must not see it."""
    state_dir = _state(tmp_path=tmp_path)
    staged = _fence_directory(state_dir=state_dir) / ".c0ffee.json.tmp1234"
    written = _module("_lpm_localstate").write_local_text(
        path=staged, text="not a fence at all", owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written

    recovered = _recover(state_dir=state_dir, store=_genesis_store(record_ids=(_FIRST_RECORD,)))

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().reconciled == ()
    assert staged.exists(), "the traversal reads nothing and removes nothing"


def test_every_fence_byte_shape_naming_no_record_identity_fails_the_whole_pass(
    tmp_path: pathlib.Path,
) -> None:
    shapes = (
        ("a JSON array", b"[]"),
        ("a non-string record_id", b'{"record_id":7}'),
        ("a JSON string", b'"1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"'),
        ("bytes that are not UTF-8", b"\xff\xfe"),
        ("bytes that are not JSON", b"not json at all"),
    )
    for index, (description, payload) in enumerate(shapes):
        state_dir = _state(tmp_path=tmp_path / f"bytes-{index}")
        written = _module("_lpm_localstate").write_local_bytes(
            path=_fence_file(state_dir=state_dir, record_id=_FIRST_RECORD),
            payload=payload,
            owner_uid=os.getuid(),
        )
        assert isinstance(written, Success), written

        refused = _recover(state_dir=state_dir, store=_genesis_store(record_ids=(_FIRST_RECORD,)))

        assert isinstance(refused, Failure), description
        assert refused.failure().error_type == "store-unavailable", description
        assert "naming no record identity" in refused.failure().message, description


def test_a_fence_path_that_is_not_a_regular_file_is_refused_unread(
    tmp_path: pathlib.Path,
) -> None:
    """Following a symlink would read outside the state directory; a FIFO would never return."""
    for index, kind in enumerate(("symlink", "directory")):
        state_dir = _state(tmp_path=tmp_path / f"path-{index}")
        path = (
            _fence_directory(state_dir=state_dir)
            / _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD).name
        )
        if kind == "symlink":
            path.symlink_to(tmp_path)
        else:
            path.mkdir(mode=0o700)

        refused = _recover(state_dir=state_dir, store=_genesis_store(record_ids=(_FIRST_RECORD,)))

        assert isinstance(refused, Failure), kind
        assert "naming no record identity" in refused.failure().message, kind


def test_a_fence_more_broadly_accessible_than_its_owner_quarantines_its_own_record(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    fence_file = _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD)
    _seed(path=fence_file, value=_expiry_fence_object(record_id=_FIRST_RECORD))
    fence_file.chmod(0o644)
    untouched = fence_file.read_bytes()

    recovered = _recover(state_dir=state_dir, store=_genesis_store(record_ids=(_FIRST_RECORD,)))

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().reconciled == ()
    assert recovered.unwrap().quarantined == (_FIRST_RECORD,)
    assert fence_file.read_bytes() == untouched, "an unsafe fence is evidence, not litter"


def test_a_fence_whose_stored_members_are_malformed_quarantines_its_own_record(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    fence_file = _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD)
    members = _expiry_fence_object(record_id=_FIRST_RECORD)
    del members["version"]
    _seed(path=fence_file, value=members)
    untouched = fence_file.read_bytes()

    recovered = _recover(state_dir=state_dir, store=_genesis_store(record_ids=(_FIRST_RECORD,)))

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().quarantined == (_FIRST_RECORD,)
    assert fence_file.read_bytes() == untouched


def test_a_fence_whose_desired_revision_is_unreconciled_stays_quarantined_and_retained(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    store = _genesis_store(record_ids=(_FIRST_RECORD,))
    _seed_fence(state_dir=state_dir, fence=_expiry_fence(record_id=_FIRST_RECORD))
    fence_file = _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD)
    retained = fence_file.read_bytes()

    recovered = _recover(state_dir=state_dir, store=_LostTransport(inner=store))

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().reconciled == ()
    assert recovered.unwrap().quarantined == (_FIRST_RECORD,)
    assert fence_file.read_bytes() == retained
    assert len(store.items[_FIRST_RECORD]) == 1, "no revision this fence did not authorize"


def test_an_uncommitted_safe_fence_retries_only_its_byte_identical_revision(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    store = _genesis_store(record_ids=(_FIRST_RECORD,))
    fence = _expiry_fence(record_id=_FIRST_RECORD)
    _seed_fence(state_dir=state_dir, fence=fence)
    probe = _ProbedStore(inner=store)

    recovered = _recover(state_dir=state_dir, store=probe)

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().reconciled == (_FIRST_RECORD,)
    assert probe.sets == [_authorized_request(fence=fence)], "only the revision the fence records"
    assert not _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD).exists()
    assert len(store.items[_FIRST_RECORD]) == 2
    assert store.items[_FIRST_RECORD][-1].title == fence.item_title


def test_an_owned_fence_retries_under_the_writer_role_its_operation_phase_implies(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    store = _genesis_store(record_ids=(_FIRST_RECORD,))
    operation = _report_operation(record_id=_FIRST_RECORD)
    operation_file = _seed_operation(state_dir=state_dir, operation=operation)
    untouched = operation_file.read_bytes()
    fence = _owned_fence(record_id=_FIRST_RECORD, operation=operation)
    _seed_fence(state_dir=state_dir, fence=fence)

    role = _validated_role(state_dir=state_dir, store=store, fence=fence)
    recovered = _recover(state_dir=state_dir, store=store)

    assert isinstance(role, Success), role
    assert role.unwrap() == _actor_for_the_report_write() == "report-writer"
    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().reconciled == (_FIRST_RECORD,)
    assert not _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD).exists()
    assert len(store.items[_FIRST_RECORD]) == 2
    assert operation_file.read_bytes() == untouched, "this pass never writes an operation record"


def test_a_fence_whose_recorded_role_is_not_its_phase_actor_is_quarantined_unretried(
    tmp_path: pathlib.Path,
) -> None:
    """A role nobody assigned that position must not be replayed under, however safe the file."""
    state_dir = _state(tmp_path=tmp_path)
    store = _genesis_store(record_ids=(_FIRST_RECORD,))
    operation = _report_operation(record_id=_FIRST_RECORD)
    _seed_operation(state_dir=state_dir, operation=operation)
    fence = _owned_fence(
        record_id=_FIRST_RECORD, operation=operation, writer_role="lifecycle-writer"
    )
    _seed_fence(state_dir=state_dir, fence=fence)
    fence_file = _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD)
    retained = fence_file.read_bytes()
    probe = _ProbedStore(inner=store)

    recovered = _recover(state_dir=state_dir, store=probe)

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().quarantined == (_FIRST_RECORD,)
    assert probe.sets == [], "the role is validated BEFORE the retry, not after it"
    assert fence_file.read_bytes() == retained
    assert len(store.items[_FIRST_RECORD]) == 1


def test_a_fence_naming_no_resolvable_owning_operation_is_quarantined_unretried(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    store = _genesis_store(record_ids=(_FIRST_RECORD,))
    operation = _report_operation(record_id=_FIRST_RECORD)
    fence = _owned_fence(record_id=_FIRST_RECORD, operation=operation)
    _seed_fence(state_dir=state_dir, fence=fence)
    probe = _ProbedStore(inner=store)

    recovered = _recover(state_dir=state_dir, store=probe)

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().quarantined == (_FIRST_RECORD,)
    assert probe.sets == []
    assert _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD).exists()


def test_a_fence_is_not_adopted_by_a_stranger_operation_record(
    tmp_path: pathlib.Path,
) -> None:
    """Operation records are keyed by command and idempotency key, so the id is the only test."""
    state_dir = _state(tmp_path=tmp_path)
    store = _genesis_store(record_ids=(_FIRST_RECORD,))
    _seed_operation(
        state_dir=state_dir,
        operation=_report_operation(
            record_id=_FIRST_RECORD,
            operation_id=_STRANGER_OPERATION_ID,
            key=_STRANGER_KEY,
        ),
    )
    fence = _owned_fence(
        record_id=_FIRST_RECORD, operation=_report_operation(record_id=_FIRST_RECORD)
    )
    _seed_fence(state_dir=state_dir, fence=fence)
    probe = _ProbedStore(inner=store)

    recovered = _recover(state_dir=state_dir, store=probe)

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().quarantined == (_FIRST_RECORD,)
    assert probe.sets == []


def test_an_unusable_operation_record_leaves_the_owner_unproven_and_quarantines(
    tmp_path: pathlib.Path,
) -> None:
    """Nobody can prove the owner is absent OR valid, so the conservative answer is quarantine."""
    for index, damage in enumerate(("unsafe", "malformed")):
        state_dir = _state(tmp_path=tmp_path / f"owner-{index}")
        store = _genesis_store(record_ids=(_FIRST_RECORD,))
        operation = _report_operation(record_id=_FIRST_RECORD)
        operation_file = _seed_operation(state_dir=state_dir, operation=operation)
        if damage == "unsafe":
            operation_file.chmod(0o644)
        else:
            members = _module("_lpm_operation").operation_object(operation=operation)
            del members["phase"]
            _seed(path=operation_file, value=members)
        _seed_fence(
            state_dir=state_dir, fence=_owned_fence(record_id=_FIRST_RECORD, operation=operation)
        )
        probe = _ProbedStore(inner=store)

        recovered = _recover(state_dir=state_dir, store=probe)

        assert isinstance(recovered, Success), damage
        assert recovered.unwrap().quarantined == (_FIRST_RECORD,), damage
        assert probe.sets == [], damage


def test_an_inherited_fence_retries_but_keeps_itself_after_an_unknown_outcome(
    tmp_path: pathlib.Path,
) -> None:
    """A recovery pass always INHERITS its fence, so no definitive result may resolve it."""
    state_dir = _state(tmp_path=tmp_path)
    store = _genesis_store(record_ids=(_FIRST_RECORD,))
    fence = _expiry_fence(record_id=_FIRST_RECORD)
    _seed_fence(state_dir=state_dir, fence=fence)
    fence_file = _fence_file(state_dir=state_dir, record_id=_FIRST_RECORD)
    retained = fence_file.read_bytes()
    probe = _ProbedStore(inner=_LostTransport(inner=store))

    recovered = _recover(state_dir=state_dir, store=probe)

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().quarantined == (_FIRST_RECORD,)
    assert probe.sets == [_authorized_request(fence=fence)], "exactly one, and only the authorized"
    assert fence_file.read_bytes() == retained
    assert len(store.items[_FIRST_RECORD]) == 1
