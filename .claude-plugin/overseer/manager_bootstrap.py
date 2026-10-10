"""Credential-free installed bootstrap for the LLM provider manager."""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Final

__all__: list[str] = [
    "CREDENTIAL_OVERRIDE_PREFIXES",
    "EXACT_CREDENTIAL_OVERRIDES",
    "INTERNAL_BUG_LINE",
    "companion_path",
    "is_credential_override",
    "main",
    "scrub_credential_overrides",
]

CREDENTIAL_OVERRIDE_PREFIXES: Final = ("ANTHROPIC_", "CLAUDE_", "OP_")
EXACT_CREDENTIAL_OVERRIDES: Final = (
    "CLAUDECODE",
    "LPM_ACQUISITION_READER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_ACQUISITION_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_PROVIDER_OBSERVER_OP_SERVICE_ACCOUNT_TOKEN",
    "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN",
)
INTERNAL_BUG_LINE: Final = (
    '{"version":1,"status":"error","error_type":"internal-bug",'
    '"message":"the isolated manager companion could not be established"}'
)

execv: Callable[[str, list[str]], None] = os.execv


def is_credential_override(*, name: str) -> bool:
    """Whether an inherited environment name belongs to the closed scrub set."""
    upper = name.upper()
    return upper in EXACT_CREDENTIAL_OVERRIDES or upper.startswith(CREDENTIAL_OVERRIDE_PREFIXES)


def scrub_credential_overrides(*, environ: MutableMapping[str, str]) -> tuple[str, ...]:
    """Remove credential overrides by name without inspecting their values."""
    removed = tuple(sorted(name for name in environ if is_credential_override(name=name)))
    for name in removed:
        del environ[name]
    return removed


def companion_path() -> Path:
    """The absolute isolated companion path shipped beside this bootstrap."""
    return Path(__file__).resolve().parent / "_lpm_commands.py"


def main() -> int:
    """Scrub first; answer help locally or replace this process with the companion."""
    _ = scrub_credential_overrides(environ=os.environ)
    if sys.argv[1:] == ["--help"]:
        _ = sys.stdout.write("usage: llm-provider-manager <subcommand> [options]\n")
        return 0
    companion = companion_path()
    with contextlib.suppress(OSError):
        execv(sys.executable, [sys.executable, "-I", "-S", str(companion), *sys.argv[1:]])
    _ = sys.stdout.write(f"{INTERNAL_BUG_LINE}\n")
    return 70


if __name__ == "__main__":
    raise SystemExit(main())
