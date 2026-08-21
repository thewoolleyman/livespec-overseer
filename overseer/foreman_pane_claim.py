"""Round-scoped foreman ownership claims for blocked-pane acts."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from time import time as time_time

import jsonio
import registry

__all__: list[str] = [
    "CLAIM_TTL_SECONDS",
    "PaneClaim",
    "active_pane_claim",
    "claim_path",
    "clear_pane_claim",
    "write_pane_claim",
]

CLAIM_FILE = ".foreman-pane-claim.json"
CLAIM_TTL_SECONDS = 120.0


@dataclass(frozen=True, kw_only=True)
class PaneClaim:
    owner: str
    session: str
    pane: str
    runtime: str
    session_identity: str
    question_fingerprint: str
    acquired_at: float
    expires_at: float


def claim_path(*, repo: str | os.PathLike[str] | Path, topic: str) -> Path:
    return Path(repo) / "tmp" / "overseer" / topic / CLAIM_FILE


def _claim_from_payload(*, payload: dict[str, object]) -> PaneClaim | None:
    owner = payload.get("owner")
    session = payload.get("session")
    pane = payload.get("pane")
    runtime = payload.get("runtime")
    session_identity = payload.get("session_identity")
    question_fingerprint = payload.get("question_fingerprint")
    acquired_at = payload.get("acquired_at")
    expires_at = payload.get("expires_at")
    if (
        not isinstance(owner, str)
        or not isinstance(session, str)
        or not isinstance(pane, str)
        or not isinstance(runtime, str)
        or not isinstance(session_identity, str)
        or not isinstance(question_fingerprint, str)
        or not isinstance(acquired_at, int | float)
        or not isinstance(expires_at, int | float)
    ):  # pragma: no cover
        return None
    return PaneClaim(
        owner=owner,
        session=session,
        pane=pane,
        runtime=runtime,
        session_identity=session_identity,
        question_fingerprint=question_fingerprint,
        acquired_at=float(acquired_at),
        expires_at=float(expires_at),
    )


def _read_pane_claim(*, path: Path) -> PaneClaim | None:
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    if jsonio.is_parse_failure(result=parsed):
        return None
    payload = parsed.unwrap()
    return None if payload is None else _claim_from_payload(payload=payload)


def write_pane_claim(*, repo: str | os.PathLike[str] | Path, topic: str, claim: PaneClaim) -> None:
    registry.atomic_write(
        path=claim_path(repo=repo, topic=topic),
        body=json.dumps(asdict(claim), indent=2, sort_keys=True) + "\n",
    )


def clear_pane_claim(*, repo: str | os.PathLike[str] | Path, topic: str) -> None:
    path = claim_path(repo=repo, topic=topic)
    try:
        path.unlink()
    except FileNotFoundError:  # pragma: no cover
        return


def active_pane_claim(
    *,
    repo: str | os.PathLike[str] | Path,
    topic: str,
    session: str,
    pane: str,
    now: float | None = None,
) -> PaneClaim | None:
    path = claim_path(repo=repo, topic=topic)
    try:
        claim = _read_pane_claim(path=path)
    except OSError:  # pragma: no cover
        return None
    current = time_time() if now is None else now
    if claim is None or claim.expires_at <= current:  # pragma: no cover
        return None
    if (
        claim.owner != "foreman" or claim.session != session or claim.pane != pane
    ):  # pragma: no cover
        return None
    return claim
