"""A client the live exercise cannot make runnable is refused before any backend starts.

Measured on the release host 2026-10-22 (work-item `overseer-fr8f`): `~/.local/bin/codex`
is a 368-byte bash shim that executes the bun global install under `~/.bun`, and the
runner bound only the shim file. The scratch home hid `~/.bun`, so the namespaced Codex
never started -- and nothing noticed until the controller gave up sixty seconds later and
recorded a FAILED `bootstrap` stage. By then Herdr was already running inside the
namespace, so the evidence blamed the lifecycle for a client that was never runnable.

A client whose executed program the runner cannot resolve must therefore be refused UP
FRONT, naming the path it could not resolve, before the runner writes any evidence record
or starts any terminal backend. Each case below runs a full `run` rather than
`--plan-only`, so an empty evidence directory is itself the proof that nothing started.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"

# Every external tool the runner reaches around the point it decides about the agent
# client. The PATH a refusal case runs under carries ONLY these, so `codex` is absent BY
# CONSTRUCTION rather than by accident: a release host carrying its own `codex` would
# otherwise make the absent-client case pass for the wrong reason. `bwrap` is among them
# deliberately -- a sealed PATH without it would refuse every case for the wrong reason,
# and the assertion that matters is that the refusal beats the namespace launch.
_RUNNER_TOOLS = (
    "bash",
    "basename",
    "bwrap",
    "cat",
    "chmod",
    "dirname",
    "find",
    "git",
    "grep",
    "head",
    "id",
    "mkdir",
    "mktemp",
    "realpath",
    "rm",
    "sed",
)


def _sealed_bin(*, root: Path) -> Path:
    sealed = root / "sealed-bin"
    sealed.mkdir(parents=True, exist_ok=True)
    for tool in _RUNNER_TOOLS:
        resolved = shutil.which(tool)
        assert resolved is not None, f"this host provides no {tool}"
        (sealed / tool).symlink_to(resolved)
    return sealed


def _launcher(*, home: Path, body: str) -> Path:
    path = home / ".local" / "bin" / "codex"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _run(*, tmp_path: Path, search_path: str) -> subprocess.CompletedProcess[str]:
    evidence = tmp_path / "evidence"
    return subprocess.run(  # noqa: S603 -- fixed repo-owned script.
        [
            str(LIVE_EXERCISE),
            "run",
            "--backend",
            "herdr",
            "--agent",
            "codex",
            "--topic",
            "client-refusal",
            "--checkout",
            str(ROOT),
            "--evidence",
            str(evidence),
            "--",
            "/bin/true",
        ],
        check=False,
        text=True,
        capture_output=True,
        env={"HOME": str(tmp_path / "home"), "PATH": search_path, "TMPDIR": str(tmp_path)},
    )


def _refused(*, completed: subprocess.CompletedProcess[str], naming: str, evidence: Path) -> None:
    assert completed.returncode != 0, completed.stdout
    assert naming in completed.stderr, completed.stderr
    assert list(evidence.iterdir()) == [], "the runner wrote evidence before refusing"


def test_an_agent_client_absent_from_path_is_refused_by_name(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    completed = _run(tmp_path=tmp_path, search_path=str(_sealed_bin(root=tmp_path)))

    _refused(completed=completed, naming="codex", evidence=tmp_path / "evidence")


def test_a_launcher_running_a_program_that_is_not_installed_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    launcher = _launcher(home=home, body='exec codex-engine "$HOME/.bun/bin/codex" "$@"')
    search_path = f"{launcher.parent}:{_sealed_bin(root=tmp_path)}"

    completed = _run(tmp_path=tmp_path, search_path=search_path)

    _refused(completed=completed, naming=str(launcher), evidence=tmp_path / "evidence")


def test_a_launcher_running_a_missing_home_path_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    launcher = _launcher(home=home, body='exec "$HOME/.bun/bin/bun" "$HOME/.bun/bin/codex" "$@"')
    search_path = f"{launcher.parent}:{_sealed_bin(root=tmp_path)}"

    completed = _run(tmp_path=tmp_path, search_path=search_path)

    _refused(completed=completed, naming=str(launcher), evidence=tmp_path / "evidence")


def test_a_launcher_whose_program_and_script_split_across_home_trees_is_refused(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    runtime = home / ".bun" / "bin" / "bun"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    runtime.chmod(0o755)
    entry = home / ".opt" / "codex" / "cli.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("// codex\n", encoding="utf-8")
    launcher = _launcher(home=home, body='exec "$HOME/.bun/bin/bun" "$HOME/.opt/codex/cli.js" "$@"')
    search_path = f"{launcher.parent}:{_sealed_bin(root=tmp_path)}"

    completed = _run(tmp_path=tmp_path, search_path=search_path)

    _refused(completed=completed, naming=str(launcher), evidence=tmp_path / "evidence")
