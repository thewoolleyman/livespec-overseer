"""A fenced conditional-set reconciles from authoritative state, and quarantine stays local.

SPECIFICATION/contracts.md states the pending metadata-effect fence as exactly ten members
whose revision, title and predecessor digest EQUAL the append-only logical-revision forms
derived from the records beside them and the effect id, and whose writer role equals the
semantic audit actor the actor table assigns to the owning operation, phase and effect. After
an unknown adapter result the manager must bypass every cache and authoritatively reread the
chain: an exact desired revision proves the effect committed, while the expected predecessor or
expected absence proves ONLY that no desired revision was visible by that reread.

THE ASYMMETRY IS WHAT THESE TESTS ARE FOR, and it runs one way only. Evidence that the revision
landed is conclusive; evidence that it did not is an absence, and an absence cannot rule out a
create still in flight. So every branch below that cannot see the desired revision RETAINS the
fence, and the two that can remove it — and the `created_from_absence` discriminator is
asserted directly, because a call that found the fence already present cannot distinguish a
crash before the adapter call from a crash after it and must treat its own definitive
`condition-failed` as inconclusive.

QUARANTINE IS ASSERTED AS A BOUND, not merely as a behaviour. One unreconcilable fence must not
wedge unrelated records, so recovery continues past it in lexical order; and a provision pool
emptied by quarantine must report `store-unavailable` rather than `retryable-exhaustion`,
because exhaustion invites a retry and a quarantined record is one nobody can read.
"""

from __future__ import annotations

import importlib
import os
import pathlib

from _lpm_results import store_unavailable

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_OTHER_RECORD_ID = "5c2f1b8a-6d3e-4a9b-8c7d-2e1f0a9b8c7d"
_OPERATION_ID = "1b4e28ba-2fa1-4d82-a4cc-3d9c5c0bb4a1"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_EFFECT_ID = "d" * 64
_KEY = "e" * 64
_GENESIS = "0" * 64
_REF = "op://llm-provider-manager-token-values/3f2504e0-gen/credential"


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _fence():
    return _module("_lpm_fence")


def _fence_store():
    return _module("_lpm_fence_store")


def _recovery():
    return _module("_lpm_fence_recovery")


def _uid() -> int:
    return os.geteuid()


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


def _genesis_fence(**changes: object):
    built = _fence().fence_for_effect(
        effect_id=_EFFECT_ID,
        writer_role="acquisition-writer",
        revision=1,
        expected_record=None,
        desired_record=_record(status="acquiring", value_generation=None, value_ref=None),
        owner_operation_id=_OPERATION_ID,
    )
    if not changes:
        return built.unwrap()
    source = _fence().fence_object(fence=built.unwrap())
    source.update(changes)
    return source


def _defect(**changes: object) -> str:
    return _fence().fence_from_object(parsed=_genesis_fence(**changes)).failure().message


# ---------------------------------------------------------------------------
# The fence record and its derived relations
# ---------------------------------------------------------------------------


def test_the_fence_is_exactly_the_ten_ratified_members_with_derived_relations():
    module = _fence()
    fence = _genesis_fence()

    assert module.FENCE_MEMBERS == (
        "version",
        "record_id",
        "effect_id",
        "writer_role",
        "revision",
        "item_title",
        "predecessor_sha256",
        "expected_record",
        "desired_record",
        "owner_operation_id",
    )
    assert module.fence_object(fence=fence) == {
        "version": 1,
        "record_id": _RECORD_ID,
        "effect_id": _EFFECT_ID,
        "writer_role": "acquisition-writer",
        "revision": 1,
        "item_title": f"{_RECORD_ID}-m00000000000000000001-{_EFFECT_ID}",
        "predecessor_sha256": _GENESIS,
        "expected_record": None,
        "desired_record": _record(status="acquiring", value_generation=None, value_ref=None),
        "owner_operation_id": _OPERATION_ID,
    }


def test_a_fence_following_an_expected_predecessor_digests_that_predecessor():
    module = _fence()
    canonical = _module("_lpm_canonical")
    expected = _record(status="revalidating")

    fence = module.fence_for_effect(
        effect_id=_EFFECT_ID,
        writer_role="lifecycle-writer",
        revision=2,
        expected_record=expected,
        desired_record=_record(status="suspect"),
        owner_operation_id=_OPERATION_ID,
    ).unwrap()

    assert fence.predecessor_sha256 == canonical.sha256_hex(
        data=canonical.canonical_json_text(value=expected).unwrap().encode("utf-8")
    )
    assert fence.item_title == f"{_RECORD_ID}-m00000000000000000002-{_EFFECT_ID}"
    assert fence.revision == 2


