"""An unknown adapter result is decided by rereading the real store, not by believing it.

SPECIFICATION/contracts.md requires that after a deadline, interruption, unavailable transport or
malformed adapter result the manager BYPASS EVERY CACHE and authoritatively reread the complete
metadata revision chain: an exact desired next revision CARRYING THAT `effect_id` proves the
logical effect committed and advances it without another adapter call, while the exact expected
predecessor or expected absence proves only that no desired revision was visible by that reread.

THESE TESTS DRIVE A REAL BACKEND, not a classification string handed in by the test. The store is
the hermetic `InMemorySecretStore`, which implements the actual append-only revision protocol —
predecessor comparison, title derivation, byte-identical collapse — so the reread is really being
computed from a chain rather than asserted. The one thing the test fabricates is the TRANSPORT
failure, through a delegating double that commits the revision and then reports `unavailable`:
that is precisely the hazard the fence exists for, and it cannot be produced any other way
without killing a process.

THE FOUR BRANCHES ARE EXERCISED SEPARATELY BECAUSE THEY DISAGREE. After an unknown result the
same fence resolves to ADVANCE when the desired revision is there, to a retained fence when the
expected predecessor is still current, to a retained fence when a DIFFERENT revision is current
and the fence was inherited, and to a definitive condition-failure only when this invocation
created the fence from absence. A reconciliation that collapsed any pair of those would either
duplicate a logical revision or strand a record behind a fence nobody can clear.

TITLE EQUALITY IS ASSERTED AS WELL AS BYTE EQUALITY, with a control: a chain whose current record
bytes EQUAL the desired record but whose revision carries a DIFFERENT effect id must NOT read as
`desired`. Two effects can legitimately desire byte-identical records, so matching bytes alone
would let one effect claim another's commit as proof of its own.
"""

from __future__ import annotations

import importlib
import pathlib
from dataclasses import dataclass, field

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_OPERATION_ID = "1b4e28ba-2fa1-4d82-a4cc-3d9c5c0bb4a1"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_EFFECT_ID = "d" * 64
_OTHER_EFFECT_ID = "e" * 64
_REF = "op://llm-provider-manager-token-values/3f2504e0-gen/credential"


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _reread():
    return _module("_lpm_fence_reread")


def _record(**changes: object) -> dict[str, object]:
    source: dict[str, object] = {
        "version": 1,
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": "acct-1",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-09-30T09:00:00Z",
        "expires_at": None,
        "last_validated": "2026-09-30T09:00:00Z",
        "value_generation": _GENERATION,
        "value_ref": _REF,
        "previous_value_ref": None,
    }
    source.update(changes)
    return source


def _acquiring() -> dict[str, object]:
    return _record(status="acquiring", value_generation=None, value_ref=None)


def _genesis_fence(*, effect_id: str = _EFFECT_ID, desired: dict[str, object] | None = None):
    return (
        _module("_lpm_fence")
        .fence_for_effect(
            effect_id=effect_id,
            writer_role="acquisition-writer",
            revision=1,
            expected_record=None,
            desired_record=_acquiring() if desired is None else desired,
            owner_operation_id=_OPERATION_ID,
        )
        .unwrap()
    )


def _successor_fence(*, expected: dict[str, object], desired: dict[str, object]):
    return (
        _module("_lpm_fence")
        .fence_for_effect(
            effect_id=_EFFECT_ID,
            writer_role="lifecycle-writer",
            revision=2,
            expected_record=expected,
            desired_record=desired,
            owner_operation_id=_OPERATION_ID,
        )
        .unwrap()
    )


def _store():
    return _module("_lpm_store").InMemorySecretStore()


