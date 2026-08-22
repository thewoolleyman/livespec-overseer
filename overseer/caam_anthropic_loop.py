"""Console entry point for the caam Anthropic account-rotation pass."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streams
from caam_anthropic_pass import run_pass
from caam_switch import SwitchResult

__all__: list[str] = [
    "Flags",
    "LineWriter",
    "SwitchResult",
    "main",
    "parse_flags",
    "run_pass",
]

_EXPECTED_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    KeyError,
    IndexError,
    subprocess.SubprocessError,
)


class LineWriter(Protocol):
    def __call__(self, line: str) -> None: ...


class PassRunner(Protocol):
    def __call__(self, *, flags: Flags) -> int: ...


@dataclass(frozen=True, kw_only=True)
class Flags:
    scheduled: bool
    force: bool
    dry_run: bool
    no_models: bool
    no_warm: bool
    foreman_model: str | None


def parse_flags(*, argv: list[str]) -> Flags:
    values = {name: False for name in ("scheduled", "force", "dry_run", "no_models", "no_warm")}
    foreman_model: str | None = None
    index = 0
    while index < len(argv):
        lowered = argv[index].strip().lower()
        if lowered.startswith("--foreman-model"):
            value = argv[index].partition("=")[2]
            if not value and index + 1 < len(argv):
                index += 1
                value = argv[index]
            foreman_model = value.strip().lower()
        elif lowered.startswith("--scheduled"):
            values["scheduled"] = True
        elif lowered.startswith("--force"):
            values["force"] = True
        elif lowered.startswith("--dry-run"):
            values["dry_run"] = True
        elif lowered.startswith("--no-models"):
            values["no_models"] = True
        elif lowered.startswith("--no-warm"):
            values["no_warm"] = True
        index += 1
    return Flags(foreman_model=foreman_model, **values)


def main(
    *,
    argv: list[str] | None = None,
    stdout: LineWriter | None = None,
    pass_runner: PassRunner | None = None,
) -> int:
    writer = _stdout_line if stdout is None else stdout
    runner = _main_pass_runner(writer=writer) if pass_runner is None else pass_runner
    try:
        return runner(flags=parse_flags(argv=list(sys.argv[1:] if argv is None else argv)))
    except _EXPECTED_ERRORS as exc:
        writer(f"FAIL {type(exc).__name__}: {exc}")
        return 2


def _main_pass_runner(*, writer: LineWriter) -> PassRunner:
    def runner(*, flags: Flags) -> int:
        return run_pass(flags=flags, stdout=writer)

    return runner


class _StdoutLine:
    def __call__(self, line: str) -> None:
        streams.write_stdout(text=line + "\n")


_stdout_line = _StdoutLine()


if __name__ == "__main__":
    raise SystemExit(main())
