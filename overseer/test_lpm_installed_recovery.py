"""Durable interruption fixtures for installed LPM subprocess scenarios."""

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import cast

from overseer.test_lpm_installed_services import OP_STATE

__all__: list[str] = [
    "interrupt_next_metadata_create",
    "interrupt_provision_after_target_commit",
    "write_registered_target",
]

_UID = 1000
_GID = 1000
_STATE = Path("home/fixture/.local/state/livespec-overseer/llm-provider-manager")
_START_EFFECTS = ["lease-create", "prepared-assignment-create", "target-write"]


def interrupt_provision_after_target_commit(*, root: Path, consumer_run_id: str) -> None:
    """Restore the exact durable state of a lost target-write checkpoint."""
    state = root / _STATE
    assignment_path = _record_path(
        state=state,
        family="assignments",
        identity=(consumer_run_id,),
    )
    assignment = _object(path=assignment_path)
    request = cast("dict[str, object]", assignment["request"])
    assignment["status"] = "prepared"
    assignment["target_committed_at"] = None
    _write_owned(path=assignment_path, value=assignment)
    for name in ("selection-state.json", "coexistence-proof.json"):
        (state / name).unlink(missing_ok=True)
    key = _digest(values=(consumer_run_id,))
    operation = {
        "version": 1,
        "operation_id": str(uuid.uuid4()),
        "command": "provision",
        "phase": "start",
        "idempotency_key": key,
        "accepted_at": assignment["lease_started_at"],
        "normalized_input": request,
        "terminal_result": None,
        "ordered_effects": _START_EFFECTS,
        "completed_step": 1,
    }
    _write_owned(
        path=_record_path(
            state=state,
            family="operations",
            identity=("provision", key),
        ),
        value=operation,
    )


def interrupt_next_metadata_create(*, root: Path) -> None:
    """Make the next metadata create commit but lose its authoritative reread."""
    path = root / OP_STATE.lstrip("/")
    state = _object(path=path)
    state["interrupt_next_create"] = True
    _write_owned(path=path, value=state)


def write_registered_target(*, destination: Path, value: bytes) -> None:
    """Create fixture-owned prior target bytes for an atomic-write refusal."""
    destination.write_bytes(value)
    os.chown(destination, _UID, _GID)
    destination.chmod(0o600)


def _record_path(*, state: Path, family: str, identity: tuple[str, ...]) -> Path:
    return state / family / f"{_digest(values=identity)}.json"


def _digest(*, values: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for value in values:
        encoded = value.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _object(*, path: Path) -> dict[str, object]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return cast("dict[str, object]", parsed)


def _write_owned(*, path: Path, value: object) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    os.chown(path, _UID, _GID)
    path.chmod(0o600)