@dataclass(kw_only=True)
class _LostTransport:
    """A store that COMMITS the revision and then reports `unavailable`.

    This is the hazard the fence exists for and the one shape a hermetic test cannot otherwise
    produce: the backend accepted the append, and the caller will never learn that it did.
    """

    inner: object
    lost_calls: int = 1
    calls: list[str] = field(default_factory=list)

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        return self.inner.metadata_get(record_id=record_id)  # pyright: ignore[reportAttributeAccessIssue]

    def metadata_list(self) -> dict[str, object]:
        return self.inner.metadata_list()  # pyright: ignore[reportAttributeAccessIssue]

    def credential_conditional_set(self, *, request: object) -> dict[str, object]:
        self.calls.append(str(request))
        committed = self.inner.credential_conditional_set(request=request)  # pyright: ignore[reportAttributeAccessIssue]
        if len(self.calls) <= self.lost_calls:
            return {"version": 1, "status": "unavailable"}
        return committed


# ---------------------------------------------------------------------------
# The reread classification, computed from a real chain
# ---------------------------------------------------------------------------


def test_a_fence_over_an_empty_chain_reads_as_its_own_expected_absence():
    module = _reread()
    store = _store()

    assert module.authoritative_reread(store=store, fence=_genesis_fence()) == "absent"
    assert (
        module.authoritative_reread(
            store=store,
            fence=_successor_fence(expected=_record(), desired=_record(status="suspect")),
        )
        == "different"
    ), "a fence expecting a predecessor meets an empty chain as a DIFFERENT current revision"


def test_the_exact_desired_revision_carrying_this_effect_id_reads_as_desired():
    module = _reread()
    store = _store()
    fence = _genesis_fence()

    before = module.authoritative_reread(store=store, fence=fence)
    _ = store.credential_conditional_set(
        request=module.conditional_set_request(fence=fence).unwrap()
    )
    after = module.authoritative_reread(store=store, fence=fence)

    assert before == "absent"
    assert after == "desired"
    assert (
        module.authoritative_reread(store=store, fence=_genesis_fence(effect_id=_OTHER_EFFECT_ID))
        == "different"
    ), "identical record bytes under a DIFFERENT effect id are not this effect's commit"


def test_an_expected_predecessor_still_current_reads_as_expected():
    module = _reread()
    store = _store()
    genesis = _genesis_fence()
    _ = store.credential_conditional_set(
        request=module.conditional_set_request(fence=genesis).unwrap()
    )
    successor = _successor_fence(expected=_acquiring(), desired=_record())

    assert module.authoritative_reread(store=store, fence=successor) == "expected"


def test_an_unavailable_or_invalid_chain_reads_as_unreadable_rather_than_absent():
    module = _reread()
    store = _store()
    revisions = _module("_lpm_revisions")
    store.items[_RECORD_ID] = [
        revisions.RevisionItem(
            title=revisions.revision_title(record_id=_RECORD_ID, revision=2, effect_id=_EFFECT_ID),
            predecessor_sha256="0" * 64,
            record="{}",
        )
    ]
    unavailable = _store()
    unavailable.available = False

    assert (
        module.authoritative_reread(store=store, fence=_genesis_fence()) == "unreadable"
    ), "an invalid chain proves nothing; collapsing it onto absence would authorize a create"
    assert module.authoritative_reread(store=unavailable, fence=_genesis_fence()) == "unreadable"


# ---------------------------------------------------------------------------
# The four unknown-outcome branches, driven end to end
# ---------------------------------------------------------------------------


def test_a_lost_transport_whose_revision_landed_advances_without_another_adapter_call():
    module = _reread()
    inner = _store()
    store = _LostTransport(inner=inner)
    fence = _genesis_fence()

    decision = module.apply_fenced_set(store=store, fence=fence, created_from_absence=True).unwrap()

    assert len(store.calls) == 1, "the reread decides it; no second adapter call is made"
    assert (
        decision.disposition == "advance"
    ), "the exact desired revision carrying this effect_id proves the logical effect committed"
    assert decision.retain_fence is False
    assert module.authoritative_reread(store=inner, fence=fence) == "desired"


