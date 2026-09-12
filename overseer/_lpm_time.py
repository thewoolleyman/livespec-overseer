"""Manager time capture and the one UTC RFC 3339-second spelling.

SPECIFICATION/contracts.md fixes exactly one
timestamp spelling for this operation — uppercase ``YYYY-MM-DDTHH:MM:SSZ``, no fractional
seconds and no numeric offset — and requires that input using any other spelling be
rejected with its command's invalid-input type BEFORE identity hashing or state mutation.
It further requires every manager time capture to read the UTC system clock and truncate
TOWARD THE EARLIER whole second, and every comparison and duration addition in one
decision to use that captured whole second without rounding.

Both rules are here because they are the same rule seen twice. A timestamp is compared
lexically all over this operation (lease fences, `expires_at`, worker deadlines, audit
ordering), and lexical comparison is only sound while every producer emits the SAME
fixed-width spelling. Rounding half-up would additionally let a capture land AFTER a
deadline it was taken before, which is the one direction a fence must never move.

Equality is deliberately inclusive at every boundary the contract states as "at or
after": a worker deadline has passed when the captured time EQUALS it, and a record is
expired when the captured time EQUALS `expires_at`. `is_at_or_after` is the single
spelling of that, so no call site re-derives it with a strict `>`.
"""

from __future__ import annotations

import datetime
import re
from typing import Final

__all__: list[str] = [
    "MANAGER_TIME_PATTERN",
    "add_seconds",
    "capture_manager_time",
    "is_at_or_after",
    "is_canonical_timestamp",
    "parse_manager_time",
]

_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"
MANAGER_TIME_PATTERN: Final = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def capture_manager_time(*, now: datetime.datetime) -> str:
    """Capture `now` as the canonical spelling, truncated toward the earlier second.

    `now` is normalized to UTC first, so a caller holding an offset-aware clock reading
    cannot smuggle a local wall-clock second into a record. A naive reading is treated as
    already-UTC: this operation's only clock source is the UTC system clock, and
    inventing a local-zone interpretation for a naive value would silently shift every
    derived deadline.
    """
    normalized = (
        now.replace(tzinfo=datetime.timezone.utc)
        if now.tzinfo is None
        else now.astimezone(datetime.timezone.utc)
    )
    return normalized.replace(microsecond=0).strftime(_FORMAT)


def is_canonical_timestamp(*, text: str) -> bool:
    """Whether `text` is the exact fixed-width spelling AND a real calendar instant.

    The pattern alone accepts `2026-02-31T00:00:00Z`; the parse is what refuses it. Both
    halves are required, and keeping them in one predicate is what stops a caller from
    validating the shape and then parsing somewhere else.
    """
    return parse_manager_time(text=text) is not None


def parse_manager_time(*, text: str) -> datetime.datetime | None:
    """The UTC instant `text` names, or None when it is not the canonical spelling."""
    if MANAGER_TIME_PATTERN.match(text) is None:
        return None
    try:
        parsed = datetime.datetime.strptime(text, _FORMAT)
    except ValueError:
        return None
    return parsed.replace(tzinfo=datetime.timezone.utc)


def add_seconds(*, timestamp: str, seconds: int) -> str | None:
    """`timestamp` advanced by `seconds`, or None when `timestamp` is not canonical.

    Every deadline in this operation is a stored canonical timestamp plus a configured
    whole-second interval, so the addition happens on the parsed instant and is re-emitted
    through the same formatter rather than by string arithmetic.
    """
    parsed = parse_manager_time(text=timestamp)
    if parsed is None:
        return None
    return capture_manager_time(now=parsed + datetime.timedelta(seconds=seconds))


def is_at_or_after(*, moment: str, limit: str) -> bool | None:
    """Whether `moment` is at or after `limit`; None when either is not canonical.

    Equality counts, because every contract boundary that uses this phrase — worker and
    attention deadlines, `expires_at`, validation age — states equality as the side that
    requires action.
    """
    left = parse_manager_time(text=moment)
    right = parse_manager_time(text=limit)
    if left is None or right is None:
        return None
    return left >= right