def test_a_desired_record_with_no_record_id_is_a_caller_bug():
    module = _fence()

    refusal = module.fence_for_effect(
        effect_id=_EFFECT_ID,
        writer_role="acquisition-writer",
        revision=1,
        expected_record=None,
        desired_record={"version": 1},
        owner_operation_id=_OPERATION_ID,
    )

    assert refusal.failure().error_type == "internal-bug"
    assert refusal.failure().message == "a desired record must carry its record_id"


def test_an_unencodable_expected_record_cannot_acquire_a_plausible_digest():
    module = _fence()

    refusal = module.fence_for_effect(
        effect_id=_EFFECT_ID,
        writer_role="lifecycle-writer",
        revision=2,
        expected_record=_record(ratio=1.5),
        desired_record=_record(status="suspect"),
        owner_operation_id=_OPERATION_ID,
    )

    assert refusal.failure().message == (
        "a fence predecessor_sha256 must be a lowercase SHA-256 hex digest"
    )


def test_every_fence_membership_and_type_defect_fails_closed():
    module = _fence()
    missing = _genesis_fence(version=1)
    del missing["revision"]

    assert module.fence_from_object(parsed="not an object").failure().message == (
        "a metadata fence must be a JSON object"
    )
    assert module.fence_from_object(parsed=missing).failure().message == (
        "a metadata fence is missing revision"
    )
    assert _defect(extra_member=1) == "a metadata fence has extra member extra_member"
    assert _defect(version=True) == "a metadata fence version must be the integer 1"
    assert _defect(version=0) == "a metadata fence version must be the integer 1"
    assert _defect(record_id="NOT-A-UUID") == (
        "a fence record_id must be a lowercase RFC 4122 UUIDv4"
    )
    assert _defect(effect_id="short") == "a fence effect_id must be a lowercase SHA-256 hex digest"
    assert _defect(predecessor_sha256="ABC") == (
        "a fence predecessor_sha256 must be a lowercase SHA-256 hex digest"
    )
    assert _defect(writer_role="janitor") == (
        "a fence writer_role must be one of acquisition-writer, lifecycle-writer, "
        "report-writer, recovery-writer"
    )
    assert _defect(revision=0) == "a fence revision must be a positive integer"
    assert _defect(revision=True) == "a fence revision must be a positive integer"
    assert _defect(item_title="") == "a fence item_title must be a non-empty string"


def test_only_operation_less_lifecycle_expiry_may_omit_its_owning_operation():
    assert _defect(owner_operation_id=None) == (
        "only operation-less lifecycle expiry may omit owner_operation_id"
    )
    assert _defect(owner_operation_id="not-a-uuid") == (
        "a fence owner_operation_id must be null or a lowercase RFC 4122 UUIDv4"
    )
    assert (
        _fence()
        .fence_from_object(
            parsed=_genesis_fence(writer_role="recovery-writer", owner_operation_id=None)
        )
        .unwrap()
        .owner_operation_id
        is None
    )


def test_an_invalid_record_inside_a_fence_makes_the_fence_unusable():
    assert _defect(desired_record=_record(status="nonsense")).startswith(
        "a fence desired_record is invalid: "
    )
    assert _defect(
        expected_record=_record(status="nonsense"),
        revision=2,
        item_title=f"{_RECORD_ID}-m00000000000000000002-{_EFFECT_ID}",
    ).startswith("a fence expected_record is invalid: ")


def test_a_fence_whose_derived_relations_disagree_is_relation_invalid():
    other = _record(record_id=_OTHER_RECORD_ID)

    assert _defect(desired_record=other) == (
        "a fence desired_record must name the fence's own record_id"
    )
    assert (
        _defect(
            expected_record=other,
            revision=2,
            item_title=f"{_RECORD_ID}-m00000000000000000002-{_EFFECT_ID}",
        )
        == "a fence expected_record must name the fence's own record_id"
    )
    assert _defect(item_title="an-invented-title") == (
        "a fence item_title must be the derived append-only revision title"
    )
    assert (
        _defect(revision=2, item_title=f"{_RECORD_ID}-m00000000000000000002-{_EFFECT_ID}")
        == "a fence creating from absence must be revision 1"
    )
    assert _defect(predecessor_sha256="a" * 64) == (
        "a fence creating from absence must carry the genesis predecessor digest"
    )


