"""A pipefail shell script must not judge a pipeline through an early-exiting reader.

Under `set -o pipefail`, a reader that exits before its writer finishes (`grep -q`,
`grep -m1`, `head -n 1`, an `awk` that exits) closes the pipe; the writer then dies of
SIGPIPE and the pipeline reports a match as a failure. It loses the race only under
load, so it presents as a flake. A reader that consumes its whole input gives the same
verdict on an input larger than the 64 KiB pipe buffer as on a small one.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"
_EARLY_READER = re.compile(
    r"""\|\s*(?:
        grep\b(?:\s+-[^\s'\"]*)*?\s+(?:-[A-Za-z]*q[A-Za-z]*\b|--quiet\b|-m\s*1\b|-m1\b)
        |head\b\s+(?:-1\b|-n\s*1\b|-n1\b|-c\s*1\b|-c1\b)
        |awk\b[^\n]*\bexit\b
    )""",
    re.VERBOSE,
)


def _tracked_shell_paths() -> tuple[Path, ...]:
    completed = subprocess.run(  # noqa: S603 -- fixed git invocation.
        ["git", "ls-files"],  # noqa: S607 -- git is resolved from PATH by design.
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths: list[Path] = []
    for raw_path in completed.stdout.splitlines():
        path = ROOT / raw_path
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix == ".sh":
            paths.append(path)
            continue
        with path.open("rb") as handle:
            first = handle.readline(256)
        if first.startswith(b"#!") and b"sh" in first:
            paths.append(path)
    return tuple(paths)


def test_no_pipefail_script_judges_a_pipeline_through_an_early_exiting_reader() -> None:
    violations: list[str] = []
    for path in _tracked_shell_paths():
        text = path.read_text(encoding="utf-8")
        if "pipefail" not in text:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if _EARLY_READER.search(line):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    assert violations == []


def test_launcher_exec_tokens_gives_the_same_verdict_on_a_large_launcher(tmp_path: Path) -> None:
    text = LIVE_EXERCISE.read_text(encoding="utf-8")
    start = text.index("launcher_exec_tokens() {")
    end = text.index("\n}\n", start) + 3
    function = text[start:end]
    launcher = tmp_path / "launcher"
    launcher.write_text("#!/bin/sh\n" + "exec /bin/true arg\n" * 20000, encoding="utf-8")
    assert launcher.stat().st_size > 64 * 1024

    program = f'{function}\nlauncher_exec_tokens "$1"'
    completed = subprocess.run(  # noqa: S603 -- fixed bash invocation.
        ["bash", "-euo", "pipefail", "-c", program, "bash", str(launcher)],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )

    assert (completed.returncode, completed.stdout) == (0, "/bin/true\narg\n")