def test_a_lost_transport_whose_revision_did_not_land_retains_the_fence():
    module = _reread()
    inner = _store()
    inner.available = False
    store = _LostTransport(inner=inner)

    decision = module.apply_fenced_set(
        store=store, fence=_genesis_fence(), created_from_absence=True
    ).unwrap()

    assert decision.disposition == "store-unavailable"
    assert (
        decision.retain_fence is True
    ), "an absence cannot rule out a create still in flight, so the guard stays"


def test_an_unknown_result_over_a_still_current_expected_predecessor_retains_the_fence():
    module = _reread()
    inner = _store()
    genesis = _genesis_fence()
    _ = inner.credential_conditional_set(
        request=module.conditional_set_request(fence=genesis).unwrap()
    )
    successor = _successor_fence(expected=_acquiring(), desired=_record())
    store = _LostTransport(inner=inner, lost_calls=0)
    store.inner = _Refusing(inner=inner)

    decision = module.apply_fenced_set(
        store=store, fence=successor, created_from_absence=True
    ).unwrap()

    assert module.authoritative_reread(store=inner, fence=successor) == "expected"
    assert decision.disposition == "store-unavailable"
    assert (
        decision.retain_fence is True
    ), "the expected predecessor proves only that no desired revision was visible"


@dataclass(kw_only=True)
class _Refusing:
    """A store whose conditional set never reaches the backend and reports `unavailable`."""

    inner: object

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        return self.inner.metadata_get(record_id=record_id)  # pyright: ignore[reportAttributeAccessIssue]

    def metadata_list(self) -> dict[str, object]:
        return self.inner.metadata_list()  # pyright: ignore[reportAttributeAccessIssue]

    def credential_conditional_set(self, *, request: object) -> dict[str, object]:
        _ = request
        return {"version": 1, "status": "unavailable"}


def test_a_different_current_revision_proves_the_condition_failed_only_for_an_absence_create():
    module = _reread()
    inner = _store()
    _ = inner.credential_conditional_set(
        request=module.conditional_set_request(
            fence=_genesis_fence(effect_id=_OTHER_EFFECT_ID, desired=_record())
        ).unwrap()
    )
    fence = _genesis_fence()

    own = module.apply_fenced_set(store=inner, fence=fence, created_from_absence=True).unwrap()
    inherited = module.apply_fenced_set(
        store=inner, fence=fence, created_from_absence=False
    ).unwrap()

    assert module.authoritative_reread(store=inner, fence=fence) == "different"
    assert own.disposition == "condition-failed"
    assert own.retain_fence is False
    assert (
        inherited.disposition == "store-unavailable"
    ), "a fence found present is conservatively treated as having a prior unknown outcome"
    assert inherited.retain_fence is True


def test_the_retry_may_issue_only_the_byte_identical_revision_built_from_the_fence():
    module = _reread()
    inner = _store()
    fence = _genesis_fence()
    request = module.conditional_set_request(fence=fence).unwrap()
    canonical = _module("_lpm_canonical")

    first = inner.credential_conditional_set(request=request)
    replayed = inner.credential_conditional_set(
        request=module.conditional_set_request(fence=fence).unwrap()
    )

    assert request.record_id == _RECORD_ID
    assert request.effect_id == _EFFECT_ID
    assert request.expected_record is None, "a genesis fence expects absence"
    assert request.desired_record == canonical.canonical_json_text(value=_acquiring()).unwrap()
    assert first["status"] == "committed"
    assert (
        replayed["status"] == "committed"
    ), "the byte-identical replay collapses onto the one logical revision"
    assert len(inner.items[_RECORD_ID]) == 1