def test_a_successor_fence_must_be_revision_two_or_later_and_digest_its_predecessor():
    expected = _record(status="revalidating")
    fence = (
        _fence()
        .fence_for_effect(
            effect_id=_EFFECT_ID,
            writer_role="lifecycle-writer",
            revision=2,
            expected_record=expected,
            desired_record=_record(status="suspect"),
            owner_operation_id=_OPERATION_ID,
        )
        .unwrap()
    )
    source = _fence().fence_object(fence=fence)

    first = dict(source)
    first["revision"] = 1
    first["item_title"] = f"{_RECORD_ID}-m00000000000000000001-{_EFFECT_ID}"
    mismatched = dict(source)
    mismatched["predecessor_sha256"] = "b" * 64

    assert _fence().fence_from_object(parsed=first).failure().message == (
        "a fence following an expected predecessor must be revision 2 or later"
    )
    assert _fence().fence_from_object(parsed=mismatched).failure().message == (
        "a fence predecessor_sha256 must digest its own expected_record"
    )
    assert _fence().fence_from_object(parsed=source).unwrap() == fence


# ---------------------------------------------------------------------------
# Claiming the fence: created from absence, or conservatively found present
# ---------------------------------------------------------------------------


def test_the_fence_path_is_the_contract_s_record_keyed_digest(tmp_path):
    paths = _module("_lpm_paths")
    state_dir = tmp_path / "state"

    resolved = _fence_store().fence_path(state_dir=state_dir, record_id=_RECORD_ID).unwrap()

    assert (
        resolved
        == paths.local_record_path(
            state_dir=state_dir, family="pending-metadata-effect", identity=(_RECORD_ID,)
        ).unwrap()
    )
    assert resolved.parent.name == "pending-metadata-effects"


def test_an_absent_fence_means_no_pending_metadata_create(tmp_path):
    store = _fence_store()
    path = store.fence_path(state_dir=tmp_path / "state", record_id=_RECORD_ID).unwrap()

    assert store.read_fence(path=path, owner_uid=_uid()).unwrap() is None


def test_a_first_claim_creates_the_fence_and_a_second_finds_it_present(tmp_path):
    store = _fence_store()
    path = store.fence_path(state_dir=tmp_path / "state", record_id=_RECORD_ID).unwrap()
    fence = _genesis_fence()

    first = store.claim_fence(path=path, fence=fence, owner_uid=_uid()).unwrap()
    second = store.claim_fence(path=path, fence=fence, owner_uid=_uid()).unwrap()

    assert first.created_from_absence is True
    assert (
        second.created_from_absence is False
    ), "a fence found present cannot distinguish a pre-call crash from a post-call one"
    assert second.fence == fence
    assert path.stat().st_mode & 0o777 == 0o600
    assert store.read_fence(path=path, owner_uid=_uid()).unwrap() == fence


def test_a_different_fence_already_guarding_the_record_is_refused_and_left_alone(tmp_path):
    store = _fence_store()
    path = store.fence_path(state_dir=tmp_path / "state", record_id=_RECORD_ID).unwrap()
    mine = _genesis_fence()
    theirs = (
        _fence()
        .fence_for_effect(
            effect_id="f" * 64,
            writer_role="recovery-writer",
            revision=1,
            expected_record=None,
            desired_record=_record(status="acquiring", value_generation=None, value_ref=None),
            owner_operation_id=_OPERATION_ID,
        )
        .unwrap()
    )
    _ = store.claim_fence(path=path, fence=theirs, owner_uid=_uid()).unwrap()
    before = path.read_bytes()

    refusal = store.claim_fence(path=path, fence=mine, owner_uid=_uid())

    assert refusal.failure().message == (
        "a different pending metadata-effect fence already guards this record"
    )
    assert path.read_bytes() == before, "the other effect's guard is never overwritten"


