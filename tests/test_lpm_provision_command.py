"""The provisioning boundary: exact request, one atomic write, one secret-free receipt.

SPECIFICATION/contracts.md fixes the provisioning request as exactly `version`, non-empty
`provider`, `kind`, `purpose`, `consumer_run_id` and `target_ref` plus optional `strategy`
and `lease_seconds`; requires the `lease_seconds` range to be enforced BEFORE recovery,
target validation, selection or lease acquisition; requires success to write exactly the raw
credential bytes resolved from the selected `value_ref`; and requires a pre-commit failure to
release any acquired lease, leave the target BYTE-IDENTICAL, leave `consumer_run_id`
unconsumed and return exactly one typed refusal.

Every refusal case below reads the destination back and inspects the lease file, because the
contract's guarantee is about the WORLD after the refusal, not about the returned object. A
test that only asserted the error type would pass against a boundary that wrote the
credential and then reported a failure.

The receipt is asserted MEMBER-FOR-MEMBER rather than field-by-field. spec.md forbids the
manager from proxying, relaying or rewriting inference traffic, and the receipt is the one
thing this boundary hands back — so what matters is not only that the five members are
right, but that a `value_ref` or a raw value cannot ride along beside them.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []

_NOW = "2026-09-12T10:00:00Z"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_OTHER_RECORD_ID = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
_VALUE_REF = "op://llm-provider-manager-token-values/value/credential"


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_provision.py"
    assert module_path.is_file(), "overseer/_lpm_provision.py must exist"
    return (
        importlib.import_module("_lpm_provision"),
        importlib.import_module("_lpm_target"),
        importlib.import_module("_lpm_eligibility"),
        importlib.import_module("_lpm_record"),
        importlib.import_module("_lpm_selection_state"),
    )


def _uid() -> int:
    return os.geteuid()


def _record(records, **changes):
    fields = {
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": "one@example.test",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": _NOW,
        "expires_at": None,
        "last_validated": _NOW,
        "value_generation": "11111111-1111-4111-8111-111111111111",
        "value_ref": _VALUE_REF,
        "previous_value_ref": None,
    }
    fields.update(changes)
    return records.CredentialRecord(**fields)


def _request(provision, **changes):
    source: dict[str, object] = {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": "run-a",
        "target_ref": "tgt-0001",
    }
    source.update(changes)
    return provision.provision_request_from_object(parsed=source)


def _context(tmp_path, *, record=None, reader=None, now=_NOW, destination=None):
    provision, target, eligibility, records, selection_state = _modules()
    chosen = _record(records) if record is None else record
    return provision.ProvisionContext(
        records=(chosen,),
        state=selection_state.initial_selection_state(),
        issuance=target.TargetIssuance(
            reference="tgt-0001",
            consumer_run_id="run-a",
            adapter="isolated-run",
            destination=str(
                tmp_path / "run-a" / "credential" if destination is None else destination
            ),
            issued_at=_NOW,
            expires_at="2026-09-13T10:00:00Z",
        ),
        issuance_bound=False,
        observations={},
        policy=eligibility.EligibilityPolicy(
            now=now,
            maximum_validation_age_seconds=3600,
            health_strategy="none",
            health_floor_percent=0,
            account_reservations={},
        ),
        lease_path=tmp_path / "leases" / "anthropic.json",
        target_lock=target.TargetLock(
            path=tmp_path / "locks" / "target.lock",
            timeout_seconds=0.0,
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        ),
        owner_uid=_uid(),
        now=now,
        read_value=_reader(b"sk-ant-oat0-live") if reader is None else reader,
    )


def _reader(payload: bytes):
    returns = importlib.import_module("overseer._vendor.returns.result")

    def read(*, value_ref: str):
        assert value_ref == _VALUE_REF
        return returns.Success(payload)

    return read


def _refusal(provision, **changes) -> str:
    return _request(provision, **changes).failure().message


def test_the_request_normalizes_both_optional_members_and_round_trips():
    provision, *_ = _modules()

    request = _request(provision).unwrap()

    assert request.strategy == "consume-first"
    assert request.lease_seconds == 21600
    assert provision.provision_request_object(request=request) == {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": "run-a",
        "target_ref": "tgt-0001",
        "strategy": "consume-first",
        "lease_seconds": 21600,
    }
    spread = _request(provision, strategy="spread", lease_seconds=60).unwrap()
    assert (spread.strategy, spread.lease_seconds) == ("spread", 60)


def test_every_malformed_request_is_invalid_request_before_anything_is_reached():
    provision, *_ = _modules()

    assert "JSON object" in provision.provision_request_from_object(parsed=7).failure().message
    assert "carries" in _refusal(provision, unexpected="member")
    assert "integer 1" in _refusal(provision, version=2)
    assert "integer 1" in _refusal(provision, version=True)
    assert "non-empty string" in _refusal(provision, provider="")
    assert "non-empty string" in _refusal(provision, target_ref=7)
    assert "strategy must be" in _refusal(provision, strategy="cheapest")
    assert "lease_seconds must be" in _refusal(provision, lease_seconds=59)

    missing = dict(_request(provision).unwrap().__dict__)
    del missing["provider"]
    assert (
        provision.provision_request_from_object(parsed=missing).failure().error_type
        == "invalid-request"
    )


def test_a_provision_writes_exactly_the_selected_credential_and_returns_five_members(tmp_path):
    provision, *_ = _modules()
    request = _request(provision).unwrap()
    context = _context(tmp_path)

    receipt = provision.provision(request=request, context=context).unwrap()

    assert pathlib.Path(context.issuance.destination).read_bytes() == b"sk-ant-oat0-live"
    assert provision.receipt_object(receipt=receipt) == {
        "record_id": _RECORD_ID,
        "account_id": "one@example.test",
        "validated_at": _NOW,
        "purpose": "factory",
        "lease_expires_at": "2026-09-12T16:00:00Z",
    }
    assert tuple(provision.receipt_object(receipt=receipt)) == provision.RECEIPT_MEMBERS
    assert "value_ref" not in provision.receipt_object(receipt=receipt)
    assert context.lease_path.exists()


def test_an_unresolvable_target_refuses_before_selection_and_takes_no_lease(tmp_path):
    provision, *_ = _modules()
    request = _request(provision, target_ref="tgt-forged").unwrap()
    context = _context(tmp_path)

    refusal = provision.provision(request=request, context=context).failure()

    assert refusal.error_type == "invalid-request"
    assert not pathlib.Path(context.issuance.destination).exists()
    assert not context.lease_path.exists()


def test_an_empty_eligible_pool_is_retryable_exhaustion_with_no_lease_and_no_write(tmp_path):
    provision, _target, _eligibility, records, _state = _modules()
    request = _request(provision).unwrap()
    context = _context(tmp_path, record=_record(records, status="suspect"))

    refusal = provision.provision(request=request, context=context).failure()

    assert refusal.error_type == "retryable-exhaustion"
    assert not pathlib.Path(context.issuance.destination).exists()
    assert not context.lease_path.exists()


def test_an_account_leased_to_another_run_is_retryable_exhaustion_and_leaves_that_lease(tmp_path):
    provision, *_ = _modules()
    leases = importlib.import_module("_lpm_leases")
    localstate = importlib.import_module("_lpm_localstate")
    request = _request(provision).unwrap()
    context = _context(tmp_path)
    foreign = leases.new_lease(
        provider="anthropic",
        account_id="one@example.test",
        record_id=_OTHER_RECORD_ID,
        consumer_run_id="run-b",
        now=_NOW,
        lease_seconds=21600,
    ).unwrap()
    _ = localstate.write_local_record(
        path=context.lease_path, value=leases.lease_object(lease=foreign), owner_uid=_uid()
    )

    refusal = provision.provision(request=request, context=context).failure()

    assert refusal.error_type == "retryable-exhaustion"
    assert not pathlib.Path(context.issuance.destination).exists()
    assert leases.read_lease(path=context.lease_path, owner_uid=_uid()).unwrap() == foreign


def test_an_unreadable_credential_value_releases_the_lease_and_leaves_the_target_alone(tmp_path):
    provision, *_ = _modules()
    returns = importlib.import_module("overseer._vendor.returns.result")
    results = importlib.import_module("_lpm_results")
    destination = tmp_path / "run-a" / "credential"
    destination.parent.mkdir(mode=0o700)
    destination.write_bytes(b"prior-credential")
    destination.chmod(0o600)

    def read(*, value_ref: str):
        assert value_ref == _VALUE_REF
        return returns.Failure(results.store_unavailable(message="the values store is down"))

    context = _context(tmp_path, reader=read)
    refusal = provision.provision(request=_request(provision).unwrap(), context=context).failure()

    assert refusal.error_type == "store-unavailable"
    assert destination.read_bytes() == b"prior-credential"
    assert not context.lease_path.exists()


def test_a_definitively_uncommitted_write_is_provisioning_failed_and_releases_its_lease(tmp_path):
    provision, *_ = _modules()
    destination = tmp_path / "run-a" / "credential"
    destination.parent.mkdir(mode=0o700)
    destination.write_bytes(b"prior-credential")
    # More broadly accessible than 0600, so the writer refuses without rewriting.
    destination.chmod(0o644)

    context = _context(tmp_path)
    refusal = provision.provision(request=_request(provision).unwrap(), context=context).failure()

    assert refusal.error_type == "provisioning-failed"
    assert destination.read_bytes() == b"prior-credential"
    assert not context.lease_path.exists()


def test_a_held_target_lock_is_retryable_exhaustion_rather_than_a_definitive_failure(tmp_path):
    provision, *_ = _modules()
    locks = importlib.import_module("_lpm_locks")
    context = _context(tmp_path)
    held = locks.take_lock(
        path=context.target_lock.path,
        owner_uid=_uid(),
        timeout_seconds=0.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    ).unwrap()

    try:
        refusal = provision.provision(
            request=_request(provision).unwrap(), context=context
        ).failure()
    finally:
        locks.release_lock(held=held)

    assert refusal.error_type == "retryable-exhaustion"
    assert not pathlib.Path(context.issuance.destination).exists()
    assert not context.lease_path.exists()


def test_a_selected_record_missing_its_value_or_validation_is_an_internal_bug(tmp_path):
    provision, _target, _eligibility, records, _state = _modules()
    # Constructed directly: `_relation_defect` refuses this shape on the parse path, so a
    # record reaching selection without a value reference is a manager bug, not input.
    broken = _record(records, value_ref=None, value_generation=None)
    context = _context(tmp_path, record=broken)

    refusal = provision.provision(request=_request(provision).unwrap(), context=context).failure()

    assert refusal.error_type == "internal-bug"
    assert not context.lease_path.exists()


def test_a_lease_release_that_itself_fails_reports_store_unavailable(tmp_path, monkeypatch):
    provision, *_ = _modules()
    returns = importlib.import_module("overseer._vendor.returns.result")
    results = importlib.import_module("_lpm_results")

    def read(*, value_ref: str):
        assert value_ref == _VALUE_REF
        return returns.Failure(results.provisioning_failed(message="the adapter refused"))

    def release(*, path, consumer_run_id, record_id, owner_uid):
        assert (consumer_run_id, record_id) == ("run-a", _RECORD_ID)
        return returns.Failure(results.store_unavailable(message="the lease store is down"))

    monkeypatch.setattr(provision, "release_lease", release)
    context = _context(tmp_path, reader=read)

    refusal = provision.provision(request=_request(provision).unwrap(), context=context).failure()

    # The lease may still stand, so the honest answer is the unknown one — never the
    # domain failure that would tell a consumer the lease was cleaned up.
    assert refusal.error_type == "store-unavailable"
    assert "lease store" in refusal.message


def test_an_unusable_manager_clock_is_reported_rather_than_leased(tmp_path):
    provision, *_ = _modules()
    dataclasses = importlib.import_module("dataclasses")
    # `issuance_bound` keeps the reference resolvable past its expiry, which is what lets
    # this reach lease construction at all — an unbound reference refuses earlier, on the
    # same unusable clock.
    context = dataclasses.replace(_context(tmp_path, now="yesterday"), issuance_bound=True)

    refusal = provision.provision(request=_request(provision).unwrap(), context=context).failure()

    assert refusal.error_type == "internal-bug"
    assert not context.lease_path.exists()

    unbound = _context(tmp_path, now="yesterday")
    earlier = provision.provision(request=_request(provision).unwrap(), context=unbound).failure()
    assert earlier.error_type == "invalid-request"
