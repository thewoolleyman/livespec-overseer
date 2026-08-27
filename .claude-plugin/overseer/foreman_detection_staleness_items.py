"""Recognize the DETECTION-STALENESS items an attention view carries.

The routing floor ratified by v035 in `SPECIFICATION/spec.md` turns on what
counts as a DETECTION-STALENESS item in the first place — a report that a
convergence detection is overdue. That question is answered here, separately
from what is then done with such an item, because the two have different
inputs: this one reads a producer's view and nothing else, while routing reads
the tick's own roster.

RECOGNITION READS THE ITEM'S OWN DECLARED KIND, normalized for spelling, and
never the title text. A title heuristic would route ordinary items on the
strength of a word, and — worse in this direction — would silently stop routing
the moment a producer reworded a title, which is the failure nobody notices.
Normalizing the kind means a producer spelling it with underscores, in capitals,
or scoped to one named detection is recognized without this repository having to
track that producer's punctuation.

AN UNREADABLE VIEW IS DISTINGUISHED FROM AN EMPTY ONE. A view that cannot be
parsed yields None rather than an empty list, so a surface that carries no
detection-staleness item can never be confused with a surface nobody could read
— the two mean opposite things about whether anything needs routing.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import jsonio

__all__: list[str] = [
    "DETECTION_STALENESS_KIND",
    "UNIDENTIFIED_ITEM_ID",
    "DetectionStalenessItem",
    "detection_kind",
    "detection_staleness_items",
    "is_detection_staleness",
    "kind_slug",
]

DETECTION_STALENESS_KIND: Final[str] = "detection-staleness"
UNIDENTIFIED_ITEM_ID: Final[str] = "detection-staleness:unidentified"
_ATTRIBUTION_KEYS: Final[tuple[str, ...]] = ("plan", "tmux", "session_name")
_NON_SLUG_RUN: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, kw_only=True)
class DetectionStalenessItem:
    """A surfaced report that a convergence detection is overdue."""

    item_id: str
    kind: str
    plan: str | None
    title: str


def kind_slug(*, kind: str) -> str:
    """Normalize a producer's kind spelling to the form this surface matches."""
    return _NON_SLUG_RUN.sub("-", kind.lower()).strip("-")


def detection_kind(*, item: Mapping[str, object]) -> str | None:
    """The normalized detection-staleness kind the item DECLARES, or None."""
    kind = item.get("kind")
    if not isinstance(kind, str):
        return None
    slug = kind_slug(kind=kind)
    scoped = slug.startswith(f"{DETECTION_STALENESS_KIND}-")
    return slug if slug == DETECTION_STALENESS_KIND or scoped else None


def is_detection_staleness(*, item: Mapping[str, object]) -> bool:
    """True for an item whose own declared kind says detection is overdue."""
    return detection_kind(item=item) is not None


def _owning_plan(*, item: Mapping[str, object]) -> str | None:
    """The plan the view attributes the item to, under whichever key it used."""
    for key in _ATTRIBUTION_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _item(*, raw: Mapping[str, object], kind: str) -> DetectionStalenessItem:
    item_id = raw.get("id")
    title = raw.get("title")
    return DetectionStalenessItem(
        # An item carrying no id is still routed, under a stable placeholder:
        # dropping it would be exactly the silence the clause forbids.
        item_id=item_id if isinstance(item_id, str) and item_id else UNIDENTIFIED_ITEM_ID,
        kind=kind,
        plan=_owning_plan(item=raw),
        title=title if isinstance(title, str) else "",
    )


def detection_staleness_items(
    *, attention: Mapping[str, object] | None
) -> list[DetectionStalenessItem] | None:
    """The view's detection-staleness items; None where the view is unreadable."""
    if attention is None:
        return None
    raw_items = jsonio.as_list(value=attention.get("items"))
    if raw_items is None:
        return None
    items: list[DetectionStalenessItem] = []
    for raw in raw_items:
        parsed = jsonio.as_object(value=raw)
        kind = None if parsed is None else detection_kind(item=parsed)
        if parsed is not None and kind is not None:
            items.append(_item(raw=parsed, kind=kind))
    return items