def test_an_unsafe_or_unencodable_fence_never_reaches_the_filesystem(tmp_path):
    store = _fence_store()
    unencodable = _fence().MetadataFence(
        record_id=_RECORD_ID,
        effect_id=_EFFECT_ID,
        writer_role="acquisition-writer",
        revision=1,
        item_title=f"{_RECORD_ID}-m00000000000000000001-{_EFFECT_ID}",
        predecessor_sha256=_GENESIS,
        expected_record=None,
        desired_record={"ratio": 1.5},
        owner_operation_id=_OPERATION_ID,
    )
    broad = tmp_path / "state" / "pending-metadata-effects"
    broad.mkdir(parents=True, mode=0o755)
    unsafe_dir = broad / f"{_RECORD_ID}.json"
    readable = tmp_path / "other"
    readable.mkdir(mode=0o700)
    existing = readable / "fence.json"
    existing.write_text("{}", encoding="utf-8")
    existing.chmod(0o644)

    bug = store.claim_fence(path=existing, fence=unencodable, owner_uid=_uid())
    unsafe_read = store.claim_fence(path=existing, fence=_genesis_fence(), owner_uid=_uid())
    unsafe_write = store.claim_fence(path=unsafe_dir, fence=_genesis_fence(), owner_uid=_uid())

    assert bug.failure().error_type == "internal-bug"
    assert bug.failure().message == "a metadata fence is not canonical-JSON encodable"
    assert unsafe_read.failure().message.endswith("is more broadly accessible")
    assert unsafe_write.failure().message.endswith("is more broadly accessible")
    assert not unsafe_dir.exists()


def test_an_unsafe_stored_fence_is_reported_rather_than_read_as_absent(tmp_path):
    store = _fence_store()
    path = store.fence_path(state_dir=tmp_path / "state", record_id=_RECORD_ID).unwrap()
    _ = store.claim_fence(path=path, fence=_genesis_fence(), owner_uid=_uid()).unwrap()
    path.chmod(0o644)

    assert (
        store.read_fence(path=path, owner_uid=_uid())
        .failure()
        .message.endswith("is more broadly accessible")
    )


def test_resolving_a_fence_is_the_idempotent_removal_its_crash_window_needs(tmp_path):
    store = _fence_store()
    path = store.fence_path(state_dir=tmp_path / "state", record_id=_RECORD_ID).unwrap()
    _ = store.claim_fence(path=path, fence=_genesis_fence(), owner_uid=_uid()).unwrap()

    assert store.resolve_fence(path=path, owner_uid=_uid()).unwrap() is None
    assert store.resolve_fence(path=path, owner_uid=_uid()).unwrap() is None
    assert not path.exists()


# ---------------------------------------------------------------------------
# Reconciliation from the authoritative reread
# ---------------------------------------------------------------------------


def test_an_authoritative_desired_revision_advances_the_effect_and_drops_the_fence():
    module = _recovery()

    for outcome in module.ADAPTER_OUTCOMES:
        for created in (True, False):
            decision = module.reconcile_conditional_set(
                adapter_outcome=outcome, created_from_absence=created, reread="desired"
            ).unwrap()

            assert decision.disposition == "advance"
            assert (
                decision.retain_fence is False
            ), "an authoritative desired revision removes the fence before advancing"


def test_every_reread_that_cannot_see_the_desired_revision_retains_the_fence():
    module = _recovery()

    def _decide(*, outcome: str, created: bool, reread: str):
        return module.reconcile_conditional_set(
            adapter_outcome=outcome, created_from_absence=created, reread=reread
        ).unwrap()

    unknown = _decide(outcome="unknown", created=True, reread="expected")
    committed_without_proof = _decide(outcome="committed", created=True, reread="absent")
    unreadable = _decide(outcome="condition-failed", created=True, reread="unreadable")

    assert module.REREAD_OUTCOMES == ("desired", "expected", "absent", "different", "unreadable")
    assert module.FENCE_DISPOSITIONS == (
        "advance",
        "condition-failed",
        "uncommitted",
        "store-unavailable",
    )
    for decision in (unknown, committed_without_proof, unreadable):
        assert decision.disposition == "store-unavailable"
        assert decision.retain_fence is True


