"""Durable-state inspection for installed LPM subprocess scenarios."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from overseer.test_lpm_installed_services import OP_STATE

__all__: list[str] = [
    "ReportSnapshot",
    "report_snapshot",
    "target_committed_at",
]

_STATE = Path("home/fixture/.local/state/livespec-overseer/llm-provider-manager")
_METADATA = "llm-provider-manager-token-metadata"


@dataclass(frozen=True, kw_only=True)
class ReportSnapshot:
    """Credential and run state whose equality proves a replay added no effect."""

    status: str
    lease_exists: bool
    assignment_exists: bool
    tombstone_exists: bool
    metadata_revisions: int
    effect_digest: str


def report_snapshot(
    *, root: Path, consumer_run_id: str, record_id: str, account_id: str
) -> ReportSnapshot:
    """Read the durable lifecycle, lease, close, and effect state for one run."""
    state = root / _STATE
    op_state = _object(path=root / OP_STATE.lstrip("/"))
    items = cast("list[object]", op_state["items"])
    revisions = _metadata_revisions(items=items, record_id=record_id)
    current = revisions[-1]
    fields = cast("dict[str, object]", current["fields"])
    record = cast("dict[str, object]", json.loads(str(fields["record"])))
    return ReportSnapshot(
        status=str(record["status"]),
        lease_exists=_record_path(
            state=state,
            family="leases",
            identity=("anthropic", account_id),
        ).exists(),
        assignment_exists=_record_path(
            state=state,
            family="assignments",
            identity=(consumer_run_id,),
        ).exists(),
        tombstone_exists=_record_path(
            state=state,
            family="tombstones",
            identity=(consumer_run_id,),
        ).exists(),
        metadata_revisions=len(revisions),
        effect_digest=_effect_digest(state=state, items=items),
    )


def target_committed_at(*, root: Path, consumer_run_id: str) -> str:
    """Read the committed target instant from a run's live assignment."""
    assignment = _object(
        path=_record_path(
            state=root / _STATE,
            family="assignments",
            identity=(consumer_run_id,),
        )
    )
    committed = assignment["target_committed_at"]
    assert isinstance(committed, str)
    return committed


def _metadata_revisions(*, items: list[object], record_id: str) -> list[dict[str, object]]:
    revisions: list[dict[str, object]] = []
    for item_object in items:
        item = cast("dict[str, object]", item_object)
        title = item.get("title")
        if (
            item.get("vault") == _METADATA
            and isinstance(title, str)
            and title.startswith(f"{record_id}-m")
        ):
            revisions.append(item)
    return sorted(revisions, key=lambda item: str(item["title"]))


def _effect_digest(*, state: Path, items: list[object]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(items, sort_keys=True, separators=(",", ":")).encode())
    if state.exists():
        for path in sorted(candidate for candidate in state.rglob("*") if candidate.is_file()):
            relative = path.relative_to(state)
            if relative.parts[0] == "locks":
                continue
            digest.update(str(relative).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _record_path(*, state: Path, family: str, identity: tuple[str, ...]) -> Path:
    digest = hashlib.sha256()
    for value in identity:
        encoded = value.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return state / family / f"{digest.hexdigest()}.json"


def _object(*, path: Path) -> dict[str, object]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return cast("dict[str, object]", parsed)
