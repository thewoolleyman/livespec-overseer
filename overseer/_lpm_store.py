"""The SecretStore boundary: its closed wire shapes and a hermetic in-memory backend.

SPECIFICATION/contracts.md makes `SecretStore` the manager's REPLACEABLE secret backend and
fixes every result that crosses the credential-role launcher boundary as exactly one UTF-8
JSON object with no extra fields: a metadata get returns `ok` with `item` null or one
valid-chain envelope, `invalid` with one invalid-chain descriptor, or `unavailable`; a list
returns `ok` with envelopes ordered by lexical `item_id` and descriptors ordered by lexical
`record_id`, or `unavailable`; an unconditional set returns `committed`, `uncommitted` or
`unavailable`; and a conditional set may additionally return `condition-failed`.

THOSE THREE NON-SUCCESS WORDS MEAN DIFFERENT THINGS AND MUST NOT BE MERGED. `uncommitted`
definitively says an attempted unconditional mutation made NO change; `condition-failed`
definitively says a conditional mutation made no change BECAUSE its predecessor comparison
failed; `unavailable` says the outcome is UNKNOWN and requires authoritative
reconciliation. Collapsing the third into either of the first two is how a write whose fate
nobody knows gets reported as a write that did not happen.

`item:null` ASSERTS AUTHORITATIVE ABSENCE, and only after the backend call and complete
chain validation found no valid or invalid chain for the requested record. A reader
`unavailable`, a deadline, an abnormal exit or any nonconforming output maps to
`store-unavailable` — NEVER to absence, because absence is what permits a genesis create.

The in-memory backend is a TEST BACKEND with the real protocol, not a stub: it enforces the
append-only chain, collapses byte-identical duplicates, and makes the same
committed/uncommitted/condition-failed distinctions. A fake that merely stored the latest
value would let every fence, retry and reconciliation test pass against a store that cannot
express the condition those rules exist to enforce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_revisions import (
    FIRST_REVISION,
    RevisionItem,
    predecessor_digest,
    resolve_chain,
    revision_title,
)

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "STORE_VERSION",
    "ConditionalSet",
    "InMemorySecretStore",
    "SecretStore",
    "invalid_chain_descriptor",
    "metadata_get_result",
    "metadata_item_envelope",
    "metadata_list_result",
    "set_result",
]

STORE_VERSION: Final = 1


def metadata_item_envelope(*, item_id: str, record: object) -> dict[str, object]:
    """The non-secret metadata envelope: exactly `item_id` and `record`."""
    return {"item_id": item_id, "record": record}


def invalid_chain_descriptor(*, record_id: str, reason: str) -> dict[str, object]:
    """The invalid-chain descriptor: exactly `record_id` and a closed `reason`."""
    return {"record_id": record_id, "reason": reason}


def metadata_get_result(*, status: str, payload: object = None) -> dict[str, object]:
    """One of the four closed metadata-get shapes."""
    if status == "ok":
        return {"version": STORE_VERSION, "status": "ok", "item": payload}
    if status == "invalid":
        return {"version": STORE_VERSION, "status": "invalid", "invalid": payload}
    return {"version": STORE_VERSION, "status": "unavailable"}


def metadata_list_result(
    *,
    status: str,
    items: list[dict[str, object]] | None = None,
    invalid: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """The closed metadata-list shape, or `unavailable`."""
    if status != "ok":
        return {"version": STORE_VERSION, "status": "unavailable"}
    return {
        "version": STORE_VERSION,
        "status": "ok",
        "items": [] if items is None else items,
        "invalid": [] if invalid is None else invalid,
    }


def set_result(*, status: str) -> dict[str, object]:
    """A `committed`, `uncommitted`, `condition-failed` or `unavailable` set result."""
    return {"version": STORE_VERSION, "status": status}


class SecretStore(Protocol):
    """The replaceable secret backend port every manager role talks through."""

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        """The current logical record for `record_id`, or authoritative absence."""
        ...

    def metadata_list(self) -> dict[str, object]:
        """Every chain's current logical revision, plus every invalid-chain descriptor."""
        ...

    def credential_conditional_set(self, *, request: ConditionalSet) -> dict[str, object]:
        """Append the one desired revision when the expected predecessor still holds."""
        ...


