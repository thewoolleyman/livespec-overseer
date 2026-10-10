"""Deterministic simultaneous-spread peer discovery from retained bindings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment, assignment_from_object
from _lpm_localstate import ensure_state_directory, read_local_record
from _lpm_results import ManagerError
from _lpm_tombstone import Tombstone, tombstone_from_object

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "simultaneous_spread_contribution",
]


@dataclass(frozen=True, kw_only=True)
class _SpreadBinding:
    consumer_run_id: str
    account_id: str
    provider: str
    kind: str
    purpose: str
    strategy: str
    lease_started_at: str
    lease_expires_at: str
    target_committed_at: str
    actual_lease_ended_at: str | None


def simultaneous_spread_contribution(
    *, state_dir: Path, owner_uid: int, assignment: Assignment, rollout_started_at: str
) -> Result[dict[str, object] | None, ManagerError]:
    """The canonical pair for `assignment`, or None when no retained peer qualifies."""
    current = cast("_SpreadBinding", _from_record(record=assignment))
    if current.strategy != "spread" or current.target_committed_at < rollout_started_at:
        return Success(None)
    bindings = _retained_bindings(state_dir=state_dir, owner_uid=owner_uid)
    if isinstance(bindings, Failure):
        return bindings
    peers = [
        peer
        for peer in bindings.unwrap()
        if _eligible(current=current, peer=peer, rollout_started_at=rollout_started_at)
    ]
    if not peers:
        return Success(None)
    peer = min(peers, key=lambda binding: _order_key(binding=binding))
    first, second = sorted((current, peer), key=lambda binding: _order_key(binding=binding))
    return Success(
        {
            "first_consumer_run_id": first.consumer_run_id,
            "first_account_id": first.account_id,
            "second_consumer_run_id": second.consumer_run_id,
            "second_account_id": second.account_id,
            "overlap_started_at": max(first.lease_started_at, second.lease_started_at),
            "overlap_ended_at": max(first.target_committed_at, second.target_committed_at),
        }
    )


def _retained_bindings(
    *, state_dir: Path, owner_uid: int
) -> Result[tuple[_SpreadBinding, ...], ManagerError]:
    retained: list[_SpreadBinding] = []
    tombstone_runs: set[str] = set()
    for family, parser in (
        ("tombstones", tombstone_from_object),
        ("assignments", assignment_from_object),
    ):
        directory = state_dir / family
        if not directory.exists():
            continue
        safe = ensure_state_directory(path=directory, owner_uid=owner_uid)
        if isinstance(safe, Failure):
            return safe
        for path in sorted(directory.glob("*.json")):
            stored = read_local_record(path=path, owner_uid=owner_uid)
            if isinstance(stored, Failure):
                return stored
            parsed = parser(parsed=stored.unwrap())
            if isinstance(parsed, Failure):
                return parsed
            binding = _from_record(record=parsed.unwrap())
            if binding is None:
                continue
            if family == "tombstones":
                tombstone_runs.add(binding.consumer_run_id)
            elif binding.consumer_run_id in tombstone_runs:
                continue
            retained.append(binding)
    return Success(tuple(retained))


def _from_record(*, record: Assignment | Tombstone) -> _SpreadBinding | None:
    if record.target_committed_at is None:
        return None
    request = record.request
    return _SpreadBinding(
        consumer_run_id=str(request["consumer_run_id"]),
        account_id=record.account_id,
        provider=str(request["provider"]),
        kind=str(request["kind"]),
        purpose=str(request["purpose"]),
        strategy=str(request["strategy"]),
        lease_started_at=record.lease_started_at,
        lease_expires_at=record.lease_expires_at,
        target_committed_at=record.target_committed_at,
        actual_lease_ended_at=record.actual_lease_ended_at,
    )


def _eligible(*, current: _SpreadBinding, peer: _SpreadBinding, rollout_started_at: str) -> bool:
    if peer.consumer_run_id == current.consumer_run_id or peer.account_id == current.account_id:
        return False
    if (peer.provider, peer.kind, peer.purpose, peer.strategy) != (
        current.provider,
        current.kind,
        current.purpose,
        "spread",
    ):
        return False
    if peer.target_committed_at < rollout_started_at:
        return False
    overlap = max(current.target_committed_at, peer.target_committed_at)
    return _contains(binding=current, instant=overlap) and _contains(binding=peer, instant=overlap)


def _contains(*, binding: _SpreadBinding, instant: str) -> bool:
    end = binding.actual_lease_ended_at or binding.lease_expires_at
    return binding.lease_started_at <= instant < end


def _order_key(*, binding: _SpreadBinding) -> tuple[str, str]:
    return binding.target_committed_at, binding.consumer_run_id
