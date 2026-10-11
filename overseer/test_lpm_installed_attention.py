"""Attention-artifact fixture for installed LPM subprocess scenarios."""

import json
import os
from pathlib import Path

__all__: list[str] = [
    "write_attention",
]

_UID = 1000
_GID = 1000
_STATE = Path("home/fixture/.local/state/livespec-overseer/llm-provider-manager")


def write_attention(*, root: Path, record_id: str) -> str:
    """Write one pending artifact and return its chroot-absolute public path."""
    directory = root / _STATE / "attention"
    directory.mkdir(mode=0o700, parents=True)
    boundary = root / "home" / "fixture"
    current = directory
    while current != boundary:
        os.chown(current, _UID, _GID)
        current.chmod(0o700)
        current = current.parent
    artifact = directory / f"{record_id}.json"
    artifact.write_text(
        json.dumps(
            {
                "version": 1,
                "type": "browser-verification-wall",
                "record_id": record_id,
                "operation_id": "9b2c4d6e-8f10-4a3b-9c5d-7e1f2a3b4c5d",
                "worker_pid": 321,
                "worker_start_ticks": 654,
                "provider": "anthropic",
                "account_id": "fixture-anthropic-account",
                "reason": "captcha",
                "status": "pending",
                "raised_at": "2026-10-11T17:00:00Z",
                "deadline": "2026-10-11T18:00:00Z",
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    os.chown(artifact, _UID, _GID)
    artifact.chmod(0o600)
    return f"/{artifact.relative_to(root)}"
