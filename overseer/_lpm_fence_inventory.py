"""What mandatory global recovery must visit: every pending fence, by its record identity.

SPECIFICATION/contracts.md puts a pending metadata-effect fence at
`<manager-state>/pending-metadata-effects/<sha256(LP(record_id))>.json` and requires mandatory
global recovery to "attempt pending fences in lexical `record_id` order", quarantining "only
that record" when one cannot be reconciled. Both halves need a RECORD IDENTITY for every fence
file on disk, and the path digest is one-way — so the identity has to come out of the file.

THE IDENTITY IS TAKEN FROM THE FILE AND THEN BOUND BACK TO ITS PATH, which is what makes
reading an unvalidated fence safe to do at all. A stored `record_id` is accepted only when the
contract's own path derivation sends it to the very file it was read from, so a fence naming
another record cannot quarantine that record, and a forged identity can only ever name the
record whose fence slot it already occupies.

THE ATTRIBUTION READ IS DELIBERATELY NOT THE SAFE READ, and that is the one place this module
steps outside `_lpm_localstate`. An UNSAFE fence — wrongly owned, or more broadly accessible
than the owner — must still quarantine its own record, and the safe read refuses such a file
before it can report anything about it. So attribution reads the bytes itself, under the one
guard that cannot be given up: a symlink or non-regular path is refused UNREAD, because
following one would read outside this manager's state directory and a FIFO would never return.
Nothing else trusts the result — the fence a traversal actually reconciles is read again
through the safe read and validated in full.

A FENCE FILE NO IDENTITY CAN BE BOUND TO FAILS THE WHOLE PASS, rather than being skipped or
quarantined under some stand-in. Quarantine is a bound on WHICH records a pass may not touch,
and a fence naming no record supplies no bound at all; skipping it would let a command proceed
against a record whose pending effect nobody looked at, which is the one outcome these rules
exist to prevent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import parse_canonical_json
from _lpm_fence_store import fence_path
from _lpm_paths import LOCAL_PATH_FAMILIES
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "PENDING_FENCE_FAMILY",
    "family_record_files",
    "pending_fence_records",
]

PENDING_FENCE_FAMILY: Final = "pending-metadata-effect"


def pending_fence_records(*, state_dir: Path) -> Result[tuple[str, ...], ManagerError]:
    """Every record identity holding a pending fence, in the lexical order recovery visits."""
    records: list[str] = []
    for path in family_record_files(state_dir=state_dir, family=PENDING_FENCE_FAMILY):
        record_id = _attributed_record(path=path, state_dir=state_dir)
        if record_id is None:
            return Failure(
                store_unavailable(
                    message=f"{path.name} is a pending metadata-effect fence naming no "
                    "record identity this recovery could bind to its own path"
                )
            )
        records.append(record_id)
    return Success(tuple(sorted(records)))


def family_record_files(*, state_dir: Path, family: str) -> list[Path]:
    """Every candidate record file of one local family, in path order.

    A staged atomic replacement is named `.<file>.<random>` with no family suffix, so
    filtering on the suffix the contract's own path table declares is what keeps a
    half-written temporary out of a traversal that would otherwise read it as a record.
    """
    # The families this traversal walks come from the contract's own path table, so an
    # unregistered name would be a defect in that table rather than an operator condition.
    row = LOCAL_PATH_FAMILIES[family]
    root = state_dir / row.directory
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.name.endswith(row.suffix))


def _attributed_record(*, path: Path, state_dir: Path) -> str | None:
    """The record `path` is the fence of, or None when no identity binds back to this path."""
    stored = _unvalidated_object(path=path)
    if not isinstance(stored, dict):
        return None
    candidate = cast("dict[str, object]", stored).get("record_id")
    if not isinstance(candidate, str):
        return None
    # The fence family and its single-value identity come from that same path table, so this
    # derivation has no refusal to report either.
    located = fence_path(state_dir=state_dir, record_id=candidate).unwrap()
    return candidate if located == path else None


def _unvalidated_object(*, path: Path) -> object:
    """`path`'s decoded JSON value, read for ATTRIBUTION ONLY, or None when it has none.

    Every negative answer collapses to None on purpose: this read decides nothing about the
    fence beyond which record's slot it occupies, and the traversal's own safe read is what
    reports WHY an unusable fence is unusable.
    """
    if path.is_symlink() or not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    parsed = parse_canonical_json(text=raw)
    return None if isinstance(parsed, Failure) else parsed.unwrap()