def test_only_an_absence_create_may_prove_the_condition_failed():
    module = _recovery()

    def _decide(*, outcome: str, created: bool, reread: str):
        return module.reconcile_conditional_set(
            adapter_outcome=outcome, created_from_absence=created, reread=reread
        ).unwrap()

    proved = _decide(outcome="condition-failed", created=True, reread="different")
    inconclusive = _decide(outcome="condition-failed", created=False, reread="different")
    without_a_different_revision = _decide(
        outcome="condition-failed", created=True, reread="expected"
    )

    assert proved.disposition == "condition-failed"
    assert proved.retain_fence is False
    assert (
        inconclusive.disposition == "store-unavailable"
    ), "a fence found present is conservatively treated as having a prior unknown outcome"
    assert inconclusive.retain_fence is True
    assert without_a_different_revision.disposition == "store-unavailable"
    assert without_a_different_revision.retain_fence is True


def test_an_uncommitted_first_call_drops_its_own_fence_but_never_an_inherited_one():
    module = _recovery()

    own = module.reconcile_conditional_set(
        adapter_outcome="uncommitted", created_from_absence=True, reread="absent"
    ).unwrap()
    inherited = module.reconcile_conditional_set(
        adapter_outcome="uncommitted", created_from_absence=False, reread="absent"
    ).unwrap()

    assert own.disposition == "uncommitted"
    assert own.retain_fence is False
    assert inherited.disposition == "uncommitted"
    assert (
        inherited.retain_fence is True
    ), "an earlier unknown attempt may still land, so its guard stays"


def test_an_unregistered_adapter_or_reread_outcome_is_a_caller_bug():
    module = _recovery()

    assert module.ADAPTER_OUTCOMES == ("committed", "condition-failed", "uncommitted", "unknown")
    assert (
        module.reconcile_conditional_set(
            adapter_outcome="maybe", created_from_absence=True, reread="desired"
        )
        .failure()
        .message
        == "maybe is not an adapter outcome"
    )
    assert (
        module.reconcile_conditional_set(
            adapter_outcome="unknown", created_from_absence=True, reread="shrug"
        )
        .failure()
        .message
        == "shrug is not an authoritative reread outcome"
    )


# ---------------------------------------------------------------------------
# Fence-to-operation relation validation and quarantine
# ---------------------------------------------------------------------------


def _terminal_operation(**changes: object):
    operation = _module("_lpm_operation")
    fields: dict[str, object] = {
        "operation_id": _OPERATION_ID,
        "command": "acquire",
        "phase": "terminal",
        "idempotency_key": _KEY,
        "accepted_at": "2026-09-30T09:00:00Z",
        "normalized_input": {"record_id": _RECORD_ID},
        "terminal_result": {
            "outcome": "success",
            "validated_at": "2026-09-30T09:00:04Z",
            "published_at": "2026-09-30T09:00:05Z",
            "expires_at": None,
            "failure_reason": None,
        },
        "ordered_effects": (
            "audit-append",
            "secret-value-set",
            "audit-append",
            "credential-conditional-set",
            "worker-record-remove",
        ),
        "completed_step": 2,
    }
    fields.update(changes)
    return operation.OperationRecord(**fields)  # pyright: ignore[reportArgumentType]


def _owned_fence(*, operation, index: int, writer_role: str):
    derived = (
        _module("_lpm_operation_identity").effect_id(operation=operation, index=index).unwrap()
    )
    return (
        _fence()
        .fence_for_effect(
            effect_id=derived,
            writer_role=writer_role,
            revision=1,
            expected_record=None,
            desired_record=_record(status="acquiring", value_generation=None, value_ref=None),
            owner_operation_id=operation.operation_id,
        )
        .unwrap()
    )


def test_a_fence_is_validated_against_its_owning_operation_rather_than_trusted():
    module = _recovery()
    operation = _terminal_operation()
    fence = _owned_fence(operation=operation, index=3, writer_role="acquisition-writer")

    assert module.fence_owner_defect(fence=fence, operation=operation, index=3) is None
    assert (
        module.fence_owner_defect(
            fence=fence, operation=_terminal_operation(command="reacquire"), index=3
        )
        == "a fence effect_id must be the owning position's derived identifier"
    )
    assert module.fence_owner_defect(fence=fence, operation=operation, index=9) == (
        "effect index is outside the operation's ordered effects"
    )
    assert module.fence_owner_defect(fence=fence, operation=operation, index=4) == (
        "a fence effect_id must be the owning position's derived identifier"
    )


