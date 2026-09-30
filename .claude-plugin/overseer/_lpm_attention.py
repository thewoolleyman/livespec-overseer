"""Pending-attention discovery: which credential identities are waiting on a human.

SPECIFICATION/contracts.md defines the list action exactly: `llm-provider-manager attention`
with no other argument "MUST then discover every pending artifact under the manager state
directory and emit exactly one secret-free single-line JSON object ... whose items contain
exactly `path`, `record_id`, `provider`, `account_id`, `reason` and `deadline`", each `path`
being "the absolute `<manager-state>/attention/<sha256>.json` path", with items sorted "by
the UTF-8 bytes of that absolute path". And, when the state cannot be read, the common
`store-unavailable` object with exit `4`.

THIS MODULE READS ARTIFACTS; IT NEVER CREATES, RESOLVES OR REMOVES ONE. The contract gives
artifact creation to the shared acquisition worker and artifact removal to the worker or to
mandatory recovery, and it gives status mutation to the two explicit local-operator actions.
A discovery pass that could also change a status would let simply LOOKING at the list consume
a human's pending decision.

ABSENCE AND UNAVAILABILITY ARE DIFFERENT ANSWERS, and conflating them fails in both
directions. A manager that has never held an artifact has no `attention/` directory at all,
and the honest answer is an EMPTY list: reporting a store outage there would tell every
operator on a healthy host that the credential store is broken. But an artifact that EXISTS
and cannot be trusted -- not owned by this manager, more broadly readable than owner-only,
or not a conforming record -- is `store-unavailable` and never a quiet skip, because a
skipped artifact is a credential identity waiting on a human that no operator is ever told
about. That is the exact failure this surface exists to prevent.

THE SORT IS EXPLICIT BECAUSE `glob` ORDER IS NOT A SORT. Filesystem iteration order is
neither stable across hosts nor meaningful, so identical state would otherwise produce
different output on a different machine -- and the contract states the ordering precisely
because an operator reading two lists needs to be able to diff them.

NOTHING READ OUT OF AN ARTIFACT REACHES A MESSAGE. Every refusal below names the DEFECT and
the member at fault; it never quotes the value. An artifact is written by a worker that has
just been near credential material, and this operation's output is required to be
secret-free, so quoting its bytes back out is the one thing a refusal must not do.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record
from _lpm_record import is_uuid4
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ATTENTION_ARTIFACT_MEMBERS",
    "ATTENTION_DIRECTORY",
    "ATTENTION_ITEM_MEMBERS",
    "ATTENTION_STATUSES",
    "ATTENTION_VERSION",
    "PENDING_ATTENTION",
    "AttentionItem",
    "attention_directory",
    "attention_item",
    "attention_item_object",
    "attention_items",
]

ATTENTION_VERSION: Final = 1
ATTENTION_DIRECTORY: Final = "attention"
PENDING_ATTENTION: Final = "pending"
ATTENTION_STATUSES: Final = (PENDING_ATTENTION, "resolved", "give-up")

ATTENTION_ITEM_MEMBERS: Final = (
    "path",
    "record_id",
    "provider",
    "account_id",
    "reason",
    "deadline",
)

ATTENTION_ARTIFACT_MEMBERS: Final = (
    "version",
    "record_id",
    "provider",
    "account_id",
    "reason",
    "deadline",
    "status",
)

_ARTIFACT_SUFFIX: Final = "*.json"
_NON_EMPTY_MEMBERS: Final = ("provider", "account_id", "reason")


@dataclass(frozen=True, kw_only=True)
class AttentionItem:
    """One pending artifact as the operator sees it: where it is, and what it is waiting for."""

    path: str
    record_id: str
    provider: str
    account_id: str
    reason: str
    deadline: str


def attention_directory(*, state_dir: Path) -> Path:
    """`<manager-state>/attention` — the one directory pending artifacts live in."""
    return state_dir / ATTENTION_DIRECTORY


def attention_item_object(*, item: AttentionItem) -> dict[str, object]:
    """The exact six-member item mapping, built from the declared member list."""
    return {member: getattr(item, member) for member in ATTENTION_ITEM_MEMBERS}


def attention_item(*, path: Path, owner_uid: int) -> Result[AttentionItem | None, ManagerError]:
    """One artifact's item, or `None` when it is absent or no longer pending.

    `None` is deliberately not a failure. An artifact removed between the directory listing
    and this read has been resolved or given up by the worker that owned it, which is the
    same answer as a stored non-pending status: it is no longer waiting on a human. Anything
    that means "this artifact exists and cannot be trusted" takes the failure rail instead.
    """
    stored = read_local_record(path=path, owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    parsed = stored.unwrap()
    if parsed is None:
        return Success(None)
    return _item_from_object(path=path, parsed=parsed)


def attention_items(
    *, state_dir: Path, owner_uid: int
) -> Result[tuple[AttentionItem, ...], ManagerError]:
    """Every pending artifact under `<manager-state>/attention`, sorted by absolute path."""
    directory = attention_directory(state_dir=state_dir)
    if directory.is_symlink():
        return Failure(store_unavailable(message=f"{ATTENTION_DIRECTORY} is a symlink"))
    if not directory.is_dir():
        return Success(())
    items: list[AttentionItem] = []
    for path in sorted(directory.glob(_ARTIFACT_SUFFIX), key=lambda entry: str(entry).encode()):
        resolved = attention_item(path=path, owner_uid=owner_uid)
        if isinstance(resolved, Failure):
            return Failure(resolved.failure())
        found = resolved.unwrap()
        if found is not None:
            items.append(found)
    return Success(tuple(items))


def _item_from_object(*, path: Path, parsed: object) -> Result[AttentionItem | None, ManagerError]:
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="an attention artifact must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    defect = _artifact_defect(source=source)
    if defect is not None:
        return Failure(store_unavailable(message=defect))
    if source["status"] != PENDING_ATTENTION:
        return Success(None)
    return Success(
        AttentionItem(
            path=str(path),
            record_id=str(source["record_id"]),
            provider=str(source["provider"]),
            account_id=str(source["account_id"]),
            reason=str(source["reason"]),
            deadline=str(source["deadline"]),
        )
    )


def _artifact_defect(*, source: dict[str, object]) -> str | None:
    """The first reason this artifact cannot be trusted, naming the member and never its value.

    Split into envelope and field halves for the same reason `_lpm_reports` splits its
    refusals: the envelope decides whether the MEMBER SET is the ratified one, and every
    field check below may then index the members it names without re-asking.
    """
    envelope = _envelope_defect(source=source)
    if envelope is not None:
        return envelope
    return _field_defect(source=source)


def _envelope_defect(*, source: dict[str, object]) -> str | None:
    if sorted(source) != sorted(ATTENTION_ARTIFACT_MEMBERS):
        return f"an attention artifact carries exactly {', '.join(ATTENTION_ARTIFACT_MEMBERS)}"
    version = source["version"]
    if isinstance(version, bool) or version != ATTENTION_VERSION:
        return "attention artifact version must be the integer 1"
    return None


def _field_defect(*, source: dict[str, object]) -> str | None:
    record_id = source["record_id"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return "attention artifact record_id must be a lowercase RFC 4122 UUIDv4"
    for member in _NON_EMPTY_MEMBERS:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return f"attention artifact {member} must be a non-empty string"
    deadline = source["deadline"]
    if not isinstance(deadline, str) or not is_canonical_timestamp(text=deadline):
        return "attention artifact deadline must be a UTC RFC 3339-second timestamp"
    if source["status"] not in ATTENTION_STATUSES:
        return f"attention artifact status must be one of: {', '.join(ATTENTION_STATUSES)}"
    return None
