"""The ledger comment channel a worker objects through, and how one is read.

THE STORE IS THE LEDGER, NOT A LOCAL CACHE. Comments are read live with
``bd comments <work-item-id> --json`` through the repository's declared
credential wrapper. A predecessor sourced objections from
``<repo>/tmp/overseer/ledger-items/<epic>.json`` instead; measured 2026-08-30
(work-item ``overseer-ow7c.9``) NOTHING in this repository has ever written
that file, so a counter reading it answered zero for every ruling, every
fingerprint and every plan epic — a check whose only input never exists.

AN UNREADABLE LEDGER IS NOT "NO OBJECTIONS". :func:`read_comments` answers
``None`` when it could not read the ledger at all and a (possibly empty) tuple
when it could, and :func:`objection_tally` carries that distinction into its
``source`` field. Conflating the two is the whole defect above: both rendered
as a bare ``0``, so a missing input read exactly like a seat that never
objected.

THE WIRE FORMAT IS RELAXED. A comment registers an objection when ANY of its
lines begins with ``OBJECTION <fingerprint>:``. The predecessor required the
FIRST line, so a refusal that argued its jurisdictional grounds before naming
the ruling — which is what a seat refusing in careful prose actually writes —
matched nothing at all.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol, cast

import jsonio
from foreman_gather_sources import parse_repo_config, string_list

__all__: list[str] = [
    "SOURCE_LEDGER",
    "SOURCE_UNAVAILABLE",
    "CommentReader",
    "ObjectionTally",
    "comment_text",
    "is_objection",
    "latest_comment_at",
    "objection_tally",
    "read_comments",
]

SOURCE_LEDGER: Final[str] = "ledger"
SOURCE_UNAVAILABLE: Final[str] = "unavailable"
_READ_TIMEOUT_SECONDS: Final[float] = 10.0
_TEXT_KEYS: Final[tuple[str, ...]] = ("text", "body", "content")
_TIMESTAMP_KEYS: Final[tuple[str, ...]] = ("created_at", "at")


@dataclass(frozen=True, kw_only=True)
class ObjectionTally:
    """How many objections matched, and whether the ledger could be read at all."""

    count: int
    source: str


class CommentReader(Protocol):
    """Reads a work item's ledger comments, or answers None if it cannot."""

    def __call__(
        self, *, repo: Path, work_item_id: str
    ) -> tuple[dict[str, object], ...] | None: ...


def read_comments(*, repo: Path, work_item_id: str) -> tuple[dict[str, object], ...] | None:
    """A work item's ledger comments, or None when the ledger cannot be read.

    None is reserved for "no answer was obtained": the wrapper or ``bd`` is
    absent, the call timed out, it exited non-zero, or its output was not JSON.
    An empty tuple means the ledger answered and the item carries no comments.
    """
    config = parse_repo_config(repo=repo)
    wrapper = string_list(value=config.get("credential_wrapper")) if config is not None else None
    prefix = wrapper if wrapper is not None else []
    try:
        completed = subprocess.run(
            args=[*prefix, "bd", "comments", work_item_id, "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_READ_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    parsed = jsonio.parse_object(text=completed.stdout)
    if not jsonio.is_parse_failure(result=parsed):
        payload = parsed.unwrap()
        if payload is not None:
            return _comment_objects(values=jsonio.as_list(value=payload.get("comments")) or [])
    try:
        raw = cast("object", json.loads(completed.stdout))
    except ValueError:
        return None
    return _comment_objects(values=jsonio.as_list(value=raw) or [])


def comment_text(*, comment: object) -> str | None:
    """The prose a ledger comment carries, under whichever key ``bd`` emitted it."""
    payload = jsonio.as_object(value=comment)
    if payload is None:
        return None
    for key in _TEXT_KEYS:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None


def is_objection(*, comment: object, fingerprint: str) -> bool:
    """Whether ``comment`` registers an objection against the ruling ``fingerprint``.

    ANY line may carry the marker — see the module docstring on why the
    first-line-only predecessor discarded well-reasoned refusals.
    """
    marker = f"OBJECTION {fingerprint}:"
    text = comment_text(comment=comment) or ""
    return any(line.startswith(marker) for line in text.splitlines())


def objection_tally(*, comments: Sequence[object] | None, fingerprint: str) -> ObjectionTally:
    """Count matching objections, keeping an unread ledger its own condition."""
    if comments is None:
        return ObjectionTally(count=0, source=SOURCE_UNAVAILABLE)
    return ObjectionTally(
        count=sum(
            1 for comment in comments if is_objection(comment=comment, fingerprint=fingerprint)
        ),
        source=SOURCE_LEDGER,
    )


def latest_comment_at(*, comments: Sequence[object] | None) -> str | None:
    """The newest comment timestamp, or None when there is none to report."""
    if comments is None:
        return None
    timestamps = tuple(
        stamp for comment in comments if (stamp := _comment_timestamp(comment=comment)) is not None
    )
    return max(timestamps) if timestamps else None


def _comment_timestamp(*, comment: object) -> str | None:
    payload = jsonio.as_object(value=comment)
    if payload is None:
        return None
    for key in _TIMESTAMP_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _comment_objects(*, values: Sequence[object]) -> tuple[dict[str, object], ...]:
    return tuple(
        comment for comment in (jsonio.as_object(value=value) for value in values) if comment
    )
