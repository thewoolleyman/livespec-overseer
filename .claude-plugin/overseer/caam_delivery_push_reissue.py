"""The optional Remote Control re-issue after a successful account change."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from caam_delivery_push_state import KNOWN_HOSTS, Host, seconds

__all__: list[str] = ["reissue", "reissue_script"]

Runner = Callable[..., tuple[int, str]]


def reissue_script(*, path: Path) -> str | None:
    """The Remote Control re-issue script, when this checkout carries it."""
    return path.read_text(encoding="utf-8") if path.is_file() else None


def reissue(
    *, host: Host, script: str | None, run: Runner, settings: dict[str, object], home: Path
) -> str:
    if script is None:
        return "re-issue unavailable"
    return run(
        target=host.target,
        program=script,
        key=str(settings["ssh_key"]),
        known_hosts=str(home / KNOWN_HOSTS),
        timeout=seconds(settings=settings, key="reissue_timeout_s"),
    )[1]
