"""The append-only logical-revision protocol behind every conditional record write.

SPECIFICATION/contracts.md makes each logical metadata record an APPEND-ONLY CHAIN of
backend revision items. A revision title is exactly `<record_id>-m<revision>-<effect_id>`
with a 20-digit zero-padded revision beginning at `00000000000000000001`; each item has
exactly two application fields, `predecessor_sha256` (64 ASCII zeroes at revision one,
otherwise the lowercase SHA-256 of the PRECEDING revision's canonical `record` bytes) and
`record`; and the current logical record is the HIGHEST CONTIGUOUS VALID REVISION FROM
REVISION ONE.

Append-only is what makes the condition enforceable at all. A mutable item update has no
way to express "replace this only if it still holds exactly what I read", and no backend
in this operation may rely on title uniqueness — so the predecessor digest carries the
comparison instead, and a stale writer's create simply cannot be the next revision.

THE FIVE INVALID-CHAIN REASONS ARE DISTINCT FAILURES, not one "corrupt" bucket: a `gap`, a
`conflict` at one revision, a `title-mismatch`, a `predecessor-mismatch` and
`multiple-successors`. Each is reported as a secret-free descriptor, and the affected
record is made INELIGIBLE while every other valid record can still satisfy the request.

Byte-identical physical duplicates COLLAPSE to one logical revision. That is what makes a
fenced retry safe: a late duplicate of the byte-identical create adds another physical
copy of the same logical revision and cannot conflict with, overwrite or outrank a later
manager revision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import sha256_hex

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "FIRST_REVISION",
    "GENESIS_PREDECESSOR",
    "INVALID_CHAIN_REASONS",
    "REVISION_DIGITS",
    "ChainResolution",
    "RevisionItem",
    "predecessor_digest",
    "resolve_chain",
    "revision_title",
]

REVISION_DIGITS: Final = 20
FIRST_REVISION: Final = 1
GENESIS_PREDECESSOR: Final = "0" * 64

INVALID_CHAIN_REASONS: Final = (
    "gap",
    "conflict",
    "title-mismatch",
    "predecessor-mismatch",
    "multiple-successors",
)


@dataclass(frozen=True, kw_only=True)
class RevisionItem:
    """One physical backend item in a logical record's chain."""

    title: str
    predecessor_sha256: str
    record: str


@dataclass(frozen=True, kw_only=True)
class ChainResolution:
    """The current logical revision of one chain, or the reason it is invalid."""

    revision: int | None
    item: RevisionItem | None
    reason: str | None


def revision_title(*, record_id: str, revision: int, effect_id: str) -> str:
    """`<record_id>-m<20-digit revision>-<effect_id>` — the one title form."""
    return f"{record_id}-m{revision:0{REVISION_DIGITS}d}-{effect_id}"


def predecessor_digest(*, record: str | None) -> str:
    """The predecessor digest for a revision following `record`, or the genesis value."""
    if record is None:
        return GENESIS_PREDECESSOR
    return sha256_hex(data=record.encode("utf-8"))


def resolve_chain(*, record_id: str, items: list[RevisionItem]) -> ChainResolution:
    """Resolve `items` into the current logical revision, or the invalid-chain reason.

    An EMPTY chain is neither valid-with-a-record nor invalid: it is authoritative absence,
    reported as revision `None` with no reason. Absence and invalidity are deliberately
    distinguishable here, because the contract lets absence permit a genesis create while
    invalidity must refuse every mutation for that record.
    """
    by_revision: dict[int, set[tuple[str, str, str]]] = {}
    for item in items:
        parsed = _parsed_revision(record_id=record_id, title=item.title)
        if parsed is None:
            return ChainResolution(revision=None, item=None, reason="title-mismatch")
        by_revision.setdefault(parsed, set()).add(
            (item.title, item.predecessor_sha256, item.record)
        )
    if not by_revision:
        return ChainResolution(revision=None, item=None, reason=None)
    return _walked(by_revision=by_revision)


def _walked(*, by_revision: dict[int, set[tuple[str, str, str]]]) -> ChainResolution:
    if FIRST_REVISION not in by_revision:
        return ChainResolution(revision=None, item=None, reason="gap")
    current: RevisionItem | None = None
    revision = FIRST_REVISION
    while revision in by_revision:
        variants = by_revision[revision]
        if len(variants) > 1:
            # Several DISTINCT items at one revision. Byte-identical copies already
            # collapsed into a single set member, so this is a genuine conflict.
            reason = "multiple-successors" if current is not None else "conflict"
            return ChainResolution(revision=None, item=None, reason=reason)
        title, predecessor, record = next(iter(variants))
        expected = predecessor_digest(record=None if current is None else current.record)
        if predecessor != expected:
            return ChainResolution(revision=None, item=None, reason="predecessor-mismatch")
        current = RevisionItem(title=title, predecessor_sha256=predecessor, record=record)
        revision += 1
    highest = max(by_revision)
    if highest >= revision:
        return ChainResolution(revision=None, item=None, reason="gap")
    return ChainResolution(revision=revision - 1, item=current, reason=None)


def _parsed_revision(*, record_id: str, title: str) -> int | None:
    prefix = f"{record_id}-m"
    if not title.startswith(prefix):
        return None
    remainder = title[len(prefix) :]
    digits, separator, effect_id = remainder.partition("-")
    if separator == "" or effect_id == "" or len(digits) != REVISION_DIGITS:
        return None
    if not digits.isdigit() or int(digits) < FIRST_REVISION:
        return None
    return int(digits)
