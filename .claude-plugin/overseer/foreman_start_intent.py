"""Pre-spawn start-intent records for an authorized operator surface.

SPECIFICATION/spec.md requires a surface that STARTS a tracked session to
durably record a start-intent BEFORE the spawn, naming the action, the target
track, and the INVOKER on whose behalf it acts. The ORDERING is the whole
property: a record written after the act cannot describe an act that did not
return, so every caller here writes the record before it issues its spawn and
never after it.

SPECIFICATION/contracts.md puts the record under the writing surface's own
runtime state in the per-repository gitignored scratch area — the same
``tmp/overseer/foreman/`` root the convene-obligation records use — and never
under ``plan/``. It also states that a record carrying NO outcome MUST be read
as an attempt that FAILED rather than as work in progress. ``outcome`` is
therefore written as null AT INTENT TIME rather than omitted, so a reader never
has to decide whether an absent key means "not yet reconciled" or "written by an
older record shape"; the empty field is the attempted-and-failed signal itself.

The two failure cases carry DIFFERENT obligations, and both are discharged here.
A spawn that fails and RESOLVES leaves a surviving surface, which amends its
record with the failure and its error (:func:`amend_start_intent`). A spawn that
does not return leaves nobody to write anything, so the record stands
outcome-less and :func:`start_intent_reads_attempted_and_failed` reads it as the
attempt it was. Amending on BOTH resolutions is what keeps the empty field
discriminating: were a successful start also left outcome-less, "no outcome"
would mean nothing at all.

The write is fsynced and atomic (``registry.atomic_write``) because the case
this record exists for is a surface that dies moments later: a record still
sitting in a buffer when the process is killed is the same as no record at all.
"""

from __future__ import annotations

import json
import os
import re
from hashlib import sha256
from pathlib import Path
from typing import Final

import foreman_runtime_identity
import jsonio
import registry

__all__: list[str] = [
    "START_INTENT_KIND",
    "amend_start_intent",
    "read_start_intent",
    "record_start_intent",
    "resolve_invoker",
    "start_intent_path",
    "start_intent_reads_attempted_and_failed",
    "write_start_intent",
]

START_INTENT_KIND: Final[str] = "foreman-start-intent"

_SCHEMA_VERSION: Final[int] = 1
_FOREMAN_STATE: Final[Path] = Path("tmp") / "overseer" / "foreman"
_ROOT: Final[str] = "start-intents"
_SAFE_FILENAME: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9._-]+")
_DIGEST_LENGTH: Final[int] = 12


def resolve_invoker(*, proposal: dict[str, object], repo: str | os.PathLike[str]) -> str:
    """Name the invoker on whose behalf the surface acts.

    A proposal MAY name its own invoker, which is the operator or seat that asked
    for the action. When it does not, the surface is acting on its own behalf, so
    the invoker is the surface's own canonical identity for that repository — a
    true answer rather than a placeholder, which matters because the record's
    whole job is to say WHO made the attempt.
    """
    declared = proposal.get("invoker")
    if isinstance(declared, str) and declared != "":
        return declared
    return foreman_runtime_identity.canonical_session_name(repo=repo)


def start_intent_path(*, repo: str | os.PathLike[str], action_id: str, target: str) -> Path:
    """Locate one action's intent record for one target track.

    The filename carries a digest of the UNSANITIZED action and target, so two
    targets whose sanitized forms collide still get distinct records.
    """
    digest = sha256(f"{action_id}\0{target}".encode()).hexdigest()[:_DIGEST_LENGTH]
    return (
        Path(repo)
        / _FOREMAN_STATE
        / _ROOT
        / _safe(component=target)
        / f"{_safe(component=action_id)}-{digest}.json"
    )


def write_start_intent(
    *, repo: str | os.PathLike[str], action_id: str, target: str, invoker: str
) -> Path:
    """Write the pre-spawn intent record, raising when it cannot be persisted."""
    path = start_intent_path(repo=repo, action_id=action_id, target=target)
    record: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "kind": START_INTENT_KIND,
        "action_id": action_id,
        "target": target,
        "invoker": invoker,
        "outcome": None,
    }
    registry.atomic_write(
        path=path,
        body=json.dumps(record, indent=2, sort_keys=True) + "\n",
        raise_errors=True,
    )
    return path


def record_start_intent(
    *,
    repo: str | os.PathLike[str],
    action_id: str,
    target: str,
    proposal: dict[str, object],
) -> bool:
    """Record the intent for a start about to be spawned; False when it did not land.

    A caller that gets False MUST NOT spawn. Spawning past an unwritten intent
    would produce exactly the residue this record exists to abolish: an attempt
    with no evidence it was ever made.
    """
    try:
        _ = write_start_intent(
            repo=repo,
            action_id=action_id,
            target=target,
            invoker=resolve_invoker(proposal=proposal, repo=repo),
        )
    except OSError:
        return False
    return True


def read_start_intent(
    *, repo: str | os.PathLike[str], action_id: str, target: str
) -> dict[str, object] | None:
    """Read one action's intent record for one target, or None when it says nothing.

    A record that is absent, unreadable, or not a JSON object reads as None. That
    is NOT the attempted-and-failed signal: it is silence, and every caller here
    treats it as such rather than inventing a disposition for a record the
    surface never wrote.
    """
    path = start_intent_path(repo=repo, action_id=action_id, target=target)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    parsed = jsonio.parse_object(text=text)
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()


def start_intent_reads_attempted_and_failed(
    *, repo: str | os.PathLike[str], action_id: str, target: str
) -> bool:
    """Whether the record on file reads as an attempt that FAILED.

    SPECIFICATION/contracts.md: an intent record carrying NO outcome MUST be read
    as an attempt that failed, never as work in progress. A surface killed
    between issuing its spawn and returning cannot write an outcome, so the empty
    field is itself the signal — which is why this is a POSITIVE reading of a
    record that exists, and why a target with no readable record reads False.
    """
    record = read_start_intent(repo=repo, action_id=action_id, target=target)
    return record is not None and record.get("outcome") is None


def amend_start_intent(
    *, repo: str | os.PathLike[str], action_id: str, target: str, error: str | None
) -> None:
    """Reconcile the intent record with the outcome of the spawn it describes.

    ``error`` names the failure of a spawn that failed and RESOLVED, and is None
    for one that started. Only a surface that survives its own spawn reaches
    here, which is exactly why an UNAMENDED record means the surface did not.

    A missing record is never re-created: writing one from this side of the spawn
    would fabricate evidence of an attempt, which is the post-hoc shape the
    pre-spawn ordering exists to refuse. The write is fail-soft for the same
    reason the reading is safe — an unpersisted amendment leaves the record
    outcome-less, and outcome-less already reads as attempted-and-failed.
    """
    record = read_start_intent(repo=repo, action_id=action_id, target=target)
    if record is None:
        return
    outcome = {"status": "failed" if error is not None else "started", "error": error}
    registry.atomic_write(
        path=start_intent_path(repo=repo, action_id=action_id, target=target),
        body=json.dumps({**record, "outcome": outcome}, indent=2, sort_keys=True) + "\n",
    )


def _safe(*, component: str) -> str:
    return _SAFE_FILENAME.sub("-", component).strip(".-") or "unnamed"