@dataclass(frozen=True, kw_only=True)
class ConditionalSet:
    """One conditional record write: the complete expectation, desire and effect id.

    `expected_record` is the complete canonical PREDECESSOR text, or None for expected
    absence. Carrying the whole record rather than a digest is what lets the backend
    enforce the comparison without trusting the caller's own hashing.
    """

    record_id: str
    effect_id: str
    expected_record: str | None
    desired_record: str


@dataclass(kw_only=True)
class InMemorySecretStore:
    """A hermetic backend implementing the real append-only revision protocol."""

    items: dict[str, list[RevisionItem]] = field(default_factory=dict)
    available: bool = True

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        """The closed metadata-get result for one record."""
        if not self.available:
            return metadata_get_result(status="unavailable")
        resolved = resolve_chain(record_id=record_id, items=self.items.get(record_id, []))
        if resolved.reason is not None:
            return metadata_get_result(
                status="invalid",
                payload=invalid_chain_descriptor(record_id=record_id, reason=resolved.reason),
            )
        if resolved.item is None:
            return metadata_get_result(status="ok", payload=None)
        return metadata_get_result(
            status="ok",
            payload=metadata_item_envelope(
                item_id=resolved.item.title, record=resolved.item.record
            ),
        )

    def metadata_list(self) -> dict[str, object]:
        """Every current revision by lexical `item_id`; every defect by lexical `record_id`."""
        if not self.available:
            return metadata_list_result(status="unavailable")
        envelopes: list[dict[str, object]] = []
        defects: list[dict[str, object]] = []
        for record_id in sorted(self.items):
            resolved = resolve_chain(record_id=record_id, items=self.items[record_id])
            if resolved.reason is not None:
                defects.append(
                    invalid_chain_descriptor(record_id=record_id, reason=resolved.reason)
                )
            elif resolved.item is not None:
                envelopes.append(
                    metadata_item_envelope(item_id=resolved.item.title, record=resolved.item.record)
                )
        envelopes.sort(key=lambda envelope: str(envelope["item_id"]))
        defects.sort(key=lambda defect: str(defect["record_id"]))
        return metadata_list_result(status="ok", items=envelopes, invalid=defects)

    def credential_conditional_set(self, *, request: ConditionalSet) -> dict[str, object]:
        """Append `request`'s one revision, or report why no change was made."""
        if not self.available:
            return set_result(status="unavailable")
        chain = self.items.setdefault(request.record_id, [])
        resolved = resolve_chain(record_id=request.record_id, items=chain)
        if resolved.reason is not None:
            return set_result(status="unavailable")
        current_item = resolved.item
        current = None if current_item is None else current_item.record
        if current_item is not None and _already_committed(
            item=current_item, revision=resolved.revision or FIRST_REVISION, request=request
        ):
            # Already committed: the desired record IS the current logical revision, in the
            # exact revision carrying this effect id. A fenced retry lands here.
            return set_result(status="committed")
        if current != request.expected_record:
            return set_result(status="condition-failed")
        next_revision = FIRST_REVISION if resolved.revision is None else resolved.revision + 1
        chain.append(
            RevisionItem(
                title=revision_title(
                    record_id=request.record_id,
                    revision=next_revision,
                    effect_id=request.effect_id,
                ),
                predecessor_sha256=predecessor_digest(record=current),
                record=request.desired_record,
            )
        )
        return set_result(status="committed")


def _already_committed(*, item: RevisionItem, revision: int, request: ConditionalSet) -> bool:
    if item.record != request.desired_record:
        return False
    return item.title == revision_title(
        record_id=request.record_id, revision=revision, effect_id=request.effect_id
    )
