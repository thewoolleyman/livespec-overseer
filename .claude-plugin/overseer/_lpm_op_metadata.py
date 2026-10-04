"""The metadata vault read as logical chains, and the two closed read answers built on them.

SPECIFICATION/contracts.md makes each logical metadata record "an append-only chain of
1Password revision items" and requires metadata get and list to "expose only each chain's
current logical revision through the envelope above, using its revision title as `item_id`,
while retaining a secret-free diagnostic for an invalid chain". Turning a flat vault
listing into those chains is this module's whole job; deciding which revision is current is
`_lpm_revisions`, and shaping the answer is `_lpm_store`.

THE WHOLE VAULT IS JUDGED, NOT JUST THE RECORD ASKED FOR. "Any other item outside the
operation's closed item grammar remains `store-unavailable`." So an item whose title no
revision grammar accepts makes every read of that vault unavailable, even a get for an
unrelated record — the grammar is a property of the vault, and a reader that skipped past a
stranger would be asserting absence about a vault it could not account for. Only AFTER
grammar membership holds does a get narrow to its own record, which is also what keeps it
from reading another record's fields.

THE ENVELOPE CARRIES THE DECODED VALUE. The contract fixes `record` as "whatever canonical
JSON value decoded from that item's canonical `record` field", so the stored text is decoded
exactly once, here, and the decoded value travels with the chain. Decoding at the envelope
instead would mean a second parse whose failure branch nothing could reach, and forwarding
the text would push the parse past a boundary the contract has already closed.

CANONICALITY IS CHECKED, NOT ASSUMED. A stored `record` that is "non-UTF-8, non-canonical,
unparseable or contains a duplicate member MUST be `store-unavailable`". Non-canonical
matters as much as the rest because `predecessor_sha256` is taken over the canonical
`record` bytes: a spelling no second encoder reproduces would break every later comparison
for a reason nobody introduced, and it would do so silently.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import canonical_json_text, parse_canonical_json
from _lpm_onepassword import METADATA_VAULT, NAMESPACE_ITEM_TITLE
from _lpm_op_items import OpItem
from _lpm_op_vault import VaultAccess, namespace_bound_summaries
from _lpm_revisions import RevisionItem, revision_title_parts
from _lpm_store import (
    chain_get_result,
    chain_list_result,
    metadata_get_result,
    metadata_list_result,
)

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "REVISION_FIELD_LABELS",
    "VaultChains",
    "metadata_chains",
    "metadata_get_answer",
    "metadata_list_answer",
]

# "It MUST have exactly two application fields: text `predecessor_sha256` ... and text
# `record`". Exactly, in both directions: a missing one and an extra one are the same defect,
# because the envelope is the whole item rather than a minimum.
REVISION_FIELD_LABELS: Final = ("predecessor_sha256", "record")


@dataclass(frozen=True, kw_only=True)
class VaultChains:
    """One enumeration's logical chains, plus the value each revision's field decoded to.

    It is ALSO the `RecordValue` for that read: calling it with one of its own revisions
    yields that revision's decoded record. Carrying the two together is what keeps the
    decode single — the chain and the values came out of the same enumeration, so there is
    no second mapping that can drift from it.
    """

    items: dict[str, list[RevisionItem]]
    decoded: dict[str, object]

    def __call__(self, *, item: RevisionItem) -> object:
        """The envelope `record` for one revision of this read: its decoded value."""
        return self.decoded[item.title]


def metadata_chains(
    *, access: VaultAccess, namespace: Mapping[str, str], record_id: str | None
) -> Result[VaultChains, str]:
    """Read the namespace-bound metadata vault into logical chains, or say why it cannot be.

    `record_id` narrows which chains are READ, never which items are JUDGED: a get supplies
    it so the fields of other records are never fetched, and a list passes None.
    """
    listing = namespace_bound_summaries(access=access, vault=METADATA_VAULT, expected=namespace)
    if isinstance(listing, Failure):
        return listing
    items: dict[str, list[RevisionItem]] = {}
    decoded: dict[str, object] = {}
    for summary in listing.unwrap():
        if summary.title == NAMESPACE_ITEM_TITLE:
            continue
        parts = revision_title_parts(title=summary.title)
        if parts is None:
            return Failure("an item outside the metadata vault's closed grammar")
        if record_id is not None and parts.record_id != record_id:
            continue
        stored = _stored_revision(access=access, summary=summary)
        if isinstance(stored, Failure):
            return stored
        revision, value = stored.unwrap()
        items.setdefault(parts.record_id, []).append(revision)
        decoded[revision.title] = value
    return Success(VaultChains(items=items, decoded=decoded))


def metadata_get_answer(
    *, access: VaultAccess, namespace: Mapping[str, str], record_id: str
) -> dict[str, object]:
    """One record's closed metadata-get result: absence, one envelope, or its defect.

    A failed chain read becomes `unavailable` and NEVER `item:null`. That is the whole
    reason this answer is not computed from whatever the backend managed to return: absence
    is what licenses a genesis create, so a store nobody could read must not be allowed to
    assert it.
    """
    chains = metadata_chains(access=access, namespace=namespace, record_id=record_id)
    if isinstance(chains, Failure):
        return metadata_get_result(status="unavailable")
    read = chains.unwrap()
    return chain_get_result(
        record_id=record_id, items=read.items.get(record_id, []), record_value=read
    )


def metadata_list_answer(*, access: VaultAccess, namespace: Mapping[str, str]) -> dict[str, object]:
    """Every chain's current logical revision, plus every invalid-chain descriptor."""
    chains = metadata_chains(access=access, namespace=namespace, record_id=None)
    if isinstance(chains, Failure):
        return metadata_list_result(status="unavailable")
    read = chains.unwrap()
    return chain_list_result(chains=read.items, record_value=read)


def _stored_revision(
    *, access: VaultAccess, summary: OpItem
) -> Result[tuple[RevisionItem, object], str]:
    """One revision item's two fields and its decoded record, or the shape-only defect.

    The returned `RevisionItem` keeps the record as its STORED TEXT, because that text is
    what `predecessor_sha256` is computed over; the decoded value travels beside it for the
    envelope. Keeping both is what lets one read serve a digest comparison and a consumer.
    """
    stored = access.fields(vault=METADATA_VAULT, item_id=summary.item_id)
    if isinstance(stored, Failure):
        return stored
    fields = stored.unwrap()
    if sorted(fields) != sorted(REVISION_FIELD_LABELS):
        return Failure("a revision item whose application fields are not the declared two")
    text = fields["record"]
    parsed = parse_canonical_json(text=text)
    if isinstance(parsed, Failure):
        return Failure("a revision item whose record field is not one JSON value")
    value = parsed.unwrap()
    canonical = canonical_json_text(value=value)
    if isinstance(canonical, Failure) or canonical.unwrap() != text:
        return Failure("a revision item whose record field is not canonical")
    revision = RevisionItem(
        title=summary.title, predecessor_sha256=fields["predecessor_sha256"], record=text
    )
    return Success((revision, value))
