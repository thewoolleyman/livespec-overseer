"""The isolated live exercise runs the installed agent client, or refuses before starting.

Integration-tier coverage for the isolated live exercise's agent-client contract, stated
in `SPECIFICATION/spec.md` and scenarized in `SPECIFICATION/scenarios.md` at v065.

Measured on the release host 2026-10-22 (work-item `overseer-fr8f`): `~/.local/bin/codex`
is a 368-byte bash shim that execs the bun global install under `~/.bun`, and the runner
bound the shim FILE alone. The scratch home hides `~/.bun`, so Codex never reached its
input prompt and the mismatch surfaced as a FAILED `bootstrap` lifecycle stage of the
authenticated run (evidence run 2026-10-22T04:31Z) rather than as a refusal before the
backend started.

These tests drive the real checked-in runner the way the operator does, on a PATH built
from symlinks so the verdict cannot depend on which agent clients the host happens to
have installed. The namespace itself is never started: the factory sandbox is denied
namespace creation, so the authenticated idle-prompt leg of the scenario remains a
host-captured release obligation. What is capturable here is the bind plan the runner
builds and the refusal it owes before any terminal backend starts.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

__all__: list[str] = []

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"

# Everything the runner itself executes before it starts a namespace. `bwrap` is
# deliberately ABSENT: these tests must never attempt namespace creation, and a refusal
# that named the client only after the `bwrap` probe would be invisible on a host without
# it.
_RUNNER_TOOLS = (
    "basename",
    "bash",
    "cat",
    "chmod",
    "cp",
    "dirname",
    "env",
    "find",
    "git",
    "grep",
    "head",
    "id",
    "install",
    "mkdir",
    "mktemp",
    "python3",
    "realpath",
    "rm",
    "sed",
    "sort",
)


def _runner_path(*, tmp_path: Path) -> Path:
    """Return a bin directory holding ONLY the tools the runner needs.

    No agent client can leak in from the ambient PATH, so "absent from PATH" is a
    property of the fixture rather than of the host the suite runs on.
    """
    bin_dir = tmp_path / "runner-bin"
    bin_dir.mkdir()
    for tool in _RUNNER_TOOLS:
        resolved = shutil.which(tool)
        assert resolved is not None, f"the live-exercise runner needs {tool} on PATH"
        (bin_dir / tool).symlink_to(resolved)
    return bin_dir


def _run(
    *, home: Path, path: str, agent: str, topic: str, evidence: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- fixed repo-owned script.
        [
            str(LIVE_EXERCISE),
            "run",
            "--backend",
            "tmux",
            "--agent",
            agent,
            "--topic",
            topic,
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
        env={"HOME": str(home), "PATH": path, "TMPDIR": os.environ.get("TMPDIR", "/tmp")},
    )


def _bun_style_launcher(*, home: Path) -> Path:
    """Install the release host's own shape: a bash shim into a bun global install."""
    launcher = home / ".local" / "bin" / "codex"
    launcher.parent.mkdir(parents=True)
    launcher.write_text(
        '#!/usr/bin/env bash\nexec "$HOME/.bun/bin/bun" "$HOME/.bun/bin/codex" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    return launcher


def test_an_agent_client_absent_from_path_refuses_before_any_backend_starts(
    *, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    evidence = tmp_path / "evidence"

    completed = _run(
        home=home,
        path=str(_runner_path(tmp_path=tmp_path)),
        agent="codex",
        topic="client-absent",
        evidence=evidence,
    )

    assert completed.returncode == 2, completed.stderr
    assert "codex" in completed.stderr
    assert not (evidence / "lifecycle.jsonl").exists(), completed.stderr
    assert not (evidence / "backend-runtime.env").exists(), completed.stderr


def test_an_unresolvable_script_launcher_refuses_and_names_the_client_path(
    *, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    launcher = _bun_style_launcher(home=home)
    evidence = tmp_path / "evidence"
    runner_bin = _runner_path(tmp_path=tmp_path)

    completed = _run(
        home=home,
        path=f"{launcher.parent}:{runner_bin}",
        agent="codex",
        topic="launcher-unresolvable",
        evidence=evidence,
    )

    assert completed.returncode == 2, completed.stderr
    assert str(launcher) in completed.stderr
    assert not (evidence / "lifecycle.jsonl").exists(), completed.stderr
    assert not (evidence / "backend-runtime.env").exists(), completed.stderr
