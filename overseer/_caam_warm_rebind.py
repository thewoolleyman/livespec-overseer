"""Re-bind a refreshed caam profile's saved identity through caam (overseer-jd42r2)."""

from __future__ import annotations

import json
import subprocess
from typing import Final, Protocol, cast

__all__: list[str] = ["CaamRunner", "LineLogger", "rebind_identity"]

_TOOL: Final = "claude"


class CaamProcess(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CaamRunner(Protocol):
    def __call__(self, *, args: tuple[str, ...]) -> CaamProcess: ...


class LineLogger(Protocol):
    def __call__(self, message: str) -> None: ...


def rebind_identity(*, name: str, caam_runner: CaamRunner, logger: LineLogger) -> None:
    """Re-bind a refreshed profile's saved identity through caam, and report any other outcome.

    The copy writes a new credential into caam's vault without caam. caam 0.1.25
    keeps an identity fingerprint, so the profile then reads `credential_changed`
    and caam refuses to switch onto it. `verify identity --repair` re-binds it to
    the account it already records, and never activates or replaces a credential
    (overseer-jd42r2). It runs right after the copy, while the new access token is
    still valid for the provider check the repair may make.
    """

    state = _rebind_state(name=name, caam_runner=caam_runner)
    if state != "verified":
        logger(
            f"FAIL warm: {name} was refreshed but caam reads its identity as {state}; "
            "a switch onto it may be refused until it is re-bound"
        )


def _rebind_state(*, name: str, caam_runner: CaamRunner) -> str:
    try:
        result = caam_runner(args=("verify", "identity", _TOOL, name, "--repair", "--json"))
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unchecked ({type(exc).__name__})"
    try:
        reply = cast(object, json.JSONDecoder().raw_decode(result.stdout.lstrip())[0])
    except ValueError:
        reply = None
    state = cast(dict[str, object], reply).get("state") if isinstance(reply, dict) else None
    return state if isinstance(state, str) and state else f"unreadable (exit {result.returncode})"