def test_a_writer_role_mismatch_against_the_actor_table_is_relation_invalid():
    module = _recovery()
    operation = _terminal_operation()
    wrong_role = _owned_fence(operation=operation, index=3, writer_role="report-writer")
    failed = _terminal_operation(
        terminal_result={
            "outcome": "failure",
            "validated_at": None,
            "published_at": None,
            "expires_at": None,
            "failure_reason": "provider-rejected",
        }
    )
    on_failure = _owned_fence(operation=failed, index=3, writer_role="lifecycle-writer")

    assert module.fence_owner_defect(fence=wrong_role, operation=operation, index=3) == (
        "a fence writer_role must equal the owning phase's semantic audit actor"
    )
    assert module.fence_owner_defect(fence=on_failure, operation=failed, index=3) is None
    assert (
        module.fence_owner_defect(
            fence=_owned_fence(operation=operation, index=1, writer_role="acquisition-writer"),
            operation=operation,
            index=1,
        )
        is None
    )


def test_a_fence_naming_another_operation_or_an_unaudited_effect_is_refused():
    module = _recovery()
    operation = _terminal_operation()
    launch = _terminal_operation(
        phase="launch",
        terminal_result=None,
        ordered_effects=("worker-record-create", "audit-append", "credential-conditional-set"),
        completed_step=-1,
    )
    foreign = (
        _fence()
        .fence_for_effect(
            effect_id=_EFFECT_ID,
            writer_role="recovery-writer",
            revision=1,
            expected_record=None,
            desired_record=_record(status="acquiring", value_generation=None, value_ref=None),
            owner_operation_id=None,
        )
        .unwrap()
    )

    assert module.fence_owner_defect(fence=foreign, operation=operation, index=3) == (
        "a fence owner_operation_id must name its owning operation"
    )
    assert (
        module.fence_owner_defect(
            fence=_owned_fence(operation=launch, index=0, writer_role="acquisition-writer"),
            operation=launch,
            index=0,
        )
        == "worker-record-create is not an audited effect"
    )


def test_global_recovery_walks_fences_in_lexical_order_and_quarantines_only_failures():
    module = _recovery()
    attempted: list[str] = []
    unreconcilable = "b0000000-0000-4000-8000-000000000000"

    def _reconcile(record_id: str):
        attempted.append(record_id)
        if record_id == unreconcilable:
            return Failure(store_unavailable(message="a malformed fence"))
        return Success(None)

    pass_one = module.recover_pending_fences(
        record_ids=[
            "c0000000-0000-4000-8000-000000000000",
            unreconcilable,
            "a0000000-0000-4000-8000-000000000000",
        ],
        reconcile=_reconcile,
    )

    assert attempted == [
        "a0000000-0000-4000-8000-000000000000",
        unreconcilable,
        "c0000000-0000-4000-8000-000000000000",
    ], "fences are attempted in lexical record_id order"
    assert pass_one.quarantined == (unreconcilable,)
    assert pass_one.reconciled == (
        "a0000000-0000-4000-8000-000000000000",
        "c0000000-0000-4000-8000-000000000000",
    ), "one unreconcilable fence cannot wedge unrelated records"


def test_a_command_depending_on_a_quarantined_record_is_refused_and_others_are_not():
    module = _recovery()

    refused = module.quarantine_refusal(record_id=_RECORD_ID, quarantined={_RECORD_ID})

    assert refused.error_type == "store-unavailable"
    assert refused.message == (
        "this record is quarantined by an unreconciled metadata-effect fence"
    )
    assert module.quarantine_refusal(record_id=_OTHER_RECORD_ID, quarantined={_RECORD_ID}) is None


def test_a_pool_emptied_by_quarantine_is_unavailable_rather_than_exhausted():
    module = _recovery()

    partial = module.selectable_candidates(
        matching=[_RECORD_ID, _OTHER_RECORD_ID], quarantined={_RECORD_ID}
    ).unwrap()
    emptied = module.selectable_candidates(matching=[_RECORD_ID], quarantined={_RECORD_ID})
    never_matched = module.selectable_candidates(matching=[], quarantined={_RECORD_ID})

    assert partial == (_OTHER_RECORD_ID,)
    assert emptied.failure().error_type == "store-unavailable"
    assert emptied.failure().message == (
        "every otherwise matching record is quarantined by a metadata fence"
    )
    assert (
        never_matched.failure().error_type == "retryable-exhaustion"
    ), "exhaustion asks to be retried; a quarantined record is one nobody can read"
