"""Round-scoped provenance for a daemon-launched fresh-Codex wrap-up restart.

The fresh-Codex arm proves its successor from evidence that exists in the phase that
produces it (see :mod:`_supervisor_codex_fresh`), and its LAST proof — the fd-gated
live join — is bounded. When that bound is reached the round is kept open and the
``ready`` declaration retained, which is correct; what was missing was any record of
WHAT the daemon had just launched, so a later tick that finally saw the successor had
no way to tell it apart from an unrelated out-of-band identity change.

This is that record. It names the predecessor rollout the restart replaced, the
canonical successor rollout the ``/rename`` proved, the tmux session and pane the
respawn happened in, the repository the track is bound to, and the ledger-grounded
resume line together with whether it has already been delivered. Those five identity
facts are what a later reconciliation re-proves against live discovery before it will
consume anything; the resume pair is what lets it deliver a still-undelivered kick
exactly once.

Round-scoped by construction, exactly like ``resume_pending``: it lives inside the
track's injection-stamp entry, so ``write_injection_stamp`` (a fresh round) drops it
and ``clear_injection_stamp`` (the round closing) deletes it. It can never outlive the
round that launched it, and therefore can never authorize anything in a later one.

Every read is fail-closed: a member that is absent, the wrong type, or empty yields
``None`` rather than a partially-trusted record, because a provenance record that
cannot be fully compared cannot discriminate the daemon's own successor from anything
else that happens to be live in that pane.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import jsonio
from _registry_core import atomic_write, file_lock, resolve_stamp_store
from _registry_stamp_core import read_stamp_data, stamp_key

__all__: list[str] = [
    "CodexFreshRestart",
    "mark_codex_fresh_restart_resume_submitted",
    "read_codex_fresh_restart",
    "record_codex_fresh_restart",
]

_MEMBER = "codex_fresh_restart"


@dataclass(frozen=True, kw_only=True)
class CodexFreshRestart:
    """What one daemon-launched fresh-Codex restart attempt claimed to have created."""

    predecessor: str
    successor: str
    tmux: str
    pane: str
    repo: str
    resume: str
    resume_submitted: bool


def _text(*, entry: dict[str, object], member: str) -> str | None:
    value = entry.get(member)
    return value if isinstance(value, str) and value else None


def read_codex_fresh_restart(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> CodexFreshRestart | None:
    """The fresh-restart provenance recorded for this track's OPEN round, or None."""
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    entry = jsonio.as_object(value=data.get(stamp_key(repo=repo, topic=topic)))
    recorded = jsonio.as_object(value=entry.get(_MEMBER)) if entry is not None else None
    if recorded is None:
        return None
    predecessor = _text(entry=recorded, member="predecessor")
    successor = _text(entry=recorded, member="successor")
    tmux = _text(entry=recorded, member="tmux")
    pane = _text(entry=recorded, member="pane")
    bound_repo = _text(entry=recorded, member="repo")
    resume = _text(entry=recorded, member="resume")
    if (
        predecessor is None
        or successor is None
        or tmux is None
        or pane is None
        or bound_repo is None
        or resume is None
    ):
        return None
    return CodexFreshRestart(
        predecessor=predecessor,
        successor=successor,
        tmux=tmux,
        pane=pane,
        repo=bound_repo,
        resume=resume,
        resume_submitted=recorded.get("resume_submitted") is True,
    )


def record_codex_fresh_restart(
    *,
    repo: str,
    topic: str,
    record: CodexFreshRestart,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Persist what this restart attempt launched, preserving the round's own data.

    Written the moment the successor is NAMED — before the resume is submitted and
    before the bounded live-adoption proof — because those are exactly the two steps
    that can time out, and a record written only after they succeed would never exist
    when it is needed.
    """
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        current = dict(entry) if entry is not None else {}
        current[_MEMBER] = {
            "pane": record.pane,
            "predecessor": record.predecessor,
            "repo": record.repo,
            "resume": record.resume,
            "resume_submitted": record.resume_submitted,
            "successor": record.successor,
            "tmux": record.tmux,
        }
        data[key] = current
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")


def mark_codex_fresh_restart_resume_submitted(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Record that this round's resume line has been delivered to the successor.

    The at-most-once bound on a late-delivered resume: a reconciliation only pastes a
    resume the record still says is undelivered, and marks it here the moment the
    submit is CONFIRMED, so no later tick can deliver it a second time.
    """
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        recorded = jsonio.as_object(value=entry.get(_MEMBER)) if entry is not None else None
        if entry is None or recorded is None:
            return
        current = dict(entry)
        current[_MEMBER] = {**recorded, "resume_submitted": True}
        data[key] = current
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