def test_an_unencodable_fenced_record_is_a_caller_bug_rather_than_a_store_answer():
    module = _reread()
    fence_module = _module("_lpm_fence")
    unencodable = fence_module.MetadataFence(
        record_id=_RECORD_ID,
        effect_id=_EFFECT_ID,
        writer_role="acquisition-writer",
        revision=1,
        item_title=f"{_RECORD_ID}-m00000000000000000001-{_EFFECT_ID}",
        predecessor_sha256="0" * 64,
        expected_record=None,
        desired_record={"ratio": 1.5},
        owner_operation_id=_OPERATION_ID,
    )
    bad_expected = fence_module.MetadataFence(
        record_id=_RECORD_ID,
        effect_id=_EFFECT_ID,
        writer_role="acquisition-writer",
        revision=2,
        item_title=f"{_RECORD_ID}-m00000000000000000002-{_EFFECT_ID}",
        predecessor_sha256="0" * 64,
        expected_record={"ratio": 1.5},
        desired_record=_acquiring(),
        owner_operation_id=_OPERATION_ID,
    )
    store = _store()

    assert module.conditional_set_request(fence=unencodable).failure().message == (
        "a fenced desired record is not encodable"
    )
    assert module.conditional_set_request(fence=bad_expected).failure().message == (
        "a fenced expected record is not encodable"
    )
    assert (
        module.apply_fenced_set(store=store, fence=unencodable, created_from_absence=True)
        .failure()
        .error_type
        == "internal-bug"
    )
    assert module.authoritative_reread(store=store, fence=unencodable) == "absent"


@dataclass(kw_only=True)
class _Nonconforming:
    """A store whose `ok` result carries an envelope that is not an object."""

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        _ = record_id
        return {"version": 1, "status": "ok", "item": "not-an-envelope"}

    def metadata_list(self) -> dict[str, object]:
        return {"version": 1, "status": "unavailable"}

    def credential_conditional_set(self, *, request: object) -> dict[str, object]:
        _ = request
        return {"version": 1, "status": "unavailable"}


def test_a_chain_this_module_cannot_compare_against_reads_as_unreadable():
    module = _reread()
    fence_module = _module("_lpm_fence")
    inner = _store()
    _ = inner.credential_conditional_set(
        request=module.conditional_set_request(fence=_genesis_fence()).unwrap()
    )
    unencodable_desired = fence_module.MetadataFence(
        record_id=_RECORD_ID,
        effect_id=_EFFECT_ID,
        writer_role="acquisition-writer",
        revision=1,
        item_title=f"{_RECORD_ID}-m00000000000000000001-{_EFFECT_ID}",
        predecessor_sha256="0" * 64,
        expected_record=None,
        desired_record={"ratio": 1.5},
        owner_operation_id=_OPERATION_ID,
    )
    unencodable_expected = fence_module.MetadataFence(
        record_id=_RECORD_ID,
        effect_id=_EFFECT_ID,
        writer_role="acquisition-writer",
        revision=2,
        item_title=f"{_RECORD_ID}-m00000000000000000002-{_EFFECT_ID}",
        predecessor_sha256="0" * 64,
        expected_record={"ratio": 1.5},
        desired_record=_record(status="suspect"),
        owner_operation_id=_OPERATION_ID,
    )

    assert module.authoritative_reread(store=_Nonconforming(), fence=_genesis_fence()) == (
        "unreadable"
    ), "an envelope this module cannot read proves nothing about the chain"
    assert (
        module.authoritative_reread(store=inner, fence=unencodable_desired) == "unreadable"
    ), "a desired record with no reproducible byte form cannot be compared to anything"
    assert module.authoritative_reread(store=inner, fence=unencodable_expected) == "unreadable"


def test_the_store_statuses_map_onto_the_contract_s_adapter_outcome_vocabulary():
    module = _reread()

    assert module.ADAPTER_OUTCOME_BY_STATUS == {
        "committed": "committed",
        "condition-failed": "condition-failed",
        "uncommitted": "uncommitted",
        "unavailable": "unknown",
    }, "an unavailable transport is the contract's UNKNOWN, never an assertion about committing"
